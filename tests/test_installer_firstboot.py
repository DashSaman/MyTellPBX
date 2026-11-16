"""Run real first-boot shell functions with fake clients; never touch a PBX."""
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
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class FirstBootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.definitions = self.base / 'definitions.sh'
        self.definitions.write_text(self.source.rsplit('\nmain "$@"', 1)[0] + '\n', encoding='utf-8')
        self.credentials = self.base / 'credentials'

    def run_shell(self, body, input_text='', env=None):
        script = self.base / 'run.sh'
        setup = 'source ' + repr(self.definitions.as_posix()) + '\n'
        setup += 'LOG=' + repr((self.base / 'log').as_posix()) + '\n'
        setup += 'CRED_FILE=' + repr(self.credentials.as_posix()) + '\n'
        setup += 'PY_BIN=' + repr(sys.executable.replace('\\', '/')) + '\n'
        setup += "openssl(){ printf 'GeneratedFixture987'; }\nsleep(){ :; }\n"
        # A test seam selects the interactive branch; read itself is exercised.
        script.write_text(setup + body, encoding='utf-8')
        child_env = dict(os.environ)
        child_env.pop('MYTELL_ADMIN_PASS', None); child_env.pop('MYTELL_MYSQL_ROOT_PASS', None)
        child_env.update(env or {})
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], input=input_text.encode('utf-8'),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=child_env)
        result.stdout = result.stdout.decode('utf-8', errors='replace')
        result.stderr = result.stderr.decode('utf-8', errors='replace')
        return result

    def load_values(self):
        return dict(re.findall(r"^(MYSQL_ROOT_PASS|ADMIN_PASS)='([^']*)'$", self.credentials.read_text(), re.M))

    def test_interactive_two_hidden_reads_preserve_literal_passwords(self):
        result = self.run_shell("credential_input_is_tty(){ return 0; }\nread(){ { printf '%s ' \"$@\"; printf '\\n'; } >> \"${CRED_FILE}.reads\"; builtin read \"$@\"; }\nensure_credentials\n", 'Panel Secret_12!\nDatabase Secret_34=\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load_values(), {'ADMIN_PASS': 'Panel Secret_12!', 'MYSQL_ROOT_PASS': 'Database Secret_34='})
        reads = Path(str(self.credentials) + '.reads').read_text().splitlines()
        self.assertEqual(len(reads), 2)
        self.assertTrue(all('-r' in line.split() and '-s' in line.split() for line in reads))
        self.assertNotIn('Panel Secret_12!', result.stdout + result.stderr)
        self.assertNotIn('Database Secret_34=', result.stdout + result.stderr)

    def test_blank_interactive_values_generate_without_extra_prompts(self):
        result = self.run_shell('credential_input_is_tty(){ return 0; }\nensure_credentials\n', '\n\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(self.load_values().values()), {'GeneratedFixture987'})
        self.assertEqual(result.stderr.count('رمز '), 2)

    def test_environment_skips_prompts_and_noninteractive_generates(self):
        result = self.run_shell('credential_input_is_tty(){ return 0; }\nread(){ return 99; }\nensure_credentials\n', env={'MYTELL_ADMIN_PASS': 'ChosenAdmin!', 'MYTELL_MYSQL_ROOT_PASS': 'ChosenDb='})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load_values()['ADMIN_PASS'], 'ChosenAdmin!')
        self.credentials.unlink()
        result = self.run_shell('read(){ return 99; }\nensure_credentials\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(self.load_values().values()), {'GeneratedFixture987'})

    def test_interrupted_or_invalid_input_never_creates_final_credentials(self):
        for incoming in ['ValidPanel!\n', "Bad'Panel\nValidDb\n", 'ValidPanel!\nBad:Db\n']:
            with self.subTest(incoming=incoming):
                result = self.run_shell('credential_input_is_tty(){ return 0; }\nensure_credentials\n', incoming)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.credentials.exists())

    def test_resume_preserves_originals_without_prompt_or_rotation(self):
        self.credentials.write_bytes(b"MYSQL_ROOT_PASS='OriginalDb!'\nADMIN_PASS='OriginalPanel='\n")
        self.credentials.chmod(0o600)
        result = self.run_shell('credential_input_is_tty(){ return 0; }\nread(){ exit 99; }\nensure_credentials\n', env={'MYTELL_ADMIN_PASS': 'Different!'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load_values(), {'MYSQL_ROOT_PASS': 'OriginalDb!', 'ADMIN_PASS': 'OriginalPanel='})

    def test_malformed_existing_credentials_fail_without_execution(self):
        sentinel = self.base / 'executed'
        self.credentials.write_text("MYSQL_ROOT_PASS='Good!'\nADMIN_PASS='Good='\ntouch '" + sentinel.as_posix() + "'\n")
        self.credentials.chmod(0o600)
        result = self.run_shell('ensure_credentials\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(sentinel.exists())

    @unittest.skipIf(os.name == 'nt', 'POSIX ownership/mode asserted on native Linux')
    def test_created_credentials_are_private(self):
        result = self.run_shell('ensure_credentials\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.credentials.stat().st_mode & 0o777, 0o600)

    def test_admin_verification_sql_does_not_expose_secret_in_argv(self):
        recorder = self.base / 'calls'
        legacy = re.search(r'    local amp_ok=""\n.*?\n    \[ "\$\{amp_ok\}" = "1" \] \|\| die [^\n]+', self.source, re.S)
        body = "ADMIN_PASS='Secret Verify_123!'\nmysql_any(){ printf '%s\\n' \"$*\" > " + repr(recorder.as_posix()) + "; cat >> " + repr(recorder.as_posix()) + "; printf 1; }\n"
        body += 'if declare -F verify_amp_admin_password >/dev/null; then verify_amp_admin_password; else legacy(){\n' + (legacy.group(0) if legacy else ':') + '\n}; legacy; fi\n'
        result = self.run_shell(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = recorder.read_text().splitlines()
        self.assertNotIn('Secret Verify_123!', lines[0])
        self.assertIn("SHA1('Secret Verify_123!')", '\n'.join(lines[1:]))

    def test_database_auth_requires_chosen_and_rejects_blank_and_wrong(self):
        for behavior, expected in [('healthy', 0), ('chosen-fails', 1), ('blank-accepted', 1), ('wrong-accepted', 1)]:
            with self.subTest(behavior=behavior):
                calls = self.base / ('mysql-' + behavior)
                body = "MYSQL_ROOT_PASS='ChosenDb!'; BEHAVIOR=" + repr(behavior) + '\n'
                body += "mysql(){ printf '%s|%s\\n' \"$*\" \"${MYSQL_PWD:-}\" >> " + repr(calls.as_posix()) + "; cat >/dev/null; case \"$BEHAVIOR:${MYSQL_PWD:-}\" in healthy:ChosenDb!|blank-accepted:ChosenDb!|wrong-accepted:*|blank-accepted:) return 0;; *) return 1;; esac; }\nverify_mysql_authentication\n"
                result = self.run_shell(body)
                self.assertEqual(result.returncode == 0, expected == 0, result.stderr)
                self.assertTrue(calls.exists(), 'real authentication client must be called')
                self.assertTrue(all(line.startswith('--no-defaults --user=root --protocol=socket ') for line in calls.read_text().splitlines()))

    def test_asterisk_inactive_disabled_or_unresponsive_is_fatal(self):
        for state, expected in [('healthy', 0), ('inactive', 1), ('disabled', 1), ('cli-failed', 1),
                                ('static', 1), ('generated', 1), ('enabled-runtime', 1)]:
            with self.subTest(state=state):
                body = 'STATE=' + repr(state) + '\nsystemctl(){ case "$1:$STATE" in is-active:inactive|is-enabled:disabled) return 1;; is-enabled:static|is-enabled:generated|is-enabled:enabled-runtime) printf \'%s\\n\' "$STATE";; is-enabled:*) printf \'enabled\\n\';; *) return 0;; esac; }\nasterisk(){ [ "$STATE" != cli-failed ]; }\nverify_asterisk_service\n'
                result = self.run_shell(body)
                self.assertEqual(result.returncode == 0, expected == 0, result.stderr)

    def test_final_console_never_prints_passwords(self):
        result = self.run_shell("ADMIN_PASS='NeverPrintAdmin'; MYSQL_ROOT_PASS='NeverPrintDb'; REBOOT_AFTER=0; hostname(){ printf 127.0.0.1; }; finish\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('NeverPrintAdmin', result.stdout); self.assertNotIn('NeverPrintDb', result.stdout)
        finish = self.source.split('finish() {', 1)[1].split('\n# ----', 1)[0]
        self.assertNotIn('${ADMIN_PASS}', finish); self.assertNotIn('${MYSQL_ROOT_PASS}', finish)

    def test_framework_and_selfcheck_use_hard_verifiers(self):
        framework = self.source.split('stage_framework_init() {', 1)[1].split('\n# ----', 1)[0]
        selfcheck = self.source.split('stage_selfcheck() {', 1)[1].split('\nfinish()', 1)[0]
        self.assertIn('verify_mysql_authentication', framework)
        self.assertIn('verify_amp_admin_password', framework)
        self.assertIn('systemctl enable asterisk', framework)
        self.assertIn('verify_asterisk_service', selfcheck)
        self.assertNotIn('asterisk unit not active yet', selfcheck)

    def test_stage_record_failure_stops_before_completion_or_continuation(self):
        for failure in ['mkdir', 'touch', 'log']:
            with self.subTest(failure=failure):
                log = self.base / 'log'
                if log.exists(): log.unlink()
                result = self.run_shell('STATE_DIR=' + repr((self.base / 'state').as_posix()) + '\n'
                                        + failure + '(){ return 1; }\nmark_stage fixture\nprintf continued\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('continued', result.stdout)
                self.assertNotIn('STAGE-COMPLETE:', log.read_text() if log.exists() else '')
        result = self.run_shell('STATE_DIR=' + repr((self.base / 'state').as_posix()) + '\nmark_stage healthy\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.base / 'state/stages/healthy.done').is_file())

    def test_main_consumes_two_passwords_then_vendor_sees_eof_but_explicit_pipe_works(self):
        inherited = self.base / 'vendor-input'; explicit = self.base / 'explicit-input'
        body = 'STATE_DIR=' + repr((self.base / 'state').as_posix()) + '\n'
        # Every provisioning/host interaction is replaced; only the real main,
        # credential collector and writes inside this temporary fixture run.
        body += '''credential_input_is_tty(){ return 0; }
preflight(){ :; }; acquire_lock(){ :; }; write_install_source(){ :; }; initialize_workspace(){ :; }; verify_bundle(){ :; }
ensure_asterisk_identity(){ :; }
repair_platform_catalog(){ :; }
stage_cli_status(){ :; }
stage_packages1(){ :; }; stage_tls(){ :; }; stage_packages2(){ :; }; stage_post_base(){ :; }; stage_framework_init(){ :; }
stage_mytel_layer(){ :; }; stage_webrtc_dtls(){ :; }; stage_geoip(){ :; }; stage_myteldesk(){ :; }; stage_selfcheck(){ :; }; finish(){ :; }
'''
        body += 'stage_repos(){ if IFS= read -r answer; then printf inherited > ' + repr(inherited.as_posix()) + '; else printf EOF > ' + repr(inherited.as_posix()) + '; fi; }\n'
        body += 'fixture_vendor(){ IFS= read -r value && printf \'%s\' "$value" > ' + repr(explicit.as_posix()) + '; }\n'
        body += "stage_update(){ printf 'ExplicitPipeInput\\n' | fixture_vendor; }\nmain\n"
        result = self.run_shell(body, 'ChosenPanel!\nChosenDatabase=\nMustNotReachVendor\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load_values(), {'ADMIN_PASS': 'ChosenPanel!', 'MYSQL_ROOT_PASS': 'ChosenDatabase='})
        self.assertEqual(inherited.read_text(), 'EOF')
        self.assertEqual(explicit.read_text(), 'ExplicitPipeInput')


if __name__ == '__main__': unittest.main()
