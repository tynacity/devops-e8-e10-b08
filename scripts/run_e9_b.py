"""Collect E9 B evidence using the teaching lab's real Git/GCC functions."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'labs/e8e10'))
from lab import fixture, patch, run, save, scan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / 'work') or out == ROOT / 'work' or out.exists():
        parser.error('choose a new subdirectory of work/')
    out.mkdir(parents=True)
    (out / 'steps').mkdir()
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
              for name in ('labs/e8e10/lab.py', 'labs/e8e10/test_profile.py', 'scripts/run_e9_b.py')}
    save(out / 'execution-context.json', {
        'platform': platform.platform(), 'python': sys.version,
        'execution_mode': os.environ.get('E9_EXECUTION_MODE', 'native Linux; not course Docker evidence'),
        'source_sha256': hashes,
        'git': run(['git', '--version'], ROOT).strip(),
        'gcc': run(['gcc', '--version'], ROOT).splitlines()[0],
    })
    rows = []
    for style in ('direct', 'macro', 'mixed'):
        project = out / style
        fixture(project, style)
        report = scan(project)
        save(out / (style + '-input.json'), report)
        before = (project / 'Makefile').read_bytes()
        diff, plan = patch(project, report)
        candidate = out / (style + '.patch')
        candidate.write_text(diff)
        save(out / (style + '-plan.json'), plan)
        assert plan == [{'target': 'main.o', 'dependency': 'config.h', 'style': style}]
        assert (project / 'Makefile').read_bytes() == before
        run(['git', 'apply', '--check', str(candidate)], project)
        assert not run(['git', 'status', '--porcelain'], project).strip()
        copy = out / ('apply-demo' if style == 'macro' else 'apply-' + style)
        shutil.copytree(project, copy, ignore=shutil.ignore_patterns('.git'))
        run(['git', 'init', '-b', 'main'], copy)
        run(['git', 'config', 'user.name', 'E9VerificationCopy'], copy)
        run(['git', 'config', 'user.email', 'e9-copy@localhost'], copy)
        run(['git', 'add', '.'], copy)
        run(['git', 'commit', '-m', 'E9 input copy'], copy)
        run(['git', 'apply', '--check', str(candidate)], copy)
        run(['git', 'apply', str(candidate)], copy)
        after = (copy / 'Makefile').read_bytes()
        assert after.count(b'config.h') == 1
        assert b'unused.h' in after
        assert [l for l in before.splitlines() if l.startswith(b'\t')] == [l for l in after.splitlines() if l.startswith(b'\t')]
        assert not any(f['type'] == 'MISSING' for f in scan(copy)['findings'])
        result = {'style': style, 'patch_applies': True, 'source_unchanged': True,
                  'recipe_unchanged': True, 'redundant_preserved': True,
                  'copy_has_no_missing': True, 'input_commit': report['commit']}
        rows.append(result)
        save(out / 'steps' / (style + '.json'), result)
        print('STYLE_PASS', style)
    save(out / 'summary.json', {'stage': 'E9', 'track': 'B', 'passed': True, 'styles': rows})
    print('E9_B_PASS', out)


if __name__ == '__main__':
    main()
