"""Native addon boundary regressions. No PBX connection or runtime claim."""
import importlib.util
import hashlib
from contextlib import closing, redirect_stdout
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('native_addons', str(ROOT / 'installer/native-addons.py'))
ADDONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADDONS)
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class OfflineProgressTests(unittest.TestCase):
    def test_private_static_check_output_and_failure_path_are_preserved(self):
        with tempfile.TemporaryDirectory() as work:
            log = Path(work) / 'netinstall.log'
            command = [sys.executable, '-c', 'print("fixture private diagnostic", flush=True); raise SystemExit(7)']
            with self.assertRaises(ValueError) as error:
                ADDONS.run(command, diagnostics=log)
            self.assertIn(str(log), str(error.exception))
            self.assertNotIn('fixture private diagnostic', str(error.exception))
            self.assertIn(b'fixture private diagnostic', log.read_bytes())

    @unittest.skipUnless(os.name == 'posix' and BASH and shutil.which('timeout'), 'Bash and GNU timeout required')
    def test_offline_package_wrapper_keeps_dnf_error_and_raw_private_output(self):
        with tempfile.TemporaryDirectory() as work:
            log = Path(work).resolve() / 'netinstall.log'
            command = [sys.executable, '-c', 'print("fixture raw dnf diagnostic"); raise SystemExit(42)']
            with self.assertRaisesRegex(ValueError, 'Package installation from ISO stopped'):
                ADDONS.install_media_packages(ROOT, log, command)
            self.assertIn(b'fixture raw dnf diagnostic', log.read_bytes())


class NativeOwnershipIntegrationTests(unittest.TestCase):
    def test_shipped_handler_is_the_exact_reviewed_source_pin(self):
        self.assertRegex(ADDONS.NATIVE_OWNERSHIP_HOOK_SHA256, r'^[0-9a-f]{64}$')
        source = (ROOT / 'installer/native-ownership-hook.py').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), ADDONS.NATIVE_OWNERSHIP_HOOK_SHA256)

    def fixture(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        root, bundle, backup = base / 'root', base / 'bundle', base / 'backup'
        root.mkdir(); backup.mkdir(); (bundle / 'installer').mkdir(parents=True)
        handler = bundle / 'installer/native-ownership-hook.py'; handler.write_bytes(b'# fixture handler\n')
        engine = root / 'var/lib/asterisk/bin/issabelpbx_engine'; engine.parent.mkdir(parents=True)
        engine.write_bytes(b'# fixture native engine\n')
        return root, bundle, backup, handler, engine

    def test_unknown_handler_or_native_contract_is_refused_before_registration(self):
        root, bundle, backup, handler, engine = self.fixture()
        for handler_sha, engine_sha in [('0' * 64, hashlib.sha256(engine.read_bytes()).hexdigest()),
                                       (hashlib.sha256(handler.read_bytes()).hexdigest(), '0' * 64)]:
            with self.subTest(handler_sha=handler_sha), \
                    mock.patch.object(ADDONS, 'NATIVE_OWNERSHIP_HOOK_SHA256', handler_sha, create=True), \
                    mock.patch.object(ADDONS, 'NATIVE_ENGINE_SHA256', engine_sha, create=True):
                with self.assertRaises(ValueError): ADDONS.ownership_hook_changes(bundle, root)
            self.assertFalse((root / 'usr/local/libexec/mytelpbx').exists())
            self.assertFalse((engine.parent / 'issabelpbx_engine_hook_mytel').exists())

    def test_registration_backs_up_both_paths_before_writes_and_then_invokes_fixed_handler(self):
        root, bundle, backup, handler, engine = self.fixture()
        target = root / 'usr/local/libexec/mytelpbx/native-ownership-hook.py'
        stub = engine.parent / 'issabelpbx_engine_hook_mytel'
        changes = {target: b'owned handler', stub: b'owned stub'}
        calls = []
        def write(path, data, uid, gid):
            self.assertTrue((backup / 'native-ownership/files.json').is_file())
            self.assertTrue((backup / 'native-ownership/targets-before.json').is_file())
            self.assertEqual(len(json.loads((backup / 'native-ownership/files.json').read_text())), 2)
            self.assertEqual((uid, gid), (0, 0))
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            calls.append(('write', path))
        def command(argv):
            self.assertEqual(target.read_bytes(), b'owned handler')
            self.assertEqual(stub.read_bytes(), b'owned stub')
            self.assertEqual(len(json.loads((backup / 'native-ownership/targets-before.json').read_text())), 4)
            calls.append(('run', argv))
        with mock.patch.object(ADDONS, 'ownership_hook_changes', return_value=changes, create=True), \
                mock.patch.object(ADDONS, 'private_directory', side_effect=lambda p: p.mkdir(parents=True, exist_ok=True)), \
                mock.patch.object(ADDONS, 'atomic_write', side_effect=write), mock.patch.object(ADDONS, 'run', side_effect=command), \
                mock.patch.object(ADDONS, 'verify_ownership_stub', create=True) as verify:
            ADDONS.install_ownership_hook(bundle, backup, root)
        self.assertEqual(calls[-1], ('run', ['/usr/libexec/platform-python', '-I', '-B', str(target)]))
        self.assertEqual(len(calls), 3)
        verify.assert_called_once_with(stub)

    @unittest.skipUnless(os.name == 'posix' and os.geteuid() == 0, 'POSIX root registration metadata test')
    def test_registration_rejects_success_without_restoring_the_already_chowned_stub(self):
        root, bundle, backup, handler, engine = self.fixture()
        target = root / 'usr/local/libexec/mytelpbx/native-ownership-hook.py'
        stub = engine.parent / 'issabelpbx_engine_hook_mytel'
        stub.write_bytes(ADDONS.OWNERSHIP_STUB)
        os.chown(str(stub), 12345, 23456); stub.chmod(0o664)
        changes = {target: b'handler', stub: ADDONS.OWNERSHIP_STUB}
        with mock.patch.object(ADDONS, 'ownership_hook_changes', return_value=changes), \
                mock.patch.object(ADDONS, 'run', return_value=b''), \
                mock.patch.object(ADDONS, 'rollback_files') as rollback:
            with self.assertRaisesRegex(ValueError, 'stub'):
                ADDONS.install_ownership_hook(bundle, backup, root)
        rollback.assert_called_once()
        # The handler, rather than atomic_write's preserved metadata, must
        # normalize the known stub during successful re-registration.
        second = backup / 'normalized'; second.mkdir()
        def normalize(argv):
            self.assertEqual(stub.stat().st_uid, 12345)
            os.chown(str(stub), 0, 0); stub.chmod(0o644)
        with mock.patch.object(ADDONS, 'ownership_hook_changes', return_value=changes), \
                mock.patch.object(ADDONS, 'run', side_effect=normalize):
            ADDONS.install_ownership_hook(bundle, second, root)
        self.assertEqual((stub.stat().st_uid, stub.stat().st_gid, stub.stat().st_mode & 0o7777), (0, 0, 0o644))

    def test_handler_failure_rolls_back_registration_and_cannot_report_success(self):
        root, bundle, backup, handler, engine = self.fixture()
        target = root / 'usr/local/libexec/mytelpbx/native-ownership-hook.py'
        changes = {target: b'handler', engine.parent / 'issabelpbx_engine_hook_mytel': b'stub'}
        with mock.patch.object(ADDONS, 'ownership_hook_changes', return_value=changes, create=True), \
                mock.patch.object(ADDONS, 'private_directory'), mock.patch.object(ADDONS, 'atomic_write'), \
                mock.patch.object(ADDONS, 'run', side_effect=ValueError('handler refused unknown metadata')), \
                mock.patch.object(ADDONS, 'rollback_files') as rollback:
            with self.assertRaises(ValueError): ADDONS.install_ownership_hook(bundle, backup, root)
        self.assertEqual(rollback.call_count, 1)
        self.assertEqual(rollback.call_args.args[1:], (backup / 'native-ownership', root))

    @unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required for native hook dispatch')
    def test_supported_stub_fails_closed_even_when_native_dispatch_ignores_return_values(self):
        for status in (0, 31):
            with self.subTest(handler_status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fake = root / 'handler-interpreter.sh'
                fake.write_text('#!/bin/bash\nexit ' + str(status) + '\n', encoding='utf-8')
                fake.chmod(0o755)
                stub = ADDONS.OWNERSHIP_STUB.decode().replace('/usr/libexec/platform-python', shlex.quote(fake.as_posix()))
                # Model the observed native call_hook bug: return codes from a
                # called hook are overwritten. Only exiting the dispatcher is safe.
                script = root / 'hook.sh'
                script.write_text(stub + '\ncall_hook(){ "$@"; return 0; }\n'
                                  'call_hook chown_asterisk_hook_mytel\nprintf "AFTER_HOOK\\n"\n', encoding='utf-8')
                result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0 if status == 0 else 1)
                self.assertEqual(b'AFTER_HOOK' in result.stdout, status == 0)
                if status:
                    self.assertIn(b'ownership validation failed', result.stderr)

    @unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required for sourced hook validation')
    def test_sourcing_stub_only_defines_function_without_running_handler(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'source-only.sh'
            script.write_bytes(ADDONS.OWNERSHIP_STUB + b'\ndeclare -F chown_asterisk_hook_mytel >/dev/null\n')
            result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, b'')


class NativeCredentialsTests(unittest.TestCase):
    def test_password_is_read_literally_without_shell_evaluation_or_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = ' abc=def==$(touch /never)`do-not-run` '
            native, amp = root / 'issabel.conf', root / 'amportal.conf'
            native.write_text('amiadminpwd=keep-native\nmysqlrootpwd=' + secret + '\n', encoding='utf-8')
            amp.write_text('AMPDBNAME=asterisk\nAMPDBPASS=other-native-user\n', encoding='utf-8')
            before = (native.read_bytes(), amp.read_bytes())
            self.assertEqual(ADDONS.native_credentials(native, amp), {'user': 'root', 'password': secret})
            self.assertEqual(before, (native.read_bytes(), amp.read_bytes()))

    def test_missing_or_duplicate_native_password_fails_without_changing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native, amp = root / 'issabel.conf', root / 'amportal.conf'
            amp.write_text('AMPDBNAME=asterisk\n', encoding='utf-8')
            for text in ('amiadminpwd=existing\n', 'mysqlrootpwd=a\nmysqlrootpwd=b\n'):
                native.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    ADDONS.native_credentials(native, amp)
                self.assertEqual(native.read_text(encoding='utf-8'), text)

    def test_database_credentials_are_only_sent_on_stdin_and_diagnostics_redacted(self):
        secret = 'special-password-not-on-command-line'
        completed = subprocess.CompletedProcess([], 0, b'[]', b'')
        with mock.patch.object(ADDONS.subprocess, 'run', return_value=completed) as command:
            self.assertEqual(ADDONS.brand_database({'user': 'root', 'password': secret}, 'snapshot'), [])
        args, kwargs = command.call_args
        self.assertNotIn(secret, str(args[0]))
        self.assertEqual(json.loads(kwargs['input'])['password'], secret)
        failed = subprocess.CompletedProcess([], 1, b'', ('database error contains ' + secret).encode())
        with mock.patch.object(ADDONS.subprocess, 'run', return_value=failed):
            with self.assertRaises(ValueError) as failure:
                ADDONS.brand_database({'user': 'root', 'password': secret}, 'snapshot')
        self.assertNotIn(secret, str(failure.exception))


class NativeIdentityTests(unittest.TestCase):
    def test_product_desk_requirement_matches_the_reviewed_candidate_pin(self):
        pin = json.loads((ROOT / 'installer/myteldesk-release.json').read_text())
        self.assertEqual(pin['version'], '1.1.4')
        self.assertEqual(ADDONS.REQUIRED_DESK_VERSION, pin['version'])

    def test_only20_is_accepted_against_actual_running_output(self):
        for major in ('20',):
            self.assertEqual(ADDONS.asterisk_major('Asterisk ' + major + '.30.1 built by vendor', major), major)
        for output in ('Asterisk 16.30.1', 'Asterisk 18.26.0', 'Asterisk 22.0.0', 'Asterisk 1.8.20', 'connection refused', 'Asterisk 160.0'):
            with self.assertRaises(ValueError):
                ADDONS.asterisk_major(output)
        with self.assertRaises(ValueError):
            ADDONS.asterisk_major('Asterisk 18.26.0', '20')

    def test_brand_config_is_idempotent_and_preserves_native_and_owner_settings(self):
        original = '# native\nAMPDBPASS=keep-secret\nAMPMGRPASS=keep-ami\nOWNER=keep\nBRAND_TITLE=Issabel\n'
        result = ADDONS.replace_brand_config(original)
        self.assertEqual(result, ADDONS.replace_brand_config(result))
        self.assertIn('AMPDBPASS=keep-secret\nAMPMGRPASS=keep-ami\nOWNER=keep\n', result)
        self.assertIn('BRAND_TITLE=MytelPBX\n', result)
        with self.assertRaises(ValueError):
            ADDONS.replace_brand_config(original + 'BRAND_TITLE=duplicate\n')


class NativeReadinessTests(unittest.TestCase):
    class NextValidation(Exception):
        pass

    def setUp(self):
        self.now = 0.0
        self.sleeps = []
        self.calls = []
        self.cli_after = 0.0
        self.unready_returncode = 0
        self.services_after = dict.fromkeys(('mariadb', 'httpd', 'asterisk'), 0.0)
        self.version = b'Asterisk 20.12.0 built by vendor\n'
        self.command_seconds = 0.0
        self.command_timeouts = False
        self.command_error = None
        self.output = io.StringIO()
        patches = [
            mock.patch.object(ADDONS.time, 'monotonic', side_effect=lambda: self.now),
            mock.patch.object(ADDONS.time, 'sleep', side_effect=self.sleep),
            mock.patch.object(ADDONS, 'NATIVE_READY_SECONDS', 6.0, create=True),
            mock.patch.object(ADDONS, 'NATIVE_PROBE_SECONDS', 2.0, create=True),
            mock.patch.object(ADDONS, 'NATIVE_POLL_SECONDS', 1.0, create=True),
            mock.patch.object(ADDONS.subprocess, 'run', side_effect=self.command),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def sleep(self, seconds):
        self.assertGreater(seconds, 0)
        self.sleeps.append(seconds)
        self.now += seconds

    def command(self, argv, **kwargs):
        self.calls.append((list(argv), dict(kwargs), self.now))
        if self.command_error:
            raise self.command_error
        if self.command_timeouts:
            self.now += kwargs['timeout']
            raise subprocess.TimeoutExpired(argv, kwargs['timeout'], output=b'private-output', stderr=b'private-diagnostic')
        self.now += self.command_seconds
        if argv == ['/usr/sbin/asterisk', '-rx', 'core show version']:
            ready = self.now >= self.cli_after
            return subprocess.CompletedProcess(argv, 0 if ready else self.unready_returncode,
                                               self.version if ready else b'Unable to connect to remote asterisk',
                                               b'' if ready else b'private-diagnostic')
        if argv[:3] == ['systemctl', 'is-active', '--quiet']:
            self.assertEqual(len(argv), 4, 'Each native service must be checked independently')
            self.assertIn(argv[3], self.services_after)
            ready = self.now >= self.services_after[argv[3]]
            return subprocess.CompletedProcess(argv, 0 if ready else 3, b'', b'private-diagnostic')
        if argv == ['httpd', '-t']:
            return subprocess.CompletedProcess(argv, 0, b'', b'')
        self.fail('Readiness must only run native read-only probes: ' + repr(argv))

    def bundle(self):
        bundle = mock.MagicMock(spec=Path)
        bundle.rglob.return_value = []
        bundle.is_symlink.return_value = False
        bundle.stat.return_value.st_uid = 0
        bundle.stat.return_value.st_mode = 0o40755
        return bundle

    def wait(self, requested='20'):
        with redirect_stdout(self.output):
            return ADDONS.wait_native_ready(requested)

    def test_install_waits_for_delayed_cli_and_every_service_before_next_validation(self):
        self.cli_after = 2.0
        self.services_after['httpd'] = 3.0
        with mock.patch.object(ADDONS, 'native_credentials', return_value={'user': 'root', 'password': 'fixture-only'}), \
                mock.patch.object(ADDONS, 'load', side_effect=self.NextValidation), \
                mock.patch.object(ADDONS, 'private_directory') as backup, \
                mock.patch.object(ADDONS, 'brand_database') as database, \
                mock.patch.object(ADDONS, 'atomic_write') as write, redirect_stdout(self.output):
            with self.assertRaises(self.NextValidation):
                ADDONS.install(self.bundle(), Path('/unused-backup'), requested='20')
        self.assertGreaterEqual(self.now, 3.0)
        self.assertTrue(self.sleeps)
        self.assertIn('waiting', self.output.getvalue().lower())
        backup.assert_not_called()
        database.assert_not_called()
        write.assert_not_called()

    def test_ready_native_twenty_requires_all_three_individual_services_without_sleep(self):
        self.assertEqual(self.wait(), '20')
        self.assertEqual(self.sleeps, [])
        self.assertEqual([a for a, unused, when in self.calls], [
            ['/usr/sbin/asterisk', '-rx', 'core show version'],
            ['systemctl', 'is-active', '--quiet', 'mariadb'],
            ['systemctl', 'is-active', '--quiet', 'httpd'],
            ['systemctl', 'is-active', '--quiet', 'asterisk'],
        ])

    def test_unready_cli_with_nonzero_exit_is_also_retried_until_ready(self):
        self.unready_returncode = 1
        self.cli_after = 2.0
        self.assertEqual(self.wait(), '20')
        self.assertEqual(self.now, 2.0)
        self.assertTrue(self.sleeps)

    def test_unsupported_requested_version_fails_before_any_probe(self):
        with self.assertRaises(ValueError):
            self.wait('18')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.sleeps, [])

    def test_each_unready_native_service_prevents_success_until_the_deadline(self):
        for missing in ('mariadb', 'httpd', 'asterisk'):
            with self.subTest(service=missing):
                self.now = 0.0
                self.calls.clear()
                self.services_after = dict.fromkeys(('mariadb', 'httpd', 'asterisk'), 0.0)
                self.services_after[missing] = float('inf')
                with self.assertRaisesRegex(ValueError, 'timed out'):
                    self.wait()
                self.assertEqual(self.now, 6.0)
                self.assertIn(missing, self.output.getvalue())
                checked = {a[3] for a, unused, when in self.calls if a[0] == 'systemctl'}
                self.assertEqual(checked, {'mariadb', 'httpd', 'asterisk'})

    def test_valid_wrong_native_versions_fail_without_waiting_or_service_probes(self):
        for version in (b'Asterisk 16.30.1', b'Asterisk 18.26.0', b'Asterisk 22.0.0'):
            with self.subTest(version=version):
                self.now = 0.0
                self.calls.clear()
                self.version = version
                with self.assertRaises(ValueError):
                    self.wait()
                self.assertEqual(self.now, 0.0)
                self.assertEqual(self.sleeps, [])
                self.assertEqual(len(self.calls), 1)

    def test_command_timeouts_share_one_deadline_and_never_use_the_long_run_wrapper(self):
        self.command_timeouts = True
        with mock.patch.object(ADDONS, 'run') as long_command:
            with self.assertRaisesRegex(ValueError, 'timed out') as failure:
                self.wait()
        self.assertEqual(self.now, 6.0)
        for unused, kwargs, started in self.calls:
            self.assertGreater(kwargs['timeout'], 0)
            self.assertLessEqual(kwargs['timeout'], 2.0)
            self.assertLessEqual(kwargs['timeout'], 6.0 - started)
        self.assertNotIn('private-output', str(failure.exception) + self.output.getvalue())
        self.assertNotIn('private-diagnostic', str(failure.exception) + self.output.getvalue())
        long_command.assert_not_called()

    def test_probe_timeout_shrinks_to_the_remaining_budget(self):
        self.command_seconds = 1.4
        self.cli_after = float('inf')
        with self.assertRaisesRegex(ValueError, 'timed out'):
            self.wait()
        self.assertTrue(any(0 < kwargs['timeout'] < 2.0 for unused, kwargs, when in self.calls))
        self.assertLessEqual(max(started for unused, kwargs, started in self.calls), 6.0)
        for unused, kwargs, started in self.calls:
            self.assertLessEqual(kwargs['timeout'], 6.0 - started)

    def test_a_successful_probe_that_finishes_past_the_deadline_is_not_accepted(self):
        self.command_seconds = 1.6
        with self.assertRaisesRegex(ValueError, 'timed out'):
            self.wait()
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(self.sleeps, [])

    def test_wait_feedback_cannot_make_the_next_sleep_exceed_the_remaining_budget(self):
        owner = self
        class SlowFeedback(io.StringIO):
            def write(self, text):
                if text.startswith('Mytel addons: waiting'):
                    owner.now += 5.5
                return super().write(text)
        self.output = SlowFeedback()
        self.cli_after = float('inf')
        with self.assertRaisesRegex(ValueError, 'timed out'):
            self.wait()
        self.assertEqual(self.now, 6.0)
        self.assertEqual(self.sleeps, [0.5])

    def test_missing_probe_fails_immediately_with_sanitized_error(self):
        self.command_error = OSError('private-diagnostic')
        with self.assertRaises(ValueError) as failure:
            self.wait()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.sleeps, [])
        self.assertNotIn('private-diagnostic', str(failure.exception))

    def test_timeout_stops_install_before_backups_ui_database_or_desk_work(self):
        self.cli_after = float('inf')
        with mock.patch.object(ADDONS, 'native_credentials', return_value={'user': 'root', 'password': 'fixture-only'}), \
                mock.patch.object(ADDONS, 'private_directory') as backup, \
                mock.patch.object(ADDONS, 'load') as desk, \
                mock.patch.object(ADDONS, 'prepare_files') as ui, \
                mock.patch.object(ADDONS, 'brand_database') as database, \
                mock.patch.object(ADDONS, 'atomic_write') as write, redirect_stdout(self.output):
            with self.assertRaisesRegex(ValueError, 'timed out'):
                ADDONS.install(self.bundle(), Path('/unused-backup'), requested='20')
        for action in (backup, desk, ui, database, write):
            action.assert_not_called()

    def test_native_credentials_are_still_validated_before_any_readiness_probe(self):
        with mock.patch.object(ADDONS, 'native_credentials', side_effect=ValueError('native credentials missing')), \
                mock.patch.object(ADDONS, 'private_directory') as backup, redirect_stdout(self.output):
            with self.assertRaisesRegex(ValueError, 'native credentials missing'):
                ADDONS.install(self.bundle(), Path('/unused-backup'), requested='20')
        self.assertEqual(self.calls, [])
        backup.assert_not_called()


class NativeCelTests(unittest.TestCase):
    def test_adds_missing_payload_then_confirms_actual_odbc_reload(self):
        creds = {'user': 'root', 'password': 'fixture'}
        before = {'has_payload': False, 'table_sql': 'vendor definition'}
        after = {'has_payload': True, 'table_sql': 'vendor definition with extra'}
        status = b'CEL Logging: Enabled\nCEL Tracking Event: HANGUP\nCEL Event Subscriber: ODBC CEL backend\n'
        with tempfile.TemporaryDirectory() as temp:
            backup = Path(temp)

            def schema(credentials, create=False):
                self.assertEqual(credentials, creds)
                if create:
                    self.assertEqual(json.loads((backup / 'cel-schema-before.json').read_text()), before)
                    return after
                return after if (backup / 'cel-schema-before.json').exists() else before

            with mock.patch.object(ADDONS, 'cel_payload_schema', side_effect=schema) as db, \
                    mock.patch.object(ADDONS, 'run', side_effect=[status, b"Module 'cel_odbc.so' reloaded successfully.\n", status]) as cli:
                self.assertEqual(ADDONS.enable_cel_payload(creds, backup),
                                 {'extra_column': 'present', 'added': True, 'odbc_reloaded': True})
            self.assertEqual(db.call_args_list, [mock.call(creds), mock.call(creds, create=True), mock.call(creds)])
            self.assertEqual(cli.call_args_list[1], mock.call(['/usr/sbin/asterisk', '-rx', 'module reload cel_odbc.so'], capture=True))


class NativeSnapshotTests(unittest.TestCase):
    def test_panel_activation_sets_persian_and_restores_previous_owned_rows(self):
        for selected in ('en', 'fa', None):
            with self.subTest(native_language=selected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                database = root / 'settings.db'
                with closing(sqlite3.connect(str(database))) as connection, connection:
                    connection.execute('CREATE TABLE settings (key TEXT,value TEXT)')
                    connection.executemany('INSERT INTO settings VALUES (?,?)', [('theme', 'native'), ('owner', 'before')])
                    if selected is not None:
                        connection.execute('INSERT INTO settings VALUES (?,?)', ('language', selected))
                before = ADDONS.snapshot_settings(database, root)
                self.assertEqual(before, ([] if selected is None else [('language', selected)]) + [('theme', 'native')])
                ADDONS.activate_panel_settings(database)
                ADDONS.activate_panel_settings(database)
                with closing(sqlite3.connect(str(database))) as connection, connection:
                    self.assertEqual(dict(connection.execute('SELECT key,value FROM settings')),
                                     {'theme': 'mytel', 'language': 'fa', 'owner': 'before'})
                    connection.execute("UPDATE settings SET value='concurrent-native-edit' WHERE key='owner'")
                ADDONS.restore_settings(database, before)
                with closing(sqlite3.connect(str(database))) as connection:
                    expected = {'theme': 'native', 'owner': 'concurrent-native-edit'}
                    if selected is not None:
                        expected['language'] = selected
                    self.assertEqual(dict(connection.execute('SELECT key,value FROM settings')), expected)
                with self.assertRaises(ValueError):
                    ADDONS.restore_settings(database, [('owner', 'before')])

    def test_settings_restore_preserves_unrelated_native_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / 'settings.db'
            with closing(sqlite3.connect(str(database))) as connection, connection:
                connection.execute('CREATE TABLE settings (key TEXT,value TEXT)')
                connection.executemany('INSERT INTO settings VALUES (?,?)', [('theme', 'elastixneo'), ('language', 'en'), ('owner', 'before')])
            rows = ADDONS.snapshot_settings(database, root)
            with closing(sqlite3.connect(str(database))) as connection, connection:
                connection.execute("UPDATE settings SET value='mytel' WHERE key='theme'")
                connection.execute("UPDATE settings SET value='concurrent-native-edit' WHERE key='owner'")
            ADDONS.restore_settings(database, rows)
            with closing(sqlite3.connect(str(database))) as connection:
                values = dict(connection.execute('SELECT key,value FROM settings'))
            self.assertEqual(values, {'theme': 'elastixneo', 'language': 'en', 'owner': 'concurrent-native-edit'})
            self.assertIn('elastixneo', (root / 'settings.sql').read_text(encoding='utf-8'))

    def test_snapshot_records_original_and_new_paths_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, backup = base / 'root', base / 'backup'
            root.mkdir(); backup.mkdir()
            existing, new = root / 'existing.php', root / 'new.php'
            existing.write_bytes(b'owner-original')
            records = ADDONS.snapshot_files({existing: b'new', new: b'added'}, backup, root)
            self.assertEqual(existing.read_bytes(), b'owner-original')
            self.assertFalse(new.exists())
            self.assertEqual((backup / 'files/existing.php').read_bytes(), b'owner-original')
            info = existing.stat()
            self.assertEqual(records, [{'path': 'existing.php', 'existed': True,
                                       'uid': info.st_uid, 'gid': info.st_gid, 'mode': info.st_mode & 0o7777},
                                      {'path': 'new.php', 'existed': False}])

    def test_snapshot_refuses_destination_outside_native_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, backup = base / 'root', base / 'backup'
            root.mkdir(); backup.mkdir()
            unrelated = base / 'unrelated'
            unrelated.write_bytes(b'keep')
            with self.assertRaises(ValueError):
                ADDONS.snapshot_files({unrelated: b'wrong'}, backup, root)
            self.assertEqual(unrelated.read_bytes(), b'keep')

    def test_missing_vendor_inputs_fail_before_installed_tree_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, work = base / 'root', base / 'work'
            root.mkdir(); work.mkdir()
            marker = root / 'native-state'
            marker.write_bytes(b'unchanged')
            with self.assertRaises(ValueError):
                ADDONS.prepare_files(ROOT, root, work)
            self.assertEqual(marker.read_bytes(), b'unchanged')
            self.assertEqual(set(root.iterdir()), {marker})

    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0, 'POSIX root file ownership test')
    def test_rollback_restores_originals_removes_new_files_and_keeps_web_parents_public(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, backup = base / 'root', base / 'backup'
            root.mkdir(); backup.mkdir()
            existing, new = root / 'existing.php', root / 'web/assets/new.php'
            existing.write_bytes(b'original')
            os.chown(str(existing), 17071, 17072)
            existing.chmod(0o640)
            changes = {existing: b'changed', new: b'new'}
            records = ADDONS.snapshot_files(changes, backup, root)
            self.assertEqual((backup / 'files/existing.php').stat().st_uid, 0,
                             'The fixture must exercise a root-owned backup of a non-root original')
            saved = json.loads((backup / 'files.json').read_text(encoding='utf-8'))
            self.assertEqual((saved[0]['uid'], saved[0]['gid'], saved[0]['mode']), (17071, 17072, 0o640))
            previous = os.umask(0o077)
            try:
                for path, data in changes.items():
                    ADDONS.atomic_write(path, data)
            finally:
                os.umask(previous)
            self.assertEqual(new.parent.stat().st_mode & 0o777, 0o755)
            # Model a failed write/recovery path after partial installation has
            # changed ownership as well as content. The recorded owner wins.
            os.chown(str(existing), 0, 0)
            ADDONS.rollback_files(records, backup, root)
            self.assertEqual(existing.read_bytes(), b'original')
            self.assertEqual(existing.stat().st_mode & 0o777, 0o640)
            self.assertEqual((existing.stat().st_uid, existing.stat().st_gid), (17071, 17072))
            self.assertFalse(new.exists())

    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0, 'POSIX root SQLite ownership test')
    def test_settings_snapshot_and_row_rollback_keep_non_root_database_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / 'settings.db'
            with closing(sqlite3.connect(str(database))) as connection, connection:
                connection.execute('CREATE TABLE settings (key TEXT,value TEXT)')
                connection.executemany('INSERT INTO settings VALUES (?,?)', [('theme', 'native'), ('language', 'en')])
            os.chown(str(database), 17071, 17072)
            database.chmod(0o640)
            before = database.stat()
            rows = ADDONS.snapshot_settings(database, root)
            ADDONS.activate_panel_settings(database)
            ADDONS.restore_settings(database, rows)
            after = database.stat()
            self.assertEqual((after.st_ino, after.st_uid, after.st_gid, after.st_mode & 0o7777),
                             (before.st_ino, 17071, 17072, 0o640))


if __name__ == '__main__':
    unittest.main()
