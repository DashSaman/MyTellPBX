"""Product-overlay contracts; no ISO build, mount, guest, network or services."""
import configparser
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / 'installer/iso/product'


class IsoBrandingTests(unittest.TestCase):
    def read(self, relative):
        path = PRODUCT / relative
        self.assertTrue(path.is_file() and not path.is_symlink(), 'Missing regular overlay input: ' + relative)
        return path.read_text(encoding='utf-8')

    def ini(self, relative):
        value = configparser.ConfigParser(interpolation=None)
        value.read_string(self.read(relative))
        return value

    def test_product_identity_and_base_compose_metadata_are_consistent(self):
        stamp = self.ini('.buildstamp')
        config = self.ini('etc/anaconda/product.d/mytelpbx.conf')
        self.assertEqual(stamp['Main']['Product'], config['Product']['product_name'])
        self.assertEqual(stamp['Main']['Product'], 'MytelPBX')
        self.assertEqual(stamp['Main']['BugURL'], 'https://mytel.one')
        self.assertEqual(stamp['Main']['Version'], '@VERSION@')
        self.assertTrue(stamp.getboolean('Main', 'IsFinal'))
        self.assertEqual(stamp['Main']['UUID'], '@BASE_UUID@')
        self.assertEqual(stamp['Compose']['Lorax'], '@BASE_LORAX@')

    def test_product_inherits_base_behavior_without_storage_or_security_overrides(self):
        config = self.ini('etc/anaconda/product.d/mytelpbx.conf')
        self.assertEqual(set(config.sections()), {'Product', 'Base Product', 'User Interface'})
        self.assertEqual(dict(config['Product']), {'product_name': 'MytelPBX'})
        self.assertEqual(dict(config['Base Product']), {'product_name': '@BASE_PRODUCT@'})
        self.assertEqual(dict(config['User Interface']), {
            'custom_stylesheet': '/usr/share/anaconda/pixmaps/mytelpbx.css'})

    def test_stylesheet_changes_only_brand_widgets_and_resolves_local_images(self):
        css = self.read('usr/share/anaconda/pixmaps/mytelpbx.css')
        plain = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        selectors = set(re.findall(r'([^{}]+)\{', re.sub(r'@define-color[^;]+;', '', plain)))
        self.assertEqual({s.strip() for s in selectors}, {
            '.logo-sidebar', '.logo', '.product-logo', 'AnacondaSpokeWindow #nav-box'})
        urls = re.findall(r'url\([\'"]?([^\'"\)]+)', css)
        self.assertTrue(urls)
        for url in urls:
            self.assertTrue(url.startswith('/usr/share/anaconda/pixmaps/'))
            self.assertNotIn('..', Path(url).parts)
            self.assertTrue((PRODUCT / url.lstrip('/')).is_file(), 'Unresolved brand image')
        self.assertNotRegex(plain, r'(?i)display\s*:\s*none|visibility\s*:\s*hidden|https?://')

    def test_wordmark_is_self_contained_and_legible_on_the_actual_brand_background(self):
        raw = self.read('usr/share/anaconda/pixmaps/mytelpbx-wordmark.svg')
        svg = ET.fromstring(raw)
        self.assertNotIn('<script', raw.lower())
        self.assertNotIn('foreignobject', raw.lower())
        self.assertFalse(any(key.endswith('href') for node in svg.iter() for key in node.attrib))
        text = ''.join(svg.itertext())
        self.assertIn('MytelPBX', text)
        self.assertIn('https://mytel.one', text)
        css = self.read('usr/share/anaconda/pixmaps/mytelpbx.css')
        background = re.search(r'@define-color mytelpbx_background (#[0-9a-fA-F]{6});', css).group(1)
        def luminance(color):
            values = [int(color[n:n+2], 16) / 255 for n in (1, 3, 5)]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
            return sum(v*w for v, w in zip(linear, (.2126, .7152, .0722)))
        for node in svg.iter():
            if node.tag.rsplit('}', 1)[-1] in ('text', 'tspan'):
                foreground = node.attrib['fill']
                bright, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
                self.assertGreaterEqual((bright + .05) / (dark + .05), 4.5)

    def test_only_builder_supported_tokens_are_required(self):
        tokens = set()
        for relative in ('.buildstamp', 'etc/anaconda/product.d/mytelpbx.conf'):
            tokens.update(re.findall(r'@[A-Z_]+@', self.read(relative)))
        self.assertEqual(tokens, {'@VERSION@', '@BASE_PRODUCT@', '@BASE_UUID@', '@BASE_LORAX@'})


if __name__ == '__main__':
    unittest.main()
