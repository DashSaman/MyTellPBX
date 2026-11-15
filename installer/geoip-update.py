#!/usr/bin/env python3
"""Bounded, keyless DB-IP Country Lite data for the installed xt_geoip consumer.

No firewall rules, services, kernel settings or vendor credentials are touched.
Python 3.6 compatible. Unknown cron/data ownership is refused, never overwritten.
"""
import argparse
import csv
import datetime
import gzip
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time

OWNER = 'MyTellPBX GeoIP'
BUILDER_SHA256 = '0cecbfa332dae054495b7aa40b6bab311325e82161f5eefa1306cd4de82b25ff'
VENDOR_CRON_SHA256 = '1d7f584b55f3dcba58e4271b03141fc2cbc424944172da859c3157c04ad3400c'
VENDOR_STATUS_SHA256 = 'de1fb7c39ec9b67859d4346e90c90a8fb440d32ea16dcb1437c1024fd8bfa34a'
PROGRAM = 'usr/local/libexec/mytellpbx/geoip-update.py'
CRON = 'etc/cron.daily/geoip_update.sh'
STATE = 'var/lib/mytellpbx-geoip'
RELEASES = 'usr/share/mytellpbx-geoip/releases'
ACTIVE = 'usr/share/xt_geoip'
MAX_COMPRESSED = 16 * 1024 * 1024
MAX_CSV = 128 * 1024 * 1024
NOTICE = ('IP Geolocation by DB-IP: https://db-ip.com\n'
          'DB-IP Country Lite, https://db-ip.com/db/download/ip-to-country-lite\n'
          'License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/\n'
          'Changes: validated ranges converted to legacy xtables binary format.\n'
          'Monthly free data has reduced coverage/accuracy; IP location is approximate.\n')
WRAPPER = ('#!/bin/sh\n# MyTellPBX managed keyless GeoIP updater v1\n'
           'exec /usr/bin/python3 -B /usr/local/libexec/mytellpbx/geoip-update.py --update\n').encode('ascii')


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected a regular owned input: ' + str(path))
    return path


def owned_path(root, relative):
    """Reject symlinked managed ancestors before creating/chmodding files."""
    path = Path(root).resolve() / relative
    if path.resolve() != path.absolute():
        raise ValueError('Managed GeoIP path contains a symlink: ' + str(path))
    return path


def verify_builder(path):
    if digest(regular(path)) != BUILDER_SHA256:
        raise ValueError('Installed GeoIP builder differs from the reviewed legacy format')


def convert_csv(source, destination, min_rows=100000, min_countries=200):
    """Validate ordered DB-IP ranges and derive every expected packed-file hash."""
    csv.field_size_limit(256)
    hashes, countries, previous = {}, set(), {4: -1, 6: -1}
    families, rows, size, last_family = {'4': 0, '6': 0}, 0, 0, 4
    deadline = time.monotonic() + 120
    with gzip.open(str(source), 'rt', encoding='utf-8', newline='') as stream, Path(destination).open('w', encoding='utf-8', newline='') as output:
        writer = csv.writer(output, lineterminator='\n')
        for row in csv.reader(stream, strict=True):
            if len(row) != 3 or not re.fullmatch('[A-Z]{2}', row[2]):
                raise ValueError('Invalid country CSV fields')
            start, end = ipaddress.ip_address(row[0]), ipaddress.ip_address(row[1])
            family, first, final = start.version, int(start), int(end)
            if family != end.version or first > final or family < last_family or first <= previous[family]:
                raise ValueError('Mixed, reversed, unordered or overlapping country range')
            previous[family], last_family = final, family
            size += sum(len(field) for field in row) + 16
            rows += 1
            if rows > 1500000 or size > MAX_CSV:
                raise ValueError('Country CSV exceeds its bounded size')
            if rows % 4096 == 0 and time.monotonic() > deadline:
                raise ValueError('Country conversion exceeded its bounded deadline')
            code = row[2]
            if code not in countries:
                countries.add(code)
                for order in ('BE', 'LE'):
                    for version in (4, 6):
                        hashes[order + '/' + code + '.iv' + str(version)] = hashlib.sha256()
            if family == 4:
                be, le = struct.pack('>II', first, final), struct.pack('<II', first, final)
            else:
                be = start.packed + end.packed
                le = b''.join(struct.pack('<4I', *struct.unpack('>4I', value)) for value in (start.packed, end.packed))
            hashes['BE/' + code + '.iv' + str(family)].update(be)
            hashes['LE/' + code + '.iv' + str(family)].update(le)
            families[str(family)] += 1
            # Full IPv6 expansion avoids the legacy builder's compressed-address ambiguity.
            writer.writerow([start.exploded, end.exploded, str(first), str(final), code, code])
    if rows < min_rows or len(countries) < min_countries or not all(families.values()):
        raise ValueError('Empty, partial or single-family country database')
    return {'rows': rows, 'families': families, 'countries': sorted(countries),
            'files': {name: value.hexdigest() for name, value in hashes.items()}}


def validate_build(directory, expected):
    found = {}
    for order in ('BE', 'LE'):
        folder = Path(directory) / order
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError('Missing packed country directory')
        for path in folder.iterdir():
            if not re.fullmatch(r'[A-Z]{2}\.iv[46]', path.name):
                raise ValueError('Unexpected packed country filename')
            regular(path)
            if path.stat().st_size % (8 if path.suffix == '.iv4' else 32):
                raise ValueError('Truncated packed country range')
            found[order + '/' + path.name] = digest(path)
    if found != expected:
        raise ValueError('Packed country data does not match all validated source ranges')
    return found


def download_month(output, month, runner=subprocess.run):
    if not re.fullmatch(r'20[0-9]{2}-(?:0[1-9]|1[0-2])', month):
        raise ValueError('Invalid monthly source identifier')
    output = Path(output)
    if output.is_symlink():
        raise ValueError('Download destination must not be a symlink')
    url = 'https://download.db-ip.com/free/dbip-country-lite-' + month + '.csv.gz'
    result = runner(['/usr/bin/curl', '--fail', '--silent', '--show-error', '--proto', '=https',
                     '--connect-timeout', '15', '--max-time', '90', '--max-filesize', str(MAX_COMPRESSED),
                     '--output', str(output), '--write-out', '%{http_code}', url],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=95)
    if result.returncode or result.stdout.strip() != '200':
        raise ValueError('Public country download failed; previous data retained')
    regular(output)
    if not 12 <= output.stat().st_size <= MAX_COMPRESSED or output.read_bytes()[:2] != b'\x1f\x8b':
        raise ValueError('Country response is not a bounded gzip archive')
    return url


def atomic(path, data, mode=0o644):
    path = Path(path)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('Owned file became a symlink or non-file')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.mytel-geoip-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def release_info(release):
    release = Path(release)
    info = json.loads(regular(release / 'manifest.json').read_text(encoding='utf-8'))
    if info.get('owner') != OWNER or info.get('layout') != 'flat-network-BE' or info.get('builder_sha256') != BUILDER_SHA256:
        raise ValueError('Country release ownership/format differs')
    validate_build(release, info['files'])
    return info


def activate(root, release):
    root, release = Path(root).resolve(), Path(release).resolve()
    if release.parent != root / RELEASES:
        raise ValueError('Country release is outside the owned release directory')
    release_info(release)
    active, backup = root / ACTIVE, None
    if active.is_symlink():
        previous = active.resolve()
        if previous.name != 'BE' or previous.parent.parent != root / RELEASES:
            raise ValueError('Existing country pointer is not owned')
        release_info(previous.parent)
        if previous == release / 'BE':
            return False
    elif active.exists():
        if not active.is_dir() or any(active.iterdir()):
            raise ValueError('Unknown populated country data is preserved')
        # First activation starts from an empty vendor directory. Preserve it;
        # subsequent valid-database updates replace one symlink atomically.
        backup = active.parent / '.xt_geoip-empty-before-mytell'
        if backup.exists() or backup.is_symlink():
            raise ValueError('Initial country-directory backup already exists')
    active.parent.mkdir(parents=True, exist_ok=True)
    pointer = active.parent / ('.xt_geoip-next-' + os.urandom(8).hex())
    try:
        os.symlink(str(release / 'BE'), str(pointer))
        if backup is not None:
            os.replace(str(active), str(backup))
        os.replace(str(pointer), str(active))
    except Exception:
        if backup is not None and backup.exists() and not active.exists() and not active.is_symlink():
            os.replace(str(backup), str(active))
        raise
    finally:
        if pointer.is_symlink():
            pointer.unlink()
    return True


def publish_status(root, info):
    directory = owned_path(root, 'usr/share/mytellpbx-geoip')
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o755)
    # Also normalize an earlier candidate's fractional timestamp on an idempotent
    # retry; a cached valid database must not leave the strict public UI unavailable.
    created = info['created_utc']
    pattern = '%Y-%m-%dT%H:%M:%S.%fZ' if '.' in created else '%Y-%m-%dT%H:%M:%SZ'
    stamp = datetime.datetime.strptime(created, pattern).strftime('%Y-%m-%dT%H:%M:%SZ')
    public = {'owner': OWNER, 'schema': 1, 'provider': 'DB-IP Country Lite', 'status': 'ready',
              'month': info['month'], 'updated_utc': stamp, 'rows': info['rows'],
              'ipv4_ranges': info['families']['4'], 'ipv6_ranges': info['families']['6'],
              'country_count': len(info['countries']), 'layout': 'flat-network-BE',
              'source_url': info['source_url'], 'source_sha256': info['source_sha256'],
              'attribution_url': 'https://db-ip.com', 'license': 'CC-BY-4.0',
              'license_url': 'https://creativecommons.org/licenses/by/4.0/'}
    atomic(directory / 'status.json', (json.dumps(public, sort_keys=True) + '\n').encode('utf-8'))
    return public


def publish_metadata(root, info):
    try:
        publish_status(root, info)
        atomic(Path(root) / STATE / 'latest.json', (json.dumps(info, sort_keys=True) + '\n').encode('utf-8'), 0o600)
    except Exception as error:
        raise ValueError('Validated GeoIP data is active; status publication incomplete. Retry the updater to repair metadata.') from error


def install(root, source, status_module=None):
    root, source = Path(root).resolve(), regular(source)
    cron, program, state = (owned_path(root, name) for name in (CRON, PROGRAM, STATE))
    owned_path(root, RELEASES)
    backup = owned_path(root, 'var/backups/mytellpbx/geoip')
    cron_data = regular(cron).read_bytes()
    if cron_data != WRAPPER and hashlib.sha256(cron_data).hexdigest() != VENDOR_CRON_SHA256:
        raise ValueError('Cron updater has unknown owner edits; no files changed')
    status_target, status_before, status_after = None, None, None
    if status_module is not None:
        status_target = owned_path(root, 'var/www/html/modules/sec_geoip_key/index.php')
        status_before = regular(status_target).read_bytes()
        status_after = regular(status_module).read_bytes()
        if status_before != status_after and hashlib.sha256(status_before).hexdigest() != VENDOR_STATUS_SHA256:
            raise ValueError('GeoIP status module has unknown owner edits; no files changed')
    verify_builder(root / 'usr/share/geoip/xt_geoip_build')
    content = source.read_bytes()
    old = None
    if (state / 'install.json').exists():
        old = json.loads(regular(state / 'install.json').read_text(encoding='utf-8'))
        if old.get('owner') != OWNER:
            raise ValueError('GeoIP installation ownership differs')
    if program.exists() or program.is_symlink():
        present = regular(program).read_bytes()
        if present != content and (not old or hashlib.sha256(present).hexdigest() != old.get('program_sha256')):
            raise ValueError('Installed updater differs from its owned source')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(str(state), 0o700)
    if cron_data != WRAPPER:
        backup.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(str(backup), 0o700)
        original = backup / ('cron-' + VENDOR_CRON_SHA256 + '.original')
        if original.exists() and regular(original).read_bytes() != cron_data:
            raise ValueError('Existing original cron backup differs')
        if not original.exists():
            atomic(original, cron_data, 0o600)
    if status_target is not None and status_before != status_after:
        backup.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup.chmod(0o700)
        original = backup / ('status-' + VENDOR_STATUS_SHA256 + '.original')
        if original.exists() and regular(original).read_bytes() != status_before:
            raise ValueError('Existing original GeoIP status backup differs')
        if not original.exists():
            atomic(original, status_before, 0o600)
    atomic(program, content, 0o755)
    atomic(cron, WRAPPER, 0o755)
    if status_target is not None:
        atomic(status_target, status_after)
    atomic(state / 'install.json', json.dumps({'owner': OWNER, 'program_sha256': hashlib.sha256(content).hexdigest()}).encode('utf-8'), 0o600)


def update(root):
    import fcntl
    root = Path(root).resolve()
    state, releases = owned_path(root, STATE), owned_path(root, RELEASES)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = owned_path(root, STATE + '/update.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        month = datetime.datetime.utcnow().strftime('%Y-%m')
        active = root / ACTIVE
        if active.is_symlink():
            prior = active.resolve()
            if prior.name != 'BE' or prior.parent.parent != releases:
                raise ValueError('Existing country pointer is not owned')
            info = release_info(prior.parent)
            if info.get('month') == month:
                publish_metadata(root, info)
                return info
        elif active.exists() and (not active.is_dir() or any(active.iterdir())):
            raise ValueError('Unknown populated country data is preserved')
        builder = root / 'usr/share/geoip/xt_geoip_build'
        verify_builder(builder)
        releases.mkdir(parents=True, exist_ok=True)
        releases.parent.chmod(0o755)
        releases.chmod(0o755)
        with tempfile.TemporaryDirectory(prefix='.stage-', dir=str(releases)) as temporary:
            work = Path(temporary)
            source, legacy, compiled = work / 'source.gz', work / 'legacy.csv', work / 'compiled'
            url = download_month(source, month)
            info = convert_csv(source, legacy)
            compiled.mkdir()
            result = subprocess.run(['/usr/bin/perl', str(builder), '-D', str(compiled), str(legacy)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
            if result.returncode:
                raise ValueError('Installed country builder failed; previous data retained')
            validate_build(compiled, info['files'])
            info.update(owner=OWNER, schema=1, layout='flat-network-BE', month=month,
                        source_url=url, source_sha256=digest(source), builder_sha256=BUILDER_SHA256,
                        license='CC-BY-4.0', attribution='https://db-ip.com',
                        created_utc=datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
            atomic(compiled / 'NOTICE.txt', NOTICE.encode('utf-8'))
            atomic(compiled / 'manifest.json', (json.dumps(info, sort_keys=True, indent=2) + '\n').encode('utf-8'))
            for folder in (compiled, compiled / 'BE', compiled / 'LE'):
                folder.chmod(0o755)
            for order in ('BE', 'LE'):
                for file in (compiled / order).iterdir():
                    file.chmod(0o644)
            destination = releases / (month + '-' + info['source_sha256'][:16])
            if destination.exists() or destination.is_symlink():
                if destination.is_symlink() or release_info(destination)['source_sha256'] != info['source_sha256']:
                    raise ValueError('Existing country release differs')
            else:
                os.replace(str(compiled), str(destination))
            activate(root, destination)
            publish_metadata(root, info)
            return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--install', action='store_true')
    mode.add_argument('--update', action='store_true')
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--status-module', type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('GeoIP activation requires root')
    os.umask(0o077)
    if args.install:
        if args.status_module is None:
            raise ValueError('--install requires the reviewed read-only provider status module')
        install(args.root, Path(__file__).resolve(), args.status_module)
    info = update(args.root)
    print(json.dumps({'owner': OWNER, 'month': info['month'], 'rows': info['rows'],
                      'countries': len(info['countries']), 'layout': info['layout'],
                      'source_sha256': info['source_sha256']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('MyTellPBX GeoIP: ' + str(error)[:300])
