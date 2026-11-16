"""Real bootstrap extraction without external tar, network or host provisioning."""
import gzip
import hashlib
import io
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class BundleExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.archive = self.base / 'bundle.tgz'
        self.output = self.base / 'output'; self.events = self.base / 'events'; self.iteration = 0
        source = (REPO / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.definitions = self.base / 'definitions.sh'
        self.definitions.write_text(source.rsplit('\nmain "$@"', 1)[0], encoding='utf-8')

    def make_archive(self, extra=(), bad_checksum=False):
        payload = b'public fixture payload\n'; script = b'#!/bin/sh\nexit 0\n'
        files = [('fixture/payload.txt', payload), ('fixture/run.sh', script),
                 ('fixture/manifest.json', b'{}\n')]
        sums = ''.join(hashlib.sha256(data if not bad_checksum else b'wrong').hexdigest()
                       + '  ' + name.split('/', 1)[1] + '\n' for name, data in files).encode()
        files.append(('fixture/SHA256SUMS', sums))
        with tarfile.open(str(self.archive), 'w:gz') as archive:
            for name in ['fixture/', 'fixture/empty/']:
                info = tarfile.TarInfo(name); info.type = tarfile.DIRTYPE; info.mode = 0o7777
                info.uid = 12345; info.gid = 12346; archive.addfile(info)
            for name, data in files:
                info = tarfile.TarInfo(name); info.size = len(data)
                info.mode = 0o6755 if name.endswith('.sh') else 0o6640
                info.uid = 12345; info.gid = 12346
                archive.addfile(info, io.BytesIO(data))
            for item in extra:
                archive.addfile(item, io.BytesIO(b'x' * item.size) if item.isreg() else None)
        return payload

    def execute(self, wrong_pin=False, existing_output=False):
        if not existing_output:
            self.iteration += 1; self.output = self.base / ('output-' + str(self.iteration))
        values = {'LOG': self.base / 'log', 'BUNDLE_FINAL': self.archive,
                  'BUNDLE_ROOT': self.output, 'PY_BIN': sys.executable.replace('\\', '/'),
                  'MYTELLPBX_BUNDLE_SHA256': '0' * 64 if wrong_pin else hashlib.sha256(self.archive.read_bytes()).hexdigest(),
                  'MYTELL_BUNDLE_FILE': '', 'EVENTS': self.events}
        script = 'source ' + shlex.quote(self.definitions.as_posix()) + '\n'
        script += '\n'.join(k + '=' + shlex.quote(str(v).replace('\\', '/')) for k, v in values.items()) + '\n'
        script += '''check_workspace(){ :; }
say(){ :; }
tar(){ printf 'tar-forbidden\\n' >> "$EVENTS"; return 127; }
curl(){ printf 'network-forbidden\\n' >> "$EVENTS"; return 127; }
verify_bundle
'''
        run = self.base / 'run.sh'; run.write_text(script, encoding='utf-8')
        return subprocess.run([BASH, '--noprofile', '--norc', str(run)],
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, encoding='utf-8', errors='replace', timeout=30)

    def test_missing_tar_does_not_prevent_the_verified_bundle_flow(self):
        payload = self.make_archive(); result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.output / 'fixture/payload.txt').read_bytes(), payload)
        self.assertTrue((self.output / 'fixture/empty').is_dir())
        self.assertFalse(self.events.exists(), 'Bootstrap extraction must not invoke tar or a downloader')

    def test_outer_pin_still_rejects_before_extraction(self):
        self.make_archive(); result = self.execute(wrong_pin=True)
        self.assertNotEqual(result.returncode, 0); self.assertFalse(self.output.exists())
        self.assertFalse(self.events.exists())

    def test_every_internal_checksum_is_still_verified(self):
        self.make_archive(bad_checksum=True); result = self.execute()
        self.assertNotEqual(result.returncode, 0)

    def test_late_unsafe_paths_are_rejected_before_any_output(self):
        for name in ['fixture/../escaped', '/absolute', 'fixture//double', 'fixture/./dot', 'fixture/back\\slash']:
            with self.subTest(name=name):
                info = tarfile.TarInfo(name); info.size = 1
                self.make_archive([info]); result = self.execute()
                self.assertNotEqual(result.returncode, 0); self.assertFalse(self.output.exists())

    def test_links_devices_fifo_and_sparse_are_rejected_before_output(self):
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE,
                     tarfile.BLKTYPE, tarfile.GNUTYPE_SPARSE]:
            with self.subTest(kind=kind):
                info = tarfile.TarInfo('fixture/unsafe'); info.type = kind; info.linkname = 'payload.txt'
                self.make_archive([info]); result = self.execute()
                self.assertNotEqual(result.returncode, 0); self.assertFalse(self.output.exists())

    def test_duplicate_and_file_parent_are_rejected_before_output(self):
        for name in ['fixture/payload.txt', 'fixture/payload.txt/child']:
            with self.subTest(name=name):
                info = tarfile.TarInfo(name); info.size = 1
                self.make_archive([info]); result = self.execute()
                self.assertNotEqual(result.returncode, 0); self.assertFalse(self.output.exists())

    def test_expanded_size_is_bounded_before_output(self):
        info = tarfile.TarInfo('fixture/oversized'); info.size = 512 * 1024 * 1024 + 1
        self.archive.write_bytes(gzip.compress(info.tobuf() + b'\0' * 1024))
        result = self.execute(); self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

    def test_existing_extraction_directory_is_preserved(self):
        self.make_archive(); self.output.mkdir(); keep = self.output / 'retained.txt'; keep.write_bytes(b'operator')
        result = self.execute(existing_output=True); self.assertNotEqual(result.returncode, 0)
        self.assertTrue(keep.exists(), 'Existing extraction data must not be deleted')
        self.assertEqual(keep.read_bytes(), b'operator')

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX file modes and ownership')
    def test_only_safe_modes_and_current_owner_are_applied(self):
        self.make_archive(); result = self.execute(); self.assertEqual(result.returncode, 0, result.stderr)
        for name, mode in [('payload.txt', 0o644), ('run.sh', 0o755), ('manifest.json', 0o644)]:
            info = (self.output / 'fixture' / name).stat()
            self.assertEqual(stat.S_IMODE(info.st_mode), mode); self.assertEqual(info.st_uid, os.getuid())
        self.assertEqual(stat.S_IMODE((self.output / 'fixture').stat().st_mode), 0o755)


if __name__ == '__main__': unittest.main()
