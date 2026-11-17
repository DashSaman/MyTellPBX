#!/usr/bin/env python3
"""Preserve only this fresh installation's native xt_geoip outputs.

This is an ownership handoff, not a dataset-validity or service-health check.
No RPM, network, cron override, database, service or legacy DAT changes occur.
Python 3.6 compatible. SPDX-License-Identifier: GPL-2.0-only
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

OWNER = 'MytelPBX native GeoIP handoff'
SOURCE = 'var/lib/mytelpbx-installer/source.json'
PACKAGES = 'var/lib/mytelpbx-installer/stages/packages2.done'
STATE = 'var/lib/mytelpbx-installer/native-geoip.json'
ACTIVE = 'usr/share/xt_geoip'
BACKUP = 'var/backups/mytellpbx/native-geoip/xt_geoip-native'
CONFIG = 'etc/geoip_key.conf'
CRON = 'etc/cron.daily/geoip_update.sh'
PROGRAM = 'usr/local/libexec/mytellpbx/geoip-update.py'
VENDOR_SHA = '1d7f584b55f3dcba58e4271b03141fc2cbc424944172da859c3157c04ad3400c'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def exists(path):
    return path.exists() or path.is_symlink()


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns if os.name == 'posix' else None)


def sync(path):
    if os.name == 'posix':
        fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)


class Context:
    def __init__(self, root=Path('/'), version='', bundle='', uid=0):
        self.root = Path(root).absolute()
        self.version, self.bundle, self.uid = version, bundle, uid

    def path(self, name):
        return self.root / name

    def directory(self, path, create=False, private=False):
        current = self.root
        for part in Path(path).relative_to(self.root).parts:
            current = current / part
            if not exists(current) and create:
                current.mkdir(mode=0o700 if private and current == path else 0o755)
                if private and current == path: current.chmod(0o700)
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode) or (os.name == 'posix' and
                    (info.st_uid != self.uid or info.st_mode & 0o022)):
                raise ValueError('Untrusted native country ancestor retained')
            if current == path and private and os.name == 'posix' and stat.S_IMODE(info.st_mode) != 0o700:
                raise ValueError('Private preservation directory required')
        return path

    def read(self, path, private=False, limit=33554432):
        path = Path(path); self.directory(path.parent)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or not 0 <= before.st_size <= limit:
            raise ValueError('Unknown native country file retained')
        if os.name == 'posix' and (before.st_uid != self.uid or before.st_mode & 0o022
                or (private and stat.S_IMODE(before.st_mode) != 0o600)):
            raise ValueError('Unsafe native country file metadata retained')
        fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'rb') as source:
            if identity(os.fstat(source.fileno())) != identity(before): raise ValueError('Native file changed')
            raw = source.read(limit + 1)
            if len(raw) != before.st_size or identity(os.fstat(source.fileno())) != identity(before):
                raise ValueError('Native file changed')
        if identity(path.lstat()) != identity(before): raise ValueError('Native file changed')
        return raw

    def save(self, value, previous=None):
        path = self.path(STATE); self.directory(path.parent, private=True)
        raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
        if exists(path) and (previous is None or self.read(path, private=True) != previous):
            raise ValueError('Unknown preservation receipt retained')
        if not exists(path) and previous is not None: raise ValueError('Owned receipt disappeared')
        fd, name = tempfile.mkstemp(prefix='.native-geoip-', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(raw); output.flush(); os.fchmod(output.fileno(), 0o600); os.fsync(output.fileno())
            if previous is None: os.link(name, str(path))
            else:
                if self.read(path, private=True) != previous: raise ValueError('Owned receipt changed')
                os.replace(name, str(path))
            sync(path.parent)
        finally:
            if os.path.exists(name): os.unlink(name)


def source(ctx):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', ctx.version) or not re.fullmatch('[0-9a-f]{64}', ctx.bundle):
        raise ValueError('Exact installer source required')
    ctx.directory(ctx.path(SOURCE).parent, private=True)
    raw = ctx.read(ctx.path(SOURCE), private=True, limit=16384)
    value = json.loads(raw.decode('utf-8'))
    expected = dict(owner='MyTellPBX', schema=1, version=ctx.version, bundle_sha256=ctx.bundle)
    if value != expected or type(value.get('schema')) is not int: raise ValueError('Installer source differs')
    updater = Path(__file__).with_name('geoip-update.py')
    # The already verified bundle supplies this public updater; no import or execution here.
    return dict(expected, source_sha256=sha(raw), updater_sha256=sha(updater.read_bytes()))


def record(ctx):
    raw = ctx.read(ctx.path(STATE), private=True, limit=2097152)
    value = json.loads(raw.decode('utf-8'))
    if (value.get('owner') != OWNER or type(value.get('schema')) is not int or value['schema'] != 1
            or value.get('phase') not in ('held', 'moving', 'handoff') or value.get('source') != source(ctx)):
        raise ValueError('Unknown native preservation receipt retained')
    keys = {'owner', 'schema', 'phase', 'source', 'initial', 'dataset_validity_claimed'}
    if value['phase'] != 'held': keys.update(('tree', 'packages2', 'active_id'))
    if (set(value) != keys or value['initial'] not in ({'kind': 'absent'}, {'kind': 'empty'})
            or value['dataset_validity_claimed'] is not False):
        raise ValueError('Unknown preservation receipt shape retained')
    return raw, value


def configuration(ctx, completed=False):
    if exists(ctx.path(CONFIG)): raise ValueError('Existing GeoIP key configuration retained')
    path = ctx.path(CRON)
    if not exists(path): return False
    raw = ctx.read(path, limit=1048576)
    if sha(raw) == VENDOR_SHA: return True
    if completed:
        updater = load_updater(ctx)
        if raw == updater.WRAPPER: return True
    raise ValueError('Unknown GeoIP cron retained')


def empty(ctx, path):
    ctx.directory(path.parent)
    if not exists(path): return False
    ctx.directory(path)
    if any(path.iterdir()): raise ValueError('Populated unknown country data retained')
    return True


def inventory(ctx, path):
    ctx.directory(path); result = {}; total = 0
    def scan(folder, prefix=''):
        nonlocal total
        before = folder.lstat()
        result[prefix or '/'] = dict(uid=before.st_uid, gid=before.st_gid,
                                     mode=stat.S_IMODE(before.st_mode))
        with os.scandir(str(folder)) as entries:
            for entry in entries:
                name = prefix + entry.name; info = entry.stat(follow_symlinks=False)
                if not prefix and entry.name in ('BE', 'LE') and stat.S_ISDIR(info.st_mode):
                    ctx.directory(Path(entry.path)); scan(Path(entry.path), entry.name + '/'); continue
                if not re.fullmatch(r'(?:(?:BE|LE)/)?[A-Z0-9]{2}\.iv[46]', name):
                    raise ValueError('Unknown native country output retained')
                if len(result) >= 3000: raise ValueError('Native country count exceeds limit')
                raw = ctx.read(Path(entry.path)); total += len(raw)
                if total > 128 * 1024 * 1024 or len(raw) % (8 if name.endswith('4') else 32):
                    raise ValueError('Native country output exceeds format bounds')
                result[name] = dict(bytes=len(raw), sha256=sha(raw), uid=info.st_uid,
                                    gid=info.st_gid, mode=stat.S_IMODE(info.st_mode), mtime_ns=info.st_mtime_ns)
        if identity(folder.lstat()) != identity(before): raise ValueError('Native country directory changed')
    scan(path)
    for prefix in ('', 'BE/', 'LE/'):
        for family in ('4', '6'):
            if not any(k.startswith(prefix) and '/' not in k[len(prefix):] and k.endswith('.iv' + family) for k in result):
                raise ValueError('Incomplete native country tree retained')
    return result


def stage(ctx):
    raw = ctx.read(ctx.path(PACKAGES), limit=0)
    if raw: raise ValueError('Unexpected packages2 marker')
    info = ctx.path(PACKAGES).lstat()
    return dict(dev=info.st_dev, ino=info.st_ino, mode=stat.S_IMODE(info.st_mode), mtime_ns=info.st_mtime_ns)


def load_updater(ctx):
    path = ctx.path(PROGRAM)
    if sha(ctx.read(path, limit=2097152)) != source(ctx)['updater_sha256']:
        raise ValueError('Managed updater source differs')
    spec = importlib.util.spec_from_file_location('native_geoip_owned_updater', str(path))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def completed(ctx, value):
    if stage(ctx) != value['packages2']: raise ValueError('Packages marker changed')
    backup = ctx.path(BACKUP); ctx.directory(backup.parent, private=True)
    if inventory(ctx, backup) != value['tree']: raise ValueError('Preserved native country data changed')
    active = ctx.path(ACTIVE)
    if active.is_symlink():
        updater = load_updater(ctx)
        release = active.resolve().parent
        expected_parent = ctx.path('usr/share/mytellpbx-geoip/releases')
        if active.resolve().name != 'BE' or release.parent != expected_parent:
            raise ValueError('Unknown active country pointer retained')
        ctx.directory(release); ctx.directory(active.resolve())
        updater.release_info(release)
        if ctx.read(ctx.path(CRON), limit=1048576) != updater.WRAPPER:
            raise ValueError('Managed cron differs')
    elif exists(active):
        empty(ctx, active)


def hold(ctx):
    identity_source = source(ctx)
    if exists(ctx.path(STATE)):
        _, value = record(ctx); configuration(ctx, value['phase'] == 'handoff')
        if value['phase'] == 'handoff': completed(ctx, value)
        return value
    configuration(ctx)
    if exists(ctx.path(PACKAGES)): raise ValueError('Cannot adopt packages completed before native hold')
    active = ctx.path(ACTIVE); kind = 'empty' if empty(ctx, active) else 'absent'
    value = dict(owner=OWNER, schema=1, source=identity_source, phase='held', initial=dict(kind=kind),
                 dataset_validity_claimed=False)
    ctx.save(value); return value


def handoff(ctx):
    raw, value = record(ctx)
    configuration(ctx, value['phase'] == 'handoff')
    marker = stage(ctx)
    if value['phase'] == 'handoff':
        if marker != value['packages2']: raise ValueError('Packages marker changed')
        completed(ctx, value); return value
    active = ctx.path(ACTIVE); backup = ctx.path(BACKUP)
    if value['phase'] == 'held':
        if not configuration(ctx): raise ValueError('Native GeoIP cron missing')
        if exists(backup): raise ValueError('Existing preservation backup retained')
        tree = inventory(ctx, active)
        parent = ctx.directory(backup.parent, create=True, private=True)
        info = active.lstat()
        if info.st_dev != parent.stat().st_dev: raise ValueError('Atomic native preservation requires one filesystem')
        value.update(phase='moving', tree=tree, packages2=marker, active_id=[info.st_dev, info.st_ino])
        ctx.save(value, raw); raw, value = record(ctx)
    if marker != value['packages2']: raise ValueError('Packages marker changed')
    ctx.directory(backup.parent, private=True)
    if not exists(backup):
        info = active.lstat()
        if ([info.st_dev, info.st_ino] != value['active_id'] or inventory(ctx, active) != value['tree']):
            raise ValueError('Native country tree changed after preservation intent')
        if source(ctx) != value['source']: raise ValueError('Installer source changed')
        if not configuration(ctx): raise ValueError('Native cron disappeared')
        os.rename(str(active), str(backup)); sync(active.parent); sync(backup.parent)
    if inventory(ctx, backup) != value['tree']: raise ValueError('Preserved country tree differs')
    if not empty(ctx, active):
        active.mkdir(mode=0o755); active.chmod(0o755); sync(active.parent)
    if source(ctx) != value['source'] or not configuration(ctx):
        raise ValueError('Source or native configuration changed during preservation')
    value['phase'] = 'handoff'; ctx.save(value, raw); return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--hold', action='store_true'); action.add_argument('--handoff', action='store_true')
    parser.add_argument('--version', required=True); parser.add_argument('--bundle-sha256', required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0: raise ValueError('Linux root required')
    ctx = Context(version=args.version, bundle=args.bundle_sha256)
    value = hold(ctx) if args.hold else handoff(ctx)
    print('Native GeoIP ownership phase: ' + value['phase'] + '; dataset validity not asserted')


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError, TypeError):
        print('Native GeoIP preservation refused; existing data retained', file=sys.stderr); sys.exit(1)
