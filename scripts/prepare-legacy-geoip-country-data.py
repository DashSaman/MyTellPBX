#!/usr/bin/env python3
"""Prepare the native GeoIP C library RPM with licensed country databases."""

import argparse
import csv
import ctypes
import ipaddress
import os
from pathlib import Path
import runpy
import shutil
import subprocess


ORIGINAL_SHA256 = 'd3c88f93c06b0abde6c6b00d89b41cbd3b8da231482414940623e0c8e258f661'
DATABASES = {4: 'GeoIP-initial.dat', 6: 'GeoIPv6-initial.dat'}


def convert(csv_path, payload, work):
    library_dir = payload / 'usr/lib64'
    library = ctypes.CDLL(str(library_dir / 'libGeoIP.so.1.6.12'))
    country_codes = (ctypes.c_char * 3 * 256).in_dll(library, 'GeoIP_country_code')
    codes = {bytes(entry).split(b'\0', 1)[0].decode('ascii') for entry in country_codes}
    library.GeoIP_open.argtypes = (ctypes.c_char_p, ctypes.c_int)
    library.GeoIP_open.restype = ctypes.c_void_p
    library.GeoIP_delete.argtypes = (ctypes.c_void_p,)
    for family, name in DATABASES.items():
        family_csv = work / ('country-v{}.csv'.format(family))
        with csv_path.open(encoding='utf-8', newline='') as src, family_csv.open(
                'w', encoding='utf-8', newline='') as target:
            writer = csv.writer(target, quoting=csv.QUOTE_ALL, lineterminator='\n')
            for row in csv.reader(src, strict=True):
                if (':' in row[0]) != (family == 6) or row[4] not in codes:
                    continue
                writer.writerow(row)
        builder = payload / 'usr/bin/geoip-csv-to-dat'
        argv = [str(builder)]
        if family == 6:
            argv.append('-6')
        argv.append(str(family_csv))
        destination = payload / 'usr/share/GeoIP' / name
        if destination.is_symlink() or destination.resolve() != destination:
            raise ValueError('Unexpected native seed database path')
        with destination.open('wb') as output:
            subprocess.run(argv, env=dict(os.environ, LD_LIBRARY_PATH=str(library_dir)),
                           stdout=output, check=True)
        query = (library.GeoIP_country_code_by_addr if family == 4
                 else library.GeoIP_country_code_by_addr_v6)
        query.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
        query.restype = ctypes.c_char_p
        path_bytes = os.fsencode(destination)
        handle = library.GeoIP_open(path_bytes, 0)
        if not handle:
            raise ValueError('Native GeoIP could not open the generated database')
        try:
            samples = (('1.1.1.1', b'AU'), ('10.0.0.1', None)) if family == 4 else (
                ('2606:4700:4700::1111', b'US'), ('fc00::1', None))
            for address, expected in samples:
                assert ipaddress.ip_address(address).version == family
                actual = query(handle, address.encode('ascii'))
                if actual != expected and not (expected is None and actual == b'--'):
                    raise ValueError('Native IPv{} country lookup did not match the control'.format(family))
        finally:
            library.GeoIP_delete(handle)
    print('Native IPv4 and IPv6 country lookups verified with public and unrouted addresses.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_rpm', type=Path)
    parser.add_argument('country_data', type=Path)
    parser.add_argument('repo_source', type=Path)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args()
    repo = args.repo_source.resolve()
    shared = runpy.run_path(str(repo / 'scripts/prepare-xtables-country-data.py'))
    rpm, source = args.original_rpm.resolve(), args.country_data.resolve()
    if (shared['digest'](rpm) != ORIGINAL_SHA256
            or shared['digest'](source) != shared['DBIP_SHA256']):
        raise ValueError('A reviewed GeoIP source checksum differs')
    work = args.workspace.resolve()
    work.mkdir(mode=0o700)
    sources, specs = work / 'SOURCES', work / 'SPECS'
    sources.mkdir()
    specs.mkdir()
    payload = work / 'payload'
    inventory = shared['payload_inventory'](rpm)
    shared['extract'](rpm, payload)
    geography = runpy.run_path(str(repo / 'installer/geoip-update.py'))
    legacy = work / 'country-legacy.csv'
    geography['convert_csv'](source, legacy)
    convert(legacy, payload, work)
    license_name = '/usr/share/licenses/issabel-geoip/DB-IP-Country-Lite.txt'
    license_path = payload / license_name[1:]
    license_path.parent.mkdir(parents=True, exist_ok=True)
    license_path.write_text(geography['NOTICE'] + 'Database transform: November 2026 legacy GeoIP country format.\n',
                            encoding='utf-8')
    inventory[license_name] = (0o100644, 128, 'root', 'root')
    shutil.copyfile(source, sources / 'dbip-country-lite-2026-11.csv.gz')
    subprocess.run([
        'tar', '-C', str(payload), '--format=ustar', '--sort=name', '--numeric-owner',
        '--owner=0', '--group=0', '--mtime=@' + shared['REVISION'],
        '-czf', str(sources / 'legacy-geoip-prepared-payload.tar.gz'), '.',
    ], check=True)
    query = lambda *flags: shared['query'](rpm, *flags).splitlines()
    dependencies = sorted({name for name in query('--requires') if not name.startswith('rpmlib(')})
    provides = [name for name in query('--provides') if name.startswith('libGeoIP.so.1')]
    content = [
        '%global debug_package %{nil}', '%global __os_install_post %{nil}',
        'Name: issabel-geoip', 'Version: 1.6.12', 'Release: 3.mytel.el8',
        'Summary: Native GeoIP library with DB-IP Country Lite data',
        'License: LGPL-2.1-or-later AND CC-BY-4.0', 'URL: https://github.com/IssabelFoundation/geoip',
        'Source0: legacy-geoip-prepared-payload.tar.gz',
        'Source1: geoip-vendor-source-without-legacy-data.tar.gz',
        'Source2: dbip-country-lite-2026-11.csv.gz', 'AutoReqProv: no',
        'Provides: GeoIP = %{version}-%{release}',
    ]
    content.extend('Provides: ' + name for name in provides)
    content.extend('Requires: ' + name for name in dependencies)
    content.extend([
        '', '%description', 'Native GeoIP library with attributed DB-IP country data.', '',
        '%prep', '', '%build', '', '%install',
        'mkdir -p %{buildroot}', 'tar -xzf %{SOURCE0} -C %{buildroot}', '',
        '%post -p /bin/sh',
        '# The verified package already provides current databases.',
        '# The native scheduled updater remains installed for subsequent updates.',
        'test -s /usr/share/GeoIP/GeoIP.dat && test -s /usr/share/GeoIP/GeoIPv6.dat',
        '', '%files',
    ])
    content.extend(shared['file_spec'](name, record) for name, record in sorted(inventory.items()))
    (specs / 'issabel-geoip.spec').write_text('\n'.join(content) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
