import configparser
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import subprocess
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock


NATIVE = Path(__file__).resolve().parents[1] / 'installer/vendor-native'
SPEC = importlib.util.spec_from_file_location('vendor_mirror', str(NATIVE / 'vendor-mirror.py'))
MIRROR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIRROR)


class VendorRepositoryTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.work = Path(work.name).resolve()
        self.state = self.work / 'state'
        self.repo = self.work / 'repos'
        self.repo.mkdir()
        self.archive = self.work / MIRROR.ASSET

    def make_archive(self, extra=(), packages=None, omit=None):
        contents = [('Packages/native-1.0.el8.x86_64.rpm', b'signed fixture'),
                    ('repodata/repomd.xml', b'fixture metadata'),
                    ('licenses/ioncube-loaders-EULA.txt', b'fixture notice')]
        contents += [(name, b'signed package fixture') for name in sorted(MIRROR.ESSENTIAL) if name != omit]
        contents.extend(extra)
        if packages is None:
            packages = sum(name.endswith('.rpm') for name, _ in contents)
        with tarfile.open(str(self.archive), 'w:gz') as out:
            for name, payload in contents:
                member = tarfile.TarInfo(name)
                member.size = len(payload)
                out.addfile(member, io.BytesIO(payload))
        data = self.archive.read_bytes()
        return dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), packages=packages)

    def configure(self, pin):
        MIRROR.configure(self.repo, self.state, self.work, pin)

    def test_archive_digest_and_repos_are_pinned_across_reruns(self):
        pin = self.make_archive()
        self.configure(pin)
        definitions = {p.name: p.read_bytes() for p in self.repo.glob('*.repo')}
        self.assertEqual(set(definitions), set(MIRROR.FILES))
        self.configure(pin)
        self.assertEqual({p.name: p.read_bytes() for p in self.repo.glob('*.repo')}, definitions)
        config = configparser.ConfigParser(interpolation=None)
        config.read([str(p) for p in self.repo.glob('*.repo')])
        self.assertEqual(config.sections(), ['mytelpbx-packages', 'mytelpbx-builds'])
        builds = config['mytelpbx-builds']
        project_key = (self.state / MIRROR.PROJECT_KEY).as_uri()
        self.assertEqual(builds['baseurl'], (self.state / 'repository').as_uri())
        self.assertEqual(builds['gpgcheck'], '1')
        self.assertEqual(builds['skip_if_unavailable'], '0')
        self.assertEqual(builds['includepkgs'], 'asterisk20,asterisk20-*,dahdi-firmware,xtables-addons,issabel-geoip')
        self.assertEqual(builds['gpgkey'], project_key)
        source = config['mytelpbx-packages']
        self.assertEqual(source['baseurl'], (self.state / 'repository').as_uri())
        self.assertEqual(source['gpgcheck'], '1')
        self.assertEqual(source['skip_if_unavailable'], '0')
        self.assertNotIn(project_key, source['gpgkey'])
        self.assertEqual(source['excludepkgs'], 'asterisk20,asterisk20-*,dahdi-firmware,xtables-addons,issabel-geoip')
        for name, digest in MIRROR.KEYS.items():
            key = self.state / name
            section = builds if name == MIRROR.PROJECT_KEY else source
            self.assertIn(key.as_uri(), section['gpgkey'].split())
            self.assertEqual(hashlib.sha256(key.read_bytes()).hexdigest(), digest)

    def test_preflight_only_extracts_metadata_and_full_install_reuses_verified_archive(self):
        pin = self.make_archive()
        private = self.repo / '.mytel-vendor'
        MIRROR.configure(self.repo, private, self.work, pin)
        self.assertTrue((private / 'repository/repodata/repomd.xml').is_file())
        self.assertFalse((private / 'repository/Packages').exists())
        with mock.patch.object(MIRROR.subprocess, 'run', side_effect=AssertionError('second download')):
            self.configure(pin)
        self.assertTrue((self.state / 'repository/Packages/native-1.0.el8.x86_64.rpm').is_file())

    def test_partial_download_resumes_only_against_the_github_release(self):
        pin = self.make_archive()
        contents = self.archive.read_bytes()
        self.archive.unlink()
        calls = []
        def curl(command, stdout):
            calls.append(command)
            part = Path(command[command.index('--output') + 1])
            if len(calls) == 1:
                part.write_bytes(contents[:29])
                return subprocess.CompletedProcess(command, 28, stdout=b'200')
            self.assertEqual(part.read_bytes(), contents[:29])
            with part.open('ab') as out:
                out.write(contents[29:])
            return subprocess.CompletedProcess(command, 0, stdout=b'206')
        output = io.StringIO()
        with mock.patch.object(MIRROR.subprocess, 'run', side_effect=curl), redirect_stdout(output):
            self.configure(pin)
        self.assertEqual(output.getvalue().splitlines(), [
            '  Downloading MytelPBX packages from GitHub (0.0 MiB)...',
            '    Retrying package download...',
        ])
        self.assertEqual(len(calls), 2)
        for command in calls:
            self.assertEqual(command[-1], 'https://github.com/DashSaman/MyTellPBX/releases/download/v7.7.0-r8/' + MIRROR.ASSET)
            self.assertIn('--continue-at', command)
            self.assertEqual(command[command.index('--proto-redir') + 1], '=https')
        self.assertFalse((self.work / (MIRROR.ASSET + '.part')).exists())

    def test_final_transfer_failure_records_numeric_evidence_privately(self):
        pin = self.make_archive()
        self.archive.unlink()
        responses = [subprocess.CompletedProcess([], 22, stdout=b'503'),
                     subprocess.CompletedProcess([], 28, stdout=b'000'),
                     subprocess.CompletedProcess([], 35, stdout=b'https://name:private@example.invalid')]
        output = io.StringIO()
        with mock.patch.object(MIRROR.subprocess, 'run', side_effect=responses), redirect_stdout(output):
            with self.assertRaisesRegex(ValueError, 'GitHub package download failed'):
                self.configure(pin)
        attempts = (self.work / 'github-package-transfer.log').read_text()
        self.assertEqual(attempts.splitlines(), [
            'attempt=1 curl=22 http=503 bytes=0', 'attempt=2 curl=28 http=000 bytes=0',
            'attempt=3 curl=35 http=unknown bytes=0'])
        self.assertNotIn('curl=', output.getvalue())
        self.assertNotIn('private@example', attempts + output.getvalue())
        self.assertFalse(list(self.repo.iterdir()))

    def test_tampered_archive_and_installed_files_fail_closed(self):
        pin = self.make_archive()
        with self.assertRaisesRegex(ValueError, 'match the release'):
            self.configure(dict(pin, sha256='0' * 64))
        self.assertFalse(list(self.repo.iterdir()))
        self.configure(pin)
        path = self.state / 'repository' / 'Packages/native-1.0.el8.x86_64.rpm'
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.configure(pin)

    def test_rejects_outside_members_and_incomplete_snapshot_before_repo_writes(self):
        pin = self.make_archive(extra=[('Packages/../../evil', b'bad')])
        with self.assertRaisesRegex(ValueError, 'Unexpected entry'):
            self.configure(pin)
        pin = self.make_archive(packages=4)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            self.configure(pin)
        self.assertFalse(list(self.repo.iterdir()))
        self.assertFalse((self.state / 'repository').exists())

    def test_rejects_non_project_firmware_from_archive(self):
        pin = self.make_archive(extra=[('Packages/dahdi-firmware-2.11.1-1.noarch.rpm', b'other payload')], packages=4)
        with self.assertRaisesRegex(ValueError, 'Unexpected hardware package'):
            self.configure(pin)
        self.assertFalse(list(self.repo.iterdir()))

    def test_original_country_database_is_rejected(self):
        pin = self.make_archive(extra=[('Packages/issabel-geoip-1.6.12-3.x86_64.rpm', b'old')])
        with self.assertRaisesRegex(ValueError, 'Unexpected country database'):
            self.configure(pin)

    def test_original_asterisk_binary_cannot_enter_source_built_release(self):
        pin = self.make_archive(extra=[('Packages/asterisk20-core-20.12.0-1.el8.x86_64.rpm', b'old')], packages=4)
        with self.assertRaisesRegex(ValueError, 'different build'):
            self.configure(pin)

    def test_each_essential_rpm_must_exist_even_when_archive_count_is_correct(self):
        self.assertIn('Packages/asterisk20-core-20.12.0-2.mytel.el8.x86_64.rpm', MIRROR.ESSENTIAL)
        self.assertIn('Packages/asterisk-pr-sounds-1.1-0.noarch.rpm', MIRROR.ESSENTIAL)
        for omitted in sorted(MIRROR.ESSENTIAL):
            with self.subTest(omitted=omitted):
                pin = self.make_archive(omit=omitted)
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    self.configure(pin)
                self.assertFalse(list(self.repo.iterdir()))

    def test_existing_signer_tamper_is_rejected(self):
        pin = self.make_archive()
        self.configure(pin)
        (self.state / 'issabel.asc').write_bytes(b'unapproved')
        with self.assertRaisesRegex(ValueError, 'key differs'):
            self.configure(pin)
