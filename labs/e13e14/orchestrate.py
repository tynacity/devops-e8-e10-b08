"""Run E14's four Compose services on one pinned teaching project."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PORTS = {'buildchecker': 18181, 'echecker': 18182, 'draft': 18183, 'mdfixer': 18184}
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'labs/e11e12'))
from paired_runtime import IMAGE_PATTERN, PROFILES, RUNTIME_TIMEOUT, build_budget
from pipeline import Failure, TINYEXPR_TARGETS, snapshot as paired_snapshot, tracked_hashes


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def container_path(path):
    return '/course/' + path.resolve().relative_to(ROOT.resolve()).as_posix()


def host_path(value):
    if not isinstance(value, str) or not value.startswith('/course/'):
        raise ValueError('Expected /course path')
    path = (ROOT / value[len('/course/'):]).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Path escapes repository')
    return path


def command(argv, cwd, log):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(p.stdout + p.stderr, encoding='utf-8')
    if p.returncode:
        raise ValueError(f'{argv[0]} failed; inspect {log}')
    return p.stdout.strip()


def snapshot(repo, revision, target, logs):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Use a full Git commit SHA')
    head = command(['git', 'rev-parse', '--verify', revision + '^{commit}'], repo,
                   logs / (target.name + '-resolve.log'))
    command(['git', 'clone', '--no-hardlinks', '--no-checkout', str(repo), str(target)], repo,
            logs / (target.name + '-clone.log'))
    command(['git', 'checkout', '--detach', head], target, logs / (target.name + '-checkout.log'))
    if {p.name for p in target.glob('*.c')} != {'main.c', 'helper.c'} or not (target / 'config.h').is_file():
        raise ValueError('Unsupported teaching project profile')
    return head


def call(role, payload, evidence, timeout=720):
    if payload.get('profile') is not None:
        save(evidence.with_name(evidence.name.replace('-response.json', '-request.json')), payload)
    req = urllib.request.Request(f'http://127.0.0.1:{PORTS[role]}/v1/run',
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors='replace')
        save(evidence, {'role': role, 'http': exc.code, 'error': body})
        if payload.get('profile') is not None:
            detail = json.loads(body)
            raise Failure(detail.get('error_code', 'ROLE_FAILED'), f'{role}: {detail.get("error", body)}') from exc
        raise ValueError(f'{role} HTTP {exc.code}: {body}') from exc
    save(evidence, data)
    if data['status'] != 'SUCCEEDED':
        raise ValueError(f'{role} did not succeed')
    return data


def source_state(repo, folder, name):
    logs = folder / 'logs'
    state = {'head': command(['git', 'rev-parse', 'HEAD'], repo, logs / f'source-{name}-head.log'),
             'status': command(['git', 'status', '--porcelain'], repo, logs / f'source-{name}-status.log'),
             'tracked_sha256': tracked_hashes(repo)}
    save(folder / f'source-{name}.json', state)
    return state


def execute(request, out):
    out = out.resolve()
    if out.exists():
        raise ValueError('Use a new output directory')
    if not out.resolve().is_relative_to((ROOT / 'work').resolve()):
        raise ValueError('Output must be inside work/')
    repo = host_path(request['repo'])
    candidate = host_path(request['candidate'])
    if not repo.resolve().is_relative_to((ROOT / 'data').resolve()) or not candidate.resolve().is_relative_to((ROOT / 'data').resolve()):
        raise ValueError('Input project and candidate must be in data/')
    out.mkdir(parents=True)
    job = 'job-' + uuid.uuid4().hex
    trace = 'trace-' + uuid.uuid4().hex
    result = {'schema_version': 'e14-compose-1', 'job_id': job, 'trace_id': trace,
              'status': 'RUNNING', 'stages': []}
    save(out / 'request.json', request)
    profile = request.get('profile')
    image = None
    source_before = None

    def payload(project, folder, **extra):
        return {'project': container_path(project), 'out': container_path(folder),
                'job_id': job, 'trace_id': trace, **extra}

    def dispatch(role, project, folder, response, **extra):
        if profile is None:
            return call(role, payload(project, folder, **extra), out / response)
        data = payload(project, folder, **extra)
        data.update(profile=profile, target_commit=target_sha)
        if image is not None:
            data['execution_image_id'] = image
        wait = 2 * build_timeout + 120 if role == 'draft' else (2 * RUNTIME_TIMEOUT + 30 if role == 'echecker' else RUNTIME_TIMEOUT + 30)
        received = call(role, data, out / response, timeout=wait)
        if image is not None and received.get('execution_image_id') != image:
            raise Failure('DRAFT_IMAGE_MISMATCH', f'{role} did not use the DRAFT image for this task')
        return received

    def stage(name, commit, data):
        item = {'name': name, 'commit': commit, 'job_id': job, 'trace_id': trace, 'status': 'SUCCEEDED', 'data': data}
        path = out / (name + '.json')
        save(path, item)
        result['stages'].append({'name': name, 'artifact': {'uri': path.name, 'sha256': digest(path)}})

    try:
        base = out / 'base-project'
        target = out / 'target-project'
        logs = out / 'logs'
        build_timeout = request.get('build_timeout', 600)
        if profile is None:
            base_sha = snapshot(repo, request['base'], base, logs)
            target_sha = snapshot(repo, request['target'], target, logs)
        else:
            if (profile not in PROFILES or request.get('mode') != 'e12'
                    or any(not isinstance(request.get(key), str) or not re.fullmatch(r'[0-9a-f]{40}', request[key])
                           for key in ('base', 'target')) or not isinstance(request.get('expected_output'), str)):
                raise Failure('INVALID_REQUEST', 'Expected an e12 paired profile, full commits and explicit expected output')
            build_timeout = build_budget(build_timeout)
            result['profile'] = profile
            source_before = source_state(repo, out, 'before')
            if source_before['status']:
                raise Failure('SOURCE_DIRTY', 'Paired project must be a clean source checkout')
            command(['git', 'merge-base', '--is-ancestor', request['base'], request['target']], repo, logs / 'ancestry.log')
            active_profile = profile if profile == 'tinyexpr' else None
            base_sha = paired_snapshot(repo, request['base'], base, logs, active_profile)
            target_sha = paired_snapshot(repo, request['target'], target, logs, active_profile)
        result.update(base_commit=base_sha, target_commit=target_sha)

        drafted = dispatch('draft', target, out / 'draft-build', 'draft-response.json',
                           candidate=container_path(candidate), expected_output=request.get('expected_output', '1'),
                           build_timeout=build_timeout)
        if profile is not None:
            image = drafted.get('execution_image_id', '')
            if not re.fullmatch(IMAGE_PATTERN, image):
                raise Failure('DRAFT_IMAGE_UNVERIFIED', 'DRAFT did not return a full execution image ID')
            result['execution_image_id'] = image
        stage('draft', target_sha, drafted)

        base_full = dispatch('buildchecker', base, out / 'baseline-full', 'baseline-response.json')
        target_full = dispatch('buildchecker', target, out / 'target-full', 'target-response.json')
        stage('full-check', base_sha, {'base': base_full, 'target': target_full})

        increment = dispatch('echecker', target, out / 'incremental', 'incremental-response.json', base=container_path(base),
                             baseline_graph=container_path(out / 'baseline-full/actual-graph.json'),
                             target_findings=container_path(out / 'target-full/findings.json'), target_commit=target_sha)
        stage('incremental-check', target_sha, increment)

        binding = {'producer_manifest': increment['producer_manifest']} if profile is not None else {}
        repair = dispatch('mdfixer', target, out / 'repair-work', 'repair-response.json',
                          report=increment['report'], report_sha256=increment['sha256'], target_commit=target_sha, **binding)
        stage('repair', target_sha, repair)

        repaired = host_path(repair['repaired_project']) if profile is not None else target
        if profile is not None and repaired != out / 'repair-work/component/target-project':
            raise Failure('REPAIR_PATH_MISMATCH', 'MDFixer returned a different task copy')
        final = dispatch('buildchecker', repaired, out / 'final-full', 'recheck-response.json')
        missing = [x for x in final['result']['findings'] if x['type'] == 'MISSING']
        if missing:
            raise ValueError(f'Recheck has {len(missing)} missing dependencies')
        if profile == 'tinyexpr' and set(final['result']['observed_targets']) != set(TINYEXPR_TARGETS):
            raise Failure('TARGET_COVERAGE_MISMATCH', 'TinyExpr recheck did not observe all three targets')
        stage('recheck', target_sha, {'result': final, 'remaining_missing': 0})
        result['status'] = 'SUCCEEDED'
    except Exception as exc:
        result.update(status='FAILED', error=str(exc))
        if profile is not None:
            result['error_code'] = getattr(exc, 'code', type(exc).__name__.upper())
    if source_before is not None:
        try:
            result['original_source_unchanged'] = source_before == source_state(repo, out, 'after')
            if not result['original_source_unchanged']:
                result.update(status='FAILED', error='Original project changed during execution', error_code='SOURCE_CHANGED')
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            result.update(status='FAILED', original_source_unchanged=False, error=str(exc), error_code='SOURCE_CHECK_FAILED')
    result['artifacts'] = [{'uri': path.relative_to(out).as_posix(), 'sha256': digest(path),
                            'bytes': path.stat().st_size} for path in sorted(out.rglob('*'))
                           if path.is_file() and '.git' not in path.parts and not path.is_symlink()]
    save(out / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = execute(json.loads(args.request.read_text(encoding='utf-8')), args.out.resolve())
    print(json.dumps({'status': result['status'], 'job_id': result['job_id'],
                      'stages': [x['name'] for x in result['stages']],
                      'error': result.get('error')}, ensure_ascii=False))
    return 0 if result['status'] == 'SUCCEEDED' else 1


if __name__ == '__main__':
    sys.exit(main())
