"""Local loopback HTTP checks with a fake Docker boundary; not E14 deployment evidence."""
import contextlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


STACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STACK))
import orchestrate
import paired_runtime
from pipeline import Failure, save


IMAGE = 'sha256:' + 'a' * 64


class FakeDraftRuntime:
    def __init__(self, root, out, image_id, detector=None):
        self.root, self.image_id, self.detector = root, image_id, detector
        self.records = []

    def mapped(self, path):
        return '/course/' + path.relative_to(self.root).as_posix()

    def run(self, action, project, *, evidence=None, cache=None, component_request=None):
        self.records.append(dict(action=action, project=self.mapped(project), image_id=self.image_id, fake=True))
        targets = ('example.o', 'tinyexpr.o', 'example') if self.detector else ('main.o', 'helper.o')
        finding = dict(type='MISSING', target=targets[0], dependency='config.h')
        findings = [finding] if project.name == 'target-project' and project.parent.name != 'component' else []
        if action == 'full':
            report = dict(status='SUCCEEDED', findings=findings, observed_targets=list(targets))
            save(evidence / 'actual-graph.json', [])
            save(evidence / 'findings.json', report)
            return report
        if action == 'scan':
            commit = subprocess.check_output(['git', '-C', str(project), 'rev-parse', 'HEAD'], text=True).strip()
            require_cache = project.name == 'target-project'
            if require_cache and (cache is None or not cache.is_file()):
                raise AssertionError('Expected the saved baseline cache')
            graph = {target: [] for target in targets}
            return dict(schema_version='e8e10-1', commit=commit, actual=graph, declared=graph, findings=findings)
        if action != 'mdfixer' or self.detector is not None:
            raise AssertionError('Expected the member 2 worker, without the external detector flag')
        request = json.loads(component_request.read_bytes())
        original = self.root / request['report'].removeprefix('/course/')
        producer = self.root / request['producer_manifest'].removeprefix('/course/')
        envelope = paired_runtime.consume(original, request['target'], producer, request['report_sha256'])
        evidence.mkdir(parents=True)
        (evidence / 'consumed-report.json').write_bytes(original.read_bytes())
        (evidence / 'producer-result.json').write_bytes(producer.read_bytes())
        (evidence / 'candidate.patch').write_bytes(b'fake patch\n')
        (evidence / 'target-project').mkdir()
        return dict(status='SUCCEEDED', original_source_unchanged=True, validation={'accepted': True},
                    input=dict(kind=envelope['kind'], commit=envelope['commit'], sha256=request['report_sha256'],
                               job_id=envelope['job_id'], trace_id=envelope['trace_id']))


def fake_build(project, candidate, out, expected, timeout):
    result = dict(status='SUCCEEDED', attempts=[{'image_id': IMAGE}],
                  verification=dict(exit_code=0, output_matches=True, command=['docker', 'run', IMAGE]))
    save(out / 'result.json', result)
    return result


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True, stderr=subprocess.STDOUT).strip()


class PairedLifecycleTests(unittest.TestCase):
    def fixture(self, root, profile):
        repo = root / 'data/project'
        repo.mkdir(parents=True)
        git(repo, 'init', '--quiet', '--template=')
        git(repo, 'config', 'user.name', 'Local E14 Test')
        git(repo, 'config', 'user.email', 'local-test@example.invalid')
        files = ['example.c', 'tinyexpr.c', 'tinyexpr.h', 'Makefile', 'course/verify_example.py'] if profile == 'tinyexpr' else ['main.c', 'helper.c', 'config.h']
        for name in files:
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'baseline\n')
        git(repo, 'add', '.')
        git(repo, 'commit', '--quiet', '-m', 'base')
        base = git(repo, 'rev-parse', 'HEAD')
        (repo / files[0]).write_bytes(b'target\n')
        git(repo, 'add', '.')
        git(repo, 'commit', '--quiet', '-m', 'target')
        target = git(repo, 'rev-parse', 'HEAD')
        (root / 'data/candidate.Dockerfile').write_bytes(b'test-only candidate\n')
        return repo, dict(mode='e12', profile=profile, repo='/course/data/project', base=base, target=target,
                          candidate='/course/data/candidate.Dockerfile', build_timeout=2400, expected_output='1')

    def hosts(self, stack, root):
        ports = {}
        modules = {}
        for role in ('draft', 'buildchecker', 'echecker', 'mdfixer'):
            spec = importlib.util.spec_from_file_location('e14_test_' + role, STACK / 'service.py')
            service = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(service)
            service.ROLE, service.ROOT = role, root
            service.RUNTIME = paired_runtime.RuntimeSessions(root)
            service.auto_build = fake_build

            def local(value, area='work'):
                path = (root / value.removeprefix('/course/')).resolve()
                if not value.startswith('/course/') or not path.is_relative_to(root / area) or path == root / area:
                    raise ValueError('Unexpected test path')
                return path

            service.local = local
            server = service.HTTPServer(('127.0.0.1', 0), service.Handler)
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.03}, daemon=True)
            thread.start()
            stack.callback(server.server_close)
            stack.callback(server.shutdown)
            ports[role], modules[role] = server.server_port, service
        stack.enter_context(patch.object(orchestrate, 'ROOT', root))
        stack.enter_context(patch.object(orchestrate, 'PORTS', ports))
        stack.enter_context(patch.object(paired_runtime, 'RUNTIME_URL', f'http://127.0.0.1:{ports["draft"]}/v1/runtime'))
        stack.enter_context(patch.object(paired_runtime, 'DraftRuntime', FakeDraftRuntime))
        stack.enter_context(patch.object(paired_runtime, 'command', return_value=IMAGE))
        stack.enter_context(patch.object(paired_runtime, 'tinyexpr_detector', return_value=root / 'mock-detector.py'))
        return modules, ports

    def test_profiles_and_image_binding_over_loopback_http(self):
        for profile in ('explicit', 'tinyexpr'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
                root = Path(directory).resolve()
                repo, request = self.fixture(root, profile)
                modules, ports = self.hosts(stack, root)
                with patch.object(orchestrate, 'call', wraps=orchestrate.call) as transport:
                    result = orchestrate.execute(request, root / 'work/success')
                self.assertEqual(result['status'], 'SUCCEEDED', result.get('error'))
                self.assertEqual(result['execution_image_id'], IMAGE)
                self.assertTrue(result['original_source_unchanged'])
                self.assertEqual([stage['name'] for stage in result['stages']], ['draft', 'full-check', 'incremental-check', 'repair', 'recheck'])
                self.assertGreater(transport.call_args_list[0].kwargs['timeout'], request['build_timeout'])
                runtime = json.loads((root / 'work/success/execution-runtime.json').read_bytes())
                self.assertEqual([item['action'] for item in runtime['operations']], ['full', 'full', 'scan', 'scan', 'mdfixer', 'full'])
                self.assertTrue(all(item['image_id'] == IMAGE for item in runtime['operations']))
                self.assertTrue(runtime['operations'][-1]['project'].endswith('/repair-work/component/target-project'))
                self.assertFalse(modules['draft'].RUNTIME.jobs)
                self.assertFalse(git(repo, 'status', '--porcelain'))
                unknown = Request(f'http://127.0.0.1:{ports["echecker"]}/v1/runtime', data=b'{}', method='POST')
                with self.assertRaises(HTTPError) as caught:
                    urlopen(unknown, timeout=3)
                self.assertEqual(caught.exception.code, 404)
                caught.exception.close()

    def test_changed_report_bytes_stop_before_member2_runtime(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory).resolve()
            _, request = self.fixture(root, 'explicit')
            self.hosts(stack, root)
            transport = orchestrate.call

            def change_report(role, payload, evidence, **kwargs):
                response = transport(role, payload, evidence, **kwargs)
                if role == 'echecker':
                    report = root / response['report'].removeprefix('/course/')
                    with report.open('ab') as handle:
                        handle.write(b'\n')
                return response

            with patch.object(orchestrate, 'call', side_effect=change_report):
                result = orchestrate.execute(request, root / 'work/tampered')
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(result['error_code'], 'ARTIFACT_HASH_MISMATCH')
            self.assertFalse((root / 'work/tampered/repair-work/component').exists())
            self.assertTrue(result['original_source_unchanged'])

    def test_runtime_rejects_image_override_and_unknown_identity(self):
        sessions = paired_runtime.RuntimeSessions(STACK)
        with self.assertRaises(Failure) as caught:
            sessions.execute({'job_id': 'missing', 'slot': 'baseline', 'image': IMAGE})
        self.assertEqual(caught.exception.code, 'INVALID_REQUEST')
        with self.assertRaises(Failure) as caught:
            sessions.execute({'job_id': 'missing', 'slot': 'baseline'})
        self.assertEqual(caught.exception.code, 'RUNTIME_ID_MISMATCH')

    def test_legacy_draft_keeps_the_fixed_sample_contract(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory).resolve()
            self.fixture(root, 'explicit')
            modules, _ = self.hosts(stack, root)
            project = root / 'work/fixed/target-project'
            project.mkdir(parents=True)
            response = modules['draft'].run(dict(project='/course/work/fixed/target-project', out='/course/work/fixed/draft-build',
                                              candidate='/course/data/candidate.Dockerfile', expected_output='1', build_timeout=600))
            self.assertEqual(set(response), {'status', 'result', 'artifact'})
            self.assertEqual(response['status'], 'SUCCEEDED')
            self.assertFalse(modules['draft'].RUNTIME.jobs)


if __name__ == '__main__':
    unittest.main()
