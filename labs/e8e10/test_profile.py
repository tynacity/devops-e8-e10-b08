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

if __name__=='__main__':unittest.main()
