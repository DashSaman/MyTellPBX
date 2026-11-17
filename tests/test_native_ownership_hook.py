"""Bounded native chown-hook checks; real metadata cases require POSIX root."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'installer/native-ownership-hook.py'
SPEC = importlib.util.spec_from_file_location('native_ownership_hook', str(SOURCE))
HOOK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOOK)


def info(uid=995, gid=992, mode=0o664, directory=False, links=1):
    return types.SimpleNamespace(st_uid=uid, st_gid=gid, st_nlink=links,
                                 st_mode=(stat.S_IFDIR if directory else stat.S_IFREG) | mode)


def state(version='1.1.2', tree='8fb715ccb2810994bb6c721b5352d699bb1867b6'):
    return {'owner': 'MytelDesk', 'schema': 1, 'status': 'ready',
            'version': version, 'tree': tree,
            'release': str(HOOK.DESK / 'releases' / (version + '-' + tree[:12])),
            'owned_hashes': {str(HOOK.MODULE / name): value
                             for name, value in HOOK.FILE_HASHES.items()},
            'recording_module': {'schema': 1, 'name': 'myteldeskrecording',
                                 'version': '1.0.0', 'directory': str(HOOK.MODULE),
                                 'files': dict(HOOK.FILE_HASHES)}}


class ReceiptTests(unittest.TestCase):
    def test_exact_recording_source_pins_are_fixed(self):
        self.assertEqual(HOOK.FILE_HASHES, {
            'functions.inc.php': 'ece7dfca5972ee7810ad3e16b8eb48086d6be3efc02a527573c95b29f7d7da62',
            'module.xml': '2c57a67a213b5b6ca85179bd3b1c825069ea2fa189a7d740a1b84954606a83cd'})

    def test_supported_stub_has_one_fixed_path_and_exact_source_pin(self):
        self.assertEqual(HOOK.STUB.as_posix(), '/var/lib/asterisk/bin/issabelpbx_engine_hook_mytel')
        self.assertEqual(HOOK.STUB_SHA256, '13c35173fe08afb72b74d5ff56e44a450669fbca3fdabfa182262b9bfc5e7cb5')

    def test_known_recording_component_allows_a_new_trusted_app_release(self):
        for version, tree in [('1.1.2', '8fb715ccb2810994bb6c721b5352d699bb1867b6'),
                              ('1.1.3', 'a' * 40)]:
            value = state(version, tree)
            self.assertEqual(HOOK.validate_state(value), value)

    def test_invalid_owner_status_schema_pending_or_source_refuses(self):
        for key, value in [('owner', 'other'), ('schema', True), ('status', 'prepared'),
                           ('pending_journal', False), ('version', '../1.1.2'),
                           ('tree', 'g' * 40), ('release', '/tmp/untrusted')]:
            with self.subTest(key=key):
                candidate = state(); candidate[key] = value
                with self.assertRaises(ValueError): HOOK.validate_state(candidate)

    def test_recording_receipt_unknown_bytes_paths_or_extra_files_refuses(self):
        changes = [('directory', '/tmp/other'), ('schema', True),
                   ('name', 'other'), ('version', '9.0.0'),
                   ('files', dict(HOOK.FILE_HASHES, extra='a' * 64)),
                   ('files', dict(HOOK.FILE_HASHES, **{'module.xml': 'b' * 64}))]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                candidate = state(); candidate['recording_module'][key] = value
                with self.assertRaises(ValueError): HOOK.validate_state(candidate)

    def test_recording_owned_hashes_must_match_both_exact_paths(self):
        for name in HOOK.FILE_HASHES:
            for missing in (True, False):
                candidate = state(); path = str(HOOK.MODULE / name)
                if missing: del candidate['owned_hashes'][path]
                else: candidate['owned_hashes'][path] = '0' * 64
                with self.assertRaises(ValueError): HOOK.validate_state(candidate)


class MetadataPolicyTests(unittest.TestCase):
    def test_known_native_and_root_module_metadata_only(self):
        for uid, gid in [(995, 992), (0, 0)]:
            for mode in (0o644, 0o664):
                self.assertEqual(HOOK.module_metadata(info(uid, gid, mode), False, 995, 992), (0, 0, 0o644))
            for mode in (0o755, 0o775):
                self.assertEqual(HOOK.module_metadata(info(uid, gid, mode, True), True, 995, 992), (0, 0, 0o755))

    def test_unknown_module_owner_mode_type_or_link_refuses(self):
        cases = [info(1234, 992), info(995, 1234), info(0, 992),
                 info(mode=0o666), info(mode=0o4644), info(directory=True), info(links=2)]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): HOOK.module_metadata(value, False, 995, 992)

    def test_native_owned_pem_is_restricted_without_owner_or_group_change(self):
        for gid in (0, 992):
            for mode in (0o600, 0o620, 0o640, 0o644, 0o660, 0o664):
                self.assertEqual(HOOK.pem_mode(info(995, gid, mode), 995, 992), 0o600)

    def test_root_owned_native_group_read_remains_available_to_asterisk(self):
        for mode in (0o640, 0o644, 0o660, 0o664):
            self.assertEqual(HOOK.pem_mode(info(0, 992, mode), 995, 992), 0o640)

    def test_unknown_pem_identity_types_links_and_permissions_refuse(self):
        for value in (info(0, 0), info(1234, 992), info(995, 1234), info(0, 992, 0o600), info(0, 992, 0o620),
                      info(mode=0o666), info(mode=0o675), info(mode=0o4600),
                      info(directory=True), info(links=2)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): HOOK.pem_mode(value, 995, 992)

    def test_cli_rejects_arbitrary_paths_before_any_repair(self):
        with mock.patch.object(HOOK, 'repair') as repair, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(HOOK.main(['--root', '/tmp']), 2)
            repair.assert_not_called()

    def test_special_file_is_refused_before_open_can_block(self):
        special = info();special.st_mode = stat.S_IFIFO | 0o600
        with mock.patch.object(HOOK, 'canonical'), mock.patch.object(Path, 'lstat', return_value=special):
            with mock.patch.object(HOOK.os, 'O_NOFOLLOW', getattr(os, 'O_NOFOLLOW', 0), create=True):
                with mock.patch.object(HOOK.os, 'open', side_effect=AssertionError('unsafe special-file open')) as opened:
                    with contextlib.ExitStack() as stack:
                        with self.assertRaises(ValueError): HOOK.open_fixed(stack, HOOK.PEM)
                    opened.assert_not_called()

    def test_growing_reader_is_bounded_to_original_size_plus_one(self):
        value = types.SimpleNamespace(st_size=3);reads = []
        def growing(fd, requested):
            reads.append(requested)
            if len(reads) > 1:
                raise AssertionError('unbounded reader retried after observing file growth')
            return b'abcd'
        with mock.patch.object(HOOK.os, 'lseek'), mock.patch.object(HOOK.os, 'read', side_effect=growing):
            with self.assertRaises(ValueError): HOOK.file_digest(123, value)
        self.assertEqual(reads, [4])

    def test_cli_propagates_handler_failure_and_prints_no_secret_or_traceback(self):
        with mock.patch.object(HOOK, 'runtime_guard'), mock.patch.object(HOOK, 'repair', side_effect=ValueError('private detail')):
            error = io.StringIO()
            with contextlib.redirect_stderr(error): self.assertEqual(HOOK.main([]), 1)
            self.assertNotIn('private detail', error.getvalue())
            self.assertNotIn('Traceback', error.getvalue())

    def test_source_is_python36_syntax_and_has_no_subprocess_or_path_cli(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'), feature_version=(3, 6))
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        self.assertNotIn('subprocess', imports)
        self.assertNotIn('argparse', imports)


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0,
                     'real POSIX root ownership and descriptor semantics')
class DescriptorRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = self.root / 'web/admin/modules/myteldeskrecording'
        self.config = self.root / 'etc/myteldesk/installation.json'
        self.desk = self.root / 'opt/myteldesk'
        self.pem = self.root / 'etc/asterisk/keys/asterisk.pem'
        self.stub = self.root / 'var/lib/asterisk/bin/issabelpbx_engine_hook_mytel'
        self.stub_bytes = b'# exact supported stub fixture\n'
        for path in (self.module, self.config.parent, self.pem.parent, self.desk / 'releases', self.stub.parent):
            path.mkdir(parents=True)
        self.payloads = {'functions.inc.php': b'<?php /* pinned fixture */\n', 'module.xml': b'<module/>\n'}
        pins = {name: hashlib.sha256(data).hexdigest() for name, data in self.payloads.items()}
        patches = {'MODULE': self.module, 'STATE': self.config, 'DESK': self.desk,
                   'STATE_BASE': self.root / 'etc', 'DESK_BASE': self.root / 'opt',
                   'PEM': self.pem, 'FILE_HASHES': pins, 'STUB': self.stub,
                   'STUB_SHA256': hashlib.sha256(self.stub_bytes).hexdigest()}
        for key, value in patches.items():
            patcher = mock.patch.object(HOOK, key, value); patcher.start(); self.addCleanup(patcher.stop)
        patcher = mock.patch.object(HOOK, 'native_ids', return_value=(17071, 17072));patcher.start();self.addCleanup(patcher.stop)
        release = self.desk / 'releases/1.1.2-8fb715ccb281';release.mkdir()
        (self.desk / 'current').symlink_to(release)
        self.config.write_text(json.dumps(state()), encoding='utf-8');self.config.chmod(0o600)
        for name, data in self.payloads.items():
            f = self.module / name;f.write_bytes(data);os.chown(str(f), 17071, 17072);f.chmod(0o664)
        os.chown(str(self.module), 17071, 17072);self.module.chmod(0o775)
        self.pem.write_bytes(b'PRIVATE KEY FIXTURE MUST NEVER BE LOGGED\n');os.chown(str(self.pem), 17071, 17072);self.pem.chmod(0o664)
        self.stub.write_bytes(self.stub_bytes);os.chown(str(self.stub), 17071, 17072);self.stub.chmod(0o664)

    def snapshot(self):
        return {str(p): (p.lstat().st_uid, p.lstat().st_gid, stat.S_IMODE(p.lstat().st_mode),
                         p.lstat().st_ino, p.read_bytes() if p.is_file() else None)
                for p in [self.module] + list(self.module.iterdir()) + [self.pem, self.stub]}

    def test_native_chown_repairs_only_known_metadata_and_is_idempotent(self):
        before = self.snapshot(); result = HOOK.repair(); after = self.snapshot()
        self.assertEqual(len(result['changed']), 5)
        for path, previous in before.items():
            current = after[path]
            self.assertEqual(current[3:], previous[3:], 'Bytes and inode must be preserved')
            self.assertEqual(current[:3], (17071, 17072, 0o600) if path == str(self.pem)
                             else (0, 0, 0o755 if path == str(self.module) else 0o644))
        self.assertEqual(HOOK.repair()['changed'], [])

    def test_repeated_native_chown_and_group_write_repairs_pem0620_and_stub(self):
        HOOK.repair();before = self.snapshot()
        targets = [self.module] + list(self.module.iterdir()) + [self.pem, self.stub]
        for cycle in range(3):
            for path in targets:
                os.chown(str(path), 17071, 17072)
                path.chmod(stat.S_IMODE(path.stat().st_mode) | 0o020)
            self.assertEqual(stat.S_IMODE(self.pem.stat().st_mode), 0o620)
            self.assertEqual(len(HOOK.repair()['changed']), 5)
            self.assertEqual(self.snapshot(), before, 'Each native cleanup must restore the exact owned metadata')

    def test_unknown_recording_bytes_fail_before_any_metadata_repair(self):
        (self.module / 'module.xml').write_bytes(b'changed');before = self.snapshot()
        with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(self.snapshot(), before)

    def test_extra_module_file_or_untrusted_receipt_fails_before_any_write(self):
        (self.module / 'extra').write_bytes(b'keep');before = self.snapshot()
        with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(self.snapshot(), before)
        (self.module / 'extra').unlink();self.config.chmod(0o664);before = self.snapshot()
        with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(self.snapshot(), before)

    def test_module_symlink_hardlink_and_pem_symlink_are_refused(self):
        f = self.module / 'module.xml';outside = self.root / 'outside';f.rename(outside);f.symlink_to(outside)
        with self.assertRaises(ValueError): HOOK.repair()
        f.unlink();os.link(str(outside), str(f))
        with self.assertRaises(ValueError): HOOK.repair()
        outside.unlink();target = self.root / 'key';self.pem.rename(target);self.pem.symlink_to(target)
        with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(target.read_bytes(), b'PRIVATE KEY FIXTURE MUST NEVER BE LOGGED\n')

    def test_missing_pem_is_not_created_and_root_group_access_is_preserved(self):
        self.pem.unlink();self.assertEqual(HOOK.repair()['pem'], 'absent');self.assertFalse(self.pem.exists())
        self.pem.write_bytes(b'unchanged');os.chown(str(self.pem), 0, 17072);self.pem.chmod(0o664)
        before = (self.pem.stat().st_ino, self.pem.read_bytes());HOOK.repair()
        self.assertEqual((self.pem.stat().st_uid,self.pem.stat().st_gid,stat.S_IMODE(self.pem.stat().st_mode)),(0,17072,0o640))
        self.assertEqual((self.pem.stat().st_ino,self.pem.read_bytes()),before)

    def test_unknown_pem_owner_or_source_link_fails_before_module_repair(self):
        os.chown(str(self.pem), 17073, 17072);before = self.snapshot()
        with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(self.snapshot(), before)
        os.chown(str(self.pem), 17071, 17072);current = self.desk / 'current';current.unlink();current.symlink_to(self.root)
        before = self.snapshot()
        with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(self.snapshot(), before)

    def test_recording_mutation_after_hashing_is_caught_before_metadata_writes(self):
        before = self.snapshot(); original = HOOK.same_path; calls = [0]
        def mutate(path, fd, expected=None):
            if path == self.config:
                calls[0] += 1
                if calls[0] == 2:
                    (self.module / 'functions.inc.php').write_bytes(b'concurrent writer')
            return original(path, fd, expected)
        with mock.patch.object(HOOK, 'same_path', side_effect=mutate):
            with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(calls[0], 2)
        for path, value in self.snapshot().items():
            self.assertEqual(value[:4], before[path][:4], 'No metadata adoption after a stale hash')

    def test_replaced_path_after_validation_never_changes_the_outside_inode(self):
        original = HOOK.same_path; calls = [0]; outside = self.root / 'moved-module'
        def replace(path, fd, expected=None):
            if path == self.config:
                calls[0] += 1
                if calls[0] == 2:
                    f = self.module / 'module.xml';f.rename(outside);f.symlink_to(outside)
            return original(path, fd, expected)
        with mock.patch.object(HOOK, 'same_path', side_effect=replace):
            with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual((outside.stat().st_uid, outside.stat().st_gid,
                          stat.S_IMODE(outside.stat().st_mode), outside.read_bytes()),
                         (17071, 17072, 0o664, self.payloads['module.xml']))
        self.assertEqual(stat.S_IMODE(self.module.stat().st_mode), 0o775)

    def test_metadata_syscall_failure_is_propagated_without_success_or_key_bytes(self):
        before = self.snapshot(); output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(HOOK.os, 'fchown', side_effect=PermissionError('fixture refusal')):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(HOOK.main([]), 1)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('PRIVATE KEY', errors.getvalue())
        self.assertNotIn('fixture refusal', errors.getvalue())

    def test_regular_to_fifo_replacement_cannot_block_the_native_hook(self):
        original = HOOK.os.open; replaced = [False];outside = self.root / 'before-fifo'
        def substitute(path, flags, *args, **kwargs):
            if path == 'module.xml' and kwargs.get('dir_fd') is not None:
                self.assertTrue(flags & os.O_NONBLOCK, 'A replacement FIFO must never block os.open')
                f = self.module / 'module.xml';f.rename(outside);os.mkfifo(str(f), 0o600);replaced[0] = True
            return original(path, flags, *args, **kwargs)
        with mock.patch.object(HOOK.os, 'open', side_effect=substitute):
            with self.assertRaises(ValueError): HOOK.repair()
        self.assertTrue(replaced[0])
        self.assertEqual((outside.stat().st_uid, outside.stat().st_gid, outside.read_bytes()),
                         (17071, 17072, self.payloads['module.xml']))
        self.assertEqual(stat.S_IMODE(self.module.stat().st_mode), 0o775)

    def test_unknown_stub_bytes_owner_or_link_fails_before_any_metadata_write(self):
        self.stub.write_bytes(b'unknown stub');before = self.snapshot()
        with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(self.snapshot(), before)
        self.stub.write_bytes(self.stub_bytes);os.chown(str(self.stub), 17073, 17072);before = self.snapshot()
        with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(self.snapshot(), before)
        os.chown(str(self.stub), 17071, 17072);outside = self.root / 'outside-stub';self.stub.rename(outside);self.stub.symlink_to(outside)
        before = self.snapshot()
        with self.assertRaises(ValueError): HOOK.repair()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(outside.read_bytes(), self.stub_bytes)


if __name__ == '__main__': unittest.main()
