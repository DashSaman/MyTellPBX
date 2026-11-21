"""Native bootstrap private-workspace lifecycle; no PBX, network or OS mutations."""
import hashlib
import os
import shlex
import shutil
import unittest
from pathlib import Path

from native_bootstrap_fixture import BASH, BootstrapFixture


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class InstallerWorkspaceTests(BootstrapFixture, unittest.TestCase):
    def main_fixture(self, child_status=0, lock_probe=False, repo_status=0, check_only=False):
        # Keep main's real flock, umask and mktemp operations inside this fixture.
        # Preflight and native execution are replaced; no target provisioning runs.
        path = self.base / 'main-definitions.sh'
        lock = self.base / 'install.lock'
        source = self.source.replace('/var/run/mytelpbx-native-install.lock', lock.as_posix())
        source = source.replace('/var/tmp/mytelpbx-native.XXXXXXXX',
                                (self.base / 'mytelpbx-native.XXXXXXXX').as_posix())
        path.write_text(source, encoding='utf-8')
        probe = ('flock -n ' + shlex.quote(lock.as_posix())
                 + " -c true && { printf 'lock-unheld\\n'; return 99; }\n") if lock_probe else ''
        # Git Bash has no flock. Only model the unrelated successful lock on
        # Windows; the real lock contract below runs with native POSIX flock.
        body = ('flock(){ :; }\n' if os.name == 'nt' else '') + '''
preflight(){ :; }
download_bundle(){ printf 'fixture-private-log\\n' > "$MYTEL_NATIVE_WORK/netinstall.log"; }
extract_bundle(){
    MYTEL_BUNDLE_ROOT="$MYTEL_NATIVE_WORK/payload"
    local native="$MYTEL_BUNDLE_ROOT/installer/vendor-native"
    mkdir -p "$native" || return 1
    printf '%s\\n' 'mytel_terminal_banner(){ :; }' > "$native/terminal-ui.sh"
    printf '%s\\n' 'mytel_collect_online_passwords(){ printf "%s\\n" Fixture-DB Fixture-Panel pjsip; }' \
        > "$native/online-credentials.sh"
}
bash(){
  if [[ "${2:-}" == --check-repositories ]]; then
    printf 'REPOSITORIES_CHECKED'
    return ''' + str(repo_status) + '''
  fi
  local db admin driver
  IFS= read -r -u 3 db && IFS= read -r -u 3 admin && IFS= read -r -u 3 driver || return 98
  [[ "$db" == Fixture-DB && "$admin" == Fixture-Panel && "$driver" == pjsip ]] || return 98
''' + probe + '''printf 'WORK=%s\\n' "$MYTEL_NATIVE_WORK" >> "$EVENTS"
return ''' + str(child_status) + '''
}
main ''' + ('--check-repositories' if check_only else '') + '\n'
        result = self.shell(body, {'MYTEL_MEDIA_ROOT': ''}, path)
        return result

    def test_initializer_always_uses_a_fresh_workspace_and_preserves_inherited_path(self):
        marker = self.work / 'owner'
        marker.write_bytes(b'preserve')
        for _ in range(2):
            result = self.main_fixture()
            self.assertEqual(result.returncode, 0, result.stderr)
        workspaces = [Path(line[5:]) for line in self.events.read_text().splitlines()]
        self.assertEqual(len(set(workspaces)), 2)
        self.assertNotIn(self.work, workspaces)
        for work in workspaces:
            self.assertEqual(work.parent, self.base)
            self.assertEqual((work / 'netinstall.log').read_bytes(), b'fixture-private-log\n')
        self.assertEqual(marker.read_bytes(), b'preserve')
        self.assertEqual(list(self.work.iterdir()), [marker])

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX directory and file modes')
    def test_initializer_private_umask_protects_logs_and_workspace(self):
        result = self.main_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        workspace = Path(self.events.read_text().strip()[5:])
        self.assertEqual(workspace.stat().st_mode & 0o777, 0o700)
        self.assertEqual((workspace / 'netinstall.log').stat().st_mode & 0o777, 0o600)
        self.assertNotIn(b'fixture-private-log', result.stdout + result.stderr)

    @unittest.skipUnless(os.name == 'posix' and shutil.which('flock'), 'Native POSIX flock required')
    def test_native_child_keeps_lock_until_return(self):
        result = self.main_fixture(lock_probe=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b'lock-unheld', result.stdout)
        self.assertTrue(self.events.exists())

    def test_native_failure_keeps_private_log_and_propagates_before_success(self):
        result = self.main_fixture(child_status=37)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'status 37', result.stderr)
        workspace = Path(self.events.read_text().strip()[5:])
        self.assertEqual((workspace / 'netinstall.log').read_bytes(), b'fixture-private-log\n')
        self.assertNotIn(b'fixture-private-log', result.stdout + result.stderr)

    def test_local_bundle_is_copied_only_into_private_workspace_without_modifying_source(self):
        self.make_archive()
        original = self.archive.read_bytes()
        result = self.shell('download_bundle\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.work / 'bundle.tgz').read_bytes(), original)
        self.assertEqual(self.archive.read_bytes(), original)
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         hashlib.sha256((self.work / 'bundle.tgz').read_bytes()).hexdigest())

    def test_failed_repository_check_stops_before_installation(self):
        result = self.main_fixture(repo_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'REPOSITORIES_CHECKED', result.stdout)
        self.assertFalse(self.events.exists())

    def test_discovery_mode_performs_only_the_repository_check(self):
        result = self.main_fixture(check_only=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'REPOSITORIES_CHECKED', result.stdout)
        self.assertFalse(self.events.exists())

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX source-symlink boundary')
    def test_symlinked_local_bundle_is_refused_without_copy_or_source_change(self):
        self.make_archive()
        original = self.archive.read_bytes()
        link = self.base / 'linked.tgz'
        link.symlink_to(self.archive)
        result = self.shell('download_bundle\n', {'MYTELL_BUNDLE_FILE': link})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.work / 'bundle.tgz').exists())
        self.assertEqual(self.archive.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
