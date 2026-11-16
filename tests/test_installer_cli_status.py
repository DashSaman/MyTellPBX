"""CLI-only vendor status repair; filesystem and PHP fixtures never provision."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'installer/patch-cli-status.py'
ORIGINAL = ROOT / 'tests/fixtures/issabel-cli-status-function.php'
PHP_FIXTURE = ROOT / 'tests/ui/cli-status.php'
GUARD = (b"    if (isset($GLOBALS['argv']) && is_array($GLOBALS['argv'])\n"
         b"        && in_array('--cli', $GLOBALS['argv'], true)) return;\n")


def fixture_after(before):
    anchor = b'function dialog_infobox($backtitle, $msgbox, $height, $width)\n{\n'
    return before.replace(anchor, anchor + GUARD, 1)


class CliStatusRepair(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'Missing exact vendor CLI status repair')
        spec = importlib.util.spec_from_file_location('cli_status_repair', str(SCRIPT))
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'root'; self.vendor = self.root / 'usr/bin/issabel-admin-passwords'
        self.vendor.parent.mkdir(parents=True)
        self.before = ORIGINAL.read_bytes(); self.after = fixture_after(self.before)
        self.vendor.write_bytes(self.before); self.vendor.chmod(0o755)
        self.backups = Path(self.tmp.name) / 'backups'
        # A public extracted fixture has its own exact whole-file pins. Native
        # review additionally exercises the immutable real vendor pins privately.
        self.module.ORIGINAL_SHA256 = hashlib.sha256(self.before).hexdigest()
        self.module.PATCHED_SHA256 = hashlib.sha256(self.after).hexdigest()

    def test_only_start_of_status_function_changes_and_repeat_is_idempotent(self):
        self.assertEqual(self.module.transform(self.before), self.after)
        self.assertEqual(self.module.transform(self.after), self.after)
        self.assertEqual(self.after.replace(GUARD, b'', 1), self.before)

    def test_actual_vendor_pins_are_not_the_public_fixture_pins(self):
        spec = importlib.util.spec_from_file_location('real_cli_status_pins', str(SCRIPT))
        original = importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
        self.assertEqual(original.ORIGINAL_SHA256, 'aa1a9bc962d5f34c57483d802b7f5e1e010133d2bf3245dc07b644387d9ef410')
        self.assertNotEqual(original.PATCHED_SHA256, original.ORIGINAL_SHA256)
        with self.assertRaises(ValueError): original.transform(self.before)

    def test_unrelated_edit_duplicate_or_changed_boundary_is_refused(self):
        for bad in [self.before + b'// owner edit\n', self.before + self.before,
                    self.before.replace(b'$height = (int)$height;', b'$height = 99;'),
                    self.after + b'// later owner edit\n']:
            with self.subTest(source=bad), self.assertRaises(ValueError): self.module.transform(bad)

    def test_hash_match_cannot_bypass_exact_function_anchor(self):
        bad = self.before.replace(b'function dialog_infobox(', b'function owner_infobox(')
        with patch.object(self.module, 'ORIGINAL_SHA256', hashlib.sha256(bad).hexdigest()):
            with self.assertRaises(ValueError): self.module.transform(bad)
        with patch.object(self.module, 'PATCHED_SHA256', 'f' * 64):
            with self.assertRaises(ValueError): self.module.transform(self.before)

    def test_backup_atomic_publication_and_repeat_preserve_mode_and_original(self):
        self.assertTrue(self.module.apply(self.root, self.backups))
        self.assertEqual(self.vendor.read_bytes(), self.after)
        saved = list(self.backups.iterdir()); self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_bytes(), self.before)
        self.assertFalse(self.module.apply(self.root, self.backups))
        self.assertEqual(len(list(self.backups.iterdir())), 1)
        if os.name == 'posix':
            self.assertEqual(self.vendor.stat().st_mode & 0o777, 0o755)
            self.assertEqual(saved[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.backups.stat().st_mode & 0o777, 0o700)

    def test_unknown_source_never_creates_backup_or_changes_file(self):
        bad = self.before + b'// unrecognized vendor version\n'; self.vendor.write_bytes(bad)
        with self.assertRaises(ValueError): self.module.apply(self.root, self.backups)
        self.assertEqual(self.vendor.read_bytes(), bad); self.assertFalse(self.backups.exists())

    def test_plan_then_edit_refuses_backup_and_overwrite(self):
        change = self.module.plan(self.root)
        self.vendor.write_bytes(self.before + b'// owner edit\n')
        with self.assertRaises(ValueError): self.module.write_change(change, self.backups)
        self.assertFalse(self.backups.exists())

    def test_conflicting_original_backup_is_preserved(self):
        self.backups.mkdir()
        target = self.backups / ('issabel-admin-passwords-' + self.module.ORIGINAL_SHA256 + '.original')
        target.write_bytes(b'owner data')
        with self.assertRaises(ValueError): self.module.apply(self.root, self.backups)
        self.assertEqual(self.vendor.read_bytes(), self.before); self.assertEqual(target.read_bytes(), b'owner data')

    def test_failed_replace_leaves_original_executable_and_saved_backup(self):
        with patch.object(self.module.os, 'replace', side_effect=OSError('fixture publication failed')):
            with self.assertRaises(OSError): self.module.apply(self.root, self.backups)
        self.assertEqual(self.vendor.read_bytes(), self.before)
        self.assertEqual([p.read_bytes() for p in self.backups.iterdir()], [self.before])
        self.assertFalse(list(self.vendor.parent.glob('.mytel-cli-status-*')))

    def test_known_after_pin_cannot_accept_a_missing_guard_boundary(self):
        with patch.object(self.module, 'PATCHED_SHA256', hashlib.sha256(self.before).hexdigest()):
            with self.assertRaises(ValueError): self.module.transform(self.before)

    def test_read_only_cli_check_then_apply_use_only_explicit_fixture_root(self):
        output = io.StringIO()
        arguments = ['patch-cli-status.py', '--root', str(self.root), '--backup-root', str(self.backups)]
        fixture_uid = os.geteuid() if hasattr(os, 'geteuid') else 0
        def privilege_probe():
            # Bypass only the CLI entry check; actual file ownership validation
            # still sees the real isolated fixture owner, including nobody.
            yield 0
            while True: yield fixture_uid
        with patch.object(self.module.os, 'geteuid', side_effect=privilege_probe().__next__, create=True), \
                patch('sys.argv', arguments + ['--check']), redirect_stdout(output):
            self.module.main()
        self.assertIn('would update', output.getvalue())
        self.assertEqual(self.vendor.read_bytes(), self.before); self.assertFalse(self.backups.exists())
        with patch.object(self.module.os, 'geteuid', side_effect=privilege_probe().__next__, create=True), \
                patch('sys.argv', arguments), redirect_stdout(output):
            self.module.main()
        self.assertEqual(self.vendor.read_bytes(), self.after)
        self.assertNotIn(self.before.decode(), output.getvalue())

    def test_cli_nonroot_refuses_before_inspecting_or_writing_vendor(self):
        with patch.object(self.module.os, 'geteuid', return_value=65534, create=True), \
                patch('sys.argv', ['patch-cli-status.py']), \
                patch.object(self.module, 'plan') as planned, \
                redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised: self.module.main()
        self.assertEqual(raised.exception.code, 2); planned.assert_not_called()
        self.assertEqual(self.vendor.read_bytes(), self.before); self.assertFalse(self.backups.exists())

    @unittest.skipIf(os.name != 'posix', 'Native POSIX path/ownership boundary')
    def test_symlink_parent_leaf_and_writable_source_are_refused(self):
        outside = Path(self.tmp.name) / 'outside'; outside.write_bytes(self.before)
        self.vendor.unlink(); self.vendor.symlink_to(outside)
        with self.assertRaises(ValueError): self.module.plan(self.root)
        self.vendor.unlink(); self.vendor.write_bytes(self.before); self.vendor.chmod(0o777)
        with self.assertRaises(ValueError): self.module.plan(self.root)
        self.vendor.chmod(0o755); moved = self.vendor.parent.with_name('moved')
        self.vendor.parent.rename(moved); self.vendor.parent.symlink_to(moved)
        with self.assertRaises(ValueError): self.module.plan(self.root)

    def test_native_php_executes_real_function_with_fake_system_only(self):
        php = shutil.which('php')
        if not php: self.skipTest('PHP unavailable; native PHP fixture is a required separate gate')
        candidate = Path(self.tmp.name) / 'candidate.php'; candidate.write_bytes(self.module.transform(self.before))
        result = subprocess.run([php, '-n', str(PHP_FIXTURE), str(candidate)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=30)
        text = result.stdout.decode('utf-8', 'replace')
        self.assertEqual(result.returncode, 0, text)
        self.assertEqual(sum(line.startswith('PASS ') for line in text.splitlines()), 10, text)
        self.assertNotIn('FAIL ', text)


if __name__ == '__main__': unittest.main()
