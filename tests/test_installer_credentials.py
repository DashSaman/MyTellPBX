"""Execute real credential call sites with recording clients, never a database."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = str(Path('C:/Program Files/Git/bin/bash.exe')) if os.name == 'nt' else shutil.which('bash')


class CredentialTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.base = Path(self.temp.name)
        self.source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        definitions = self.source.rsplit('\nmain "$@"', 1)[0] + '\n'
        self.definitions = self.base / 'definitions.sh'; self.definitions.write_text(definitions, encoding='utf-8')
        self.records = self.base / 'calls.jsonl'; self.recorder = self.base / 'record.py'
        self.recorder.write_text("import json,os,sys\na=sys.argv[1:];probe=a==['-N','-e','SELECT 1'];body='' if probe else sys.stdin.read()\nwith open(os.environ['FIXTURE_CALLS'],'a',encoding='utf-8') as f:f.write(json.dumps({'argv':a,'mysql_env':os.environ.get('MYSQL_PWD'),'stdin':body})+'\\n')\nsys.exit(1 if probe else 0)\n", encoding='utf-8')
        (self.base / 'installer').mkdir(); (self.base / 'installer/password-init.php').write_text('<?php // recording client fixture')

    def run_shell(self, body):
        script = self.base / 'run.sh'
        setup = 'source ' + repr(self.definitions.as_posix()) + '\nLOG=' + repr((self.base / 'log').as_posix()) + '\nPY_BIN=' + repr(sys.executable.replace('\\','/')) + '\nBUNDLE_DIR=' + repr(self.base.as_posix()) + '\n'
        setup += "MYSQL_ROOT_PASS='FixtureDb_123!'\nADMIN_PASS='Fixture Admin.456='\nexport FIXTURE_CALLS=" + repr(self.records.as_posix()) + '\n'
        setup += 'mysql(){ "$PY_BIN" ' + repr(self.recorder.as_posix()) + ' "$@"; }\nrun_logged(){ "$PY_BIN" ' + repr(self.recorder.as_posix()) + ' "$@"; }\n'
        script.write_text(setup + body, encoding='utf-8')
        result = subprocess.run([BASH,'--noprofile','--norc',str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace')
        records = [json.loads(line) for line in self.records.read_text(encoding='utf-8').splitlines()] if self.records.exists() else []
        return result, records

    def test_mysql_auth_uses_environment_and_preserves_callers_stdin_and_options(self):
        result, calls = self.run_shell("printf 'SELECT 42;\\n' | mysql_any -N\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        writer = calls[-1]
        self.assertNotIn('FixtureDb_123!', ' '.join(writer['argv']))
        self.assertEqual(writer['mysql_env'], 'FixtureDb_123!')
        self.assertEqual(writer['argv'], ['-N']); self.assertEqual(writer['stdin'], 'SELECT 42;\n')

    def test_temporary_mysql_password_sql_and_auth_are_not_process_arguments(self):
        legacy = re.search(r'    local tmp_pwd\n.*?(?=\n    # Framework marker:)', self.source, re.S)
        body = "openssl(){ printf 'FixtureTemporary123'; }\n"
        body += 'if declare -F normalize_framework_mysql >/dev/null; then normalize_framework_mysql; else legacy_normalize(){\n' + (legacy.group(0) if legacy else ':') + '\n}; legacy_normalize; fi\n'
        result, calls = self.run_shell(body)
        self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(len(calls), 2)
        self.assertTrue(all('FixtureTemporary123' not in ' '.join(c['argv']) for c in calls))
        self.assertIn("PASSWORD('FixtureTemporary123')", calls[0]['stdin'])
        self.assertEqual(calls[1]['mysql_env'], 'FixtureTemporary123')
        self.assertIn("PASSWORD('')", calls[1]['stdin'])

    def test_amp_admin_password_is_sql_stdin_not_mysql_argv(self):
        legacy = re.search(r'    local my_args=\(\)\n.*?(?=\n    ADMIN_PASS=)', self.source, re.S)
        body = 'if declare -F ensure_amp_admin_password >/dev/null; then ensure_amp_admin_password; else legacy_amp(){\n' + (legacy.group(0) if legacy else ':') + '\n}; legacy_amp; fi\n'
        result, calls = self.run_shell(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        writer = calls[-1]
        self.assertNotIn('Fixture Admin.456=', ' '.join(writer['argv']))
        self.assertNotIn('FixtureDb_123!', ' '.join(writer['argv']))
        self.assertIn("SHA1('Fixture Admin.456=')", writer['stdin'])
        self.assertEqual(writer['mysql_env'], 'FixtureDb_123!')

    def test_vendor_init_receives_secrets_in_stdin_not_outer_process_argv(self):
        legacy = re.search(r'    run_logged /usr/bin/issabel-admin-passwords --cli init \\\n.*?\n        \|\| die [^\n]+', self.source, re.S)
        body = 'if declare -F initialize_framework_passwords >/dev/null; then initialize_framework_passwords; else\n' + (legacy.group(0) if legacy else ':') + '\nfi\n'
        result, calls = self.run_shell(body)
        self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(len(calls), 1)
        self.assertNotIn('FixtureDb_123!', ' '.join(calls[0]['argv']))
        self.assertNotIn('Fixture Admin.456=', ' '.join(calls[0]['argv']))
        self.assertEqual(calls[0]['stdin'], 'FixtureDb_123!\nFixture Admin.456=\n')

    def test_saved_mysql_password_check_is_exact_and_rejects_duplicate_keys(self):
        config = self.base / 'issabel-fixture.conf'
        legacy = re.search(r'    grep -q "\^mysqlrootpwd=.*?\n        \|\| die [^\n]+', self.source, re.S)
        for content, expected in [('mysqlrootpwd=Fixture.Db_123!\n', 0),
                                  ('mysqlrootpwd=FixtureXDb_123!\n', 1),
                                  ('mysqlrootpwd=Fixture.Db_123!\nmysqlrootpwd=another\n', 1)]:
            config.write_text(content)
            old = legacy.group(0).replace('/etc/issabel.conf', repr(config.as_posix())) if legacy else ':'
            body = "MYSQL_ROOT_PASS='Fixture.Db_123!'\nif declare -F verify_mysql_root_password >/dev/null; then verify_mysql_root_password " + repr(config.as_posix()) + '; else legacy_verify(){\n' + old + '\n}; legacy_verify; fi\n'
            result, _calls = self.run_shell(body)
            with self.subTest(content=content):
                self.assertEqual(result.returncode == 0, expected == 0, result.stderr)


if __name__ == '__main__': unittest.main()
