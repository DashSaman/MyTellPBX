"""Privileged rollout operations stay attached to validated directory objects."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('atomic_rollout_policy',ROOT/'scripts/ui/rollout.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

@unittest.skipUnless(os.name=='posix','Production POSIX directory descriptors required')
class AtomicParentTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.base=Path(temp.name)
        self.parent=self.base/'admin/modules/report';self.parent.mkdir(parents=True)
        self.target=self.parent/'functions.inc.php';self.target.write_bytes(b'original')
        self.redirect=self.base/'unrelated';self.redirect.mkdir();(self.redirect/self.target.name).write_bytes(b'original')
    def swap_parent(self):
        self.parent.rename(self.base/'saved-report');self.parent.symlink_to(self.redirect,target_is_directory=True)
    def test_symlink_substitution_before_atomic_write_cannot_escape(self):
        self.swap_parent()
        with self.assertRaises((ValueError,OSError)):policy.atomic_bytes(self.target,b'reviewed',self.target)
        self.assertEqual((self.redirect/self.target.name).read_bytes(),b'original')
    def test_swap_during_commit_cannot_redirect_replace(self):
        original=os.replace;swapped=[False]
        def replace(source,destination,*args,**kwargs):
            if not swapped[0]:
                # Clone the generated temporary too: an attack against path-only
                # rename would otherwise merely fail because the temp moved.
                for item in self.parent.iterdir():shutil.copy2(item,self.redirect/item.name)
                self.swap_parent();swapped[0]=True
            return original(source,destination,*args,**kwargs)
        with patch.object(policy.os,'replace',side_effect=replace):
            try:policy.atomic_bytes(self.target,b'reviewed',self.target)
            except (ValueError,OSError):pass
        self.assertTrue(swapped[0])
        self.assertEqual((self.redirect/self.target.name).read_bytes(),b'original')
    def test_new_file_never_clobbers_a_concurrently_created_owner_file(self):
        target=self.parent/'new-helper.php';target.write_bytes(b'owner file')
        with self.assertRaises((ValueError,OSError)):policy.atomic_bytes(target,b'reviewed',None)
        self.assertEqual(target.read_bytes(),b'owner file')
    def test_safe_unlink_rejects_parent_substitution_and_wrong_content(self):
        self.assertTrue(hasattr(policy,'atomic_remove'),'Rollback still uses path-following unlink')
        with self.assertRaises(ValueError):policy.atomic_remove(self.target,'0'*64)
        self.swap_parent()
        with self.assertRaises((ValueError,OSError)):policy.atomic_remove(self.target,policy.digest(self.redirect/self.target.name))
        self.assertTrue((self.redirect/self.target.name).exists())
    def test_regular_write_and_restore_preserve_mode_mtime_and_user_xattr(self):
        self.target.chmod(0o640);os.utime(self.target,ns=(1234567890000000000,1234567890000000000))
        if hasattr(os,'setxattr'):os.setxattr(self.target,b'user.mytell-fixture',b'owned')
        backup=self.base/'original';shutil.copy2(self.target,backup)
        policy.atomic_bytes(self.target,b'reviewed',self.target)
        self.assertEqual(self.target.stat().st_mode&0o777,0o640)
        self.assertNotEqual(self.target.stat().st_mtime_ns,backup.stat().st_mtime_ns)
        policy.atomic_bytes(self.target,b'original',backup,preserve_mtime=True)
        self.assertEqual(self.target.stat().st_mtime_ns,backup.stat().st_mtime_ns)
        if hasattr(os,'getxattr'):self.assertEqual(os.getxattr(self.target,b'user.mytell-fixture'),b'owned')

if __name__=='__main__':unittest.main()
