"""Vendor-documented Remi HTTPS transport, with no network or package writes."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'installer/repair-repository-transport.py'


def vendor_fixture(section, family, newline='\n'):
    return newline.join([
        '# Vendor documented mirror alternatives; synthetic fixture',
        '[' + section + ']', 'name=Known repository $releasever - $basearch',
        '#baseurl=http://rpms.remirepo.net/enterprise/$releasever/' + family + '/$basearch/',
        '#mirrorlist=https://rpms.remirepo.net/enterprise/$releasever/' + family + '/$basearch/httpsmirror',
        'mirrorlist=http://cdn.remirepo.net/enterprise/$releasever/' + family + '/$basearch/mirror',
        'enabled=' + ('0' if family == 'remi' else '1'), 'gpgcheck=1', 'repo_gpgcheck=0',
        'gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-remi.el$releasever',
        '', '[' + section + '-unrelated-disabled]', 'enabled=0',
        'baseurl=http://rpms.remirepo.net/enterprise/$releasever/debug-remi/$basearch/', ''])


class RepositoryTransportTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'Missing repository transport repair')
        spec = importlib.util.spec_from_file_location('repository_transport', str(SCRIPT))
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'root'
        self.repos = self.root / 'etc/yum.repos.d'; self.repos.mkdir(parents=True)
        self.backups = Path(self.tmp.name) / 'backups'
        for filename, section, family in self.module.TARGETS:
            (self.repos / filename).write_bytes(vendor_fixture(section, family).encode())

    def test_only_three_observed_primary_transport_lines_change(self):
        for _filename, section, family in self.module.TARGETS:
            before = vendor_fixture(section, family)
            old = 'mirrorlist=http://cdn.remirepo.net/enterprise/$releasever/' + family + '/$basearch/mirror'
            new = 'mirrorlist=https://rpms.remirepo.net/enterprise/$releasever/' + family + '/$basearch/httpsmirror'
            after = self.module.transform_repository(before, section, family)
            self.assertEqual(after, before.replace('\n' + old + '\n', '\n' + new + '\n'))
            self.assertEqual(self.module.transform_repository(after, section, family), after)

    def test_crlf_comments_signing_options_and_disabled_sections_are_preserved(self):
        text = vendor_fixture('remi-safe', 'safe', '\r\n')
        after = self.module.transform_repository(text, 'remi-safe', 'safe')
        self.assertEqual(after.count('\r\n'), text.count('\r\n'))
        self.assertIn('gpgcheck=1\r\nrepo_gpgcheck=0\r\n', after)
        self.assertIn('[remi-safe-unrelated-disabled]\r\nenabled=0\r\nbaseurl=http://', after)

    def test_unknown_duplicate_partial_or_missing_vendor_alternative_is_refused(self):
        text = vendor_fixture('remi-safe', 'safe')
        for bad in [text.replace('cdn.remirepo.net', 'owner.example'),
                    text.replace('#mirrorlist=https:', '#owner-mirrorlist=https:'),
                    text + '\n[remi-safe]\n',
                    text.replace('enabled=1', 'baseurl=https://owner.example\nenabled=1'),
                    text.replace('mirrorlist=http:', 'mirrorlist=https:')]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.module.transform_repository(bad, 'remi-safe', 'safe')

    def test_all_inputs_are_validated_before_any_write_and_backup(self):
        victim = self.repos / 'remi-safe.repo'
        victim.write_bytes(b'unknown owner repository\n')
        before = {path.name: path.read_bytes() for path in self.repos.iterdir()}
        with self.assertRaises(ValueError): self.module.apply(self.root, self.backups)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.repos.iterdir()})
        self.assertFalse(self.backups.exists())

    def test_atomic_changes_keep_original_backups_and_are_idempotent(self):
        before = {path.name: path.read_bytes() for path in self.repos.iterdir()}
        for path in self.repos.iterdir(): path.chmod(0o644)
        self.assertEqual(len(self.module.apply(self.root, self.backups)), 3)
        saved = {path.read_bytes() for path in self.backups.iterdir()}
        self.assertEqual(saved, set(before.values()))
        self.assertEqual(self.module.apply(self.root, self.backups), [])
        self.assertEqual(len(list(self.backups.iterdir())), 3)
        if os.name == 'posix':
            self.assertEqual(self.backups.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in self.backups.iterdir()))
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o644 for path in self.repos.iterdir()))

    def test_apply_refuses_file_drift_after_plan(self):
        changes = self.module.plan(self.root)
        changed = self.repos / 'remi.repo'; changed.write_bytes(changed.read_bytes() + b'# owner edit\n')
        with self.assertRaises(ValueError): self.module.write_change(changes[0], self.backups)
        self.assertFalse(self.backups.exists())

    @unittest.skipIf(os.name != 'posix', 'Native POSIX symlink boundary')
    def test_symlinked_file_or_parent_is_refused(self):
        path = self.repos / 'remi.repo'; outside = Path(self.tmp.name) / 'outside'
        outside.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(outside)
        with self.assertRaises(ValueError): self.module.plan(self.root)
        path.unlink(); path.write_bytes(outside.read_bytes())
        moved = self.repos.with_name('moved'); self.repos.rename(moved); self.repos.symlink_to(moved)
        with self.assertRaises(ValueError): self.module.plan(self.root)

    def test_installer_repairs_transport_before_module_operations(self):
        source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        stage = source.split('stage_repos() {', 1)[1].split('\n# ----', 1)[0]
        # The local-only branch deliberately does not run remote transport repair.
        stage = stage[stage.index('local repo_src='):]
        self.assertLess(stage.index('remi-release-8.rpm'), stage.rindex('installer/repair-repository-transport.py'))
        self.assertLess(stage.rindex('installer/repair-repository-transport.py'), stage.index('repositories module reset'))
        self.assertIn('repository transport repair failed', stage)

    def test_optional_preflight_skips_absent_but_refuses_partial_repositories(self):
        for path in self.repos.iterdir(): path.unlink()
        self.assertEqual(self.module.plan(self.root, if_present=True), [])
        (self.repos / 'remi.repo').write_bytes(vendor_fixture('remi', 'remi').encode())
        with self.assertRaises(ValueError): self.module.plan(self.root, if_present=True)

    def test_resumed_stage_repairs_before_first_dnf_and_after_vendor_rpm(self):
        bash = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')
        definitions = Path(self.tmp.name) / 'definitions.sh'
        fixture_repos = self.root / 'repo-files'; fixture_repos.mkdir()
        definitions.write_text((ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8').rsplit('\nmain "$@"', 1)[0]
                               .replace('/etc/yum.repos.d', fixture_repos.as_posix()), encoding='utf-8')
        (self.root / 'installer/repos').mkdir(parents=True)
        (self.root / 'installer/repos/mytelpbx-base.repo.in').write_text('fixture')
        script = Path(self.tmp.name) / 'order.sh'
        body = 'source ' + repr(definitions.as_posix()) + '\nLOG=' + repr((self.root / 'log').as_posix()) + '\nBUNDLE_DIR=' + repr(self.root.as_posix()) + '\n'
        body += '''PY_BIN=repair_stub
READY=0
stage_done(){ return 1; }; step(){ :; }; cp(){ :; }; chmod(){ :; }; grep(){ return 0; }; mark_stage(){ :; }
repair_stub(){ printf 'repair %s\\n' "$*"; READY=1; }
dnf(){ [ "$READY" = 1 ] || return 28; printf 'dnf %s\\n' "$*"; }
run_logged(){ "$@" >>"$LOG" 2>&1; }
stage_repos
'''
        # Repair output is normally private; override only logging redirection
        # by inspecting that log alongside the public fake-command sequence.
        script.write_text(body, encoding='utf-8')
        result = subprocess.run([bash, '--noprofile', '--norc', str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        repairs = (self.root / 'log').read_text()
        self.assertIn('--if-present', repairs)
        self.assertEqual(repairs.count('repair '), 2)

    def test_bundle_explicitly_includes_repository_transport_helper(self):
        builder = (ROOT / 'scripts/build-installer-bundle.sh').read_text(encoding='utf-8')
        self.assertIn('copy_path "installer/repair-repository-transport.py"', builder)


if __name__ == '__main__': unittest.main()
