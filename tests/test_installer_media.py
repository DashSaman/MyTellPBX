"""Local ISO media contracts. No packages, network, services or host state."""
import hashlib
import gzip
import importlib.util
import json
import os
import contextlib
import io
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'media'; self.root.mkdir()
        self.data = {'bootstrap': 'bootstrap/install.sh', 'bundle': 'payload/pbx.tgz',
                     'desk': 'desk/desk.tgz', 'node': 'runtime/node.tar.xz'}
        self.manifest = dict(schema=1, owner='MyTellPBX', platform='rocky8.10-x86_64',
                             files={}, wheels=['wheels/one.whl'],
                             geoip={'path': 'geoip/country.csv.gz', 'month': '2026-11'},
                             repositories=[dict(id='mytel-media-baseos', path='repos/baseos', gpgkey='keys/os.asc')],
                             **self.data)
        for name in list(self.data.values()) + self.manifest['wheels'] + ['geoip/country.csv.gz', 'keys/os.asc',
                'repos/baseos/repodata/repomd.xml', 'repos/baseos/Packages/signed.rpm']:
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(name.encode())
            self.manifest['files'][name] = dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size)
        source = ROOT / 'installer/media.py'
        self.assertTrue(source.is_file(), 'Offline media loader is missing')
        spec = importlib.util.spec_from_file_location('installer_media_fixture', str(source))
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)

    def save(self):
        raw = (json.dumps(self.manifest, sort_keys=True) + '\n').encode()
        (self.root / 'manifest.json').write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def load(self, **kwargs):
        return self.module.load(self.root, self.save(), expected_uid=os.getuid() if hasattr(os, 'getuid') else 0, **kwargs)

    def test_valid_complete_profile_resolves_and_generates_only_signed_local_repos(self):
        media = self.load(bundle_sha256=self.manifest['files'][self.data['bundle']]['sha256'])
        self.assertEqual(media.asset('bundle'), self.root / self.data['bundle'])
        config = media.repo_text()
        self.assertIn('baseurl=file://', config); self.assertIn('gpgcheck=1', config)
        self.assertNotIn('https:', config); self.assertNotIn('mirrorlist', config)

    def test_wrong_manifest_and_bundle_pins_fail(self):
        self.save()
        with self.assertRaises(ValueError): self.module.load(self.root, '0' * 64)
        with self.assertRaises(ValueError): self.load(bundle_sha256='0' * 64)

    def test_missing_changed_and_unlisted_files_fail(self):
        target = self.root / self.data['node']; target.write_bytes(b'tampered')
        with self.assertRaises(ValueError): self.load()
        target.unlink()
        with self.assertRaises(ValueError): self.load()

    def test_extra_files_are_not_executed_or_adopted(self):
        (self.root / 'operator-secret').write_bytes(b'private')
        with self.assertRaises(ValueError): self.load()

    def test_unknown_schema_platform_and_unsafe_paths_fail(self):
        for field, value in [('schema', True), ('platform', 'other'), ('bundle', '../outside'),
                             ('node', 'https://remote/node')]:
            old = self.manifest[field]; self.manifest[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.load()
            self.manifest[field] = old

    def test_repository_collision_or_remote_directory_fails(self):
        self.manifest['repositories'].append(dict(self.manifest['repositories'][0]))
        with self.assertRaises(ValueError): self.load()
        self.manifest['repositories'] = [dict(id='baseos', path='https://remote/repo', gpgkey='keys/os.asc')]
        with self.assertRaises(ValueError): self.load()

    def test_cli_reports_the_same_verified_paths_and_repo_policy(self):
        pin = self.save(); original = self.module.load
        def fixture_load(*args, **kwargs):
            return original(*args, expected_uid=os.getuid() if hasattr(os, 'getuid') else 0, **kwargs)
        for mode in ['--plan', '--repos']:
            output = io.StringIO()
            with mock.patch.object(sys, 'argv', ['media.py', '--root', str(self.root), '--manifest-sha256', pin, mode]), \
                 mock.patch.object(os, 'geteuid', return_value=0, create=True), \
                 mock.patch.object(self.module, 'load', side_effect=fixture_load), contextlib.redirect_stdout(output):
                self.module.main()
            if mode == '--plan': self.assertEqual(json.loads(output.getvalue())['bundle'], str(self.root / self.data['bundle']))
            else: self.assertIn('gpgcheck=1', output.getvalue())

    def test_invalid_size_hash_or_asset_mapping_fails(self):
        entry = self.manifest['files'][self.data['desk']]
        for key, value in [('bytes', True), ('sha256', 'bad')]:
            old = entry[key]; entry[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.load()
            entry[key] = old
        self.manifest['wheels'] = ['not-listed.whl']
        with self.assertRaises(ValueError): self.load()

    def test_selected_asset_is_revalidated_after_profile_load(self):
        media = self.load(); (self.root / self.data['desk']).write_bytes(b'changed')
        with self.assertRaises(ValueError): media.asset('desk')

    def test_copy_requires_exact_expected_pin_and_does_not_fall_back_to_network(self):
        media = self.load(); destination = Path(self.temp.name) / 'copied.tgz'
        with self.assertRaises(ValueError): media.copy('desk', destination, '0' * 64)
        self.assertFalse(destination.exists())
        media.copy('desk', destination, self.manifest['files'][self.data['desk']]['sha256'])
        self.assertEqual(destination.read_bytes(), (self.root / self.data['desk']).read_bytes())

    def test_real_desk_workflow_uses_media_and_forwards_offline_mode(self):
        def module(name, source):
            spec = importlib.util.spec_from_file_location(name, str(ROOT / source))
            value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value
        fixtures = module('desk_existing_fixture', 'tests/test_installer_desk.py')
        desk = fixtures.helper()
        archive = self.root / self.data['desk']; pin = fixtures.make_archive(archive)
        self.manifest['files'][self.data['desk']] = dict(sha256=pin['sha256'], bytes=archive.stat().st_size)
        media = self.load(); calls = []; state = Path(self.temp.name) / 'state.json'
        with mock.patch.object(desk, 'secure_bundle'), \
             mock.patch.object(desk, 'secure_directory', side_effect=lambda path: path.mkdir(parents=True, exist_ok=True)):
            try:
                desk.install(pin, Path(self.temp.name) / 'cache', run=fixtures.ready_runner(state, pin, calls),
                             fetch=lambda *a: self.fail('network called'), legacy_paths=[], standalone_state=state,
                             media=media)
            except TypeError as error: self.fail('Offline Desk workflow absent: ' + str(error))
        self.assertIn('--offline-media', calls[0]); self.assertIn(str(self.root), calls[0])
        self.assertIn(media.manifest_sha256, calls[0])

    def test_geoip_uses_pinned_local_source_without_a_downloader(self):
        spec = importlib.util.spec_from_file_location('offline_geoip_fixture', str(ROOT / 'installer/geoip-update.py'))
        geo = importlib.util.module_from_spec(spec); spec.loader.exec_module(geo)
        target = Path(self.temp.name) / 'source.gz'
        source = self.root / self.manifest['geoip']['path']
        source.write_bytes(gzip.compress(b'1.0.0.0,1.0.0.255,AU\n'))
        record = dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        with mock.patch.object(geo, 'download_month', side_effect=AssertionError('network forbidden')):
            self.assertTrue(hasattr(geo, 'offline_source'), 'Offline GeoIP source contract missing')
            geo.offline_source(self.root / self.manifest['geoip']['path'], record['sha256'], '2026-11', target,
                               expected_uid=os.getuid() if hasattr(os, 'getuid') else 0)
        self.assertEqual(target.read_bytes(), (self.root / self.manifest['geoip']['path']).read_bytes())
        with self.assertRaises(ValueError):
            geo.offline_source(self.root / self.manifest['geoip']['path'], '0' * 64, '2026-11', target)

    def test_offline_geoip_cron_keeps_the_fixed_local_profile(self):
        spec = importlib.util.spec_from_file_location('offline_geoip_cron_fixture', str(ROOT / 'installer/geoip-update.py'))
        geo = importlib.util.module_from_spec(spec); spec.loader.exec_module(geo)
        source = self.root / self.manifest['geoip']['path']; source.write_bytes(gzip.compress(b'country data'))
        profile = dict(path=source, sha256=hashlib.sha256(source.read_bytes()).hexdigest(), month='2026-11')
        with mock.patch.object(geo, 'offline_source', wraps=geo.offline_source) as validate:
            if os.name == 'posix' and os.getuid() != 0:
                with mock.patch.object(geo, 'offline_source', side_effect=lambda *a: None): data = geo.updater_wrapper(profile)
            else: data = geo.updater_wrapper(profile)
        self.assertIn(b'--offline-source ', data); self.assertIn(b'--offline-source-month 2026-11', data)
        self.assertNotIn(b'curl', data); self.assertEqual(geo.updater_wrapper(), geo.WRAPPER)

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX ownership/link boundary')
    def test_symlink_and_writable_media_fail(self):
        target = self.root / self.data['node']; target.unlink(); target.symlink_to('/etc/passwd')
        with self.assertRaises(ValueError): self.load()
        target.unlink(); target.write_bytes(self.data['node'].encode()); target.chmod(0o666)
        with self.assertRaises(ValueError): self.load()


if __name__ == '__main__': unittest.main()
