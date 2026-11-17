"""Online factory preservation; reuse the disposable real-Bash stage fixture."""
import unittest

import test_installer_offline_geoip_wiring as fixture_module

ROOT = fixture_module.ROOT


class NativeGeoipWiringTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.OfflineGeoipWiringTests(methodName='runTest')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)

    def exercise(self, **kwargs):
        kwargs.setdefault('offline', False)
        return self.fixture.exercise(**kwargs)

    def test_online_hold_precedes_package_transaction_and_handoff_precedes_updater(self):
        result, events = self.exercise(); self.assertEqual(result.returncode, 0, result.stderr)
        order = [row[3] if row[0]=='NATIVE' else row[0] for row in events]
        for before, after in [('--hold','DNF'), ('DNF','--handoff'), ('--handoff','UPDATER'),
                              ('UPDATER','CONSUMER'), ('CONSUMER','DESK')]:
            self.assertIn(before, order); self.assertIn(after, order)
            self.assertLess(order.index(before), order.index(after), order)

    def test_both_calls_bind_only_current_version_and_bundle(self):
        result, events = self.exercise(); self.assertEqual(result.returncode, 0, result.stderr)
        calls = [row for row in events if row[0]=='NATIVE']
        # Read the actual source identity using Bash, rather than duplicating a
        # release literal in this component test when ROOT later repins it.
        self.fixture.events.unlink()
        identity_result, identity = self.exercise(action='event SOURCE "$MYTELLPBX_VERSION" "$MYTELLPBX_BUNDLE_SHA256"')
        self.assertEqual(identity_result.returncode, 0, identity_result.stderr)
        _, version, bundle = next(row for row in identity if row[0]=='SOURCE')
        expected = [['NATIVE','-B',(self.fixture.bundle/'installer/prepare-native-geoip.py').as_posix(), phase,
                     '--version',version,'--bundle-sha256',bundle] for phase in ['--hold','--handoff']]
        self.assertEqual(calls, expected)

    def test_owned_marker_resume_still_calls_both_preservation_phases(self):
        result, events = self.exercise(resume=True); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row[3] for row in events if row[0]=='NATIVE'], ['--hold','--handoff'])
        self.assertFalse(any(row[0] in ['DNF','UPDATER'] for row in events))
        self.assertTrue(any(row[0]=='CONSUMER' for row in events))

    def test_hold_failure_prevents_all_stage_two_and_managed_actions(self):
        result, events = self.exercise(fail='--hold'); self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(row[0] in ['DNF','UPDATER','CONSUMER','DESK','DONE'] for row in events))

    def test_package_failure_prevents_handoff(self):
        result, events = self.exercise(fail='packages'); self.assertNotEqual(result.returncode, 0)
        self.assertEqual([row[3] for row in events if row[0]=='NATIVE'], ['--hold'])

    def test_handoff_failure_prevents_managed_activation(self):
        result, events = self.exercise(fail='--handoff'); self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(row[0] in ['UPDATER','CONSUMER','DESK','DONE'] for row in events))

    def test_media_path_runs_only_its_existing_three_bridge_phases(self):
        result, events = self.exercise(offline=True); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(row[0]=='NATIVE' for row in events))
        self.assertEqual([row[3] for row in events if row[0]=='BRIDGE'], ['--prepare','--handoff','--finish'])

    def test_online_path_never_runs_offline_bridge(self):
        result, events = self.exercise(); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(row[0]=='BRIDGE' for row in events))

    def test_exact_native_helper_is_required_bundle_payload(self):
        text = (ROOT/'scripts/build-installer-bundle.sh').read_text()
        self.assertIn('copy_path "installer/prepare-native-geoip.py"', text)


if __name__ == '__main__': unittest.main()
