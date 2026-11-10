"""The follow-up artifact cannot broaden write scope or skip journey evidence."""
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, str(REPO/relative))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POLICY = load('submit_policy_test', 'scripts/ui/rollout.py')
PATCH = load('submit_marker_test', 'admin-fixes/patch-submit.py')


class SubmitScopeTests(unittest.TestCase):
    def test_scope_is_exactly_the_six_reviewed_admin_paths(self):
        self.assertEqual(len(POLICY.SUBMIT_PATHS), 6)
        for path in POLICY.SUBMIT_PATHS:
            self.assertTrue(POLICY.allowed({'root':'admin','path':path}, POLICY.SUBMIT_PROFILE))
            for other in ('panel','legacy','desk','phone'):
                self.assertFalse(POLICY.allowed({'root':other,'path':path}, POLICY.SUBMIT_PROFILE))
        for path in ('functions.inc.php','libraries/view.functions.php','modules/sipsettings/functions.inc.php','modules/core/functions.inc.php'):
            self.assertFalse(POLICY.allowed({'root':'admin','path':path}, POLICY.SUBMIT_PROFILE))

    def test_save_and_lifecycle_evidence_are_required(self):
        self.assertTrue({'save-browser','toast-lifecycle'}.issubset(POLICY.SUBMIT_CHECKS))
        self.assertTrue(POLICY.SCOPED_CHECKS.issubset(POLICY.SUBMIT_CHECKS))

    def test_marker_is_idempotent_and_preserves_native_owner_code(self):
        source='owner prefix\n'+PATCH.ANCHOR+'\nowner suffix'
        changed=PATCH.transform(source)
        self.assertEqual(PATCH.transform(changed), changed)
        self.assertTrue(changed.startswith('owner prefix\n'))
        self.assertTrue(changed.endswith('\nowner suffix'))
        self.assertEqual(changed.count(PATCH.ANCHOR),1)

    def test_source_drift_and_partial_marker_fail_closed(self):
        for source in ('changed heading',PATCH.ANCHOR*2,'MyTellPBX native save result v753\n'+PATCH.ANCHOR):
            with self.assertRaises(ValueError): PATCH.transform(source)
