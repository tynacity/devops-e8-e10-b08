"""CI acceptance of the fixed teaching sample, not paired-project release approval.

Run after prepare and Compose up in an isolated checkout. Keep all three tasks.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/e14-ci'
COMPOSE = ['docker', 'compose', '-f', 'labs/e13e14/compose.yaml']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def run(args, log, expected=0):
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=900)
    log.write_text(p.stdout + p.stderr, encoding='utf-8')
    if p.returncode != expected:
        print((p.stdout + p.stderr)[-2000:], flush=True)
    assert p.returncode == expected, (args, p.returncode, expected, str(log))
    return p.stdout


def verify(folder, success):
    result = read(folder / 'result.json')
    request = read(folder / 'request.json')
    assert result['status'] == ('SUCCEEDED' if success else 'FAILED')
    assert result['base_commit'] == request['base']
    assert result['target_commit'] == request['target']
    assert result['job_id'] and result['trace_id']
    artifacts = result['artifacts']
    assert artifacts and len({a['uri'] for a in artifacts}) == len(artifacts)
    for item in artifacts:
        path = (folder / item['uri']).resolve()
        assert path.is_relative_to(folder.resolve()) and not path.is_symlink()
        data = path.read_bytes()
        assert len(data) == item['bytes'], item['uri']
        assert hashlib.sha256(data).hexdigest() == item['sha256'], item['uri']
    if success:
        names = ['draft', 'full-check', 'incremental-check', 'repair', 'recheck']
        assert [s['name'] for s in result['stages']] == names
        for stage in result['stages']:
            path = folder / (stage['name'] + '.json')
            assert stage['artifact']['uri'] == path.name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == stage['artifact']['sha256']
            data = read(path)
            assert data['status'] == 'SUCCEEDED'
            assert (data['job_id'], data['trace_id']) == (result['job_id'], result['trace_id'])
            assert data['commit'] == (request['base'] if stage['name'] == 'full-check' else request['target'])
        report = folder / 'incremental/incremental-check.json'
        envelope = read(report)
        assert (envelope['commit'], envelope['job_id'], envelope['trace_id']) == (
            request['target'], result['job_id'], result['trace_id'])
        assert hashlib.sha256(report.read_bytes()).hexdigest() == read(folder / 'incremental-response.json')['sha256']
        repair = read(folder / 'repair-response.json')
        assert repair['validation']['accepted'] is True
        assert hashlib.sha256((folder / 'repair-work/candidate.patch').read_bytes()).hexdigest() == repair['sha256']
        assert read(folder / 'recheck.json')['data']['remaining_missing'] == 0
        assert not any(f['type'] == 'MISSING' for f in read(folder / 'final-full/findings.json')['findings'])
    else:
        assert result['stages'] == []
        assert read(folder / 'draft-build/result.json')['status'] == 'TIMED_OUT'
        assert read(folder / 'draft-response.json')['http'] == 422
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'data/integration-sample/e12.json'
    timeout_request = source.with_name('e14-ci-timeout.json')
    assert not timeout_request.exists(), 'Preserve existing inputs'
    request = read(source)
    request['build_timeout'] = 0.01
    timeout_request.write_text(json.dumps(request, indent=2) + '\n', encoding='utf-8')
    results = []
    for name, input_path, success in [('normal', source, True), ('timeout', timeout_request, False), ('recovery', source, True)]:
        folder = OUT / name
        assert not folder.exists(), 'Use a fresh CI checkout'
        run([sys.executable, 'labs/e13e14/orchestrate.py', '--request', str(input_path), '--out', str(folder)],
            OUT / (name + '.log'), 0 if success else 1)
        results.append(verify(folder, success))
        if not success:
            top = run(COMPOSE + ['top', 'draft'], OUT / 'draft-processes-after-timeout.log')
            assert not any('docker build' in line or 'docker-buildx' in line for line in top.splitlines())
    assert len({r['job_id'] for r in results}) == 3
    assert len({r['trace_id'] for r in results}) == 3
    assert read(OUT / 'timeout/result.json')['status'] == 'FAILED'
    for role in ['buildchecker', 'echecker', 'draft', 'mdfixer']:
        logs = run(COMPOSE + ['logs', '--no-color', '--no-log-prefix', role], OUT / (role + '.log'))
        events = [json.loads(line) for line in logs.splitlines() if line.startswith('{')]
        for result in (results[0], results[2]):
            assert any(e.get('role') == role and e.get('job_id') == result['job_id'] and
                       e.get('trace_id') == result['trace_id'] and e.get('status') == 'SUCCEEDED' for e in events), role
        if role == 'draft':
            assert any(e.get('job_id') == results[1]['job_id'] and e.get('error_code') == 'TIMEOUT' for e in events)
    images = {os.environ['E14_IMAGE']}
    for name in ('normal', 'recovery'):
        draft = read(OUT / name / 'draft-build/result.json')
        images.add(draft['attempts'][-1]['image_id'])
    for index, image in enumerate(sorted(images)):
        run(['docker', 'image', 'inspect', image], OUT / f'image-{index}.json')
        run([sys.executable, 'scripts/secret_scan.py', '.', '--image', image], OUT / f'image-{index}-scan.log')
    summary = {'scope': 'fixed teaching sample only; paired projects and release gate remain separate',
               'tasks': [{'job_id': r['job_id'], 'trace_id': r['trace_id'], 'status': r['status'],
                          'artifacts_checked': len(r['artifacts'])} for r in results],
               'role_logs_verified': 4, 'scanned_images': sorted(images)}
    (OUT / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        frame = traceback.extract_tb(exc.__traceback__)[-1]
        message = f'{type(exc).__name__} at {Path(frame.filename).name}:{frame.lineno}: {exc}'
        for name in ('normal', 'timeout', 'recovery'):
            path = OUT / name / 'result.json'
            if path.exists():
                result = read(path)
                message += f'; {name}={result.get("status")}, error={str(result.get("error"))[:400]}'
        message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::error::' + message, flush=True)
        raise
