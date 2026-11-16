#!/usr/bin/env python3
"""Prepare native required includes before the first install_amp manager reload.

Only the exact observed IssabelPBX framework installer or known repaired bytes
are accepted. The existing native include preparation block is moved intact;
a failed preparation stops before apply_conf/reload. No native SQL, passwords,
module logic or binary is changed. Canonical root-owned OS parents are trusted
against concurrent privileged replacement. Python3.6 compatible.

SPDX-License-Identifier: GPL-2.0-only
Native boundary: Copyright 2006-2014 Schmooze Com Inc.; 2022 Issabel Foundation.
Original legal notices are retained byte for byte in the vendor executable.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile

ORIGINAL_SHA256 = '2524787d3fb15068ab126d3d35ff7bdf539466aeb0d01a3935f2ea8e23cffd15'
PATCHED_SHA256 = '799ba95ba7c068a9f14d535ddec68d988d33af01a85ecee3b83d9f1921d4fd22'
TARGET = 'usr/src/issabelPBX/framework/install_amp'
APPLY_START = b'    // edit conf file passwords and then\n'
INCLUDE_START = b'    /* As of Asterisk 1.4.16 or there about, a missing #include file will make the reload fail. So\n'
INCLUDE_END = b'    if (! $include_err) {\n        out("OK");\n    }\n\n'
FAIL_GUARD = b'    if ($include_err) {\n        out("Required native #include preparation failed; reload not attempted.");\n        exit(1);\n    }\n\n'

def transform(source):
    checksum=hashlib.sha256(source).hexdigest()
    if checksum==PATCHED_SHA256:
        if source.count(FAIL_GUARD)!=1 or source.index(INCLUDE_START)>source.index(APPLY_START):
            raise ValueError('Known native include boundary changed')
        return source
    if checksum!=ORIGINAL_SHA256:raise ValueError('Unknown native framework installer; no files changed')
    if any(source.count(marker)!=1 for marker in (APPLY_START,INCLUDE_START,INCLUDE_END)) or FAIL_GUARD in source:
        raise ValueError('Missing or duplicate native include boundary')
    first=source.index(APPLY_START);middle=source.index(INCLUDE_START);last=source.index(INCLUDE_END)+len(INCLUDE_END)
    if not first<middle<last:raise ValueError('Native include order differs')
    result=source[:first]+source[middle:last]+FAIL_GUARD+source[first:middle]+source[last:]
    if hashlib.sha256(result).hexdigest()!=PATCHED_SHA256:raise ValueError('Unexpected native ordering result')
    return result


def regular_file(path):
    path = Path(path)
    if path.resolve() != path.absolute():
        raise ValueError('Symlinked executable/backup path refused')
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError('Executable/backup must be a regular file')
    if os.name == 'posix' and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022):
        raise ValueError('Unsafe executable/backup ownership or write permissions')
    return metadata


def identity(metadata):
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns,
            metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode))


def plan(root):
    base = Path(root).absolute()
    if base.resolve() != base: raise ValueError('Symlinked source root refused')
    parent = base
    for part in Path(TARGET).parts[:-1]:
        parent = parent / part
        metadata = parent.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or (os.name == 'posix' and
                (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022)):
            raise ValueError('Unsafe native installer parent')
    path = base / TARGET
    previous = regular_file(path)
    before = path.read_bytes()
    return path, before, transform(before), previous


def unchanged(path, before, previous):
    if identity(regular_file(path)) != identity(previous) or path.read_bytes() != before:
        raise ValueError('Vendor executable changed after validation; refusing overwrite')


def write_change(change, backup_root):
    path, before, after, previous = change
    unchanged(path, before, previous)
    if before == after: return False
    backup_root = Path(backup_root).absolute()
    if backup_root.resolve() != backup_root:
        raise ValueError('Symlinked backup directory refused')
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not backup_root.is_dir() or (os.name == 'posix' and backup_root.stat().st_uid != os.geteuid()):
        raise ValueError('Unsafe backup directory ownership')
    backup_root.chmod(0o700)
    backup = backup_root / ('install_amp-' + hashlib.sha256(before).hexdigest() + '.original')
    if backup.exists() or backup.is_symlink():
        saved = regular_file(backup)
        if os.name == 'posix' and stat.S_IMODE(saved.st_mode) != 0o600:
            raise ValueError('Vendor backup is not private')
        if backup.read_bytes() != before:
            raise ValueError('Original vendor backup differs; refusing overwrite')
    else:
        fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(before); stream.flush(); os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix='.mytel-include-order-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(after); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temporary, stat.S_IMODE(previous.st_mode))
            if hasattr(os, 'fchown'): os.fchown(stream.fileno(), previous.st_uid, previous.st_gid)
        unchanged(path, before, previous)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return True


def apply(root, backup_root):
    return write_change(plan(root), backup_root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--backup-root', type=Path, default=Path('/var/backups/mytellpbx/native-include-order'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0: parser.error('root required')
    if args.check:
        _path, before, after, _metadata = plan(args.root)
        print('MytelPBX native include ordering: ' + ('would update' if before != after else 'unchanged'))
    else:
        print('MytelPBX native include ordering: ' + ('updated' if apply(args.root, args.backup_root) else 'unchanged'))


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError) as error:
        print('MytelPBX native include ordering repair refused: ' + str(error), file=sys.stderr)
        sys.exit(1)
