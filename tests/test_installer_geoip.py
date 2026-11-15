"""Offline GeoIP conversion/build/activation contracts; never changes firewall rules."""
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mytel_geoip', str(REPO / 'installer/geoip-update.py'))
geoip = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(geoip)

CSV = ('1.0.0.0,1.0.0.255,AU\n8.8.8.0,8.8.8.255,US\n'
       '2001:db8::,2001:db8::ffff,IR\n2001:db9::,2001:db9::ffff,US\n')


class GeoipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mytel-geoip-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'country.csv.gz'
        self.source.write_bytes(gzip.compress(CSV.encode('utf-8')))
        self.legacy = self.base / 'legacy.csv'

    def convert(self, text=CSV):
        self.source.write_bytes(gzip.compress(text.encode('utf-8')))
        return geoip.convert_csv(self.source, self.legacy, min_rows=4, min_countries=3)

    def build_fixture(self):
        info = self.convert()
        stage = self.base / 'release'
        for endian in ['BE', 'LE']:
            (stage / endian).mkdir(parents=True)
        for name in info['files']:
            (stage / name).write_bytes(b'')
        (stage / 'BE/AU.iv4').write_bytes(struct.pack('>II', 16777216, 16777471))
        (stage / 'LE/AU.iv4').write_bytes(struct.pack('<II', 16777216, 16777471))
        (stage / 'BE/US.iv4').write_bytes(struct.pack('>II', 134744064, 134744319))
        (stage / 'LE/US.iv4').write_bytes(struct.pack('<II', 134744064, 134744319))
        for country, first in [('IR', 0x0db8), ('US', 0x0db9)]:
            start = struct.pack('>8H', 0x2001, first, 0, 0, 0, 0, 0, 0)
            end = struct.pack('>8H', 0x2001, first, 0, 0, 0, 0, 0, 0xffff)
            (stage / ('BE/' + country + '.iv6')).write_bytes(start + end)
            (stage / ('LE/' + country + '.iv6')).write_bytes(
                struct.pack('<4I', *struct.unpack('>4I', start)) + struct.pack('<4I', *struct.unpack('>4I', end)))
        return stage, info

    def test_converts_dbip_to_actual_legacy_builder_fields_without_losing_ipv6(self):
        info = self.convert()
        rows = list(csv.reader(io.StringIO(self.legacy.read_text(encoding='utf-8'))))
        self.assertEqual(info['rows'], 4)
        self.assertEqual(info['families'], {'4': 2, '6': 2})
        self.assertEqual(rows[0], ['1.0.0.0', '1.0.0.255', '16777216', '16777471', 'AU', 'AU'])
        self.assertEqual(rows[2][0], '2001:0db8:0000:0000:0000:0000:0000:0000')
        self.assertEqual(set(info['countries']), {'AU', 'IR', 'US'})

    def test_invalid_reversed_overlapping_mixed_family_or_unsafe_country_is_rejected(self):
        for bad in ['x,y,US\n', '8.8.8.8,8.8.8.0,US\n', '1.0.0.0,::1,US\n',
                    '1.0.0.0,1.0.0.255,../US\n', '1.0.0.0,1.0.0.255,us\n',
                    '1.0.0.0,1.0.0.255,US,extra\n',
                    '1.0.0.0,1.0.0.255,US\n1.0.0.1,1.0.0.2,AU\n']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.convert(bad)

    def test_truncated_gzip_empty_partial_and_single_family_data_are_rejected(self):
        self.source.write_bytes(self.source.read_bytes()[:-8])
        with self.assertRaises((ValueError, EOFError, OSError)):
            geoip.convert_csv(self.source, self.legacy, min_rows=4, min_countries=3)
        for text in ['', CSV.splitlines()[0] + '\n', '\n'.join(CSV.splitlines()[:2]) + '\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.convert(text)

    def test_every_packed_country_family_endian_is_verified(self):
        stage, info = self.build_fixture()
        self.assertEqual(geoip.validate_build(stage, info['files']), info['files'])
        target = stage / 'BE/US.iv4'
        target.write_bytes(target.read_bytes()[:-1])
        with self.assertRaises(ValueError):
            geoip.validate_build(stage, info['files'])

    def test_extra_or_wrong_endian_build_is_rejected(self):
        stage, info = self.build_fixture()
        (stage / 'BE/US.iv4').write_bytes((stage / 'LE/US.iv4').read_bytes())
        with self.assertRaises(ValueError):
            geoip.validate_build(stage, info['files'])
        (stage / 'BE/US.iv4').write_bytes(struct.pack('>II', 134744064, 134744319))
        (stage / 'BE/ZZ.iv4').write_bytes(b'')
        with self.assertRaises(ValueError):
            geoip.validate_build(stage, info['files'])

    def test_download_is_fixed_https_bounded_and_rejects_redirect_or_html(self):
        def runner(argv, **kwargs):
            self.assertIn('https://download.db-ip.com/free/dbip-country-lite-2026-11.csv.gz', argv)
            self.assertIn('--max-time', argv)
            self.assertIn('--connect-timeout', argv)
            self.assertNotIn('-k', argv)
            self.assertLessEqual(kwargs['timeout'], 100)
            Path(argv[argv.index('--output') + 1]).write_bytes(gzip.compress(CSV.encode()))
            return mock.Mock(returncode=0, stdout='200', stderr='')
        output = self.base / 'download.gz'
        geoip.download_month(output, '2026-11', runner=runner)
        self.assertEqual(gzip.decompress(output.read_bytes()).decode(), CSV)
        with self.assertRaises(ValueError):
            geoip.download_month(output, '2026-11/../../bad', runner=runner)
        with self.assertRaises(ValueError):
            geoip.download_month(output, '2026-11', runner=lambda *a, **k: mock.Mock(returncode=0, stdout='302', stderr=''))
        def html(argv, **kwargs):
            output.write_bytes(b'<html>not country data</html>')
            return mock.Mock(returncode=0, stdout='200', stderr='')
        with self.assertRaises(ValueError):
            geoip.download_month(output, '2026-11', runner=html)

    def test_csv_field_and_coverage_limits_reject_bombs_and_partial_data(self):
        with self.assertRaises((ValueError, csv.Error)):
            self.convert('x' * 10000 + ',1.1.1.1,US\n')
        self.source.write_bytes(gzip.compress(CSV.encode('utf-8')))
        with self.assertRaises(ValueError):
            geoip.convert_csv(self.source, self.legacy, min_rows=1, min_countries=200)

    @unittest.skipUnless(os.name == 'posix' and os.environ.get('MT_GEOIP_TEST_BUILDER'), 'Native reviewed installed Perl builder')
    def test_actual_installed_legacy_builder_matches_independent_packed_bytes(self):
        builder = Path(os.environ['MT_GEOIP_TEST_BUILDER'])
        geoip.verify_builder(builder)
        stage, info = self.build_fixture()
        expected = {name: (stage / name).read_bytes() for name in info['files']}
        actual = self.base / 'native-output'
        actual.mkdir()
        result = subprocess.run(['/usr/bin/perl', str(builder), '-D', str(actual), str(self.legacy)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        self.assertEqual(geoip.validate_build(actual, info['files']), info['files'])
        self.assertEqual({name: (actual / name).read_bytes() for name in info['files']}, expected)

    def test_builder_source_drift_is_rejected_before_execution(self):
        path = self.base / 'builder'
        path.write_bytes(b'not the installed reviewed builder')
        with self.assertRaises(ValueError):
            geoip.verify_builder(path)

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX symlink activation contract')
    def test_flat_network_order_activation_is_atomic_and_unknown_data_is_preserved(self):
        root = self.base / 'root'
        active = root / 'usr/share/xt_geoip'
        active.mkdir(parents=True)
        stage, info = self.build_fixture()
        release = root / 'usr/share/mytellpbx-geoip/releases/test'
        release.parent.mkdir(parents=True)
        stage.rename(release)
        info.update(owner=geoip.OWNER, layout='flat-network-BE', builder_sha256=geoip.BUILDER_SHA256)
        (release / 'manifest.json').write_text(json.dumps(info), encoding='utf-8')
        geoip.activate(root, release)
        self.assertTrue(active.is_symlink())
        self.assertEqual(active.resolve(), release / 'BE')
        self.assertTrue((active / 'US.iv4').is_file())
        self.assertFalse((active / 'BE').exists())
        self.assertEqual(geoip.activate(root, release), False)
        active.unlink()
        active.mkdir()
        (active / 'owner-data').write_bytes(b'retain')
        with self.assertRaises(ValueError):
            geoip.activate(root, release)
        self.assertEqual((active / 'owner-data').read_bytes(), b'retain')

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX atomic pointer contract')
    def test_failed_atomic_switch_keeps_previous_valid_database(self):
        root = self.base / 'root'
        active = root / 'usr/share/xt_geoip'
        active.mkdir(parents=True)
        stage, info = self.build_fixture()
        release = root / 'usr/share/mytellpbx-geoip/releases/first'
        release.parent.mkdir(parents=True)
        stage.rename(release)
        info.update(owner=geoip.OWNER, layout='flat-network-BE', builder_sha256=geoip.BUILDER_SHA256)
        (release / 'manifest.json').write_text(json.dumps(info), encoding='utf-8')
        geoip.activate(root, release)
        import shutil
        next_release = release.parent / 'second'
        shutil.copytree(str(release), str(next_release))
        replace = os.replace
        def fail_pointer(source, destination):
            if Path(destination) == active:
                raise OSError('fixture switch failure')
            return replace(source, destination)
        with mock.patch.object(geoip.os, 'replace', side_effect=fail_pointer), self.assertRaises(OSError):
            geoip.activate(root, next_release)
        self.assertEqual(active.resolve(), release / 'BE')
        self.assertEqual((active / 'US.iv4').read_bytes(), struct.pack('>II', 134744064, 134744319))

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX managed path ownership')
    def test_symlinked_state_parent_is_refused_without_chmod_or_writes(self):
        root = self.base / 'root'
        (root / 'var/lib').mkdir(parents=True)
        victim = self.base / 'victim'
        victim.mkdir(mode=0o755)
        (root / geoip.STATE).symlink_to(victim)
        before = victim.stat().st_mode
        with self.assertRaises(ValueError):
            geoip.update(root)
        self.assertEqual(list(victim.iterdir()), [])
        self.assertEqual(victim.stat().st_mode, before)

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX existing-data failure retention')
    def test_failed_monthly_download_retains_live_pointer_and_previous_status(self):
        root = self.base / 'root'
        (root / geoip.ACTIVE).mkdir(parents=True)
        stage, info = self.build_fixture()
        release = root / geoip.RELEASES / 'prior'
        release.parent.mkdir(parents=True)
        stage.rename(release)
        info.update(owner=geoip.OWNER, layout='flat-network-BE', builder_sha256=geoip.BUILDER_SHA256,
                    month='2000-01', created_utc='2000-01-01T00:00:00Z', source_sha256='a' * 64,
                    source_url='https://download.db-ip.com/free/dbip-country-lite-2000-01.csv.gz')
        (release / 'manifest.json').write_text(json.dumps(info), encoding='utf-8')
        geoip.activate(root, release)
        geoip.publish_status(root, info)
        status = root / 'usr/share/mytellpbx-geoip/status.json'
        before = status.read_bytes()
        with mock.patch.object(geoip, 'verify_builder'), mock.patch.object(geoip, 'download_month', side_effect=ValueError('fixture network failure')):
            with self.assertRaises(ValueError):
                geoip.update(root)
        self.assertEqual((root / geoip.ACTIVE).resolve(), release / 'BE')
        self.assertEqual(status.read_bytes(), before)
        self.assertEqual((release / 'BE/US.iv4').read_bytes(), struct.pack('>II', 134744064, 134744319))

    def test_public_status_is_provider_attribution_only_and_has_no_secret_or_private_paths(self):
        info = self.convert()
        info.update(month='2026-11', created_utc='2026-11-15T18:00:00Z', source_sha256='a' * 64,
                    source_url='https://download.db-ip.com/free/dbip-country-lite-2026-11.csv.gz')
        result = geoip.publish_status(self.base / 'root', info)
        self.assertEqual(result['provider'], 'DB-IP Country Lite')
        self.assertEqual(result['license'], 'CC-BY-4.0')
        self.assertEqual(result['country_count'], 3)
        self.assertEqual(result['layout'], 'flat-network-BE')
        saved = self.base / 'root/usr/share/mytellpbx-geoip/status.json'
        self.assertEqual(json.loads(saved.read_text(encoding='utf-8')), result)
        self.assertFalse(any(key in result for key in ('password', 'key', 'secret', 'root', 'program')))

    def test_actual_publisher_normalizes_prior_fractional_utc_to_the_ui_contract(self):
        info = self.convert()
        info.update(month='2026-11', created_utc='2026-11-15T18:00:00.123456Z', source_sha256='a' * 64,
                    source_url='https://download.db-ip.com/free/dbip-country-lite-2026-11.csv.gz')
        result = geoip.publish_status(self.base / 'root', info)
        self.assertEqual(result['updated_utc'], '2026-11-15T18:00:00Z')
        self.assertRegex(result['updated_utc'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')

    def test_metadata_failure_reports_active_valid_data_and_retry_repairs_both_files(self):
        info = self.convert()
        root = self.base / 'root'
        info.update(month='2026-11', created_utc='2026-11-15T18:00:00Z', source_sha256='a' * 64,
                    source_url='https://download.db-ip.com/free/dbip-country-lite-2026-11.csv.gz')
        atomic = geoip.atomic
        def fail_latest(path, *args, **kwargs):
            if Path(path).name == 'latest.json':
                raise OSError('fixture metadata failure')
            return atomic(path, *args, **kwargs)
        with mock.patch.object(geoip, 'atomic', side_effect=fail_latest):
            with self.assertRaisesRegex(ValueError, 'data is active; status publication incomplete'):
                geoip.publish_metadata(root, info)
        geoip.publish_metadata(root, info)
        self.assertEqual(json.loads((root / geoip.STATE / 'latest.json').read_text(encoding='utf-8')), info)
        self.assertEqual(json.loads((root / 'usr/share/mytellpbx-geoip/status.json').read_text(encoding='utf-8'))['updated_utc'], info['created_utc'])

    def test_cron_install_refuses_unknown_source_without_writing(self):
        root = self.base / 'root'
        cron = root / 'etc/cron.daily/geoip_update.sh'
        cron.parent.mkdir(parents=True)
        cron.write_bytes(b'#!/bin/sh\necho owner customization\n')
        with self.assertRaises(ValueError):
            geoip.install(root, REPO / 'installer/geoip-update.py')
        self.assertEqual(cron.read_bytes(), b'#!/bin/sh\necho owner customization\n')
        self.assertFalse((root / 'usr/local/libexec/mytellpbx/geoip-update.py').exists())

    def test_known_cron_install_is_backed_up_and_idempotent_then_rejects_helper_drift(self):
        root = self.base / 'root'
        cron = root / geoip.CRON
        cron.parent.mkdir(parents=True)
        vendor = b'#!/bin/sh\necho vendor fixture\n'
        cron.write_bytes(vendor)
        with mock.patch.object(geoip, 'VENDOR_CRON_SHA256', hashlib.sha256(vendor).hexdigest()), mock.patch.object(geoip, 'verify_builder'):
            geoip.install(root, REPO / 'installer/geoip-update.py')
            self.assertEqual(cron.read_bytes(), geoip.WRAPPER)
            backups = list((root / 'var/backups/mytellpbx/geoip').iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), vendor)
            geoip.install(root, REPO / 'installer/geoip-update.py')
            self.assertEqual(len(list(backups[0].parent.iterdir())), 1)
            program = root / geoip.PROGRAM
            program.write_bytes(b'owner changed this updater')
            with self.assertRaises(ValueError):
                geoip.install(root, REPO / 'installer/geoip-update.py')
            self.assertEqual(program.read_bytes(), b'owner changed this updater')
            if os.name == 'posix':
                self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
                self.assertEqual(cron.stat().st_mode & 0o777, 0o755)

    def test_status_wiring_is_source_guarded_backed_up_and_idempotent(self):
        root = self.base / 'root'
        cron = root / geoip.CRON
        cron.parent.mkdir(parents=True)
        vendor_cron = b'#!/bin/sh\necho vendor fixture\n'
        cron.write_bytes(vendor_cron)
        target = root / 'var/www/html/modules/sec_geoip_key/index.php'
        target.parent.mkdir(parents=True)
        vendor_status = b'<?php echo "vendor status fixture";'
        target.write_bytes(vendor_status)
        payload = self.base / 'status.php'
        payload.write_bytes(b'<?php echo "read-only provider fixture";')
        with mock.patch.object(geoip, 'VENDOR_CRON_SHA256', hashlib.sha256(vendor_cron).hexdigest()), \
                mock.patch.object(geoip, 'VENDOR_STATUS_SHA256', hashlib.sha256(vendor_status).hexdigest()), \
                mock.patch.object(geoip, 'verify_builder'):
            geoip.install(root, REPO / 'installer/geoip-update.py', payload)
            self.assertEqual(target.read_bytes(), payload.read_bytes())
            backups = list((root / 'var/backups/mytellpbx/geoip').iterdir())
            self.assertEqual(len(backups), 2)
            self.assertIn(vendor_status, [item.read_bytes() for item in backups])
            geoip.install(root, REPO / 'installer/geoip-update.py', payload)
            target.write_bytes(b'<?php echo "owner edit";')
            with self.assertRaises(ValueError):
                geoip.install(root, REPO / 'installer/geoip-update.py', payload)
            self.assertEqual(target.read_bytes(), b'<?php echo "owner edit";')

    def test_install_metadata_write_failure_is_recoverable_with_the_same_source(self):
        root = self.base / 'root'
        cron = root / geoip.CRON
        cron.parent.mkdir(parents=True)
        vendor = b'#!/bin/sh\necho vendor fixture\n'
        cron.write_bytes(vendor)
        atomic = geoip.atomic
        def fail_receipt(path, *args, **kwargs):
            if Path(path).name == 'install.json':
                raise OSError('fixture receipt write failure')
            return atomic(path, *args, **kwargs)
        with mock.patch.object(geoip, 'VENDOR_CRON_SHA256', hashlib.sha256(vendor).hexdigest()), mock.patch.object(geoip, 'verify_builder'):
            with mock.patch.object(geoip, 'atomic', side_effect=fail_receipt), self.assertRaises(OSError):
                geoip.install(root, REPO / 'installer/geoip-update.py')
            self.assertEqual(cron.read_bytes(), geoip.WRAPPER)
            geoip.install(root, REPO / 'installer/geoip-update.py')
            self.assertEqual(json.loads((root / geoip.STATE / 'install.json').read_text(encoding='utf-8'))['owner'], geoip.OWNER)


if __name__ == '__main__':
    unittest.main()
