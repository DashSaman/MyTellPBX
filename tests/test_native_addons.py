"""Native addon boundary regressions. No PBX connection or runtime claim."""
import importlib.util
from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('native_addons', str(ROOT / 'installer/native-addons.py'))
ADDONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADDONS)


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
    def test_supported_versions_are_checked_against_actual_running_output(self):
        for major in ('16', '18', '20'):
            self.assertEqual(ADDONS.asterisk_major('Asterisk ' + major + '.30.1 built by vendor', major), major)
        for output in ('Asterisk 22.0.0', 'Asterisk 1.8.20', 'connection refused', 'Asterisk 160.0'):
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


class NativeSnapshotTests(unittest.TestCase):
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
            with closing(sqlite3.connect(str(database))) as connection, connection:
                connection.execute("UPDATE settings SET value='mytel' WHERE key='theme'")
            ADDONS.restore_settings(database, rows)
            after = database.stat()
            self.assertEqual((after.st_ino, after.st_uid, after.st_gid, after.st_mode & 0o7777),
                             (before.st_ino, 17071, 17072, 0o640))


if __name__ == '__main__':
    unittest.main()
