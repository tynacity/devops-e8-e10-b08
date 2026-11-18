import sys
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1])]
from run_member2_c5 import injected_makefile


class C5InjectionTests(unittest.TestCase):
    def setUp(self):
        self.corrected = ('CFLAGS = -O0\nmain.o: main.c unused.h config.h extra.h\n'
                          '\tgcc $(CFLAGS) -c main.c -o main.o\n'
                          'helper.o: helper.c extra.h\n\tgcc $(CFLAGS) -c helper.c -o helper.o\n')

    def test_headerflow_missing_config_keeps_other_repairs(self):
        result = injected_makefile(self.corrected, 'missing-config')
        self.assertIn('main.o: main.c unused.h extra.h\n', result)
        self.assertIn('helper.o: helper.c extra.h\n', result)
        self.assertIn('\tgcc $(CFLAGS) -c main.c -o main.o\n', result)

    def test_compile_error_keeps_all_dependency_repairs(self):
        result = injected_makefile(self.corrected, 'compile-error')
        self.assertIn('main.o: main.c unused.h config.h extra.h\n', result)
        self.assertIn('helper.o: helper.c extra.h\n', result)
        self.assertIn('gcc --member2-c5-invalid-option $(CFLAGS)', result)

    def test_h2_dependency_order_is_supported(self):
        source = self.corrected.replace('main.c unused.h config.h', 'main.c config.h unused.h')
        self.assertNotIn('config.h', injected_makefile(source, 'missing-config'))

    def test_missing_probe_dependency_is_rejected(self):
        with self.assertRaises(ValueError):
            injected_makefile(self.corrected.replace(' config.h', ''), 'missing-config')

    def test_missing_compile_recipe_is_rejected(self):
        with self.assertRaises(ValueError):
            injected_makefile(self.corrected.replace('gcc $(CFLAGS) -c main.c', 'cc main.c'), 'compile-error')

    def test_unknown_injection_is_rejected(self):
        with self.assertRaises(ValueError):
            injected_makefile(self.corrected, 'unknown')
