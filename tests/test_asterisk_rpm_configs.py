"""Exercise the native configs scriptlet before the core RPM owns /etc/asterisk."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SPEC = Path(__file__).resolve().parents[1] / 'packaging/asterisk20/asterisk20.spec'


@unittest.skipUnless(os.name == 'posix' and shutil.which('sh'), 'POSIX RPM scriptlet fixture')
class ConfigPackageTests(unittest.TestCase):
    def test_fresh_config_is_staged_and_scriptlet_preserves_owner_settings(self):
        spec = SPEC.read_text(encoding='utf-8')
        begin = 'sample="%{buildroot}/etc/asterisk/asterisk.conf"'
        stage = begin + spec.split(begin, 1)[1].split('install -Dpm0644', 1)[0]
        post = spec.split("%post configs\nrunuser -u asterisk -- /bin/sh <<'AST_CONFIG'\n", 1)[1]
        post = post.split('\nAST_CONFIG\n', 1)[0]
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            directory = root / 'etc/asterisk'
            directory.mkdir(parents=True)
            config = directory / 'asterisk.conf'
            config.write_bytes(b'[options]\n;execincludes = yes\t; Support #exec in config files.\n')
            subprocess.run(['sh', '-eu', '-c', stage.replace('%{buildroot}', str(root))], check=True)
            self.assertIn(b'\nexecincludes = yes\t', config.read_bytes())

            # An administrator may already have a modified %config(noreplace).
            custom = directory / 'modules_custom.conf'
            custom.write_bytes(b'; Existing modules\n')
            config.write_bytes(b'[options]\n;execincludes = yes\t; operator preference\n')
            prior = config.read_bytes()
            command = ['sh', '-eu', '-c', post.replace('/etc/asterisk', str(directory))]
            root.chmod(0o755)
            directory.parent.chmod(0o755)
            if os.geteuid() == 0:
                import pwd
                account = pwd.getpwnam('nobody')
                if not shutil.which('runuser'):
                    self.skipTest('runuser is needed to exercise unprivileged writes as root')
                for file in (config, custom):
                    os.chown(file, account.pw_uid, account.pw_gid)
                command = ['runuser', '-u', 'nobody', '--'] + command
            directory.chmod(0o555)
            try:
                for _ in range(2):
                    subprocess.run(command, check=True)
            finally:
                directory.chmod(0o755)
            self.assertEqual(config.read_bytes(), prior)
            self.assertEqual(custom.read_bytes(), b'; Existing modules\nnoload => cdr_mysql.so\n')
