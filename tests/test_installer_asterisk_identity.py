"""Asterisk RPM ownership ordering with synthetic NSS and account commands."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class AsteriskIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        definitions = self.base / 'definitions.sh'
        definitions.write_text(self.source.rsplit('\nmain "$@"', 1)[0], encoding='utf-8')
        self.setup = 'source ' + repr(definitions.as_posix()) + '\nLOG=' + repr((self.base / 'log').as_posix()) + '\n'
        self.calls = self.base / 'calls'
        self.setup += 'CALLS=' + repr(self.calls.as_posix()) + '\n'
        self.setup += '''GROUP=''; ACCOUNT=''; FAIL=''
getent(){
    [ "$FAIL" != getent ] || return 3
    case "$1:$2" in
      group:asterisk) [ -n "$GROUP" ] || return 2; printf '%s\\n' "$GROUP";;
      passwd:asterisk) [ -n "$ACCOUNT" ] || return 2; printf '%s\\n' "$ACCOUNT";;
      *) return 3;;
    esac
}
run_logged(){
    printf '%s\\n' "$*" >> "$CALLS"
    case "$1" in
      /usr/sbin/groupadd) [ "$FAIL" != groupadd ] || return 1; GROUP='asterisk:x:997:';;
      /usr/sbin/useradd) [ "$FAIL" != useradd ] || return 1; ACCOUNT='asterisk:x:998:997:Asterisk PBX:/var/lib/asterisk:/bin/bash';;
      *) return 99;;
    esac
}
'''

    def run_shell(self, body):
        script = self.base / 'identity.sh'; script.write_text(self.setup + body, encoding='utf-8')
        return subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')

    def test_missing_service_identity_is_created_once_with_original_defaults(self):
        result = self.run_shell('ensure_asterisk_identity\nensure_asterisk_identity\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls.read_text().splitlines()
        self.assertEqual(calls, ['/usr/sbin/groupadd -r asterisk', '/usr/sbin/useradd -r -g asterisk -c Asterisk PBX -s /bin/bash -d /var/lib/asterisk asterisk'])

    def test_valid_existing_identity_and_group_members_are_preserved(self):
        result = self.run_shell("GROUP='asterisk:x:95:existing-member'\nACCOUNT='asterisk:x:75:95:Existing comment:/var/lib/asterisk:/bin/bash'\nensure_asterisk_identity\nprintf '%s\\n%s' \"$GROUP\" \"$ACCOUNT\"\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.calls.exists())
        self.assertIn('asterisk:x:95:existing-member', result.stdout)
        self.assertIn('asterisk:x:75:95:Existing comment:', result.stdout)

    def test_conflicting_identity_refuses_before_any_account_mutation(self):
        cases = [('', 'asterisk:x:75:95:Asterisk:/var/lib/asterisk:/bin/bash'),
                 ('asterisk:x:1000:', ''), ('asterisk:x:0:', ''),
                 ('asterisk:x:95:', 'asterisk:x:1000:95:Asterisk:/var/lib/asterisk:/bin/bash'),
                 ('asterisk:x:95:', 'asterisk:x:0:95:Asterisk:/var/lib/asterisk:/bin/bash'),
                 ('asterisk:x:95:', 'asterisk:x:75:96:Asterisk:/var/lib/asterisk:/bin/bash'),
                 ('asterisk:x:95:', 'asterisk:x:75:95:Asterisk:/home/operator:/bin/bash'),
                 ('asterisk:x:95:', 'other-asterisk:x:75:95:Asterisk:/var/lib/asterisk:/bin/bash')]
        for group, account in cases:
            with self.subTest(group=group, account=account):
                result = self.run_shell('GROUP=' + repr(group) + '\nACCOUNT=' + repr(account) + '\nensure_asterisk_identity\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.calls.exists())

    def test_creation_or_lookup_failure_stops_instead_of_claiming_success(self):
        for failure in ['groupadd', 'useradd', 'getent']:
            with self.subTest(failure=failure):
                result = self.run_shell('FAIL=' + failure + '\nensure_asterisk_identity\nprintf continued\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('continued', result.stdout)

    def test_stage1_ensures_identity_before_any_rpm_install_and_skips_done_stage(self):
        bundle = self.base / 'bundle/installer/packages'; bundle.mkdir(parents=True)
        (bundle / 'rocky8-stage1.txt').write_text('asterisk20-configs\n')
        body = 'BUNDLE_DIR=' + repr((self.base / 'bundle').as_posix()) + '\n'
        body += '''READY=0; DONE=0
stage_done(){ [ "$DONE" = 1 ]; }; step(){ :; }
ensure_asterisk_identity(){ printf 'identity\\n' >> "$CALLS"; READY=1; }
install_with_retry(){ [ "$READY" = 1 ] || return 42; printf 'rpm\\n' >> "$CALLS"; }
mark_stage(){ DONE=1; }
stage_packages1
stage_packages1
'''
        result = self.run_shell(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls.read_text().splitlines() if self.calls.exists() else [], ['identity', 'rpm'])

    def test_postbase_rechecks_same_identity_instead_of_silent_account_creation(self):
        postbase = self.source.split('stage_post_base() {', 1)[1].split('\n# ----', 1)[0]
        self.assertIn('ensure_asterisk_identity', postbase)
        self.assertLess(postbase.index('ensure_asterisk_identity'), postbase.index('systemctl'))
        self.assertNotIn('groupadd', postbase); self.assertNotIn('useradd', postbase)

    def test_framework_start_uses_one_native_unit_without_safe_asterisk_helper(self):
        # Redirect only the optional vendor executable's path into a fixture;
        # every start/provisioning command is intercepted below.
        vendor = self.base / 'start_asterisk'; vendor.write_text('#!/bin/bash\nexit 99\n'); vendor.chmod(0o755)
        original = self.base / 'definitions.sh'
        original.write_text(self.source.rsplit('\nmain "$@"', 1)[0].replace('/usr/src/issabelPBX/framework/start_asterisk', vendor.as_posix()), encoding='utf-8')
        unit = self.base / 'unit-started'
        body = 'UNIT=' + repr(unit.as_posix()) + '\n'
        body += 'BUNDLE_DIR=' + repr((self.base / 'bundle').as_posix()) + '\nPY_BIN=fixture_python\n'
        body += '''stage_done(){ return 1; }; ensure_credentials(){ :; }; guard_empty_framework_bootstrap(){ :; }
framework_service_config(){ printf absent; }; sleep(){ :; }
native_start(){ :; }
bootstrap_empty_framework(){ exit 42; }
wait_asterisk_ready(){ printf 'readiness\n' >> "$CALLS"; }
asterisk(){ [ -f "$UNIT" ]; }
systemctl(){ printf 'unit %s\\n' "$*" >> "$CALLS"; [ "$1" != start ] || printf started > "$UNIT"; }
run_logged(){
    if [ "$#" = 3 ] && [ "$1" = "$PY_BIN" ] && [ "$2" = -B ] && [ "$3" = "${BUNDLE_DIR}/installer/patch-native-include-order.py" ]; then return 0; fi
    printf 'manual %s\\n' "$*" >> "$CALLS"; return 99
}
stage_framework_init
'''
        result = self.run_shell(body)
        self.assertEqual(result.returncode, 42, result.stderr)
        calls = self.calls.read_text()
        self.assertNotIn('manual ', calls)
        self.assertEqual(calls.count('unit start asterisk'), 1)
        self.assertIn('readiness', calls)
        self.assertLess(calls.index('unit start asterisk'), calls.index('readiness'))
        self.assertLess(calls.index('readiness'), calls.index('unit enable asterisk'))


if __name__ == '__main__': unittest.main()
