"""Report artifacts are derived from private site sources without changing them."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
policy=load('asternic_prepare_policy',REPO/'scripts/ui/rollout.py')

class AsternicPrepareTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.base=Path(temp.name)
        self.roots={name:self.base/name for name in policy.ROOTS};self.module=self.roots['admin']/'modules/asternic_cdr';self.module.mkdir(parents=True)
        self.source=self.base/'source';fix=self.source/'admin-fixes';fix.mkdir(parents=True)
        (fix/'asternic-direction.php').write_bytes(b'<?php // reviewed classifier')
        (fix/'patch-asternic-direction.py').write_text("def transform_page(text):\n if 'owner page' not in text:raise ValueError('Unknown report anchor')\n return text+'\\n// scoped direction hook'\ndef transform_functions(text):\n if 'owner functions' not in text:raise ValueError('Unknown functions anchor')\n return text+'\\n// scoped direction hook'\n")
        (self.module/'page.asternic_cdr.php').write_text('<?php // owner page')
        (self.module/'functions.inc.php').write_text('<?php // owner functions')
        for name,data in [('module.xml','<module><rawname>asternic_cdr</rawname><version>1.6.6</version></module>'),('asternic_cdr.js','// original UI'),('menu.php','<?php // original menu')]:
            (self.module/name).write_text(data)
        self.output=self.base/'artifact';self.checks=[{'check':name,'rc':0} for name in policy.ASTERNIC_CHECKS]
    def prepare(self):
        module=load('asternic_prepare_under_test',REPO/'scripts/ui/prepare-asternic.py')
        return module.prepare(self.output,self.roots,'a'*40,self.checks,source=self.source)
    def test_derives_only_two_reports_and_helper_preserving_owner_source_and_ui(self):
        before={p.name:p.read_bytes() for p in self.module.iterdir()};manifest=self.prepare()
        self.assertEqual({x['path'] for x in manifest['files']},policy.ASTERNIC_PATHS)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.module.iterdir()})
        self.assertIn('owner page',(self.output/'payload/admin/modules/asternic_cdr/page.asternic_cdr.php').read_text())
        self.assertEqual({x['path'] for x in manifest['inputs']},{'modules/asternic_cdr/'+n for n in ['module.xml','asternic_cdr.js','menu.php']})
    def test_unknown_report_anchor_fails_before_output_creation(self):
        (self.module/'functions.inc.php').write_text('<?php // foreign report')
        with self.assertRaisesRegex(ValueError,'anchor'):self.prepare()
        self.assertFalse(self.output.exists())
    def test_unsupported_module_version_fails_before_output_creation(self):
        (self.module/'module.xml').write_text('<module><rawname>asternic_cdr</rawname><version>9.0.0</version></module>')
        with self.assertRaisesRegex(ValueError,'version'):self.prepare()
        self.assertFalse(self.output.exists())
    def test_missing_native_ui_guard_is_not_silently_ignored(self):
        (self.module/'asternic_cdr.js').unlink()
        with self.assertRaisesRegex(ValueError,'guard'):self.prepare()
        self.assertFalse(self.output.exists())
    def test_foreign_classifier_file_is_never_adopted_or_overwritten(self):
        (self.module/'mytell-direction.php').write_text('<?php // foreign implementation')
        with self.assertRaisesRegex(ValueError,'helper|classifier'):self.prepare()
        self.assertFalse(self.output.exists())
    def test_failed_evidence_or_invalid_source_id_cannot_create_artifact(self):
        self.checks[0]['rc']=1
        with self.assertRaisesRegex(ValueError,'checks'):self.prepare()
        self.assertFalse(self.output.exists())
        self.checks[0]['rc']=0
        module=load('asternic_prepare_invalid_id',REPO/'scripts/ui/prepare-asternic.py')
        with self.assertRaisesRegex(ValueError,'Git tree'):
            module.prepare(self.output,self.roots,'main',self.checks,source=self.source)
        self.assertFalse(self.output.exists())
    def test_served_output_and_existing_artifact_are_rejected(self):
        self.output=self.module/'public-artifact'
        with self.assertRaisesRegex(ValueError,'outside'):self.prepare()
        self.output=self.base/'artifact';self.output.mkdir();(self.output/'owner').write_text('preserve')
        with self.assertRaisesRegex(ValueError,'new|exists'):self.prepare()
        self.assertEqual((self.output/'owner').read_text(),'preserve')
if __name__=='__main__':unittest.main()
