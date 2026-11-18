"""DNF renderer and private-log contracts for the native online installer."""
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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

    def test_output_failures_drain_input_to_eof_and_fail_without_interrupting_dnf(self):
        class BrokenOutput:
            def write(self, _data): raise BrokenPipeError('fixture output closed')
            def flush(self): pass
        class FailedLog:
            def write(self, _data): raise OSError('fixture disk full')
            def flush(self): pass
        fixture = b'(1/200): first\n' + b'x' * 70000 + b'\n(200/200): last\n'
        source = io.BytesIO(fixture); raw = io.BytesIO()
        reporter = self.module.ProgressReporter(BrokenOutput(), 'update')
        self.assertFalse(self.module.copy_progress(source, raw, reporter))
        self.assertEqual(source.tell(), len(fixture)); self.assertEqual(raw.getvalue(), fixture)
        source = io.BytesIO(fixture)
        self.assertFalse(self.module.copy_progress(source, FailedLog(), self.reporter()))
        self.assertEqual(source.tell(), len(fixture))

    def test_short_private_log_writes_are_completed_without_data_loss(self):
        class ShortLog(io.BytesIO):
            def write(self, data): return super().write(data[:3])
        fixture = b'(1/200): first\n(200/200): last'
        raw = ShortLog()
        self.assertTrue(self.module.copy_progress(io.BytesIO(fixture), raw, self.reporter()))
        self.assertEqual(raw.getvalue(), fixture)

    def invoke_main(self, source, output=None):
        log = self.base / 'direct.log'; output = output if output is not None else io.StringIO()
        with patch.object(sys, 'argv', [str(SCRIPT), '--log', str(log), '--kind', 'update']), \
             patch.object(sys, 'stdin', SimpleNamespace(buffer=source)), \
             patch.object(sys, 'stdout', output), patch.object(sys, 'stderr', io.StringIO()):
            status = self.module.main()
        return status, log, output

    def test_console_language_preserves_private_bytes_counters_and_failure_drain(self):
        class BrokenConsole:
            def write(self, _data): raise BrokenPipeError('fixture')
            def flush(self): pass
        fixture = b'RawSecret URL=https://private.invalid\n(176/200): private-package\n'
        for english in ['0', '1']:
            with self.subTest(english=english), patch.dict(os.environ, {'MYTELL_CONSOLE_ENGLISH': english}):
                log_path = self.base / 'direct.log'
                if log_path.exists(): log_path.unlink()
                status, log, output = self.invoke_main(io.BytesIO(fixture))
                self.assertEqual(status, 0); self.assertEqual(log.read_bytes(), fixture)
                self.assertIn('176 of 200' if english == '1' else '176 از 200', output.getvalue())
                if english == '1': self.assertNotRegex(output.getvalue(), r'[\u0600-\u06ff]')
                self.assertNotIn('RawSecret', output.getvalue()); self.assertNotIn('private-package', output.getvalue())
                log_path.unlink()
                source = io.BytesIO(fixture + b'x' * 70000 + b'\n')
                status, log, _output = self.invoke_main(source, BrokenConsole())
                self.assertEqual(status, 1); self.assertEqual(source.tell(), len(fixture) + 70001)
                self.assertEqual(log.read_bytes(), fixture + b'x' * 70000 + b'\n')
                error_output = io.StringIO(); source = io.BytesIO(fixture)
                with patch.object(self.module, 'open_private_log', side_effect=OSError('fixture error')), \
                     patch.object(sys, 'argv', [str(SCRIPT), '--log', str(log_path), '--kind', 'update']), \
                     patch.object(sys, 'stdin', SimpleNamespace(buffer=source)), patch.object(sys, 'stderr', error_output):
                    self.assertEqual(self.module.main(), 1)
                self.assertEqual(source.tell(), len(fixture))
                self.assertIn('Private package logging failed' if english == '1' else 'ثبت امن گزارش', error_output.getvalue())
                if english == '1': self.assertNotRegex(error_output.getvalue(), r'[\u0600-\u06ff]')

    def test_main_check_log_never_reads_input_or_prints_progress(self):
        class UnreadInput:
            def read(self, _size): raise AssertionError('check-log must never read stdin')
        output = io.StringIO(); log = self.base / 'check.log'
        with patch.object(sys, 'argv', [str(SCRIPT), '--log', str(log), '--kind', 'packages', '--check-log']), \
             patch.object(sys, 'stdin', SimpleNamespace(buffer=UnreadInput())), patch.object(sys, 'stdout', output):
            self.assertEqual(self.module.main(), 0)
        self.assertEqual(log.read_bytes(), b''); self.assertEqual(output.getvalue(), '')

    def test_main_success_keeps_full_raw_log_and_only_safe_public_progress(self):
        fixture = b'RawSecret URL=https://private.invalid\r\n(176/200): private-package'
        status, log, output = self.invoke_main(io.BytesIO(fixture))
        self.assertEqual(status, 0); self.assertEqual(log.read_bytes(), fixture)
        self.assertIn('176 از 200', output.getvalue()); self.assertNotIn('RawSecret', output.getvalue())
        self.assertNotIn('private-package', output.getvalue())

    def test_main_open_and_console_failures_drain_then_return_failure(self):
        class BrokenConsole:
            def write(self, _data): raise BrokenPipeError('fixture')
            def flush(self): pass
        fixture = b'(1/200): first\n' + b'x' * 70000 + b'\n(200/200): last'
        source = io.BytesIO(fixture)
        with patch.object(self.module, 'open_private_log', side_effect=OSError('fixture open error')):
            status, _log, _output = self.invoke_main(source)
        self.assertEqual(status, 1); self.assertEqual(source.tell(), len(fixture))
        source = io.BytesIO(fixture)
        status, log, _output = self.invoke_main(source, BrokenConsole())
        self.assertEqual(status, 1); self.assertEqual(source.tell(), len(fixture))
        self.assertEqual(log.read_bytes(), fixture)

    def test_invalid_counts_unknown_output_and_oversized_records_are_not_printed(self):
        reporter = self.reporter(); raw = io.BytesIO()
        fixture = b'(2/1): bad\n(0/0): bad\nRandom: secret 1/10\n' + b'x' * 20000 + b'\n'
        self.module.copy_progress(io.BytesIO(fixture), raw, reporter)
        self.assertEqual(raw.getvalue(), fixture); self.assertEqual(self.output.getvalue(), '')

    def test_detailed_output_uses_observed_counts_and_validated_rpm_names(self):
        output = io.StringIO()
        reporter = self.module.ProgressReporter(output, 'packages', english=True, detail=True)
        stream = (b'(1/2):  httpd-2.4.37-62.el8.x86_64.rpm 10 MB/s\r'
                  b'(1/2):  httpd-2.4.37-62.el8.x86_64.rpm 10 MB/s\r'
                  b'(2/2): https://example.invalid/private?secret=RedactMe\n'
                  b'  Installing : dep-1.2-3.el8.noarch 1/2\n'
                  b'  Running scriptlet : dep-1.2-3.el8.noarch 1/2\n'
                  b'  Verifying : URL https://example.invalid/token: RedactMe.noarch 2/2')
        raw = io.BytesIO()
        self.assertTrue(self.module.copy_progress(io.BytesIO(stream), raw, reporter))
        self.assertEqual(raw.getvalue(), stream)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 4)
        self.assertIn('Download  1/2  httpd-2.4.37-62.el8.x86_64.rpm', lines[0])
        self.assertIn('Transaction  1/2  dep-1.2-3.el8.noarch', lines[2])
        self.assertNotIn('RedactMe', output.getvalue())

    def test_idle_message_is_about_waiting_and_preserves_the_next_observation(self):
        output = io.StringIO()
        self.now = 0
        reporter = self.module.ProgressReporter(output, 'update', clock=lambda: self.now,
                                                interval=20, english=True, detail=True)
        readiness = iter((False, True, True))
        def wait():
            self.now = 20
            return next(readiness)
        stream = b'(2/2):  httpd-2.4.37-62.el8.x86_64.rpm 10 MB/s'
        raw = io.BytesIO()
        self.assertTrue(self.module.copy_progress(io.BytesIO(stream), raw, reporter, wait_for_input=wait))
        self.assertIn('Waiting for package manager output · 20s', output.getvalue())
        self.assertIn('Download  2/2', output.getvalue())
        self.assertEqual(raw.getvalue(), stream)
    @unittest.skipIf(os.name != 'posix', 'Native POSIX private-log boundary')
    def test_log_refuses_symlink_and_nonprivate_file(self):
        outside = self.base / 'outside'; outside.write_bytes(b'original')
        target = self.base / 'log'; target.symlink_to(outside)
        with self.assertRaises(ValueError): self.module.open_private_log(target)
        self.assertEqual(outside.read_bytes(), b'original')
        target.unlink(); target.write_bytes(b'original'); target.chmod(0o666)
        with self.assertRaises(ValueError): self.module.open_private_log(target)
        self.assertEqual(target.read_bytes(), b'original')

    @unittest.skipIf(os.name != 'posix', 'Native POSIX FIFO boundary')
    def test_log_fifo_is_refused_without_blocking(self):
        fifo = self.base / 'fifo'; os.mkfifo(str(fifo), 0o600)
        # Expected refusal is a test result, not an unhandled crash-report event.
        # Unexpected exceptions must never satisfy this exact sentinel assertion.
        code = """import errno, importlib.util, sys
s=importlib.util.spec_from_file_location('p',sys.argv[1])
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
try:
    stream=m.open_private_log(sys.argv[2])
except OSError as error:
    if error.errno != errno.ENXIO: raise
    sys.exit(23)
except ValueError as error:
    if str(error) != 'DNF log must be a regular file': raise
    sys.exit(23)
else:
    stream.close()
    sys.exit(0)
"""
        result = subprocess.run([sys.executable, '-c', code, str(SCRIPT), str(fifo)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2)
        self.assertEqual(result.returncode, 23, result.stderr)



if __name__ == '__main__': unittest.main()
