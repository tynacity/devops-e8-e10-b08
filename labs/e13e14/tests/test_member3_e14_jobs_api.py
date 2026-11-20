"""Exercise the task API and four role HTTP handlers with a simulated Docker boundary."""
import contextlib
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import test_member3_e14_paired as fixtures
import jobs_api
from server import create_server


class JobsApiTests(unittest.TestCase):
    def environment(self, stack, root, profile='tinyexpr'):
        setup = fixtures.PairedLifecycleTests()
        repo, request = setup.fixture(root, profile)
        modules, _ = setup.hosts(stack, root)
        store, url = self.start_api(stack, root / 'work/api')
        return request, store, repo, modules, url

    def start_api(self, stack, storage):
        store = jobs_api.E14Store(storage)
        stack.callback(store.pool.shutdown)
        server = create_server(store, port=0)
        threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.03}, daemon=True).start()
        stack.callback(server.server_close)
        stack.callback(server.shutdown)
        return store, f'http://127.0.0.1:{server.server_port}'

    def call(self, url, path, body=None, expected=200, binary=False):
        raw = json.dumps(body).encode() if body is not None else None
        request = Request(url + path, data=raw, headers={'Content-Type': 'application/json'})
        try:
            response = urlopen(request, timeout=6)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            self.assertEqual(response.status, expected, data[:300])
            return (data, response.headers) if binary else json.loads(data)

    def submit(self, url, request, key, status=202):
        return self.call(url, '/v1/jobs', {'input': request, 'idempotency_key': key}, expected=status)

    def terminal(self, url, job):
        ends = time.monotonic() + 25
        while time.monotonic() < ends:
            state = self.call(url, '/v1/jobs/' + job)
            if state['status'] not in ('QUEUED', 'RUNNING'):
                return state
            time.sleep(0.05)
        self.fail(f'{job} did not reach a terminal state')

    def test_tinyexpr_api_carries_one_identity_through_four_roles_and_downloads(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory).resolve()
            request, store, repo, _, url = self.environment(stack, root)
            gate = threading.Event()
            stack.callback(gate.set)
            run_pipeline = store.run_pipeline

            def queued(job_request, out, job):
                if not gate.wait(timeout=15):
                    raise AssertionError('Test did not release queued job')
                return run_pipeline(job_request, out, job)

            with patch.object(store, 'run_pipeline', side_effect=queued):
                self.assertEqual(self.call(url, '/health')['schema_version'], 'e14-compose-1')
                first = self.submit(url, request, 'tinyexpr-normal')
                job = first['job_id']
                endpoint = '/v1/jobs/' + job
                try:
                    self.assertEqual(self.call(url, endpoint + '/artifacts', expected=409)['error'], 'RESULT_NOT_READY')
                    self.assertEqual(self.call(url, endpoint + '/files/request.json', expected=409)['error'], 'RESULT_NOT_READY')
                finally:
                    gate.set()
                state = self.terminal(url, job)
            self.assertEqual(state['status'], 'SUCCEEDED', state.get('error'))
            manifest = self.call(url, endpoint + '/artifacts')
            self.assertEqual((manifest['job_id'], manifest['trace_id']), (job, state['trace_id']))
            self.assertEqual([item['name'] for item in manifest['stages']], ['draft', 'full-check', 'incremental-check', 'repair', 'recheck'])
            evidence = store.root / job / 'evidence'
            with (evidence / 'unlisted.txt').open('x', encoding='utf-8') as extra:
                extra.write('Not declared in the finished manifest')
            self.assertEqual(self.call(url, endpoint + '/files/unlisted.txt', expected=404)['error'], 'NOT_FOUND')
            prefix = f'artifact://{job}/'
            by_name = {}
            for item in manifest['artifacts']:
                self.assertTrue(item['uri'].startswith(prefix))
                name = item['uri'].removeprefix(prefix)
                raw, headers = self.call(url, endpoint + '/files/' + quote(name, safe='/'), binary=True)
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest(), headers['X-Content-SHA256']),
                                 (item['bytes'], item['sha256'], item['sha256']))
                by_name[name] = raw
            for stage in manifest['stages']:
                key = stage['artifact']['uri'].removeprefix(prefix)
                payload = json.loads(by_name[key])
                self.assertEqual((payload['job_id'], payload['trace_id']), (job, state['trace_id']))
            for role in ('draft','baseline','target','incremental','repair','recheck'):
                payload = json.loads(by_name[f'{role}-request.json'])
                self.assertEqual((payload['job_id'], payload['trace_id']), (job, state['trace_id']))
            self.assertEqual(manifest['execution_image_id'], fixtures.IMAGE)
            runtime = json.loads(by_name['execution-runtime.json'])
            self.assertEqual(len(runtime['operations']), 6)
            self.assertTrue(manifest['original_source_unchanged'])
            self.assertFalse(fixtures.git(repo, 'status', '--porcelain'))
            self.assertEqual(self.submit(url, request, 'tinyexpr-normal')['job_id'], job)
            self.assertEqual(self.submit(url, dict(request, expected_output='different'), 'tinyexpr-normal', 409)['error'], 'IDEMPOTENCY_CONFLICT')
            self.assertEqual(len(store.jobs), 1)
            (evidence / 'request.json').write_bytes(b'changed-after-completion\n')
            self.assertEqual(self.call(url, endpoint + '/files/request.json', expected=409)['error'], 'ARTIFACT_HASH_MISMATCH')

    def test_timeout_terminal_state_then_new_headerflow_task_recovers(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory).resolve()
            request, store, _, modules, url = self.environment(stack, root, profile='explicit')

            def controlled_build(project, candidate, out, expected, timeout):
                if timeout < 0.1:
                    result = {'status': 'TIMED_OUT', 'error': 'simulated time budget'}
                    fixtures.save(out / 'result.json', result)
                    return result
                return fixtures.fake_build(project, candidate, out, expected, timeout)

            modules['draft'].auto_build = controlled_build
            timed_job = self.submit(url, dict(request, build_timeout=0.01), 'controlled-timeout')['job_id']
            failed = self.terminal(url, timed_job)
            self.assertEqual((failed['status'], failed['error']['code']), ('FAILED','TIMEOUT'))
            result = self.call(url, f'/v1/jobs/{timed_job}/artifacts')
            self.assertEqual(result['stages'], [])
            failed_artifact = self.call(url, f'/v1/jobs/{timed_job}/files/draft-build/result.json', binary=True)[0]
            self.assertEqual(json.loads(failed_artifact)['status'], 'TIMED_OUT')
            restored_job = self.submit(url, request, 'recovery')['job_id']
            recovered = self.terminal(url, restored_job)
            self.assertEqual(recovered['status'], 'SUCCEEDED', recovered.get('error'))
            self.assertNotEqual(recovered['trace_id'], failed['trace_id'])
            self.assertNotEqual(restored_job, timed_job)
            self.assertEqual(self.call(url, f'/v1/jobs/{timed_job}')['status'], 'FAILED')
            self.assertEqual(len(store.jobs), 2)

    def test_new_gateway_rejects_g2_mode_and_untrusted_input_fields(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory).resolve()
            request, store, _, _, url = self.environment(stack, root)
            for change in ({'mode': 'e13-b'}, {'profile': 'unknown'}, {'job_id': 'provided-by-caller'},
                           {'candidate': '/course/work/candidate.Dockerfile'}, {'build_timeout': False}):
                with self.subTest(change=change):
                    self.submit(url, dict(request, **change), 'invalid', 400)
            self.assertFalse(store.jobs)

    def test_restart_does_not_expose_result_from_interrupted_job(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory).resolve()
            stack.enter_context(patch.object(jobs_api.orchestrate, 'ROOT', root))
            storage = root / 'work/api'
            job = 'job-' + '1' * 32
            schema = jobs_api.E14Store.schema_version
            fixtures.save(storage / job / 'state.json', {
                'job_id': job, 'schema_version': schema, 'status': 'RUNNING',
                'idempotency_key': 'interrupted', 'request_hash': 'a' * 64,
            })
            evidence = storage / job / 'evidence'
            fixtures.save(evidence / 'request.json', {})
            fixtures.save(evidence / 'result.json', {
                'job_id': job, 'schema_version': schema, 'status': 'SUCCEEDED', 'trace_id': 'trace-' + '2' * 32,
                'artifacts': [jobs_api.artifact(evidence / 'request.json', evidence, job)],
            })
            _, url = self.start_api(stack, storage)
            endpoint = f'/v1/jobs/{job}'
            state = self.call(url, endpoint)
            self.assertEqual((state['status'], state['error']['code']), ('FAILED', 'SERVER_RESTARTED'))
            for suffix in ('/artifacts', '/files/request.json'):
                self.assertEqual(self.call(url, endpoint + suffix, expected=409)['error'], 'RESULT_STATE_MISMATCH')


if __name__ == '__main__':
    unittest.main()
