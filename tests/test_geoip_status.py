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

    def module_fixture(self, state='ready'):
        running='4.18.0-553.184.1.el8_10.x86_64'
        return dict(schema='mytellpbx-geoip-module/1',owner='MyTellPBX',module='xt_geoip',state=state,
                    running_kernel=running,target_kernel=running,loaded=True,persistent=True,module_sha256='b'*64)

    def run_consumer(self, module, kernel='4.18.0-553.184.1.el8_10.x86_64', loaded=True, persian=False):
        code=('require $argv[1]; $v=json_decode(stream_get_contents(STDIN),true); '
              'echo json_encode(array("valid"=>function_exists("mytellGeoipValidModuleStatus")?mytellGeoipValidModuleStatus($v["module"]):false,'
              '"html"=>mytellGeoipRender($v["data"],$v["persian"],$v["module"],$v["kernel"],$v["loaded"])));')
        value=dict(data=self.fixture(),module=module,kernel=kernel,loaded=loaded,persian=persian)
        result=subprocess.run(['php','-d','auto_prepend_file=','-d','auto_append_file=','-r',code,str(MODULE)],input=json.dumps(value).encode(),
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf-8','replace'))
        return json.loads(result.stdout.decode())

    def test_data_ready_is_separate_from_missing_consumer_receipt(self):
        html=self.run_consumer(None)['html']
        self.assertIn('DB-IP Country Lite',html)
        self.assertIn('data-geoip-consumer-state="unknown"',html)
        self.assertIn('Not verified',html)

    def test_ready_consumer_requires_live_loaded_module_and_same_kernel(self):
        value=self.module_fixture()
        self.assertTrue(self.run_consumer(value)['valid'])
        self.assertIn('data-geoip-consumer-state="ready"',self.run_consumer(value)['html'])
        self.assertIn('data-geoip-consumer-state="unavailable"',self.run_consumer(value,loaded=False)['html'])
        self.assertIn('data-geoip-consumer-state="unknown"',self.run_consumer(value,kernel='4.18.0-other.x86_64')['html'])

    def test_pending_restart_is_truthful_and_can_promote_only_on_target_boot(self):
        value=self.module_fixture('pending-reboot');value['running_kernel']='4.18.0-553.134.1.el8_10.x86_64';value['loaded']=False
        html=self.run_consumer(value,kernel=value['running_kernel'],loaded=False)['html']
        self.assertIn('data-geoip-consumer-state="pending-reboot"',html);self.assertIn('Restart required',html)
        self.assertIn('data-geoip-consumer-state="ready"',self.run_consumer(value)['html'])
        self.assertIn('data-geoip-consumer-state="unknown"',self.run_consumer(value,kernel='4.18.0-other.x86_64')['html'])

    def test_unavailable_metadata_never_becomes_ready_from_data_or_loaded_flag(self):
        value=self.module_fixture('unavailable');value['module_sha256']=None;value['target_kernel']=None;value['loaded']=False
        for loaded in [True,False]:
            self.assertIn('data-geoip-consumer-state="unavailable"',self.run_consumer(value,loaded=loaded)['html'])

    def test_consumer_schema_types_identity_and_markup_are_strict(self):
        base=self.module_fixture()
        for key,value in [('schema',1),('owner','operator'),('loaded',1),('persistent','yes'),('module_sha256','<script>'),
                          ('target_kernel','../escape'),('state','owner'),('running_kernel','<script>')]:
            changed=dict(base);changed[key]=value;result=self.run_consumer(changed)
            self.assertFalse(result['valid'],(key,value));self.assertNotIn('<script>',result['html'])
            self.assertIn('data-geoip-consumer-state="unknown"',result['html'])
        self.assertFalse(self.run_consumer(dict(base,extra='unknown'))['valid'])

    def test_persian_consumer_copy_stays_separate_from_country_data(self):
        html=self.run_consumer(None,persian=True)['html']
        self.assertIn('تشخیص کشور ترافیک',html);self.assertIn('وضعیت تأیید نشده',html)
        self.assertIn('پایگاه داده',html)


if __name__ == '__main__':
    unittest.main()
