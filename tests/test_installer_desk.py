"""Pinned Desk installation and base-installer resume contracts. No host changes."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
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
        with mock.patch.object(self.module, 'secure_directory', side_effect=lambda p: p.mkdir(parents=True, exist_ok=True)):
            self.module.install(release_pin, self.base / 'cache', 'https://pbx.example',
                                run=lambda argv: calls.append(argv), fetch=lambda _u, p: p.write_bytes(archive.read_bytes()),
                                legacy_paths=[], standalone_state=self.base / 'absent-state')
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


class InstallerStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.base = Path(self.temp.name)
        source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.source = self.base / 'definitions.sh'; self.source.write_text(source.rsplit('\nmain "$@"', 1)[0] + '\n', encoding='utf-8')
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
        result = self.shell('curl(){ echo "$*" >> ' + repr(marker.as_posix()) + '; case "$*" in *http_code*) printf 200;; esac; }\nBUNDLE_FINAL=\nMYTELL_BUNDLE_FILE=\ncheck_network_prerequisites\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('mirror.issabel.org', marker.read_text()); self.assertIn('rpms.remirepo.net', marker.read_text())


if __name__ == '__main__': unittest.main()
