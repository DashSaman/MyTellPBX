"""Fresh-only native WebSocket ownership; all subprocesses are fixture-owned."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('pjsip_websocket', ROOT / 'installer/prepare-pjsip-websocket.py')
WS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WS)


class NativeRowsTests(unittest.TestCase):
    def test_factory_adds_exactly_one_native_boolean_preserving_every_seed(self):
        before = WS.factory_rows()
        actual = WS.plan_rows(before)
        self.assertEqual(actual, sorted(before + [['websocket_enabled', 'no', '0', '0']]))
        self.assertEqual(len(before), 17)
        self.assertEqual(before, WS.factory_rows())

    def test_explicit_operator_choice_is_never_changed(self):
        for choice in ['yes', 'no', 'unknown']:
            self.assertIsNone(WS.plan_rows(WS.factory_rows() + [['websocket_enabled', choice, '0', '0']]))

    def test_nonfactory_profile_and_custom_values_are_refused(self):
        for rows in [[], WS.factory_rows()[1:], WS.factory_rows() + [['nat_mode', 'public', '0', '0']]]:
            with self.assertRaises(ValueError):
                WS.plan_rows(rows)


if __name__ == '__main__':
    unittest.main()
