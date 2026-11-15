"""Exercise online preflight with the observed unavailable mirror, not live DNS."""
import configparser
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASH=str(Path('C:/Program Files/Git/bin/bash.exe')) if os.name=='nt' else shutil.which('bash')

class RepositoryAvailabilityTests(unittest.TestCase):
    def test_online_preflight_uses_working_official_https_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=(ROOT/'install-mytellpbx.sh').read_text(encoding='utf-8')
            definitions=base/'definitions.sh';definitions.write_text(source.rsplit('\nmain "$@"',1)[0]+'\n',encoding='utf-8')
            record=base/'curl-calls.txt';script=base/'run.sh'
            script.write_text('source '+repr(definitions.as_posix())+'\n'
                +'LOG='+repr((base/'log').as_posix())+'\nBUNDLE_FINAL='+repr((base/'absent').as_posix())+'\n'
                +'PY_BIN='+repr(os.sys.executable.replace('\\','/'))+'\nstage_done(){ return 1; }\n'
                +'curl(){ printf "%s\\n" "$*" >> '+repr(record.as_posix())+';\n'
                +'case "$*" in *https://repo.us.issabel.org/issabel/5/base/x86_64/repodata/repomd.xml*) printf \'<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary"><location href="repodata/primary.xml.gz"/></data></repomd>\';;\n'
                +'*mirror.issabel.org*|*http://repo.issabel.org*) return 28;;\n'
                +'*https://github.com*releases*) printf 206;; *) return 0;; esac; }\n'
                +'check_network_prerequisites\n',encoding='utf-8')
            result=subprocess.run([BASH,'--noprofile','--norc',str(script)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8',errors='replace')
            self.assertEqual(result.returncode,0,result.stderr)
            calls=record.read_text(encoding='utf-8')
            self.assertIn('https://repo.us.issabel.org/issabel/5/base/x86_64/repodata/repomd.xml',calls)
            self.assertNotIn('http://mirror.issabel.org',calls)

    def test_every_configured_stream_has_verified_https_base_and_signing_key(self):
        config=configparser.ConfigParser(interpolation=None)
        config.read(str(ROOT/'installer/repos/mytelpbx-base.repo.in'))
        self.assertEqual(len(config.sections()),9)
        for section in config.sections():
            with self.subTest(section=section):
                urls=config[section].get('baseurl','').split()
                self.assertTrue(urls,'No direct repository fallback: '+section)
                self.assertTrue(all(url.startswith(('https://repo.us.issabel.org/issabel/','https://repo.issabel.org/issabel/')) for url in urls))
                self.assertNotIn('mirrorlist',config[section])
                self.assertTrue(config[section]['gpgkey'].startswith('https://repo.us.issabel.org/issabel/'))

if __name__=='__main__':unittest.main()
