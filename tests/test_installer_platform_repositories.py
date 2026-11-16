"""Retire only observed RPM duplicates; no DNF/network/host configuration writes."""
import configparser
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'installer/repair-platform-repositories.py'
FIXTURES = ROOT / 'tests/fixtures/platform-repositories'


class PlatformRepositoryTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('platform_repositories', str(HELPER))
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'root'
        self.repos = self.root / 'etc/yum.repos.d'
        self.repos.mkdir(parents=True)
        self.backup = Path(self.temp.name) / 'backup'
        for name in ['Issabel.repo', 'Issabel5.repo', 'commercial-addons.repo']:
            shutil.copyfile(str(FIXTURES / name), str(self.repos / name))
        self.canonical = self.repos / 'mytelpbx-base.repo'
        self.canonical.write_bytes((ROOT / 'installer/repos/mytelpbx-base.repo.in').read_bytes())
        self.unrelated = self.repos / 'owner.repo'
        self.unrelated.write_bytes(b'[owner-repo]\nname=Owner retained\nenabled=0\ngpgcheck=1\nbaseurl=https://example.test/rpms\n')

    def apply(self, **kwargs):
        return self.module.apply(self.root, self.backup, **kwargs)

    def snapshot(self):
        return {path.name: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode) for path in self.repos.iterdir()}

    def test_three_exact_rpm_duplicates_are_backed_up_and_only_nine_canonical_ids_remain(self):
        canonical_before = self.canonical.read_bytes()
        untouched = (self.unrelated.read_bytes(), self.unrelated.stat().st_mtime_ns)
        originals = {(self.repos / name).read_bytes() for name in self.module.VENDOR_HASHES}
        changed = self.apply()
        self.assertEqual({path.name for path in changed}, set(self.module.VENDOR_HASHES))
        self.assertEqual({path.read_bytes() for path in self.backup.iterdir()}, originals)
        self.assertEqual(self.canonical.read_bytes(), canonical_before)
        self.assertEqual((self.unrelated.read_bytes(), self.unrelated.stat().st_mtime_ns), untouched)
        found = []
        for path in self.repos.glob('*.repo'):
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(path.read_text())
            found.extend(parser.sections())
        self.assertEqual(len(found), len(set(found)))
        self.assertEqual(len([value for value in found if value != 'owner-repo']), 9)
        self.assertNotIn(b'mirrorlist=http:', b''.join(path.read_bytes() for path in self.repos.glob('*.repo')))

    def test_public_fixtures_match_observed_rpm_hashes_and_repair_is_idempotent(self):
        for name, expected in self.module.VENDOR_HASHES.items():
            self.assertEqual(hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest(), expected)
        self.apply()
        before = self.snapshot()
        self.assertEqual(self.apply(), [])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(list(self.backup.iterdir())), 3)

    def test_unknown_vendor_edit_or_canonical_edit_is_refused_before_any_backup_or_write(self):
        for path in [self.repos / 'Issabel5.repo', self.canonical]:
            original = path.read_bytes()
            path.write_bytes(original + b'# owner edit\n')
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.apply()
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(self.backup.exists())
            path.write_bytes(original)

    def test_unknown_duplicate_repo_id_is_refused_without_modifying_other_files(self):
        self.unrelated.write_bytes(b'[issabel-cinco]\nenabled=0\nbaseurl=https://owner.test\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.backup.exists())

    def test_missing_canonical_or_required_vendor_file_is_refused(self):
        self.canonical.unlink()
        with self.assertRaises(ValueError):
            self.apply()
        self.canonical.write_bytes((ROOT / 'installer/repos/mytelpbx-base.repo.in').read_bytes())
        (self.repos / 'Issabel5.repo').unlink()
        with self.assertRaises(ValueError):
            self.apply()
        self.assertFalse(self.backup.exists())

    def test_optional_resume_repairs_only_present_known_vendor_files(self):
        (self.repos / 'commercial-addons.repo').unlink()
        changed = self.apply(if_present=True)
        self.assertEqual({path.name for path in changed}, {'Issabel.repo', 'Issabel5.repo'})
        (self.repos / 'Issabel.repo').unlink()
        (self.repos / 'Issabel5.repo').unlink()
        self.assertEqual(self.apply(if_present=True), [])

    def test_owner_drift_or_added_duplicate_after_plan_stops_before_any_write(self):
        plan = self.module.plan(self.root)
        self.unrelated.write_bytes(self.unrelated.read_bytes() + b'# owner changed after plan\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.module.apply_plan(plan, self.backup)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.backup.exists())
        plan = self.module.plan(self.root)
        (self.repos / 'new.repo').write_bytes(b'[issabel-cinco]\nenabled=0\n')
        with self.assertRaises(ValueError):
            self.module.apply_plan(plan, self.backup)
        self.assertFalse(self.backup.exists())

    def test_mismatched_previous_backup_is_preserved_without_repository_changes(self):
        self.backup.mkdir()
        name = 'Issabel.repo'
        path = self.backup / (name + '-' + self.module.VENDOR_HASHES[name] + '.original')
        path.write_bytes(b'owner backup content')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(path.read_bytes(), b'owner backup content')
        self.assertEqual(self.snapshot(), before)

    @unittest.skipIf(os.name != 'posix', 'Native POSIX repository metadata and symlink boundary')
    def test_symlinks_writable_inputs_and_metadata_preservation(self):
        target = self.repos / 'Issabel.repo'
        original = target.read_bytes()
        target.chmod(0o666)
        with self.assertRaises(ValueError):
            self.apply()
        target.chmod(0o644)
        outside = self.root / 'outside'; outside.write_bytes(original)
        target.unlink(); target.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.apply()
        target.unlink(); target.write_bytes(original); target.chmod(0o644)
        commercial = self.repos / 'commercial-addons.repo'; commercial.chmod(0o755)
        self.apply()
        self.assertEqual(commercial.stat().st_mode & 0o777, 0o755)
        self.assertEqual(target.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in self.backup.iterdir()))


if __name__ == '__main__':
    unittest.main()
