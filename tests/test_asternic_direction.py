"""Guarded Asternic source transformation, no PBX/database connection."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'admin-fixes/patch-asternic-direction.py'


class AsternicDirectionPatcherTests(unittest.TestCase):
    def load(self):
        self.assertTrue(PATH.is_file(), 'Asternic direction patcher missing')
        spec = importlib.util.spec_from_file_location('asternic_direction_patch', str(PATH))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_unknown_page_and_function_sources_fail_before_changes(self):
        patcher = self.load()
        for transform in (patcher.transform_page, patcher.transform_functions):
            with self.subTest(transform=transform.__name__):
                with self.assertRaises(ValueError): transform('<?php // unfamiliar optional report module\n')

    def test_planning_missing_optional_module_is_explicit_and_non_mutating(self):
        patcher = self.load()
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'missing-module'
            self.assertEqual(patcher.plan(root), {})
            self.assertFalse(root.exists())

    def test_main_and_bundle_require_direction_runtime_dependencies(self):
        self.assertTrue('patch-asternic-direction.py' in (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8'), 'Optional Asternic installer hook missing')
        bundle = (ROOT / 'scripts/build-installer-bundle.sh').read_text(encoding='utf-8')
        for name in ('patch-asternic-direction.py', 'asternic-direction.php'):
            self.assertTrue('copy_path "admin-fixes/' + name + '"' in bundle, 'Bundle dependency missing: ' + name)


if __name__ == '__main__': unittest.main()
