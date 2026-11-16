"""Run the actual CLI repair stage/main with fake clients and temporary paths."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class CliStatusWiringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mytell-cli-wiring-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.events = self.base / 'events'
        self.bundle = self.base / 'bundle with spaces'
        self.source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.definitions = self.base / 'definitions.sh'
        self.definitions.write_bytes((self.source.rsplit('\nmain "$@"', 1)[0] + '\n').encode('utf-8'))

    def run_fixture(self, action, helper_failure=False, restore_failure=False, restore_available=True, done=False):
        body = 'source ' + shlex.quote(self.definitions.as_posix()) + '\n'
        for name, value in [('LOG', self.base / 'log'), ('STATE_DIR', self.base / 'state'),
                            ('BUNDLE_DIR', self.bundle), ('EVENTS', self.events)]:
            body += name + '=' + shlex.quote(value.as_posix()) + '\n'
        body += 'HELPER_FAILURE=' + str(int(helper_failure)) + '\n'
        body += 'RESTORE_FAILURE=' + str(int(restore_failure)) + '\n'
        body += 'RESTORE_AVAILABLE=' + str(int(restore_available)) + '\n'
        body += 'DONE=' + str(int(done)) + '\n'
        body += '''PY_BIN=fixture_python
event(){ printf '%s' "$1" >> "$EVENTS"; shift; printf '\\t%s' "$@" >> "$EVENTS"; printf '\\n' >> "$EVENTS"; }
fixture_python(){ event HELPER "$@"; [ "$HELPER_FAILURE" = 0 ]; }
restorecon(){ event RESTORECON "$@"; [ "$RESTORE_FAILURE" = 0 ]; }
command(){
    if [ "${1:-}" = -v ] && [ "${2:-}" = restorecon ]; then
        [ "$RESTORE_AVAILABLE" = 1 ]; return
    fi
    builtin command "$@"
}
stage_done(){ event STAGE_DONE "$@"; [ "$DONE" = 1 ]; }
preflight(){ :; }; acquire_lock(){ :; }; write_install_source(){ :; }
initialize_workspace(){ :; }; verify_bundle(){ :; }; ensure_credentials(){ :; }
repair_platform_catalog(){ event CATALOG "$@"; }
stage_repos(){ :; }; stage_update(){ :; }; stage_packages1(){ :; }; stage_tls(){ :; }
stage_packages2(){ event PACKAGES2 "$DONE"; }
stage_post_base(){ event POST_BASE; }; stage_framework_init(){ event FRAMEWORK; }
stage_mytel_layer(){ :; }; stage_webrtc_dtls(){ :; }; stage_geoip(){ :; }; stage_myteldesk(){ :; }
stage_selfcheck(){ :; }; finish(){ event FINISH; }
'''
        body += action + '\n'
        script = self.base / 'run.sh'
        script.write_bytes(body.encode('utf-8'))
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                                encoding='utf-8', errors='replace', timeout=30)
        events = [line.rstrip('\t').split('\t') for line in self.events.read_text(encoding='utf-8').splitlines()] if self.events.exists() else []
        return result, events

    def helper_arguments(self):
        return ['HELPER', '-B', self.bundle.as_posix() + '/installer/patch-cli-status.py']

    def test_fresh_and_resumed_stage_always_revalidate_exact_source_with_the_same_arguments(self):
        for done in [False, True]:
            with self.subTest(done=done):
                if self.events.exists(): self.events.unlink()
                result, events = self.run_fixture('stage_cli_status\nstage_cli_status\nevent CONTINUED', done=done)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(events, [self.helper_arguments(), ['RESTORECON', '/usr/bin/issabel-admin-passwords'],
                                          self.helper_arguments(), ['RESTORECON', '/usr/bin/issabel-admin-passwords'], ['CONTINUED']])

    def test_failed_helper_is_fatal_before_restorecon_or_continuation(self):
        result, events = self.run_fixture('stage_cli_status\nevent CONTINUED', helper_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, [self.helper_arguments()])
        self.assertIn('CLI status repair refused', result.stderr)

    def test_failed_security_context_repair_is_fatal_after_the_helper(self):
        result, events = self.run_fixture('stage_cli_status\nevent CONTINUED', restore_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, [self.helper_arguments(), ['RESTORECON', '/usr/bin/issabel-admin-passwords']])
        self.assertIn('security context could not be restored', result.stderr)

    def test_absent_restorecon_skips_only_that_optional_client(self):
        result, events = self.run_fixture('stage_cli_status\nevent CONTINUED', restore_available=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, [self.helper_arguments(), ['CONTINUED']])

    def test_real_main_orders_the_repair_after_packages_and_mandatory_catalog_before_framework(self):
        for done in [False, True]:
            with self.subTest(done=done):
                if self.events.exists(): self.events.unlink()
                result, events = self.run_fixture('main', done=done)
                self.assertEqual(result.returncode, 0, result.stderr)
                names = [event[0] for event in events]
                self.assertEqual(names.count('HELPER'), 1)
                helper = names.index('HELPER')
                self.assertLess(names.index('PACKAGES2'), events.index(['CATALOG', 'mandatory']))
                self.assertLess(events.index(['CATALOG', 'mandatory']), helper)
                self.assertLess(helper, names.index('RESTORECON'))
                self.assertLess(names.index('RESTORECON'), names.index('POST_BASE'))
                self.assertLess(names.index('POST_BASE'), names.index('FRAMEWORK'))
                self.assertEqual(events[helper], self.helper_arguments())

    def test_real_main_cannot_initialize_framework_after_either_client_failure(self):
        for helper, restore in [(True, False), (False, True)]:
            with self.subTest(helper=helper, restore=restore):
                if self.events.exists(): self.events.unlink()
                result, events = self.run_fixture('main', helper_failure=helper, restore_failure=restore)
                self.assertNotEqual(result.returncode, 0)
                names = [event[0] for event in events]
                self.assertIn('PACKAGES2', names)
                self.assertIn('HELPER', names)
                self.assertNotIn('POST_BASE', names)
                self.assertNotIn('FRAMEWORK', names)
                self.assertNotIn('FINISH', names)
                self.assertEqual('RESTORECON' in names, restore)

    def test_release_builder_contains_the_tracked_helper_exactly_once(self):
        builder = (ROOT / 'scripts/build-installer-bundle.sh').read_text(encoding='utf-8')
        self.assertEqual(builder.count('copy_path "installer/patch-cli-status.py"'), 1)


if __name__ == '__main__':
    unittest.main()
