#!/usr/bin/env python3
"""Prepare the Apache/FOP2 TLS pair before fresh vendor package scriptlets.

Preserve an existing valid matching pair, including custom identities. Refuse
partial/invalid pairs rather than rotating them. Only new files are published,
with exclusive hard links and rollback scoped to those exact new inodes.
Root-owned OS directory components are trusted against concurrent privileged
replacement; this helper is not a sandbox against another root process.
Python 3.6 compatible. No network, service, firewall or trust-store changes.
"""
import argparse
import datetime
import ipaddress
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile

CERTIFICATE = 'etc/pki/tls/certs/localhost.crt'
PRIVATE_KEY = 'etc/pki/tls/private/localhost.key'
COMMAND_TIMEOUT = 30


def run_command(arguments):
    try:
        result = subprocess.run(arguments, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=COMMAND_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('TLS command unavailable or timed out') from error
    if result.returncode:
        # OpenSSL stderr may contain input material; do not expose it in logs.
        raise ValueError('TLS command failed; existing files were not replaced')
    return result.stdout


def subject_alternatives(hostnames, addresses):
    names = []
    for hostname in hostnames:
        if (not isinstance(hostname, str) or len(hostname) > 253 or
                not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', hostname) or
                any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                    for label in hostname.split('.'))):
            raise ValueError('Invalid TLS hostname')
        names.append('DNS:' + hostname.lower())
    for address in addresses:
        try:
            if '%' in address:
                raise ValueError('Scoped addresses are not certificate identities')
            names.append('IP:' + str(ipaddress.ip_address(address)))
        except (ValueError, TypeError) as error:
            raise ValueError('Invalid TLS IP address') from error
    if not names or len(names) > 64:
        raise ValueError('TLS requires between 1 and 64 identities')
    return ','.join(sorted(set(names)))


def trusted_directory(path):
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or path.is_symlink():
        raise ValueError('Non-directory or symlinked TLS parent refused')
    if os.name == 'posix' and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022):
        raise ValueError('Unsafe TLS directory owner or permissions')


def prepare_directories(root, relative):
    path = root
    trusted_directory(path)
    for component in Path(relative).parent.parts:
        path = path / component
        if not path.exists() and not path.is_symlink():
            path.mkdir(mode=0o755)
        trusted_directory(path)


def regular_file(path):
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink() or metadata.st_size > 1024 * 1024:
        raise ValueError('Invalid or symlinked TLS file')
    if os.name == 'posix' and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022):
        raise ValueError('Unsafe TLS file owner or permissions')
    return metadata


def validate_pair(certificate, key, openssl):
    regular_file(certificate)
    regular_file(key)
    dates = run_command([openssl, 'x509', '-in', str(certificate), '-noout', '-startdate', '-enddate'])
    try:
        parsed = dict(line.split('=', 1) for line in dates.decode('ascii').splitlines())
        start = datetime.datetime.strptime(parsed['notBefore'], '%b %d %H:%M:%S %Y GMT')
        end = datetime.datetime.strptime(parsed['notAfter'], '%b %d %H:%M:%S %Y GMT')
        now = datetime.datetime.utcnow()
        if not start <= now < end:
            raise ValueError('Certificate is not currently valid')
    except (UnicodeError, KeyError, ValueError) as error:
        raise ValueError('TLS certificate validity check failed') from error
    public_certificate = run_command([openssl, 'x509', '-in', str(certificate), '-pubkey', '-noout'])
    public_key = run_command([openssl, 'pkey', '-in', str(key), '-passin', 'pass:', '-pubout'])
    if public_certificate.replace(b'\r\n', b'\n') != public_key.replace(b'\r\n', b'\n'):
        raise ValueError('TLS certificate and private key do not match')


def restore_context(paths):
    run_command(['/usr/sbin/restorecon', '--'] + [str(path) for path in paths])


def remove_owned_links(published):
    for path, identity in reversed(published):
        try:
            metadata = path.lstat()
            if (metadata.st_dev, metadata.st_ino) == identity and stat.S_ISREG(metadata.st_mode):
                path.unlink()
        except FileNotFoundError:
            pass


def prepare(root, hostnames, addresses, openssl='/usr/bin/openssl', relabel=restore_context):
    alternatives = subject_alternatives(hostnames, addresses)
    root = Path(root).absolute()
    if root.resolve() != root or root.is_symlink():
        raise ValueError('Symlinked TLS root refused')
    for relative in [CERTIFICATE, PRIVATE_KEY]:
        prepare_directories(root, relative)
    certificate, key = root / CERTIFICATE, root / PRIVATE_KEY
    existing = [path.exists() or path.is_symlink() for path in [certificate, key]]
    if any(existing):
        if not all(existing):
            raise ValueError('Partial TLS pair refused; restore the matching pair explicitly')
        validate_pair(certificate, key, openssl)
        return 'preserved'
    with tempfile.TemporaryDirectory(prefix='.mytell-tls-', dir=str(key.parent)) as temporary:
        staged_key, staged_certificate = Path(temporary) / 'key.pem', Path(temporary) / 'cert.pem'
        run_command([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '365',
                     '-subj', '/O=MyTellPBX/CN=MyTellPBX', '-addext', 'subjectAltName=' + alternatives,
                     '-addext', 'extendedKeyUsage=serverAuth',
                     '-keyout', str(staged_key), '-out', str(staged_certificate)])
        os.chmod(str(staged_key), 0o600)
        os.chmod(str(staged_certificate), 0o644)
        validate_pair(staged_certificate, staged_key, openssl)
        published = []
        try:
            for source, target in [(staged_key, key), (staged_certificate, certificate)]:
                os.link(str(source), str(target))
                metadata = source.stat()
                published.append((target, (metadata.st_dev, metadata.st_ino)))
            relabel([certificate, key])
        except Exception:
            remove_owned_links(published)
            raise
    return 'created'


def local_identities():
    # Local interface inspection only: no DNS resolution or outbound connections.
    hostname = socket.gethostname().rstrip('.')
    names = [hostname, 'localhost'] if hostname != 'localhost' else ['localhost']
    output = run_command(['/usr/sbin/ip', '-o', 'address', 'show'])
    addresses = ['127.0.0.1', '::1']
    for value in re.findall(rb'\binet6?\s+([^\s/]+)/[0-9]+', output):
        address = value.decode('ascii')
        if '%' not in address:
            addresses.append(address)
    return names, addresses


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/')
    parser.add_argument('--hostname', action='append', default=[])
    parser.add_argument('--ip', action='append', default=[])
    args = parser.parse_args(argv)
    if getattr(os, 'geteuid', lambda: -1)() != 0:
        parser.error('TLS preparation requires root')
    try:
        names, addresses = (args.hostname, args.ip) if args.hostname or args.ip else local_identities()
        status = prepare(args.root, names, addresses)
        print('MyTellPBX TLS: ' + status)
        return 0
    except (OSError, ValueError) as error:
        print('MyTellPBX TLS preparation failed: ' + str(error), file=__import__('sys').stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
