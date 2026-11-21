import configparser
import hashlib
import importlib.util
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


NATIVE = Path(__file__).resolve().parents[1] / 'installer/vendor-native'
SPEC = importlib.util.spec_from_file_location('vendor_mirror', str(NATIVE / 'vendor-mirror.py'))
MIRROR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIRROR)
NS = '{http://www.metalinker.org/}'


class VendorRepositoryMirrorTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name).resolve()
        self.repo = self.root / 'repos'
        self.repo.mkdir()
        self.state = self.root / 'snapshot' / 'r7'
        script = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        pattern = r'cat > "\$repo_dir/([^"]+\.repo)" <<EOF \|\| return 1\n(.*?)\nEOF'
        self.original = {name: text.replace('\\$basearch', '$basearch') + '\n'
                         for name, text in re.findall(pattern, script, re.S)}
        self.assertEqual(set(self.original), set(MIRROR.FILES))
        for name, text in self.original.items():
            (self.repo / name).write_text(text, encoding='utf-8')

    def test_all_enabled_native_repos_pin_repomd_and_use_local_signer_keys(self):
        MIRROR.configure(self.repo, self.state)
        self.assertEqual(len(list(self.state.glob('*.metalink'))), 9)
        for name, repositories in MIRROR.FILES.items():
            config = configparser.ConfigParser(interpolation=None)
            config.read(str(self.repo / name), encoding='utf-8')
            original = configparser.ConfigParser(interpolation=None)
            original.read_string(self.original[name])
            for repo in original.sections():
                if repo not in repositories:
                    self.assertEqual(dict(original[repo]), dict(config[repo]))
                    continue
                stanza = config[repo]
                self.assertEqual(stanza['gpgcheck'], '1')
                self.assertEqual(stanza['sslverify'], '1')
                self.assertEqual(stanza['skip_if_unavailable'], '0')
                self.assertNotIn('mirrorlist', stanza)
                self.assertNotIn('baseurl', stanza)
                path = self.state / (repo + '.metalink')
                self.assertEqual(stanza['metalink'], path.as_uri())
                checked = ET.fromstring(path.read_bytes()).find(NS + 'files/' + NS + 'file')
                self.assertEqual(checked.get('name'), 'repomd.xml')
                pin = checked.find(NS + 'verification/' + NS + 'hash')
                self.assertEqual(pin.get('type'), 'sha256')
                self.assertEqual(pin.text, MIRROR.SNAPSHOTS[repo][1])
                resource_path = '/issabel/' + MIRROR.SNAPSHOTS[repo][0] + '/repodata/repomd.xml'
                urls = [item.text for item in checked.findall(NS + 'resources/' + NS + 'url')]
                self.assertEqual(urls, ['https://repo.us.issabel.org' + resource_path,
                                        'http://repo.issabel.org' + resource_path])
                key_names = ['issabel.asc', 'legacy-elastix.asc'] if repo == 'issabel-updates' else ['issabel.asc']
                self.assertEqual(stanza['gpgkey'].split(), [(self.state / key).as_uri() for key in key_names])
                for key in key_names:
                    self.assertEqual(hashlib.sha256((self.state / key).read_bytes()).hexdigest(), MIRROR.KEYS[key])

    def test_repeat_is_stable_and_rejects_modified_trust_files(self):
        MIRROR.configure(self.repo, self.state)
        configured = {p.name: p.read_bytes() for p in self.repo.glob('*.repo')}
        MIRROR.configure(self.repo, self.state)
        (self.state / 'issabel.asc').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'differs'):
            MIRROR.configure(self.repo, self.state)
        self.assertEqual({p.name: p.read_bytes() for p in self.repo.glob('*.repo')}, configured)

    def test_unreviewed_enabled_sections_refused_before_repo_writes(self):
        file = self.repo / 'commercial-addons.repo'
        with file.open('a') as handle:
            handle.write('\n[other]\nenabled=1\n')
        previous = {p.name: p.read_bytes() for p in self.repo.glob('*.repo')}
        with self.assertRaisesRegex(ValueError, 'Unexpected enabled'):
            MIRROR.configure(self.repo, self.state)
        self.assertEqual({p.name: p.read_bytes() for p in self.repo.glob('*.repo')}, previous)
        self.assertFalse(list(self.state.iterdir()))

    @unittest.skipUnless(os.name == 'posix', 'Unix publication modes')
    def test_private_preflight_and_public_persistent_material_respect_their_scope(self):
        original_mode = os.umask(0o077)
        try:
            MIRROR.configure(self.repo, self.repo / '.mytel-vendor')
            self.assertEqual((self.repo / '.mytel-vendor').stat().st_mode & 0o777, 0o700)
            MIRROR.configure(self.repo, self.state)
            self.assertEqual(self.state.stat().st_mode & 0o777, 0o755)
            self.assertEqual(self.state.parent.stat().st_mode & 0o777, 0o755)
            self.assertEqual((self.state / 'issabel.asc').stat().st_mode & 0o777, 0o644)
        finally:
            os.umask(original_mode)
