"""Disposable native-country handoff; no RPM, network, service or DB actions."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'installer/prepare-native-geoip.py'


class NativeGeoIPTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'Fresh online native country outputs have no ownership handoff')
        spec = importlib.util.spec_from_file_location('native_geoip_fixture', str(SCRIPT))
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.uid = os.geteuid() if hasattr(os, 'geteuid') else 0
        self.ctx = self.m.Context(self.root, '7.6.2', 'a' * 64, self.uid)
        (self.root / 'usr/share').mkdir(parents=True)
        self.put(self.m.SOURCE, json.dumps(dict(owner='MyTellPBX', schema=1,
            version='7.6.2', bundle_sha256='a' * 64)).encode(), 0o600)
        (self.root / self.m.SOURCE).parent.chmod(0o700)
        self.m.VENDOR_SHA = 'fixture'

    def put(self, name, raw=b'', mode=0o644):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw); path.chmod(mode); return path

    def generated(self):
        self.put(self.m.PACKAGES)
        cron = self.put(self.m.CRON, b'known native cron')
        self.m.VENDOR_SHA = self.m.sha(cron.read_bytes())
        for prefix in ['', 'BE/', 'LE/']:
            for family in [4, 6]:
                for code in ['US', 'A1', 'A2', 'O1']:
                    self.put(self.m.ACTIVE + '/' + prefix + code + '.iv' + str(family),
                             bytes([family]) * (8 if family == 4 else 32))
        self.put('usr/share/GeoIP/GeoIP.dat', b'legacy dat unchanged')
        self.put('usr/share/geoip/BE/US.iv4', b'legacy BE unchanged')

    def handoff(self):
        self.m.hold(self.ctx); self.generated(); return self.m.handoff(self.ctx)

    def test_real_source_and_initial_empty_state_are_required(self):
        value = self.m.hold(self.ctx)
        self.assertEqual(value['phase'], 'held')
        self.assertEqual(value['initial']['kind'], 'absent')
        self.assertFalse((self.root / self.m.BACKUP).exists())
        self.assertEqual(self.m.hold(self.ctx), value)
        source = self.root / self.m.SOURCE; source.write_bytes(b'{}')
        with self.assertRaises(ValueError): self.m.hold(self.ctx)

    def test_new_hold_never_adopts_existing_country_data_or_completed_packages(self):
        path = self.put(self.m.ACTIVE + '/operator.data', b'keep')
        with self.assertRaises(ValueError): self.m.hold(self.ctx)
        self.assertEqual(path.read_bytes(), b'keep')
        path.unlink(); path.parent.rmdir(); self.put(self.m.PACKAGES)
        with self.assertRaises(ValueError): self.m.hold(self.ctx)

    def test_known_empty_directory_is_preserved_until_native_generation(self):
        path = self.root / self.m.ACTIVE; path.mkdir(parents=True)
        self.assertEqual(self.m.hold(self.ctx)['initial']['kind'], 'empty')
        self.assertTrue(path.is_dir()); self.assertFalse(any(path.iterdir()))

    def test_handoff_preserves_all_native_bytes_metadata_and_other_legacy_paths(self):
        self.m.hold(self.ctx); self.generated()
        original = self.m.inventory(self.ctx, self.root / self.m.ACTIVE)
        value = self.m.handoff(self.ctx)
        self.assertEqual(value['phase'], 'handoff'); self.assertFalse(value['dataset_validity_claimed'])
        self.assertEqual(self.m.inventory(self.ctx, self.root / self.m.BACKUP), original)
        self.assertIn('BE/A1.iv4', original); self.assertIn('LE/A2.iv6', original); self.assertIn('O1.iv4', original)
        self.assertFalse(any((self.root / self.m.ACTIVE).iterdir()))
        self.assertEqual((self.root / 'usr/share/GeoIP/GeoIP.dat').read_bytes(), b'legacy dat unchanged')
        self.assertEqual((self.root / 'usr/share/geoip/BE/US.iv4').read_bytes(), b'legacy BE unchanged')
        self.assertEqual(self.m.handoff(self.ctx), value)
        self.assertEqual(self.m.hold(self.ctx), value)

    def test_packages_marker_and_exact_native_cron_are_required(self):
        self.m.hold(self.ctx)
        with self.assertRaises((ValueError, OSError)): self.m.handoff(self.ctx)
        self.generated(); (self.root / self.m.CRON).write_bytes(b'operator cron')
        with self.assertRaises(ValueError): self.m.handoff(self.ctx)
        self.assertFalse((self.root / self.m.BACKUP).exists())

    def test_unknown_configuration_is_preserved_and_refused(self):
        config = self.put(self.m.CONFIG, b'customer key configuration', 0o600)
        with self.assertRaises(ValueError): self.m.hold(self.ctx)
        self.assertEqual(config.read_bytes(), b'customer key configuration')
        config.unlink(); self.m.hold(self.ctx); self.generated(); config.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.m.handoff(self.ctx)

    def test_unknown_country_entry_and_existing_backup_are_never_overwritten(self):
        self.m.hold(self.ctx); self.generated()
        unknown = self.put(self.m.ACTIVE + '/customer.csv', b'keep')
        with self.assertRaises(ValueError): self.m.handoff(self.ctx)
        self.assertEqual(unknown.read_bytes(), b'keep'); unknown.unlink()
        prior = self.put(self.m.BACKUP + '/prior', b'preserve')
        with self.assertRaises(ValueError): self.m.handoff(self.ctx)
        self.assertEqual(prior.read_bytes(), b'preserve')

    def test_failed_rename_leaves_durable_exact_intent_and_resumes_once(self):
        self.m.hold(self.ctx); self.generated()
        with mock.patch.object(self.m.os, 'rename', side_effect=OSError('injected')):
            with self.assertRaises(OSError): self.m.handoff(self.ctx)
        self.assertEqual(json.loads((self.root / self.m.STATE).read_text())['phase'], 'moving')
        self.assertTrue((self.root / self.m.ACTIVE / 'US.iv4').is_file())
        self.assertEqual(self.m.handoff(self.ctx)['phase'], 'handoff')

    def test_crash_after_move_recovers_only_matching_archived_tree(self):
        self.m.hold(self.ctx); self.generated(); original = self.m.os.rename
        def moved_then_failed(before, after):
            original(before, after); raise OSError('after atomic move')
        with mock.patch.object(self.m.os, 'rename', side_effect=moved_then_failed):
            with self.assertRaises(OSError): self.m.handoff(self.ctx)
        self.assertFalse((self.root / self.m.ACTIVE).exists())
        self.assertEqual(self.m.handoff(self.ctx)['phase'], 'handoff')

    def test_changed_country_after_intent_and_changed_backup_refuse(self):
        self.m.hold(self.ctx); self.generated()
        with mock.patch.object(self.m.os, 'rename', side_effect=OSError('injected')):
            with self.assertRaises(OSError): self.m.handoff(self.ctx)
        path = self.root / self.m.ACTIVE / 'US.iv4'; path.write_bytes(b'changed!')
        with self.assertRaises(ValueError): self.m.handoff(self.ctx)
        self.assertEqual(path.read_bytes(), b'changed!')

    def test_source_or_stage_receipt_changes_after_intent_refuse(self):
        self.m.hold(self.ctx); self.generated()
        with mock.patch.object(self.m.os, 'rename', side_effect=OSError('injected')):
            with self.assertRaises(OSError): self.m.handoff(self.ctx)
        (self.root / self.m.PACKAGES).write_bytes(b'not an empty native stage marker')
        with self.assertRaises(ValueError): self.m.handoff(self.ctx)
        self.assertFalse((self.root / self.m.BACKUP).exists())

    def test_archived_data_and_directory_metadata_changes_are_not_adopted(self):
        self.handoff(); path = self.root / self.m.BACKUP / 'US.iv4'; path.write_bytes(b'changed!')
        with self.assertRaises(ValueError): self.m.hold(self.ctx)
        self.assertEqual(path.read_bytes(), b'changed!')

    def test_completed_handoff_does_not_recreate_an_interrupted_managed_activation(self):
        value = self.handoff(); active = self.root / self.m.ACTIVE
        managed_backup = active.parent / '.xt_geoip-empty-before-mytell'
        os.replace(str(active), str(managed_backup))
        self.assertEqual(self.m.handoff(self.ctx), value)
        self.assertEqual(self.m.hold(self.ctx), value)
        self.assertFalse(active.exists()); self.assertTrue(managed_backup.is_dir())
        self.assertFalse(any(managed_backup.iterdir()))

    def test_unknown_managed_program_is_rejected_before_import(self):
        self.handoff(); self.put(self.m.PROGRAM, b'raise AssertionError("must not execute")')
        with self.assertRaisesRegex(ValueError, 'Managed updater source differs'):
            self.m.load_updater(self.ctx)

    def test_changed_private_receipt_cannot_claim_dataset_validity_or_unknown_fields(self):
        self.m.hold(self.ctx); path = self.root / self.m.STATE
        original = path.read_bytes()
        for key, value in [('dataset_validity_claimed', True), ('foreign', 'unknown')]:
            changed = json.loads(original); changed[key] = value; path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError): self.m.hold(self.ctx)
        path.write_bytes(original)
        self.assertEqual(self.m.hold(self.ctx)['phase'], 'held')

    @unittest.skipUnless(os.name == 'posix', 'Native managed symlink reentry')
    def test_exact_managed_pointer_reenters_but_unknown_pointer_is_retained(self):
        value = self.handoff(); active = self.root / self.m.ACTIVE; active.rmdir()
        release = self.root / 'usr/share/mytellpbx-geoip/releases/owned'; (release / 'BE').mkdir(parents=True)
        active.symlink_to(release / 'BE'); self.put(self.m.CRON, b'owned wrapper')
        checked = []
        updater = SimpleNamespace(WRAPPER=b'owned wrapper', release_info=lambda p: checked.append(p))
        with mock.patch.object(self.m, 'load_updater', return_value=updater):
            self.assertEqual(self.m.handoff(self.ctx), value)
            self.assertEqual(self.m.hold(self.ctx), value)
            self.assertEqual(checked, [release, release])
            active.unlink(); other = self.root / 'operator'; (other / 'BE').mkdir(parents=True)
            active.symlink_to(other / 'BE')
            with self.assertRaises(ValueError): self.m.handoff(self.ctx)
            self.assertTrue(active.is_symlink())

    @unittest.skipUnless(os.name == 'posix', 'Native symlink refusal')
    def test_symlink_country_and_unknown_active_pointer_are_preserved(self):
        self.m.hold(self.ctx); self.generated()
        path = self.root / self.m.ACTIVE / 'US.iv4'; path.unlink()
        target = self.put('operator.data', b'private'); path.symlink_to(target)
        with self.assertRaises(ValueError): self.m.handoff(self.ctx)
        self.assertTrue(path.is_symlink()); self.assertEqual(target.read_bytes(), b'private')

    @unittest.skipUnless(os.name == 'posix', 'Canonical native parent refusal')
    def test_absent_active_under_symlinked_parent_is_not_adopted(self):
        target = self.root / 'operator'; target.mkdir()
        (self.root / 'usr/share').rmdir(); (self.root / 'usr/share').symlink_to(target)
        with self.assertRaises(ValueError): self.m.hold(self.ctx)
        self.assertFalse((self.root / self.m.STATE).exists()); self.assertFalse(any(target.iterdir()))


if __name__ == '__main__': unittest.main()
