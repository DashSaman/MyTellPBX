"""Focused checks of the online installer prompts and native secret transport."""

import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
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
        self.assertIn(b'/mytel-online-language.sh', rendered)
        self.assertIn(b'mytel-online-sip.sh', rendered)
        self.assertIn(b'--defaults-file=/proc/self/fd/3', rendered)
        with self.assertRaises(ValueError):
            module.render(fixture + b'unexpected native update')

    @unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
    def test_persian_setup_preserves_native_values_and_has_no_terminal_side_effect(self):
        spec = importlib.util.spec_from_file_location('online_sip', str(NATIVE / 'online-sip.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = (ROOT / 'tests/fixtures/vendor-native/issabel-change-language').read_bytes()
        script = module.derive_language(original).decode()
        for action in ('dialog ', '/dev/tty', '\nlogo', '\n    clear', '/tmp/ipbx.lang'):
            self.assertNotIn(action, script)
        with self.assertRaises(ValueError):
            module.derive_language(original + b'\n# drift')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ['settings.db', 'fop2settings.db', 'asterisk.conf', 'chan_dahdi.conf']:
                (root / path).write_text('[channels]\ndefaultlanguage=en\n')
            (root / 'issabel.conf').write_text('mysqlrootpwd=Example.9081\n')
            for native in ('/var/www/db/settings.db', '/usr/local/fop2/fop2settings.db',
                           '/etc/asterisk/asterisk.conf', '/etc/asterisk/chan_dahdi.conf', '/etc/issabel.conf'):
                script = script.replace(native, (root / Path(native).name).as_posix())
            events = root / 'events'
            setup = 'EVENTS=' + shlex.quote(events.as_posix()) + '\n' + '''sqlite3(){ printf '%s\\n' "$*" >> "$EVENTS"; }
mysql(){
    [ "$1" = '--defaults-extra-file=/dev/fd/3' ] && grep -qx 'password="Example.9081"' <&3 || exit 81
    printf '%s\\n' "$*" >> "$EVENTS"
}
amportal(){ printf 'amportal %s\\n' "$*" >> "$EVENTS"; return 37; }
'''
            result = subprocess.run([BASH, '--noprofile', '--norc', '-s'], input=(setup + script).encode(),
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 37, result.stderr)
            self.assertEqual(result.stdout + result.stderr, b'')
            actions = events.read_text()
            self.assertIn("value='fa' where key='language'", actions)
            self.assertIn("'sip_language','pr'", actions)
            self.assertIn("'LANGUAGE','en_US'", actions)
            self.assertEqual(actions.count('--defaults-extra-file=/dev/fd/3'), 4)
            self.assertNotIn('Example.9081', actions)
            self.assertEqual(actions.splitlines()[-1], 'amportal a r')
            self.assertIn('defaultlanguage=pr', (root / 'asterisk.conf').read_text())
            # DAHDI is optional on pure SIP installations. A database error
            # must stop before reloading, even when a later sed would succeed.
            (root / 'chan_dahdi.conf').unlink()
            for tool in ('mysql', 'sqlite3'):
                with self.subTest(failing_tool=tool):
                    events.write_text('')
                    fixture = setup + tool + '(){ return 43; }\n' + script
                    result = subprocess.run([BASH, '--noprofile', '--norc', '-s'], input=fixture.encode(),
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 43, result.stderr)
                    self.assertNotIn('amportal', events.read_text())
            result = subprocess.run([BASH, '--noprofile', '--norc', '-s'], input=(setup + script).encode(),
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 37, result.stderr)
            self.assertEqual(result.stdout + result.stderr, b'')

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
