import json, tempfile, unittest
from pathlib import Path
from lab import fixture,scan,patch,commit

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'sample';fixture(self.p)

    def test_independent_known_edges(self):
        r=scan(self.p)
        self.assertEqual(r['actual']['main.o'],['config.h','main.c'])
        self.assertEqual({(f['type'],f['dependency']) for f in r['findings']},{('MISSING','config.h'),('REDUNDANT','unused.h')})

    def test_unchanged_reuses_both_targets(self):
        r=scan(self.p,scan(self.p));self.assertEqual(r['reused'],['main.o','helper.o']);self.assertEqual(r['refreshed'],[])

    def test_include_added_invalidates_cache(self):
        old=scan(self.p)
        (self.p/'main.c').write_text('#include "extra.h"\n'+(self.p/'main.c').read_text());commit(self.p,'new include')
        r=scan(self.p,old)
        self.assertIn(['MISSING','main.o','extra.h'],r['added']);self.assertEqual(len(r['refreshed']),2)

    def test_patch_preserves_redundant_dependency(self):
        r=scan(self.p);diff,plan=patch(self.p,r)
        self.assertIn('+main.o: main.c unused.h config.h',diff)
        self.assertNotIn('-\tgcc',diff)
        self.assertNotIn('config.h',(self.p/'Makefile').read_text())

    def test_old_report_rejected(self):
        r=scan(self.p);r['commit']='0'*40
        with self.assertRaisesRegex(ValueError,'STALE_REPORT'):patch(self.p,r)

    def test_unsafe_dependency_rejected(self):
        r=scan(self.p);r['findings']=[{'type':'MISSING','target':'main.o','dependency':'../outside.h'}]
        with self.assertRaisesRegex(ValueError,'UNSAFE_PATH'):patch(self.p,r)

    def test_unsupported_configuration_rejected(self):
        (self.p/'Makefile').write_text((self.p/'Makefile').read_text().replace('-O0','-include unknown.h'))
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_FLAGS'):scan(self.p)

    def test_symlink_dependency_outside_project_rejected_without_source_changes(self):
        outside=Path(self.tmp.name)/'outside.h'
        outside.write_text('#define OUTSIDE 1\n')
        (self.p/'linked.h').symlink_to(outside)
        report={'commit':commit(self.p,'external header link'),'findings':[
            {'type':'MISSING','target':'main.o','dependency':'config.h'},
            {'type':'MISSING','target':'main.o','dependency':'linked.h'}]}
        before=(self.p/'Makefile').read_bytes()
        with self.assertRaisesRegex(ValueError,'^UNSAFE_PATH$'):
            patch(self.p,report)
        self.assertEqual((self.p/'Makefile').read_bytes(),before)
        self.assertEqual(outside.read_bytes(),b'#define OUTSIDE 1\n')

    def test_symlink_directory_outside_project_rejected(self):
        outside=Path(self.tmp.name)/'external'
        outside.mkdir();(outside/'header.h').write_text('/* external */\n')
        (self.p/'headers').symlink_to(outside,target_is_directory=True)
        report={'commit':commit(self.p,'external directory link'),'findings':[
            {'type':'MISSING','target':'main.o','dependency':'headers/header.h'}]}
        before=(self.p/'Makefile').read_bytes()
        with self.assertRaisesRegex(ValueError,'^UNSAFE_PATH$'):
            patch(self.p,report)
        self.assertEqual((self.p/'Makefile').read_bytes(),before)

    def test_symlink_dependency_within_project_keeps_declared_path(self):
        (self.p/'linked.h').symlink_to('config.h')
        report={'commit':commit(self.p,'local header link'),'findings':[
            {'type':'MISSING','target':'main.o','dependency':'linked.h'}]}
        before=(self.p/'Makefile').read_bytes()
        diff,plan=patch(self.p,report)
        self.assertIn('+main.o: main.c unused.h linked.h',diff)
        self.assertEqual(plan,[{'target':'main.o','dependency':'linked.h','style':'direct'}])
        self.assertEqual((self.p/'Makefile').read_bytes(),before)


class Student241880528E8Tests(unittest.TestCase):
    def test_redundant_only_produces_no_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'sample'
            fixture(project)

            makefile = project / 'Makefile'
            original = makefile.read_text()
            self.assertIn('main.o: main.c unused.h\n', original)
            makefile.write_text(original.replace(
                'main.o: main.c unused.h\n',
                'main.o: main.c unused.h config.h\n',
            ))
            commit(project, 'declare config.h for RD-only test')

            report = scan(project)
            self.assertEqual(report['findings'], [
                {'type': 'REDUNDANT', 'target': 'main.o',
                 'dependency': 'unused.h'},
            ])

            before = makefile.read_bytes()
            diff, edits = patch(project, report)

            self.assertEqual(diff, '')
            self.assertEqual(edits, [])
            self.assertEqual(makefile.read_bytes(), before)


class Student241880529E9Tests(unittest.TestCase):
    def test_duplicate_missing_findings_produce_one_edit_per_style(self):
        from lab import run
        for style in ('direct', 'macro', 'mixed'):
            with self.subTest(style=style), tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / 'project'
                fixture(project, style)
                report = scan(project)
                missing = next(f for f in report['findings'] if f['type'] == 'MISSING')
                report['findings'].extend([dict(missing), dict(missing)])
                before = (project / 'Makefile').read_bytes()
                diff, plan = patch(project, report)
                self.assertEqual(plan, [{'target': 'main.o', 'dependency': 'config.h', 'style': style}])
                self.assertEqual((project / 'Makefile').read_bytes(), before)
                candidate = Path(directory) / 'candidate.patch'
                candidate.write_text(diff)
                run(['git', 'apply', '--check', str(candidate)], project)
                run(['git', 'apply', str(candidate)], project)
                after = (project / 'Makefile').read_bytes()
                self.assertEqual(after.count(b'config.h'), 1)
                self.assertEqual(
                    [line for line in before.splitlines() if line.startswith(b'\t')],
                    [line for line in after.splitlines() if line.startswith(b'\t')])
                expected = {
                    'direct': 'main.o: main.c unused.h config.h',
                    'macro': 'DEPS = main.c unused.h config.h',
                    'mixed': 'main.o: main.c $(HEADERS) config.h',
                }[style]
                self.assertIn(expected, after.decode())
                if style == 'macro':
                    self.assertIn('main.o: $(DEPS)', after.decode())
                self.assertFalse(any(f['type'] == 'MISSING' for f in scan(project)['findings']))

from test_implicit import ImplicitRepairTests

if __name__=='__main__':unittest.main()
