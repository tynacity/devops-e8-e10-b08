"""One downstream operation, invoked inside an actual DRAFT image."""
import argparse
import json
from pathlib import Path
from lab import scan, patch, validate
from buildchecker.fullcheck import full_check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', choices=['full', 'scan', 'patch', 'validate'], required=True)
    for name in ('project', 'result', 'evidence', 'cache', 'report', 'patch'):
        parser.add_argument('--' + name, type=Path, required=name in ('project', 'result'))
    args = parser.parse_args()
    try:
        if args.action == 'full':
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
    except Exception as exc:
        result = {'ok': False, 'error': {'code': getattr(exc, 'code', 'EXECUTION_FAILED'), 'message': str(exc)}}
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
