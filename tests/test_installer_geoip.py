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
        return geoip.convert_csv(self.source, self.legacy, min_rows=4)

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
            geoip.convert_csv(self.source, self.legacy, min_rows=4)
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
        release = root / 'usr/share/mytellpbx-geoip/releases/test'
        (release / 'BE').mkdir(parents=True)
        (release / 'BE/US.iv4').write_bytes(struct.pack('>II', 134744064, 134744319))
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

    def test_cron_install_refuses_unknown_source_without_writing(self):
        root = self.base / 'root'
        cron = root / 'etc/cron.daily/geoip_update.sh'
        cron.parent.mkdir(parents=True)
        cron.write_bytes(b'#!/bin/sh\necho owner customization\n')
        with self.assertRaises(ValueError):
            geoip.install(root, REPO / 'installer/geoip-update.py')
        self.assertEqual(cron.read_bytes(), b'#!/bin/sh\necho owner customization\n')
        self.assertFalse((root / 'usr/local/libexec/mytellpbx/geoip-update.py').exists())


if __name__ == '__main__':
    unittest.main()
