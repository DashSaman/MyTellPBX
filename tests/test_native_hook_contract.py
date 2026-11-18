"""Execute the native hook and exact shared shell with a disposable Python target."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class NativeHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='native-hook-contract-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bundle = self.base / 'bundle'
        installer = self.bundle / 'installer'
        installer.mkdir(parents=True)
        shutil.copyfile(ROOT / 'installer/install-mytel-addons.sh', installer / 'install-mytel-addons.sh')
        (installer / 'native-addons.py').write_text('''import json,os,sys
keys=['ASTVER','MYTEL_BUNDLE_ROOT','MYTEL_MEDIA_ROOT','MYTEL_MEDIA_MANIFEST_SHA256','MYTELL_DESK_PUBLIC_URL']
print(json.dumps(dict(env={k:os.environ.get(k) for k in keys},argv=sys.argv[1:])))
raise SystemExit(int(os.environ.get('FIXTURE_STATUS','0')))
''', encoding='utf-8')
        source = (ROOT / 'installer/vendor-native/mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        self.definitions = source.split('\n# MYTEL_NATIVE_FLOW\n', 1)[0]

    def exercise(self, major='20', status=0, offline=False):
        values = {'MYTEL_BUNDLE_ROOT': self.bundle.as_posix(), 'MYTEL_NATIVE_WORK': self.base.as_posix(),
                  'MYTEL_PYTHON': Path(sys.executable).as_posix(), 'ASTVER': major,
                  'FIXTURE_STATUS': str(status), 'MYTEL_MEDIA_ROOT': '/verified/media' if offline else '',
                  'MYTEL_MEDIA_MANIFEST_SHA256': 'a' * 64 if offline else '',
                  'MYTELL_DESK_PUBLIC_URL': 'https://pbx.example/MytellDesk'}
        script = self.definitions + '\n'
        # Export only the same integration fields that the bootstrap provides;
        # ASTVER is deliberately unexported until the REAL mytel_addons function.
        script += '\n'.join(('' if key == 'ASTVER' else 'export ') + key + '=' + shlex.quote(value)
                            for key, value in values.items())
        script += '\nbash(){ command ' + shlex.quote(Path(BASH).as_posix()) + ' "$@"; }\n'
        terminal = ROOT / 'installer/vendor-native/terminal-ui.sh'
        script += 'source ' + shlex.quote(terminal.as_posix()) + '\n'
        script += 'mytel_native_step mytel_addons\nprintf "CONTINUED\\n"\n'
        return subprocess.run([BASH, '--noprofile', '--norc', '-s'], input=script.encode('utf-8'),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
                              env=dict(os.environ, MSYS2_ENV_CONV_EXCL='*'))

    def test_only20_reaches_exact_shared_hook_without_rewriting_arguments(self):
        for major in ('20',):
            with self.subTest(major=major):
                result = self.exercise(major)
                self.assertEqual(result.returncode, 0, result.stderr)
                value = json.loads(next(line for line in result.stdout.splitlines() if line.startswith(b'{')))
                self.assertEqual(value['env']['ASTVER'], major)
                self.assertEqual(value['env']['MYTEL_BUNDLE_ROOT'], self.bundle.as_posix())
                self.assertEqual(value['argv'], [])
                self.assertIn(b'CONTINUED', result.stdout)

    def test_older_or_unknown_majors_cannot_enter_the_product_addon_hook(self):
        for major in ('16', '18', '21', ''):
            with self.subTest(major=major):
                result = self.exercise(major)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'CONTINUED', result.stdout)
                self.assertNotIn(b'"env"', result.stdout)

    def test_sealed_offline_identity_and_public_origin_survive_both_shell_boundaries(self):
        result = self.exercise(offline=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(next(line for line in result.stdout.splitlines() if line.startswith(b'{')))['env']
        self.assertEqual(value['MYTEL_MEDIA_ROOT'], '/verified/media')
        self.assertEqual(value['MYTEL_MEDIA_MANIFEST_SHA256'], 'a' * 64)
        self.assertEqual(value['MYTELL_DESK_PUBLIC_URL'], 'https://pbx.example/MytellDesk')

    def test_shared_hook_failure_prevents_later_native_cleanup_or_reboot(self):
        result = self.exercise(status=37)
        self.assertEqual(result.returncode, 37)
        self.assertNotIn(b'CONTINUED', result.stdout)
        self.assertIn(b'mytel_addons (status 37)', result.stderr)
        self.assertIn(b'No automatic reboot', result.stderr)


if __name__ == '__main__':
    unittest.main()
