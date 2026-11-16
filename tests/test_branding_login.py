"""Native banner presentation and bounded, reversible filesystem contract.

Official fixtures are data. Never source motd.sh: its unrelated DAHDI branch
can restart telephony. Only static echo statements are rendered in a subprocess.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / 'tests/fixtures/branding'
PATCHER = REPO / 'admin-theme/patch-login-branding.py'
MOTD = (FIXTURE / 'upstream-motd.sh').read_text(encoding='utf-8')
PROFILE = (FIXTURE / 'upstream-login-info.sh').read_text(encoding='utf-8')
MODULE = None
if PATCHER.exists():
    spec = importlib.util.spec_from_file_location('login_branding', str(PATCHER))
    MODULE = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(MODULE)


def transform(text):
    # The current installer has no OS-login branding step. Its real baseline
    # is the unchanged vendor banner, rather than an artificial import error.
    return MODULE.transform_motd(text) if MODULE else text


def static_banner(text):
    return '\n'.join(line for line in text.splitlines()
                     if line.startswith('echo ') and '$' not in line) + '\n'


class LoginBrandingTests(unittest.TestCase):
    def require_patcher(self):
        if MODULE is None:
            self.skipTest('Bounded writer is introduced after the executed banner RED')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mytel-branding-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'root'
        self.motd = self.root / 'usr/local/sbin/motd.sh'
        self.profile = self.root / 'etc/profile.d/login-info.sh'
        self.motd.parent.mkdir(parents=True)
        self.profile.parent.mkdir(parents=True)
        self.motd.write_bytes(MOTD.encode('utf-8'))
        self.profile.write_bytes(PROFILE.encode('utf-8'))
        self.backups = Path(self.temp.name) / 'private-backups'

    def test_official_fixtures_are_exact_pinned_source(self):
        self.assertEqual(hashlib.sha256((FIXTURE / 'upstream-motd.sh').read_bytes()).hexdigest(),
                         'beedb52cbbe09c482c6a3d3cd77a588b7b25e876e8b40aff8ba4644510578c64')
        self.assertEqual(hashlib.sha256((FIXTURE / 'upstream-login-info.sh').read_bytes()).hexdigest(),
                         '5da3d50d0684d296d54d2b8640dc7400869559d99de45438b6850f39802c9f9f')

    def test_login_banner_uses_our_product_and_support(self):
        banner = static_banner(transform(MOTD))
        self.assertNotRegex(banner, r'(?i)issabel')
        self.assertIn('MytelPBX', banner)
        self.assertIn('https://mytel.one', banner)
        self.assertNotIn('patreon.com', banner)

    def test_real_shell_renders_no_upstream_product_promotion(self):
        bash = shutil.which('bash')
        if os.name == 'nt':
            candidate = Path('C:/Program Files/Git/bin/bash.exe')
            bash = str(candidate) if candidate.exists() else None
        if not bash:
            self.skipTest('Native Bash is unavailable')
        result = subprocess.run([bash, '--noprofile', '--norc', '-s'],
                                input=static_banner(transform(MOTD)), universal_newlines=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotRegex(result.stdout, r'(?i)issabel')
        self.assertIn('MytelPBX', result.stdout)
        self.assertIn('https://mytel.one', result.stdout)

    def test_only_known_echo_lines_change_and_legal_text_survives(self):
        self.require_patcher()
        retained = ('\n# Copyright Issabel Foundation; GPL-2.0\n'
                    'echo "Dependency package: issabel-framework; config /etc/issabel.conf"\n'
                    'echo "License source: https://github.com/IssabelFoundation/framework"\n')
        original = MOTD + retained
        after = transform(original)
        self.assertTrue(after.endswith(retained))
        before_other = [s for s in original.splitlines() if s not in MODULE.REPLACEMENTS]
        after_other = [s for s in after.splitlines() if s not in MODULE.REPLACEMENTS.values()]
        self.assertEqual(before_other, after_other)
        self.assertEqual(transform(after), after)

    def test_drift_partial_or_duplicate_banner_is_refused(self):
        self.require_patcher()
        first, replacement = next(iter(MODULE.REPLACEMENTS.items()))
        for source in (MOTD.replace(first, first + ' owner change'),
                       MOTD.replace(first, replacement), MOTD + first + '\n'):
            with self.subTest(source=source[-90:]), self.assertRaises(ValueError):
                transform(source)

    def test_previous_owned_spelling_upgrades_without_rewriting_owner_text(self):
        self.require_patcher()
        retained = '\n# Owner label: MyTellPBX; retain this operator text\n'
        previous = transform(MOTD).replace('MytelPBX', 'MyTellPBX') + retained
        after = transform(previous)
        self.assertIn('MytelPBX', static_banner(after))
        self.assertNotIn('MyTellPBX', static_banner(after))
        self.assertTrue(after.endswith(retained))
        self.assertEqual(transform(after), after)
        edited = previous.replace('MyTellPBX support:', 'Owner support:')
        with self.assertRaises(ValueError):
            transform(edited)

    def test_missing_profile_or_changed_invocation_refuses_all_writes(self):
        self.require_patcher()
        before = self.motd.read_bytes()
        self.profile.write_text(PROFILE.replace('/usr/local/sbin/motd.sh', '/opt/owner/motd.sh'), encoding='utf-8')
        with self.assertRaises(ValueError):
            MODULE.apply(self.root, self.backups)
        self.assertEqual(self.motd.read_bytes(), before)
        self.assertFalse(self.backups.exists())

    def test_writer_changes_only_motd_with_private_original_backup_and_is_idempotent(self):
        self.require_patcher()
        before = self.motd.read_bytes()
        profile_before = self.profile.read_bytes()
        issue = self.root / 'etc/issue'
        issue.write_bytes(b'Rocky Linux 8.10; operator notice\n')
        self.motd.chmod(0o755)
        self.assertEqual(MODULE.apply(self.root, self.backups), [self.motd])
        self.assertEqual(self.profile.read_bytes(), profile_before)
        self.assertEqual(issue.read_bytes(), b'Rocky Linux 8.10; operator notice\n')
        saved = list(self.backups.iterdir())
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_bytes(), before)
        if os.name == 'posix':
            self.assertEqual(self.motd.stat().st_mode & 0o777, 0o755)
            self.assertEqual(self.backups.stat().st_mode & 0o777, 0o700)
            self.assertEqual(saved[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(MODULE.apply(self.root, self.backups), [])
        self.assertEqual(list(self.backups.iterdir()), saved)

    def test_changed_source_plan_and_symlinks_are_refused(self):
        self.require_patcher()
        plan = MODULE.plan(self.root)
        self.motd.write_text(MOTD + '# owner changed after validation\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            MODULE.write_change(plan[0], self.backups)
        self.assertFalse(self.backups.exists())
        if os.name != 'posix':
            return  # Windows symlink privilege is not assumed.
        self.motd.unlink()
        outside = Path(self.temp.name) / 'outside'
        outside.write_text(MOTD, encoding='utf-8')
        self.motd.symlink_to(outside)
        with self.assertRaises(ValueError):
            MODULE.apply(self.root, self.backups)
        self.assertEqual(outside.read_text(encoding='utf-8'), MOTD)


if __name__ == '__main__':
    unittest.main()
