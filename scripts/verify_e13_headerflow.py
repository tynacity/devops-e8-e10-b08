"""Restore the frozen A shipment and verify B's three E13 consumption cases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA = '4feb035daf0f429bbd0e85986887bc47ac1c0dcb757f465c2bfe2e4e3cdc0bda'
REPORT_SHA = 'c86c2db4b14c84df6f736044e6fcc3993f0a0a04cff7076355996d45ec0d323c'
BASE = '88af5173a249ee4f30f3d7da51b20169db47d234'
TARGET = '961f40cb8fbb71de304b782ff754522d59d51305'
A_JOB = 'job-6e7f20bbfc9c49adb76d8432ce08f542'
A_TRACE = 'trace-027e97ba3b724c3bb84a2026e4dc6ac8'
BRANCH = 'e13e14/input-A-headerflow'
CANDIDATE_SHA = '3836baf65c06a241b58505606714f4d443067ae894390471335ff212db1437dd'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def course(path):
    return '/course/' + path.relative_to(ROOT).as_posix()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], timeout=60).decode().strip()


def restore(archive):
    raw = archive.read_bytes()
    require(sha(raw) == ARCHIVE_SHA, 'Wrong A attachment SHA-256')
    with zipfile.ZipFile(archive) as packet:
        name, = [n for n in packet.namelist() if n.count('/') == 1 and n.endswith('/FILES.json')]
        prefix = name.removesuffix('FILES.json')
        members = {x['path']: x for x in json.loads(packet.read(name))}

        def read(relative):
            b = packet.read(prefix + relative)
            meta = members[relative]
            require(sha(b) == meta['sha256'] and len(b) == meta['bytes'], 'Wrong archive member: ' + relative)
            return b

        items = {rel: read(rel) for rel in ('project-A/project.bundle', 'project-A/candidate.Dockerfile',
                                           'A-e11a/incremental-check.json', 'A-e11a/result.json', 'handoff.json')}
        require(sha(items['A-e11a/incremental-check.json']) == REPORT_SHA, 'Wrong A report bytes')
        require(sha(items['project-A/candidate.Dockerfile']) == CANDIDATE_SHA, 'Wrong A candidate bytes')
    data = ROOT / 'data'
    data.mkdir(exist_ok=True)
    dest = Path(tempfile.mkdtemp(prefix='e13-headerflow-', dir=data))
    for key, value in items.items():
        (dest / key.rsplit('/', 1)[-1]).write_bytes(value)
    repo = dest / 'project'
    subprocess.run(['git', 'clone', '-q', '-b', BRANCH, str(dest / 'project.bundle'), str(repo)],
                   check=True, timeout=60)
    require(git(repo, 'rev-parse', 'HEAD') == TARGET and not git(repo, 'status', '--porcelain'),
            'A target checkout does not match the frozen input')
    git(repo, 'merge-base', '--is-ancestor', BASE, TARGET)
    report = dest / 'incremental-check.json'
    altered = dest / 'tampered-incremental-check.json'
    altered.write_bytes(report.read_bytes() + b'\n')
    normal = dict(mode='e13-b', profile='explicit', base=BASE, target=TARGET, repo=course(repo),
                  candidate=course(dest / 'candidate.Dockerfile'), expected_output='1', build_timeout=600,
                  report=course(report), producer_manifest=course(dest / 'result.json'), report_sha256=REPORT_SHA)
    cases = [('stale', dict(normal, target=BASE), 'STALE_REPORT'),
             ('tampered', dict(normal, report=course(altered)), 'ARTIFACT_HASH_MISMATCH'),
             ('accept', normal, None)]
    return dest, repo, cases


def run(archive):
    dest, repo, cases = restore(archive)
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='e13-b-consume-', dir=work))
    tool_sha = git(ROOT, 'rev-parse', 'HEAD')
    require(not git(ROOT, 'status', '--porcelain'), 'Use a clean, committed B checkout')
    print('EVIDENCE_DIR=' + str(output), flush=True)
    verified = []
    for label, req, code in cases:
        print('CASE=' + label, flush=True)
        request_path = dest / (label + '-request.json')
        request_path.write_text(json.dumps(req, indent=2) + '\n')
        with (output / (label + '.log')).open('wb') as log:
            rc = subprocess.run([sys.executable, 'run_e11e12.py', 'run',
                                 '--request', str(request_path), '--out', str(output / label)],
                                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
        run_dir = output / label
        result_path = run_dir / 'result.json'
        require(result_path.is_file(), f'{label}: no result.json; inspect {label}.log')
        result = json.loads(result_path.read_bytes())
        for item in result['artifacts']:
            prefix = f"artifact://{result['job_id']}/"
            require(item['uri'].startswith(prefix), f'{label}: foreign artifact job')
            f = (run_dir / item['uri'][len(prefix):]).resolve()
            require(f.is_relative_to(run_dir) and sha(f.read_bytes()) == item['sha256']
                    and f.stat().st_size == item['bytes'], f"{label}: invalid artifact {item['uri']}")
        if code:
            require(rc == 1 and result['status'] == 'FAILED' and result['error']['code'] == code
                    and not result['stages'] and not (run_dir / 'draft-build').exists(),
                    f'{label}: expected {code}, got {result.get("error")}')
        else:
            require(rc == 0 and result['status'] == 'SUCCEEDED', f'{label}: {result.get("error")}')
            src = result['source_report']
            require((src['job_id'], src['trace_id'], src['sha256']) == (A_JOB, A_TRACE, REPORT_SHA)
                    and result['job_id'] != A_JOB and result['trace_id'] != A_TRACE, 'Wrong A/B identities')
            require(result['original_source_unchanged'] and not git(repo, 'status', '--porcelain'),
                    'A project was changed')
            recheck = json.loads((run_dir / 'recheck.json').read_bytes())
            require(recheck['data']['remaining_missing'] == 0 and any(
                (f['type'], f['target'], f['dependency']) == ('REDUNDANT', 'main.o', 'unused.h')
                for f in recheck['data']['findings']), 'Expected no MD and the existing RD')
            runtime = json.loads((run_dir / 'execution-runtime.json').read_bytes())
            require(len(runtime['operations']) == 1 and runtime['operations'][0]['action'] == 'mdfixer'
                    and runtime['image_id'] == result['execution_image_id']
                    and result['execution_image_id'] in runtime['operations'][0]['command'],
                    'MDFixer did not use the verified DRAFT image')
        verified.append({'case': label, 'exit_code': rc, 'job_id': result['job_id'],
                         'trace_id': result['trace_id'], 'status': result['status'],
                         'error_code': code, 'image_id': result.get('execution_image_id')})
        print('CASE_VERIFIED=' + label, flush=True)
    require(len({item['job_id'] for item in verified}) == len(verified), 'Cases shared a job ID')
    (output / 'verification.json').write_text(json.dumps({
        'passed': True, 'tool_commit': tool_sha, 'A_packet_sha256': ARCHIVE_SHA, 'cases': verified
    }, indent=2) + '\n')
    print('E13_B_CONSUMER_PASSED=true\nSOURCE_SHA=' + tool_sha, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--a-archive', type=Path, required=True)
    try:
        run(p.parse_args().a_archive.resolve())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
