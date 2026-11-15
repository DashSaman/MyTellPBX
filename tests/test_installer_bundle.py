"""Execute the real bundle builder against a committed disposable source tree."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
BASH=shutil.which('bash')


@unittest.skipUnless(os.name!='nt' and BASH and Path(BASH).is_file(),'Target Linux GNU tools are required for real bundle assembly')
class InstallerBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.root=self.base/'source';self.root.mkdir()
        # The source may itself be a source-complete release archive, not a Git
        # checkout. Only the disposable fixture needs Git metadata.
        shutil.copytree(REPO/'theme',self.root/'theme',ignore=shutil.ignore_patterns('cache','*.tplc','__pycache__','.env*'))
        paths=re.findall(r'^copy_path "([^"]+)"', (REPO/'scripts/build-installer-bundle.sh').read_text(),re.M)
        for name in set(paths+['VERSION','LICENSE','.gitattributes']):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((REPO/name).read_bytes())
        for name in ['installer/install-myteldesk.py','installer/myteldesk-release.json','installer/password-init.php','modules/mytellpbxopdesk/launcher-access.php','admin-fixes/patch-asternic-direction.py','admin-fixes/asternic-direction.php']:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture corresponding source: '+name.encode())
        (self.root/'.gitignore').write_text('.env\n*.tgz\n')
        self.env=dict(os.environ)
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1')
        subprocess.check_call(['git','init','--quiet'],cwd=self.root,env=self.env)
        subprocess.check_call(['git','add','.'],cwd=self.root,env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.check_call(['git','-c','user.name=Fixture','-c','user.email=fixture@example.test','-c','commit.gpgsign=false','commit','--quiet','-m','fixture source'],cwd=self.root,env=self.env)

    def build(self):
        result=subprocess.run([BASH,str(REPO/'scripts/build-installer-bundle.sh'),str(self.root)],cwd=self.root,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=90)
        version=(self.root/'VERSION').read_text().strip();archive=self.root/'dist'/('mytelpbx-bundle-'+version+'.tgz')
        return result,archive,'mytelpbx-bundle-'+version+'/'

    def test_bundle_includes_desk_stage_launcher_dependency_and_license(self):
        result,archive,prefix=self.build();self.assertEqual(result.returncode,0,result.stdout)
        with tarfile.open(archive) as tar:
            names=set(tar.getnames())
            for name in ['installer/install-myteldesk.py','installer/myteldesk-release.json','installer/password-init.php','installer/repair-repository-transport.py','installer/dnf-progress.py','installer/prepare-tls.py','installer/geoip-update.py','modules/mytellpbxgeoip/index.php','modules/mytellpbxopdesk/index.php','modules/mytellpbxopdesk/launcher-access.php','admin-theme/patch-login-branding.py','admin-fixes/patch-asternic-direction.py','admin-fixes/asternic-direction.php','admin-fixes/licenses/GPL-3.0.txt','LICENSE']:
                with self.subTest(name=name):
                    self.assertIn(prefix+name,names)
                    if prefix+name in names:self.assertEqual(tar.extractfile(prefix+name).read(),(self.root/name).read_bytes())

    def test_ignored_local_secret_is_not_part_of_theme_payload(self):
        (self.root/'theme/.env').write_text('PRIVATE_BUNDLE_FIXTURE_SENTINEL')
        result,archive,prefix=self.build();self.assertEqual(result.returncode,0,result.stdout)
        with tarfile.open(archive) as tar:self.assertNotIn(prefix+'theme/.env',tar.getnames())

    def test_dirty_tracked_source_is_rejected_before_bundle_output(self):
        with (self.root/'theme/css/workspace.css').open('ab') as out:out.write(b'\n/* unreviewed change */\n')
        result,archive,_=self.build()
        self.assertNotEqual(result.returncode,0,'unreviewed source was packaged')
        self.assertIn('clean',result.stdout.lower())
        self.assertFalse(archive.exists())

    def test_clean_line_ending_conversion_cannot_change_published_source_bytes(self):
        relative='theme/css/workspace.css';path=self.root/relative
        with (self.root/'.gitattributes').open('a') as attributes:
            attributes.write('\n'+relative+' text eol=crlf\n')
        subprocess.check_call(['git','add','.gitattributes'],cwd=self.root,env=self.env)
        subprocess.check_call(['git','-c','user.name=Fixture','-c','user.email=fixture@example.test','-c','commit.gpgsign=false','commit','--quiet','-m','fixture CRLF checkout'],cwd=self.root,env=self.env)
        path.unlink()  # Require a fresh checkout instead of a cached stat match.
        subprocess.check_call(['git','checkout-index','--force','--index','--',relative],cwd=self.root,env=self.env)
        committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=self.root,env=self.env)
        self.assertNotIn(b'\r\n',committed,'the committed fixture must have LF source bytes')
        self.assertIn(b'\r\n',path.read_bytes(),'Git must perform the CRLF checkout conversion')
        self.assertEqual(path.read_bytes(),committed.replace(b'\n',b'\r\n'))
        self.assertEqual(subprocess.check_output(['git','status','--porcelain'],cwd=self.root,env=self.env),b'')
        result,archive,prefix=self.build();self.assertEqual(result.returncode,0,result.stdout)
        with tarfile.open(archive) as tar:self.assertEqual(tar.extractfile(prefix+relative).read(),committed)


if __name__=='__main__':unittest.main()
