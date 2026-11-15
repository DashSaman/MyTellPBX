"""Prove bootstrap preserves existing/unknown data with fake SQL/OS clients."""
import base64
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class BootstrapPreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.root = self.base / 'root'; (self.root / 'etc').mkdir(parents=True)
        self.events = self.base / 'events'
        self.source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        definitions = self.base / 'definitions.sh'; definitions.write_text(self.source.rsplit('\nmain "$@"', 1)[0], encoding='utf-8')
        self.setup = 'source ' + repr(definitions.as_posix()) + '\nLOG=' + repr((self.base / 'log').as_posix()) + '\n'
        self.setup += 'PY_BIN=' + repr(sys.executable.replace('\\', '/')) + '\n'
        uid = os.getuid() if hasattr(os, 'getuid') else 989
        gid = os.getgid() if hasattr(os, 'getgid') else 984
        self.setup += 'getent(){ case "$1:$2" in passwd:asterisk) printf \'asterisk:x:' + str(uid) + ':' + str(gid) + ':Asterisk:/var/lib/asterisk:/bin/bash\\n\';; group:asterisk) printf \'asterisk:x:' + str(gid) + ':\\n\';; *) return 2;; esac; }\n'
        self.setup += 'FIXTURE_ROOT=' + repr(self.root.as_posix()) + '\nEVENTS=' + repr(self.events.as_posix()) + '\nATTEMPTS=0\n'
        # ALL SQL, password changes, config removal and vendor commands are
        # intercepted. Nothing outside this temporary directory is provisioned.
        self.setup += '''MYSQL_ROOT_PASS='FixtureDb!'; LANG_SEL=fa
mysql_any(){
    local query="$*"
    case "$*" in *-e*) ;; *) query=$(cat);; esac
    case "$MODE" in invalid-count) printf NaN; return 0;; duplicate-count) printf '0\\n0'; return 0;; esac
    if [ "$MODE" = metadata-fail ]; then return 7; fi
    if [ "$MODE" = post-query-fail ] && [ "$ATTEMPTS" -gt 0 ]; then return 7; fi
    case "$query" in
      *information_schema.SCHEMATA*) [ "$MODE" != unknown-schema ] && printf 0 || printf 1;;
      *TABLE_NAME=*)
        if [ "$MODE" = fresh ] && [ "$ATTEMPTS" -gt 0 ]; then printf 1; else printf 0; fi;;
      *information_schema.TABLES*|*information_schema.tables*)
        if [ "$MODE" = populated ]; then printf 8
        elif [ "$MODE" = partial-after ] && [ "$ATTEMPTS" -gt 0 ]; then printf 8
        elif [ "$ATTEMPTS" -gt 0 ] && [ "$MODE" = fresh ]; then printf 10
        else printf 0; fi;;
      *asterisk.modules*) [ "$MODE" = fresh ] && [ "$ATTEMPTS" -gt 0 ] && printf 6 || printf 0;;
      *SHOW*ampusers*) [ "$MODE" = fresh ] && [ "$ATTEMPTS" -gt 0 ] && printf ampusers || return 1;;
      *) return 8;;
    esac
}
mysql(){
    local query="$*"
    case "$*" in *-e*) ;; *) query=$(cat);; esac
    printf 'mysql %s\\n' "$query" >> "$EVENTS"
    case "$query" in *SELECT*) return 1;; esac
}
run_logged(){
    printf 'vendor %s\\n' "$*" >> "$EVENTS"
    case "$1" in
      */install_amp)
        ATTEMPTS=$((ATTEMPTS+1))
        if [ "$MODE" = fresh ]; then printf 'fresh config\\n' > "$FIXTURE_ROOT/etc/amportal.conf"; return 0; fi
        return 1;;
      *) return 0;;
    esac
}
normalize_framework_mysql(){ printf 'normalize\\n' >> "$EVENTS"; }
rm(){ printf 'rm %s\\n' "$*" >> "$EVENTS"; }
sleep(){ :; }
'''
        self.ami = b'Factory123'
        self.jwt = base64.b64encode(bytes(range(32)))
        self.factory = b'amiadminpwd=' + self.ami + b'\npbxapijwtsecret=' + self.jwt + b'\n'
        old = re.search(r'    # Framework first-boot install\..*?(?=    # Non-interactive password initialization)', self.source, re.S)
        self.legacy = 'legacy_bootstrap(){\n' + (old.group(0) if old else ':') + '\n}\n'

    def run_bootstrap(self, mode):
        script = self.base / 'run.sh'
        body = self.setup + 'MODE=' + mode + '\n' + self.legacy
        body += 'if declare -F bootstrap_empty_framework >/dev/null; then bootstrap_empty_framework "$FIXTURE_ROOT"; else legacy_bootstrap; fi\n'
        script.write_text(body, encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        return result, self.events.read_text() if self.events.exists() else ''

    def test_existing_partial_framework_and_cdr_config_cannot_reinitialize(self):
        config = self.root / 'etc/amportal.conf'; config.write_bytes(b'operator config\n')
        result, events = self.run_bootstrap('populated')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, '', 'no install, config removal, DROP or password clearing is authorized')
        self.assertEqual(config.read_bytes(), b'operator config\n')

    def test_metadata_failure_or_unknown_schema_cannot_trigger_reset(self):
        for mode in ['metadata-fail', 'invalid-count', 'duplicate-count', 'unknown-schema', 'populated']:
            with self.subTest(mode=mode):
                if self.events.exists(): self.events.unlink()
                result, events = self.run_bootstrap(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(events, '')

    def test_fresh_bootstrap_succeeds_without_drop_or_config_deletion(self):
        result, events = self.run_bootstrap('fresh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events.count('/install_amp '), 1)
        self.assertIn('normalize\n', events)
        self.assertNotIn('DROP ', events)
        self.assertNotIn('/etc/amportal.conf', events)
        self.assertNotIn('/etc/issabel.conf', events)

    def test_no_progress_is_bounded_but_partial_progress_is_never_dropped(self):
        for mode, attempts in [('no-progress', 3), ('partial-after', 1), ('post-query-fail', 1)]:
            with self.subTest(mode=mode):
                if self.events.exists(): self.events.unlink()
                result, events = self.run_bootstrap(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(events.count('/install_amp '), attempts)
                self.assertNotIn('DROP ', events)
                self.assertNotIn('/etc/amportal.conf', events)

    def test_postbase_has_no_password_normalization_or_config_removal(self):
        postbase = self.source.split('stage_post_base() {', 1)[1].split('\n# ----', 1)[0]
        self.assertNotIn('normalize_framework_mysql', postbase)
        self.assertNotIn('rm -f /etc/issabel.conf', postbase)

    def test_healthy_framework_marker_returns_without_mutating_or_querying(self):
        script = self.base / 'healthy.sh'
        script.write_text(self.setup + 'MODE=metadata-fail\nstage_done(){ [ "$1" = framework ]; }\nstage_framework_init\n', encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.events.exists())

    def test_selfcheck_query_failure_preserves_completed_framework_marker(self):
        state = self.base / 'state'; (state / 'stages').mkdir(parents=True)
        marker = state / 'stages/framework.done'; marker.touch()
        script = self.base / 'selfcheck.sh'
        script.write_text(self.setup + 'STATE_DIR=' + repr(state.as_posix()) + '\nMODE=metadata-fail\nensure_credentials(){ :; }\n'
                          + 'rm(){ command rm "$@"; }\nstage_selfcheck\n', encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(marker.exists(), 'a failed query is not evidence that the completed framework is absent')

    def write_factory(self, content=None):
        path = self.root / 'etc/issabel.conf'; path.write_bytes(self.factory if content is None else content)
        path.chmod(0o600)
        return path

    def test_observed_factory_service_config_is_preserved_during_fresh_bootstrap(self):
        config = self.write_factory()
        result, _events = self.run_bootstrap('fresh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(config.read_bytes(), self.factory)

    def test_unknown_duplicate_initialized_or_invalid_factory_keys_are_refused(self):
        for content in [self.factory + b'unknown=operator\n', self.factory + b'mysqlrootpwd=existing\n',
                        self.factory + b'amiadminpwd=duplicate\n',
                        self.factory.replace(self.ami, b'too-short'),
                        self.factory.replace(self.ami, b'Bad:Secret'),
                        self.factory.replace(self.jwt, b'!' * 44),
                        b'amiadminpwd=' + self.ami + b'\npbxapijwtsecret=' + base64.b64encode(b'short') + b'\n']:
            with self.subTest(content=content):
                self.write_factory(content)
                if self.events.exists(): self.events.unlink()
                result, events = self.run_bootstrap('fresh')
                self.assertNotEqual(result.returncode, 0); self.assertEqual(events, '')

    def test_native_initialization_receives_factory_ami_then_verifies_both_keys(self):
        config = self.write_factory(); native = self.base / 'native-input'
        body = self.setup + 'MODE=fresh\nADMIN_PASS=ChosenPanel!\n'
        body += 'initialize_framework_passwords(){ printf \'%s\' "$1" > ' + repr(native.as_posix()) + '; printf \'mysqlrootpwd=FixtureDb!\\ncyrususerpwd=FixtureDb!\\n\' >> "$FIXTURE_ROOT/etc/issabel.conf"; }\n'
        body += 'initialize_preserving_framework_keys "$FIXTURE_ROOT"\n'
        script = self.base / 'native.sh'; script.write_text(body, encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(native.read_bytes(), self.ami)
        self.assertIn(self.factory, config.read_bytes())
        self.assertNotIn(self.ami, result.stdout + result.stderr); self.assertNotIn(self.jwt, result.stdout + result.stderr)

    def test_native_init_key_rotation_or_unknown_field_is_rejected(self):
        for change in ['rotate', 'unknown']:
            with self.subTest(change=change):
                self.write_factory()
                body = self.setup + 'ADMIN_PASS=ChosenPanel!\n'
                if change == 'rotate':
                    body += "initialize_framework_passwords(){ printf 'amiadminpwd=Changed123\\npbxapijwtsecret=" + self.jwt.decode() + "\\nmysqlrootpwd=FixtureDb!\\ncyrususerpwd=FixtureDb!\\n' > \"$FIXTURE_ROOT/etc/issabel.conf\"; }\n"
                else:
                    body += "initialize_framework_passwords(){ printf 'mysqlrootpwd=FixtureDb!\\ncyrususerpwd=FixtureDb!\\nunknown=operator\\n' >> \"$FIXTURE_ROOT/etc/issabel.conf\"; }\n"
                body += 'initialize_preserving_framework_keys "$FIXTURE_ROOT"\n'
                script = self.base / 'changed.sh'; script.write_text(body, encoding='utf-8')
                result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertNotEqual(result.returncode, 0)

    @unittest.skipIf(os.name != 'posix', 'Native POSIX private configuration boundary')
    def test_factory_config_wrong_permissions_symlink_or_owner_is_refused(self):
        config = self.write_factory(); config.chmod(0o644)
        result, events = self.run_bootstrap('fresh')
        self.assertNotEqual(result.returncode, 0); self.assertEqual(events, '')
        config.unlink(); outside = self.base / 'outside'; outside.write_bytes(self.factory)
        config.symlink_to(outside)
        result, events = self.run_bootstrap('fresh')
        self.assertNotEqual(result.returncode, 0); self.assertEqual(events, '')


if __name__ == '__main__': unittest.main()
