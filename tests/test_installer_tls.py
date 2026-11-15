"""Generate disposable certificates with real OpenSSL; never touch host TLS paths."""
import importlib.util
import datetime
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'installer/prepare-tls.py'
OPENSSL = shutil.which('openssl') or str(Path('C:/Program Files/Git/usr/bin/openssl.exe'))


def load_helper():
    spec = importlib.util.spec_from_file_location('prepare_tls', str(HELPER))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TLSPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cert = self.root / 'etc/pki/tls/certs/localhost.crt'
        self.key = self.root / 'etc/pki/tls/private/localhost.key'
        self.module = load_helper()
        self.labels = []

    def prepare(self, **kwargs):
        options = dict(openssl=OPENSSL, relabel=lambda paths: self.labels.extend(paths))
        options.update(kwargs)
        return self.module.prepare(self.root, ['pbx.example.test'], ['192.0.2.15', '2001:db8::15'], **options)

    def openssl(self, *args):
        return subprocess.check_output([OPENSSL] + list(args), stdin=subprocess.DEVNULL, stderr=subprocess.PIPE).decode('ascii')

    def make_pair(self, cert=None, key=None, common_name='Existing Customer PBX'):
        cert, key = cert or self.cert, key or self.key
        cert.parent.mkdir(parents=True, exist_ok=True)
        key.parent.mkdir(parents=True, exist_ok=True)
        subprocess.check_call([OPENSSL, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
                               '-subj', '/CN=' + common_name, '-keyout', str(key), '-out', str(cert)],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.chmod(str(key), 0o600)
        os.chmod(str(cert), 0o644)

    def test_absent_pair_is_branded_valid_matching_and_has_ip_and_hostname_sans(self):
        self.assertEqual(self.prepare(), 'created')
        subject = self.openssl('x509', '-in', str(self.cert), '-noout', '-subject', '-ext', 'subjectAltName')
        self.assertIn('MyTellPBX', subject)
        for identity in ['DNS:pbx.example.test', 'IP Address:192.0.2.15', '2001:DB8:0:0:0:0:0:15']:
            self.assertIn(identity, subject)
        self.assertEqual(self.openssl('x509', '-in', str(self.cert), '-pubkey', '-noout'),
                         self.openssl('pkey', '-in', str(self.key), '-passin', 'pass:', '-pubout'))
        self.assertEqual(set(self.labels), {self.cert, self.key})
        if os.name == 'posix':
            self.assertEqual(stat.S_IMODE(self.key.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(self.cert.stat().st_mode), 0o644)

    def test_valid_custom_pair_is_preserved_with_metadata_and_without_relabel(self):
        self.make_pair()
        before = [(path.read_bytes(), path.stat().st_mtime_ns, stat.S_IMODE(path.stat().st_mode)) for path in [self.cert, self.key]]
        self.assertEqual(self.prepare(), 'preserved')
        after = [(path.read_bytes(), path.stat().st_mtime_ns, stat.S_IMODE(path.stat().st_mode)) for path in [self.cert, self.key]]
        self.assertEqual(before, after)
        self.assertEqual(self.labels, [])

    def test_partial_and_mismatched_pairs_fail_without_overwrite(self):
        self.make_pair()
        original = self.cert.read_bytes()
        self.key.unlink()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(self.cert.read_bytes(), original)
        self.make_pair(self.root / 'other.crt', self.key)
        before = self.key.read_bytes()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(self.cert.read_bytes(), original)
        self.assertEqual(self.key.read_bytes(), before)

    def test_invalid_certificate_or_encrypted_key_fails_without_interactive_input(self):
        self.make_pair()
        self.cert.write_bytes(b'not a certificate\n')
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(self.cert.read_bytes(), b'not a certificate\n')
        self.make_pair()
        encrypted = self.root / 'encrypted.key'
        subprocess.check_call([OPENSSL, 'pkey', '-in', str(self.key), '-aes256', '-passout', 'pass:fixture-only', '-out', str(encrypted)],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.key.write_bytes(encrypted.read_bytes())
        with self.assertRaises(ValueError):
            self.prepare()

    def test_invalid_identities_are_rejected_before_creation(self):
        for names, addresses in [(['pbx/escape'], []), (['pbx\nsubject'], []), (['-host'], []), ([], ['not-an-ip']), ([], [])]:
            with self.subTest(names=names, addresses=addresses):
                with self.assertRaises(ValueError):
                    self.module.prepare(self.root, names, addresses, openssl=OPENSSL, relabel=lambda paths: None)
                self.assertFalse(self.cert.exists())
                self.assertFalse(self.key.exists())

    def test_relabel_failure_removes_only_new_pair(self):
        def fail(_paths):
            raise OSError('fixture restorecon failure')
        with self.assertRaises(OSError):
            self.prepare(relabel=fail)
        self.assertFalse(self.cert.exists())
        self.assertFalse(self.key.exists())

    def test_exclusive_publication_refuses_concurrent_target_and_preserves_it(self):
        original_link = os.link
        def raced_link(source, target, *args, **kwargs):
            if Path(target) == self.cert:
                self.cert.write_bytes(b'concurrent owner certificate')
            return original_link(source, target, *args, **kwargs)
        with mock.patch.object(self.module.os, 'link', side_effect=raced_link):
            with self.assertRaises(FileExistsError):
                self.prepare()
        self.assertEqual(self.cert.read_bytes(), b'concurrent owner certificate')
        self.assertFalse(self.key.exists())

    @unittest.skipIf(os.name != 'posix', 'POSIX filesystem trust checks')
    def test_symlink_or_writable_ancestor_is_refused(self):
        actual = self.root / 'actual'
        actual.mkdir()
        (self.root / 'etc').symlink_to(actual, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(list(actual.iterdir()), [])
        (self.root / 'etc').unlink()
        (self.root / 'etc').mkdir(mode=0o777)
        os.chmod(str(self.root / 'etc'), 0o777)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_subprocesses_always_have_closed_stdin_bounded_timeout_and_no_shell(self):
        original = subprocess.run
        seen = []
        def record(*args, **kwargs):
            seen.append(kwargs)
            return original(*args, **kwargs)
        with mock.patch.object(self.module.subprocess, 'run', side_effect=record):
            self.prepare()
        self.assertGreater(len(seen), 3)
        for options in seen:
            self.assertIs(options.get('stdin'), subprocess.DEVNULL)
            self.assertGreater(options.get('timeout', 0), 0)
            self.assertFalse(options.get('shell', False))

    def test_expired_or_not_yet_valid_certificate_is_preserved_and_refused(self):
        self.make_pair()
        before = self.cert.read_bytes()
        original = datetime.datetime
        for year in [2000, 2050]:
            class Clock(original):
                @classmethod
                def utcnow(cls):
                    return original(year, 1, 1)
            with mock.patch.object(self.module.datetime, 'datetime', Clock):
                with self.assertRaises(ValueError):
                    self.prepare()
        self.assertEqual(self.cert.read_bytes(), before)

    def test_rollback_never_removes_a_replaced_owner_file(self):
        def replace_then_fail(_paths):
            self.key.unlink()
            self.key.write_bytes(b'owner replacement key')
            raise OSError('fixture relabel failure')
        with self.assertRaises(OSError):
            self.prepare(relabel=replace_then_fail)
        self.assertEqual(self.key.read_bytes(), b'owner replacement key')
        self.assertFalse(self.cert.exists())

    def test_command_timeout_or_missing_tool_fails_with_sanitized_error(self):
        for error in [OSError('private tool detail'), subprocess.TimeoutExpired('private command detail', 30)]:
            with mock.patch.object(self.module.subprocess, 'run', side_effect=error):
                with self.assertRaisesRegex(ValueError, 'unavailable or timed out'):
                    self.module.run_command(['fixture-tool'])
        self.assertFalse(self.cert.exists())

    def test_cli_rejects_non_root_and_passes_only_validated_requested_identities(self):
        with mock.patch.object(self.module.os, 'geteuid', return_value=1000, create=True):
            with mock.patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.module.main([])
        with mock.patch.object(self.module.os, 'geteuid', return_value=0, create=True):
            with mock.patch.object(self.module, 'prepare', return_value='created') as prepare:
                with mock.patch('sys.stdout', io.StringIO()):
                    self.assertEqual(self.module.main(['--hostname', 'pbx.example.test', '--ip', '192.0.2.15']), 0)
                prepare.assert_called_once_with('/', ['pbx.example.test'], ['192.0.2.15'])
            with mock.patch.object(self.module, 'local_identities', return_value=(['local.test'], ['192.0.2.16'])):
                with mock.patch.object(self.module, 'prepare', side_effect=ValueError('fixture invalid pair')):
                    with mock.patch('sys.stderr', io.StringIO()):
                        self.assertEqual(self.module.main([]), 1)

    def test_local_discovery_uses_only_local_interface_output_and_restorecon_fixed_paths(self):
        with mock.patch.object(self.module.socket, 'gethostname', return_value='pbx.example.test'):
            with mock.patch.object(self.module, 'run_command', return_value=b'2: eth0 inet 192.0.2.10/24 scope global\n2: eth0 inet6 2001:db8::10/64 scope global\n') as run:
                names, addresses = self.module.local_identities()
                self.assertIn('pbx.example.test', names)
                self.assertIn('192.0.2.10', addresses)
                self.assertIn('2001:db8::10', addresses)
                run.assert_called_once_with(['/usr/sbin/ip', '-o', 'address', 'show'])
        with mock.patch.object(self.module, 'run_command') as run:
            self.module.restore_context([self.cert, self.key])
            run.assert_called_once_with(['/usr/sbin/restorecon', '--', str(self.cert), str(self.key)])


if __name__ == '__main__':
    unittest.main()
