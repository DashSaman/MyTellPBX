"""Cold native-unit readiness: real stage orchestration, all OS commands mocked."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


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
