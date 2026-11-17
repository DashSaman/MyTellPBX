"""Exercise real installer wiring with fake clients, never a running PBX."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class NativeConsumerWiringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mytell-native-wiring-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bundle = self.base / 'bundle with spaces'
        for name in ['prepare-pjsip-websocket.py', 'pjsip-websocket-native.php',
                     'prepare-geoip-module.py', 'geoip-update.py', 'prepare-webrtc-dtls.py']:
            path = self.bundle / 'installer' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture client only\n')
        (self.bundle / 'modules/mytellpbxgeoip').mkdir(parents=True)
        self.events = self.base / 'events'
        self.definitions = self.base / 'definitions.sh'
        text = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.definitions.write_text(text.rsplit('\nmain "$@"', 1)[0], encoding='utf-8')

    def run_fixture(self, action, fail='', done=False):
        if self.events.exists():
            self.events.unlink()
        body = 'source ' + shlex.quote(self.definitions.as_posix()) + '\n'
        for name, value in [('LOG', self.base / 'log'), ('EVENTS', self.events),
                            ('STATE_DIR', self.base / 'state'), ('BUNDLE_DIR', self.bundle),
                            ('FIXTURE_ROOT', self.base / 'root')]:
            body += name + '=' + shlex.quote(value.as_posix()) + '\n'
        body += 'FAIL=' + shlex.quote(fail) + '\nDONE=' + str(int(done)) + '\n'
        body += '''PY_BIN=fixture_python
event(){ printf '%s' "$1" >> "$EVENTS"; shift; printf '\\t%s' "$@" >> "$EVENTS"; printf '\\n' >> "$EVENTS"; }
fixture_python(){
    case "$2" in
      */prepare-pjsip-websocket.py) event WEBSOCKET "$@"; [ "$FAIL" != "$3" ];;
      */geoip-update.py) event DATA "$@"; [ "$FAIL" != data ];;
      */prepare-geoip-module.py) event MODULE "$@"; [ "$FAIL" != module ];;
      */prepare-webrtc-dtls.py) event DTLS "$@"; [ "$FAIL" != dtls ];;
      *) return 99;;
    esac
}
run_logged(){
    case "$1" in
      */install_amp) event INITIALIZER "$@";;
      */retrieve_conf) event GENERATE "$@"; [ "$FAIL" != retrieve ];;
      fixture_python) "$@";;
      *) return 99;;
    esac
}
guard_empty_framework_bootstrap(){ event EMPTY_GUARD; }
normalize_framework_mysql(){ event NORMALIZE; }
framework_bootstrap_healthy(){ return 0; }
wait_asterisk_ready(){ :; } # Runtime probes are covered by the isolated readiness fixtures.
rm(){ event MARKER_REMOVE "$@"; }
stage_done(){ [ "$DONE" = 1 ]; }
mark_stage(){ event COMPLETE "$@"; }
'''
        body += action + '\nevent CONTINUED\n'
        script = self.base / 'run.sh'
        script.write_text(body, encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, encoding='utf-8', errors='replace', timeout=30)
        events = [line.rstrip('\t').split('\t') for line in self.events.read_text().splitlines()] if self.events.exists() else []
        return result, events

    def test_fresh_bootstrap_brackets_one_native_generation_with_owned_phases(self):
        result, events = self.run_fixture('bootstrap_empty_framework "$FIXTURE_ROOT"')
        self.assertEqual(result.returncode, 0, result.stderr)
        native = [e for e in events if e[0] in ['INITIALIZER', 'WEBSOCKET', 'GENERATE']]
        self.assertEqual([e[0] for e in native], ['INITIALIZER', 'WEBSOCKET', 'GENERATE', 'WEBSOCKET'])
        self.assertEqual([native[1][3], native[3][3]], ['prepare', 'activate'])
        self.assertEqual(native[1][1:3], ['-B', self.bundle.as_posix() + '/installer/prepare-pjsip-websocket.py'])
        self.assertEqual(native[1][4:6], ['--state-dir', (self.base / 'state').as_posix()])
        self.assertIn('--version', native[1])
        self.assertIn('--bundle-sha256', native[1])

    def test_each_failure_stops_before_the_next_phase_without_retry(self):
        for fail, expected in [('prepare', ['INITIALIZER', 'WEBSOCKET']),
                               ('retrieve', ['INITIALIZER', 'WEBSOCKET', 'GENERATE']),
                               ('activate', ['INITIALIZER', 'WEBSOCKET', 'GENERATE', 'WEBSOCKET'])]:
            with self.subTest(fail=fail):
                result, events = self.run_fixture('bootstrap_empty_framework "$FIXTURE_ROOT"', fail=fail)
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertEqual([e[0] for e in events if e[0] in ['INITIALIZER', 'WEBSOCKET', 'GENERATE']], expected)
                self.assertNotIn('CONTINUED', [e[0] for e in events])

    def test_missing_native_adapter_refuses_before_generation(self):
        (self.bundle / 'installer/pjsip-websocket-native.php').unlink()
        result, events = self.run_fixture('bootstrap_empty_framework "$FIXTURE_ROOT"')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('GENERATE', [e[0] for e in events])

    def test_geoip_data_and_consumer_both_finish_before_stage_completion(self):
        result, events = self.run_fixture('stage_geoip')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e[0] for e in events], ['DATA', 'MODULE', 'COMPLETE', 'CONTINUED'])
        self.assertEqual(events[1][1:], ['-B', self.bundle.as_posix() + '/installer/prepare-geoip-module.py'])

    def test_completed_data_stage_revalidates_the_current_kernel_consumer(self):
        result, events = self.run_fixture('stage_geoip', done=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e[0] for e in events], ['MODULE', 'COMPLETE', 'CONTINUED'])

    def test_geoip_failure_never_marks_completion_or_continues(self):
        for fail, expected in [('data', ['DATA']), ('module', ['DATA', 'MODULE'])]:
            with self.subTest(fail=fail):
                result, events = self.run_fixture('stage_geoip', fail=fail)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([e[0] for e in events], expected)

    def test_missing_geoip_consumer_refuses_before_data_or_module_execution(self):
        (self.bundle / 'installer/prepare-geoip-module.py').unlink()
        result, events = self.run_fixture('stage_geoip')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, [])

    def test_dtls_validation_runs_even_when_stage_was_already_completed(self):
        for done in (False, True):
            with self.subTest(done=done):
                result, events = self.run_fixture('stage_webrtc_dtls', done=done)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([e[0] for e in events], ['DTLS', 'COMPLETE', 'CONTINUED'])
                self.assertEqual(events[0][1:3], ['-B', self.bundle.as_posix() + '/installer/prepare-webrtc-dtls.py'])
                self.assertEqual(events[0][3:], ['--backup-root', (self.base / 'state/webrtc-dtls').as_posix()])
                self.assertEqual(events[1][1:], ['webrtc-dtls'])

    def test_invalid_dtls_does_not_mark_completion_or_continue(self):
        result, events = self.run_fixture('stage_webrtc_dtls', fail='dtls', done=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([e[0] for e in events], ['DTLS'])

    def test_missing_dtls_helper_refuses_without_invoking_other_consumers(self):
        (self.bundle / 'installer/prepare-webrtc-dtls.py').unlink()
        result, events = self.run_fixture('stage_webrtc_dtls')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, [])

    def dtls_main_action(self):
        return '''preflight(){ :; }; acquire_lock(){ :; }; write_install_source(){ :; }
initialize_workspace(){ :; }; verify_bundle(){ :; }; ensure_credentials(){ :; }
repair_platform_catalog(){ :; }; stage_repos(){ :; }; stage_native_platform(){ :; }; native_geoip(){ :; }; stage_update(){ :; }
stage_packages1(){ :; }; stage_tls(){ :; }; stage_packages2(){ :; }
stage_cli_status(){ :; }; stage_post_base(){ :; }
stage_framework_init(){ event FRAMEWORK; }; stage_mytel_layer(){ event MYTEL_LAYER; }
stage_geoip(){ :; }; stage_myteldesk(){ event DESK; }
stage_selfcheck(){ event SELF_CHECK; }; finish(){ event FINISH; }
main'''

    def test_real_main_prepares_dtls_after_framework_and_before_desk(self):
        result, events = self.run_fixture(self.dtls_main_action())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e[0] for e in events],
                         ['FRAMEWORK', 'MYTEL_LAYER', 'DTLS', 'COMPLETE', 'DESK', 'SELF_CHECK', 'FINISH', 'CONTINUED'])

    def test_real_main_dtls_failure_stops_before_desk_or_success(self):
        result, events = self.run_fixture(self.dtls_main_action(), fail='dtls')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([e[0] for e in events], ['FRAMEWORK', 'MYTEL_LAYER', 'DTLS'])


if __name__ == '__main__':
    unittest.main()
