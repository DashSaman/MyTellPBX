"""Native first-start safety using disposable files and fake systemd only.

The public fixture contains no real accounts, credentials, DB or daemon.  Tests
replace only the captured public PROFILE hashes; production CLI pins stay fixed.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'installer/prepare-native-start.py'
FIXTURE = ROOT / 'tests/fixtures/native-start/profile.json'
STATE = 'var/lib/mytelpbx-installer'
PREPARED = STATE + '/config-prepared.json'
PROBE = '--property=Id,LoadState,ActiveState,SubState,MainPID,NRestarts,ControlGroup,DropInPaths,FragmentPath'
UNITS = ('asterisk.service', 'issabel-firstboot.service', 'amportal-reload.service')


class NativeStartTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'Native first-start still has no source-bound config preparation/interlock')
        spec = importlib.util.spec_from_file_location('native_start_fixture', str(SCRIPT))
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.uid = os.geteuid() if hasattr(os, 'geteuid') else 0
        self.gid = os.getegid() if hasattr(os, 'getegid') else 0
        self.calls = []; self.active = {}; self.dropins = {}; self.restart_count = {}; self.fragments = {}
        data = json.loads(FIXTURE.read_text())
        self.profile = {'service_sha': '', 'units': {}, 'templates': {}, 'amp_sha': '', 'config_links': {}}
        for relative, text in data['files'].items():
            raw = text.encode('utf-8'); self.put(relative, raw)
            digest = hashlib.sha256(raw).hexdigest()
            if relative == 'usr/sbin/service': self.profile['service_sha'] = digest
            elif relative.endswith('/install_amp'): self.profile['amp_sha'] = digest
            elif relative.startswith('usr/lib/systemd/system/'):
                self.profile['units'][Path(relative).name] = digest
            elif '/amp_conf/astetc/' in relative:
                self.profile['templates'][Path(relative).name] = digest
        self.profile_patch = mock.patch.object(self.m, 'PROFILE', self.profile)
        self.profile_patch.start(); self.addCleanup(self.profile_patch.stop)
        initializers = mock.patch.object(self.m, 'foreign_initializers', return_value=[])
        initializers.start(); self.addCleanup(initializers.stop)
        self.put(STATE + '/source.json', json.dumps(dict(owner='MyTellPBX', schema=1,
                 version='7.6.2', bundle_sha256='a' * 64)).encode(), 0o600)
        (self.root / STATE).chmod(0o700)
        self.put('etc/asterisk/modules.conf', b'; native live config\n#include modules_additional.conf\n#include modules_custom.conf\n')
        self.put('etc/asterisk/manager.conf', b'; native live config\n#include manager_general_additional.conf\n#include manager_custom.conf\n')
        self.put('etc/asterisk/res_parking.conf', b'; native live config\n#include res_parking_additional.conf\n')
        self.ctx = self.m.Context(root=self.root, version='7.6.2', bundle='a' * 64,
                                 uid=self.uid, ast_uid=self.uid, ast_gid=self.gid, run=self.run_command)

    def put(self, relative, data, mode=0o644):
        path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data); path.chmod(mode)
        return path

    def run_command(self, args, **kwargs):
        self.calls.append(list(args))
        if args == ['systemctl', 'daemon-reload']:
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        if len(args) == 4 and args[:2] == ['systemctl', 'show'] and args[2] in UNITS and args[3] == PROBE:
            name = args[2]; active = self.active.get(name, False)
            dropins = self.dropins.get(name)
            if dropins is None:
                dropins = ' '.join(str(p) for p in sorted((self.root / 'etc/systemd/system' / (name + '.d')).glob('*.conf')))
            text = ('Id={0}\nLoadState={7}\nActiveState={1}\nSubState={2}\nMainPID={3}\n'
                    'NRestarts={4}\nControlGroup={5}\nDropInPaths={6}\nFragmentPath={8}\n').format(
                        name, 'active' if active else 'inactive', 'running' if active else 'dead',
                        12345 if active else 0, self.restart_count.get(name, 0),
                        '/system.slice/' + name if active else '', dropins,
                        'loaded' if (self.root / 'usr/lib/systemd/system' / name).is_file() else 'not-found',
                        self.fragments.get(name, str(self.root / 'usr/lib/systemd/system' / name)
                                           if (self.root / 'usr/lib/systemd/system' / name).is_file() else ''))
            return SimpleNamespace(returncode=0, stdout=text.encode(), stderr=b'')
        raise AssertionError('Unexpected native command: only unit metadata and daemon-reload are allowed')

    def hold(self):
        return self.m.hold(self.ctx)

    def prepare(self):
        self.hold(); return self.m.prepare_configs(self.ctx)

    def ready(self):
        return self.root / PREPARED

    def assert_no_service_or_database_mutation(self):
        self.assertTrue(all(c == ['systemctl', 'daemon-reload'] or c[:2] == ['systemctl', 'show'] for c in self.calls))

    def test_hold_installs_three_real_conditions_without_starting_any_service(self):
        self.hold()
        found = list((self.root / 'etc/systemd/system').glob('*.service.d/*.conf'))
        self.assertEqual(len(found), 3)
        content = {p.parent.name[:-2]: p.read_text() for p in found}
        self.assertIn('ConditionPathExists=/var/lib/mytelpbx-installer/config-prepared.json', content['asterisk.service'])
        self.assertIn('ConditionPathExists=!/var/lib/mytelpbx-installer/source.json', content['issabel-firstboot.service'])
        self.assertIn('ConditionPathExists=/var/lib/mytelpbx-installer/stages/framework.done', content['amportal-reload.service'])
        self.assertFalse(self.ready().exists()); self.assert_no_service_or_database_mutation()

    def test_wrong_source_receipt_refuses_before_installing_dropins(self):
        path = self.root / STATE / 'source.json'; record = json.loads(path.read_text()); record['bundle_sha256'] = 'b' * 64
        path.write_text(json.dumps(record))
        with self.assertRaises((ValueError, RuntimeError)): self.hold()
        self.assertFalse((self.root / 'etc/systemd/system').exists())

    def test_foreign_active_initializer_is_not_adopted(self):
        self.active['issabel-firstboot.service'] = True
        with self.assertRaises((ValueError, RuntimeError)): self.hold()
        self.assertFalse(self.ready().exists()); self.assert_no_service_or_database_mutation()

    def test_unprepared_running_asterisk_is_not_adopted(self):
        self.active['asterisk.service'] = True
        with self.assertRaises((ValueError, RuntimeError)): self.hold()
        self.assertFalse(self.ready().exists())

    def test_other_initializer_process_refuses(self):
        with mock.patch.object(self.m, 'foreign_initializers', return_value=[31337]):
            with self.assertRaises((ValueError, RuntimeError)): self.hold()
        self.assertFalse(self.ready().exists())

    def test_unknown_dropin_is_preserved(self):
        path = self.put('etc/systemd/system/asterisk.service.d/operator.conf', b'[Service]\nNice=1\n')
        with self.assertRaises((ValueError, RuntimeError)): self.hold()
        self.assertEqual(path.read_bytes(), b'[Service]\nNice=1\n')

    def test_runtime_full_unit_override_is_preserved_and_refused(self):
        path = self.put('run/systemd/system/asterisk.service', b'[Service]\nExecStart=/foreign\n')
        with self.assertRaises((ValueError, RuntimeError)): self.hold()
        self.assertEqual(path.read_bytes(), b'[Service]\nExecStart=/foreign\n'); self.assertFalse(self.ready().exists())

    def test_loaded_foreign_fragment_path_is_refused(self):
        self.fragments['asterisk.service'] = str(self.root / 'run/systemd/system/asterisk.service')
        with self.assertRaises((ValueError, RuntimeError)): self.hold()
        self.assertFalse(self.ready().exists())

    def test_daemon_reload_failure_remains_unready_and_exact_owned_hold_resumes(self):
        def fail_reload(args, **kwargs):
            if args == ['systemctl', 'daemon-reload']:
                self.calls.append(list(args))
                return SimpleNamespace(returncode=1, stdout=b'', stderr=b'injected daemon-reload failure')
            return self.run_command(args, **kwargs)
        failed = self.m.Context(root=self.root, version='7.6.2', bundle='a' * 64,
                                uid=self.uid, ast_uid=self.uid, ast_gid=self.gid, run=fail_reload)
        with self.assertRaises((ValueError, RuntimeError, OSError)): self.m.hold(failed)
        self.assertFalse(self.ready().exists())
        self.hold(); self.assertFalse(self.ready().exists()); self.assert_no_service_or_database_mutation()

    def test_interrupted_nonconf_publication_file_is_ignored_and_preserved_on_hold_resume(self):
        self.hold()
        path = self.put('etc/systemd/system/asterisk.service.d/.mytel-native-interrupted', b'partial inert temporary')
        try: self.hold()
        except ValueError: self.fail('Interrupted non-.conf publication incorrectly prevents owned hold resume')
        self.assertEqual(path.read_bytes(), b'partial inert temporary'); self.assertFalse(self.ready().exists())

    def test_legacy_dispatch_path_refuses_without_changing_it(self):
        path = self.put('etc/rc.d/init.d/asterisk', b'#!/bin/sh\nexit 0\n', 0o755)
        with self.assertRaises((ValueError, RuntimeError)): self.hold()
        self.assertTrue(path.exists()); self.assertFalse(self.ready().exists())

    def test_prepare_closes_missing_modules_custom_before_ready(self):
        self.put('etc/asterisk/modules.conf', b'; live operator-preserved configuration\n#include modules_custom.conf\n')
        before = (self.root / 'etc/asterisk/modules.conf').read_bytes()
        self.prepare()
        self.assertTrue((self.root / 'etc/asterisk/modules_custom.conf').is_file())
        self.assertEqual((self.root / 'etc/asterisk/modules_custom.conf').read_bytes(), b'')
        self.assertEqual((self.root / 'etc/asterisk/modules.conf').read_bytes(), before)
        self.assertTrue(self.ready().is_file()); self.assert_no_service_or_database_mutation()

    def test_existing_custom_include_bytes_are_preserved(self):
        path = self.put('etc/asterisk/modules_custom.conf', b'noload => app_example.so\n')
        self.put('etc/asterisk/modules.conf', b'#include modules_custom.conf\n')
        self.prepare(); self.assertEqual(path.read_bytes(), b'noload => app_example.so\n')

    def test_native_non_utf8_comment_is_preserved_while_ascii_include_is_prepared(self):
        path = self.put('etc/asterisk/minivm.conf', b'; native single-byte comment\xe5\n#include minivm_custom.conf\n')
        before = path.read_bytes(); self.prepare()
        self.assertEqual(path.read_bytes(), before)
        self.assertTrue((self.root / 'etc/asterisk/minivm_custom.conf').is_file()); self.assertTrue(self.ready().is_file())

    def test_unknown_template_profile_cannot_publish_ready(self):
        path = self.root / 'usr/src/issabelPBX/framework/amp_conf/astetc/modules.conf'
        path.write_bytes(path.read_bytes() + b'; unreviewed\n')
        with self.assertRaises((ValueError, RuntimeError)): self.prepare()
        self.assertFalse(self.ready().exists())

    def test_unknown_native_unit_cannot_publish_ready(self):
        path = self.root / 'usr/lib/systemd/system/asterisk.service'; path.write_bytes(b'[Service]\nExecStart=/foreign\n')
        with self.assertRaises((ValueError, RuntimeError)): self.prepare()
        self.assertFalse(self.ready().exists())

    def test_unknown_service_dispatch_cannot_publish_ready(self):
        self.hold(); path = self.root / 'usr/sbin/service'; path.write_bytes(b'foreign service dispatch')
        with self.assertRaises((ValueError, RuntimeError)): self.m.prepare_configs(self.ctx)
        self.assertFalse(self.ready().exists())

    def test_recovered_restart_is_never_a_healthy_prepare(self):
        self.hold(); self.restart_count['asterisk.service'] = 1
        with self.assertRaises((ValueError, RuntimeError)): self.m.prepare_configs(self.ctx)
        self.assertFalse(self.ready().exists())

    def test_unpatched_install_amp_cannot_publish_ready(self):
        path = self.root / 'usr/src/issabelPBX/framework/install_amp'; path.write_bytes(b'unknown native installer')
        with self.assertRaises((ValueError, RuntimeError)): self.prepare()
        self.assertFalse(self.ready().exists())

    def test_ready_publication_failure_stays_unready_and_owned_resume_completes(self):
        self.hold(); replace = self.m.os.replace; link = self.m.os.link
        def fail_replace(source, destination, *args, **kwargs):
            if Path(destination) == self.ready(): raise OSError('Injected publication failure')
            return replace(source, destination, *args, **kwargs)
        def fail_link(source, destination, *args, **kwargs):
            if Path(destination) == self.ready(): raise OSError('Injected publication failure')
            return link(source, destination, *args, **kwargs)
        with mock.patch.object(self.m.os, 'replace', side_effect=fail_replace), mock.patch.object(self.m.os, 'link', side_effect=fail_link):
            with self.assertRaises(OSError): self.m.prepare_configs(self.ctx)
        self.assertFalse(self.ready().exists()); self.assert_no_service_or_database_mutation()
        self.m.prepare_configs(self.ctx); self.assertTrue(self.ready().is_file())

    def test_idempotent_prepare_revalidates_receipt_and_does_not_rewrite_configs(self):
        self.prepare(); path = self.root / 'etc/asterisk/modules.conf'; before = path.read_bytes(); stamp = path.stat().st_mtime_ns
        self.m.prepare_configs(self.ctx)
        self.assertEqual(path.read_bytes(), before); self.assertEqual(path.stat().st_mtime_ns, stamp)
        receipt = json.loads(self.ready().read_text()); receipt['bundle_sha256'] = 'b' * 64; self.ready().write_text(json.dumps(receipt))
        with self.assertRaises((ValueError, RuntimeError)): self.m.prepare_configs(self.ctx)

    def test_source_change_after_hold_cannot_publish_ready(self):
        self.hold(); path = self.root / STATE / 'source.json'; value = json.loads(path.read_text()); value['version'] = '7.6.3'; path.write_text(json.dumps(value))
        with self.assertRaises((ValueError, RuntimeError)): self.m.prepare_configs(self.ctx)
        self.assertFalse(self.ready().exists())

    def test_real_bash_wiring_holds_before_shortcut_and_prepares_before_one_start(self):
        bash = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')
        if not bash: self.skipTest('Bash unavailable')
        text = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.assertEqual(text.count('\nmain "$@"'), 1)
        definitions = self.put('definitions.sh', text.rsplit('\nmain "$@"', 1)[0].encode())
        events = self.root / 'events'; bundle = self.root / 'bundle'
        self.put('bundle/installer/patch-native-include-order.py', b'# never executed\n')
        self.put('bundle/installer/prepare-native-start.py', b'# never executed\n')
        settings = {'EVENTS': events, 'LOG': self.root / 'log', 'BUNDLE_DIR': bundle,
                    'STATE_DIR': self.root / 'state', 'MYTELLPBX_VERSION': '7.6.2',
                    'MYTELLPBX_BUNDLE_SHA256': 'a' * 64, 'PY_BIN': 'fixture_python', 'ADMIN_PASS': 'fixture'}
        body = 'source ' + shlex.quote(definitions.as_posix()) + '\n'
        body += '\n'.join(k + '=' + shlex.quote(str(v).replace('\\', '/')) for k, v in settings.items()) + '\n'
        body += '''
event(){ printf '%s\\n' "$1" >>"$EVENTS"; }
step(){ :; }; say(){ :; }; warn(){ :; }
die(){ event FORBIDDEN; exit 98; }
stage_done(){ event "DONE:$1"; [ "$1" = native-platform ]; }
mark_stage(){ event "MARK:$1"; }
native_start(){ event "NATIVE:$*"; }
ensure_credentials(){ :; }
framework_service_config(){ printf 'fixture-digest'; }
guard_empty_framework_bootstrap(){ event GUARD; }
run_logged(){ case "$*" in *patch-native-include-order.py*) event PATCH;; */create_fop2_manager_user.pl*) :;; *) event FORBIDDEN; return 97;; esac; }
systemctl(){ case "$*" in 'start asterisk') event START;; 'enable asterisk') event ENABLE;; *) event FORBIDDEN; return 96;; esac; }
wait_asterisk_ready(){ event WAIT; }
bootstrap_empty_framework(){ event BOOTSTRAP; }
initialize_preserving_framework_keys(){ event INIT; }
verify_native_migrations_complete(){ :; }; verify_mysql_root_password(){ :; }
verify_mysql_authentication(){ :; }; ensure_admin_credentials(){ :; }; verify_amp_admin_password(){ :; }
php(){ cat >/dev/null; }
stage_native_platform
stage_framework_init
'''
        script = self.put('run-wiring.sh', body.encode())
        result = subprocess.run([bash, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        log = events.read_text().splitlines(); self.assertNotIn('FORBIDDEN', log)
        self.assertLess(log.index('NATIVE:--hold'), log.index('DONE:native-platform'))
        ordered = ['GUARD', 'PATCH', 'NATIVE:--prepare-config', 'START', 'WAIT', 'BOOTSTRAP']
        self.assertEqual([name for name in log if name in ordered][:len(ordered)], ordered)
        self.assertEqual(log.count('START'), 1); self.assertEqual(log.count('WAIT'), 2)
        self.assertEqual(log[-2:], ['WAIT', 'MARK:framework'])

    def test_escaping_live_include_cannot_create_files_outside_native_directory(self):
        self.put('etc/asterisk/modules.conf', b'#include ../operator.conf\n')
        self.hold()
        with self.assertRaises((ValueError, RuntimeError)): self.m.prepare_configs(self.ctx)
        self.assertFalse((self.root / 'etc/operator.conf').exists()); self.assertFalse(self.ready().exists())

    @unittest.skipUnless(os.name == 'posix', 'Native known factory symlink profile')
    def test_known_factory_link_is_validated_without_replacing_it(self):
        target = self.put('var/www/html/admin/modules/core/etc/enum.conf', b'; safe native factory target\n')
        path = self.root / 'etc/asterisk/enum.conf'; path.symlink_to('/var/www/html/admin/modules/core/etc/enum.conf')
        self.profile['config_links']['enum.conf'] = '/var/www/html/admin/modules/core/etc/enum.conf'
        self.prepare()
        self.assertTrue(path.is_symlink()); self.assertEqual(os.readlink(str(path)), '/var/www/html/admin/modules/core/etc/enum.conf')
        self.assertEqual(target.read_bytes(), b'; safe native factory target\n'); self.assertTrue(self.ready().exists())

    @unittest.skipUnless(os.name == 'posix', 'Native no-symlink boundary')
    def test_foreign_live_include_symlink_is_preserved_and_refused(self):
        self.put('etc/asterisk/modules.conf', b'#include modules_custom.conf\n')
        outside = self.put('operator-data', b'keep'); path = self.root / 'etc/asterisk/modules_custom.conf'; path.symlink_to(outside)
        self.hold()
        with self.assertRaises((ValueError, RuntimeError)): self.m.prepare_configs(self.ctx)
        self.assertEqual(outside.read_bytes(), b'keep'); self.assertTrue(path.is_symlink()); self.assertFalse(self.ready().exists())

    @unittest.skipUnless(os.name == 'posix', 'Native nonblocking nonregular read boundary')
    def test_fifo_include_is_refused_without_open_blocking(self):
        self.hold(); path = self.root / 'etc/asterisk/modules_custom.conf'; os.mkfifo(str(path))
        original_open = self.m.os.open; opened = []
        def guarded_open(name, flags, *args, **kwargs):
            if Path(name) == path:
                opened.append(flags)
                self.assertTrue(flags & os.O_NONBLOCK, 'FIFO read would block before the regular-file check')
            return original_open(name, flags, *args, **kwargs)
        with mock.patch.object(self.m.os, 'open', side_effect=guarded_open):
            with self.assertRaises((ValueError, RuntimeError)): self.m.prepare_configs(self.ctx)
        # Rejecting the FIFO by lstat before open is also correct. If a future
        # implementation opens it, guarded_open requires nonblocking flags.
        self.assertFalse(self.ready().exists()); self.assertTrue(path.exists())


if __name__ == '__main__': unittest.main()
