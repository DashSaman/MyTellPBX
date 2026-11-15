#!/usr/bin/env python3
"""Install the pinned MytelDesk product, including its automatic CPU VAD runtime.

Python 3.6+, standard library only. Never imports or patches released application
code. The upstream installer retains ownership of services, secrets and rollback.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

sys.dont_write_bytecode = True
MAX_DOWNLOAD = 128 * 1024 * 1024
MAX_UNPACKED = 512 * 1024 * 1024
LEGACY_PATHS = (Path('/opt/opdesk'), Path('/opt/OpDesk'), Path('/etc/mytellpbx/opdesk.env'),
                Path('/etc/systemd/system/mytellpbx-opdesk.service'))
STANDALONE_STATE = Path('/etc/myteldesk/installation.json')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''): result.update(block)
    return result.hexdigest()


def validate_pin(value):
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1:
        raise ValueError('Unsupported MytelDesk release pin')
    if value.get('repository') != 'DashSaman/MytelDesk': raise ValueError('Unexpected MytelDesk repository')
    version = value.get('version', '')
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Invalid MytelDesk version')
    if value.get('archive') != 'myteldesk-' + version + '.tar.gz': raise ValueError('Invalid MytelDesk archive')
    for key, size in [('sha256', 64), ('source_commit', 40), ('source_tree', 40)]:
        if not isinstance(value.get(key), str) or not re.fullmatch('[0-9a-f]{' + str(size) + '}', value[key]):
            raise ValueError('Incomplete MytelDesk source pin')
    return value


def validate_public_url(value):
    if value is None or value == '': return None
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError()
        if url.path not in ('', '/', '/MytellDesk', '/MytellDesk/') or any(c.isspace() for c in value): raise ValueError()
        if url.port is not None and not 1 <= url.port <= 65535: raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('MytelDesk public URL must be an HTTPS origin without credentials or query data') from None
    return value


def secure_directory(path):
    """Do not adopt a writable/symlinked root cache path or any existing parent."""
    path = Path(path)
    if not path.is_absolute(): raise ValueError('MytelDesk cache requires an absolute path')
    for candidate in reversed([path] + list(path.parents)):
        if candidate.is_symlink(): raise ValueError('MytelDesk cache symlink refused')
        if candidate.exists():
            info = candidate.stat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
                raise ValueError('MytelDesk cache has unsafe ownership or permissions')
        else: candidate.mkdir(mode=0o700)
    path.chmod(0o700)


def relative_name(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('Unsafe release path')
    parsed = PurePosixPath(name)
    if parsed.is_absolute() or '..' in parsed.parts or name != parsed.as_posix(): raise ValueError('Unsafe release path')
    return parsed


def verify_bundle(bundle, pin):
    pin = validate_pin(pin); bundle = Path(bundle)
    if bundle.is_symlink() or not bundle.is_dir(): raise ValueError('Invalid cached MytelDesk bundle')
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 1 or manifest.get('version') != pin['version'] or manifest.get('source_tree') != pin['source_tree']:
        raise ValueError('MytelDesk manifest does not match the release pin')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files: raise ValueError('Empty MytelDesk manifest')
    actual = set()
    for item in bundle.rglob('*'):
        if item.is_symlink(): raise ValueError('Cached MytelDesk symlink refused')
        if item.is_file(): actual.add(item.relative_to(bundle).as_posix())
    if actual != set(files) | {'manifest.json'}: raise ValueError('MytelDesk bundle has missing or unlisted files')
    for name, info in files.items():
        relative_name(name)
        if not isinstance(info, dict) or type(info.get('bytes')) is not int or info['bytes'] < 0:
            raise ValueError('Invalid MytelDesk manifest entry')
        path = bundle / name
        if path.stat().st_size != info['bytes'] or digest(path) != info.get('sha256'):
            raise ValueError('MytelDesk file checksum mismatch')
    if (bundle / 'SOURCE_TREE').read_text(encoding='ascii').strip() != pin['source_tree']:
        raise ValueError('MytelDesk source tree mismatch')
    return bundle


def extract_verified(archive, destination, pin):
    pin = validate_pin(pin); destination = Path(destination)
    if destination.exists() or destination.is_symlink(): raise ValueError('Extraction destination already exists')
    if digest(archive) != pin['sha256']: raise ValueError('MytelDesk archive checksum mismatch')
    prefix = 'myteldesk-' + pin['version']
    with tarfile.open(str(archive), 'r:gz') as source:
        members = source.getmembers()
        if len(members) > 100000 or sum(max(0, member.size) for member in members) > MAX_UNPACKED:
            raise ValueError('MytelDesk release exceeds extraction limits')
        names = set()
        for member in members:
            name = member.name.rstrip('/') if member.isdir() else member.name
            parsed = relative_name(name)
            if parsed.parts[0] != prefix or name in names or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe MytelDesk archive member')
            names.add(name)
        destination.mkdir(mode=0o700)
        for member in members:
            target = destination / member.name
            if member.isdir(): target.mkdir(mode=0o755, parents=True, exist_ok=True)
            else:
                target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                with source.extractfile(member) as incoming, target.open('xb') as output: shutil.copyfileobj(incoming, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
    return verify_bundle(destination / prefix, pin)


def download(url, destination):
    started = time.monotonic(); received = 0
    try:
        with urlopen(url, timeout=45) as response, Path(destination).open('wb') as output:
            if urlsplit(response.geturl()).scheme != 'https': raise ValueError('Insecure release redirect')
            for block in iter(lambda: response.read(1024 * 1024), b''):
                received += len(block)
                if received > MAX_DOWNLOAD or time.monotonic() - started > 600: raise ValueError('Release download exceeded limits')
                output.write(block)
    except (OSError, ValueError): raise OSError('Pinned MytelDesk download failed; rerun to retry') from None


def obtain_bundle(pin, cache, fetch=download):
    pin = validate_pin(pin); cache = Path(cache)
    archive = cache / ('myteldesk-' + pin['version'] + '-' + pin['sha256'][:12] + '.tar.gz')
    bundle = cache / ('bundle-' + pin['version'] + '-' + pin['source_tree'][:12])
    if archive.is_symlink() or bundle.is_symlink(): raise ValueError('MytelDesk cache symlink refused')
    if bundle.exists(): return verify_bundle(bundle, pin)
    if not archive.exists():
        descriptor, temporary = tempfile.mkstemp(prefix='.download-', dir=str(cache)); os.close(descriptor)
        temporary = Path(temporary)
        try:
            url = 'https://github.com/' + pin['repository'] + '/releases/download/v' + pin['version'] + '/' + pin['archive']
            fetch(url, temporary)
            if temporary.is_symlink() or digest(temporary) != pin['sha256']: raise ValueError('MytelDesk download checksum mismatch')
            os.replace(str(temporary), str(archive))
        finally:
            if temporary.exists(): temporary.unlink()
    if digest(archive) != pin['sha256']: raise ValueError('Cached MytelDesk archive checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='.extract-', dir=str(cache)) as temporary:
        extracted = extract_verified(archive, Path(temporary) / 'payload', pin)
        os.replace(str(extracted), str(bundle))
    return verify_bundle(bundle, pin)


def run_command(argv):
    subprocess.run(argv, check=True, timeout=2700)


def install_launcher(source, web_root, expected_uid=0):
    """Add fixed launcher files without following a framework-directory symlink.

    Directory descriptors also prevent a writable framework parent being swapped
    into an arbitrary root write between pathname validation and installation.
    """
    source, web_root = Path(source), Path(web_root)
    payloads = {}
    for name in ('launcher-access.php', 'index.php'):
        path = source / name
        if path.is_symlink() or not path.is_file(): raise ValueError('MytelDesk launcher source missing or symlinked')
        payloads[name] = path.read_bytes()
    if os.name != 'posix' or not web_root.is_absolute(): raise ValueError('Launcher installation requires a POSIX web root')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current = os.open('/', flags)
    modules = target = None
    try:
        for part in web_root.parts[1:]:
            if part in ('.', '..'): raise ValueError('Unsafe launcher web root')
            next_directory = os.open(part, flags, dir_fd=current); os.close(current); current = next_directory
        try: os.mkdir('modules', mode=0o755, dir_fd=current)
        except FileExistsError: pass
        modules = os.open('modules', flags, dir_fd=current)
        try: os.mkdir('mytellpbxopdesk', mode=0o755, dir_fd=modules)
        except FileExistsError: pass
        target = os.open('mytellpbxopdesk', flags, dir_fd=modules)
        identity = os.fstat(target)
        if identity.st_uid != expected_uid or stat.S_IMODE(identity.st_mode) & 0o022:
            raise ValueError('Launcher directory has unsafe ownership or permissions')
        missing = []
        for name, data in payloads.items():
            try: descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=target)
            except FileNotFoundError: missing.append(name); continue
            with os.fdopen(descriptor, 'rb') as existing:
                if not stat.S_ISREG(os.fstat(existing.fileno()).st_mode) or existing.read(512 * 1024 + 1) != data:
                    raise ValueError('Existing launcher was edited; preserve it for reviewed maintenance')
        for name in missing:
            temporary = '.mytell-' + os.urandom(12).hex()
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=target)
            try:
                with os.fdopen(descriptor, 'wb') as output:
                    output.write(payloads[name]); output.flush(); os.fsync(output.fileno()); os.fchmod(output.fileno(), 0o644)
                os.rename(temporary, name, src_dir_fd=target, dst_dir_fd=target)
            finally:
                try: os.unlink(temporary, dir_fd=target)
                except FileNotFoundError: pass
        observed = os.stat('mytellpbxopdesk', dir_fd=modules, follow_symlinks=False)
        if (observed.st_dev, observed.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError('Launcher parent changed during installation')
    finally:
        if target is not None: os.close(target)
        if modules is not None: os.close(modules)
        os.close(current)


def install(pin, cache, public_url=None, run=run_command, fetch=download,
            legacy_paths=LEGACY_PATHS, standalone_state=STANDALONE_STATE, launcher_source=None,
            web_root=Path('/var/www/html')):
    pin = validate_pin(pin); public_url = validate_public_url(public_url)
    if not Path(standalone_state).is_file() and any(Path(path).exists() for path in legacy_paths):
        raise ValueError('Legacy Desk installation detected; use reviewed migration, not the fresh PBX installer')
    cache = Path(cache); secure_directory(cache)
    print('MytelDesk ' + pin['version'] + ': verifying the pinned release and automatic CPU voice analysis.', flush=True)
    bundle = obtain_bundle(pin, cache, fetch)
    argv = [sys.executable, '-B', str(bundle / 'installer/install.py'), 'install', '--bundle', str(bundle)]
    if public_url: argv.extend(['--public-url', public_url])
    run(argv)
    run(['/usr/local/sbin/myteldesk', 'doctor'])
    if launcher_source is not None: install_launcher(launcher_source, web_root)
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pin', type=Path, default=Path(__file__).with_name('myteldesk-release.json'))
    parser.add_argument('--cache-root', type=Path, default=Path('/var/lib/mytelpbx-installer/cache/myteldesk'))
    parser.add_argument('--public-url')
    parser.add_argument('--launcher-source', type=Path, default=Path(__file__).resolve().parents[1] / 'modules/mytellpbxopdesk')
    parser.add_argument('--web-root', type=Path, default=Path('/var/www/html'))
    args = parser.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0: parser.error('Run as root on the existing Issabel server')
    try:
        install(json.loads(args.pin.read_text(encoding='utf-8')), args.cache_root, args.public_url,
                launcher_source=args.launcher_source, web_root=args.web_root)
    except ValueError as error:
        print('MytelDesk: ' + str(error), file=sys.stderr)
        return 1
    except (OSError, tarfile.TarError, subprocess.SubprocessError):
        print('MytelDesk installation did not complete. Preserve existing data and review the diagnostics above before retrying.', file=sys.stderr)
        return 1
    print('MytelDesk and CPU VAD verified. Local administrator record: /etc/myteldesk/initial-admin.txt', flush=True)
    return 0


if __name__ == '__main__': sys.exit(main())
