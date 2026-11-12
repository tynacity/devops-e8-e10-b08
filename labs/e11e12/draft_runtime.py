"""Execute downstream stages in the DRAFT image against the current mounted tree."""
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


class RuntimeFailure(ValueError):
    def __init__(self, message):
        self.code = 'DRAFT_RUNTIME_FAILED'
        super().__init__(message)


class DraftRuntime:
    def __init__(self, root, out, image_id, host_root=None, detector=None):
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
            raise RuntimeFailure('Expected a complete DRAFT image ID')
        self.root, self.out, self.image_id = root.resolve(), out, image_id
        host_root = host_root or os.environ.get('E11_HOST_ROOT')
        if self.root == Path('/course').resolve() and not host_root:
            raise RuntimeFailure('E11_HOST_ROOT is required for sibling-container mounts')
        self.host_root = host_root or self.root.as_posix()
        self.detector = detector
        if not PurePosixPath(self.host_root).is_absolute():
            raise RuntimeFailure('Host mount root must be an absolute Linux path')
        self.records = []

    def mapped(self, path):
        try:
            return '/course/' + Path(path).resolve().relative_to(self.root).as_posix()
        except ValueError as exc:
            raise RuntimeFailure('Stage path is outside the mounted repository') from exc

    def run(self, action, project, *, evidence=None, cache=None, report=None, patch=None, report_sha256=None):
        record_dir = self.out / 'runtime' / ('%02d-%s' % (len(self.records) + 1, action))
        record_dir.mkdir(parents=True, exist_ok=False)
        payload = record_dir / 'payload.json'
        argv = ['docker', 'run', '--rm', '--network', 'none', '--cap-add', 'SYS_PTRACE',
                '--user', '%s:%s' % (os.getuid(), os.getgid()), '-e', 'HOME=/tmp',
                '-e', 'PYTHONDONTWRITEBYTECODE=1',
                '-e', 'PYTHONPATH=/course/labs/e11e12:/course/labs/e8e10:/course/labs/e11e12/environment/services/buildchecker',
                '-v', self.host_root + ':/course', '-w', '/course', '--entrypoint', 'python3',
                self.image_id, 'labs/e11e12/runtime_worker.py', '--action', action,
                '--project', self.mapped(project), '--result', self.mapped(payload)]
        for flag, path in [('evidence', evidence), ('cache', cache), ('report', report), ('patch', patch)]:
            if path is not None:
                argv += ['--' + flag, self.mapped(path)]
        if self.detector is not None:
            argv += ['--tinyexpr-detector', self.mapped(self.detector)]
        if report_sha256 is not None:
            argv += ['--report-sha256', report_sha256]
        record = {'action': action, 'image_id': self.image_id, 'command': argv,
                  'project': str(project), 'host_root': self.host_root}
        self.records.append(record)
        try:
            with (record_dir / 'stdout.log').open('wb') as stdout, (record_dir / 'stderr.log').open('wb') as stderr:
                run = subprocess.run(argv, cwd=self.root, stdout=stdout, stderr=stderr, timeout=900)
            record['exit_code'] = run.returncode
            if not payload.is_file():
                raise RuntimeFailure('DRAFT stage failed; inspect ' + str(record_dir))
            result = json.loads(payload.read_bytes())
            if not result.get('ok'):
                error = result['error']
                failure = RuntimeFailure(error['message'])
                failure.code = error['code']
                raise failure
            if run.returncode:
                raise RuntimeFailure('DRAFT stage exited unsuccessfully; inspect ' + str(record_dir))
            return result['data']
        finally:
            (record_dir / 'command.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
