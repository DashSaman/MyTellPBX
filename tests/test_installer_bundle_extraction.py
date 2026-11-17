"""Real native-bootstrap extraction with bounded inputs, no external tar or network."""
import gzip
import os
from pathlib import Path
import tarfile
import unittest

from native_bootstrap_fixture import BASH, BootstrapFixture


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class BundleExtractionTests(BootstrapFixture, unittest.TestCase):
    def execute(self, wrong_pin=False):
        return self.shell('''
tar(){ printf 'tar-forbidden\\n' >> "$EVENTS"; return 127; }
curl(){ printf 'network-forbidden\\n' >> "$EVENTS"; return 127; }
download_bundle
extract_bundle
''', {'MYTELLPBX_BUNDLE_SHA256': '0' * 64} if wrong_pin else None)

    def test_missing_tar_does_not_prevent_the_verified_bundle_flow(self):
        files = self.make_archive()
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.payload / 'payload.txt').read_bytes(), files['payload.txt'])
        self.assertTrue((self.payload / 'empty').is_dir())
        self.assertFalse(self.events.exists(), 'No downloader or external tar may run')

    def test_outer_pin_still_rejects_before_extraction(self):
        self.make_archive()
        result = self.execute(wrong_pin=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.events.exists())

    def test_every_internal_checksum_is_still_verified(self):
        self.make_archive(bad_checksum=True)
        result = self.execute()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'internal checksums failed', result.stderr)

    def test_late_unsafe_paths_are_rejected_before_any_output(self):
        for name in (self.prefix + '/../escaped', '/absolute', self.prefix + '//double',
                     self.prefix + '/./dot', self.prefix + '/back\\slash'):
            with self.subTest(name=name):
                info = tarfile.TarInfo(name)
                info.size = 1
                self.make_archive([info])
                result = self.execute()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())

    def test_links_devices_fifo_and_sparse_are_rejected_before_output(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE,
                     tarfile.FIFOTYPE, tarfile.GNUTYPE_SPARSE):
            with self.subTest(kind=kind):
                info = tarfile.TarInfo(self.prefix + '/unsafe')
                info.type, info.linkname = kind, '/outside'
                self.make_archive([info])
                result = self.execute()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())

    def test_duplicate_and_file_parent_are_rejected_before_output(self):
        for name in ('payload.txt', 'payload.txt/child'):
            with self.subTest(name=name):
                info = tarfile.TarInfo(self.prefix + '/' + name)
                info.size = 1
                self.make_archive([info])
                self.assertNotEqual(self.execute().returncode, 0)
                self.assertFalse(self.output.exists())

    def test_expanded_size_is_bounded_before_output(self):
        # Only an oversized header is stored; no oversized body is allocated.
        info = tarfile.TarInfo(self.prefix + '/large')
        info.size = 128 * 1024 * 1024 + 1
        with gzip.open(self.archive, 'wb') as outgoing:
            outgoing.write(info.tobuf() + b'\0' * 1024)
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertFalse(self.output.exists())

    def test_existing_extraction_directory_is_preserved(self):
        self.make_archive()
        self.output.mkdir()
        marker = self.output / 'owner'
        marker.write_bytes(b'preserve')
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertEqual(marker.read_bytes(), b'preserve')
        self.assertEqual(list(self.output.iterdir()), [marker])

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX file modes and ownership')
    def test_only_safe_modes_and_current_owner_are_applied(self):
        self.make_archive()
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.payload / 'run.sh').stat().st_mode & 0o7777, 0o755)
        self.assertEqual((self.payload / 'payload.txt').stat().st_mode & 0o7777, 0o644)
        self.assertEqual((self.payload / 'payload.txt').stat().st_uid, os.geteuid())
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)


if __name__ == '__main__':
    unittest.main()
