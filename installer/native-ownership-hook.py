#!/usr/bin/env python3
"""Restore the receipted recording component and exact supported native hook stub.

Python 3.6 standard library; no arguments or environment-selected paths. Native
PBX files, services and key bytes are never rewritten. The native engine hook
must propagate a nonzero exit, and its caller must subsequently run Desk doctor.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
STATE_BASE = Path('/etc')
STATE = STATE_BASE / 'myteldesk/installation.json'
DESK_BASE = Path('/opt')
DESK = DESK_BASE / 'myteldesk'
MODULE = Path('/var/www/html/admin/modules/myteldeskrecording')
PEM = Path('/etc/asterisk/keys/asterisk.pem')
STUB = Path('/var/lib/asterisk/bin/issabelpbx_engine_hook_mytel')
STUB_SHA256 = '13c35173fe08afb72b74d5ff56e44a450669fbca3fdabfa182262b9bfc5e7cb5'
FILE_HASHES = {
    'functions.inc.php': 'ece7dfca5972ee7810ad3e16b8eb48086d6be3efc02a527573c95b29f7d7da62',
    'module.xml': '2c57a67a213b5b6ca85179bd3b1c825069ea2fa189a7d740a1b84954606a83cd',
}


def validate_state(value):
    if (not isinstance(value, dict) or value.get('owner') != 'MytelDesk'
            or type(value.get('schema')) is not int or value['schema'] != 1
            or value.get('status') != 'ready' or 'pending_journal' in value):
        raise ValueError('Untrusted or incomplete Desk ownership receipt')
    version, tree = value.get('version'), value.get('tree')
    if (not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version)
            or not isinstance(tree, str) or not re.fullmatch('[0-9a-f]{40}', tree)
            or value.get('release') != str(DESK / 'releases' / (version + '-' + tree[:12]))):
        raise ValueError('Invalid installed Desk source identity')
    recording = value.get('recording_module')
    expected = {'schema': 1, 'name': 'myteldeskrecording', 'version': '1.0.0',
                'directory': str(MODULE), 'files': FILE_HASHES}
    if (not isinstance(recording, dict) or type(recording.get('schema')) is not int
            or recording != expected):
        raise ValueError('Unknown recording component receipt')
    owned = value.get('owned_hashes')
    if not isinstance(owned, dict) or any(owned.get(str(MODULE / name)) != digest
                                          for name, digest in FILE_HASHES.items()):
        raise ValueError('Recording ownership hashes differ')
    return value


def module_metadata(info, directory, uid, gid):
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    modes = (0o755, 0o775) if directory else (0o644, 0o664)
    if (not kind(info.st_mode) or (not directory and info.st_nlink != 1)
            or (info.st_uid, info.st_gid) not in ((0, 0), (uid, gid))
            or stat.S_IMODE(info.st_mode) not in modes):
        raise ValueError('Unexpected recording component metadata')
    return 0, 0, 0o755 if directory else 0o644


def pem_mode(info, uid, gid):
    mode = stat.S_IMODE(info.st_mode)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or mode not in (0o600, 0o620, 0o640, 0o644, 0o660, 0o664)):
        raise ValueError('Unexpected native PEM type or permissions')
    # Repeated native chmod g+w turns this owner's secured 0600 into 0620.
    # The root-owned branch still requires existing group read, rejecting 0620.
    if info.st_uid == uid and info.st_gid in (0, gid):
        return 0o600
    # Do not remove the native service's existing group access to a root key.
    # A root-only key or an unrelated owner/group is not ours to adopt.
    if info.st_uid == 0 and info.st_gid == gid and mode & 0o040:
        return 0o640
    raise ValueError('Unknown native PEM ownership or access')


def native_ids():
    import grp
    import pwd
    user = pwd.getpwnam('asterisk')
    group = grp.getgrnam('asterisk')
    if user.pw_uid <= 0 or user.pw_gid <= 0 or user.pw_gid != group.gr_gid:
        raise ValueError('Unexpected native Asterisk identity')
    return user.pw_uid, group.gr_gid


def canonical(path):
    if not path.is_absolute() or path.resolve() != path.absolute() or path.is_symlink():
        raise ValueError('Noncanonical or symlinked fixed path')


def trusted_directories(path, base):
    canonical(path)
    if path != base and base not in path.parents:
        raise ValueError('Unexpected trusted directory boundary')
    for candidate in [path] + list(path.parents):
        info = candidate.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Desk source or receipt directory is not root controlled')
        if candidate == base:
            return
    raise ValueError('Missing trusted directory boundary')


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def same_path(path, fd, expected=None):
    canonical(path)
    current = os.fstat(fd)
    if identity(path.lstat()) != identity(current) or (expected is not None
                                                      and identity(current) != identity(expected)):
        raise ValueError('Fixed path changed during ownership verification')
    return current


def open_fixed(stack, path, directory=False, parent_fd=None):
    canonical(path)
    before = path.lstat()
    if (directory and not stat.S_ISDIR(before.st_mode)) or (not directory and
            (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1)):
        raise ValueError('Unexpected fixed path type before open')
    # A regular-to-FIFO replacement between lstat and open must not hang the
    # native engine. Descriptor/path identity checks below still reject it.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_DIRECTORY if directory else 0)
    fd = os.open(str(path) if parent_fd is None else path.name, flags, dir_fd=parent_fd)
    stack.callback(os.close, fd)
    info = same_path(path, fd, before)
    if (directory and not stat.S_ISDIR(info.st_mode)) or (not directory and
            (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)):
        raise ValueError('Fixed path is not the expected single-link file or directory')
    return fd, info


def file_digest(fd, info):
    if info.st_size <= 0 or info.st_size > 1024 * 1024:
        raise ValueError('Unexpected fixed file size')
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while total <= info.st_size:
        block = os.read(fd, min(65536, info.st_size + 1 - total))
        if not block:
            break
        total += len(block)
        if total > info.st_size:
            raise ValueError('Fixed file grew beyond its verified size')
        digest.update(block)
    if total != info.st_size or identity(os.fstat(fd)) != identity(info):
        raise ValueError('Fixed file changed while hashing')
    return digest.hexdigest()


def repair():
    uid, gid = native_ids()
    changed = []
    with ExitStack() as stack:
        trusted_directories(STATE.parent, STATE_BASE)
        receipt_fd, receipt_info = open_fixed(stack, STATE)
        if (receipt_info.st_uid, receipt_info.st_gid, stat.S_IMODE(receipt_info.st_mode)) != (0, 0, 0o600):
            raise ValueError('Desk ownership receipt is not private and root owned')
        if receipt_info.st_size <= 0 or receipt_info.st_size > 4 * 1024 * 1024:
            raise ValueError('Unexpected Desk receipt size')
        with os.fdopen(os.dup(receipt_fd), 'r', encoding='utf-8') as source:
            value = validate_state(json.load(source))
        release = Path(value['release'])
        trusted_directories(release, DESK_BASE)
        current = DESK / 'current'
        link = current.lstat()
        if (not stat.S_ISLNK(link.st_mode) or link.st_uid != 0 or link.st_gid != 0
                or current.resolve() != release):
            raise ValueError('Installed Desk source link differs from its trusted receipt')
        directory_fd, directory_info = open_fixed(stack, MODULE, directory=True)
        targets = [(MODULE, directory_fd, directory_info,
                    module_metadata(directory_info, True, uid, gid), None)]
        if set(os.listdir(directory_fd)) != set(FILE_HASHES):
            raise ValueError('Unexpected recording component entries')
        for name, expected in sorted(FILE_HASHES.items()):
            path = MODULE / name
            fd, info = open_fixed(stack, path, parent_fd=directory_fd)
            metadata = module_metadata(info, False, uid, gid)
            if file_digest(fd, info) != expected:
                raise ValueError('Recording component bytes differ from the trusted source')
            targets.append((path, fd, info, metadata, expected))
        # The vendor recursively chowns ASTVARLIBDIR/AMPBIN, which includes its
        # supported stub. Seal only our exact known stub again before returning.
        stub_fd, stub_info = open_fixed(stack, STUB)
        stub_metadata = module_metadata(stub_info, False, uid, gid)
        if file_digest(stub_fd, stub_info) != STUB_SHA256:
            raise ValueError('Unknown supported native ownership stub')
        targets.append((STUB, stub_fd, stub_info, stub_metadata, STUB_SHA256))
        pem = None
        # Missing is supported; dangling links and all other unexpected types fail.
        if PEM.exists() or PEM.is_symlink():
            fd, info = open_fixed(stack, PEM)
            mode = pem_mode(info, uid, gid)
            pem = (fd, info, mode, file_digest(fd, info))
        # Validate every target, including the key, before changing any metadata.
        same_path(STATE, receipt_fd, receipt_info)
        for path, fd, info, metadata, digest in targets:
            same_path(path, fd, info)
        if pem:
            same_path(PEM, pem[0], pem[1])
        for path, fd, info, metadata, digest in targets:
            same_path(path, fd, info)
            owner, group, mode = metadata
            if (info.st_uid, info.st_gid) != (owner, group):
                os.fchown(fd, owner, group)
            if stat.S_IMODE(info.st_mode) != mode:
                os.fchmod(fd, mode)
            after = same_path(path, fd)
            if (after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode)) != metadata:
                raise ValueError('Recording metadata repair did not verify')
            if digest is not None and file_digest(fd, after) != digest:
                raise ValueError('Recording bytes changed during metadata repair')
            if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != metadata:
                changed.append(str(path))
        if pem:
            fd, info, mode, digest = pem
            same_path(PEM, fd, info)
            if stat.S_IMODE(info.st_mode) != mode:
                os.fchmod(fd, mode)
                changed.append(str(PEM))
            after = same_path(PEM, fd)
            if ((after.st_dev, after.st_ino, after.st_uid, after.st_gid) !=
                    (info.st_dev, info.st_ino, info.st_uid, info.st_gid)
                    or stat.S_IMODE(after.st_mode) != mode or file_digest(fd, after) != digest):
                raise ValueError('Native PEM identity or bytes did not verify')
        same_path(STATE, receipt_fd, receipt_info)
    return {'status': 'ok', 'changed': changed, 'pem': 'restricted' if pem else 'absent'}


def runtime_guard():
    if (os.name != 'posix' or os.geteuid() != 0 or not hasattr(os, 'O_NOFOLLOW')
            or not hasattr(os, 'O_DIRECTORY') or not hasattr(os, 'O_NONBLOCK')
            or not hasattr(os, 'fchown')):
        raise ValueError('Native ownership hook requires POSIX root')


def main(argv=None):
    if list(sys.argv[1:] if argv is None else argv):
        print('Usage: native-ownership-hook.py (no arguments)', file=sys.stderr)
        return 2
    try:
        runtime_guard()
        result = repair()
    except (OSError, ValueError, KeyError, TypeError):
        print('MytelPBX native ownership hook failed; independent verification required.', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
