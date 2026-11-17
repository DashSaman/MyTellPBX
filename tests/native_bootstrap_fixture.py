"""Disposable real-Bash fixtures for the native bootstrap; no host provisioning."""
import hashlib
import io
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class BootstrapFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='native-bootstrap-contract-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.work = self.base / 'private'
        self.work.mkdir(mode=0o700)
        self.archive = self.base / 'bundle.tgz'
        self.events = self.base / 'events'
        self.source = (ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8')
        self.version = re.search(r'^MYTELLPBX_VERSION="([0-9.]+)"$', self.source, re.M).group(1)
        self.prefix = 'mytelpbx-bundle-' + self.version
        self.output = self.work / 'payload'
        self.payload = self.output / self.prefix
        self.definitions = self.base / 'definitions.sh'
        self.definitions.write_text(self.source, encoding='utf-8')

    def make_archive(self, extra=(), bad_checksum=False):
        files = {'payload.txt': b'public fixture payload\n',
                 'run.sh': b'#!/bin/sh\nexit 0\n', 'manifest.json': b'{}\n'}
        for name in ('issabel5-netinstall.sh', 'mytelpbx-netinstall.sh', 'derive-native.py'):
            relative = 'installer/vendor-native/' + name
            files[relative] = (ROOT / relative).read_bytes()
        files['SHA256SUMS'] = ''.join(
            hashlib.sha256(b'wrong' if bad_checksum else data).hexdigest() + '  ./' + name + '\n'
            for name, data in files.items()).encode()
        with tarfile.open(str(self.archive), 'w:gz') as archive:
            for name in (self.prefix + '/', self.prefix + '/empty/'):
                info = tarfile.TarInfo(name)
                info.type, info.mode, info.uid, info.gid = tarfile.DIRTYPE, 0o7777, 12345, 12346
                archive.addfile(info)
            for name, data in files.items():
                info = tarfile.TarInfo(self.prefix + '/' + name)
                info.size, info.uid, info.gid = len(data), 12345, 12346
                info.mode = 0o6755 if name.endswith('.sh') else 0o6640
                archive.addfile(info, io.BytesIO(data))
            for info in extra:
                archive.addfile(info, io.BytesIO(b'x' * info.size) if info.isreg() else None)
        return files

    def shell(self, body, values=None, definitions=None):
        settings = {'MYTEL_NATIVE_WORK': self.work, 'MYTEL_PYTHON': Path(sys.executable).as_posix(),
                    'MYTELL_BUNDLE_FILE': self.archive, 'MYTELLPBX_BUNDLE_SHA256':
                    hashlib.sha256(self.archive.read_bytes()).hexdigest() if self.archive.is_file() else 'a' * 64,
                    'EVENTS': self.events}
        settings.update(values or {})
        script = 'source ' + shlex.quote((definitions or self.definitions).as_posix()) + '\n'
        script += '\n'.join(key + '=' + shlex.quote(str(value).replace('\\', '/'))
                            for key, value in settings.items()) + '\n' + body
        return subprocess.run([BASH, '--noprofile', '--norc', '-s'], input=script.encode('utf-8'),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
