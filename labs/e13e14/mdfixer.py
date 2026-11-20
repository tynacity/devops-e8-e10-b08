"""Member 2 component API, executed inside the caller's selected project image."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e11e12'))
from pipeline import Failure, command, save, snapshot, tracked_hashes
from tinyexpr_repair import consume, full_check, patch_tinyexpr, validate_tinyexpr
from lab import patch, validate


def require(condition, code, message):
    if not condition:
        raise Failure(code, message)


def repair(request, out):
    """Consume one artifact, repair an isolated checkout and record source hashes."""
    out = Path(out).resolve()
    repo = Path(request['repo']).resolve()
    require(out != repo and repo not in out.parents, 'INVALID_REQUEST', 'Output must be outside input repository')
    out.mkdir(parents=True, exist_ok=False)
    result = {'schema_version': 'e11e12-1', 'status': 'FAILED', 'profile': request.get('profile'),
              'target_commit': request.get('target'), 'runtime': 'caller-process'}
    before = None
    project = None
    original_makefile = None
    try:
        save(out / 'request.json', request)
        source_head = command(['git', 'rev-parse', 'HEAD'], repo, out / 'source-head-before.log')
        source_status = command(['git', 'status', '--porcelain'], repo, out / 'source-before.log')
        before = tracked_hashes(repo)
        save(out / 'source-before.json', before)
        target = request.get('target', '')
        require(isinstance(target, str) and re.fullmatch(r'[0-9a-f]{40}', target), 'INVALID_REQUEST', 'Full target SHA required')
        profile = request.get('profile')
        require(profile in ('explicit', 'tinyexpr'), 'INVALID_REQUEST', 'Choose explicit or tinyexpr')
        expected = request.get('report_sha256', '')
        require(isinstance(expected, str) and re.fullmatch(r'[0-9a-f]{64}', expected), 'INVALID_REQUEST', 'Report SHA-256 required')
        report = Path(request['report']).resolve()
        producer = Path(request['producer_manifest']).resolve() if request.get('producer_manifest') else None
        envelope = consume(report, target, producer, expected)
        # Copy exactly the bytes whose digest was checked, then bind the saved input again.
        raw = report.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, 'ARTIFACT_HASH_MISMATCH', 'Input changed during consumption')
        (out / 'consumed-report.json').write_bytes(raw)
        if producer:
            (out / 'producer-result.json').write_bytes(producer.read_bytes())
        result['input'] = {'sha256': expected, 'kind': envelope['kind'], 'commit': target,
                           'job_id': envelope.get('job_id'), 'trace_id': envelope.get('trace_id')}
        project = out / 'target-project'
        snapshot(repo, target, project, out / 'logs', 'tinyexpr' if profile == 'tinyexpr' else None)
        original_makefile = (project / 'Makefile').read_bytes()
        save(out / 'target-before.json', tracked_hashes(project))
        command(['git', 'rev-parse', 'HEAD'], project, out / 'target-head-before.log')
        data = envelope['data']
        if profile == 'explicit':
            require(all(f['target'] in ('main.o', 'helper.o') for f in data['findings'] if f['type'] == 'MISSING'),
                    'UNSUPPORTED_TARGET', 'Expected main.o/helper.o findings')
            diff, plan = patch(project, data)
        else:
            diff, plan = patch_tinyexpr(project, data)
        require(bool(diff), 'NO_MISSING_DEPENDENCY', 'No missing dependency produced an edit')
        candidate = out / 'candidate.patch'
        candidate.write_text(diff, encoding='utf-8')
        save(out / 'repair-plan.json', plan)
        save(out / 'repair.json', {'schema_version': 'e11e12-1', 'kind': 'repair', 'commit': target,
                                  'status': 'SUCCEEDED', 'data': {'edits': plan, 'input_report': result['input']}})
        validator = validate_tinyexpr if profile == 'tinyexpr' else validate
        verdict = validator(project, candidate, out / 'validation')
        result['validation'] = verdict
        require(verdict['accepted'], 'REPAIR_REJECTED', 'Inspect validation/validation.json')
        recheck = full_check(project, out / 'final-full', clean_command='make clean',
                             build_command='make example' if profile == 'tinyexpr' else 'make app')
        save(out / 'recheck.json', recheck)
        require(recheck['status'] == 'SUCCEEDED' and not any(f['type'] == 'MISSING' for f in recheck['findings']),
                'RECHECK_FAILED', 'Dynamic recheck must succeed without missing dependencies')
        result['status'] = 'SUCCEEDED'
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        result['error'] = {'code': getattr(exc, 'code', 'EXECUTION_FAILED'), 'message': str(exc)}
    finally:
        if project is not None and original_makefile is not None:
            if result['status'] != 'SUCCEEDED':
                (project / 'Makefile').write_bytes(original_makefile)
            save(out / 'target-after.json', tracked_hashes(project))
            command(['git', 'rev-parse', 'HEAD'], project, out / 'target-head-after.log')
        if before is not None:
            after = tracked_hashes(repo)
            save(out / 'source-after.json', after)
            after_head = command(['git', 'rev-parse', 'HEAD'], repo, out / 'source-head-after.log')
            after_status = command(['git', 'status', '--porcelain'], repo, out / 'source-after.log')
            result['original_source_unchanged'] = before == after and source_head == after_head and source_status == after_status
            if not result['original_source_unchanged']:
                result.update(status='FAILED', error={'code': 'SOURCE_CHANGED', 'message': 'Input repository changed'})
        save(out / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = repair(json.loads(args.request.read_bytes()), args.out)
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'SUCCEEDED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
