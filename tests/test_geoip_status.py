"""Render real PHP status functions without a framework, DB or network."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / 'modules/mytellpbxgeoip/index.php'


@unittest.skipUnless(shutil.which('php'), 'Native PHP runtime required')
class GeoipStatusTests(unittest.TestCase):
    def fixture(self):
        return dict(schema=1, owner='MyTellPBX GeoIP', provider='DB-IP Country Lite',
                    status='ready', layout='flat-network-BE', license='CC-BY-4.0',
                    attribution_url='https://db-ip.com',
                    license_url='https://creativecommons.org/licenses/by/4.0/',
                    month='2026-11', source_url='https://download.db-ip.com/free/dbip-country-lite-2026-11.csv.gz',
                    source_sha256='a' * 64, updated_utc='2026-11-15T12:34:56Z',
                    rows=600000, ipv4_ranges=400000, ipv6_ranges=200000, country_count=250)

    def run_php(self, value, persian=True):
        code = ('require $argv[1]; $v=json_decode(stream_get_contents(STDIN),true); '
                'echo json_encode(array("valid"=>mytellGeoipValidStatus($v),'
                '"html"=>mytellGeoipRender($v,' + ('true' if persian else 'false') + ')));')
        result = subprocess.run(['php', '-r', code, str(MODULE)], input=json.dumps(value).encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        return json.loads(result.stdout.decode())

    def test_real_ready_status_and_attribution(self):
        result = self.run_php(self.fixture())
        self.assertTrue(result['valid'])
        self.assertIn('آماده', result['html'])
        self.assertIn('https://db-ip.com', result['html'])
        self.assertIn('CC BY 4.0', result['html'])
        self.assertNotIn('<input', result['html'])
        self.assertNotIn('MaxMind', result['html'])

    def test_unavailable_and_english_view(self):
        result = self.run_php(None, False)
        self.assertFalse(result['valid'])
        self.assertIn('not ready yet', result['html'])
        self.assertIn('No license key', result['html'])

    def test_rejects_untrusted_provider_urls_and_markup(self):
        for key in ['provider', 'attribution_url', 'license_url', 'source_url', 'month']:
            value = self.fixture()
            value[key] = '<script>alert(1)</script>'
            result = self.run_php(value)
            self.assertFalse(result['valid'], key)
            self.assertNotIn('<script>', result['html'])

    def test_rejects_corrupt_counts_dates_and_receipt_identity(self):
        for key, bad in [('schema', '1'), ('owner', 'other'), ('status', 'failed'),
                         ('rows', 600001), ('ipv4_ranges', -1), ('ipv6_ranges', '200000'),
                         ('country_count', 301), ('month', '2026-13'),
                         ('updated_utc', '2026-02-30T12:34:56Z'), ('source_sha256', 'z' * 64)]:
            value = self.fixture()
            value[key] = bad
            self.assertFalse(self.run_php(value)['valid'], (key, bad))


if __name__ == '__main__':
    unittest.main()
