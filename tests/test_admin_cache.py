"""New presentation bytes use a fresh URL without weakening header drift checks."""
import importlib.util
from pathlib import Path
import unittest

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cache_header_test',str(REPO/'admin-theme/patch-admin-theme.py'))
patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
HEADER="<?php\n$html='';\n$html .= '<head>';\n// owner customization\n$html .= '</head>';\necho $html;\n"


class HeaderAssetVersionTests(unittest.TestCase):
    def test_new_header_fetches_new_workspace_presentation(self):
        result=patch.transform_header(HEADER)
        self.assertEqual(result.count('workspace.css?v=761'),1)
        self.assertEqual(result.count('workspace.js?v=761'),1)
        self.assertIn('// owner customization',result)

    def test_previous_known_versions_upgrade_without_changing_apply_controllers(self):
        fresh=patch.transform_header(HEADER)
        for version in ['740','752','760','761']:
            old=fresh.replace('workspace.css?v=761','workspace.css?v='+version).replace('workspace.js?v=761','workspace.js?v='+version)
            with self.subTest(version=version):
                result=patch.transform_header(old)
                self.assertEqual(result.count('workspace.css?v=761'),1)
                self.assertEqual(result.count('workspace.js?v=761'),1)
                self.assertEqual(result.count('assets/mytel/save.js?v=753'),1)
                self.assertEqual(patch.transform_header(result),result)

    def test_unrecognized_workspace_url_is_preserved_by_refusal(self):
        old=patch.transform_header(HEADER).replace('workspace.css?v=761','workspace.css?v=operator')
        with self.assertRaisesRegex(ValueError,'marker changed'):patch.transform_header(old)


if __name__=='__main__':unittest.main()
