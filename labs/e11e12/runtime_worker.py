"""One downstream operation, invoked inside an actual DRAFT image."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from lab import scan, patch, validate
from buildchecker.fullcheck import full_check


def run_tinyexpr(args):
    if args.action in ('full', 'scan'):
        argument = args.evidence if args.action == 'full' else args.cache
        argv = [sys.executable, '-B', str(args.tinyexpr_detector), args.action, str(args.project)]
        if argument is not None:
            argv.append(str(argument))
        # Run A's original worker in a separate interpreter with its own module paths.
        env = dict(os.environ, E11E12_PROJECT_PROFILE='tinyexpr')
        env.pop('PYTHONPATH', None)
        output = subprocess.run(argv, cwd=args.project, env=env, capture_output=True, check=True, timeout=600)
        return json.loads(output.stdout)

    from tinyexpr_repair import check_tinyexpr_report, patch_tinyexpr, validate_tinyexpr
    if args.action == 'patch':
        from pipeline import check_envelope, load_artifact
        target = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.project, text=True, timeout=30).strip()
        envelope = load_artifact(args.report, args.report_sha256)
        check_envelope(envelope, target, 'incremental-check')
        diff, edits = patch_tinyexpr(args.project, check_tinyexpr_report(envelope, target))
        return {'diff': diff, 'edits': edits}
    return validate_tinyexpr(args.project, args.patch, args.evidence)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', choices=['full', 'scan', 'patch', 'validate'], required=True)
    for name in ('project', 'result', 'evidence', 'cache', 'report', 'patch'):
        parser.add_argument('--' + name, type=Path, required=name in ('project', 'result'))
    parser.add_argument('--tinyexpr-detector', type=Path)
    parser.add_argument('--report-sha256')
    args = parser.parse_args()
    try:
        if args.tinyexpr_detector:
            data = run_tinyexpr(args)
        elif args.action == 'full':
            data = full_check(args.project, args.evidence)
        elif args.action == 'scan':
            data = scan(args.project, json.loads(args.cache.read_bytes()) if args.cache else None)
        elif args.action == 'patch':
            report = json.loads(args.report.read_bytes())
            diff, edits = patch(args.project, report['data'])
            data = {'diff': diff, 'edits': edits}
        else:
            data = validate(args.project, args.patch, args.evidence)
        result = {'ok': True, 'data': data}
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode(errors='replace') if isinstance(exc.stderr, bytes) else exc.stderr
        result = {'ok': False, 'error': {'code': 'COMMAND_FAILED', 'message': message or str(exc)}}
    except Exception as exc:
        result = {'ok': False, 'error': {'code': getattr(exc, 'code', 'EXECUTION_FAILED'), 'message': str(exc)}}
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
