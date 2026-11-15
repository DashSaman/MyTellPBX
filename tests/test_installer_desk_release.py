"""Real released pin through the helper's ownership/upgrade workflow.

Only archive acquisition and vendor commands are synthetic. These tests do not
claim archive verification or account/database migration; those have separate
package/native-product acceptance gates.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.1.1'
TREE = '555fa5ed80f0233af22073ae376e4da7c3c035e2'
TREE_110 = '59c96ab9ad25cf54161d198b1202cd1f28ea79ad'
TREE_100 = '1d5a25c4b3bc4bc7d2b00e11099d64bb287b43ce'
SHA_110 = '5e06a6ec8c2579fabec48706590ccc54ae47a4000313f907951f41b1ff1e0ac7'


class RealDeskReleaseWorkflow(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('desk_real_pin', str(ROOT / 'installer/install-myteldesk.py'))
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.pin = json.loads((ROOT / 'installer/myteldesk-release.json').read_text())
        self.module.validate_pin(self.pin)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.cache = self.base / 'cache'; self.state = self.base / 'installation.json'
        self.web = self.base / 'web'; self.events = []
        self.bundle = self.base / ('bundle-' + self.pin['version'] + '-' + self.pin['source_tree'][:12])
        (self.bundle / 'installer').mkdir(parents=True)
        (self.bundle / 'installer/install.py').write_text('# synthetic callback target; never executed\n')
        self.retained = self.base / 'retained-operator-data'; self.retained.write_bytes(b'owned account/key fixture\n')
        if os.name != 'posix':
            adapter = mock.patch.object(self.module, 'secure_bundle', return_value=None)
            adapter.start(); self.addCleanup(adapter.stop)

    def owned(self, version, tree, status='ready'):
        self.state.write_text(json.dumps(dict(owner='MytelDesk', schema=1, status=status,
            version=version, tree=tree, retained='operator-owned', public_url='https://pbx.example/MytellDesk/')))
        self.state.chmod(0o600)

    def run_workflow(self):
        def directory(path): self.events.append('cache'); path.mkdir(exist_ok=True)
        def obtain(pin, cache, _fetch):
            self.assertEqual(pin, self.pin); self.assertEqual(cache, self.cache)
            self.events.append('obtain'); return self.bundle
        def command(argv):
            self.events.append(tuple(argv))
            if 'install' in argv:
                state = json.loads(self.state.read_text())
                state.update(status='ready', version=self.pin['version'], tree=self.pin['source_tree'])
                self.state.write_text(json.dumps(state)); self.state.chmod(0o600)
        with mock.patch.object(self.module, 'secure_directory', side_effect=directory), \
                mock.patch.object(self.module, 'obtain_bundle', side_effect=obtain), \
                mock.patch.object(self.module, 'install_launcher', side_effect=lambda *_args: self.events.append('launcher')):
            self.module.install(self.pin, self.cache, run=command,
                fetch=lambda *_args: self.fail('No real network allowed'), legacy_paths=[],
                standalone_state=self.state, launcher_source=self.base / 'launcher', web_root=self.web)

    def assert_ready_workflow(self, version, tree):
        self.owned(version, tree)
        try: self.run_workflow()
        except ValueError as error: self.fail('Reviewed ready source was rejected: ' + str(error))
        value = json.loads(self.state.read_text())
        self.assertEqual((value['status'], value['version'], value['tree']), ('ready', VERSION, TREE))
        self.assertEqual(value['retained'], 'operator-owned')
        self.assertEqual(self.retained.read_bytes(), b'owned account/key fixture\n')
        commands = [event for event in self.events if isinstance(event, tuple)]
        self.assertEqual(len(commands), 2)
        self.assertIn('install', commands[0]); self.assertIn(str(self.bundle / 'installer/install.py'), commands[0])
        self.assertEqual(commands[1], ('/usr/local/sbin/myteldesk', 'doctor'))
        self.assertEqual(self.events[-1], 'launcher')
        receipt = json.loads((self.cache / 'attempt.json').read_text())
        self.assertEqual(receipt['phase'], 'complete')
        self.assertEqual(receipt['target'], self.module.target_identity(self.pin))

    def test_ready_published_110_may_upgrade_and_keep_operator_data(self):
        self.assert_ready_workflow('1.1.0', TREE_110)

    def test_ready_known_100_remains_an_allowed_upgrade(self):
        self.assert_ready_workflow('1.0.0', TREE_100)

    def test_ready_reviewed_111_delegates_same_release_and_doctor(self):
        self.assert_ready_workflow(VERSION, TREE)

    def test_unknown_110_newer_or_equal_wrong_tree_cannot_adopt_files(self):
        for version, tree in [('1.1.0', 'f' * 40), ('1.2.0', 'a' * 40), (VERSION, 'e' * 40)]:
            self.owned(version, tree); before = self.state.read_bytes()
            with self.subTest(version=version, tree=tree), self.assertRaises(ValueError): self.run_workflow()
            self.assertEqual(self.events, []); self.assertFalse(self.cache.exists()); self.assertFalse(self.web.exists())
            self.assertEqual(self.state.read_bytes(), before)
            self.assertEqual(self.retained.read_bytes(), b'owned account/key fixture\n')

    def test_old_failed_partial_receipt_does_not_authorize_a_different_target(self):
        self.owned('1.1.0', TREE_110, status='prepared')
        self.cache.mkdir(); receipt = dict(owner='MyTellPBXDeskBootstrap', schema=1, phase='failed',
            target=dict(version='1.1.0', source_tree=TREE_110, sha256=SHA_110),
            state_sha256=hashlib.sha256(self.state.read_bytes()).hexdigest())
        attempt = self.cache / 'attempt.json'; attempt.write_text(json.dumps(receipt)); attempt.chmod(0o600)
        before = self.state.read_bytes(); receipt_before = attempt.read_bytes()
        with self.assertRaises(ValueError): self.run_workflow()
        self.assertEqual(self.events, []); self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(attempt.read_bytes(), receipt_before); self.assertFalse(self.web.exists())

    def test_reviewed_archive_and_git_commit_are_bound_to_the_release(self):
        self.assertEqual(self.pin['version'], VERSION)
        self.assertEqual(self.pin['archive'], 'myteldesk-1.1.1.tar.gz')
        self.assertEqual(self.pin['sha256'], '5f2811822b3d9a3818f94339f41b74ef94b5551816d59affcda2d6cae0dbfbb5')
        self.assertEqual(self.pin['source_commit'], '33d228b11ba1526126122cba124ee74a4548a61d')
        self.assertEqual(self.pin['source_tree'], TREE)


if __name__ == '__main__': unittest.main()
