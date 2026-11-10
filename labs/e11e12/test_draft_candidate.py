"""Member 4 checks for the TinyExpr handoff's DRAFT instruction contract."""
import unittest

from draft.autobuild import prepare_candidate


class TinyExprCandidateContract(unittest.TestCase):
    def setUp(self):
        self.broken = ('FROM python:3.13-slim\nWORKDIR /work\n'
                       'COPY Makefile example.c tinyexpr.c tinyexpr.h ./\n'
                       'RUN make example\nCMD ["./example"]\n')
        # A syntax-only digest fixture; no network or Docker execution is implied.
        self.pinned = 'FROM python:3.13-slim@sha256:' + 'a' * 64
        self.candidate = self.broken.replace('FROM python:3.13-slim', self.pinned).replace(
            'RUN make example', 'RUN apt-get update && apt-get install -y build-essential\nRUN make example')

    def test_repair_preserves_original_project_build_and_runtime(self):
        baseline = prepare_candidate(self.broken, self.candidate)
        self.assertEqual(baseline, self.broken.replace('FROM python:3.13-slim', self.pinned))

    def test_changing_program_to_echo_expected_output_is_rejected(self):
        invalid = self.candidate.replace('CMD ["./example"]', 'CMD ["echo", "15.198684"]')
        with self.assertRaisesRegex(ValueError, 'required project/build/runtime instructions'):
            prepare_candidate(self.broken, invalid)

    def test_dropping_header_from_build_context_is_rejected(self):
        invalid = self.candidate.replace('tinyexpr.c tinyexpr.h ./', 'tinyexpr.c ./')
        with self.assertRaisesRegex(ValueError, 'required project/build/runtime instructions'):
            prepare_candidate(self.broken, invalid)


if __name__ == '__main__':
    unittest.main()
