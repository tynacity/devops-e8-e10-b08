import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'labs/e13e14'), str(ROOT / 'labs/e11e12')]
from mdfixer import repair
from lab import commit, fixture, scan


class Member2MDFixerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        fixture(self.repo)
        (self.repo / 'main.c').write_text('#include <stdio.h>\n#include "config.h"\n#include "extra.h"\nint main(void){printf("%d\\n", VALUE + EXTRA);return 0;}\n')
        self.target = commit(self.repo, 'input')
        self.data = scan(self.repo)

    def request(self, data=None, manifest=False):
        envelope = {'schema_version': 'e11e12-1', 'kind': 'incremental-check' if manifest else 'fixed-md',
                    'commit': self.target, 'status': 'SUCCEEDED', 'data': data or self.data,
                    'job_id': 'a-job', 'trace_id': 'a-trace'}
        path = self.root / 'report.json'
        path.write_text(json.dumps(envelope))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        request = {'profile': 'explicit', 'repo': str(self.repo), 'target': self.target,
                   'report': str(path), 'report_sha256': sha}
        if manifest:
            producer = {'schema_version': 'e11e12-1', 'status': 'SUCCEEDED', 'target_commit': self.target,
                        'job_id': 'a-job', 'trace_id': 'a-trace', 'stages': [
                            {'name': 'incremental-check', 'artifact': {
                                'uri': 'artifact://a-job/incremental-check.json', 'sha256': sha}}]}
            source = self.root / 'producer.json'
            source.write_text(json.dumps(producer))
            request['producer_manifest'] = str(source)
        return request

    def run_case(self, request):
        before = {p.name: p.read_bytes() for p in self.repo.iterdir() if p.is_file()}
        result = repair(request, self.root / 'run')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.repo.iterdir() if p.is_file()})
        self.assertTrue(result['original_source_unchanged'])
        return result

    def test_actual_report_generates_verified_patch(self):
        result = self.run_case(self.request(manifest=True))
        self.assertEqual(result['status'], 'SUCCEEDED')
        self.assertTrue(result['validation']['accepted'])
        self.assertEqual(result['input']['job_id'], 'a-job')
        self.assertTrue((self.root / 'run/recheck.json').is_file())

    def test_report_hash_is_required(self):
        request = self.request()
        del request['report_sha256']
        self.assertEqual(self.run_case(request)['error']['code'], 'INVALID_REQUEST')

    def test_changed_report_is_rejected(self):
        request = self.request()
        with Path(request['report']).open('a') as f:
            f.write('\n')
        self.assertEqual(self.run_case(request)['error']['code'], 'ARTIFACT_HASH_MISMATCH')

    def test_stale_inner_commit_is_rejected(self):
        data = dict(self.data, commit='0' * 40)
        self.assertEqual(self.run_case(self.request(data))['error']['code'], 'STALE_REPORT')

    def test_wrong_kind_is_rejected(self):
        request = self.request()
        path = Path(request['report'])
        envelope = json.loads(path.read_bytes())
        envelope['kind'] = 'full-check'
        path.write_text(json.dumps(envelope))
        request['report_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(self.run_case(request)['error']['code'], 'ARTIFACT_TYPE_MISMATCH')

    def test_invalid_profile_is_rejected(self):
        request = dict(self.request(), profile='unknown')
        self.assertEqual(self.run_case(request)['error']['code'], 'INVALID_REQUEST')

    def test_failed_upstream_is_rejected(self):
        request = self.request(manifest=True)
        path = Path(request['producer_manifest'])
        producer = json.loads(path.read_bytes())
        producer['status'] = 'FAILED'
        path.write_text(json.dumps(producer))
        self.assertEqual(self.run_case(request)['error']['code'], 'UPSTREAM_FAILED')

    def test_incomplete_repair_rolls_back_target(self):
        data = dict(self.data, findings=[f for f in self.data['findings'] if f['dependency'] != 'config.h'])
        result = self.run_case(self.request(data))
        self.assertEqual(result['error']['code'], 'REPAIR_REJECTED')
        self.assertTrue(result['validation']['rollback'])
        self.assertEqual((self.root / 'run/target-project/Makefile').read_bytes(),
                         (self.repo / 'Makefile').read_bytes())

    def test_existing_output_is_preserved(self):
        out = self.root / 'run'
        out.mkdir()
        (out / 'retained').write_text('original')
        with self.assertRaises(FileExistsError):
            repair(self.request(), out)
        self.assertEqual((out / 'retained').read_text(), 'original')


if __name__ == '__main__':
    unittest.main()
