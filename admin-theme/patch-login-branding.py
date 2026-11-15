#!/usr/bin/env python3
"""Brand the known framework login banner without executing it.

Only six stock presentation statements change. Package/configuration identities,
legal notices, network discovery, the login profile and service logic stay intact.
Python 3.6 compatible; unrecognized or partly changed banners are refused.
The installer runs as root in trusted root-owned OS directories. The writer's
path checks are not a sandbox against concurrent privileged directory replacement.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import tempfile

REPLACEMENTS = {
    r'echo -e "  O \e[96m@ \e[91m@    \e[0mIssabel is a product meant to be configured through a web browser."':
        r'echo -e "\e[1;36mMyTellPBX\e[0m is a product meant to be configured through a web browser."',
    r'echo -e "  \e[31;1m@ \e[35m@ \e[39mO    \e[0mAny changes made from within the command line may corrupt the system"':
        r'echo -e "Any changes made from within the command line may corrupt the system"',
    r'echo -e "  \e[33;1m@ \e[39mO O    \e[0mconfiguration and produce unexpected behavior; in addition, changes"':
        r'echo -e "configuration and produce unexpected behavior; in addition, changes"',
    r'echo -e "\e[1m    O      \e[0mmade to system files through here may be lost when doing an update."':
        r'echo -e "made to system files through here may be lost when doing an update."',
    'echo "To access your Issabel System, using a separate workstation (PC/MAC/Linux)"':
        'echo "To access your MyTellPBX System, using a separate workstation (PC/MAC/Linux)"',
    r'echo -e "\e[1mYour opportunity to give back: \e[4mhttp://www.patreon.com/issabel\e[0m"':
        r'echo -e "\e[1mMyTellPBX support: \e[4mhttps://mytel.one\e[0m"',
}


def transform_motd(text):
    lines = text.splitlines(keepends=True)
    plain = [line.rstrip('\r\n') for line in lines]
    old_counts = [plain.count(line) for line in REPLACEMENTS]
    new_counts = [plain.count(line) for line in REPLACEMENTS.values()]
    if all(count == 1 for count in new_counts) and not any(old_counts):
        return text
    if not all(count == 1 for count in old_counts) or any(new_counts):
        raise ValueError('Unknown, partial or duplicate login banner; refusing to overwrite owner edits')
    return ''.join(REPLACEMENTS.get(line.rstrip('\r\n'), line.rstrip('\r\n'))
                   + line[len(line.rstrip('\r\n')):] for line in lines)


def regular_file(root, relative):
    path = root / relative
    if path.is_symlink() or not path.is_file() or path.resolve() != path.absolute():
        raise ValueError('Missing or symlinked branding input: ' + str(path))
    return path


def plan(root):
    root = Path(root).resolve()
    profile = regular_file(root, 'etc/profile.d/login-info.sh')
    if profile.read_bytes().decode('utf-8').splitlines().count('/usr/local/sbin/motd.sh') != 1:
        raise ValueError('Login profile no longer invokes the known banner; no files changed')
    path = regular_file(root, 'usr/local/sbin/motd.sh')
    before = path.read_bytes()
    after = transform_motd(before.decode('utf-8')).encode('utf-8')
    return [(path, before, after)]


def write_change(change, backup_root):
    path, before, after = change
    if before == after:
        return False
    if path.is_symlink() or path.resolve() != path.absolute() or path.read_bytes() != before:
        raise ValueError('Login banner changed after validation; no files changed')
    previous = path.stat()
    backup_root = Path(backup_root)
    if backup_root.is_symlink():
        raise ValueError('Backup directory must not be a symlink')
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(str(backup_root), 0o700)
    backup = backup_root / ('motd.sh-' + hashlib.sha256(before).hexdigest() + '.original')
    if backup.exists() or backup.is_symlink():
        if backup.is_symlink() or not backup.is_file() or backup.read_bytes() != before:
            raise ValueError('Existing branding backup does not match the original')
    else:
        fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(before)
    fd, temporary = tempfile.mkstemp(prefix='.mytel-login-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
            os.chmod(temporary, stat.S_IMODE(previous.st_mode))
            if hasattr(os, 'fchown'):
                os.fchown(stream.fileno(), previous.st_uid, previous.st_gid)
        if path.is_symlink() or path.read_bytes() != before:
            raise ValueError('Login banner changed while preparing replacement')
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def apply(root, backup_root):
    changes = plan(root)  # Every source/anchor is validated before the first write.
    return [path for path, before, after in changes
            if write_change((path, before, after), backup_root)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--backup-root', type=Path, default=Path('/var/backups/mytellpbx/login-branding'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        for path, before, after in plan(args.root):
            print(('WOULD UPDATE ' if before != after else 'UNCHANGED ') + str(path))
    else:
        changed = apply(args.root, args.backup_root)
        print('MyTellPBX login branding: ' + ('updated' if changed else 'unchanged'))


if __name__ == '__main__':
    main()
