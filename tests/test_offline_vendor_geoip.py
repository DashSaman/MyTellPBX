"""Private files and injected lookup only; never install RPMs or fetch data."""
import hashlib
import importlib.util
import io
import json
import gzip
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'installer/offline-vendor-geoip.py'


class OfflineVendorGeoIPTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(),'Offline RPM GeoIP postscript still has no verified cache bridge')
        spec=importlib.util.spec_from_file_location('offline_geoip_fixture',str(SCRIPT))
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.m.EXPECTED_UID=os.geteuid() if hasattr(os,'geteuid') else 0
        self.native_payload_guard=self.m.rpm_payload_guard
        guard=mock.patch.object(self.m,'rpm_payload_guard',return_value={'packages':1,'filelists_sha256':'a'*64,'owns_geoip_key_config':False})
        guard.start();self.addCleanup(guard.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def cached_profile(self):
        media=self.root/'media';(media/'geoip').mkdir(parents=True)
        rows=[]
        for index in range(205):
            fields=['']*19;fields[0]=chr(65+index//26)+chr(65+index%26);fields[4]='Country';fields[16]=str(index+1);rows.append('\t'.join(fields))
        country=('\n'.join(rows)+'\n').encode()
        raw=''.join('1.0.0.{0},1.0.0.{0},{1}\n'.format(i,code) for i,code in enumerate(['AA','AB','AC','AD']))
        raw+=''.join('2001:db8::{0},2001:db8::{0},{1}\n'.format(i,code) for i,code in enumerate(['AA','AB','AC','AD']))
        files={'geoip/countryInfo.txt':country,'geoip/dbip-country-lite-2020-01.csv.gz':gzip.compress(raw.encode())}
        for name,data in files.items():(media/name).write_bytes(data)
        value={'schema':1,'owner':'MyTellPBX','platform':'rocky8.10-x86_64',
               'geoip':{'path':'geoip/dbip-country-lite-2020-01.csv.gz','month':'2020-01'},
               'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()}}
        data=json.dumps(value).encode();(media/'manifest.json').write_bytes(data)
        return media,hashlib.sha256(data).hexdigest()

    def prepared(self):
        media,pin=self.cached_profile()
        with mock.patch.object(self.m,'module',return_value=SimpleNamespace(load=lambda *a,**kw:None)):
            value=self.m.prepare(self.root,media,pin)
        cron=self.root/self.m.CRON;cron.parent.mkdir(parents=True,exist_ok=True);cron.write_bytes(b'known vendor fixture')
        self.m.VENDOR=hashlib.sha256(cron.read_bytes()).hexdigest()
        return media,pin,value

    def consumed(self):
        media,pin,value=self.prepared()
        out=io.BytesIO();self.m.serve(self.root,'wget',['-q','https://download.db-ip.com/free/dbip-country-lite-2030-01.csv.gz','-O-'],out)
        self.assertEqual(hashlib.sha256(out.getvalue()).hexdigest(),value['profile']['dbip']['sha256'])
        out=io.BytesIO();self.m.serve(self.root,'curl',['-s','http://download.geonames.org/export/dump/countryInfo.txt'],out)
        for relative in ['usr/share/GeoIP/GeoIP.dat','usr/share/GeoIP/GeoIPv6.dat']:
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture native output'*100)
            converted=self.root/'tmp'/path.name;converted.parent.mkdir(exist_ok=True);converted.write_bytes(path.read_bytes())
        for prefix in ['', 'BE/', 'LE/']:
            for family in (4,6):
                path=self.root/self.m.ACTIVE/(prefix+'US.iv'+str(family));path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\0'*(8 if family==4 else 32))
        return media,pin

    def test_only_exact_native_transport_arguments_are_accepted(self):
        self.assertEqual(self.m.asset_for('wget',['-q','https://download.db-ip.com/free/dbip-country-lite-2030-01.csv.gz','-O-']),'dbip')
        self.assertEqual(self.m.asset_for('curl',['-s','http://download.geonames.org/export/dump/countryInfo.txt']),'country')
        for tool,args in [('wget',['https://other.example/']),('wget',['-q','http://download.db-ip.com/free/dbip-country-lite-2030-01.csv.gz','-O-']),
                          ('curl',['-k','http://download.geonames.org/export/dump/countryInfo.txt']),('curl',['-s','https://other.example/']),('date',['+%Y-%m'])]:
            with self.subTest(tool=tool,args=args),self.assertRaises(ValueError):self.m.asset_for(tool,args)

    def test_unknown_existing_configuration_is_preserved(self):
        config=self.root/self.m.CONFIG;config.parent.mkdir();config.write_bytes(b'LICENSE_KEY=operator-owned\n')
        with self.assertRaises(ValueError):self.m.prepare(self.root,self.root,'a'*64)
        self.assertEqual(config.read_bytes(),b'LICENSE_KEY=operator-owned\n')

    def test_interrupted_prepare_completes_only_recorded_owned_publications(self):
        media,pin=self.cached_profile();original=self.m.write
        def fail_program(path,*args,**kwargs):
            if path==self.root/self.m.PROGRAM:raise OSError('Interrupted before helper publication')
            return original(path,*args,**kwargs)
        with mock.patch.object(self.m,'module',return_value=SimpleNamespace(load=lambda *a,**kw:None)):
            with mock.patch.object(self.m,'write',side_effect=fail_program):
                with self.assertRaises(OSError):self.m.prepare(self.root,media,pin)
            self.assertEqual(self.m.state(self.root)[1]['phase'],'prepared')
            self.assertFalse((self.root/self.m.CONFIG).exists())
            value=self.m.prepare(self.root,media,pin)
        self.assertEqual(value['phase'],'prepared')
        self.assertEqual((self.root/self.m.CONFIG).read_bytes(),self.m.config_bytes(self.root))
        self.assertTrue((self.root/self.m.PROGRAM).is_file())

    def test_interrupted_prepare_refuses_foreign_helper_collision(self):
        media,pin=self.cached_profile();original=self.m.write
        def fail_program(path,*args,**kwargs):
            if path==self.root/self.m.PROGRAM:raise OSError('Interrupted')
            return original(path,*args,**kwargs)
        with mock.patch.object(self.m,'module',return_value=SimpleNamespace(load=lambda *a,**kw:None)):
            with mock.patch.object(self.m,'write',side_effect=fail_program):
                with self.assertRaises(OSError):self.m.prepare(self.root,media,pin)
            before=(self.root/self.m.STATE).read_bytes();program=self.root/self.m.PROGRAM;program.write_bytes(b'operator')
            with self.assertRaises(ValueError):self.m.prepare(self.root,media,pin)
        self.assertEqual(program.read_bytes(),b'operator');self.assertFalse((self.root/self.m.CONFIG).exists())
        self.assertEqual((self.root/self.m.STATE).read_bytes(),before)

    def test_interrupted_prepare_refuses_new_populated_country_directory(self):
        media,pin=self.cached_profile();original=self.m.write
        def fail_program(path,*args,**kwargs):
            if path==self.root/self.m.PROGRAM:raise OSError('Interrupted')
            return original(path,*args,**kwargs)
        with mock.patch.object(self.m,'module',return_value=SimpleNamespace(load=lambda *a,**kw:None)):
            with mock.patch.object(self.m,'write',side_effect=fail_program):
                with self.assertRaises(OSError):self.m.prepare(self.root,media,pin)
            active=self.root/self.m.ACTIVE;active.mkdir(parents=True);(active/'operator').write_bytes(b'keep')
            with self.assertRaises(ValueError):self.m.prepare(self.root,media,pin)
        self.assertEqual((active/'operator').read_bytes(),b'keep');self.assertFalse((self.root/self.m.CONFIG).exists())

    def test_country_info_requires_real_unique_country_rows(self):
        with self.assertRaises(ValueError):self.m.country_info(b'not country data')
        row=b'US\tUSA\t840\tUS\tUnited States\t\t\t\t\t\t\t\t\t\t\t\t6252001\n'
        with self.assertRaises(ValueError):self.m.country_info(row*220)

    def test_selected_rpm_payloads_are_read_only_and_config_collision_refuses(self):
        media,pin=self.cached_profile();path=media/'manifest.json';value=json.loads(path.read_text())
        value['files']['repos/test/Packages/public.rpm']={'bytes':1,'sha256':'a'*64};path.write_text(json.dumps(value))
        response=SimpleNamespace(returncode=0,stdout=b'/etc/cron.daily/geoip_update.sh\n/usr/bin/geoiplookup\n',stderr=b'')
        with mock.patch.object(self.m.subprocess,'run',return_value=response) as command:
            proof=self.native_payload_guard(media)
        self.assertEqual(proof['packages'],1);self.assertFalse(proof['owns_geoip_key_config'])
        self.assertEqual(command.call_args[0][0][:3],['/usr/bin/rpm','-qpl','--'])
        self.assertEqual(command.call_args[1]['stdin'],subprocess.DEVNULL)
        response.stdout+=b'/etc/geoip_key.conf\n'
        with mock.patch.object(self.m.subprocess,'run',return_value=response):
            with self.assertRaises(ValueError):self.native_payload_guard(media)

    def test_payload_collision_is_refused_before_any_bridge_state(self):
        media,pin=self.cached_profile()
        with mock.patch.object(self.m,'module',return_value=SimpleNamespace(load=lambda *a,**kw:None)), \
             mock.patch.object(self.m,'rpm_payload_guard',side_effect=ValueError('RPM owns config')):
            with self.assertRaises(ValueError):self.m.prepare(self.root,media,pin)
        self.assertFalse((self.root/self.m.STATE).exists());self.assertFalse((self.root/self.m.CONFIG).exists())

    def test_verified_asset_bytes_and_real_cached_month_are_retained(self):
        media,pin,value=self.prepared();first=(self.root/self.m.CONFIG).read_bytes()
        out=io.BytesIO();self.m.serve(self.root,'wget',['-q','https://download.db-ip.com/free/dbip-country-lite-2030-01.csv.gz','-O-'],out)
        self.assertEqual(out.getvalue(),Path(value['profile']['dbip']['path']).read_bytes())
        self.assertEqual(self.m.state(self.root)[1]['profile']['month'],'2020-01')
        self.assertEqual(self.m.prepare(self.root,media,pin)['served'],['dbip'])
        self.assertEqual((self.root/self.m.CONFIG).read_bytes(),first)

    def test_bad_cache_or_unknown_cron_emits_no_bytes(self):
        media,pin,value=self.prepared();out=io.BytesIO()
        Path(value['profile']['dbip']['path']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):self.m.serve(self.root,'wget',['-q','https://download.db-ip.com/free/dbip-country-lite-2030-01.csv.gz','-O-'],out)
        self.assertEqual(out.getvalue(),b'')

    def test_missing_country_metadata_and_wrong_manifest_pin_refuse(self):
        media,pin=self.cached_profile()
        with self.assertRaises(ValueError):self.m.profile(media,'0'*64)
        (media/'geoip/countryInfo.txt').unlink()
        with self.assertRaises(FileNotFoundError):self.m.profile(media,pin)

    def test_actual_conversion_controls_use_both_families_and_preserve_native_output(self):
        media,pin=self.consumed();observed=[]
        value=self.m.handoff(self.root,media,pin,lookup=lambda rows:observed.extend(rows))
        self.assertEqual(len(observed),8);self.assertEqual({row['family'] for row in observed},{4,6})
        self.assertEqual(value['phase'],'handoff');self.assertEqual(len(value['legacy']),2)
        self.assertFalse(any((self.root/self.m.ACTIVE).iterdir()))
        self.assertEqual(self.m.inventory(self.root/self.m.BACKUP),value['packed'])
        self.assertEqual(self.m.handoff(self.root,media,pin,lookup=lambda rows:None)['packed'],value['packed'])

    def test_native_factory_numeric_alias_filenames_are_preserved_in_all_layouts(self):
        media,pin=self.consumed();aliases={}
        for prefix in ['', 'BE/', 'LE/']:
            for code in ['A1','A2','O1']:
                for family in (4,6):
                    name=prefix+code+'.iv'+str(family);data=b'\x01'*(8 if family==4 else 32)
                    (self.root/self.m.ACTIVE/name).write_bytes(data);aliases[name]=data
        try:value=self.m.handoff(self.root,media,pin,lookup=lambda rows:None)
        except ValueError:self.fail('Native factory archive aliases A1/A2/O1 were incorrectly rejected')
        for name,data in aliases.items():
            self.assertEqual((self.root/self.m.BACKUP/name).read_bytes(),data)
            self.assertEqual(value['packed'][name],{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        self.assertFalse(any((self.root/self.m.ACTIVE).iterdir()))
        # Filename aliases do not relax the separate actual country-data parser.
        path=self.root/'invalid-country.csv.gz'
        path.write_bytes(gzip.compress(b'1.0.0.0,1.0.0.1,A1\n'))
        with self.assertRaises(ValueError):self.m.samples(path)

    def test_invalid_native_archive_filenames_still_refuse_without_moving_data(self):
        media,pin=self.consumed()
        for name in ['A_.iv4','AAA.iv4','a1.iv4','A1.dat','.A1.iv4']:
            with self.subTest(name=name):
                path=self.root/self.m.ACTIVE/name;path.write_bytes(b'\0'*8)
                with self.assertRaises(ValueError):self.m.handoff(self.root,media,pin,lookup=lambda rows:None)
                self.assertEqual(path.read_bytes(),b'\0'*8);self.assertFalse((self.root/self.m.BACKUP).exists())
                path.unlink()

    @unittest.skipUnless(os.name=='posix','Native archive alias symlink boundary')
    def test_numeric_alias_symlink_is_refused_and_original_target_is_preserved(self):
        media,pin=self.consumed();target=self.root/'operator-data';target.write_bytes(b'\0'*8)
        alias=self.root/self.m.ACTIVE/'A1.iv4';alias.symlink_to(target)
        with self.assertRaises(ValueError):self.m.handoff(self.root,media,pin,lookup=lambda rows:None)
        self.assertTrue(alias.is_symlink());self.assertEqual(target.read_bytes(),b'\0'*8)
        self.assertFalse((self.root/self.m.BACKUP).exists())

    def test_interrupted_handoff_resumes_only_exact_recorded_native_output(self):
        media,pin=self.consumed()
        with mock.patch.object(self.m.os,'rename',side_effect=OSError('Interrupted before move')):
            with self.assertRaises(OSError):self.m.handoff(self.root,media,pin,lookup=lambda rows:None)
        self.assertEqual(self.m.state(self.root)[1]['phase'],'handoff')
        self.assertEqual(self.m.handoff(self.root,media,pin,lookup=lambda rows:None)['phase'],'handoff')
        self.assertFalse(any((self.root/self.m.ACTIVE).iterdir()))

    def test_native_lookup_failure_never_moves_active_country_data(self):
        media,pin=self.consumed();before=self.m.inventory(self.root/self.m.ACTIVE)
        def fail(rows):raise ValueError('Native lookup mismatch')
        with self.assertRaises(ValueError):self.m.handoff(self.root,media,pin,lookup=fail)
        self.assertEqual(self.m.inventory(self.root/self.m.ACTIVE),before)
        self.assertFalse((self.root/self.m.BACKUP).exists())

    def test_short_native_conversion_cannot_adopt_the_old_installed_table(self):
        media,pin=self.consumed();(self.root/'tmp/GeoIP.dat').write_bytes(b'short failed conversion')
        with self.assertRaises(ValueError):self.m.handoff(self.root,media,pin,lookup=lambda rows:None)
        self.assertFalse((self.root/self.m.BACKUP).exists())

    def test_unknown_existing_conversion_temporary_is_preserved(self):
        path=self.root/'tmp/GeoIP.dat';path.parent.mkdir();path.write_bytes(b'operator')
        media,pin=self.cached_profile()
        with self.assertRaises(ValueError):self.m.prepare(self.root,media,pin)
        self.assertEqual(path.read_bytes(),b'operator');self.assertFalse((self.root/self.m.STATE).exists())

    def test_partial_native_cache_requests_cannot_be_handed_off(self):
        media,pin,value=self.prepared()
        with self.assertRaises(ValueError):self.m.handoff(self.root,media,pin,lookup=lambda rows:None)

    def test_unknown_native_files_are_retained(self):
        media,pin=self.consumed();foreign=self.root/self.m.ACTIVE/'operator.txt';foreign.write_bytes(b'keep')
        with self.assertRaises(ValueError):self.m.handoff(self.root,media,pin,lookup=lambda rows:None)
        self.assertEqual(foreign.read_bytes(),b'keep')

    @unittest.skipUnless(os.name=='posix','Native symlink guard')
    def test_redirected_native_directory_is_rejected(self):
        target=self.root/'target';target.mkdir();(self.root/'link').symlink_to(target,target_is_directory=True)
        with self.assertRaises(ValueError):self.m.inventory(self.root/'link')

    @unittest.skipUnless(os.name=='posix','Native managed symlink handoff')
    def test_finish_restores_only_owned_absence_after_managed_validation(self):
        media,pin=self.consumed();self.m.handoff(self.root,media,pin,lookup=lambda rows:None)
        release=self.root/'usr/share/mytellpbx-geoip/releases/fixture';(release/'BE').mkdir(parents=True)
        active=self.root/self.m.ACTIVE;active.rmdir();active.symlink_to(release/'BE',target_is_directory=True)
        status={'owner':'MyTellPBX GeoIP','status':'ready','month':'2020-01',
                'source_sha256':self.m.state(self.root)[1]['profile']['dbip']['sha256']}
        (release.parent.parent/'status.json').write_text(json.dumps(status))
        program=self.root/'usr/local/libexec/mytellpbx/geoip-update.py';program.write_bytes((ROOT/'installer/geoip-update.py').read_bytes())
        with mock.patch.object(self.m,'module',return_value=SimpleNamespace(release_info=lambda path:{'source_sha256':status['source_sha256']})):
            self.assertEqual(self.m.handoff(self.root,media,pin)['phase'],'handoff')
            value=self.m.finish(self.root,media,pin)
            self.assertEqual(value['phase'],'finished');self.assertFalse((self.root/self.m.CONFIG).exists())
            self.assertEqual(self.m.finish(self.root,media,pin)['phase'],'finished')

    def test_unknown_caller_does_not_install_shell_function_overrides(self):
        bash='C:/Program Files/Git/bin/bash.exe' if os.name=='nt' else shutil.which('bash')
        if not bash:self.skipTest('Bash unavailable')
        config=self.root/'config.sh';config.write_bytes(self.m.config_bytes(self.root))
        command='source '+str(config).replace('\\','/')+'; [ "$(type -t wget)" != function ] && [ "$(type -t curl)" != function ]'
        result=subprocess.run([bash,'-c',command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))


if __name__=='__main__':unittest.main()
