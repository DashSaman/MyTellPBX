#!/usr/bin/env python3
"""Brand native dialogs, guard early absent config and replace optional joke UX.

The password tool receives display substitutions only. The language tool also
guards its initial config load only when the file is genuinely absent before
core installation; native selection, auth and later password flow stay intact.
The optional completion helper is replaced only at its known source hash. Source
revisions and the narrow startup guard are recorded in provenance.json. No
passwords are accepted, read or passed. Originals are backed up before replacement.
Python 3.6 compatible.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import tempfile

TOOLS = {
    'completion': ('issabel-patreon',
                   'aa865928497e0c32f42a73e2e15b73cd0be201ca4157df07098d695fe7718af9', ()),
    'language': ('issabel-change-language',
                 'c92b4c14ea2d37c1728a08da4741839b111e65f32ce8fdf897ed3b03777b13b6', (
        (b'--backtitle "Issabel"', b'--backtitle "MytelPBX / Mytel.one"', 1),
        (br'\nIssabel"', br'\nMytelPBX\nMytel.one"', 1),
        (b'        7 11\n', b'        8 15\n', 1),
        (b'source /etc/issabel.conf\n',
         b'if [ -e /etc/issabel.conf ] || [ -L /etc/issabel.conf ]; then\n'
         b'    source /etc/issabel.conf\nfi\n', 1),
    )),
    'passwords': ('issabel-admin-passwords',
                  'aa1a9bc962d5f34c57483d802b7f5e1e010133d2bf3245dc07b644387d9ef410', (
        (b"define('BACKTITLE', 'Issabel password configuration');",
         b"define('BACKTITLE', 'MytelPBX password configuration - Mytel.one');", 1),
        (br"\nIssabel',7,11", br"\nMytelPBX\nMytel.one',8,15", 2),
        (b'The Issabel system uses', b'The MytelPBX system uses', 1),
        (b'Several Issabel components', b'Several MytelPBX components', 1),
        (b'be used for: Issabel Web Login and IssabelPBX.',
         b'be used for: MytelPBX Web Login and PBX settings.', 1),
        (b"your new password for IssabelPBX 'admin':",
         b"your new password for MytelPBX 'admin':", 2),
        (b"'IssabelPBX database password' =>", b"'MytelPBX database password' =>", 1),
        (b"'IssabelPBX admin password' =>", b"'MytelPBX PBX admin password' =>", 1),
        (b"'Issabel admin password' =>", b"'MytelPBX web admin password' =>", 1),
        (b'dialog_infobox(\'Status\',"Found Issabel CallCenter database.',
         b'dialog_infobox(\'Status\',"Found MytelPBX CallCenter database.', 1),
        (b'Installing IssabelPBX, please wait...', b'Installing MytelPBX, please wait...', 1),
    )),
}

COMPLETION_HELPER = b'''#!/bin/bash
# MytelPBX optional completion display. Native core/password logic is unchanged.
exec dialog --stdout --backtitle "MytelPBX / Mytel.one" --title "Native setup complete" \\
    --sleep 3 --infobox "Native PBX core/password wizard completed.\\n\\nMytel add-ons will run NEXT.\\nPlease wait for their final result." 9 66
'''


def transform(tool, source):
    _filename, expected, replacements = TOOLS[tool]
    checksum = hashlib.sha256(source).hexdigest()
    if tool == 'completion':
        if source == COMPLETION_HELPER:
            return source
        if checksum != expected:
            raise ValueError('Unknown optional native completion helper')
        return COMPLETION_HELPER
    # Reversing only declared labels/startup guard makes repeat runs idempotent;
    # the resulting full source must still match the pinned original hash.
    if checksum != expected:
        original = source
        for before, after, count in reversed(replacements):
            if original.count(after) != count:
                raise ValueError('Unknown native dialog source: ' + tool)
            original = original.replace(after, before)
        if hashlib.sha256(original).hexdigest() != expected:
            raise ValueError('Unknown native dialog source: ' + tool)
        return source
    result = source
    for before, after, count in replacements:
        if result.count(before) != count:
            raise ValueError('Native source boundary changed: ' + tool)
        result = result.replace(before, after)
    return result


def regular(path):
    info = path.lstat()
    if (path.resolve() != path.absolute() or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1 or info.st_mode & 0o022
            or (os.name == 'posix' and info.st_uid != os.geteuid())):
        raise ValueError('Unsafe native executable or backup path')
    return info


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def apply(tool, root, backup_root):
    path = root.absolute() / 'usr/bin' / TOOLS[tool][0]
    previous = regular(path)
    before = path.read_bytes()
    after = transform(tool, before)
    if before == after:
        return False
    backup_root = backup_root.absolute()
    if backup_root.resolve() != backup_root:
        raise ValueError('Linked native backup directory refused')
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (not backup_root.is_dir() or backup_root.stat().st_mode & 0o077
            or (os.name == 'posix' and backup_root.stat().st_uid != os.geteuid())):
        raise ValueError('Unsafe native backup directory')
    backup = backup_root / (path.name + '-' + hashlib.sha256(before).hexdigest() + '.original')
    if backup.exists() or backup.is_symlink():
        regular(backup)
        if backup.read_bytes() != before:
            raise ValueError('Native executable backup differs')
    else:
        fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(before)
            stream.flush()
            os.fsync(stream.fileno())
    fd, name = tempfile.mkstemp(prefix='.mytel-native-display-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
            if hasattr(os, 'fchmod'):
                os.fchmod(stream.fileno(), stat.S_IMODE(previous.st_mode))
            else:
                os.chmod(name, stat.S_IMODE(previous.st_mode))
            if hasattr(os, 'fchown'):
                os.fchown(stream.fileno(), previous.st_uid, previous.st_gid)
        if identity(regular(path)) != identity(previous) or path.read_bytes() != before:
            raise ValueError('Native executable changed during preparation')
        os.replace(name, str(path))
    finally:
        if os.path.lexists(name):
            os.unlink(name)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool', choices=sorted(TOOLS), required=True)
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--backup-root', type=Path,
                        default=Path('/var/backups/mytelpbx/native-display'))
    args = parser.parse_args()
    if os.name != 'posix' or os.geteuid() != 0:
        parser.error('Root on the fresh installation target is required')
    changed = apply(args.tool, args.root, args.backup_root)
    print('MytelPBX native dialog preparation: ' + ('updated' if changed else 'unchanged'))


if __name__ == '__main__':
    main()
