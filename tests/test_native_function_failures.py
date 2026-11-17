"""Failure injection into actual native Bash functions, never host commands."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class NativeFunctionFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='native-function-contract-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.log = self.base / 'netinstall.log'
        source = (ROOT / 'installer/vendor-native/mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        self.definitions = source.split('\n# MYTEL_NATIVE_FLOW\n', 1)[0]
        # Only fixture paths are writable, and every target command is stubbed.
        self.definitions = self.definitions.replace('/usr/sbin/amportal', 'amportal_fixture')
        self.definitions = self.definitions.replace('/etc/asterisk/modules_additional.conf',
                                                    '${MYTEL_NATIVE_WORK}/modules.conf')
        self.definitions = self.definitions.replace('/etc/redhat-release',
                                                    (self.base / 'redhat-release').as_posix())
        self.definitions = self.definitions.replace('/etc/dnf/dnf.conf',
                                                    (self.base / 'dnf.conf').as_posix())
        (self.base / 'redhat-release').write_text('Rocky Linux release 8.10 (Green Obsidian)\n')
        (self.base / 'dnf.conf').write_text('[main]\n')

    def shell(self, body):
        script = self.definitions + '\nMYTEL_NATIVE_WORK=' + shlex.quote(self.base.as_posix())
        script += '\nMYTEL_BUNDLE_ROOT=/fixture\nMYTEL_PYTHON=repair_stub\nBACKTITLE=Fixture\n'
        script += body
        return subprocess.run([BASH, '--noprofile', '--norc', '-s'], input=script.encode('utf-8'),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)

    def test_package_transaction_failure_survives_successful_dialog_and_trailing_log(self):
        result = self.shell('''
dialog(){ cat >/dev/null; }
rpm(){ return 1; }
yum(){ printf 'private-fixture-package-diagnostic\\n'; return 42; }
mytel_native_step yum_gauge "required-package" Fixture install
printf 'CONTINUED\\n'
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'CONTINUED', result.stdout)
        self.assertNotIn(b'private-fixture-package-diagnostic', result.stdout + result.stderr)
        self.assertIn('private-fixture-package-diagnostic', self.log.read_text())
        self.assertIn('required-package: ERROR', (self.base / 'netinstall_errors.txt').read_text())

    def test_dialog_failure_is_fatal_even_after_successful_package_transaction(self):
        result = self.shell('''
dialog(){ cat >/dev/null; return 7; }
rpm(){ return 1; }
yum(){ return 0; }
mytel_native_step yum_gauge "required-package" Fixture install
printf 'CONTINUED\\n'
''')
        self.assertEqual(result.returncode, 7)
        self.assertNotIn(b'CONTINUED', result.stdout)

    def test_update_catalog_failure_cannot_become_empty_successful_update(self):
        result = self.shell('''
yum(){ return 42; }
mytel_native_step update_os
printf 'CONTINUED\\n'
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'CONTINUED', result.stdout)
        self.assertNotIn('no package to upgrade', self.log.read_text())

    def test_every_essential_post_install_failure_stops_before_later_stage(self):
        for failing in ('enable-mariadb', 'start-mariadb', 'set-root-pass', 'enable-httpd',
                        'clear-root-pass', 'mv', 'amportal'):
            with self.subTest(command=failing):
                result = self.shell('FAIL=' + shlex.quote(failing) + '''
systemctl(){ case "$1 $2" in 'enable mariadb.service') key=enable-mariadb;; 'start mariadb') key=start-mariadb;; 'enable httpd') key=enable-httpd;; *) key=other;; esac; [ "$FAIL" != "$key" ]; }
mysql(){ if [[ "$1" = -p* ]]; then key=clear-root-pass; else key=set-root-pass; fi; [ "$FAIL" != "$key" ]; }
mv(){ [ "$FAIL" != mv ]; }
amportal_fixture(){ [ "$FAIL" != amportal ]; }
setenforce(){ :; }; sed(){ :; }; cp(){ :; }; firewall-cmd(){ :; }; rm(){ :; }; mkdir(){ :; }
mytel_native_step post_install
printf 'CONTINUED\\n'
''')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'CONTINUED', result.stdout)
                self.assertIn(b'stopped at post_install', result.stderr)

    def test_native_remi_repair_precedes_every_module_operation(self):
        result = self.shell('''
dnf(){ printf 'DNF:%s\\n' "$*"; }
repair_stub(){ printf 'REPAIR:%s\\n' "$*"; }
mytel_native_step centos8_tweaks
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        events = result.stdout.decode().splitlines() + self.log.read_text().splitlines()
        # Repair goes to the console; native dnf output goes to its private log.
        self.assertTrue(any('repair-repository-transport.py' in line for line in events))
        self.assertIn('DNF:module enable php:remi-7.4 -y', events)
        # Execute a stronger causal guard: module operations refuse unless repair
        # has actually run; the first Remi package transaction remains permitted.
        result = self.shell('''
REPAIRED=0
repair_stub(){ REPAIRED=1; }
dnf(){ case "$*" in 'install -y https://rpms.remirepo.net/'*) return 0;; *) [ "$REPAIRED" = 1 ];; esac; }
mytel_native_step centos8_tweaks
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_remi_failure_stops_and_check_upgrade_status100_is_expected(self):
        for failure in ('install', 'repair', 'module', 'remi', 'powertools', 'devel', 'check-upgrade'):
            with self.subTest(command=failure):
                result = self.shell('FAIL=' + shlex.quote(failure) + '''
repair_stub(){ [ "$FAIL" != repair ]; }
dnf(){ case "$*" in 'install '*) key=install;; 'module '*) key=module;; *'--set-enabled remi') key=remi;; *'--set-enabled powertools') key=powertools;; *'--set-enabled devel') key=devel;; *'check-upgrade') key=check-upgrade;; *) return 99;; esac; [ "$FAIL" != "$key" ]; }
mytel_native_step centos8_tweaks
printf 'CONTINUED\\n'
''')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'CONTINUED', result.stdout)
        result = self.shell('''
repair_stub(){ :; }
dnf(){ case "$*" in *'check-upgrade') return 100;; *) return 0;; esac; }
mytel_native_step centos8_tweaks
''')
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
