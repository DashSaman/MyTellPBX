"""Actual DNF-only foreground logger contracts; no package/network commands."""
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'installer/dnf-progress.py'
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class DnfProgressTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'Missing DNF-only progress logger')
        spec = importlib.util.spec_from_file_location('dnf_progress', str(SCRIPT))
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def reporter(self):
        self.output = io.StringIO(); self.now = 0.0
        return self.module.ProgressReporter(self.output, 'update', clock=lambda: self.now)

    def test_real_counters_are_rate_limited_with_major_phase_transitions(self):
        reporter = self.reporter()
        reporter.observe(b'(1/200): package.rpm 20 kB/s | 1 kB 00:01')
        self.now = 5; reporter.observe(b'(2/200): package.rpm 20 kB/s | 1 kB 00:01')
        self.now = 31; reporter.observe(b'(176/200): sssd.rpm 415 kB/s | 121 kB 00:00')
        self.now = 32; reporter.observe(b'  Upgrading        : libgcc.x86_64                        1/347 ')
        self.now = 33; reporter.observe(b'  Running scriptlet: libgcc.x86_64                        1/347 ')
        self.now = 34; reporter.observe(b'  Verifying        : libgcc.x86_64                        3/347 ')
        lines = self.output.getvalue().splitlines()
        self.assertEqual(len(lines), 4)
        for current, total in [('1', '200'), ('176', '200'), ('1', '347'), ('3', '347')]:
            self.assertTrue(any(current + ' از ' + total in line for line in lines))
        self.assertNotIn('%', self.output.getvalue())
        self.assertNotIn('2 از 200', self.output.getvalue())

    def test_sensitive_raw_bytes_only_reach_private_log_including_unterminated_line(self):
        reporter = self.reporter(); raw = io.BytesIO()
        fixture = b'Failure https://user:RawSecret@repo.example/private?token=FixtureToken\n\xff\r(200/200): linux-firmware 13 MB/s | 662 MB 00:52'
        self.module.copy_progress(io.BytesIO(fixture), raw, reporter)
        self.assertEqual(raw.getvalue(), fixture)
        self.assertIn('200 از 200', self.output.getvalue())
        for secret in ['RawSecret', 'FixtureToken', 'repo.example', 'linux-firmware', 'Failure']:
            self.assertNotIn(secret, self.output.getvalue())

    def test_invalid_counts_unknown_output_and_oversized_records_are_not_printed(self):
        reporter = self.reporter(); raw = io.BytesIO()
        fixture = b'(2/1): bad\n(0/0): bad\nRandom: secret 1/10\n' + b'x' * 20000 + b'\n'
        self.module.copy_progress(io.BytesIO(fixture), raw, reporter)
        self.assertEqual(raw.getvalue(), fixture); self.assertEqual(self.output.getvalue(), '')

    def test_foreground_wrapper_preserves_failed_dnf_status_and_raw_log(self):
        source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        definitions = self.base / 'definitions.sh'; definitions.write_text(source.rsplit('\nmain "$@"', 1)[0], encoding='utf-8')
        for status in [0, 28, 42]:
            with self.subTest(status=status):
                log = self.base / ('dnf-' + str(status) + '.log')
                script = self.base / 'wrapper.sh'
                body = 'source ' + repr(definitions.as_posix()) + '\n'
                body += 'PY_BIN=' + repr(sys.executable.replace('\\', '/')) + '\nBUNDLE_DIR=' + repr(ROOT.as_posix()) + '\nLOG=' + repr(log.as_posix()) + '\n'
                body += "dnf(){ printf 'RawSecret URL=https://private.invalid\\n(176/200): package 1 MB/s\\n'; return " + str(status) + '; }\nrun_dnf_logged update -y update\n'
                script.write_text(body, encoding='utf-8')
                result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertIn('RawSecret URL=', log.read_text())
                self.assertNotIn('RawSecret', result.stdout + result.stderr)
                self.assertIn('176 از 200', result.stdout)
                if os.name == 'posix': self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    def test_noop_logger_cannot_turn_failed_dnf_into_success(self):
        source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.assertIn('run_dnf_logged()', source)
        # Both command and logger failures must propagate; no trailing say/tee.
        definition = self.base / 'definitions.sh'; definition.write_text(source.rsplit('\nmain "$@"', 1)[0])
        script = self.base / 'failed.sh'
        script.write_text('source ' + repr(definition.as_posix()) + '\nPY_BIN=true\nBUNDLE_DIR=/fixture\nLOG=/unused\ndnf(){ return 42; }\nrun_dnf_logged update -y update\n')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)])
        self.assertEqual(result.returncode, 42)

    def test_only_dnf_paths_use_progress_and_bundle_contains_logger(self):
        source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.assertIn('run_dnf_logged update -y update', source)
        self.assertIn('run_dnf_logged packages -y install "$@"', source)
        self.assertIn('run_logged() { "$@" >>"$LOG" 2>&1; }', source)
        self.assertIn('printf \'%s\\n%s\\n\' "${MYSQL_ROOT_PASS}" "${ADMIN_PASS}" | run_logged php', source)
        self.assertIn('copy_path "installer/dnf-progress.py"', (ROOT / 'scripts/build-installer-bundle.sh').read_text())


if __name__ == '__main__': unittest.main()
