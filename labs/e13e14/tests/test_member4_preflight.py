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
