import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tinyexpr_repair import Failure, consume, patch_tinyexpr


class TinyExprRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        self.makefile = self.project / 'Makefile'
        self.makefile.write_text('example: example.o tinyexpr.o\n\tgcc -o $@ $^ -lm\n'
                                 '.c.o:\n\tgcc -c $< -o $@\n')
        for name in ('example.c', 'tinyexpr.c', 'tinyexpr.h'):
            (self.project / name).write_text('/* fixture */\n')
        for args in (['init', '-b', 'main'], ['add', '.'],
                     ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                      'commit', '-m', 'fixture']):
            subprocess.run(['git', *args], cwd=self.project, check=True, capture_output=True)
        self.sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.project, text=True).strip()
        self.finding = {'type': 'MISSING', 'target': 'example.o', 'dependency': 'tinyexpr.h'}

    def test_adds_prerequisite_only_rules_and_deduplicates(self):
        report = {'commit': self.sha, 'findings': [self.finding, self.finding,
                  dict(self.finding, target='tinyexpr.o')]}
        before = self.makefile.read_bytes()
        diff, plan = patch_tinyexpr(self.project, report)
        self.assertEqual(len(plan), 2)
        self.assertEqual(self.makefile.read_bytes(), before)
        self.assertIn('+example.o: tinyexpr.h', diff)
        self.assertIn('+tinyexpr.o: tinyexpr.h', diff)
        self.assertFalse(any(line[1:].startswith('\t') for line in diff.splitlines()
                             if line.startswith(('+', '-'))))

    def test_rejects_object_outside_selected_graph(self):
        report = {'commit': self.sha, 'findings': [dict(self.finding, target='repl.o')]}
        with self.assertRaises(Failure) as caught:
            patch_tinyexpr(self.project, report)
        self.assertEqual(caught.exception.code, 'UNSUPPORTED_TARGET')

    def test_rejects_external_symlink(self):
        outside = Path(self.temp.name) / 'outside.h'
        outside.write_text('/* outside */\n')
        (self.project / 'linked.h').symlink_to(outside)
        report = {'commit': self.sha, 'findings': [dict(self.finding, dependency='linked.h')]}
        with self.assertRaisesRegex(ValueError, 'UNSAFE_PATH'):
            patch_tinyexpr(self.project, report)

    def test_rejects_inner_commit_mismatch(self):
        report = {'schema_version': 'e11e12-1', 'kind': 'fixed-md', 'status': 'SUCCEEDED',
                  'commit': self.sha, 'data': {'commit': '0' * 40, 'findings': [self.finding]}}
        path = Path(self.temp.name) / 'report.json'
        path.write_text(json.dumps(report))
        with self.assertRaises(Failure) as caught:
            consume(path, self.sha)
        self.assertEqual(caught.exception.code, 'STALE_REPORT')

    def test_incremental_report_is_bound_to_producer_and_digest(self):
        report = {'schema_version': 'e11e12-1', 'kind': 'incremental-check', 'status': 'SUCCEEDED',
                  'job_id': 'job-fixture', 'trace_id': 'trace-fixture', 'commit': self.sha,
                  'data': {'schema_version': 'e8e10-1', 'commit': self.sha, 'findings': [self.finding]}}
        path = Path(self.temp.name) / 'incremental-check.json'
        path.write_text(json.dumps(report))
        producer = {'schema_version': 'e11e12-1', 'status': 'SUCCEEDED', 'job_id': 'job-fixture',
                    'trace_id': 'trace-fixture', 'target_commit': self.sha, 'stages': [
                        {'name': 'incremental-check', 'artifact': {
                            'uri': 'artifact://job-fixture/incremental-check.json',
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}]}
        manifest = Path(self.temp.name) / 'result.json'
        manifest.write_text(json.dumps(producer))
        self.assertEqual(consume(path, self.sha, manifest, hashlib.sha256(path.read_bytes()).hexdigest()), report)
        with self.assertRaises(Failure) as caught:
            consume(path, self.sha, manifest, '0' * 64)
        self.assertEqual(caught.exception.code, 'ARTIFACT_HASH_MISMATCH')
        manifest.write_text(json.dumps(dict(producer, trace_id='trace-other')))
        with self.assertRaises(Failure) as caught:
            consume(path, self.sha, manifest)
        self.assertEqual(caught.exception.code, 'ARTIFACT_ID_MISMATCH')
        manifest.write_text(json.dumps(producer))
        path.write_text(json.dumps(report) + '\n')
        with self.assertRaises(Failure) as caught:
            consume(path, self.sha, manifest)
        self.assertEqual(caught.exception.code, 'ARTIFACT_HASH_MISMATCH')
