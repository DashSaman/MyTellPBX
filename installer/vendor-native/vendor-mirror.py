#!/usr/bin/env python3
"""Prepare the signed MytelPBX DNF repository from its checksum-pinned GitHub release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

RELEASE = 'https://github.com/DashSaman/MyTellPBX/releases/download/v7.7.0-r8/'
ASSET = 'mytelpbx-vendor-el8-x86_64.tar.gz'
FILES = ('Issabel.repo', 'Issabel5.repo', 'commercial-addons.repo')
PROJECT_KEY = 'mytelpbx-rpm-signing.asc'
PROJECT_RPM = 'Packages/dahdi-firmware-2.11.1-2.mytel.el8.noarch.rpm'
XTABLES_RPM = 'Packages/xtables-addons-3.18-1dkms.mytel.el8.x86_64.rpm'
GEOIP_RPM = 'Packages/issabel-geoip-1.6.12-3.mytel.el8.x86_64.rpm'
PROJECT_FILTER = 'asterisk20,asterisk20-*,dahdi-firmware,xtables-addons,issabel-geoip'
ASTERISK_BUILD = '-20.12.0-2.mytel.el8.x86_64.rpm'
ASTERISK_PARTS = ('', '-core', '-configs', '-dahdi', '-doc', '-odbc', '-voicemail', '-resample', '-curl',
                 '-devel', '-addons', '-addons-core', '-addons-bluetooth', '-addons-ooh323', '-addons-mysql')
ESSENTIAL = {PROJECT_RPM, XTABLES_RPM, GEOIP_RPM, 'Packages/asterisk-pr-sounds-1.1-0.noarch.rpm',
             'Packages/asterisk-sounds-en-gsm-1.5-1.el7.centos.noarch.rpm', 'Packages/issabel-packetbl-1.0-3.x86_64.rpm',
             'Packages/issabel-framework-5.0.0-6.noarch.rpm', 'Packages/issabel-pbx-5.0.0-4.noarch.rpm',
             'Packages/issabelPBX-2.12.0-5.noarch.rpm', 'Packages/issabel-firstboot-5.0.0-2.noarch.rpm',
             'Packages/issabel-config_helpers-5.0.0-1.noarch.rpm'}
ESSENTIAL.update('Packages/asterisk20' + part + ASTERISK_BUILD for part in ASTERISK_PARTS)


# The second key signs php-magpierss in issabel-updates. Both public keys
# were obtained over verified publisher HTTPS and checked on native Rocky.
KEYS = {
    'issabel.asc': 'f7eb76b75127d29c5e5aa33ca2b7504680592e0882af7aeea185eeffcd8b4a0d',
    PROJECT_KEY: '0f72ccbc23227524baf1990fa868b429eedf1e6669cb093c9521f27d07c98ca2',
    'legacy-elastix.asc': '71de56885e8f5fb84b02bc31a5fa498d7f2f26df4b5ccc9debff536a0f3b67ba',
}


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


def sha256(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()


def release_pin():
    pin = json.loads(Path(__file__).with_name('vendor-release.json').read_text(encoding='utf-8'))
    if (not re.fullmatch('[0-9a-f]{64}', pin['sha256']) or
            not 0 < pin['bytes'] <= 512 * 1024 * 1024 or not 0 < pin['packages'] < 1000):
        raise ValueError('Invalid vendor package release pin')
    return pin


def fetch(workdir, pin):
    archive = workdir / ASSET
    if not archive.exists():
        # Workdir is private and shared only between the two phases of this run.
        progress = '--progress-bar' if sys.stderr.isatty() else '--silent'
        print('  Downloading MytelPBX packages from GitHub ({:.1f} MiB)...'.format(pin['bytes'] / 1048576), flush=True)
        part = workdir / (ASSET + '.part')
        if part.exists() or part.is_symlink():
            regular(part)
        else:
            part.touch(mode=0o600, exist_ok=False)
        log = workdir / 'github-package-transfer.log'
        if log.exists() or log.is_symlink():
            regular(log)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(str(log), flags, 0o600), 'a', encoding='ascii') as diagnostic:
            for attempt in range(1, 4):
                command = ['curl', '--disable', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
                           progress, '--connect-timeout', '20', '--speed-limit', '1024', '--speed-time', '90',
                           '--max-time', '1800', '--max-filesize', str(pin['bytes']), '--continue-at', '-',
                           '--write-out', '%{http_code}', '--output', str(part), RELEASE + ASSET]
                result = subprocess.run(command, stdout=subprocess.PIPE)
                status = result.stdout.strip()
                http = status.decode('ascii') if re.fullmatch(rb'[0-9]{3}', status) else 'unknown'
                diagnostic.write('attempt={} curl={} http={} bytes={}\n'.format(
                    attempt, result.returncode, http, part.stat().st_size))
                diagnostic.flush()
                if result.returncode == 0:
                    break
                if result.returncode == 33:  # Server does not accept a Range request.
                    part.write_bytes(b'')
                if attempt < 3:
                    print('    Retrying package download...', flush=True)
            else:
                raise ValueError('GitHub package download failed')
        candidate = part
    else:
        candidate = archive
    regular(candidate)
    with candidate.open('rb') as stream:
        if candidate.stat().st_size != pin['bytes'] or sha256(stream) != pin['sha256']:
            raise ValueError('Downloaded MytelPBX packages do not match the release')
    if candidate != archive:
        os.replace(str(candidate), str(archive))
    return archive


def unpack(archive, state_dir, pin, metadata_only=False):
    # A second run may reuse a persistent snapshot. Check its contents against
    # the authenticated archive before installing repository definitions.
    target = state_dir / 'repository'
    exists = target.exists() or target.is_symlink()
    if exists:
        checked_directory(target)
    with tempfile.TemporaryDirectory(prefix='.unpack-', dir=str(state_dir)) as temp:
        new = Path(temp) / 'repository'
        root = target if exists else new
        if not exists:
            new.mkdir()
        seen = set()
        packages = expanded = 0
        with tarfile.open(str(archive), 'r:gz') as data:
            for member in data:
                name = member.name
                if name.startswith('./'):
                    name = name[2:]
                if member.isdir() and name in ('.', '', 'Packages', 'repodata', 'licenses'):
                    continue
                if (member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or member.sparse is not None or
                        not (re.fullmatch(r'Packages/[A-Za-z0-9][A-Za-z0-9_.+%-]*\.rpm', name) or
                             re.fullmatch(r'repodata/[A-Za-z0-9][A-Za-z0-9_.+-]*', name) or
                             re.fullmatch(r'licenses/[A-Za-z0-9][A-Za-z0-9_.+-]*\.txt', name)) or name in seen):
                    raise ValueError('Unexpected entry in package release')
                expanded += member.size
                if member.size <= 0 or expanded > 1024 * 1024 * 1024 or len(seen) >= 1100:
                    raise ValueError('Invalid package release size')
                if name.startswith('Packages/dahdi-firmware-') and name != PROJECT_RPM:
                    raise ValueError('Unexpected hardware package in software-only release')
                if name.startswith('Packages/xtables-addons-') and name != XTABLES_RPM:
                    raise ValueError('Unexpected packet filtering package in release')
                if name.startswith('Packages/issabel-geoip-') and name != GEOIP_RPM:
                    raise ValueError('Unexpected country database package in release')
                if name.startswith('Packages/asterisk20-') and name not in ESSENTIAL:
                    raise ValueError('Unexpected Asterisk package from a different build')
                seen.add(name)
                packages += int(name.startswith('Packages/'))
                # DNF makecache reads only metadata. Keep the authenticated archive
                # for installation without occupying a second RPM-sized private tree.
                if metadata_only and not name.startswith('repodata/'):
                    continue
                path = root / name
                with data.extractfile(member) as incoming:
                    if exists:
                        checked_directory(path.parent)
                        regular(path)
                        with path.open('rb') as old:
                            if sha256(incoming) != sha256(old):
                                raise ValueError('Existing MytelPBX package repository differs')
                    else:
                        path.parent.mkdir(exist_ok=True)
                        with path.open('xb') as outgoing:
                            shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
                        path.chmod(0o644)
        if (packages != pin['packages'] or not ESSENTIAL.issubset(seen) or
                'repodata/repomd.xml' not in seen or
                'licenses/ioncube-loaders-EULA.txt' not in seen):
            raise ValueError('Incomplete MytelPBX package repository')
        if not exists:
            for directory in [new] + list(new.iterdir()):
                directory.chmod(0o755)
            new.rename(target)
    return target


def configure(repo_dir, state_dir, workdir, pin):
    repo_dir = checked_directory(repo_dir)
    workdir = checked_directory(workdir)
    staged = repo_dir in state_dir.parents
    state_dir = checked_directory(state_dir, 0o700 if staged else 0o755)
    keys = {}
    for name, expected in KEYS.items():
        data = (Path(__file__).with_name('keys') / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Reviewed RPM public key differs')
        key = state_dir / name
        if key.exists() or key.is_symlink():
            regular(key)
            if key.read_bytes() != data:
                raise ValueError('Existing MytelPBX public key differs')
        keys[key] = data
    repository = unpack(fetch(workdir, pin), state_dir, pin, metadata_only=staged)
    for key, data in keys.items():
        if not key.exists():
            atomic_write(key, data, 0o644)
    # These project builds include Asterisk, the optional hardware importer
    # and both native-format country data consumers.
    # Keep native and project RPMs disjoint when DNF selects package sources.
    base = ('baseurl={}\nenabled=1\ngpgcheck=1\nsslverify=1\nskip_if_unavailable=0\n'
            .format(repository.as_uri()))
    native_keys = ' '.join(key.as_uri() for key in sorted(keys) if key.name != PROJECT_KEY)
    definition = ('[mytelpbx-packages]\nname=MytelPBX packages\n' + base +
                  'excludepkgs=' + PROJECT_FILTER + '\ngpgkey=' + native_keys +
                  '\n\n[mytelpbx-builds]\nname=MytelPBX builds\n' + base +
                  'includepkgs=' + PROJECT_FILTER + '\ngpgkey=' + (state_dir / PROJECT_KEY).as_uri() + '\n').encode('ascii')
    for filename in FILES:
        path = repo_dir / filename
        if path.exists() or path.is_symlink():
            regular(path)
        # Keep all three native filenames under management: vendor RPMs can
        # recreate them from scriptlets before the next transaction.
        content = definition if filename == FILES[0] else b'# Sources are configured in Issabel.repo\n'
        atomic_write(path, content, 0o644)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-dir', required=True, type=Path)
    parser.add_argument('--state-dir', required=True, type=Path)
    parser.add_argument('--workdir', required=True, type=Path)
    args = parser.parse_args()
    try:
        configure(args.repo_dir, args.state_dir, args.workdir, release_pin())
    except (OSError, ValueError, KeyError, EOFError, tarfile.TarError) as error:
        message = (str(error) if isinstance(error, ValueError) and
                   str(error) in ('GitHub package download failed',
                                  'Downloaded MytelPBX packages do not match the release',
                                  'Existing MytelPBX package repository differs') else
                   'MytelPBX package source could not be prepared')
        try:
            workdir = checked_directory(args.workdir)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=str(workdir),
                                             prefix='package-source-', suffix='.log', delete=False) as log:
                log.write(str(error) + '\n')
                if str(error) == 'GitHub package download failed':
                    log.write('Transfer attempts: ' + str(workdir / 'github-package-transfer.log') + '\n')
                message += '. Private log: ' + log.name
        except (OSError, ValueError):
            pass
        parser.exit(1, message + '\n')
