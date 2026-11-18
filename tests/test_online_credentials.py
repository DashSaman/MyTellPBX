"""Focused checks of the online installer prompts and native secret transport."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'installer/vendor-native'
SHELL_HELPER = NATIVE / 'online-credentials.sh'
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class OnlineCredentialsTest(unittest.TestCase):
    def test_native_initializer_reads_confirmed_pair_before_any_initialization(self):
        spec = importlib.util.spec_from_file_location('online_passwords', str(NATIVE / 'online-passwords.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fixture = (ROOT / 'tests/fixtures/vendor-native/issabel-admin-passwords').read_bytes()
        rendered = module.render(fixture)
        main = rendered.split(b"case '--init':", 1)[1].split(b"case '--change':", 1)[0]
        self.assertIn(b"$argv[1] !== '--init'", rendered)
        self.assertLess(main.index(b'php://fd/3'), main.index(b'ensure_pbxapi_jwt_secret()'))
        self.assertIn(b'if (!apply_updatesql()) error_exit(', rendered)
        self.assertIn(b'issabel_cli_web_passwd(FALSE, $mytelOnlinePasswords[1])', rendered)
        self.assertIn(b'/usr/bin/issabel-change-language pr', rendered)
        self.assertIn(b'mytel-online-sip.sh', rendered)
        self.assertIn(b'--defaults-file=/proc/self/fd/3', rendered)
        with self.assertRaises(ValueError):
            module.render(fixture + b'unexpected native update')

    @unittest.skipUnless(os.name == 'posix' and BASH, 'Linux pipe descriptor semantics')
    def test_receive_closes_descriptor_and_only_exports_driver(self):
        script = '''
source "$1"
mytel_receive_online_passwords || exit $?
[ "$_mytel_db_password" = 'FakeDb.42!' ] && [ "$_mytel_admin_password" = 'FakeAdmin.52!' ] || exit 21
if { : <&3; } 2>/dev/null; then exit 22; fi
if env | grep -q -E '(_mytel_db_password|_mytel_admin_password)='; then exit 23; fi
printf '%s\\n' "$MYTEL_ONLINE_SIP_DRIVER"
'''
        env = dict(os.environ, _mytel_db_password='INHERITED', _mytel_admin_password='INHERITED')
        start = [BASH, '--noprofile', '--norc', '-c', 'exec bash -c "$1" -- "$2" 3<&0',
                 '--', script, str(SHELL_HELPER)]
        for driver in ('pjsip', 'sip'):
            with self.subTest(driver=driver):
                valid = ('FakeDb.42!\nFakeAdmin.52!\n' + driver + '\n').encode()
                result = subprocess.run(start, input=valid, env=env, capture_output=True, timeout=8)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, (driver + '\n').encode(), b''))
                result = subprocess.run(start, input=valid + b'partial', env=env, capture_output=True, timeout=8)
                self.assertNotEqual(result.returncode, 0)
                output = result.stdout + result.stderr
                self.assertNotIn(b'FakeDb.42!', output)
                self.assertNotIn(b'FakeAdmin.52!', output)


if __name__ == '__main__':
    unittest.main()
