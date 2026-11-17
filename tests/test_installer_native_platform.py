"""Real Bash native prerequisites with only disposable config and fake clients."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class NativePlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.events = self.base / 'events'
        self.config = self.base / 'selinux.conf'; self.config.write_text('# retained\nSELINUX=enforcing\nSELINUXTYPE=targeted\n')
        self.definitions = self.base / 'definitions.sh'
        source = (REPO / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.definitions.write_text(source.rsplit('\nmain "$@"', 1)[0], encoding='utf-8')

    def run_fixture(self, action='stage_native_platform', mode='Enforcing', failure='', offline=True):
        q = shlex.quote
        settings = {'LOG': self.base / 'log', 'EVENTS': self.events, 'CONFIG': self.config,
                    'STATE_DIR': self.base / 'state', 'STAGES': self.base / 'stages',
                    'BUNDLE_DIR': self.base / 'bundle', 'MEDIA_ROOT': self.base / 'media' if offline else '',
                    'MEDIA_REPOS_DIR': self.base / 'media-repos', 'MODE': mode, 'FAILURE': failure}
        body = 'source ' + q(self.definitions.as_posix()) + '\n'
        body += '\n'.join(k + '=' + q(str(v).replace('\\', '/')) for k, v in settings.items()) + '\n'
        body += '''
event(){ printf '%s' "$1" >>"$EVENTS"; shift; printf '\\t%s' "$@" >>"$EVENTS"; printf '\\n' >>"$EVENTS"; }
step(){ :; }; say(){ :; }; warn(){ :; }; sleep(){ :; }
stage_done(){ [ -f "$STAGES/$1" ]; }
mark_stage(){ mkdir -p "$STAGES"; touch "$STAGES/$1"; event MARK "$1"; }
native_start(){ :; } # Interlock is exercised by focused native-start tests.
offline_vendor_geoip(){ :; } # Bridge phases have separate real-main wiring tests.
ensure_asterisk_identity(){ event IDENTITY; }
getenforce(){ event GETENFORCE; [ "$FAILURE" != read ] || return 31; printf '%s\\n' "$MODE"; }
setenforce(){ event SETENFORCE "$@"; [ "$FAILURE" != runtime ]; }
sed(){
 event CONFIG "$@"; [ "$FAILURE" != config ] || return 32
 local args=() a; for a in "$@"; do [ "$a" != /etc/selinux/config ] || a="$CONFIG"; args+=("$a"); done
 command sed "${args[@]}"
}
grep(){
 local args=() a; for a in "$@"; do [ "$a" != /etc/selinux/config ] || a="$CONFIG"; args+=("$a"); done
 command grep "${args[@]}"
}
dnf(){ event DNF "$@"; [ "$FAILURE" != package ]; }
run_logged(){ "$@"; }
PY_BIN=fixture_python
fixture_python(){ case "$*" in *--check-log*) return 0;; *dnf-progress.py*) cat;; *) return 91;; esac; }
systemctl(){ event FORBIDDEN_SERVICE; return 92; }
mysql(){ event FORBIDDEN_DATABASE; return 93; }
curl(){ event FORBIDDEN_NETWORK; return 94; }
preflight(){ :; }; acquire_lock(){ :; }; write_install_source(){ :; }; initialize_workspace(){ :; }
verify_bundle(){ :; }; initialize_media(){ :; }; ensure_credentials(){ :; }; repair_platform_catalog(){ :; }
stage_repos(){ event REPOS; }; stage_update(){ event UPDATE; }; stage_packages1(){ event PACKAGES1; }
stage_tls(){ :; }; stage_packages2(){ :; }; stage_cli_status(){ :; }; stage_post_base(){ :; }
stage_framework_init(){ :; }; stage_mytel_layer(){ :; }; stage_webrtc_dtls(){ :; }; stage_geoip(){ :; }
stage_myteldesk(){ :; }; stage_selfcheck(){ :; }; finish(){ :; }
'''
        script = self.base / 'run.sh'; script.write_text(body + action + '\n', encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace', timeout=30)
        events = [line.rstrip('\t').split('\t') for line in self.events.read_text().splitlines()] if self.events.exists() else []
        self.assertFalse(any(e[0].startswith('FORBIDDEN') for e in events), events)
        return result, events

    def test_real_main_prepares_native_platform_between_repos_and_update(self):
        result, events = self.run_fixture('main')
        self.assertEqual(result.returncode, 0, result.stderr)
        names = [e[0] for e in events]
        self.assertIn('IDENTITY', names, 'Native prerequisites were never prepared')
        self.assertLess(names.index('REPOS'), names.index('IDENTITY'))
        self.assertLess(names.index('IDENTITY'), names.index('SETENFORCE'))
        self.assertLess(names.index('SETENFORCE'), names.index('DNF'))
        self.assertLess(names.index('DNF'), names.index('UPDATE'))
        self.assertLess(names.index('UPDATE'), names.index('PACKAGES1'))

    def test_same_documented_policy_and_only_signed_local_helpers_transaction(self):
        result, events = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e for e in events if e[0] == 'SETENFORCE'], [['SETENFORCE', '0']])
        self.assertEqual(self.config.read_text(), '# retained\nSELINUX=disabled\nSELINUXTYPE=targeted\n')
        calls = [e for e in events if e[0] == 'DNF']; self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-3:], ['-y', 'install', 'issabel-config_helpers'])
        self.assertIn('--setopt=gpgcheck=1', calls[0]); self.assertTrue(any('reposdir=' in a for a in calls[0]))
        self.assertEqual(events[-1], ['MARK', 'native-platform'])

    def test_owned_marker_avoids_repeated_policy_or_package_actions(self):
        result, events = self.run_fixture('stage_native_platform; stage_native_platform')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(e[0] == 'IDENTITY' for e in events), 1)
        self.assertEqual(sum(e[0] == 'DNF' for e in events), 1)
        self.assertEqual(sum(e[0] == 'CONFIG' for e in events), 1)

    def test_already_permissive_or_disabled_does_not_call_setenforce(self):
        for mode in ['Permissive', 'Disabled']:
            with self.subTest(mode=mode):
                if self.events.exists(): self.events.unlink()
                marker = self.base / 'stages/native-platform'
                if marker.exists(): marker.unlink()
                result, events = self.run_fixture(mode=mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(any(e[0] == 'SETENFORCE' for e in events))
                self.assertTrue(any(e[0] == 'DNF' for e in events))

    def test_unknown_or_failed_runtime_policy_stops_before_packages(self):
        for mode, failure in [('unknown', ''), ('Enforcing', 'read'), ('Enforcing', 'runtime')]:
            with self.subTest(mode=mode, failure=failure):
                if self.events.exists(): self.events.unlink()
                result, events = self.run_fixture(mode=mode, failure=failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(e[0] in ['CONFIG', 'DNF', 'MARK'] for e in events))

    def test_failed_persistent_policy_stops_before_helper_install(self):
        result, events = self.run_fixture(failure='config')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(e[0] in ['DNF', 'MARK'] for e in events))

    def test_failed_helper_package_does_not_mark_platform_complete(self):
        result, events = self.run_fixture(failure='package')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum(e[0] == 'DNF' for e in events), 5)
        self.assertFalse(any(e[0] == 'MARK' for e in events))

    def test_online_helpers_transaction_keeps_normal_dnf_arguments(self):
        result, events = self.run_fixture(offline=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e for e in events if e[0] == 'DNF'], [['DNF', '-y', 'install', 'issabel-config_helpers']])


if __name__ == '__main__': unittest.main()
