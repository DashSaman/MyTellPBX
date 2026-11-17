"""Pinned Desk installation and base-installer resume contracts. No host changes."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash') if os.name != 'nt' else str(Path('C:/Program Files/Git/bin/bash.exe'))


def helper():
    spec = importlib.util.spec_from_file_location('mytell_desk_fixture', str(ROOT / 'installer/install-myteldesk.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pin(sha='a' * 64):
    return {'schema': 1, 'repository': 'DashSaman/MytelDesk', 'version': '1.1.0',
            'archive': 'myteldesk-1.1.0.tar.gz', 'sha256': sha,
            'source_commit': 'a' * 40, 'source_tree': 'b' * 40}


def ready_runner(path, release_pin, calls):
    def run(argv):
        calls.append(argv)
        if 'install' in argv:
            value = json.loads(path.read_text()) if path.exists() else {}
            value.update(owner='MytelDesk', schema=1, status='ready', version=release_pin['version'], tree=release_pin['source_tree'])
            path.write_text(json.dumps(value))
    return run


def make_archive(path, extra=None):
    files = {'installer/install.py': b'# upstream entry point\n', 'backend/vad/models/silero_vad.onnx': b'fixture model',
             'VERSION': b'1.1.0\n', 'SOURCE_TREE': ('b' * 40 + '\n').encode()}
    manifest = {'schema': 1, 'version': '1.1.0', 'source_tree': 'b' * 40,
                'files': {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)} for name, data in files.items()}}
    files['manifest.json'] = json.dumps(manifest).encode()
    with tarfile.open(str(path), 'w:gz') as archive:
        for name, data in files.items():
            member = tarfile.TarInfo('myteldesk-1.1.0/' + name); member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        if extra is not None: archive.addfile(extra, io.BytesIO(b'x') if extra.isfile() else None)
    return pin(hashlib.sha256(path.read_bytes()).hexdigest())


class DeskHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.module = helper()
        if os.name != 'posix':
            # Root/POSIX permission checks run for real in the isolated Linux
            # suite. Windows only exercises the portable workflow callbacks.
            owner_adapter = mock.patch.object(self.module, 'secure_bundle', return_value=None)
            owner_adapter.start(); self.addCleanup(owner_adapter.stop)

    def test_pin_accepts_only_named_release_and_exact_source_identity(self):
        self.assertEqual(self.module.validate_pin(pin()), pin())
        for field, value in [('repository', 'elsewhere/Desk'), ('version', '../1.1.0'), ('archive', '../../script'),
                             ('sha256', 'short'), ('source_tree', 'z' * 40), ('schema', True)]:
            invalid = pin(); invalid[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.module.validate_pin(invalid)

    def test_public_url_rejects_credentials_fragment_and_arbitrary_paths(self):
        for value in ['https://pbx.example', 'https://pbx.example:8443/MytellDesk/']:
            self.assertEqual(self.module.validate_public_url(value), value)
        for value in ['http://pbx.example', 'https://u:secret@pbx.example', 'https://pbx.example/?token=x',
                      'https://pbx.example/#secret', 'https://pbx.example/unrelated', 'https://pbx.example:99999']:
            with self.subTest(value=value), self.assertRaises(ValueError): self.module.validate_public_url(value)

    def test_archive_verifies_every_file_and_source_tree(self):
        archive = self.base / 'release.tgz'; release_pin = make_archive(archive); target = self.base / 'bundle'
        bundle = self.module.extract_verified(archive, target, release_pin)
        self.assertEqual(bundle, target / 'myteldesk-1.1.0')
        self.module.verify_bundle(bundle, release_pin)
        (bundle / 'VERSION').write_text('tampered')
        with self.assertRaises(ValueError): self.module.verify_bundle(bundle, release_pin)

    def test_unknown_extra_and_symlink_files_are_not_adopted(self):
        archive = self.base / 'release.tgz'; release_pin = make_archive(archive)
        bundle = self.module.extract_verified(archive, self.base / 'bundle', release_pin)
        (bundle / 'unlisted').write_text('not part of release')
        with self.assertRaises(ValueError): self.module.verify_bundle(bundle, release_pin)
        (bundle / 'unlisted').unlink()
        if hasattr(os, 'symlink'):
            try: (bundle / 'unlisted').symlink_to(bundle / 'VERSION')
            except OSError: return  # Windows does not necessarily grant symlink creation.
            with self.assertRaises(ValueError): self.module.verify_bundle(bundle, release_pin)

    def test_unsafe_tar_members_fail_before_any_payload_is_extracted(self):
        for name, kind in [('../escape', 'file'), ('/absolute', 'file'), ('myteldesk-1.1.0/link', 'link'),
                           ('other-product/file', 'file'), ('myteldesk-1.1.0/../escape', 'file')]:
            archive = self.base / 'bad.tgz'; member = tarfile.TarInfo(name)
            member.type = tarfile.SYMTYPE if kind == 'link' else tarfile.REGTYPE
            member.linkname = '/etc/passwd'; member.size = 1 if kind == 'file' else 0
            release_pin = make_archive(archive, member); target = self.base / 'candidate'
            with self.subTest(name=name), self.assertRaises(ValueError): self.module.extract_verified(archive, target, release_pin)
            self.assertFalse(target.exists())

    def test_cached_release_is_verified_and_reused_without_network(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive); cache = self.base / 'cache'; cache.mkdir()
        calls = []
        def fetch(url, destination): calls.append(url); destination.write_bytes(archive.read_bytes())
        first = self.module.obtain_bundle(release_pin, cache, fetch)
        second = self.module.obtain_bundle(release_pin, cache, lambda *_: self.fail('healthy cache fetched again'))
        self.assertEqual(first, second); self.assertEqual(len(calls), 1)

    def test_network_interruption_and_hash_mismatch_are_retryable_without_untrusted_execution(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive); cache = self.base / 'cache'; cache.mkdir()
        def interrupted(_url, destination): destination.write_bytes(b'partial'); raise OSError('fixture interrupted')
        with self.assertRaises(OSError): self.module.obtain_bundle(release_pin, cache, interrupted)
        self.assertEqual(list(cache.iterdir()), [])
        with self.assertRaises(ValueError): self.module.obtain_bundle(release_pin, cache, lambda _u, p: p.write_bytes(b'wrong digest'))
        self.assertEqual(list(cache.iterdir()), [])
        result = self.module.obtain_bundle(release_pin, cache, lambda _u, p: p.write_bytes(archive.read_bytes()))
        self.assertTrue((result / 'installer/install.py').is_file())

    def test_install_runs_upstream_with_bytecode_disabled_then_real_doctor(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive); calls = []
        state = self.base / 'state.json'
        with mock.patch.object(self.module, 'secure_directory', side_effect=lambda p: p.mkdir(parents=True, exist_ok=True)):
            self.module.install(release_pin, self.base / 'cache', 'https://pbx.example',
                                run=ready_runner(state, release_pin, calls), fetch=lambda _u, p: p.write_bytes(archive.read_bytes()),
                                legacy_paths=[], standalone_state=state)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0:2], [sys.executable, '-B'])
        self.assertIn('install', calls[0]); self.assertIn('--bundle', calls[0])
        self.assertEqual(calls[0][-2:], ['--public-url', 'https://pbx.example'])
        self.assertEqual(calls[1], ['/usr/local/sbin/myteldesk', 'doctor'])

    def test_legacy_unknown_install_stops_before_download_or_commands(self):
        legacy = self.base / 'old-opdesk'; legacy.mkdir()
        with self.assertRaises(ValueError):
            self.module.install(pin(), self.base / 'cache', run=lambda _a: self.fail('legacy changed'),
                                fetch=lambda *_a: self.fail('unneeded network'), legacy_paths=[legacy],
                                standalone_state=self.base / 'absent')
        self.assertFalse((self.base / 'cache').exists())

    def test_failed_upstream_is_not_reported_healthy(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive); calls = []
        def run(argv): calls.append(argv); raise subprocess.CalledProcessError(1, argv)
        with mock.patch.object(self.module, 'secure_directory', side_effect=lambda p: p.mkdir(parents=True, exist_ok=True)):
            with self.assertRaises(subprocess.CalledProcessError):
                self.module.install(release_pin, self.base / 'cache', run=run,
                                    fetch=lambda _u, p: p.write_bytes(archive.read_bytes()), legacy_paths=[],
                                    standalone_state=self.base / 'absent')
        self.assertEqual(len(calls), 1)

    def test_launcher_replaced_existing_inode_stays_private_and_mkdir_failure_restores_umask(self):
        class Source:
            def __truediv__(self, name): return self
            def is_symlink(self): return False
            def is_file(self): return True
            def read_bytes(self): return b'<?php // fixed public fixture'
        class Web:
            parts = ('/', 'web')
            def is_absolute(self): return True
        class Stream(io.BytesIO):
            def fileno(self): return 5
        for failure in (False, True):
            with self.subTest(mkdir_failure=failure):
                state = {'mode':0o700, 'umask':0o077, 'chmods':[]}
                def open_(name, flags, dir_fd=None):
                    return {'/':1, 'web':2, 'modules':3, 'mytellpbxopdesk':4}.get(name, 5)
                def mkdir(name, mode, dir_fd):
                    if failure: raise OSError('fixture mkdir refused')
                    if name == 'modules': raise FileExistsError()
                    # Newly made inode100 was displaced; open binds an existing
                    # root-owned private inode200. Never chmod that replacement.
                def umask(value):
                    previous = state['umask']; state['umask'] = value; return previous
                def fstat(fd):
                    return types.SimpleNamespace(st_uid=0, st_dev=1, st_ino=200,
                        st_mode=(stat.S_IFDIR | state['mode']) if fd == 4 else stat.S_IFREG | 0o644)
                def fchmod(fd, mode): state['mode'] = mode; state['chmods'].append((fd, mode))
                client = types.SimpleNamespace(name='posix', O_RDONLY=0, O_DIRECTORY=1, O_NOFOLLOW=2,
                    O_NONBLOCK=4, open=open_, mkdir=mkdir, close=lambda fd:None, umask=umask,
                    fstat=fstat, fchmod=fchmod, fdopen=lambda fd, mode:Stream(b'<?php // fixed public fixture'),
                    stat=lambda *a, **kw:types.SimpleNamespace(st_dev=1, st_ino=200))
                with mock.patch.object(self.module, 'Path', side_effect=lambda p:p), mock.patch.object(self.module, 'os', client):
                    if failure:
                        with self.assertRaises(OSError): self.module.install_launcher(Source(), Web())
                    else: self.module.install_launcher(Source(), Web())
                self.assertEqual(state['mode'], 0o700)
                self.assertEqual(state['chmods'], [])
                self.assertEqual(state['umask'], 0o077)

    @unittest.skipUnless(os.name == 'posix', 'Native descriptor-relative POSIX installation')
    def test_launcher_installs_complete_new_files_without_rewriting_owned_content(self):
        source = self.base / 'source'; source.mkdir(); (self.base / 'web').mkdir(); target = self.base / 'web/modules/mytellpbxopdesk'
        for name in ['index.php', 'launcher-access.php']: (source / name).write_text('<?php // ' + name)
        self.module.install_launcher(source, self.base / 'web', expected_uid=os.geteuid())
        self.assertEqual((target / 'index.php').read_bytes(), (source / 'index.php').read_bytes())
        stamp = (target / 'index.php').stat().st_mtime_ns
        self.module.install_launcher(source, self.base / 'web', expected_uid=os.geteuid())
        self.assertEqual((target / 'index.php').stat().st_mtime_ns, stamp)

    @unittest.skipUnless(os.name == 'posix', 'Actual descriptor-relative POSIX umask contract')
    def test_launcher_new_public_directories_remain_readable_under_private_umask(self):
        source = self.base / 'source'; source.mkdir(); web = self.base / 'web'; web.mkdir()
        for name in ['index.php', 'launcher-access.php']: (source / name).write_text('<?php // public ' + name)
        previous = os.umask(0o077)
        try: self.module.install_launcher(source, web, expected_uid=os.geteuid())
        finally: os.umask(previous)
        target = web / 'modules/mytellpbxopdesk'
        for directory in [web / 'modules', target]:
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o755,
                             'A fresh public directory must be traversable by the separate PHP worker')
        for name in ['index.php', 'launcher-access.php']:
            self.assertEqual(stat.S_IMODE((target / name).stat().st_mode), 0o644)
            self.assertEqual((target / name).read_bytes(), (source / name).read_bytes())

    @unittest.skipUnless(os.name == 'posix', 'Actual descriptor-relative POSIX permission preservation')
    def test_launcher_preserves_existing_directory_and_operator_file_permissions(self):
        source = self.base / 'source'; source.mkdir(); web = self.base / 'web'; web.mkdir()
        modules = web / 'modules'; modules.mkdir(); modules.chmod(0o750)
        target = modules / 'mytellpbxopdesk'; target.mkdir(); target.chmod(0o700)
        for name in ['index.php', 'launcher-access.php']:
            (source / name).write_text('<?php // public ' + name)
            (target / name).write_bytes((source / name).read_bytes()); (target / name).chmod(0o644)
        operator = target / 'operator-private'; operator.write_bytes(b'private fixture'); operator.chmod(0o600)
        before = {p: (stat.S_IMODE(p.stat().st_mode), p.stat().st_mtime_ns) for p in [modules, target, operator]}
        previous = os.umask(0o077)
        try: self.module.install_launcher(source, web, expected_uid=os.geteuid())
        finally: os.umask(previous)
        self.assertEqual({p: (stat.S_IMODE(p.stat().st_mode), p.stat().st_mtime_ns) for p in before}, before)
        self.assertEqual(operator.read_bytes(), b'private fixture')

    @unittest.skipUnless(os.name == 'posix', 'Actual descriptor-relative POSIX no-follow contract')
    def test_launcher_symlink_target_never_changes_outside_directory_permissions(self):
        source = self.base / 'source'; source.mkdir(); web = self.base / 'web'; web.mkdir()
        for name in ['index.php', 'launcher-access.php']: (source / name).write_text('<?php // public ' + name)
        modules = web / 'modules'; modules.mkdir()
        outside = self.base / 'outside'; outside.mkdir(); outside.chmod(0o700)
        (outside / 'operator').write_bytes(b'preserve'); stamp = outside.stat().st_mtime_ns
        (modules / 'mytellpbxopdesk').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError): self.module.install_launcher(source, web, expected_uid=os.geteuid())
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o700)
        self.assertEqual(outside.stat().st_mtime_ns, stamp)
        self.assertEqual(list(outside.iterdir()), [outside / 'operator'])

    @unittest.skipUnless(os.name == 'posix', 'Native descriptor-relative POSIX installation')
    def test_unknown_launcher_edits_are_preserved_before_any_partial_install(self):
        source = self.base / 'source'; source.mkdir(); target = self.base / 'web/modules/mytellpbxopdesk'; target.mkdir(parents=True)
        for name in ['index.php', 'launcher-access.php']: (source / name).write_text('<?php // reviewed ' + name)
        (target / 'index.php').write_text('operator customization')
        with self.assertRaises(ValueError): self.module.install_launcher(source, self.base / 'web', expected_uid=os.geteuid())
        self.assertEqual((target / 'index.php').read_text(), 'operator customization')
        self.assertFalse((target / 'launcher-access.php').exists())

    @unittest.skipUnless(os.name == 'posix', 'Native cached-payload ownership contract')
    def test_writable_cached_payload_is_refused_before_root_command_execution(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive); cache = self.base / 'cache'; cache.mkdir()
        bundle = self.module.obtain_bundle(release_pin, cache, lambda _u, p: p.write_bytes(archive.read_bytes()))
        (bundle / 'installer/install.py').chmod(0o777)
        calls = []
        with mock.patch.object(self.module, 'secure_directory', return_value=None):
            with self.assertRaises(ValueError):
                self.module.install(release_pin, cache, run=lambda argv: calls.append(argv), legacy_paths=[],
                                    standalone_state=self.base / 'absent')
        self.assertEqual(calls, [])

    def test_cached_manifest_cannot_redefine_a_trusted_payload(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive); cache = self.base / 'cache'; cache.mkdir()
        bundle = self.module.obtain_bundle(release_pin, cache, lambda _u, p: p.write_bytes(archive.read_bytes()))
        changed = bundle / 'installer/install.py'; changed.write_bytes(b'# altered executable\n')
        manifest = json.loads((bundle / 'manifest.json').read_text())
        manifest['files']['installer/install.py'] = {'sha256': hashlib.sha256(changed.read_bytes()).hexdigest(), 'bytes': changed.stat().st_size}
        (bundle / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(ValueError): self.module.obtain_bundle(release_pin, cache)

    def test_newer_foreign_or_different_ready_desk_stops_before_fetch_run_and_launcher(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive); state = self.base / 'state.json'
        for index, value in enumerate([
            {'owner':'MytelDesk','schema':1,'status':'ready','version':'1.2.0','tree':'c'*40},
            {'owner':'MytelDesk','schema':1,'status':'ready','version':'1.1.0','tree':'c'*40},
            {'owner':'other','schema':1,'status':'ready','version':'1.1.0','tree':'b'*40},
            {'owner':'MytelDesk','schema':1,'status':'ready'},
            {'owner':'MytelDesk','schema':1,'status':'preparing','public_url':'https://pbx.example'},
        ]):
            state.write_text(json.dumps(value)); cache = self.base / ('cache-' + str(index)); calls = []
            with mock.patch.object(self.module, 'secure_directory', side_effect=lambda p: p.mkdir(parents=True, exist_ok=True)), \
                    mock.patch.object(self.module, 'install_launcher', side_effect=lambda *_a: calls.append('launcher')):
                with self.subTest(state=value), self.assertRaises(ValueError):
                    self.module.install(release_pin, cache, run=lambda a: calls.append(a),
                                        fetch=lambda _u,p: (calls.append('fetch'),p.write_bytes(archive.read_bytes())),
                                        legacy_paths=[], standalone_state=state)
            self.assertEqual(calls, []); self.assertFalse(cache.exists())

    def test_known_owned_older_release_may_upgrade_without_resetting_state_values(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive)
        release_pin['upgrades_from'] = [{'version':'1.0.0','source_tree':'c'*40}]
        state = self.base / 'state.json'; original = json.dumps({'owner':'MytelDesk','schema':1,'status':'ready','version':'1.0.0','tree':'c'*40,'retained':'operator-value'})
        state.write_text(original); calls = []
        with mock.patch.object(self.module, 'secure_directory', side_effect=lambda p: p.mkdir(parents=True, exist_ok=True)):
            self.module.install(release_pin, self.base / 'cache', run=ready_runner(state, release_pin, calls),
                                fetch=lambda _u,p: p.write_bytes(archive.read_bytes()), legacy_paths=[], standalone_state=state)
        self.assertEqual(len(calls), 2); self.assertEqual(json.loads(state.read_text())['retained'], 'operator-value')

    def test_helper_failure_records_exact_partial_state_for_a_safe_same_pin_retry(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive); state = self.base / 'state.json'; cache = self.base / 'cache'
        def failed(argv):
            state.write_text(json.dumps({'owner':'MytelDesk','schema':1,'status':'preparing','public_url':'https://pbx.example'}))
            raise subprocess.CalledProcessError(1, argv)
        with mock.patch.object(self.module, 'secure_directory', side_effect=lambda p: p.mkdir(parents=True, exist_ok=True)):
            with self.assertRaises(subprocess.CalledProcessError):
                self.module.install(release_pin, cache, run=failed, fetch=lambda _u,p: p.write_bytes(archive.read_bytes()), legacy_paths=[], standalone_state=state)
            receipt = json.loads((cache / 'attempt.json').read_text())
            self.assertEqual(receipt['state_sha256'], hashlib.sha256(state.read_bytes()).hexdigest())
            calls = []
            self.module.install(release_pin, cache, run=ready_runner(state, release_pin, calls), legacy_paths=[], standalone_state=state)
            self.assertEqual(len(calls), 2)

    def test_zero_exit_without_pinned_ready_state_is_not_installation_success(self):
        archive = self.base / 'source.tgz'; release_pin = make_archive(archive)
        with mock.patch.object(self.module, 'secure_directory', side_effect=lambda p: p.mkdir(parents=True, exist_ok=True)):
            with self.assertRaises(ValueError):
                self.module.install(release_pin, self.base / 'cache', run=lambda _a: None,
                                    fetch=lambda _u,p: p.write_bytes(archive.read_bytes()), legacy_paths=[],
                                    standalone_state=self.base / 'absent')


class InstallerStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.base = Path(self.temp.name)
        source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.source = self.base / 'definitions.sh'; self.source.write_text(source.rsplit('\nmain "$@"', 1)[0] + '\n', encoding='utf-8')
        with self.source.open("a", encoding="utf-8") as fixture: fixture.write("\nensure_local_hostname_resolution(){ :; }\n")
        self.log = self.base / 'install.log'; self.state = self.base / 'state'; self.bundle = self.base / 'bundle'
        (self.bundle / 'installer').mkdir(parents=True); (self.bundle / 'installer/install-myteldesk.py').write_text('# fixture')

    def shell(self, body):
        script = self.base / 'run.sh'
        script.write_text('source ' + repr(self.source.as_posix()) + '\nLOG=' + repr(self.log.as_posix()) + '\nSTATE_DIR=' + repr(self.state.as_posix()) + '\nBUNDLE_DIR=' + repr(self.bundle.as_posix()) + '\nPY_BIN=' + repr(sys.executable.replace('\\', '/')) + '\n' + body, encoding='utf-8')
        return subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace')

    def test_new_desk_stage_executes_helper_and_marks_only_after_success(self):
        fake = self.base / 'python-fixture'; calls = self.base / 'calls'
        fake.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> ' + repr(calls.as_posix()) + '\necho cpu-doctor-ok\n', encoding='utf-8'); fake.chmod(0o755)
        result = self.shell('PY_BIN=' + repr(fake.as_posix()) + '\nMYTELL_DESK_PUBLIC_URL=https://pbx.example\nstage_myteldesk\nstage_myteldesk\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.state / 'stages/myteldesk.done').is_file())
        self.assertEqual(len(calls.read_text().splitlines()), 2, 'completed stage must still verify runtime health')
        self.assertIn('-B ', calls.read_text()); self.assertIn('--public-url https://pbx.example', calls.read_text())
        self.assertIn('cpu-doctor-ok', result.stdout)

    def test_failed_desk_stage_does_not_mark_success(self):
        fake = self.base / 'failing-python'; fake.write_text('#!/bin/bash\nexit 7\n'); fake.chmod(0o755)
        result = self.shell('PY_BIN=' + repr(fake.as_posix()) + '\nstage_myteldesk\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.state / 'stages/myteldesk.done').exists())

    def test_main_refuses_unknown_or_cross_version_state_before_mutating_stages(self):
        self.state.mkdir(); source = self.state / 'source.json'; mutation = self.base / 'mutation'
        for receipt in [None, {'owner': 'MyTellPBX', 'schema': 1, 'version': '7.5.1', 'bundle_sha256': 'a' * 64},
                        {'owner': 'other', 'schema': 1, 'version': '7.6.0', 'bundle_sha256': 'a' * 64}]:
            if receipt is None:
                if source.exists(): source.unlink()
            else: source.write_text(json.dumps(receipt))
            result = self.shell('MYTELLPBX_VERSION=7.6.0\nMYTELLPBX_BUNDLE_SHA256=' + 'a' * 64 + '\npreflight(){ guard_install_source; }\nacquire_lock(){ :; }\nverify_bundle(){ echo mutated > ' + repr(mutation.as_posix()) + '; exit 42; }\nmain\n')
            with self.subTest(receipt=receipt):
                self.assertNotEqual(result.returncode, 0); self.assertFalse(mutation.exists())

    def test_valid_source_receipt_allows_retry_and_rejects_a_different_bundle(self):
        self.state.mkdir(); (self.state / 'source.json').write_text(json.dumps({'owner':'MyTellPBX','schema':1,'version':'7.6.0','bundle_sha256':'a'*64}))
        # Fixture stat isolates ownership from the non-root CI/Windows account.
        metadata = 'stat(){ if [ "$2" = "%u" ]; then echo 0; elif [ "$2" = "%a" ]; then if [ -d "${@: -1}" ]; then echo 700; else echo 600; fi; fi; }\n'
        okay = self.shell(metadata + 'MYTELLPBX_VERSION=7.6.0\nMYTELLPBX_BUNDLE_SHA256=' + 'a' * 64 + '\nguard_install_source\n')
        self.assertEqual(okay.returncode, 0, okay.stderr)
        bad = self.shell(metadata + 'MYTELLPBX_VERSION=7.6.0\nMYTELLPBX_BUNDLE_SHA256=' + 'b' * 64 + '\nguard_install_source\n')
        self.assertNotEqual(bad.returncode, 0)

    def test_offline_and_completed_base_stages_do_not_require_dead_mirror_probes(self):
        marker = self.base / 'curl-calls'
        curl = 'curl(){ echo "$*" >> ' + repr(marker.as_posix()) + '; case "$*" in *http_code*) printf 200;; esac; }\n'
        offline = self.shell(curl + 'MYTELL_BUNDLE_FILE=local-fixture\ncheck_network_prerequisites\n')
        self.assertEqual(offline.returncode, 0, offline.stderr); self.assertFalse(marker.exists())
        self.state.joinpath('stages').mkdir(parents=True)
        for stage in ['repos', 'packages1', 'packages2']: (self.state / ('stages/' + stage + '.done')).touch()
        archive = self.base / 'cached-bundle'; archive.write_text('fixture')
        resumed = self.shell(curl + 'MYTELL_BUNDLE_FILE=\nBUNDLE_FINAL=' + repr(archive.as_posix()) + '\ncheck_network_prerequisites\n')
        self.assertEqual(resumed.returncode, 0, resumed.stderr); self.assertFalse(marker.exists())

    def test_pending_fresh_package_stages_still_probe_required_repositories(self):
        marker = self.base / 'curl-calls'
        metadata = '<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary"><location href="repodata/primary.xml.gz"/></data></repomd>'
        result = self.shell('curl(){ echo "$*" >> ' + repr(marker.as_posix()) + '; case "$*" in *http_code*) printf 200;; *repomd.xml*) printf \'%s\' ' + repr(metadata) + ';; esac; }\nBUNDLE_FINAL=\nMYTELL_BUNDLE_FILE=\ncheck_network_prerequisites\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('https://repo.us.issabel.org', marker.read_text()); self.assertIn('rpms.remirepo.net', marker.read_text())
        self.assertNotIn('http://mirror.issabel.org', marker.read_text())

    def test_empty_interrupted_state_requires_positive_fresh_package_inventory(self):
        self.state.mkdir()
        metadata = 'stat(){ if [ "$2" = "%u" ]; then echo 0; elif [ "$2" = "%a" ]; then echo 700; fi; }\n'
        fresh = self.shell(metadata + 'rpm(){ return 1; }\nguard_install_source\n')
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        existing = self.shell(metadata + 'rpm(){ return 0; }\nguard_install_source\n')
        self.assertNotEqual(existing.returncode, 0)
        unavailable = self.shell(metadata + 'rpm(){ return 7; }\nguard_install_source\n')
        self.assertNotEqual(unavailable.returncode, 0)
        (self.state / 'legacy-stage.done').touch()
        legacy = self.shell(metadata + 'rpm(){ return 1; }\nguard_install_source\n')
        self.assertNotEqual(legacy.returncode, 0)

    def test_bundle_failure_keeps_a_same_source_resume_receipt_before_download(self):
        first = self.shell('MYTELLPBX_VERSION=7.6.0\nMYTELLPBX_BUNDLE_SHA256=' + 'a' * 64 + '\npreflight(){ guard_install_source; }\nacquire_lock(){ :; }\ninitialize_workspace(){ :; }\nverify_bundle(){ exit 13; }\nmain\n')
        self.assertEqual(first.returncode, 13, first.stderr)
        receipt = json.loads((self.state / 'source.json').read_text())
        self.assertEqual(receipt['bundle_sha256'], 'a' * 64)
        metadata = 'stat(){ if [ "$2" = "%u" ]; then echo 0; elif [ "$2" = "%a" ]; then if [ -d "${@: -1}" ]; then echo 700; else echo 600; fi; fi; }\n'
        second = self.shell(metadata + 'MYTELLPBX_VERSION=7.6.0\nMYTELLPBX_BUNDLE_SHA256=' + 'a' * 64 + '\nguard_install_source\n')
        self.assertEqual(second.returncode, 0, second.stderr)


if __name__ == '__main__': unittest.main()
