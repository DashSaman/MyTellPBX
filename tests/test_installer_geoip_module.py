"""Only disposable files/fake metadata commands; never load a kernel module."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'installer/prepare-geoip-module.py'
CURRENT = '4.18.0-553.184.1.el8_10.x86_64'
OLD = '4.18.0-553.134.1.el8_10.x86_64'


class GeoIPModuleTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HELPER.is_file(), 'Fresh GeoIP data has no owned kernel-load/boot preparation helper')
        spec = importlib.util.spec_from_file_location('geoip_module', str(HELPER))
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = []
        self.available = {CURRENT}
        self.default = CURRENT
        self.bad_magic = False; self.load_failure = False; self.omit_loaded = False
        for relative in ['etc/modules-load.d', 'usr/share/mytellpbx-geoip', 'lib/modules', 'proc', 'boot']:
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        (self.root / 'proc/modules').write_text('')
        self.add_module(CURRENT)

    def add_module(self, kernel):
        path = self.root / 'lib/modules' / kernel / 'extra/xt_geoip.ko.xz'
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'disposable module fixture')
        path.chmod(0o644)
        (self.root / 'boot' / ('vmlinuz-' + kernel)).write_bytes(b'fixture image')

    def command(self, args):
        self.calls.append(args)
        if args[0].endswith('grubby'):
            return subprocess.CompletedProcess(args, 0, ('/boot/vmlinuz-' + self.default + '\n').encode(), b'')
        if args[0].endswith('modprobe'):
            if self.load_failure: return subprocess.CompletedProcess(args, 1, b'', b'fixture load failure')
            if not self.omit_loaded: (self.root / 'proc/modules').write_text('xt_geoip 24576 0 - Live 0x0\n')
            return subprocess.CompletedProcess(args, 0, b'', b'')
        self.assertEqual(args[0], '/usr/sbin/modinfo')
        kernel = args[args.index('-k') + 1]; field = args[args.index('-F') + 1]
        if kernel not in self.available:
            return subprocess.CompletedProcess(args, 1, b'', b'modinfo: ERROR: Module xt_geoip not found.\n')
        values = {'name': 'xt_geoip', 'vermagic': (OLD if self.bad_magic else kernel) + ' SMP mod_unload modversions',
                  'filename': '/lib/modules/' + kernel + '/extra/xt_geoip.ko.xz'}
        return subprocess.CompletedProcess(args, 0, (values[field] + '\n').encode(), b'')

    def prepare(self, kernel=CURRENT):
        return self.m.prepare(self.root, kernel, self.command)

    def test_matching_running_module_loads_and_is_persistent(self):
        status = self.prepare()
        self.assertEqual(status['state'], 'ready'); self.assertTrue(status['loaded'])
        self.assertEqual((self.root / self.m.LOADER).read_bytes(), self.m.LOADER_BYTES)
        self.assertEqual(json.loads((self.root / self.m.STATUS).read_text()), status)
        self.assertEqual([x for x in self.calls if x[0].endswith('modprobe')], [['/usr/sbin/modprobe', 'xt_geoip']])
        self.assertFalse(any(any(word in arg for word in ['iptables', 'systemctl', 'firewall']) for x in self.calls for arg in x))
        if os.name == 'posix':
            for relative in [self.m.LOADER,self.m.STATUS]:
                self.assertEqual(stat.S_IMODE((self.root/relative).stat().st_mode),0o644)

    def test_pending_reboot_uses_verified_default_boot_module_without_loading_old_kernel(self):
        status = self.prepare(OLD)
        self.assertEqual(status['state'], 'pending-reboot'); self.assertFalse(status['loaded'])
        self.assertEqual(status['target_kernel'], CURRENT)
        self.assertFalse(any(x[0].endswith('modprobe') for x in self.calls))
        self.assertTrue((self.root / self.m.LOADER).is_file())

    def test_already_loaded_repeat_preserves_loader_and_unrelated_custom_file(self):
        custom = self.root / 'etc/modules-load.d/operator.conf'; custom.write_bytes(b'operator_driver\n')
        first = self.prepare(); path = self.root / self.m.LOADER
        before = (path.read_bytes(), path.stat().st_mtime_ns, custom.read_bytes(), custom.stat().st_mtime_ns)
        self.calls.clear(); second = self.prepare()
        self.assertEqual(first, second)
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns, custom.read_bytes(), custom.stat().st_mtime_ns))
        self.assertFalse(any(x[0].endswith('modprobe') for x in self.calls))

    def test_unknown_managed_loader_is_preserved_before_any_command(self):
        path = self.root / self.m.LOADER; path.write_bytes(b'owner edits\n')
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(path.read_bytes(), b'owner edits\n'); self.assertEqual(self.calls, [])

    def test_unknown_public_status_is_preserved_without_a_loader_or_command(self):
        path = self.root / self.m.STATUS; path.write_bytes(b'{"owner":"operator"}')
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(path.read_bytes(), b'{"owner":"operator"}')
        self.assertFalse((self.root / self.m.LOADER).exists()); self.assertEqual(self.calls, [])

    def test_wrong_vermagic_refuses_load_and_never_publishes_ready(self):
        self.bad_magic = True
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(any(x[0].endswith('modprobe') for x in self.calls))
        self.assertFalse((self.root / self.m.LOADER).exists())
        self.assertNotEqual(json.loads((self.root / self.m.STATUS).read_text())['state'], 'ready')

    def test_failed_modprobe_or_unobserved_load_is_not_success(self):
        for flag in ['load_failure', 'omit_loaded']:
            with self.subTest(flag=flag):
                setattr(self, flag, True)
                with self.assertRaises(ValueError): self.prepare()
                self.assertEqual(json.loads((self.root / self.m.STATUS).read_text())['state'], 'unavailable')
                setattr(self, flag, False)

    def test_no_valid_next_boot_module_is_unavailable_without_loader(self):
        self.default = OLD
        with self.assertRaises(ValueError): self.prepare(OLD)
        self.assertFalse((self.root / self.m.LOADER).exists())
        self.assertEqual(json.loads((self.root / self.m.STATUS).read_text())['state'], 'unavailable')

    def test_ambiguous_modinfo_error_does_not_become_pending_reboot(self):
        def denied(args): return subprocess.CompletedProcess(args, 1, b'', b'permission denied')
        with self.assertRaises(ValueError): self.m.prepare(self.root, OLD, denied)
        self.assertFalse((self.root / self.m.LOADER).exists())

    def test_invalid_boot_kernel_or_running_name_refuses(self):
        for value in ['../escape', 'bad/name', '-option', 'current\nforged']:
            with self.subTest(value=value), self.assertRaises(ValueError): self.prepare(value)
        self.default = '../escape'
        with self.assertRaises(ValueError): self.prepare(OLD)
        self.assertFalse((self.root / self.m.LOADER).exists())

    @unittest.skipUnless(os.name == 'posix', 'Native symlink and owner/mode guard')
    def test_symlinked_managed_file_or_ancestor_is_never_followed(self):
        victim = self.root / 'victim'; victim.write_bytes(b'owner')
        (self.root / self.m.LOADER).symlink_to(victim)
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(victim.read_bytes(), b'owner'); self.assertEqual(self.calls, [])

    @unittest.skipUnless(os.name == 'posix', 'Native module permission guard')
    def test_writable_module_is_refused_before_modprobe(self):
        path = self.root / 'lib/modules' / CURRENT / 'extra/xt_geoip.ko.xz'; path.chmod(0o666)
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(any(x[0].endswith('modprobe') for x in self.calls))

    def test_real_command_transport_is_bounded_no_stdin_and_scrubs_environment(self):
        result = subprocess.CompletedProcess([], 0, b'xt_geoip\n', b'')
        with mock.patch.object(self.m.subprocess, 'run', return_value=result) as child:
            self.assertEqual(self.m.run_command(['/usr/sbin/modprobe','xt_geoip']).returncode, 0)
        kwargs = child.call_args[1]
        self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
        self.assertLessEqual(kwargs['timeout'], 15)
        self.assertEqual(set(kwargs['env']), {'PATH','LANG','LC_ALL'})

    def test_timeout_is_a_sanitized_failure_not_pending_success(self):
        with mock.patch.object(self.m.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture',15)):
            with self.assertRaisesRegex(ValueError, 'timed out'):
                self.m.run_command(['/usr/sbin/modprobe','xt_geoip'])

    def test_public_status_validator_rejects_unknown_types_and_impossible_states(self):
        good=self.prepare(); self.assertTrue(self.m.valid_status(good))
        for key,value in [('loaded',1),('persistent','yes'),('module_sha256',7),('target_kernel','../escape'),
                          ('state','owner'),('target_kernel',None),('owner','operator')]:
            item=dict(good); item[key]=value
            with self.subTest(key=key,value=value):self.assertFalse(self.m.valid_status(item))
        self.assertFalse(self.m.valid_status(dict(good,extra='unknown')))
        self.assertFalse(self.m.valid_status(None))

    def test_cli_root_boundary_and_pending_notice_use_no_real_commands(self):
        denied=SimpleNamespace(name='posix',geteuid=lambda:65534)
        with mock.patch.object(self.m,'os',denied),mock.patch.object(self.m,'prepare') as prepare:
            with self.assertRaisesRegex(ValueError,'Linux root'):self.m.main()
            prepare.assert_not_called()
        allowed=SimpleNamespace(name='posix',geteuid=lambda:0,uname=lambda:SimpleNamespace(release=OLD))
        stdout,stderr=io.StringIO(),io.StringIO()
        with mock.patch.object(self.m,'os',allowed),mock.patch.object(self.m,'prepare',return_value={'state':'pending-reboot'}) as prepare, \
             mock.patch.object(self.m.sys,'stdout',stdout),mock.patch.object(self.m.sys,'stderr',stderr):
            self.m.main()
        self.assertEqual(json.loads(stdout.getvalue())['state'],'pending-reboot')
        self.assertIn('restart',stderr.getvalue());self.assertEqual(prepare.call_args[0][1],OLD)


if __name__ == '__main__': unittest.main()
