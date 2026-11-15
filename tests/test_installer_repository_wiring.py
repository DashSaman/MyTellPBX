"""Execute actual Bash repair/main orchestration with temporary paths and fake tools."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class RepositoryWiringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mytell-repo-wire-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repos = self.base / 'repo-files'; self.repos.mkdir()
        self.catalog = self.repos / 'mytelpbx-base.repo'
        self.events = self.base / 'events'
        self.bundle = self.base / 'bundle'
        (self.bundle / 'installer/repos').mkdir(parents=True)
        (self.bundle / 'installer/repos/mytelpbx-base.repo.in').write_bytes(b'fixture canonical copied before DNF\n')
        source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8').rsplit('\nmain "$@"', 1)[0]
        # Only the fixture's copy changes absolute host paths. Product helpers
        # are fake commands here; their actual semantics have separate tests.
        source = source.replace('/etc/yum.repos.d', self.repos.as_posix())
        source = source.replace('/etc/dnf/dnf.conf', (self.base / 'dnf.conf').as_posix())
        self.definitions = self.base / 'definitions.sh'; self.definitions.write_text(source, encoding='utf-8')

    def run_fixture(self, action, done=False, failure='', extra=''):
        body = 'source ' + repr(self.definitions.as_posix()) + '\n'
        for name, value in [('LOG', self.base / 'log'), ('STATE_DIR', self.base / 'state'),
                            ('BUNDLE_DIR', self.bundle), ('EVENTS', self.events)]:
            body += name + '=' + repr(value.as_posix()) + '\n'
        body += 'REPOS_DONE=' + ('1' if done else '0') + '\nFAIL_HELPER=' + repr(failure) + '\n'
        body += '''PY_BIN=fixture_helper
stage_done(){ [ "$1" = repos ] && [ "$REPOS_DONE" = 1 ]; }
step(){ :; }; mark_stage(){ :; }; grep(){ return 0; }
fixture_helper(){
    case "$*" in
      *repair-platform-repositories.py*) printf 'PLATFORM %s\\n' "$*" >> "$EVENTS"; [ "$FAIL_HELPER" != platform ];;
      *repair-repository-transport.py*) printf 'REMI %s\\n' "$*" >> "$EVENTS"; [ "$FAIL_HELPER" != remi ];;
      *) return 89;;
    esac
}
run_logged(){ "$@" >>"$LOG" 2>&1; }
dnf(){ printf 'DNF %s\\n' "$*" >> "$EVENTS"; }
run_dnf_logged(){ printf 'DNF %s\\n' "$*" >> "$EVENTS"; }
'''
        body += extra + '\n' + action + '\n'
        script = self.base / 'run.sh'; script.write_text(body, encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                                encoding='utf-8', errors='replace')
        events = self.events.read_text().splitlines() if self.events.exists() else []
        return result, events

    def main_stubs(self, packages2='printf "PACKAGES2\\n" >> "$EVENTS"'):
        return '''preflight(){ :; }; acquire_lock(){ :; }; write_install_source(){ :; }
initialize_workspace(){ :; }; verify_bundle(){ :; }; ensure_credentials(){ :; }
stage_update(){ printf 'UPDATE\\n' >> "$EVENTS"; }
stage_packages1(){ :; }; stage_tls(){ :; }
stage_cli_status(){ :; }
stage_packages2(){ ''' + packages2 + '''; }
stage_post_base(){ :; }; stage_framework_init(){ :; }; stage_mytel_layer(){ :; }
stage_geoip(){ :; }; stage_myteldesk(){ printf 'DESK\\n' >> "$EVENTS"; }
stage_selfcheck(){ :; }; finish(){ :; }
'''

    def test_initial_fresh_optional_check_needs_no_canonical_or_vendor_files(self):
        result, events = self.run_fixture('repair_platform_catalog')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].startswith('REMI '))
        self.assertIn('--if-present', events[0])
        self.assertFalse(self.catalog.exists())

    def test_done_repositories_with_missing_canonical_fail_before_any_package_command(self):
        result, events = self.run_fixture('main', done=True, extra=self.main_stubs())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('catalog is missing', result.stderr)
        self.assertFalse(any(value.startswith(('DNF ', 'UPDATE', 'DESK')) for value in events))

    def test_vendor_file_without_canonical_is_preserved_and_refused(self):
        vendor = self.repos / 'Issabel.repo'; vendor.write_bytes(b'unknown owner bytes\n')
        result, events = self.run_fixture('repair_platform_catalog')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(vendor.read_bytes(), b'unknown owner bytes\n')
        self.assertFalse(any(value.startswith(('PLATFORM ', 'DNF ')) for value in events))

    def test_existing_catalog_uses_optional_but_mandatory_mode_drops_if_present_flag(self):
        self.catalog.write_bytes(b'fixture')
        result, events = self.run_fixture('repair_platform_catalog\nrepair_platform_catalog mandatory')
        self.assertEqual(result.returncode, 0, result.stderr)
        platform = [value for value in events if value.startswith('PLATFORM ')]
        self.assertEqual(len(platform), 2)
        self.assertIn('--if-present', platform[0])
        self.assertNotIn('--if-present', platform[1])

    def test_mandatory_mode_cannot_skip_missing_canonical_on_fresh_state(self):
        result, events = self.run_fixture('repair_platform_catalog mandatory')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(value.startswith(('PLATFORM ', 'DNF ')) for value in events))

    def test_fresh_stage_copies_catalog_and_repairs_before_first_dnf(self):
        result, events = self.run_fixture('stage_repos')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.catalog.read_bytes(), b'fixture canonical copied before DNF\n')
        platform = next(index for index, value in enumerate(events) if value.startswith('PLATFORM '))
        dnf = next(index for index, value in enumerate(events) if value.startswith('DNF '))
        self.assertLess(platform, dnf)

    def test_resumed_main_checks_before_repos_done_and_mandatory_after_package_shortcut(self):
        self.catalog.write_bytes(b'fixture')
        result, events = self.run_fixture('main', done=True, extra=self.main_stubs())
        self.assertEqual(result.returncode, 0, result.stderr)
        platform = [(index, value) for index, value in enumerate(events) if value.startswith('PLATFORM ')]
        self.assertEqual(len(platform), 2)
        self.assertLess(platform[0][0], events.index('UPDATE'))
        self.assertIn('--if-present', platform[0][1])
        self.assertGreater(platform[1][0], events.index('PACKAGES2'))
        self.assertLess(platform[1][0], events.index('DESK'))
        self.assertNotIn('--if-present', platform[1][1])

    def test_either_helper_failure_stops_resumed_main_before_package_commands(self):
        self.catalog.write_bytes(b'fixture')
        for failure in ['remi', 'platform']:
            with self.subTest(failure=failure):
                if self.events.exists(): self.events.unlink()
                result, events = self.run_fixture('main', done=True, failure=failure, extra=self.main_stubs())
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(value.startswith(('DNF ', 'UPDATE', 'PACKAGES2', 'DESK')) for value in events))

    def test_package_stage_losing_catalog_fails_before_desk_even_with_repos_marker(self):
        self.catalog.write_bytes(b'fixture')
        second = 'printf "PACKAGES2\\n" >> "$EVENTS"; rm -- ' + repr(self.catalog.as_posix())
        result, events = self.run_fixture('main', done=True, extra=self.main_stubs(second))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PACKAGES2', events)
        self.assertNotIn('DESK', events)


if __name__ == '__main__':
    unittest.main()
