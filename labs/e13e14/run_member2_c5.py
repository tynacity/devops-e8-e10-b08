"""C5 evidence collector for the explicit Make profile, inside the selected runtime."""
import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e11e12'))
from pipeline import command, save, snapshot, tracked_hashes
from lab import patch, scan, validate
from tinyexpr_repair import consume, full_check


def state(repo):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()
    return {'head': git('rev-parse', 'HEAD'), 'status': git('status', '--porcelain'),
            'diff_summary': git('diff', '--summary'), 'files': tracked_hashes(repo)}


def injected_makefile(corrected, case):
    if case == 'missing-config':
        match = re.search(r'^main\.o: ([^\n]*)$', corrected, re.M)
        if not match or 'config.h' not in match[1].split():
            raise ValueError('C5 requires a repaired direct main.o dependency on config.h')
        dependencies = [name for name in match[1].split() if name != 'config.h']
        return corrected[:match.start(1)] + ' '.join(dependencies) + corrected[match.end(1):]
    if case == 'compile-error':
        recipe = 'gcc $(CFLAGS) -c main.c'
        if corrected.count(recipe) != 1:
            raise ValueError('C5 requires exactly one main.c GCC recipe')
        return corrected.replace(recipe, 'gcc --member2-c5-invalid-option $(CFLAGS) -c main.c')
    raise ValueError('Unknown C5 injection')


def execute(repo, target, out, report_path=None, producer=None, report_sha256=None):
    out.mkdir(parents=True, exist_ok=False)
    before = state(repo)
    save(out / 'source-before.json', before)
    envelope = None
    if report_path is not None:
        if producer is None or report_sha256 is None:
            raise ValueError('C5 actual-report mode requires producer manifest and SHA-256')
        envelope = consume(report_path, target, producer, report_sha256)
        raw = report_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != report_sha256:
            raise ValueError('Report changed during consumption')
        (out / 'consumed-report.json').write_bytes(raw)
        (out / 'producer-result.json').write_bytes(producer.read_bytes())
    cases = []
    for name in ('positive', 'missing-config', 'compile-error'):
        folder = out / name
        project = folder / 'target-project'
        snapshot(repo, target, project, folder / 'logs')
        target_before = state(project)
        save(folder / 'target-before.json', target_before)
        report = envelope['data'] if envelope is not None else scan(project)
        save(folder / 'input-md.json', report)
        diff, plan = patch(project, report)
        original = (project / 'Makefile').read_text()
        if name != 'positive':
            reference = folder / 'reference.patch'
            reference.write_text(diff, encoding='utf-8')
            injection_base = folder / 'injection-base'
            injection_base.mkdir()
            (injection_base / 'Makefile').write_text(original)
            command(['git', 'init', '-b', 'main'], injection_base, folder / 'reference-init.log')
            command(['git', 'apply', str(reference)], injection_base, folder / 'reference-apply.log')
            changed = injected_makefile((injection_base / 'Makefile').read_text(), name)
            diff = ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                                               fromfile='a/Makefile', tofile='b/Makefile'))
        candidate = folder / 'candidate.patch'
        candidate.write_text(diff, encoding='utf-8')
        save(folder / 'repair-plan.json', plan if name == 'positive' else {'injection': name})
        verdict = validate(project, candidate, folder / 'validation')
        after = state(project)
        save(folder / 'target-after.json', after)
        if name == 'positive':
            assert verdict['accepted'] and all(verdict['checks'].values()), verdict
            command(['make', 'clean'], project, folder / 'clean.log')
            command(['make', 'app'], project, folder / 'build.log')
            assert command(['./app'], project, folder / 'behavior.log') == '1'
            recheck = full_check(project, folder / 'final-full')
            save(folder / 'recheck.json', recheck)
            assert recheck['status'] == 'SUCCEEDED' and not any(f['type'] == 'MISSING' for f in recheck['findings'])
            if (project / 'tests/verify_behavior.py').is_file():
                command(['python3', 'tests/verify_behavior.py'], project, folder / 'project-behavior.log')
        else:
            assert not verdict['accepted'] and verdict['rollback'] and before['head'] == target
            assert target_before == after, 'Rejected target changed'
            if name == 'missing-config':
                assert not verdict['checks']['header_change'] and not verdict['checks']['no_missing']
            else:
                assert verdict['error'] and 'member2-c5-invalid-option' in verdict['error']
        cases.append({'case': name, 'accepted': verdict['accepted'], 'rollback': verdict['rollback'],
                      'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
                      'target_files_unchanged': target_before['files'] == after['files']})
    after = state(repo)
    save(out / 'source-after.json', after)
    assert before == after, 'Original input repository changed'
    result = {'status': 'SUCCEEDED', 'scope': 'Explicit Make C5 verification',
              'target': target, 'original_source_unchanged': True, 'cases': cases}
    if envelope is not None:
        result['input_report'] = {'sha256': report_sha256, 'job_id': envelope.get('job_id'),
                                  'trace_id': envelope.get('trace_id'), 'kind': envelope['kind']}
    save(out / 'result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--producer-manifest', type=Path)
    parser.add_argument('--report-sha256')
    args = parser.parse_args()
    print(json.dumps(execute(args.repo.resolve(), args.target, args.out.resolve(), args.report,
                             args.producer_manifest, args.report_sha256), indent=2))
