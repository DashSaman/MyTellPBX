#!/usr/bin/env python3
"""Verify an immutable ISO depot. Python3.6+, no network or package actions.

The manifest digest comes from the reviewed ISO first-boot launcher. All media
bytes are public release assets. Path checks are for trusted root-owned media,
not a sandbox against concurrent privileged directory replacement.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

MAX_FILES = 100000
MAX_BYTES = 64 * 1024 ** 3
FIELDS = {'schema', 'owner', 'platform', 'files', 'bootstrap', 'bundle', 'desk',
          'node', 'wheels', 'geoip', 'repositories'}


def relative(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.+/-]+', value)
            or value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('Unsafe media relative path')
    return PurePosixPath(value).as_posix()


def trusted(path, uid, directory=False):
    info = path.lstat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError('Media links and special files are refused')
    if os.name == 'posix' and (info.st_uid != uid or info.st_mode & 0o022):
        raise ValueError('Media must be owned by root and not group/world writable')
    return info


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns if os.name == 'posix' else None)


def verified(path, record, uid):
    before = trusted(path, uid)
    if before.st_size != record['bytes']: raise ValueError('Media file size mismatch')
    checksum = hashlib.sha256()
    fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before): raise ValueError('Media input changed before read')
        for block in iter(lambda: stream.read(1024 * 1024), b''): checksum.update(block)
        if identity(os.fstat(stream.fileno())) != identity(before): raise ValueError('Media input changed during read')
    if identity(path.lstat()) != identity(before) or checksum.hexdigest() != record['sha256']:
        raise ValueError('Media checksum or identity changed')
    return path


class Media:
    def __init__(self, root, manifest, uid, manifest_sha256):
        self.root, self.manifest, self.uid = root, manifest, uid
        self.manifest_sha256 = manifest_sha256

    def asset(self, name):
        value = self.manifest[name]
        if not isinstance(value, str): raise ValueError('Expected one media asset')
        return verified(self.root / value, self.manifest['files'][value], self.uid)

    def copy(self, name, destination, expected):
        source = self.asset(name)
        if self.manifest['files'][self.manifest[name]]['sha256'] != expected:
            raise ValueError('Media asset differs from the product release pin')
        destination = Path(destination)
        if destination.is_symlink(): raise ValueError('Media copy destination is a symlink')
        shutil.copyfile(str(source), str(destination))
        if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
            raise ValueError('Media changed while copying')

    def repo_text(self):
        result = []
        for repo in self.manifest['repositories']:
            result.extend(['[' + repo['id'] + ']', 'name=MytelPBX verified offline media',
                           'baseurl=' + (self.root / repo['path']).as_uri(), 'enabled=1',
                           'gpgcheck=1', 'repo_gpgcheck=0',
                           'gpgkey=' + (self.root / repo['gpgkey']).as_uri(),
                           'skip_if_unavailable=0', ''])
        return '\n'.join(result)


def load(root, manifest_sha256, bundle_sha256=None, expected_uid=0):
    root = Path(root)
    if (not root.is_absolute() or root.resolve() != root.absolute()
            or not re.fullmatch(r'[0-9a-f]{64}', str(manifest_sha256))):
        raise ValueError('Canonical media root and explicit manifest checksum required')
    trusted(root, expected_uid, True)
    path = root / 'manifest.json'; info = trusted(path, expected_uid)
    if not 0 < info.st_size <= 32 * 1024 * 1024: raise ValueError('Media manifest size invalid')
    raw = path.read_bytes()
    if identity(path.lstat()) != identity(info) or hashlib.sha256(raw).hexdigest() != manifest_sha256:
        raise ValueError('Media manifest checksum or identity mismatch')
    value = json.loads(raw.decode('utf-8'))
    if (not isinstance(value, dict) or set(value) != FIELDS or type(value['schema']) is not int
            or value['schema'] != 1 or value['owner'] != 'MyTellPBX'
            or value['platform'] != 'rocky8.10-x86_64'):
        raise ValueError('Unknown offline media profile')
    files = value['files']
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES: raise ValueError('Invalid media inventory')
    total = 0
    for name, record in files.items():
        relative(name)
        if (name == 'manifest.json' or not isinstance(record, dict) or set(record) != {'sha256', 'bytes'}
                or type(record['bytes']) is not int or not 0 < record['bytes'] <= MAX_BYTES
                or not re.fullmatch(r'[0-9a-f]{64}', str(record['sha256']))):
            raise ValueError('Invalid media file record')
        total += record['bytes']
    if total > MAX_BYTES: raise ValueError('Media byte limit exceeded')
    paths = [value[k] for k in ('bootstrap', 'bundle', 'desk', 'node')]
    if not isinstance(value['wheels'], list) or not value['wheels']: raise ValueError('Missing media wheels')
    paths += value['wheels']
    geo = value['geoip']
    if (not isinstance(geo, dict) or set(geo) != {'path', 'month'}
            or not re.fullmatch(r'20[0-9]{2}-(?:0[1-9]|1[0-2])', str(geo['month']))):
        raise ValueError('Invalid media GeoIP source')
    paths.append(geo['path'])
    if any(relative(p) not in files for p in paths) or len(set(paths)) != len(paths):
        raise ValueError('Missing or duplicated media asset')
    repos = value['repositories']; ids = set()
    if not isinstance(repos, list) or not repos: raise ValueError('Missing local package repositories')
    for repo in repos:
        if (not isinstance(repo, dict) or set(repo) != {'id', 'path', 'gpgkey'}
                or not re.fullmatch(r'[A-Za-z0-9_-]+', str(repo['id'])) or repo['id'] in ids):
            raise ValueError('Invalid or duplicate local repository')
        ids.add(repo['id']); directory = relative(repo['path']); key = relative(repo['gpgkey'])
        if directory + '/repodata/repomd.xml' not in files or key not in files:
            raise ValueError('Local repository metadata or signing key missing')
    actual = set()
    for parent, directories, names in os.walk(str(root), followlinks=False):
        for name in directories: trusted(Path(parent) / name, expected_uid, True)
        for name in names:
            file = Path(parent) / name; trusted(file, expected_uid)
            actual.add(file.relative_to(root).as_posix())
    if actual != set(files) | {'manifest.json'}: raise ValueError('Unlisted or missing media file')
    for name, record in files.items(): verified(root / name, record, expected_uid)
    if bundle_sha256 is not None and files[value['bundle']]['sha256'] != bundle_sha256:
        raise ValueError('Offline PBX bundle differs from bootstrap pin')
    return Media(root, value, expected_uid, manifest_sha256)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--manifest-sha256', required=True)
    p.add_argument('--bundle-sha256')
    p.add_argument('--plan', action='store_true')
    p.add_argument('--repos', action='store_true')
    args = p.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0: p.error('Linux root required')
    media = load(args.root, args.manifest_sha256, args.bundle_sha256)
    if args.repos: print(media.repo_text())
    else:
        print(json.dumps(dict(schema=1, root=str(media.root), bundle=str(media.asset('bundle')),
                             desk=str(media.asset('desk')), repositories=[x['id'] for x in media.manifest['repositories']],
                             files=len(media.manifest['files']), manifest_sha256=args.manifest_sha256)))


if __name__ == '__main__': main()
