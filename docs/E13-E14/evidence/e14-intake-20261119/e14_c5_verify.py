"""Run an isolated E14 HeaderFlow rejection test against real Docker services."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.request import urlopen
import zipfile


BASE = 'fcd36c0082be043c8fece6a61941321833171aa7'
IMAGE = 'sha256:1fa773b9ed7fdf35281eda86ec53ebf61048f271a70a43f9ccfd0e2d7a759829'
BRANCH = 'student/241880492/e13-e14-paired-acceptance'
ZIP_SHA = '24f62182b4871ffeab42f7c9559bd6710d42bec2ce23ddb5fccd6e617ead2364'
ROLES = ('buildchecker', 'echecker', 'draft', 'mdfixer')
STAGES = ['draft', 'full-check', 'incremental-check', 'repair', 'recheck']
# Only the generated candidate changes. The report, validator and HTTP path stay intact.
HOOK = '''
        if out == Path(__file__).resolve().parents[2] / 'work/reject-missing-config/repair-work/component':
            good_line = '+main.o: main.c unused.h config.h extra.h\\n'
            bad_line = '+main.o: main.c unused.h extra.h\\n'
            require(diff.count(good_line) == 1, 'TEST_INJECTION_MISMATCH', 'Expected one HeaderFlow config.h addition')
            (out / 'generated-candidate.patch').write_text(diff, encoding='utf-8')
            diff = diff.replace(good_line, bad_line, 1)
'''


def need(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify_input(pack, dest):
    need(sha(pack.read_bytes()) == ZIP_SHA, 'Input archive SHA mismatch')
    with zipfile.ZipFile(pack) as archive:
        manifest = json.loads(archive.read('FILES.json'))
        for item in manifest:
            name = item['path']
            data = archive.read(name)
            need(len(data) == item['bytes'] and sha(data) == item['sha256'], name)
            path = (dest / name).resolve()
            need(path.is_relative_to(dest), name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


def prepare(pack, directory):
    source = directory / 'input'
    verify_input(pack, source)
    repo = directory / 'repo'
    subprocess.run(['git', 'clone', '--branch', BRANCH, str(source / 'source/tools-paired.bundle'), str(repo)], check=True)
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    need(revision == BASE, 'Base SHA mismatch')
    identity = read(source / 'SOURCE_IDENTITY.json')
    for name, digest in identity['overlay_files'].items():
        data = (source / 'overlay' / name).read_bytes()
        need(sha(data) == digest, name)
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = repo / 'data/headerflow'
    data.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'clone', '--branch', 'e13e14/input-A-headerflow',
                    str(source / 'inputs/headerflow/project.bundle'), str(data / 'repo')], check=True)
    for name, origin in [('candidate.Dockerfile', 'inputs/headerflow'), ('HeaderFlow-e14.json', 'requests')]:
        (data / name).write_bytes((source / origin / name).read_bytes())
    component = repo / 'labs/e13e14/mdfixer.py'
    original = component.read_bytes().replace(b'\r\n', b'\n')
    needle = b"        candidate = out / 'candidate.patch'\n"
    need(original.count(needle) == 1, 'Injection site must occur once')
    patched = original.replace(needle, HOOK.encode() + needle)
    compile(patched, str(component), 'exec')
    component.write_bytes(patched)
    identity['test_instrumentation'] = {
        'path': 'labs/e13e14/mdfixer.py', 'before_sha256': sha(original),
        'tested_sha256': sha(patched), 'job_output': 'work/reject-missing-config',
        'change': 'Remove only config.h from generated main.o prerequisites before validation.',
    }
    save(directory / 'source-identity.json', identity)
    (directory / 'mdfixer-tested.py').write_bytes(patched)
    return repo


def run_command(args, repo, env, log, expected=0):
    with log.open('wb') as stream:
        result = subprocess.run(args, cwd=repo, env=env, stdout=stream, stderr=subprocess.STDOUT)
    if expected is not None:
        need(result.returncode == expected, f'Exit {result.returncode}, expected {expected}. See {log}')
    return result.returncode


def verify_artifacts(task, result):
    for item in result['artifacts'] + [s['artifact'] for s in result['stages']]:
        path = (task / item['uri']).resolve()
        need(path.is_relative_to(task), 'Artifact path outside task')
        data = path.read_bytes()
        need(sha(data) == item['sha256'] and len(data) == item.get('bytes', len(data)), item['uri'])


def verify_task(repo, name, rejected):
    task = repo / 'work' / name
    result = read(task / 'result.json')
    component = task / 'repair-work/component'
    repair = read(component / 'result.json')
    verdict = read(component / 'validation/validation.json')
    request = read(task / 'repair-request.json')
    response = read(task / 'repair-response.json')
    runtime = read(task / 'execution-runtime.json')
    image = result['execution_image_id']
    report = (task / 'incremental/incremental-check.json').read_bytes()
    report_hash = sha(report)
    need(report == (component / 'consumed-report.json').read_bytes(), 'Report bytes changed')
    need((task / 'incremental/producer-result.json').read_bytes() == (component / 'producer-result.json').read_bytes(),
         'Producer bytes changed')
    need(report_hash == request['report_sha256'] == repair['input']['sha256'], 'Report SHA mismatch')
    for key in ('job_id', 'trace_id'):
        need(repair['input'][key] == request[key] == result[key], 'Task identity mismatch')
    need(repair['input']['commit'] == result['target_commit'], 'Target mismatch')
    need(read(task / 'source-before.json') == read(task / 'source-after.json'), 'Original source changed')
    need(result['original_source_unchanged'] and repair['original_source_unchanged'], 'Source protection failed')
    need(runtime['image_id'] == image and re.fullmatch(r'sha256:[0-9a-f]{64}', image), 'Missing runtime image ID')
    operations = runtime['operations']
    actions = ['full', 'full', 'scan', 'scan', 'mdfixer'] + ([] if rejected else ['full'])
    need([op['action'] for op in operations] == actions, 'Unexpected executed operations')
    need(all(op['image_id'] == image and image in op['command'] and op['command'][:2] == ['docker', 'run']
             for op in operations), 'Operation ran outside the bound Docker image')
    need(all(op['exit_code'] == 0 for op in operations), 'Docker worker did not report a completed operation')
    names = [s['name'] for s in result['stages']]
    candidate = (component / 'candidate.patch').read_bytes()
    if rejected:
        generated = (component / 'generated-candidate.patch').read_bytes()
        need(generated != candidate and generated.replace(
            b'+main.o: main.c unused.h config.h extra.h\n', b'+main.o: main.c unused.h extra.h\n', 1
        ) == candidate, 'Unexpected fault injection')
        need(result['status'] == 'FAILED' and result['error_code'] == 'REPAIR_REJECTED', 'Wrong job failure')
        need(response['http'] == 422 and json.loads(response['error'])['error_code'] == 'REPAIR_REJECTED',
             'Wrong HTTP rejection')
        need(repair['status'] == 'FAILED' and repair['error']['code'] == 'REPAIR_REJECTED', 'Wrong component rejection')
        need(verdict['accepted'] is False and verdict['rollback'] is True and verdict['source_unchanged'] is True,
             'Rollback did not pass')
        checks = verdict['checks']
        need(all(checks[key] is True for key in ('patch_applies', 'build', 'test')) and
             all(checks[key] is False for key in ('header_change', 'no_missing')), 'Failure did not exercise dependency validation')
        need(read(component / 'target-before.json') == read(component / 'target-after.json'), 'Task checkout bytes changed')
        need((component / 'target-head-before.log').read_bytes() == (component / 'target-head-after.log').read_bytes(),
             'Task checkout HEAD changed')
        findings = read(component / 'validation/recheck.json')['findings']
        need(any((f['type'], f['target'], f['dependency']) == ('MISSING', 'main.o', 'config.h') for f in findings),
             'Missing dependency not corroborated')
        need(names == STAGES[:3] and not (task / 'final-full').exists(), 'Failed candidate promoted')
    else:
        need(result['status'] == 'SUCCEEDED' and names == STAGES and verdict['accepted'] and all(verdict['checks'].values()),
             'Fresh positive task failed')
        need(read(task / 'recheck.json')['data']['remaining_missing'] == 0, 'Positive final recheck failed')
        need(not (component / 'generated-candidate.patch').exists(), 'Positive task received test injection')
    verify_artifacts(task, result)
    return {'status': result['status'], 'job_id': result['job_id'], 'trace_id': result['trace_id'],
            'target_commit': result['target_commit'], 'image_id': image, 'report_sha256': report_hash,
            'candidate_sha256': sha(candidate), 'stages': names, 'operations': actions,
            'original_source_unchanged': True, 'validation': verdict,
            'artifact_count': len(result['artifacts']), 'http_rejection': response if rejected else None}


def run(pack, directory):
    repo = prepare(pack, directory)
    project = 'b08-e14-c5-241880529-' + str(os.getpid())
    compose = ['docker', 'compose', '-p', project, '-f', 'labs/e13e14/compose.yaml']
    env = dict(os.environ, E14_ROOT=str(repo), E14_IMAGE=IMAGE)
    preflight = subprocess.check_output(
        ['docker', 'image', 'inspect', '--format', '{{.Id}} {{.Os}}/{{.Architecture}}', IMAGE], text=True).strip()
    need(preflight == f'{IMAGE} linux/amd64', 'Expected AMD64 environment image')
    for port in (18181, 18182, 18183, 18184):
        import socket
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', port))
    save(directory / 'preflight.json', {'environment_image': preflight, 'project': project, 'ports': [18181, 18182, 18183, 18184]})
    positive_request = repo / 'data/headerflow/HeaderFlow-e14.json'
    run_command(compose + ['config', '--quiet'], repo, env, directory / 'compose-config.log')
    try:
        run_command(compose + ['up', '-d', '--wait'], repo, env, directory / 'compose-up.log')
        health = {}
        for port, role in enumerate(ROLES, 18181):
            with urlopen(f'http://127.0.0.1:{port}/health', timeout=5) as response:
                health[role] = json.load(response)
            need(health[role] == {'role': role, 'status': 'ok'}, f'{role} unhealthy')
        save(directory / 'health.json', health)
        results = {}
        for name, rejected in [('reject-missing-config', True), ('positive-after-rejection', False)]:
            run_command(['python3', '-B', 'labs/e13e14/orchestrate.py', '--request', str(positive_request),
                         '--out', f'work/{name}'], repo, env, directory / (name + '.log'), int(rejected))
            results[name] = verify_task(repo, name, rejected)
            save(directory / 'verification.json', {'project': project, 'tasks': results})
    finally:
        try:
            run_command(compose + ['logs', '--no-color'], repo, env, directory / 'role-logs.txt', None)
        finally:
            run_command(compose + ['down'], repo, env, directory / 'compose-down.log')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack', type=Path)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    if args.prepare_only:
        prepare(args.pack.resolve(), directory)
    else:
        run(args.pack.resolve(), directory)
