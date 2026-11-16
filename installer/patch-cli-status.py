#!/usr/bin/env python3
"""Keep Issabel's status dialog out of its explicitly selected --cli mode.

Only the exact observed Issabel 5 executable or its known patched bytes are
accepted. No authentication, database, functional error or interactive dialog
logic is changed or executed. Root-owned OS directories are trusted against
concurrent changes by another privileged process. Python 3.6 compatible.

The insertion into Issabel code and extracted test fixture are GPL version 2:
SPDX-License-Identifier: GPL-2.0-only
Original program copyright (c) 2023 Issabel Foundation and
copyright (c) 2006 Palosanto Solutions S. A. Original notices remain unchanged.
https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile

ORIGINAL_SHA256 = 'aa1a9bc962d5f34c57483d802b7f5e1e010133d2bf3245dc07b644387d9ef410'
PATCHED_SHA256 = 'd5b692ffeaf073707e6d3754adbcbe364c4cdee270cab5b6902797e88b89abc7'
HEADER = b'function dialog_infobox($backtitle, $msgbox, $height, $width)\n{\n'
CLI_GUARD = (b"    if (isset($GLOBALS['argv']) && is_array($GLOBALS['argv'])\n"
             b"        && in_array('--cli', $GLOBALS['argv'], true)) return;\n")


def transform(source):
    checksum = hashlib.sha256(source).hexdigest()
    if checksum == PATCHED_SHA256:
        if source.count(HEADER + CLI_GUARD) != 1 or source.count(CLI_GUARD) != 1:
            raise ValueError('Known CLI status guard boundary changed')
        return source
    if checksum != ORIGINAL_SHA256:
        raise ValueError('Unknown Issabel password tool source; no files changed')
    if source.count(HEADER) != 1 or CLI_GUARD in source:
        raise ValueError('Missing, duplicate or changed status function boundary')
    result = source.replace(HEADER, HEADER + CLI_GUARD, 1)
    if hashlib.sha256(result).hexdigest() != PATCHED_SHA256:
        raise ValueError('Unexpected CLI status repair result')
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
    path = Path(root).absolute() / 'usr/bin/issabel-admin-passwords'
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
    backup = backup_root / ('issabel-admin-passwords-' + hashlib.sha256(before).hexdigest() + '.original')
    if backup.exists() or backup.is_symlink():
        regular_file(backup)
        if backup.read_bytes() != before:
            raise ValueError('Original vendor backup differs; refusing overwrite')
    else:
        fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(before); stream.flush(); os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix='.mytel-cli-status-', dir=str(path.parent))
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
    parser.add_argument('--backup-root', type=Path, default=Path('/var/backups/mytellpbx/cli-status'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0: parser.error('root required')
    if args.check:
        _path, before, after, _metadata = plan(args.root)
        print('MyTellPBX CLI status: ' + ('would update' if before != after else 'unchanged'))
    else:
        print('MyTellPBX CLI status: ' + ('updated' if apply(args.root, args.backup_root) else 'unchanged'))


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError) as error:
        print('MyTellPBX CLI status repair refused: ' + str(error), file=sys.stderr)
        sys.exit(1)
