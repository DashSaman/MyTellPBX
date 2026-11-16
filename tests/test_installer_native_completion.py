"""Native init success must not hide pending migrations or lose ownership.

The actual Bash stage functions run against private temporary fixtures. All
service, password, SQL and native provisioning actions are intercepted.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASH='C:/Program Files/Git/bin/bash.exe'if os.name=='nt'else shutil.which('bash')

@unittest.skipUnless(BASH, 'Bash is required for the real stage fixture')
class NativeCompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.spool=self.base/'updates';self.spool.mkdir();self.state=self.base/'state';(self.state/'stages').mkdir(parents=True)
        self.calls=self.base/'calls';self.marker=self.state/'stages/framework.done'
        self.source=(ROOT/'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.source=self.source.rsplit('\nmain "$@"',1)[0].replace('/var/spool/issabel-mysqldbscripts',self.spool.as_posix())
        self.definitions=self.base/'definitions.sh';self.definitions.write_text(self.source,encoding='utf-8')
        self.setup='source '+repr(self.definitions.as_posix())+'\nLOG='+repr((self.base/'log').as_posix())+'\nSTATE_DIR='+repr(self.state.as_posix())+'\nCALLS='+repr(self.calls.as_posix())+'\nPY_BIN='+repr(Path(sys.executable).as_posix())+'\nADMIN_PASS=fixture-only-panel\nMYSQL_ROOT_PASS=fixture-only-database\n'
    def shell(self,body):
        script=self.base/'case.sh';script.write_text(self.setup+body,encoding='utf-8')
        return subprocess.run([BASH,'--noprofile','--norc',str(script)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8',timeout=20)
    def framework(self):
        return self.shell('''stage_done(){ return 1; }; step(){ :; }; ensure_credentials(){ :; }
framework_service_config(){ printf absent; }; guard_empty_framework_bootstrap(){ :; }
systemctl(){ :; }; wait_asterisk_ready(){ :; }; bootstrap_empty_framework(){ :; }
initialize_preserving_framework_keys(){ printf 'NATIVE_INIT_EXIT0_CORRECT_KEYS\n'; }
verify_mysql_root_password(){ :; }; verify_mysql_authentication(){ :; }
ensure_admin_credentials(){ :; }; verify_amp_admin_password(){ :; }
php(){ cat >/dev/null; }; run_logged(){ :; }
mark_stage(){ printf '%s\n' "$1" >> "$CALLS"; }
stage_framework_init
''')
    def test_successful_native_migrations_allow_framework_completion(self):
        (self.spool/'readme.txt').write_text('not a native migration')
        result=self.framework();self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(self.calls.read_text().splitlines(),['framework'])
    def test_empty_or_absent_native_spool_allows_framework_completion(self):
        for absent in [False,True]:
            with self.subTest(absent=absent):
                if absent:self.spool.rmdir()
                if self.calls.exists():self.calls.unlink()
                result=self.framework();self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(self.calls.read_text().splitlines(),['framework'])
    def test_exit0_correct_credentials_but_failed_sql_or_shell_migration_refuses_completion(self):
        for suffix in ['sql','sh']:
            with self.subTest(suffix=suffix):
                pending=self.spool/('failed.'+suffix);raw=b'disposable failed native migration fixture\n';pending.write_bytes(raw)
                if self.calls.exists():self.calls.unlink()
                result=self.framework();self.assertIn('NATIVE_INIT_EXIT0_CORRECT_KEYS',result.stdout)
                self.assertNotEqual(result.returncode,0,'Unapplied native migration must not be certified by password success')
                self.assertIn(suffix+'=1',result.stderr);self.assertNotIn(pending.name,result.stdout+result.stderr)
                self.assertFalse(self.calls.exists());self.assertEqual(pending.read_bytes(),raw);pending.unlink()
    def assert_spool_refused(self):
        result=self.framework()
        self.assertIn('NATIVE_INIT_EXIT0_CORRECT_KEYS',result.stdout)
        self.assertNotEqual(result.returncode,0,'Unsafe migration spool must not be certified complete')
        self.assertFalse(self.calls.exists());self.assertIn('native migration',result.stderr)
        self.assertIn('scoped repair',result.stderr)
        return result
    def test_pending_directory_is_refused_without_deletion(self):
        pending=self.spool/'unknown.sql';pending.mkdir()
        self.assert_spool_refused();self.assertTrue(pending.is_dir())
    def test_spool_regular_file_is_refused_without_replacement(self):
        self.spool.rmdir();self.spool.write_bytes(b'not a migration directory')
        self.assert_spool_refused();self.assertEqual(self.spool.read_bytes(),b'not a migration directory')
    @unittest.skipUnless(os.name=='posix','POSIX links are exercised by the native fixture')
    def test_linked_spool_is_refused_even_when_target_empty(self):
        target=self.base/'different-directory';target.mkdir();self.spool.rmdir();self.spool.symlink_to(target,target_is_directory=True)
        self.assert_spool_refused();self.assertTrue(self.spool.is_symlink());self.assertEqual(list(target.iterdir()),[])
    @unittest.skipUnless(os.name=='posix','POSIX links are exercised by the native fixture')
    def test_pending_link_is_refused_without_following_or_deleting_target(self):
        target=self.base/'retained-target';target.write_bytes(b'private fixture bytes')
        pending=self.spool/'unknown.sh';pending.symlink_to(target)
        result=self.assert_spool_refused();self.assertTrue(pending.is_symlink())
        self.assertEqual(target.read_bytes(),b'private fixture bytes')
        self.assertNotIn('retained-target',result.stdout+result.stderr)
        self.assertNotIn('private fixture bytes',result.stdout+result.stderr)
    @unittest.skipUnless(os.name=='posix'and hasattr(os,'mkfifo'),'Native POSIX special-file fixture')
    def test_pending_fifo_is_refused_without_reading_or_deleting_it(self):
        import stat
        pending=self.spool/'unknown.sql';os.mkfifo(str(pending))
        self.assert_spool_refused();self.assertTrue(stat.S_ISFIFO(pending.lstat().st_mode))
    def test_incomplete_selfcheck_retains_framework_marker_and_requests_scoped_repair(self):
        missing=self.base/'missing-pjsip.conf';source=self.source.replace('/etc/asterisk/pjsip_additional.conf',missing.as_posix())
        doctor=self.base/'myteldesk';doctor.write_text('#!/bin/bash\nprintf UNEXPECTED_DOCTOR >> '+repr(self.calls.as_posix())+'\nexit 99\n');doctor.chmod(0o755)
        self.definitions.write_text(source.replace('/usr/local/sbin/myteldesk',doctor.as_posix()),encoding='utf-8');self.marker.write_text('owned completed marker')
        result=self.shell('''step(){ :; }; ensure_credentials(){ :; }; bootstrap_query_count(){ printf 57; }
run_logged(){ :; }; systemctl(){ :; }; verify_asterisk_service(){ :; }; verify_mysql_authentication(){ :; }
sleep(){ :; }; php(){ printf mytel; }; curl(){ printf login; }; mark_stage(){ :; }
stage_selfcheck
''')
        self.assertNotEqual(result.returncode,0);self.assertTrue(self.marker.exists(),'Incomplete selfcheck must retain the owned framework marker');self.assertEqual(self.marker.read_text(),'owned completed marker')
        self.assertIn('scoped repair',result.stderr);self.assertIn('existing data retained',result.stderr)
        self.assertNotIn('run the installer again to repair',result.stderr);self.assertFalse(self.calls.exists())

if __name__=='__main__':unittest.main()
