"""Exact native ordering transform; PHP tests use only inert namespaced stubs."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/native-installamp-include-order.php'


class NativeIncludeOrderTests(unittest.TestCase):
    def setUp(self):
        path=ROOT/'installer/patch-native-include-order.py'
        self.assertTrue(path.is_file(),'First native manager reload still precedes include preparation')
        spec=importlib.util.spec_from_file_location('native_include_order',str(path));self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def fixture(self):
        before=FIXTURE.read_bytes();a=before.index(self.m.APPLY_START);b=before.index(self.m.INCLUDE_START)
        after=before[:a]+before[b:]+self.m.FAIL_GUARD+before[a:b]
        return before,after

    def fixture_pins(self):
        before,after=self.fixture()
        return mock.patch.multiple(self.m,ORIGINAL_SHA256=hashlib.sha256(before).hexdigest(),PATCHED_SHA256=hashlib.sha256(after).hexdigest())

    def test_include_preparation_precedes_first_native_reload_and_error_is_fatal(self):
        before,after=self.fixture()
        with self.fixture_pins():result=self.m.transform(before)
        self.assertEqual(result,after)
        self.assertLess(result.index(b'creating missing #include'),result.index(b'// edit conf file passwords'))
        self.assertLess(result.index(b'if ($include_err)'),result.index(b'// edit conf file passwords'))

    def test_unknown_and_changed_known_boundaries_are_refused(self):
        before,after=self.fixture()
        with self.fixture_pins():
            for raw in [before+b'operator',after+b'operator',before.replace(b'creating missing #include',b'other')]:
                with self.assertRaises(ValueError):self.m.transform(raw)
            self.assertEqual(self.m.transform(after),after)

    def test_actual_whole_vendor_source_is_pinned_and_idempotent(self):
        path=ROOT.parent/'audit/public-native-init-source/install_amp'
        if not path.is_file():self.skipTest('Private whole-vendor source binding is a separate native gate')
        before=path.read_bytes();self.assertEqual(hashlib.sha256(before).hexdigest(),self.m.ORIGINAL_SHA256)
        after=self.m.transform(before);self.assertEqual(hashlib.sha256(after).hexdigest(),self.m.PATCHED_SHA256)
        self.assertEqual(self.m.transform(after),after)
        self.assertEqual(after.replace(self.m.FAIL_GUARD,b'').count(b'change_ami_password'),before.count(b'change_ami_password'))

    def test_atomic_backup_preserves_source_mode_and_repeat_does_not_rewrite(self):
        before,after=self.fixture();path=self.root/self.m.TARGET;path.parent.mkdir(parents=True);path.write_bytes(before);path.chmod(0o750)
        backup=self.root/'backup'
        with self.fixture_pins():
            self.assertTrue(self.m.apply(self.root,backup));stamp=path.stat().st_mtime_ns
            self.assertFalse(self.m.apply(self.root,backup));self.assertEqual(path.stat().st_mtime_ns,stamp)
        self.assertEqual(path.read_bytes(),after);self.assertEqual(next(backup.iterdir()).read_bytes(),before)
        if os.name=='posix':self.assertEqual(path.stat().st_mode&0o777,0o750)

    def test_failed_atomic_replace_retains_original_and_backup(self):
        before,after=self.fixture();path=self.root/self.m.TARGET;path.parent.mkdir(parents=True);path.write_bytes(before)
        with self.fixture_pins(),mock.patch.object(self.m.os,'replace',side_effect=OSError('fixture replace failure')):
            with self.assertRaises(OSError):self.m.apply(self.root,self.root/'backup')
        self.assertEqual(path.read_bytes(),before);self.assertEqual(next((self.root/'backup').iterdir()).read_bytes(),before)

    def test_plan_then_write_drift_refuses(self):
        before,after=self.fixture();path=self.root/self.m.TARGET;path.parent.mkdir(parents=True);path.write_bytes(before)
        with self.fixture_pins():change=self.m.plan(self.root)
        path.write_bytes(b'operator change')
        with self.assertRaises(ValueError):self.m.write_change(change,self.root/'backup')
        self.assertEqual(path.read_bytes(),b'operator change')

    def test_backup_collision_is_preserved_before_source_change(self):
        before,after=self.fixture();path=self.root/self.m.TARGET;path.parent.mkdir(parents=True);path.write_bytes(before)
        backup=self.root/'backup';backup.mkdir();collision=backup/('install_amp-'+hashlib.sha256(before).hexdigest()+'.original');collision.write_bytes(b'operator')
        with self.fixture_pins(),self.assertRaises(ValueError):self.m.apply(self.root,backup)
        self.assertEqual(path.read_bytes(),before);self.assertEqual(collision.read_bytes(),b'operator')

    @unittest.skipUnless(os.name=='posix','Native symlink boundary')
    def test_redirected_source_is_preserved(self):
        before,after=self.fixture();path=self.root/self.m.TARGET;path.parent.mkdir(parents=True)
        target=self.root/'operator';target.write_bytes(before);path.symlink_to(target)
        with self.fixture_pins(),self.assertRaises(ValueError):self.m.plan(self.root)
        self.assertEqual(target.read_bytes(),before)

    def run_php(self,raw,mode):
        php=shutil.which('php')
        if not php:self.skipTest('Actual native PHP fixture runs in the isolated Linux gate')
        script=self.root/'fixture.php'
        prefix='''<?php
namespace InertNative;
$events=array();$mode='MODE';$amp_conf=array('ASTETCDIR'=>'/owned');$asteriskuser='fixture';$force_amportal_conf=false;
define(__NAMESPACE__.'\\AMP_CONF','/owned/amportal.conf');
function out($value){ } function outn($value){ } function debug($value){ } function putenv($value){ return true; }
function file_exists($value){return substr($value,-13)=='apply_conf.sh';}
function exec($value,&$output=null,&$result=null){
 global $events,$mode;$result=0;
 if(strpos($value,"grep '#include'")===0){$events[]='scan';$output=array('/owned/manager.conf: manager_custom.conf');if($mode=='scan-fail')$result=1;}
 elseif(strpos($value,'sudo -u ')===0){$events[]='touch';if($mode=='touch-fail')$result=1;}
 elseif(strpos($value,'apply_conf.sh')!==false){$events[]='reload';$output=array();}
 else throw new \\Exception('Unreviewed command in inert fixture');
}
register_shutdown_function(function(){global $events;echo implode(',',$events);});
'''.replace('MODE',mode)
        body=raw.split(b'\n',4)[-1].decode('utf-8')
        script.write_text(prefix+body,encoding='utf-8')
        return subprocess.run([php,'-n',str(script)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)

    def test_native_php_healthy_prepares_before_reload(self):
        before,after=self.fixture()
        with self.fixture_pins():after=self.m.transform(before)
        result=self.run_php(after,'healthy');self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,b'scan,touch,reload')

    def test_native_php_include_failure_cannot_reach_reload(self):
        before,after=self.fixture()
        with self.fixture_pins():after=self.m.transform(before)
        for mode in ['scan-fail','touch-fail']:
            result=self.run_php(after,mode);self.assertEqual(result.returncode,1,result.stderr)
            self.assertNotIn(b'reload',result.stdout)


if __name__=='__main__':unittest.main()
