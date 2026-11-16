"""Cold native-unit readiness: real stage orchestration, all OS commands mocked."""
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class ProbeFixture:
    def __init__(self,mode='ready'):
        self.mode=mode;self.now=0.0;self.calls=[];self.cli_count=0;self.boot_count=0;self.unit_count=0;self.messages=[];self.log=io.BytesIO()
    def clock(self):return self.now
    def pause(self,delay):self.now+=delay
    def run(self,args,**options):
        assert options['stdin']==subprocess.DEVNULL and options['close_fds']is True
        assert 0<options['timeout']<=5
        self.calls.append((args,options['timeout']));self.now+=0.01
        if args[0]=='systemctl':
            self.unit_count+=1;assert args[1:3]==['show','asterisk']
            if self.mode=='unit-timeout':self.now+=options['timeout'];raise subprocess.TimeoutExpired(args,options['timeout'])
            if self.mode=='unit-error':return SimpleNamespace(returncode=1,stdout=b'',stderr=b'fixture unavailable')
            active='failed'if self.mode=='inactive'else'active';pid=78 if self.mode=='pid-change'and self.unit_count>1 else 77
            restarts=1 if self.mode=='restarted'else 0
            cgroup='/unrelated.service'if self.mode=='wrong-cgroup'else'/system.slice/asterisk.service'
            return SimpleNamespace(returncode=0,stdout=('ActiveState='+active+'\nSubState=running\nMainPID='+str(pid)+'\nNRestarts='+str(restarts)+'\nControlGroup='+cgroup+'\n').encode(),stderr=b'fixture warning'if self.mode=='unit-stderr'else b'')
        assert args[0:2]==['asterisk','-rx'];self.cli_count+=1;command=args[2]
        if self.mode=='timeout':
            self.now+=options['timeout'];raise subprocess.TimeoutExpired(args,options['timeout'],output=b'',stderr=b'fixture client timeout')
        if self.mode=='missing-command':raise FileNotFoundError('fixture executable absent')
        if self.mode=='never'or(self.mode=='delayed'and self.cli_count<3):return SimpleNamespace(returncode=1,stdout=b'',stderr=b'control socket absent')
        if command=='core show version':
            text=b''if self.mode=='empty-version'else b'Asterisk 20.12.0 built by fixture\n'
        else:
            assert command=='core waitfullybooted'
            self.boot_count+=1
            if self.mode=='boot-delayed'and self.boot_count<3:
                self.now+=options['timeout'];raise subprocess.TimeoutExpired(args,options['timeout'])
            text=b"No such command 'core waitfullybooted'"if self.mode=='unknown-boot'else(b''if self.mode=='empty-boot'else b'Asterisk has fully booted.\n')
        warning=(self.mode=='version-stderr'and command=='core show version')or(self.mode=='boot-stderr'and command=='core waitfullybooted')
        return SimpleNamespace(returncode=0,stdout=text,stderr=b'fixture error/warning'if warning else b'')


class NativeReadinessProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=(ROOT/'install-mytellpbx.sh').read_text(encoding='utf-8')
        block=source.split('wait_asterisk_ready() {',1)[1].split('\n}\n',1)[0]
        python=re.search(r"<<'PY'\n([\s\S]+?)\nPY",block).group(1)
        cls.namespace={'__name__':'probe_tests'};exec(compile(python,'actual-inline-readiness','exec'),cls.namespace)
    def exercise(self,fixture,timeout=180):
        return self.namespace['wait_ready'](fixture.log,run=fixture.run,clock=fixture.clock,pause=fixture.pause,emit=fixture.messages.append,timeout=timeout)
    def test_immediate_ready_requires_supported_full_boot_marker_and_stable_unit(self):
        f=ProbeFixture();self.exercise(f)
        self.assertEqual([a[2]for a,_ in f.calls if a[0]=='asterisk'],['core show version','core waitfullybooted'])
        self.assertGreaterEqual(f.unit_count,2);self.assertTrue(any('ready' in message.lower()for message in f.messages))
    def test_delayed_control_socket_retries_read_only_with_elapsed_feedback(self):
        f=ProbeFixture('delayed');self.exercise(f)
        self.assertGreaterEqual(f.cli_count,4);self.assertGreater(f.now,0)
        self.assertIn(b'control socket absent',f.log.getvalue())
        self.assertTrue(any('elapsed' in message for message in f.messages))
        self.assertTrue(all(args[0:2]in (['systemctl','show'],['asterisk','-rx'])for args,_ in f.calls))
    def test_inactive_unit_stops_before_cli(self):
        f=ProbeFixture('inactive')
        with self.assertRaisesRegex(RuntimeError,'active'):self.exercise(f)
        self.assertEqual(f.cli_count,0)
    def test_unavailable_unit_or_wrong_cgroup_is_fatal(self):
        for mode in ['unit-timeout','unit-error','wrong-cgroup']:
            with self.subTest(mode=mode):
                f=ProbeFixture(mode)
                with self.assertRaises(RuntimeError):self.exercise(f)
                self.assertEqual(f.cli_count,0)
    def test_waitfullybooted_client_timeouts_do_not_restart_daemon(self):
        f=ProbeFixture('boot-delayed');self.exercise(f)
        self.assertEqual(f.boot_count,3);self.assertGreaterEqual(f.now,14)
        self.assertTrue(all(args[0:2]in (['systemctl','show'],['asterisk','-rx'])for args,_ in f.calls))
    def test_log_failure_does_not_continue_to_cli_or_report_success(self):
        class BrokenLog:
            def write(self,value):raise OSError('fixture log unavailable')
        f=ProbeFixture();f.log=BrokenLog()
        with self.assertRaises(OSError):self.exercise(f)
        self.assertEqual(f.cli_count,0);self.assertFalse(any(message.startswith('Native Asterisk ready')for message in f.messages))
    def test_changed_pid_or_automatic_restart_is_not_readiness(self):
        for mode in ['pid-change','restarted']:
            with self.subTest(mode=mode):
                with self.assertRaises(RuntimeError):self.exercise(ProbeFixture(mode))
    def test_unknown_or_empty_successful_cli_is_refused(self):
        for mode in ['unknown-boot','empty-boot','empty-version']:
            with self.subTest(mode=mode):
                with self.assertRaises(RuntimeError):self.exercise(ProbeFixture(mode))
    def test_zero_exit_with_warning_or_error_stderr_is_not_success(self):
        for mode in ['version-stderr','boot-stderr','unit-stderr']:
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(RuntimeError,'stderr'):self.exercise(ProbeFixture(mode))
    def test_missing_cli_executable_is_fatal(self):
        f=ProbeFixture('missing-command')
        with self.assertRaises(OSError):self.exercise(f)
        self.assertEqual(f.cli_count,1)
    def test_per_probe_timeout_and_total_monotonic_deadline(self):
        for mode in ['never','timeout']:
            with self.subTest(mode=mode):
                f=ProbeFixture(mode)
                with self.assertRaisesRegex(RuntimeError,'deadline'):self.exercise(f,timeout=12)
                self.assertLessEqual(f.now,12.02);self.assertTrue(all(0<duration<=5 for _,duration in f.calls))
                self.assertFalse(any(message.startswith('Native Asterisk ready')for message in f.messages))
    def test_long_wait_has_bounded_elapsed_not_fake_percentage(self):
        f=ProbeFixture('never')
        with self.assertRaises(RuntimeError):self.exercise(f,timeout=35)
        self.assertGreaterEqual(len(f.messages),3);self.assertLessEqual(len(f.messages),4)
        self.assertTrue(all('%'not in message for message in f.messages))


class NativeReadinessStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        definitions = self.base / 'definitions.sh'
        definitions.write_text(source.rsplit('\nmain "$@"', 1)[0], encoding='utf-8')
        bootstrap = self.base / 'python-bootstrap.py'
        bootstrap.write_text('''import os, subprocess, sys, time
from pathlib import Path
from types import SimpleNamespace
root=Path(os.environ['FIXTURE_ROOT']); clock=[0.0]
def fake_run(args, **options):
    assert args[0] in ('systemctl','asterisk'), 'No real OS command permitted'
    assert options['stdin']==subprocess.DEVNULL and 0<options['timeout']<=5
    clock[0]+=0.01
    with (root/'calls').open('a') as out:out.write('probe '+' '.join(args)+'\\n')
    if args[0]=='systemctl':
        assert args[1:3]==['show','asterisk']
        return SimpleNamespace(returncode=0,stdout=b'ActiveState=active\\nSubState=running\\nMainPID=77\\nNRestarts=0\\nControlGroup=/system.slice/asterisk.service\\n',stderr=b'')
    assert args[1]=='-rx'
    counter=root/'cli-count'; count=int(counter.read_text() if counter.exists() else '0')+1;counter.write_text(str(count))
    if count==1:return SimpleNamespace(returncode=1,stdout=b'',stderr=b'Unable to connect: control socket absent\\n')
    if args[2]=='core show version':return SimpleNamespace(returncode=0,stdout=b'Asterisk 20.12.0 built by fixture\\n',stderr=b'')
    assert args[2]=='core waitfullybooted'
    return SimpleNamespace(returncode=0,stdout=b'Asterisk has fully booted.\\n',stderr=b'')
subprocess.run=fake_run;time.monotonic=lambda:clock[0];time.sleep=lambda delay:clock.__setitem__(0,clock[0]+delay)
code=sys.stdin.read();sys.argv=['-']+sys.argv[1:];exec(compile(code,'actual-inline-readiness','exec'),{'__name__':'__main__'})
''', encoding='utf-8')
        self.script = '''source {definitions}
LOG={log}; CALLS={calls}; CLI_COUNT={counter}
export FIXTURE_ROOT={base}
REAL_PY={python}; BOOTSTRAP={bootstrap}
python_fixture() {{ shift 2; "$REAL_PY" "$BOOTSTRAP" "$@"; }}
PY_BIN=python_fixture
stage_done() {{ return 1; }}; step() {{ :; }}; ensure_credentials() {{ :; }}
framework_service_config() {{ printf absent; }}; guard_empty_framework_bootstrap() {{ :; }}
bootstrap_empty_framework() {{ printf 'BOOTSTRAP\\n' >> "$CALLS"; exit 42; }}
systemctl() {{ printf 'unit %s\\n' "$*" >> "$CALLS"; }}
asterisk() {{
    local count=0
    [ ! -f "$CLI_COUNT" ] || count=$(cat "$CLI_COUNT")
    count=$((count+1)); printf '%s' "$count" > "$CLI_COUNT"
    printf 'direct CLI %s\\n' "$*" >> "$CALLS"
    if [ "$count" = 1 ]; then printf 'Unable to connect: control socket absent\\n' >&2; return 1; fi
    printf 'Asterisk 20.12.0 built by fixture\\n'
}}
run_logged() {{ printf 'UNEXPECTED MUTATION %s\\n' "$*" >> "$CALLS"; return 99; }}
stage_framework_init
'''.format(definitions=repr(definitions.as_posix()), log=repr((self.base/'log').as_posix()),
           calls=repr((self.base/'calls').as_posix()), counter=repr((self.base/'cli-count').as_posix()),
           base=repr(self.base.as_posix()), python=repr(Path(sys.executable).as_posix()), bootstrap=repr(bootstrap.as_posix()))

    def test_cold_delayed_socket_waits_before_bootstrap_with_one_native_start(self):
        script = self.base / 'stage.sh'; script.write_text(self.script, encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 42, result.stderr)
        calls = (self.base/'calls').read_text()
        self.assertEqual(calls.count('unit start asterisk'), 1)
        self.assertIn('BOOTSTRAP', calls)
        self.assertNotIn('UNEXPECTED MUTATION', calls)
        self.assertNotIn('restart', calls); self.assertNotIn('safe_asterisk', calls)


if __name__ == '__main__': unittest.main()
