"""Member 2 repair profile for TinyExpr's make example graph."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from pipeline import ROOT, Failure, check_envelope, command, load_artifact, save
from lab import patch

sys.path.insert(0, str(Path(__file__).parent / 'environment/services/buildchecker'))
from buildchecker.fullcheck import full_check

OBJECTS = ('example.o', 'tinyexpr.o')
BUILD = ['make', 'example']
CLEAN = ['make', 'clean']


def require(condition, code, message):
    if not condition:
        raise Failure(code, message)


def consume(path, target, manifest_path=None, expected_sha256=None):
    if manifest_path:
        manifest = json.loads(manifest_path.read_bytes())
        require(manifest.get('schema_version') == 'e11e12-1', 'SCHEMA_MISMATCH', 'Producer manifest')
        require(manifest.get('status') == 'SUCCEEDED', 'UPSTREAM_FAILED', 'Producer manifest')
        require(manifest.get('target_commit') == target, 'STALE_REPORT', 'Producer target differs')
        entries = [s['artifact'] for s in manifest['stages'] if s['name'] == 'incremental-check']
        require(len(entries) == 1, 'ARTIFACT_TYPE_MISMATCH', 'Expected one incremental-check')
        entry = entries[0]
        uri = f"artifact://{manifest['job_id']}/incremental-check.json"
        require(entry['uri'] == uri, 'ARTIFACT_TYPE_MISMATCH', 'Unexpected artifact URI')
        if expected_sha256:
            require(expected_sha256 == entry['sha256'], 'ARTIFACT_HASH_MISMATCH',
                    'Expected digest differs from producer manifest')
        envelope = load_artifact(path, entry['sha256'])
        check_envelope(envelope, target, 'incremental-check')
        require(all(envelope.get(k) == manifest.get(k) and manifest.get(k)
                    for k in ('job_id', 'trace_id')), 'ARTIFACT_ID_MISMATCH', 'Producer identity')
    else:
        envelope = load_artifact(path, expected_sha256) if expected_sha256 else json.loads(path.read_bytes())
        check_envelope(envelope, target, 'fixed-md')
    check_tinyexpr_report(envelope, target)
    return envelope


def check_tinyexpr_report(envelope, target):
    """Check the inner MDFixer input after validating the outer artifact reference."""
    require(isinstance(envelope.get('data'), dict) and envelope['data'].get('commit') == target,
            'STALE_REPORT', 'Inner report belongs to another commit')
    require(envelope['data'].get('schema_version') == 'e8e10-1', 'SCHEMA_MISMATCH', 'Inner MD report')
    findings = envelope['data'].get('findings')
    require(isinstance(findings, list) and all(isinstance(f, dict) and f.get('type') in ('MISSING', 'REDUNDANT')
            and all(isinstance(f.get(k), str) and f[k] for k in ('target', 'dependency')) for f in findings),
            'INVALID_REPORT', 'Expected structured findings')
    return envelope['data']


def patch_tinyexpr(project, report):
    for finding in report['findings']:
        if finding['type'] != 'MISSING':
            continue
        require(finding['target'] in OBJECTS, 'UNSUPPORTED_TARGET', finding['target'])
        require(finding['dependency'].endswith('.h'), 'UNSUPPORTED_DEPENDENCY', finding['dependency'])
    return patch(project, report, append_rules_for=OBJECTS)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_times(project):
    return {name: (project / name).stat().st_mtime_ns for name in (*OBJECTS, 'example')}


def behavior(project, logs, phase):
    command(['python3', 'course/verify_example.py'], project, logs / (phase + '-behavior.log'))
    return command(['./example'], project, logs / (phase + '-output.log'))


def validate_tinyexpr(project, candidate, out):
    out.mkdir(parents=True, exist_ok=False)
    original = (project / 'Makefile').read_bytes()
    sandbox = out / 'sandbox'
    shutil.copytree(project, sandbox, ignore=shutil.ignore_patterns('.git', '*.o', 'example'))
    checks, error = {}, None
    try:
        command(['git', 'init', '-b', 'main'], sandbox, out / 'sandbox-init.log')
        command(['git', 'apply', '--check', str(candidate.resolve())], sandbox, out / 'apply-check.log')
        command(['git', 'apply', str(candidate.resolve())], sandbox, out / 'apply.log')
        checks['patch_applies'] = True
        recipes = lambda content: [line for line in content.splitlines() if line.startswith(b'\t')]
        checks['recipes_preserved'] = recipes(original) == recipes((sandbox / 'Makefile').read_bytes())
        command(CLEAN, sandbox, out / 'clean.log')
        command(BUILD, sandbox, out / 'build.log')
        checks['build'] = True
        before_output = behavior(sandbox, out, 'initial')
        checks['behavior'] = True
        before = object_times(sandbox)
        command(BUILD, sandbox, out / 'unchanged.log')
        checks['unchanged_input_no_rebuild'] = before == object_times(sandbox)
        header = sandbox / 'tinyexpr.h'
        header_bytes = header.read_bytes()
        time.sleep(1.05)
        header.write_bytes(header_bytes + b'\n/* MDFixer header-change probe */\n')
        command(BUILD, sandbox, out / 'incremental.log')
        after = object_times(sandbox)
        checks['header_change_rebuilds_objects_and_link'] = all(after[name] > before[name] for name in before)
        save(out / 'object-times.json', {'before': before, 'after_header_change': after})
        incremental_output = behavior(sandbox, out, 'incremental')
        incremental_hashes = {name: file_hash(sandbox / name) for name in after}
        command(CLEAN, sandbox, out / 'comparison-clean.log')
        command(BUILD, sandbox, out / 'comparison-build.log')
        clean_output = behavior(sandbox, out, 'comparison')
        clean_hashes = {name: file_hash(sandbox / name) for name in after}
        checks['clean_build_matches'] = before_output == incremental_output == clean_output and incremental_hashes == clean_hashes
        save(out / 'comparison.json', {'incremental_sha256': incremental_hashes, 'clean_sha256': clean_hashes,
                                       'output_equal': incremental_output == clean_output})
        header.write_bytes(header_bytes)
        recheck = full_check(sandbox, out / 'final-full', clean_command='make clean', build_command='make example')
        save(out / 'recheck.json', recheck)
        checks['no_missing'] = recheck['status'] == 'SUCCEEDED' and not any(
            f['type'] == 'MISSING' for f in recheck['findings'])
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        error = str(exc)
    accepted = bool(checks) and all(checks.values()) and error is None
    if accepted:
        (project / 'Makefile').write_bytes((sandbox / 'Makefile').read_bytes())
    unchanged = (project / 'Makefile').read_bytes() == original
    verdict = {'accepted': accepted, 'checks': checks, 'error': error,
               'source_unchanged': unchanged, 'rollback': not accepted and unchanged}
    save(out / 'validation.json', verdict)
    return verdict


def execute(repo, target, report_path, out, manifest_path=None, report_sha256=None):
    out.mkdir(parents=True, exist_ok=False)
    result = {'schema_version': 'e11e12-1', 'profile': 'tinyexpr-example', 'target_commit': target,
              'status': 'FAILED', 'runtime': 'linux-process'}
    try:
        require(re.fullmatch(r'[0-9a-f]{40}', target), 'INVALID_TARGET', 'Expected full SHA')
        source_status = command(['git', 'status', '--porcelain'], repo, out / 'source-before.log')
        envelope = consume(report_path, target, manifest_path, report_sha256)
        result['input'] = {'kind': envelope['kind'], 'commit': target, 'sha256': file_hash(report_path),
                           'job_id': envelope.get('job_id'), 'trace_id': envelope.get('trace_id')}
        shutil.copyfile(report_path, out / 'consumed-report.json')
        if manifest_path:
            shutil.copyfile(manifest_path, out / 'producer-result.json')
        project = out / 'target-project'
        command(['git', 'clone', '--no-hardlinks', '--no-checkout', str(repo), str(project)], repo, out / 'clone.log')
        command(['git', 'checkout', '--detach', target], project, out / 'checkout.log')
        diff, plan = patch_tinyexpr(project, envelope['data'])
        require(bool(diff), 'NO_MISSING_DEPENDENCY', 'Report did not produce a patch')
        candidate = out / 'candidate.patch'
        candidate.write_text(diff, encoding='utf-8')
        save(out / 'repair-plan.json', plan)
        repair = {'schema_version': 'e11e12-1', 'kind': 'repair', 'commit': target,
                  'status': 'SUCCEEDED', 'data': {'edits': plan, 'input_report': result['input'],
                                                  'candidate_sha256': file_hash(candidate)}}
        save(out / 'repair.json', repair)
        verdict = validate_tinyexpr(project, candidate, out / 'validation')
        require(verdict['accepted'], 'REPAIR_REJECTED', str(verdict))
        shutil.copyfile(out / 'validation/recheck.json', out / 'recheck.json')
        require(command(['git', 'status', '--porcelain'], repo, out / 'source-after.log') == source_status,
                'SOURCE_CHANGED', 'Original repository changed')
        result.update(status='SUCCEEDED', original_source_unchanged=True)
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
        result['error'] = {'code': getattr(exc, 'code', 'EXECUTION_FAILED'), 'message': str(exc)}
    save(out / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--report-sha256')
    parser.add_argument('--producer-manifest', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--image-id', help='Run repair in this exact DRAFT image ID')
    a = parser.parse_args()
    if a.image_id:
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', a.image_id):
            parser.error('Use the full DRAFT image ID')
        out = a.out.resolve()
        if out.exists():
            parser.error('Use a new output directory')
        def mapped(path):
            try:
                return '/course/' + path.resolve().relative_to(ROOT).as_posix()
            except ValueError:
                parser.error(f'Docker inputs and outputs must be under {ROOT}: {path}')

        argv = ['docker', 'run', '--rm', '--network', 'none', '--cap-add', 'SYS_PTRACE',
                '--user', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp', '-v', f'{ROOT}:/course',
                '-w', '/course', '--entrypoint', 'python3', a.image_id, 'labs/e11e12/tinyexpr_repair.py',
                '--repo', mapped(a.repo), '--target', a.target, '--report', mapped(a.report), '--out', mapped(out)]
        if a.producer_manifest:
            argv += ['--producer-manifest', mapped(a.producer_manifest)]
        if a.report_sha256:
            argv += ['--report-sha256', a.report_sha256]
        result = subprocess.run(argv, check=False)
        save(out / 'docker-execution.json', {'image_id': a.image_id, 'command': argv, 'exit_code': result.returncode})
        return result.returncode
    result = execute(a.repo.resolve(), a.target, a.report.resolve(), a.out.resolve(),
                     a.producer_manifest, a.report_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'SUCCEEDED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
