"""Render source-proven branding statements without running a native view.

The two small PHP statements are from Issabel header/footer (GPL-2.0-only;
Issabel Foundation/Palosanto notices remain in installed vendor files). No full
view, configuration, authentication, database, service or network code runs.
"""
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import parse_qsl, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('asset_query_patch', str(ROOT / 'admin-theme/patch-admin-theme.py'))
PATCH = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(PATCH)
PHP = shutil.which('php')
HEADER = '''<?php
$html = '';
$html .= '<head>';
// Owner header stays untouched.
if ($amp_conf['BRAND_CSS_CUSTOM']) {
    $html .= '<link href="' . $amp_conf['BRAND_CSS_CUSTOM']
            . $version_tag . '" rel="stylesheet" type="text/css"/>';
}
$html .= '</head>';
echo $html;
'''
FOOTER = '''<?php
$html = '';
// Owner footer stays untouched.
if ($amp_conf['BRAND_ALT_JS']) {
    $html .= '<script src="' . $amp_conf['BRAND_ALT_JS'] . $version_tag . '&mt-ui=752"></script>';
}
echo $html;
'''


class AssetTags(HTMLParser):
    def __init__(self): super().__init__(); self.links = []; self.scripts = []
    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if tag == 'link' and 'href' in values: self.links.append(values['href'])
        if tag == 'script' and 'src' in values: self.scripts.append(values['src'])


class BrandAssetQueries(unittest.TestCase):
    def test_duplicate_brand_asset_statement_is_refused(self):
        for source, transform, marker in [(HEADER, PATCH.transform_header, '$html .= \'<link href='),
                                           (FOOTER, PATCH.transform_footer, '$html .= \'<script src=')]:
            duplicate = source + source[source.index('if ($amp_conf['):source.rindex('echo $html;')]
            with self.subTest(marker=marker), self.assertRaises(ValueError): transform(duplicate)

    def test_changed_owned_asset_helper_marker_is_preserved_by_refusal(self):
        changed = HEADER + '\n/* MyTellPBX asset query v761 BEGIN */\n// Owner changed this block.\n/* MyTellPBX asset query v761 END */\n'
        with self.assertRaises(ValueError): PATCH.transform_header(changed)

    def test_unknown_brand_renderer_or_controlled_cache_is_refused(self):
        with self.assertRaises(ValueError): PATCH.transform_header(HEADER.replace('. $version_tag', '. owner_version_tag()'))
        with self.assertRaises(ValueError): PATCH.transform_footer(FOOTER.replace('&mt-ui=752', '&mt-ui=owner'))

    def test_unknown_php_view_prefix_is_refused_instead_of_emitting_helper_text(self):
        cases = [(' \n' + HEADER, PATCH.transform_header),
                 (FOOTER.replace('<?php', '<?PHP', 1), PATCH.transform_footer)]
        for source, transform in [(HEADER, PATCH.transform_header), (FOOTER, PATCH.transform_footer)]:
            for boundary in ['', '\u00a0', '\u2003']:
                cases.append((source.replace('<?php\n', '<?php' + boundary, 1), transform))
        for source, transform in cases:
            with self.subTest(source=source[:12]), self.assertRaises(ValueError): transform(source)

    def test_transforms_are_idempotent_and_keep_owner_content(self):
        for source, transform in [(HEADER, PATCH.transform_header), (FOOTER, PATCH.transform_footer)]:
            for boundary in ['\n', ' ', '\t', '\r\n']:
                once = transform(source.replace('<?php\n', '<?php' + boundary, 1))
                self.assertEqual(transform(once), once)
                self.assertIn('// Owner ', once)
                self.assertTrue(once.endswith('echo $html;\n'))

    def render(self, kind, url, tag='?load_version=2.12.0.3'):
        transform, source = (PATCH.transform_header, HEADER) if kind == 'css' else (PATCH.transform_footer, FOOTER)
        prelude = "<?php\n$input=array(); parse_str(stream_get_contents(STDIN),$input);\n$amp_conf=array('BRAND_CSS_CUSTOM'=>$input['url'],'BRAND_ALT_JS'=>$input['url']);\n$version_tag=$input['tag'];\n?>"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'fixture.php'; path.write_text(prelude + transform(source), encoding='utf-8')
            result = subprocess.run([PHP, '-n', str(path)], input=urlencode({'url':url,'tag':tag}).encode('ascii'),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        output = result.stdout.decode('utf-8', 'replace')
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn('Warning:', output); self.assertNotIn('Fatal error:', output)
        parsed = AssetTags(); parsed.feed(output)
        return parsed.links[0] if kind == 'css' else parsed.scripts[0]

    def assert_url(self, kind, url, tag='?load_version=2.12.0.3'):
        rendered = self.render(kind, url, tag)
        before, after = urlsplit(url), urlsplit(rendered)
        self.assertEqual((after.scheme,after.netloc,after.path,after.fragment),
                         (before.scheme,before.netloc,before.path,before.fragment))
        original = parse_qsl(before.query, keep_blank_values=True)
        expected = list(original); names = {name for name,_value in original}
        for name,value in parse_qsl(tag.lstrip('?&') + '&mt-ui=761', keep_blank_values=True):
            if name not in names: expected.append((name,value)); names.add(name)
        self.assertEqual(parse_qsl(after.query, keep_blank_values=True), expected)
        if before.query.rstrip('&'):
            self.assertTrue(after.query.startswith(before.query.rstrip('&') + '&') or after.query == before.query)
        self.assertNotIn('?load_version=', after.query)

    @unittest.skipUnless(PHP, 'Native PHP renderer gate')
    def test_actual_owned_brand_urls_keep_separate_cache_parameters(self):
        for kind,url in [('css','assets/mytel/skin.css?v=27'),('js','assets/mytel/sub.js?v=24')]:
            with self.subTest(kind=kind): self.assert_url(kind,url)

    @unittest.skipUnless(PHP, 'Native PHP renderer gate')
    def test_bare_custom_assets_and_fragment_only_urls_remain_valid(self):
        for kind in ['css','js']:
            for url in ['assets/owner/custom.' + kind, 'assets/owner/custom.' + kind + '#section']:
                with self.subTest(kind=kind,url=url): self.assert_url(kind,url)

    @unittest.skipUnless(PHP, 'Native PHP renderer gate')
    def test_custom_queries_preserve_bytes_order_values_and_fragments(self):
        for kind in ['css','js']:
            for url in ['assets/owner/custom.' + kind + '?theme=dark&sig=a%2Bb%26c#palette',
                        'https://cdn.example/custom.' + kind + '?owner=1&v=custom#palette']:
                with self.subTest(kind=kind,url=url): self.assert_url(kind,url)

    @unittest.skipUnless(PHP, 'Native PHP renderer gate')
    def test_empty_query_and_trailing_separator_do_not_create_duplicate_cache_keys(self):
        for url in ['assets/owner/custom.js?', 'assets/owner/custom.js?owner=1&']:
            with self.subTest(url=url): self.assert_url('js',url)

    @unittest.skipUnless(PHP, 'Native PHP renderer gate')
    def test_existing_explicit_cache_parameters_are_preserved_without_duplicates(self):
        for url in ['assets/owner/custom.css?load_version=owner&v=custom',
                    'assets/owner/custom.css?mt-ui=owner&load_version=custom']:
            with self.subTest(url=url): self.assert_url('css',url)

    @unittest.skipUnless(PHP, 'Native PHP renderer gate')
    def test_native_force_download_suffix_and_encoded_custom_values_survive(self):
        self.assert_url('js','assets/owner/custom.js?v=custom','?load_version=2.12.0.3.1700000000')
        self.assert_url('css','assets/owner/custom.css?name=%22quoted%22&space=a%20b#fragment')


if __name__ == '__main__': unittest.main()
