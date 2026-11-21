"""Member 4 preparation checks, not the E13 paired-project acceptance matrix.

C2/C3 replay the archived E12 A-report at the existing public consume boundary.
C6 exercises the runtime scanner through its command-line interface.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'labs/e11e12'))
from tinyexpr_repair import Failure, consume
from pipeline import execute

ARCHIVE = ROOT / 'docs/students/241880546/e11-e12/evidence/tinyexpr-ab-8d2fa1f23ff7/a'
SCANNER = ROOT / 'labs/e13e14/scan_runtime_logs.py'


class ArchivedReportPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name) / 'incremental-check.json'
        self.manifest = Path(self.temp.name) / 'result.json'
        self.original = (ARCHIVE / 'incremental-check.json').read_bytes()
        self.report.write_bytes(self.original)
        self.manifest.write_bytes((ARCHIVE / 'result.json').read_bytes())
        producer = json.loads(self.manifest.read_bytes())
        self.target = producer['target_commit']
        self.base = producer['base_commit']
        self.digest = hashlib.sha256(self.original).hexdigest()

    def test_archived_valid_report_is_accepted(self):
        report = consume(self.report, self.target, self.manifest, self.digest)
        self.assertEqual(report['commit'], self.target)
        self.assertEqual(report['data']['commit'], self.target)

    def test_c2_report_for_another_target_is_rejected(self):
        self.assertNotEqual(self.base, self.target)
        with self.assertRaises(Failure) as caught:
            consume(self.report, self.base, self.manifest, self.digest)
        self.assertEqual(caught.exception.code, 'STALE_REPORT')
        self.assertEqual(self.report.read_bytes(), self.original)

    def test_c3_changed_bytes_with_original_digest_are_rejected(self):
        self.report.write_bytes(self.original + b'\n')
        self.assertNotEqual(hashlib.sha256(self.report.read_bytes()).hexdigest(), self.digest)
        with self.assertRaises(Failure) as caught:
            consume(self.report, self.target, self.manifest, self.digest)
        self.assertEqual(caught.exception.code, 'ARTIFACT_HASH_MISMATCH')
        self.assertEqual((ARCHIVE / 'incremental-check.json').read_bytes(), self.original)


class PublicReportBoundaryPreflight(unittest.TestCase):
    """Exercise the new public mode's rejection contract before any build."""

    def setUp(self):
        for name in ('data', 'work'):
            (ROOT / name).mkdir(exist_ok=True)
        inputs = tempfile.TemporaryDirectory(prefix='member4-boundary-', dir=ROOT / 'data')
        outputs = tempfile.TemporaryDirectory(prefix='member4-boundary-', dir=ROOT / 'work')
        self.addCleanup(inputs.cleanup)
        self.addCleanup(outputs.cleanup)
        self.inputs = Path(inputs.name)
        self.out = Path(outputs.name) / 'task'
        self.report = self.inputs / 'incremental-check.json'
        self.manifest = self.inputs / 'producer-result.json'
        self.report.write_bytes((ARCHIVE / 'incremental-check.json').read_bytes())
        self.manifest.write_bytes((ARCHIVE / 'result.json').read_bytes())
        producer = json.loads(self.manifest.read_bytes())
        project = self.inputs / 'repo'
        project.mkdir()
        candidate = self.inputs / 'candidate.Dockerfile'
        candidate.write_text('FROM scratch\n', encoding='utf-8')
        self.request = dict(mode='e13-b', profile='tinyexpr', repo=str(project),
                            candidate=str(candidate), expected_output='1',
                            base=producer['base_commit'], target=producer['target_commit'],
                            report=str(self.report), producer_manifest=str(self.manifest),
                            report_sha256=hashlib.sha256(self.report.read_bytes()).hexdigest())

    def rejected(self, code):
        result = execute(self.request, self.out)
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['error']['code'], code)
        self.assertEqual(result['stages'], [])
        self.assertFalse((self.out / 'draft-build').exists())

    def test_public_wrong_target_rejected_before_build(self):
        self.request['target'] = self.request['base']
        self.rejected('STALE_REPORT')

    def test_public_changed_report_rejected_before_build(self):
        self.report.write_bytes(self.report.read_bytes() + b'\n')
        self.rejected('ARTIFACT_HASH_MISMATCH')

    def test_public_wrong_baseline_rejected_before_build(self):
        self.request['base'] = '0' * 40
        self.rejected('STALE_REPORT')

    def test_public_producer_size_mismatch_rejected_before_build(self):
        producer = json.loads(self.manifest.read_bytes())
        entry, = [s['artifact'] for s in producer['stages'] if s['name'] == 'incremental-check']
        entry['bytes'] = self.report.stat().st_size + 1
        self.manifest.write_text(json.dumps(producer), encoding='utf-8')
        self.rejected('ARTIFACT_HASH_MISMATCH')


class RuntimeScannerPreflight(unittest.TestCase):
    def scan(self, path):
        return subprocess.run([sys.executable, str(SCANNER), str(path)],
                              text=True, capture_output=True, check=False)

    def test_c6_work_log_hit_is_redacted_and_cleaning_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / 'work'
            work.mkdir()
            log = work / 'probe.log'
            fake = 'sk-' + 'member4probe0123456789abcdef'
            log.write_text('api_key = "' + fake + '"\n', encoding='utf-8')
            hit = self.scan(work)
            self.assertEqual(hit.returncode, 1, hit.stderr)
            self.assertIn('FOUND', hit.stdout)
            self.assertNotIn(fake, hit.stdout + hit.stderr)
            log.write_text('probe completed; clean content\n', encoding='utf-8')
            clean = self.scan(work)
            self.assertEqual(clean.returncode, 0, clean.stderr)
            self.assertNotIn('FOUND', clean.stdout)

    def test_missing_path_does_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.scan(Path(temp) / 'missing')
            self.assertEqual(result.returncode, 2)
            self.assertIn('SCAN_ERROR', result.stderr)

    def test_empty_directory_does_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.scan(Path(temp))
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
