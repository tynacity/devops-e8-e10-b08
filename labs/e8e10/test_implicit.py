import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from implicit import prepare, receive, verify


class ImplicitRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'run'
        prepare(self.out)

    def reply(self, makefile=None):
        # Synthetic candidate only for unit tests, never model provenance.
        original = (self.out / 'project/Makefile').read_text()
        fixed = original.replace('CFLAGS = -O0', 'CFLAGS = -O0\nDEPFLAGS = -MMD -MP\nDEPS = $(OBJS:.o=.d)')
        fixed = fixed.replace('$(CC) $(CFLAGS) -c', '$(CC) $(CFLAGS) $(DEPFLAGS) -c')
        fixed = fixed.replace('rm -f $(OBJS) app', 'rm -f $(OBJS) $(DEPS) app')
        fixed += '\n-include $(DEPS)\n'
        raw = json.dumps({'makefile': fixed if makefile is None else makefile, 'explanation': 'Synthetic unit-test input'})
        provenance = {'provider': 'unit-test', 'model': 'synthetic',
                      'prompt_sha256': hashlib.sha256((self.out / 'prompt.txt').read_bytes()).hexdigest(),
                      'response_sha256': hashlib.sha256(raw.encode()).hexdigest()}
        receive(self.out, raw, provenance)

    def test_reproduces_stale_binary_and_binds_prompt(self):
        baseline = json.loads((self.out / 'baseline.json').read_text())
        self.assertEqual(baseline['before'], '1')
        self.assertEqual(baseline['after_header_change'], '1')
        self.assertTrue(baseline['missing_rebuild'])
        prompt = (self.out / 'prompt.txt').read_text()
        self.assertIn('%.o: %.c', prompt)
        self.assertIn('config.h', prompt)

    def test_candidate_tracks_existing_and_new_transitive_headers(self):
        before = (self.out / 'project/Makefile').read_bytes()
        self.reply()
        result = verify(self.out)
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['outputs'], ['1', '2', '3', '4'])
        self.assertTrue(result['source_unchanged'])
        self.assertEqual(before, (self.out / 'project/Makefile').read_bytes())
        self.assertIn('extra.h', (self.out / 'validation/main.d.saved').read_text())

    def test_refuses_changed_project(self):
        (self.out / 'project/config.h').write_text('#define VALUE 7\n')
        with self.assertRaisesRegex(ValueError, 'STALE_INPUT'):
            self.reply()

    def test_refuses_mismatched_response_provenance(self):
        with self.assertRaisesRegex(ValueError, 'RESPONSE_HASH_MISMATCH'):
            receive(self.out, '{}', {'prompt_sha256': 'x', 'response_sha256': 'x'})

    def test_buildable_unfixed_candidate_is_rejected(self):
        self.reply((self.out / 'project/Makefile').read_text())
        result = verify(self.out)
        self.assertFalse(result['passed'])
        self.assertTrue(result['source_unchanged'])

    def test_undeclared_makefile_input_is_rejected(self):
        (self.out / 'project/GNUmakefile').write_text('all:\n\ttrue\n')
        with self.assertRaisesRegex(ValueError, 'STALE_INPUT'):
            self.reply()

    def test_recipe_cannot_modify_source(self):
        self.reply()
        # A new receipt directory retains the same prepared input and prompt.
        raw = json.loads((self.out / 'raw-response.txt').read_text())
        raw['makefile'] = raw['makefile'].replace('clean:\n', 'clean:\n\techo "/* mutation */" >> helper.c\n')
        # Recreate the response through the public receiver in a fresh prepared run.
        other = Path(self.temp.name) / 'mutation'
        prepare(other)
        response = json.dumps(raw)
        receive(other, response, {'provider': 'unit-test', 'model': 'synthetic',
            'prompt_sha256': hashlib.sha256((other / 'prompt.txt').read_bytes()).hexdigest(),
            'response_sha256': hashlib.sha256(response.encode()).hexdigest()})
        result = verify(other)
        self.assertFalse(result['passed'])
        self.assertIn('SANDBOX_SOURCE_MODIFIED', result['error'])

    def test_unused_depfiles_do_not_qualify(self):
        original = (self.out / 'project/Makefile').read_text()
        fake = original.replace('$(CFLAGS) -c', '$(CFLAGS) -MMD -MP -c')
        fake = fake.replace('rm -f $(OBJS) app', 'rm -f $(OBJS) $(OBJS:.o=.d) app')
        fake += '\nmain.o: $(wildcard *.h)\n'
        self.reply(fake)
        self.assertFalse(verify(self.out)['passed'])

    def test_crlf_response_bytes_preserved(self):
        response = b'{\r\n"makefile": "all:\\n\\ttrue\\n"\r\n}\r\n'
        provenance = {'provider': 'unit-test', 'model': 'synthetic',
            'prompt_sha256': hashlib.sha256((self.out / 'prompt.txt').read_bytes()).hexdigest(),
            'response_sha256': hashlib.sha256(response).hexdigest()}
        receive(self.out, response, provenance)
        self.assertEqual((self.out / 'raw-response.txt').read_bytes(), response)


if __name__ == '__main__':
    unittest.main()
