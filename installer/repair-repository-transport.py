#!/usr/bin/env python3
"""Select the three installed Remi repositories' documented HTTPS mirrors.

Only the active mirrorlist lines in remi, remi-safe and remi-modular change.
The vendor's disabled testing/debug repositories, IDs, PHP streams, signing
policy and keys remain byte-identical. Unknown source edits fail closed.
Python 3.6 compatible. Run only on a fresh installer-owned OS as root.
Root-owned OS directories are trusted; this is not a sandbox against another
privileged process concurrently replacing their directory components.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile

TARGETS = (
    ('remi.repo', 'remi', 'remi'),
    ('remi-safe.repo', 'remi-safe', 'safe'),
    ('remi-modular.repo', 'remi-modular', 'modular'),
)


def transform_repository(text, section, family):
    if (section, family) not in [(item[1], item[2]) for item in TARGETS]:
        raise ValueError('Unsupported repository identity')
    lines = text.splitlines(keepends=True)
    headers = [(index, line.rstrip('\r\n')) for index, line in enumerate(lines)
               if re.fullmatch(r'\[[^\]\r\n]+\]', line.rstrip('\r\n'))]
    matches = [index for index, label in headers if label == '[' + section + ']']
    if len(matches) != 1:
        raise ValueError('Missing or duplicate repository section: ' + section)
    begin = matches[0]
    end = next((index for index, _label in headers if index > begin), len(lines))
    plain = [line.rstrip('\r\n') for line in lines[begin + 1:end]]
    base = 'https://rpms.remirepo.net/enterprise/$releasever/' + family + '/$basearch/httpsmirror'
    old = 'mirrorlist=http://cdn.remirepo.net/enterprise/$releasever/' + family + '/$basearch/mirror'
    new = 'mirrorlist=' + base
    active = [line for line in plain if re.match(r'\s*(?:mirrorlist|baseurl)\s*=', line)]
    if plain.count('#' + new) != 1 or active not in ([old], [new]):
        raise ValueError('Unknown repository transport or vendor alternative: ' + section)
    if active == [new]:
        return text
    index = begin + 1 + plain.index(old)
    ending = lines[index][len(lines[index].rstrip('\r\n')):]
    lines[index] = new + ending
    return ''.join(lines)


def regular_file(path):
    path = Path(path)
    if path.resolve() != path.absolute():
        raise ValueError('Symlinked repository path refused: ' + str(path))
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError('Repository is not a regular file: ' + str(path))
    if os.name == 'posix' and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022):
        raise ValueError('Unsafe repository ownership or write permissions: ' + str(path))
    return metadata


def identity(metadata):
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns,
            metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode))


def plan(root, if_present=False):
    root = Path(root).absolute()
    paths = [root / 'etc/yum.repos.d' / filename for filename, _section, _family in TARGETS]
    present = [path.exists() or path.is_symlink() for path in paths]
    if if_present and not any(present):
        return []
    if not all(present):
        raise ValueError('Missing or partial installed Remi repository set')
    changes = []
    for filename, section, family in TARGETS:
        path = root / 'etc/yum.repos.d' / filename
        metadata = regular_file(path)
        before = path.read_bytes()
        after = transform_repository(before.decode('utf-8'), section, family).encode('utf-8')
        changes.append((path, before, after, metadata))
    return changes


def unchanged(path, before, previous):
    if identity(regular_file(path)) != identity(previous) or path.read_bytes() != before:
        raise ValueError('Repository changed after validation; refusing overwrite')


def write_change(change, backup_root):
    path, before, after, previous = change
    unchanged(path, before, previous)
    if before == after:
        return False
    backup_root = Path(backup_root).absolute()
    if backup_root.resolve() != backup_root or backup_root.is_symlink():
        raise ValueError('Symlinked backup directory refused')
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not backup_root.is_dir() or (os.name == 'posix' and backup_root.stat().st_uid != os.geteuid()):
        raise ValueError('Unsafe backup directory ownership')
    os.chmod(str(backup_root), 0o700)
    backup = backup_root / (path.name + '-' + hashlib.sha256(before).hexdigest() + '.original')
    if backup.exists() or backup.is_symlink():
        if backup.is_symlink() or not backup.is_file() or backup.read_bytes() != before:
            raise ValueError('Original repository backup mismatch')
    else:
        fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(before); stream.flush(); os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix='.mytel-repo-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(after); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temporary, stat.S_IMODE(previous.st_mode))
            if hasattr(os, 'fchown'):
                os.fchown(stream.fileno(), previous.st_uid, previous.st_gid)
        unchanged(path, before, previous)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return True


def apply(root, backup_root, if_present=False):
    changes = plan(root, if_present=if_present)  # Check all before any write.
    return [change[0] for change in changes if write_change(change, backup_root)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--backup-root', type=Path, default=Path('/var/backups/mytellpbx/repository-transport'))
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--if-present', action='store_true', help='skip only when all three vendor repository files are absent')
    args = parser.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0:
        parser.error('root required')
    if args.check:
        for path, before, after, _metadata in plan(args.root, if_present=args.if_present):
            print(('WOULD UPDATE ' if before != after else 'UNCHANGED ') + str(path))
    else:
        print('MyTellPBX Remi HTTPS transport: ' + ('updated' if apply(args.root, args.backup_root, if_present=args.if_present) else 'unchanged'))


if __name__ == '__main__': main()
