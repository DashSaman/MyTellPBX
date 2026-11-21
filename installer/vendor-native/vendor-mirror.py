#!/usr/bin/env python3
"""Install DNF metalinks for the reviewed Issabel metadata snapshot on Rocky 8."""

import argparse
import configparser
import hashlib
import io
import os
from pathlib import Path
import stat
import tempfile
import xml.etree.ElementTree as ET


# Exact repomd bytes from HTTPS downloads on 2026-11-18. The live HTTP mirror
# matched those independently retained bytes; it supplies data, never the pins.
SNAPSHOTS = {
    'issabel-base': ('4/base/x86_64', 'ee375feeec00a59a52748e296b06d72a8789283c88a03b46dd18f06529fa3fb1'),
    'issabel-updates': ('4/updates/x86_64', '9dd19b3c6e91813410cbc57111f5f9e94a0e7be247bbb2d2673e3eacd6a0456f'),
    'issabel-cinco': ('5/base/x86_64', '78c0143a03d03fb5d9a15b250b13f0f79bc5c0974ebb2835ba5f80949fbf7063'),
    'issabel-cinco-noarch': ('5/base/noarch', '29351fcf8dcafc9267b39ccba9dd0e5b16c594b9d721561c1aa76b9e9d4d6f27'),
    'issabel-cinco-updates': ('5/updates/x86_64', '888ce70328aee60e2887d33e6373eefadb0bebc7c256ebb5ff4d724245146589'),
    'issabel-cinco-updates-noarch': ('5/updates/noarch', '3a04470e029b22f765be51971d50032f359ff2a85bf006cc9c9238ce005da024'),
    'issabel-cinco-extras': ('5/extras/x86_64', 'cf5933d06109aae8b4f79cb8e0761dbc865f6708edb3a54155b00d782d7bc35c'),
    'issabel-cinco-extras-noarch': ('5/extras/noarch', 'c851c6bd03139326501dfe2fd3caa4145d8c0af073e18244920f40fb08aafefa'),
    'commercial-addons': ('5/commercial_addons/x86_64', 'e31de3c1e1a5b0ce4572f5f68edd4661669d1d230e113a4ad2327c55a956e430'),
}
FILES = {
    'Issabel.repo': ('issabel-base', 'issabel-updates'),
    'Issabel5.repo': tuple(name for name in SNAPSHOTS if name.startswith('issabel-cinco')),
    'commercial-addons.repo': ('commercial-addons',),
}
# The second key signs php-magpierss in issabel-updates. Both public keys
# were obtained over verified publisher HTTPS and checked on native Rocky.
KEYS = {
    'issabel.asc': 'f7eb76b75127d29c5e5aa33ca2b7504680592e0882af7aeea185eeffcd8b4a0d',
    'legacy-elastix.asc': '71de56885e8f5fb84b02bc31a5fa498d7f2f26df4b5ccc9debff536a0f3b67ba',
}


def metalink(repo):
    path, checksum = SNAPSHOTS[repo]
    root = ET.Element('metalink', xmlns='http://www.metalinker.org/', version='3.0')
    target = ET.SubElement(ET.SubElement(root, 'files'), 'file', name='repomd.xml')
    ET.SubElement(ET.SubElement(target, 'verification'), 'hash', type='sha256').text = checksum
    resources = ET.SubElement(target, 'resources', maxconnections='1')
    for protocol, host, priority in [('https', 'repo.us.issabel.org', '100'), ('http', 'repo.issabel.org', '90')]:
        url = ET.SubElement(resources, 'url', protocol=protocol, type=protocol, preference=priority)
        url.text = '{}://{}/issabel/{}/repodata/repomd.xml'.format(protocol, host, path)
    return ET.tostring(root, encoding='utf-8') + b'\n'


def checked_directory(path, create_mode=None):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('Repository configuration directory must have a canonical absolute path')
    for parent in list(reversed(path.parents)) + [path]:
        if create_mode is not None and not parent.exists():
            parent.mkdir(mode=create_mode)
            # The native installer has umask 077. Its published key/metadata
            # path must also work for unprivileged read-only package queries.
            parent.chmod(create_mode)
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('Unsafe repository configuration directory')
        if os.name == 'posix':
            # Root-owned sticky /tmp and /var/tmp can contain our private stage.
            shared_tmp = parent != path and info.st_uid == 0 and info.st_mode & stat.S_ISVTX
            if info.st_uid not in (0, os.geteuid()) or (info.st_mode & 0o022 and not shared_tmp):
                raise ValueError('Untrusted repository configuration directory')
    return path


def atomic_write(path, data, mode):
    fd, name = tempfile.mkstemp(prefix='.vendor-snapshot-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
            if hasattr(os, 'fchmod'):
                os.fchmod(output.fileno(), mode)
        os.replace(name, str(path))
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Unsafe repository configuration file: ' + path.name)
    if os.name == 'posix' and (info.st_uid != os.geteuid() or info.st_mode & 0o022):
        raise ValueError('Untrusted repository configuration file: ' + path.name)
    return stat.S_IMODE(info.st_mode)


def configure(repo_dir, state_dir):
    repo_dir = checked_directory(repo_dir)
    state_dir = Path(state_dir)
    state_dir = checked_directory(state_dir, 0o700 if repo_dir in state_dir.parents else 0o755)
    material = {}
    for name, sha256 in KEYS.items():
        data = (Path(__file__).with_name('keys') / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != sha256:
            raise ValueError('Reviewed RPM public key differs: ' + name)
        material[state_dir / name] = data
    configs = {}
    for filename, repos in FILES.items():
        path = repo_dir / filename
        mode = regular(path)
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(path.read_text(encoding='utf-8'))
        enabled = {name for name in parser.sections() if parser[name].getboolean('enabled', fallback=True)}
        if enabled != set(repos) or parser.defaults():
            raise ValueError('Unexpected enabled native repository sections: ' + filename)
        for repo in repos:
            section = parser[repo]
            link = state_dir / (repo + '.metalink')
            material[link] = metalink(repo)
            for key in ('baseurl', 'mirrorlist'):
                section.pop(key, None)
            section['metalink'] = link.as_uri()
            section['gpgcheck'] = '1'
            section['sslverify'] = '1'
            section['skip_if_unavailable'] = '0'
            keys = ['issabel.asc', 'legacy-elastix.asc'] if repo == 'issabel-updates' else ['issabel.asc']
            section['gpgkey'] = ' '.join((state_dir / key).as_uri() for key in keys)
        output = io.StringIO()
        parser.write(output, space_around_delimiters=False)
        configs[path] = (output.getvalue().encode('utf-8'), mode)
    for path, data in material.items():
        if path.exists() or path.is_symlink():
            regular(path)
            if path.read_bytes() != data:
                raise ValueError('Existing pinned repository material differs: ' + path.name)
    for path, data in material.items():
        if not path.exists():
            atomic_write(path, data, 0o644)
    for path, (data, mode) in configs.items():
        if path.read_bytes() != data:
            atomic_write(path, data, mode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-dir', required=True, type=Path)
    parser.add_argument('--state-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        configure(args.repo_dir, args.state_dir)
    except (OSError, ValueError, configparser.Error) as error:
        parser.exit(1, 'MytelPBX repository snapshot: {}\n'.format(error))
