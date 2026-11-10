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
THEME = load('submit_header_test', 'admin-theme/patch-admin-theme.py')


class SubmitScopeTests(unittest.TestCase):
    def test_modified_or_duplicate_apply_blocks_fail_closed(self):
        source = "$html .= '<head>';\n$html .= '</head>';"
        candidate = THEME.transform_header(source)
        self.assertEqual(THEME.transform_header(candidate), candidate)
        modified = candidate.replace('assets/mytel/apply.js?v=753', 'assets/mytel/apply.js?v=owner')
        with self.assertRaisesRegex(ValueError, 'drift'):
            THEME.transform_header(modified)
        with self.assertRaises(ValueError):
            THEME.transform_header(candidate + candidate)

    def test_scope_is_exactly_the_eight_reviewed_admin_paths(self):
        self.assertEqual(len(POLICY.SUBMIT_PATHS), 8)
        for path in POLICY.SUBMIT_PATHS:
            self.assertTrue(POLICY.allowed({'root':'admin','path':path}, POLICY.SUBMIT_PROFILE))
            for other in ('panel','legacy','desk','phone'):
                self.assertFalse(POLICY.allowed({'root':other,'path':path}, POLICY.SUBMIT_PROFILE))
        for path in ('functions.inc.php','libraries/view.functions.php','modules/core/functions.inc.php'):
            self.assertFalse(POLICY.allowed({'root':'admin','path':path}, POLICY.SUBMIT_PROFILE))

    def test_save_and_lifecycle_evidence_are_required(self):
        self.assertTrue({'save-browser','toast-lifecycle'}.issubset(POLICY.SUBMIT_CHECKS))
        self.assertTrue(POLICY.SCOPED_CHECKS.issubset(POLICY.SUBMIT_CHECKS))

    def test_transaction_anchor_is_idempotent_and_rejects_mixed_blocks(self):
        candidate = PATCH.transform_functions(PATCH.OLD_REPLACE)
        self.assertEqual(PATCH.transform_functions(candidate), candidate)
        for source in (candidate+PATCH.OLD_REPLACE, candidate+candidate, 'owner changed replacement'):
            with self.assertRaises(ValueError): PATCH.transform_functions(source)

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
