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
    def run_metadata(self,curl_body):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=(ROOT/'install-mytellpbx.sh').read_text(encoding='utf-8')
            definitions=base/'definitions.sh';definitions.write_text(source.rsplit('\nmain "$@"',1)[0]+'\n',encoding='utf-8')
            script=base/'metadata.sh';record=base/'calls.txt'
            script.write_text('source '+repr(definitions.as_posix())+'\nLOG='+repr((base/'log').as_posix())
                +'\nPY_BIN='+repr(os.sys.executable.replace('\\','/'))+'\n'
                +'curl(){ printf "%s\\n" "$*" >> '+repr(record.as_posix())+'; '+curl_body+'; }\n'
                +'repository_metadata_reachable\n',encoding='utf-8')
            result=subprocess.run([BASH,'--noprofile','--norc',str(script)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8',errors='replace')
            calls=record.read_text(encoding='utf-8').splitlines() if record.exists() else []
            return result,calls

    def test_primary_fallback_is_used_only_after_first_official_metadata_fails(self):
        xml='<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary"><location href="repodata/primary.xml.gz"/></data></repomd>'
        result,calls=self.run_metadata('case "$*" in *repo.us.issabel.org*) return 28;; *) printf '+repr(xml)+';; esac')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(calls),2)
        self.assertIn('https://repo.issabel.org/issabel/',calls[-1])

    def test_empty_html_or_non_repository_success_bodies_are_rejected(self):
        for body in ['', '<html>service unavailable</html>', '<repomd/>', '<repomd xmlns="http://linux.duke.edu/metadata/repo"/>']:
            with self.subTest(body=body):
                result,calls=self.run_metadata('printf %s '+repr(body))
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(len(calls),2)

    def test_failed_transfer_cannot_pass_even_if_a_valid_prefix_was_received(self):
        xml='<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary"><location href="repodata/primary.xml.gz"/></data></repomd>'
        result,calls=self.run_metadata('printf %s '+repr(xml)+'; return 56')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(len(calls),2)

    def test_primary_location_requires_href_and_metadata_never_needs_dtd_entities(self):
        for content in ['<location/>','<location href=""/>','<location href=" "/>']:
            result,_calls=self.run_metadata('printf %s '+repr('<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary">'+content+'</data></repomd>'))
            self.assertNotEqual(result.returncode,0,'Missing primary metadata path was accepted')
        document='<!DOCTYPE repomd [<!ENTITY path "repodata/primary.xml.gz">]><repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary"><location href="&path;"/></data></repomd>'
        result,_calls=self.run_metadata('printf %s '+repr(document))
        self.assertNotEqual(result.returncode,0,'Unnecessary DTD/entity declaration was accepted')

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
                self.assertNotEqual(config[section].get('sslverify','1'),'0')

if __name__=='__main__':unittest.main()
