"""Read-only native GeoIP presentation; never installs or updates country data."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('php'), 'Native PHP runtime required')
class NativeGeoipTests(unittest.TestCase):
    def render(self, root, persian=False):
        code = ('require $argv[1]; $v=mytellGeoipNativeEvidence($argv[2]); '
                'echo json_encode(array("evidence"=>$v,"html"=>mytellGeoipNativeRender($v,$argv[3]==="fa")));')
        result = subprocess.run(['php', '-r', code, str(ROOT / 'modules/mytellpbxgeoip/index.php'),
                                 str(root), 'fa' if persian else 'en'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        return json.loads(result.stdout.decode('utf-8'))

    def test_native_files_and_loaded_module_never_claim_country_matching_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ('usr/share/GeoIP/GeoIP.dat', 'usr/share/GeoIP/GeoIPv6.dat', 'usr/share/xt_geoip/BE/IR.iv4'):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'native-vendor-data')
            (root / 'sys/module/xt_geoip').mkdir(parents=True)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = self.render(root)
            self.assertTrue(result['evidence']['ipv4_present'])
            self.assertTrue(result['evidence']['ipv6_present'])
            self.assertTrue(result['evidence']['module_loaded'])
            self.assertEqual(result['evidence']['country_table_files'], 1)
            self.assertIn('data-geoip-source="native"', result['html'])
            self.assertIn('have not been verified', result['html'])
            self.assertNotIn('data-geoip-consumer-state="ready"', result['html'])
            self.assertNotIn('DB-IP', result['html'])
            self.assertNotIn('automatically', result['html'])
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_missing_vendor_data_has_truthful_persian_status_without_write_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.render(Path(directory), True)
            self.assertFalse(result['evidence']['ipv4_present'])
            self.assertEqual(result['evidence']['country_table_files'], 0)
            self.assertIn('مشاهده نشد', result['html'])
            self.assertIn('تأیید نشده', result['html'])
            self.assertNotIn('<input', result['html'])
            self.assertNotIn('<form', result['html'])
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
