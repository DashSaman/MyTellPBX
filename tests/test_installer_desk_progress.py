"""Desk command elapsed notices with fake child processes, never RPM or services."""
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class FakeChild:
    def __init__(self, argv, clock, duration, returncode):
        self.args = argv; self.clock = clock; self.remaining = duration
        self.final_code = returncode; self.returncode = None
        self.waits = []; self.kills = 0

    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.kills: return self.returncode
        if timeout is not None and self.remaining > timeout:
            self.clock[0] += timeout; self.remaining -= timeout
            raise subprocess.TimeoutExpired(self.args, timeout)
        self.clock[0] += self.remaining; self.remaining = 0
        self.returncode = self.final_code
        return self.returncode

    def communicate(self, input=None, timeout=None):
        self.wait(timeout); return None, None

    def poll(self): return self.returncode

    def kill(self):
        self.kills += 1; self.returncode = -9


class DeskProgressTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('desk_progress', str(ROOT / 'installer/install-myteldesk.py'))
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.argv = ['/usr/local/sbin/myteldesk', 'doctor']
        self.clock = [0.0]; self.options = None

    def run_child(self, duration, status=0, output=None):
        self.child = FakeChild(self.argv, self.clock, duration, status)
        def spawn(argv, **options):
            self.assertEqual(argv, self.argv); self.options = options
            return self.child
        with mock.patch.object(self.module.subprocess, 'Popen', side_effect=spawn), \
             mock.patch.object(self.module.time, 'monotonic', side_effect=lambda: self.clock[0]), \
             mock.patch('sys.stdout', output if output is not None else io.StringIO()):
            self.module.run_command(self.argv)

    def test_slow_child_shows_fixed_elapsed_notices_without_commands_or_percent(self):
        output = io.StringIO()
        self.run_child(65, output=output)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn('30 seconds', lines[0]); self.assertIn('60 seconds', lines[1])
        self.assertNotIn('/usr/local', output.getvalue()); self.assertNotIn('doctor', output.getvalue())
        self.assertNotIn('%', output.getvalue())
        self.assertTrue(all(timeout <= 30 for timeout in self.child.waits))
        self.assertEqual(self.child.kills, 0)

    def test_fast_child_has_no_heartbeat_and_cannot_read_terminal(self):
        output = io.StringIO(); self.run_child(1, output=output)
        self.assertEqual(output.getvalue(), '')
        self.assertIs(self.options.get('stdin'), subprocess.DEVNULL)
        self.assertIsNone(self.options.get('stdout')); self.assertIsNone(self.options.get('stderr'))
        self.assertFalse(self.options.get('shell', False))

    def test_nonzero_child_preserves_failure_without_killing_completed_child(self):
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            self.run_child(31, 7)
        self.assertEqual(failure.exception.returncode, 7)
        self.assertEqual(self.child.kills, 0)

    def test_broken_heartbeat_output_does_not_kill_active_child_or_mask_exit(self):
        class BrokenOutput:
            def write(self, _value): raise BrokenPipeError('fixture output failure')
            def flush(self): pass
        self.run_child(65, output=BrokenOutput())
        self.assertEqual(self.clock[0], 65); self.assertEqual(self.child.kills, 0)
        self.clock[0] = 0
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            self.run_child(65, 9, BrokenOutput())
        self.assertEqual(failure.exception.returncode, 9); self.assertEqual(self.child.kills, 0)

    def test_original_2700_second_deadline_and_timeout_cleanup_are_preserved(self):
        with self.assertRaises(subprocess.TimeoutExpired) as failure:
            self.run_child(3000)
        self.assertEqual(failure.exception.timeout, 2700)
        self.assertEqual(self.clock[0], 2700); self.assertEqual(self.child.kills, 1)
        self.assertIn(None, self.child.waits)

    def test_argument_values_are_never_echoed_in_heartbeat(self):
        self.argv = ['python', '-B', '/private/installer/install.py', 'install', '--fixture-secret', 'NeverEchoSecret']
        output = io.StringIO(); self.run_child(31, output=output)
        self.assertNotIn('NeverEchoSecret', output.getvalue())
        self.assertNotIn('/private', output.getvalue())
        self.assertIn('30 seconds', output.getvalue())


if __name__ == '__main__': unittest.main()
