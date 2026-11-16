"""Execute the optional prebootstrap chown line against local absent/present fixtures."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASH='C:/Program Files/Git/bin/bash.exe'if os.name=='nt'else shutil.which('bash')

class OptionalAmportalTests(unittest.TestCase):
    def test_missing_optional_binary_is_skipped_and_present_optional_failure_ignored(self):
        source=(ROOT/'install-mytellpbx.sh').read_text(encoding='utf-8')
        line=next(line for line in source.splitlines()if '/usr/sbin/amportal chown'in line)
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);binary=root/'amportal';calls=root/'calls';log=root/'log'
            for present in [False,True]:
                with self.subTest(present=present):
                    if present:binary.write_text('#!/bin/bash\nprintf called >> "$CALLS"\nexit 1\n');binary.chmod(0o755)
                    command=line.replace('/usr/sbin/amportal',repr(binary.as_posix()))
                    script=root/'test.sh';script.write_text('export CALLS='+repr(calls.as_posix())+'\nLOG='+repr(log.as_posix())+'\n'+command+'\nprintf continued\n')
                    result=subprocess.run([BASH,'--noprofile','--norc',str(script)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
                    self.assertEqual(result.returncode,0,result.stderr);self.assertIn(b'continued',result.stdout)
                    self.assertEqual(calls.exists(),present)
                    if not present:self.assertFalse(log.exists()and log.stat().st_size,'Absent optional binary should not be invoked or log an error')

if __name__=='__main__':unittest.main()
