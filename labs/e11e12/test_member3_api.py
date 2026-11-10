"""241880546: real HTTP contracts and sibling-container source mapping."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pipeline
import server
from draft_runtime import DraftRuntime, RuntimeFailure


class Member3ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = server.Store(self.root / 'jobs')
        self.release = threading.Event()
        self.started = threading.Event()
        self.calls = []

        def execute(request, out, jid):
            self.calls.append(jid)
            self.started.set()
            self.release.wait(10)
            out.mkdir(parents=True)
            data = b'fixture patch\n'
            (out / 'candidate.patch').write_bytes(data)
            result = {'status': 'SUCCEEDED', 'job_id': jid, 'trace_id': 'trace-http',
                      'artifacts': [{'uri': 'artifact://' + jid + '/candidate.patch',
                                     'sha256': hashlib.sha256(data).hexdigest()}]}
            pipeline.save(out / 'result.json', result)
            return result

        self.mock = patch.object(server, 'execute', execute)
        self.mock.start()
        self.http = server.create_server(self.store, port=0)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.http.server_port)
        self.request = {'mode': 'e12', 'repo': str(pipeline.ROOT / 'data/http-fixture'),
                        'base': 'a' * 40, 'target': 'b' * 40}

    def tearDown(self):
        self.release.set()
        self.store.pool.shutdown()
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        self.mock.stop()
        self.temp.cleanup()

    def http_call(self, route, body=None):
        payload = json.dumps(body).encode() if body is not None else None
        request = Request(self.url + route, data=payload, headers={'Content-Type': 'application/json'})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as response_error:
            response = response_error
        with response:
            return response.status, dict(response.headers), response.read()

    def submit(self, **changes):
        code, _, body = self.http_call('/v1/jobs', {'idempotency_key': 'member3',
                                                  'input': dict(self.request, **changes)})
        return code, json.loads(body)

    def wait_finished(self, jid):
        self.release.set()
        for _ in range(100):
            code, _, body = self.http_call('/v1/jobs/' + jid)
            state = json.loads(body)
            if state['status'] == 'SUCCEEDED':
                return state
            time.sleep(.01)
        self.fail('Job did not finish')

    def test_http_idempotency_and_conflict_do_not_repeat_execution(self):
        code, first = self.submit()
        self.assertEqual(code, 202)
        self.assertTrue(self.started.wait(5))
        self.assertEqual(self.submit()[1]['job_id'], first['job_id'])
        self.assertEqual(self.submit(target='c' * 40), (409, {'error': 'IDEMPOTENCY_CONFLICT'}))
        self.wait_finished(first['job_id'])
        self.assertEqual(self.calls, [first['job_id']])

    def test_download_hash_matches_manifest_and_traversal_is_rejected(self):
        _, first = self.submit()
        jid = first['job_id']
        self.wait_finished(jid)
        code, _, body = self.http_call('/v1/jobs/' + jid + '/artifacts')
        self.assertEqual(code, 200)
        manifest = json.loads(body)
        code, headers, data = self.http_call('/v1/jobs/' + jid + '/files/candidate.patch')
        self.assertEqual(code, 200)
        self.assertEqual(headers['X-Content-SHA256'], manifest['artifacts'][0]['sha256'])
        self.assertEqual(hashlib.sha256(data).hexdigest(), headers['X-Content-SHA256'])
        (self.root / 'outside.txt').write_text('private')
        self.assertEqual(self.http_call('/v1/jobs/' + jid + '/files/%2e%2e/%2e%2e/outside.txt')[0], 404)
        self.assertEqual(self.http_call('/v1/jobs/' + jid + '/files/.git/config')[0], 404)

    def test_running_job_has_no_artifact_manifest(self):
        _, first = self.submit()
        self.assertTrue(self.started.wait(5))
        self.assertEqual(self.http_call('/v1/jobs/' + first['job_id'] + '/artifacts')[0], 409)

    def test_restart_preserves_completed_job_and_marks_unfinished_job(self):
        _, first = self.submit()
        self.wait_finished(first['job_id'])
        state = {'schema_version': 'e11e12-1', 'job_id': 'job-interrupted', 'status': 'RUNNING',
                 'idempotency_key': 'interrupted', 'request_hash': 'old'}
        pipeline.save(self.store.root / 'job-interrupted/state.json', state)
        restored = server.Store(self.store.root)
        try:
            self.assertEqual(restored.jobs[first['job_id']]['status'], 'SUCCEEDED')
            self.assertEqual(restored.jobs['job-interrupted']['error']['code'], 'SERVER_RESTARTED')
            with patch.object(restored.pool, 'submit') as queued:
                self.assertEqual(restored.submit(self.request, 'member3')['job_id'], first['job_id'])
                queued.assert_not_called()
        finally:
            restored.pool.shutdown()


class Member3RuntimeTests(unittest.TestCase):
    def test_actual_working_copy_is_mapped_to_the_host_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = 'sha256:' + 'd' * 64
            runtime = DraftRuntime(root, root / 'evidence', image, host_root='/srv/student/241880546')
            self.assertEqual(runtime.mapped(root / 'work/current-target'), '/course/work/current-target')
            with self.assertRaises(RuntimeFailure):
                runtime.mapped(root.parent / 'outside')

    def test_docker_command_uses_draft_id_and_current_source_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = 'sha256:' + 'e' * 64
            runtime = DraftRuntime(root, root / 'evidence', image, host_root='/srv/student/241880546')
            def execute(argv, **kwargs):
                mapped = argv[argv.index('--result') + 1]
                destination = root / mapped.removeprefix('/course/')
                destination.write_text(json.dumps({'ok': True, 'data': {'current': True}}))
                return type('Completed', (), {'returncode': 0})()
            with patch('draft_runtime.os.getuid', return_value=1000, create=True), \
                 patch('draft_runtime.os.getgid', return_value=1000, create=True), \
                 patch('draft_runtime.subprocess.run', side_effect=execute) as invoked:
                self.assertEqual(runtime.run('scan', root / 'work/current-target'), {'current': True})
            argv = invoked.call_args.args[0]
            self.assertIn(image, argv)
            self.assertEqual(argv[argv.index('-v') + 1], '/srv/student/241880546:/course')
            self.assertEqual(argv[argv.index('--project') + 1], '/course/work/current-target')
