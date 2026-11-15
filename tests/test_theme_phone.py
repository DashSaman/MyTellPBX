"""Optional standalone phone entry availability, rendered by the real native Smarty."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SMARTY = Path(os.environ.get('MT_TEST_SMARTY', '/usr/share/php/Smarty/Smarty.class.php'))
PHP = os.environ.get('MT_TEST_PHP') or shutil.which('php')


@unittest.skipUnless(PHP and SMARTY.is_file(), 'Native PHP and Smarty rendering fixture')
class OptionalPhoneTests(unittest.TestCase):
    def render(self, mode):
        with tempfile.TemporaryDirectory(prefix='mytel-phone-links-') as directory:
            result = subprocess.run([PHP, str(REPO / 'tests/ui/phone-links.php'), '--smarty=' + str(SMARTY),
                                     '--fixture=' + str(Path(directory) / 'fixture'), '--case=' + mode],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = json.loads(result.stdout)
            self.assertFalse(any(value['unexpanded'] for value in rendered.values()))
            return rendered

    def absent(self, mode):
        rendered = self.render(mode)
        self.assertEqual(rendered['index.tpl']['phone_links'], 0, 'Fresh installs must not advertise absent /Phone/')
        self.assertEqual(rendered['index.tpl']['phone_cards'], 0)
        self.assertEqual(rendered['index.tpl']['desk_cards'], 1)
        self.assertEqual(rendered['login.tpl']['phone_links'], 0)
        self.assertEqual(rendered['login.tpl']['desk_links'], 1, 'Anonymous entry should lead to the actual Desk login')

    def installed(self, mode):
        rendered = self.render(mode)
        self.assertEqual(rendered['index.tpl']['phone_links'], 1)
        self.assertEqual(rendered['index.tpl']['phone_cards'], 1)
        self.assertEqual(rendered['index.tpl']['desk_cards'], 1)
        self.assertEqual(rendered['login.tpl']['phone_links'], 1)

    def test_fresh_install_without_a_phone_entry_uses_only_available_products(self):
        self.absent('absent')

    def test_polish_assets_alone_do_not_advertise_a_phone_product(self):
        self.absent('assets')

    def test_existing_html_phone_entry_is_preserved(self):
        self.installed('html')

    def test_existing_php_phone_entry_is_preserved(self):
        self.installed('php')

    def test_dangling_phone_entry_is_not_advertised(self):
        self.absent('dangling')


if __name__ == '__main__':
    unittest.main()
