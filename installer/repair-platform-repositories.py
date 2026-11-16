#!/usr/bin/env python3
"""Retire exact vendor RPM duplicates in favor of the installed HTTPS catalog.

The existing nine-stream MyTellPBX catalog is hash-verified and never rewritten.
Only three captured public RPM files may become comment-only handoff files;
original bytes receive private backups. Unknown edits or repository-ID collisions
fail before any changes. Other repositories and signing policy remain unchanged.
RPM flags do not protect these handoffs from package upgrades: the installer must
revalidate after its package stages and before package commands on resume.
Python 3.6 compatible. Root-owned OS directories are trusted against concurrent
privileged directory replacement. No DNF, network, service or RPM commands.
"""
import argparse
from collections import namedtuple
import configparser
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile

VENDOR_HASHES = {
    'Issabel.repo': '6b7f618781b45c438bf02d3def4b7baa801957a476177ad946821ce40b7f2398',
    'Issabel5.repo': '4ee41bf20aa9b813ff7169e50dad983766500ca51e65c3c3dce352946039396a',
    'commercial-addons.repo': 'e3ed8e5d7b170bfb0f2e7a7db465f7160059ecf4ea971566f23bb14559c85223',
}
CANONICAL = 'mytelpbx-base.repo'
CANONICAL_SHA256 = '53795bb92a24a62cd60f0ff9de931fc94813f77e7b3bf8c9806aaf5dfc930733'
Plan = namedtuple('Plan', ['directory', 'files'])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def handoff(filename):
    return ('# MyTellPBX managed repository handoff v1.\n'
            '# Active telephony streams are defined in mytelpbx-base.repo.\n'
            '# Original vendor file: ' + filename + '\n'
            '# Original SHA256: ' + VENDOR_HASHES[filename] + '\n'
            '# Original bytes are retained in the root-private installer backup.\n'
            '# Revalidate after package installation; RPMs may replace this file.\n').encode('ascii')


def trusted_directory(path):
    path = Path(path).absolute()
    if path.resolve() != path or path.is_symlink():
        raise ValueError('Symlinked repository or backup directory refused')
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError('Repository or backup parent is not a directory')
    if os.name == 'posix' and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022):
        raise ValueError('Unsafe repository or backup directory permissions')
    return path


def regular_file(path):
    metadata = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 2 * 1024 * 1024:
        raise ValueError('Repository input is not a bounded regular file')
    if os.name == 'posix' and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022):
        raise ValueError('Unsafe repository input owner or permissions')
    return metadata


def identity(metadata):
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns,
            metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode))


def repository_ids(data):
    try:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(data.decode('utf-8'))
        return parser.sections()
    except (UnicodeError, configparser.Error) as error:
        raise ValueError('Repository configuration cannot be safely inventoried') from error


def plan(root, if_present=False):
    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError('Symlinked installation root refused')
    directory = trusted_directory(root / 'etc/yum.repos.d')
    files = []
    for path in sorted(directory.glob('*.repo')):
        metadata = regular_file(path)
        before = path.read_bytes()
        after = before
        if path.name in VENDOR_HASHES:
            if digest(before) == VENDOR_HASHES[path.name]:
                after = handoff(path.name)
            elif before != handoff(path.name):
                raise ValueError('Unknown vendor repository edits retained: ' + path.name)
        files.append((path, before, after, metadata))
    names = {path.name for path, _before, _after, _metadata in files}
    if CANONICAL not in names:
        raise ValueError('Reviewed canonical HTTPS catalog is missing')
    canonical = next(before for path, before, _after, _metadata in files if path.name == CANONICAL)
    if digest(canonical) != CANONICAL_SHA256 or len(repository_ids(canonical)) != 9:
        raise ValueError('Canonical HTTPS catalog differs; existing configuration retained')
    if not if_present and not set(VENDOR_HASHES).issubset(names):
        raise ValueError('Required vendor repository files are missing')
    found = set()
    for _path, _before, after, _metadata in files:
        for section in repository_ids(after):
            if section in found:
                raise ValueError('Unknown duplicate repository ID retained; repair refused')
            found.add(section)
    return Plan(directory, files)


def unchanged(change):
    path, before, _after, previous = change
    if identity(regular_file(path)) != identity(previous) or path.read_bytes() != before:
        raise ValueError('Repository changed after validation; no overwrite allowed')


def revalidate(planned):
    trusted_directory(planned.directory)
    if sorted(planned.directory.glob('*.repo')) != [change[0] for change in planned.files]:
        raise ValueError('Repository inventory changed after validation')
    for change in planned.files:
        unchanged(change)


def backup_path(directory, change):
    return directory / (change[0].name + '-' + digest(change[1]) + '.original')


def replace_change(change):
    path, before, after, previous = change
    unchanged(change)
    fd, temporary = tempfile.mkstemp(prefix='.mytell-platform-repo-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(after); output.flush(); os.fsync(output.fileno())
            os.chmod(temporary, stat.S_IMODE(previous.st_mode))
            if hasattr(os, 'fchown'):
                os.fchown(output.fileno(), previous.st_uid, previous.st_gid)
            if hasattr(os, 'listxattr'):
                for attribute in os.listxattr(str(path)):
                    os.setxattr(temporary, attribute, os.getxattr(str(path), attribute))
        unchanged(change)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_plan(planned, backup_root):
    revalidate(planned)
    changes = [change for change in planned.files if change[1] != change[2]]
    if not changes:
        return []
    backup_root = Path(backup_root).absolute()
    if backup_root.resolve() != backup_root or backup_root.is_symlink():
        raise ValueError('Symlinked backup directory refused')
    # Validate every pre-existing backup before creating any backup or changing
    # any repository. A conflict is never treated as permission to overwrite.
    for change in changes:
        backup = backup_path(backup_root, change)
        if backup.exists() or backup.is_symlink():
            metadata = regular_file(backup)
            if backup.read_bytes() != change[1] or (os.name == 'posix' and stat.S_IMODE(metadata.st_mode) != 0o600):
                raise ValueError('Existing original repository backup differs')
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    trusted_directory(backup_root)
    os.chmod(str(backup_root), 0o700)
    for change in changes:
        backup = backup_path(backup_root, change)
        if not backup.exists():
            fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as output:
                output.write(change[1]); output.flush(); os.fsync(output.fileno())
    revalidate(planned)
    for change in changes:
        replace_change(change)
    return [change[0] for change in changes]


def apply(root, backup_root, if_present=False):
    return apply_plan(plan(root, if_present=if_present), backup_root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--backup-root', type=Path, default=Path('/var/backups/mytellpbx/platform-repositories'))
    parser.add_argument('--if-present', action='store_true', help='allow absent vendor RPM files before their package stages')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    if getattr(os, 'geteuid', lambda: -1)() != 0:
        parser.error('root required')
    try:
        planned = plan(args.root, if_present=args.if_present)
        if args.check:
            print('MyTellPBX platform repositories: ' + str(sum(before != after for _path, before, after, _metadata in planned.files)) + ' known file(s) need repair')
        else:
            print('MyTellPBX platform repositories: ' + str(len(apply_plan(planned, args.backup_root))) + ' repaired')
        return 0
    except (OSError, ValueError) as error:
        print('MyTellPBX repository repair refused: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
