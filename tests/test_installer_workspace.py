"""Execute real bundle functions using disposable files and no host provisioning.

POSIX filesystem semantics are required. UID probes alone are fixture adapters:
the test runs unprivileged, while modelling a root-owned install workspace.
No PBX command, network request, package manager or service action is executed.
"""
import hashlib
import io
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'Native POSIX workspace/symlink contract')
class InstallerWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mytell-workspace-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.private = self.base / 'private'
        self.private.mkdir(mode=0o700)
        self.outside = self.base / 'outside'
        self.outside.mkdir()
        self.archive = self.base / 'fixture.tgz'
        data = b'fixture payload only\n'
        digest = hashlib.sha256(data).hexdigest()
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, content in {'fixture/payload.txt': data, 'fixture/manifest.json': b'{}\n',
                                  'fixture/SHA256SUMS': (digest + '  payload.txt\n').encode()}.items():
                member = tarfile.TarInfo(name)
                member.mode = 0o644
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        source = (REPO / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        source, calls = re.subn(r'^main "\$@"\s*$', '# Test loads definitions only.', source, flags=re.M)
        self.assertEqual(calls, 1, 'Cannot safely detach the installer entry point')
        self.source = source

    def execute(self, body, private=None):
        private = private or self.private
        quote = shlex.quote
        # Actual filesystem modes and operations stay real; only root UID probes
        # are adapted so this suite can run with no capabilities as nobody.
        fixtures = '''
id() { if [ "$#" -eq 1 ] && [ "$1" = '-u' ]; then printf '0\\n'; else command id "$@"; fi; }
stat() {
    if [ "$#" -ge 2 ] && [ "$1" = '-c' ]; then local format="${2//%u/0}"; shift 2; command stat -c "$format" "$@";
    else command stat "$@"; fi
}
say() { :; }
warn() { :; }
die() { printf 'EXPECTED-REFUSAL: %s\\n' "$*" >&2; exit 1; }
'''
        settings = {
            'LOG': str(self.base / 'fixture.log'), 'WORK_DIR': str(private),
            'BUNDLE_TMP': str(private / 'fixture.tgz.part'), 'BUNDLE_FINAL': str(private / 'fixture.tgz'),
            'BUNDLE_ROOT': str(private / 'extracted'), 'MYTELL_BUNDLE_FILE': str(self.archive),
            'MYTELLPBX_BUNDLE_SHA256': hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            'MYTELLPBX_BUNDLE': 'fixture.tgz', 'STATE_DIR': str(self.base / 'state'),
        }
        assignments = '\n'.join(key + '=' + quote(value) for key, value in settings.items())
        return subprocess.run(['bash', '-s'], input=(self.source + '\n' + fixtures + assignments + '\n' + body),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              cwd=str(self.base), timeout=20,
                              env=dict(os.environ, TMPDIR=str(self.base)))

    def test_download_destination_symlink_never_clobbers_another_file(self):
        victim = self.outside / 'retained.txt'
        victim.write_bytes(b'operator data must remain\n')
        (self.private / 'fixture.tgz').symlink_to(victim)
        result = self.execute('verify_bundle')
        self.assertEqual(victim.read_bytes(), b'operator data must remain\n',
                         'The real installer followed a pre-existing destination symlink')
        self.assertNotEqual(result.returncode, 0, 'A symlinked download destination must be refused')

    def test_bundle_paths_outside_owned_workspace_are_refused_before_copy(self):
        destination = self.outside / 'unowned-cache.tgz'
        result = self.execute('BUNDLE_FINAL=' + shlex.quote(str(destination)) + '\nverify_bundle')
        self.assertFalse(destination.exists(), 'The real installer wrote outside its private workspace')
        self.assertNotEqual(result.returncode, 0)

    def test_world_writable_workspace_is_refused_before_copy(self):
        self.private.chmod(0o777)
        result = self.execute('verify_bundle')
        self.assertFalse((self.private / 'fixture.tgz').exists())
        self.assertNotEqual(result.returncode, 0)

    def test_private_workspace_preserves_real_verified_bundle_flow(self):
        result = self.execute('verify_bundle')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.private / 'extracted/fixture/payload.txt').read_bytes(), b'fixture payload only\n')

    def test_existing_regular_verified_archive_is_a_valid_workspace_child(self):
        shutil.copyfile(str(self.archive), str(self.private / 'fixture.tgz'))
        result = self.execute('verify_bundle')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.private / 'extracted/fixture/payload.txt').read_bytes(), b'fixture payload only\n')

    def test_initializer_uses_fresh_private_paths_and_exit_cleanup_is_scoped(self):
        retained = self.outside / 'retained.txt'
        retained.write_bytes(b'keep\n')
        # The real POSIX allocator and EXIT trap execute. Only a fresh private
        # directory is writable; unrelated fixture files must remain untouched.
        result = self.execute('''
WORK_DIR=''
initialize_workspace
printf '%s\\n' "$WORK_DIR" "$BUNDLE_TMP" "$BUNDLE_FINAL" "$BUNDLE_ROOT"
command stat -c %a "$WORK_DIR"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertGreaterEqual(len(lines), 5, 'Initializer must expose its owned paths')
        work = Path(lines[-5])
        self.assertTrue(work.is_absolute())
        self.assertNotEqual(work, self.private)
        self.assertEqual(lines[-1], '700')
        for name in lines[-4:-1]:
            self.assertIn(work, Path(name).parents)
        self.assertFalse(work.exists(), 'The owned fresh workspace must be cleaned on exit')
        self.assertEqual(retained.read_bytes(), b'keep\n')
