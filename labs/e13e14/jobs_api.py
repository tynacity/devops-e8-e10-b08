"""Loopback asynchronous API for the E14 four-role orchestrator."""
import argparse
import json
import os
from pathlib import Path
import re
import uuid

import orchestrate
from pipeline import Failure, artifact, save
from server import Store, create_server


INPUT_KEYS = {'mode', 'profile', 'repo', 'candidate', 'base', 'target', 'expected_output', 'build_timeout'}


def public_path(name):
    if not isinstance(name, str) or '\\' in name or ':' in name:
        return False
    parts = name.lower().split('/')
    return all(part not in ('', '.', '..', '.git', '.env', 'id_rsa', 'id_ed25519')
               and not part.startswith('.env.') and not part.endswith(('.pem', '.key', '.pfx')) for part in parts)


def published_result(result, job_id, trace_id):
    if (result.get('job_id'), result.get('trace_id'), result.get('schema_version')) != (job_id, trace_id, E14Store.schema_version):
        raise Failure('ARTIFACT_ID_MISMATCH', 'Four-role result does not belong to this API task')
    if result.get('status') not in ('SUCCEEDED', 'FAILED', 'TIMED_OUT'):
        raise Failure('WORKER_FAILED', 'Four-role result is missing a terminal state')
    published = {}
    for entry in result['artifacts']:
        name = entry['uri']
        if public_path(name):
            if name in published:
                raise Failure('ARTIFACT_ID_MISMATCH', 'Duplicate artifact in four-role result')
            published[name] = dict(entry, uri=f'artifact://{job_id}/{name}')
    stages = []
    for stage in result['stages']:
        entry = stage['artifact']
        bound = published.get(entry['uri'])
        if bound is None or bound['sha256'] != entry['sha256']:
            raise Failure('ARTIFACT_HASH_MISMATCH', 'Stage output differs from its published artifact')
        stages.append(dict(stage, artifact=bound))
    response = dict(result, artifacts=list(published.values()), stages=stages)
    if response['status'] != 'SUCCEEDED':
        response['error'] = {'code': result.get('error_code') or 'ROLE_FAILED',
                             'message': result.get('error') or 'Inspect the four-role evidence'}
    return response


class E14Store(Store):
    schema_version = 'e14-compose-1'
    declared_only = True

    def __init__(self, root):
        root = root.resolve()
        work = (orchestrate.ROOT / 'work').resolve()
        if root == work or not root.is_relative_to(work):
            raise ValueError('E14 job storage must be below work/')
        for state in root.glob('job-*/state.json'):
            if json.loads(state.read_text(encoding='utf-8')).get('schema_version') != self.schema_version:
                raise ValueError('Use an E14-only job store')
        self.service_id = os.environ.get('E14_SERVICE_ID') or 'course-e14-four-role'
        super().__init__(root)

    def validate_input(self, request):
        if request.get('mode') != 'e12' or set(request) - INPUT_KEYS:
            raise ValueError('Expected a four-role e12 request with the documented fields')
        if request.get('profile') is not None and request['profile'] not in orchestrate.PROFILES:
            raise ValueError('Expected profile explicit or tinyexpr')
        for field in ('base', 'target'):
            value = request.get(field)
            if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{40}', value):
                raise ValueError(f'{field} requires a full lowercase Git SHA')
        data = (orchestrate.ROOT / 'data').resolve()
        for field, predicate in (('repo', Path.is_dir), ('candidate', Path.is_file)):
            target = orchestrate.host_path(request.get(field))
            if target == data or not target.is_relative_to(data) or not predicate(target):
                raise ValueError(f'{field} must exist below /course/data')
        if not isinstance(request.get('expected_output', '1'), str) or (request.get('profile') and not isinstance(request.get('expected_output'), str)):
            raise ValueError('expected_output must be a string and is required for a paired profile')
        orchestrate.build_budget(request.get('build_timeout', 600))

    def run_pipeline(self, request, out, job_id):
        trace_id = 'trace-' + uuid.uuid4().hex
        try:
            result = orchestrate.execute(request, out, job_id=job_id, trace_id=trace_id)
            response = published_result(result, job_id, trace_id)
        except Exception as error:
            request_file = out / 'request.json'
            if not request_file.exists():
                save(request_file, request)
            response = {'schema_version': self.schema_version, 'job_id': job_id, 'trace_id': trace_id,
                        'status': 'FAILED', 'stages': [], 'artifacts': [artifact(request_file, out, job_id)],
                        'error': {'code': getattr(error, 'code', 'WORKER_FAILED'), 'message': str(error)}}
        save(out / 'result.json', response)
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18594)
    parser.add_argument('--root', type=Path, default=orchestrate.ROOT / 'work/e14-api-jobs')
    options = parser.parse_args()
    if not 1 <= options.port <= 65535:
        parser.error('--port must be 1..65535')
    try:
        store = E14Store(options.root)
    except ValueError as error:
        parser.error(str(error))
    httpd = None
    try:
        httpd = create_server(store, host='127.0.0.1', port=options.port)
        print(f'E14_API=127.0.0.1:{options.port} SERVICE_ID={store.service_id} STORE={store.root}', flush=True)
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if httpd is not None:
            httpd.server_close()
        store.pool.shutdown()


if __name__ == '__main__':
    main()
