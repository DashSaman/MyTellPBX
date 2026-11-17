"""Real Main/embedded hostname guard in temporary roots; no DNS or host writes."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class HostnameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); (self.root / 'etc').mkdir(mode=0o700)
        self.hosts = self.root / 'etc/hosts'; self.hosts.write_bytes(b'127.0.0.1 localhost .localdomain4\n::1 localhost\n')
        self.hosts.chmod(0o644); self.state = self.root / 'state'; self.state.mkdir(mode=0o700)
        self.source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.version = re.search(r'^MYTELLPBX_VERSION="([^"]+)"', self.source, re.M).group(1)
        self.pin = re.search(r'^MYTELLPBX_BUNDLE_SHA256="([^"]+)"', self.source, re.M).group(1)
        self.receipt = self.state / 'source.json'
        self.receipt.write_text(json.dumps(dict(owner='MyTellPBX', schema=1, version=self.version, bundle_sha256=self.pin)))
        self.receipt.chmod(0o600)

    def driver(self, hostname='mytelpbx-fixture', injection=''):
        match = re.search(r"<<'PY_HOSTNAME'[^\n]*\n(.*?)\nPY_HOSTNAME", self.source, re.S)
        # Old Main has no guard and leaves hosts unchanged: the intended RED.
        code = match.group(1) if match else ''
        embedded = self.root / 'embedded.py'; embedded.write_text(code, encoding='utf-8')
        driver = self.root / 'driver.py'
        driver.write_text('import socket\nsocket.gethostname=lambda: ' + repr(hostname) + '\n' + injection
                          + '\nwith open(' + repr(str(embedded)) + ', encoding="utf-8") as source: code=source.read()\n'
                          + 'exec(compile(code, "Main:hostname", "exec"))\n', encoding='utf-8')
        return driver

    def run_guard(self, mode='prepare', hostname='mytelpbx-fixture', injection=''):
        return subprocess.run([sys.executable, '-B', str(self.driver(hostname, injection)), mode,
                               str(self.hosts), str(self.state), self.version, self.pin],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)

    def test_missing_exact_hostname_gets_one_loopback_alias_and_backup_then_noop(self):
        before = self.hosts.read_bytes(); result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.hosts.read_bytes(), before + b'127.0.0.1 mytelpbx-fixture\n')
        backup = self.state / 'hostname-hosts.before.json'; self.assertTrue(backup.is_file())
        saved = backup.read_bytes(); metadata = self.hosts.stat()
        result = self.run_guard(); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(backup.read_bytes(), saved)
        self.assertEqual(self.hosts.stat().st_ino, metadata.st_ino)
        if os.name == 'posix':
            self.assertEqual(self.hosts.stat().st_mode & 0o777, 0o644)
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_existing_ipv4_ipv6_and_case_insensitive_aliases_remain_byte_identical(self):
        for raw in [b'192.0.2.5 other MYTELPBX-FIXTURE # preserve\n', b'::1 mytelpbx-fixture\n',
                    b'2001:db8::1 other mytelpbx-fixture\r\n']:
            with self.subTest(raw=raw):
                self.hosts.write_bytes(raw); before = self.hosts.stat()
                self.receipt.write_text('unknown operator source'); self.receipt.chmod(0o600)
                result = self.run_guard(); self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.hosts.read_bytes(), raw); self.assertEqual(self.hosts.stat().st_ino, before.st_ino)
                self.assertFalse((self.state / 'hostname-hosts.before.json').exists())

    def test_comments_and_substrings_do_not_count_as_aliases_and_bytes_are_preserved(self):
        raw = b'# mytelpbx-fixture\xff\n127.0.0.1 mytelpbx-fixture-other'
        self.hosts.write_bytes(raw); result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.hosts.read_bytes(), raw + b'\n127.0.0.1 mytelpbx-fixture\n')

    def test_invalid_hostname_or_mapping_and_binary_hosts_refuse_without_backup(self):
        for hostname, raw in [('bad/name', b'127.0.0.1 localhost\n'), ('192.0.2.3', b'127.0.0.1 localhost\n'),
                              ('mytelpbx-fixture', b'invalid-ip mytelpbx-fixture\n'),
                              ('mytelpbx-fixture', b'127.0.0.1 localhost\x00\n')]:
            with self.subTest(hostname=hostname, raw=raw):
                self.hosts.write_bytes(raw); result = self.run_guard(hostname=hostname)
                self.assertNotEqual(result.returncode, 0); self.assertEqual(self.hosts.read_bytes(), raw)
                self.assertFalse((self.state / 'hostname-hosts.before.json').exists())

    def test_existing_framework_or_deployment_and_untrusted_source_refuse(self):
        for relative in ['state/stages/framework.done', 'etc/asterisk', 'var/www/html/admin', 'etc/myteldesk']:
            with self.subTest(relative=relative):
                marker = self.root / relative; marker.parent.mkdir(parents=True, exist_ok=True); marker.touch()
                before = self.hosts.read_bytes(); result = self.run_guard()
                self.assertNotEqual(result.returncode, 0); self.assertEqual(self.hosts.read_bytes(), before)
                marker.unlink()
        self.receipt.write_text('{}'); self.receipt.chmod(0o600)
        self.assertNotEqual(self.run_guard().returncode, 0)

    def test_unknown_backup_and_concurrent_operator_change_are_preserved(self):
        before = self.hosts.read_bytes(); backup = self.state / 'hostname-hosts.before.json'
        backup.write_bytes(b'unknown'); backup.chmod(0o600)
        self.assertNotEqual(self.run_guard().returncode, 0)
        self.assertEqual(backup.read_bytes(), b'unknown'); self.assertEqual(self.hosts.read_bytes(), before)
        backup.unlink()
        injection = ('import tempfile, pathlib\noriginal=tempfile.mkstemp\n'
                     'def changed(*a, **kw):\n'
                     '    result=original(*a, **kw)\n'
                     '    if kw.get("prefix")==".mytel-hosts-": pathlib.Path(' + repr(str(self.hosts)) + ').write_bytes(b"operator change\\n")\n'
                     '    return result\ntempfile.mkstemp=changed\n')
        self.assertNotEqual(self.run_guard(injection=injection).returncode, 0)
        self.assertEqual(self.hosts.read_bytes(), b'operator change\n')

    def test_interrupted_owned_backup_resumes_without_changing_original_preimage(self):
        before = self.hosts.read_bytes()
        injection = '''import tempfile
original=tempfile.mkstemp
def failed(*a, **kw):
    if kw.get('prefix')=='.mytel-hosts-': raise OSError('fixture before publication')
    return original(*a, **kw)
tempfile.mkstemp=failed
'''
        self.assertNotEqual(self.run_guard(injection=injection).returncode, 0)
        self.assertEqual(self.hosts.read_bytes(), before)
        backup = self.state / 'hostname-hosts.before.json'; saved = backup.read_bytes()
        result = self.run_guard(); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(backup.read_bytes(), saved)
        self.assertEqual(self.hosts.read_bytes(), before + b'127.0.0.1 mytelpbx-fixture\n')

    @unittest.skipUnless(hasattr(os, 'setxattr'), 'Native extended attributes')
    def test_native_mode_owner_and_extended_attributes_are_preserved(self):
        os.setxattr(str(self.hosts), 'user.fixture', b'preserved metadata')
        self.hosts.chmod(0o640); before = self.hosts.stat()
        result = self.run_guard(); self.assertEqual(result.returncode, 0, result.stderr)
        after = self.hosts.stat()
        self.assertEqual((after.st_uid, after.st_gid, after.st_mode & 0o777),
                         (before.st_uid, before.st_gid, 0o640))
        self.assertEqual(os.getxattr(str(self.hosts), 'user.fixture'), b'preserved metadata')

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX symlink/mode boundary')
    def test_symlink_and_writable_hosts_are_refused(self):
        outside = self.root / 'outside'; outside.write_bytes(b'preserve')
        self.hosts.unlink(); self.hosts.symlink_to(outside)
        self.assertNotEqual(self.run_guard().returncode, 0); self.assertEqual(outside.read_bytes(), b'preserve')
        self.hosts.unlink(); self.hosts.write_bytes(b'127.0.0.1 localhost\n'); self.hosts.chmod(0o666)
        self.assertNotEqual(self.run_guard().returncode, 0)
        self.hosts.chmod(0o644); os.link(str(self.hosts), str(self.root / 'hardlink'))
        self.assertNotEqual(self.run_guard().returncode, 0)

    def test_real_main_prepares_alias_after_credentials_and_before_native_work(self):
        definitions = self.root / 'definitions.sh'; definitions.write_text(self.source.rsplit('\nmain "$@"', 1)[0], encoding='utf-8')
        body = 'source ' + shlex.quote(definitions.as_posix()) + '\n'
        for key, value in {'LOG': self.root / 'log', 'STATE_DIR': self.state, 'PY_BIN': Path(sys.executable)}.items():
            body += key + '=' + shlex.quote(value.as_posix()) + '\n'
        body += 'hostname_hosts_file(){ "$PY_BIN" ' + shlex.quote(self.driver().as_posix()) + ' "$1" ' + shlex.quote(self.hosts.as_posix()) + ' "$STATE_DIR" "$MYTELLPBX_VERSION" "$MYTELLPBX_BUNDLE_SHA256"; }\n'
        body += '''preflight(){ :; }; acquire_lock(){ :; }; write_install_source(){ :; }; initialize_workspace(){ :; }
verify_bundle(){ :; }; initialize_media(){ :; }; ensure_credentials(){ printf CREDENTIALS; }
guard_install_source(){ :; }; rpm(){ if IFS= read -r unexpected; then return 99; fi; return 1; }
repair_platform_catalog(){ :; }; stage_repos(){ grep -q '^127.0.0.1 mytelpbx-fixture$' ''' + shlex.quote(self.hosts.as_posix()) + ''' || exit 24; printf NATIVE; }
stage_native_platform(){ :; }; stage_update(){ :; }; stage_packages1(){ :; }; stage_tls(){ :; }; native_geoip(){ :; }
stage_packages2(){ :; }; stage_cli_status(){ :; }; stage_post_base(){ :; }; stage_framework_init(){ :; }
stage_mytel_layer(){ :; }; stage_webrtc_dtls(){ :; }; stage_geoip(){ :; }; stage_myteldesk(){ :; }; stage_selfcheck(){ :; }; finish(){ :; }
main
'''
        script = self.root / 'main.sh'; script.write_text(body, encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], input=b'NotForNativeRpm\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'CREDENTIALS', result.stdout); self.assertIn(b'NATIVE', result.stdout)

    def test_real_fresh_detector_refuses_installed_pbx_but_existing_mapping_is_noop(self):
        definitions = self.root / 'definitions.sh'; definitions.write_text(self.source.rsplit('\nmain "$@"', 1)[0], encoding='utf-8')
        for mapped in [False, True]:
            with self.subTest(mapped=mapped):
                raw = b'192.0.2.8 mytelpbx-fixture\n' if mapped else b'127.0.0.1 localhost\n'
                self.hosts.write_bytes(raw); called = self.root / 'rpm-called'
                if called.exists(): called.unlink()
                body = 'source ' + shlex.quote(definitions.as_posix()) + '\n'
                for key, value in {'LOG': self.root / 'log', 'STATE_DIR': self.state, 'PY_BIN': Path(sys.executable)}.items():
                    body += key + '=' + shlex.quote(value.as_posix()) + '\n'
                body += 'hostname_hosts_file(){ "$PY_BIN" ' + shlex.quote(self.driver().as_posix()) + ' "$1" ' + shlex.quote(self.hosts.as_posix()) + ' "$STATE_DIR" "$MYTELLPBX_VERSION" "$MYTELLPBX_BUNDLE_SHA256"; }\n'
                body += 'guard_install_source(){ :; }; rpm(){ printf called > ' + shlex.quote(called.as_posix()) + '; return 0; }\nensure_local_hostname_resolution\n'
                script = self.root / 'fresh.sh'; script.write_text(body, encoding='utf-8')
                result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                self.assertEqual(result.returncode == 0, mapped, result.stderr)
                self.assertEqual(called.exists(), not mapped)
                self.assertEqual(self.hosts.read_bytes(), raw)
                self.assertFalse((self.state / 'hostname-hosts.before.json').exists())


if __name__ == '__main__': unittest.main()
