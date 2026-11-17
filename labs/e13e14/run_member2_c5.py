"""C5 evidence collector for the explicit Make profile, inside the selected runtime."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e11e12'))
from pipeline import command, save, snapshot, tracked_hashes
from lab import patch, scan, validate
from tinyexpr_repair import full_check


def state(repo):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()
    return {'head': git('rev-parse', 'HEAD'), 'status': git('status', '--porcelain'),
            'diff_summary': git('diff', '--summary'), 'files': tracked_hashes(repo)}


def execute(repo, target, out):
    out.mkdir(parents=True, exist_ok=False)
    before = state(repo)
    save(out / 'source-before.json', before)
    cases = []
    for name in ('positive', 'missing-config', 'compile-error'):
        folder = out / name
        project = folder / 'target-project'
        snapshot(repo, target, project, folder / 'logs')
        target_before = state(project)
        save(folder / 'target-before.json', target_before)
        report = scan(project)
        save(folder / 'input-md.json', report)
        diff, plan = patch(project, report)
        original = (project / 'Makefile').read_text()
        if name != 'positive':
            changed = original.replace('main.o: main.c config.h unused.h', 'main.o: main.c unused.h extra.h')
            if name == 'compile-error':
                changed = changed.replace('gcc $(CFLAGS) -c main.c', 'gcc --member2-c5-invalid-option $(CFLAGS) -c main.c')
            assert changed != original, 'C5 injector requires the original H2 Makefile'
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
    result = {'status': 'SUCCEEDED', 'scope': 'H2 course fixture C5 component verification',
              'target': target, 'original_source_unchanged': True, 'cases': cases}
    save(out / 'result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.repo.resolve(), args.target, args.out.resolve()), indent=2))
