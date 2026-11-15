"""Artifact preparation never rewrites live snapshots or unrelated products."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
policy=load('polish_prepare_policy',REPO/'scripts/ui/rollout.py')


class PolishPrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        self.roots={name:self.base/name for name in policy.ROOTS}
        for path in self.roots.values():path.mkdir()
        self.source=self.base/'source';self.source.mkdir();self.output=self.base/'artifact'
        self.checks=[{'check':name,'rc':0} for name in policy.POLISH_CHECKS]
        for name in policy.POLISH_PANEL:
            self.write(self.source/'theme'/name,b'new '+name.encode());self.write(self.roots['panel']/name,b'old '+name.encode())
        for name in ['workspace.css','workspace.js']:
            self.write(self.source/'admin-theme'/name,b'new '+name.encode());self.write(self.roots['admin']/'assets/mytel'/name,b'old '+name.encode())
        self.header="<?php\n$html='';\n$html .= '<head>';\n// owner code\n$html .= '</head>';\n"
        self.write(self.roots['admin']/'views/header.php',self.header.encode())
        self.write(self.source/'admin-theme/patch-admin-theme.py',(REPO/'admin-theme/patch-admin-theme.py').read_bytes())
        for name in ['index.php','launcher-access.php']:
            self.write(self.source/'modules/mytellpbxopdesk'/name,b'<?php // new '+name.encode())
        self.write(self.roots['legacy']/'modules/mytellpbxopdesk/index.php',b'<?php // old launcher')
        for name in ['assets/js/pbxlib.js','libraries/ampuser.class.php']:
            self.write(self.roots['admin']/name,b'guarded native dependency')

    @staticmethod
    def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)

    def prepare(self,**kwargs):
        module=load('polish_prepare_under_test',REPO/'scripts/ui/prepare-polish.py')
        return module.prepare(self.output,self.roots,'a'*40,self.checks,source=self.source,**kwargs)

    def test_preparation_builds_only_reviewable_ui_and_entry_payloads(self):
        before={str(p):p.read_bytes() for root in self.roots.values() for p in root.rglob('*') if p.is_file()}
        manifest=self.prepare()
        self.assertEqual(manifest['profile'],policy.POLISH_PROFILE)
        self.assertTrue(all(policy.allowed(row,policy.POLISH_PROFILE) for row in manifest['files']))
        self.assertEqual(before,{str(p):p.read_bytes() for root in self.roots.values() for p in root.rglob('*') if p.is_file()})
        self.assertIn('// owner code',(self.output/'payload/admin/views/header.php').read_text())
        helper=next(row for row in manifest['files'] if row['path'].endswith('launcher-access.php'))
        self.assertIsNone(helper['before']);self.assertEqual(helper['order'],10)

    def test_missing_native_dependency_fails_before_creating_artifact(self):
        (self.roots['admin']/'libraries/ampuser.class.php').unlink()
        with self.assertRaisesRegex(ValueError,'guard|dependency'):self.prepare()
        self.assertFalse(self.output.exists())

    def test_header_drift_fails_before_creating_artifact(self):
        (self.roots['admin']/'views/header.php').write_text('unknown owner header')
        with self.assertRaisesRegex(ValueError,'anchor'):self.prepare()
        self.assertFalse(self.output.exists())

    def test_existing_artifact_is_never_overwritten(self):
        self.output.mkdir();marker=self.output/'owner.txt';marker.write_text('keep')
        with self.assertRaisesRegex(ValueError,'new|exist'):self.prepare()
        self.assertEqual(marker.read_text(),'keep')

    def test_output_inside_served_tree_is_rejected(self):
        self.output=self.roots['legacy']/'exposed-artifact'
        with self.assertRaisesRegex(ValueError,'outside'):self.prepare()
        self.assertFalse(self.output.exists())

    def test_failed_check_is_rejected_before_candidate_creation(self):
        self.checks[0]['rc']=1
        with self.assertRaisesRegex(ValueError,'check'):self.prepare()
        self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
