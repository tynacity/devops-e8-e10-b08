"""Bounded E9 implicit-rule experiment with an externally supplied model reply."""
import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from lab import commit, run, save

INPUTS = ('Makefile', 'main.c', 'helper.c', 'config.h', '.gitignore')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inputs(project):
    return {name: digest((project / name).read_bytes()) for name in INPUTS}


def execute(command, project, logfile):
    result = subprocess.run(command, cwd=project, text=True, capture_output=True, timeout=30)
    save(logfile.with_suffix('.json'), {'command': command, 'exit_code': result.returncode,
                                      'stdout': result.stdout, 'stderr': result.stderr})
    logfile.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError('COMMAND_FAILED ' + repr(command))
    return result.stdout.strip()


def check_input(out):
    manifest = json.loads((out / 'input-manifest.json').read_text())
    project = out / 'project'
    if {item.name for item in project.iterdir() if item.name != '.git'} != set(INPUTS):
        raise ValueError('STALE_INPUT unexpected files')
    if inputs(project) != manifest['sha256'] or run(['git', 'rev-parse', 'HEAD'], project).strip() != manifest['commit']:
        raise ValueError('STALE_INPUT')
    if digest((out / 'prompt.txt').read_bytes()) != manifest['prompt_sha256']:
        raise ValueError('PROMPT_HASH_MISMATCH')
    return manifest


def prepare(out):
    if out.exists():
        raise ValueError('OUTPUT_MUST_BE_NEW')
    project = out / 'project'
    project.mkdir(parents=True)
    (project / 'Makefile').write_text(
        'CC = gcc\nCFLAGS = -O0\nOBJS = main.o helper.o\n\n'
        'app: $(OBJS)\n\t$(CC) $(OBJS) -o $@\n\n'
        '%.o: %.c\n\t$(CC) $(CFLAGS) -c $< -o $@\n\n'
        '.PHONY: clean\nclean:\n\trm -f $(OBJS) app\n')
    (project / 'main.c').write_text('#include <stdio.h>\n#include "config.h"\nint helper(void);\nint main(void){printf("%d\\n",VALUE+helper());return 0;}\n')
    (project / 'helper.c').write_text('int helper(void){return 0;}\n')
    (project / 'config.h').write_text('#define VALUE 1\n')
    (project / '.gitignore').write_text('*.o\n*.d\napp\n')
    run(['git', 'init', '-b', 'main'], project)
    run(['git', 'config', 'user.name', 'ImplicitFixture'], project)
    run(['git', 'config', 'user.email', 'fixture@localhost'], project)
    sha = commit(project, 'Implicit pattern-rule baseline')
    execute(['make', 'app'], project, out / 'baseline-build.log')
    before = execute(['./app'], project, out / 'baseline-output.log')
    time.sleep(1.05)
    (project / 'config.h').write_text('#define VALUE 2\n')
    execute(['make', 'app'], project, out / 'baseline-incremental.log')
    after = execute(['./app'], project, out / 'baseline-stale-output.log')
    baseline = {'before': before, 'after_header_change': after,
                'expected_after_change': '2', 'missing_rebuild': before == after == '1'}
    save(out / 'baseline.json', baseline)
    if not baseline['missing_rebuild']:
        raise ValueError('BASELINE_NOT_REPRODUCED')
    (project / 'config.h').write_text('#define VALUE 1\n')
    execute(['make', 'clean'], project, out / 'baseline-clean.log')
    actual = execute(['gcc', '-MM', '-MT', 'main.o', 'main.c'], project, out / 'gcc-dependencies.log')
    if 'config.h' not in actual.split():
        raise ValueError('EXPECTED_HEADER_NOT_OBSERVED')
    report = {'schema_version': 'e9-implicit-1', 'commit': sha,
              'detector': 'GCC_MM_AND_OBSERVED_MAKE_NON_REBUILD',
              'profile': 'fixed two-source pattern-rule fixture; not general Make parsing',
              'findings': [{'type': 'MISSING', 'target': 'main.o', 'dependency': 'config.h'}],
              'evidence': baseline}
    save(out / 'md-report.json', report)
    context = {name: (project / name).read_text() for name in INPUTS}
    prompt = (
        'Act as the candidate-generating LLM for a bounded MDfixer E9 reproduction.\n'
        'Generate a minimal Makefile-only repair for the supplied implicit pattern rule.\n'
        'Use compiler-generated .d dependencies so current, newly added and transitive local headers\n'
        'trigger rebuilds. Preserve pattern rules, object list, linking behavior, clean target,\n'
        'and default app goal. Clean must remove generated .d files. Do not hard-code config.h\n'
        'as an explicit main.o prerequisite. Do not change C/header files or download anything.\n'
        'Return ONLY a JSON object with keys makefile (complete file with TAB recipes) and explanation.\n'
        'Do not use tools, edit files or run tests; return the candidate for independent validation.\n'
        'Project files and detector evidence follow as JSON data:\n'
        + json.dumps({'files': context, 'report': report}, indent=2) + '\n')
    (out / 'prompt.txt').write_text(prompt)
    save(out / 'input-manifest.json', {'commit': sha, 'sha256': inputs(project),
                                     'prompt_sha256': digest((out / 'prompt.txt').read_bytes())})


def receive(out, response, provenance):
    raw = response.encode('utf-8') if isinstance(response, str) else response
    if digest(raw) != provenance.get('response_sha256'):
        raise ValueError('RESPONSE_HASH_MISMATCH')
    manifest = check_input(out)
    if provenance.get('prompt_sha256') != manifest['prompt_sha256']:
        raise ValueError('PROVENANCE_PROMPT_MISMATCH')
    if not provenance.get('provider') or not provenance.get('model'):
        raise ValueError('MISSING_MODEL_PROVENANCE')
    if (out / 'raw-response.txt').exists():
        raise ValueError('RESPONSE_ALREADY_RECORDED')
    payload = json.loads(raw)
    candidate = payload['makefile']
    if not isinstance(candidate, str) or not candidate.strip():
        raise ValueError('INVALID_MAKEFILE_RESPONSE')
    (out / 'raw-response.txt').write_bytes(raw)
    (out / 'candidate.Makefile').write_text(candidate)
    original = (out / 'project/Makefile').read_text()
    diff = ''.join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
                                      fromfile='a/Makefile', tofile='b/Makefile'))
    (out / 'candidate.patch').write_text(diff)
    save(out / 'provenance.json', dict(provenance, candidate_sha256=digest((out / 'candidate.Makefile').read_bytes()),
                                     patch_sha256=digest((out / 'candidate.patch').read_bytes()),
                                     input_commit=manifest['commit'], explanation=payload.get('explanation', '')))


def verify(out):
    check_input(out)
    provenance = json.loads((out / 'provenance.json').read_text())
    for name, key in [('candidate.Makefile', 'candidate_sha256'), ('candidate.patch', 'patch_sha256'),
                      ('raw-response.txt', 'response_sha256')]:
        if digest((out / name).read_bytes()) != provenance[key]:
            raise ValueError('CANDIDATE_HASH_MISMATCH')
    project = out / 'project'
    before = inputs(project)
    evidence = out / 'validation'
    evidence.mkdir()
    sandbox = evidence / 'sandbox'
    shutil.copytree(project, sandbox, ignore=shutil.ignore_patterns('.git', '*.o', '*.d', 'app'))
    checks, outputs, error = {}, [], None
    expected_sources = {name: (sandbox / name).read_bytes() for name in INPUTS if name != 'Makefile'}
    expected_sources['Makefile'] = (out / 'candidate.Makefile').read_bytes()

    def ensure_sources():
        for name, expected in expected_sources.items():
            if not (sandbox / name).is_file() or (sandbox / name).read_bytes() != expected:
                raise ValueError('SANDBOX_SOURCE_MODIFIED ' + name)
    try:
        run(['git', 'init', '-b', 'main'], sandbox)
        execute(['git', 'apply', '--check', str((out / 'candidate.patch').resolve())], sandbox, evidence / 'apply-check.log')
        execute(['git', 'apply', str((out / 'candidate.patch').resolve())], sandbox, evidence / 'apply.log')
        if (sandbox / 'Makefile').read_bytes() != (out / 'candidate.Makefile').read_bytes():
            raise ValueError('PATCH_CANDIDATE_MISMATCH')
        checks['patch_applies'] = True
        execute(['make', 'clean'], sandbox, evidence / 'clean.log')
        ensure_sources()
        execute(['make'], sandbox, evidence / 'build.log')
        ensure_sources()
        outputs.append(execute(['./app'], sandbox, evidence / 'output-1.log'))
        checks['initial_output'] = outputs[-1] == '1'
        depfile = sandbox / 'main.d'
        checks['generated_depfile'] = depfile.exists() and 'config.h' in depfile.read_text().split()
        database = execute(['make', '-np', 'app'], sandbox, evidence / 'make-database.log')
        match = re.search(r'^MAKEFILE_LIST\s*:?=\s*(.*)$', database, re.M)
        checks['make_loads_depfiles'] = bool(match and 'main.d' in match[1].split() and 'helper.d' in match[1].split())
        ensure_sources()
        timestamps = {name: (sandbox / name).stat().st_mtime_ns for name in ('main.o', 'helper.o', 'app')}
        execute(['make'], sandbox, evidence / 'unchanged-make.log')
        ensure_sources()
        checks['unchanged_input_does_not_rebuild'] = all(
            (sandbox / name).stat().st_mtime_ns == value for name, value in timestamps.items())
        for number in (2, 3, 4):
            time.sleep(1.05)
            if number == 2:
                (sandbox / 'config.h').write_text('#define VALUE 2\n')
            elif number == 3:
                (sandbox / 'headers').mkdir()
                (sandbox / 'headers/extra.h').write_text('#define EXTRA 3\n')
                (sandbox / 'config.h').write_text('#include "headers/extra.h"\n#define VALUE EXTRA\n')
            else:
                (sandbox / 'headers/extra.h').write_text('#define EXTRA 4\n')
            expected_sources['config.h'] = (sandbox / 'config.h').read_bytes()
            if number >= 3:
                expected_sources['headers/extra.h'] = (sandbox / 'headers/extra.h').read_bytes()
            previous = (sandbox / 'main.o').stat().st_mtime_ns
            helper_previous = (sandbox / 'helper.o').stat().st_mtime_ns
            execute(['make'], sandbox, evidence / ('incremental-' + str(number) + '.log'))
            ensure_sources()
            outputs.append(execute(['./app'], sandbox, evidence / ('output-' + str(number) + '.log')))
            checks['rebuild_' + str(number)] = (sandbox / 'main.o').stat().st_mtime_ns > previous and outputs[-1] == str(number)
            checks['unaffected_helper_' + str(number)] = (sandbox / 'helper.o').stat().st_mtime_ns == helper_previous
        checks['new_transitive_header_in_depfile'] = depfile.exists() and 'headers/extra.h' in depfile.read_text().split()
        if depfile.exists():
            (evidence / 'main.d.saved').write_bytes(depfile.read_bytes())
        execute(['make', 'clean'], sandbox, evidence / 'final-clean.log')
        ensure_sources()
        checks['clean_removes_depfiles'] = not list(sandbox.glob('*.d'))
        checks['sandbox_sources_preserved'] = True
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        error = str(exc)
    unchanged = inputs(project) == before
    result = {'passed': bool(checks) and all(checks.values()) and unchanged and error is None,
              'checks': checks, 'outputs': outputs, 'error': error, 'source_unchanged': unchanged,
              'scope': 'E9 candidate qualification in copy; no write-back or E10 acceptance',
              'candidate_sha256': provenance['candidate_sha256']}
    save(evidence / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'receive', 'verify'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--response', type=Path)
    parser.add_argument('--provenance', type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    root = Path(__file__).resolve().parents[2]
    if not out.is_relative_to(root / 'work') or out == root / 'work':
        parser.error('out must be a subdirectory of repository work/')
    if args.stage == 'prepare':
        prepare(out)
        print('PROMPT_READY', out / 'prompt.txt')
    elif args.stage == 'receive':
        if not args.response or not args.provenance:
            parser.error('receive requires response and provenance files')
        receive(out, args.response.read_bytes(), json.loads(args.provenance.read_text()))
        print('CANDIDATE_RECORDED')
    else:
        result = verify(out)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
