#!/usr/bin/env python3
"""Prepare the reviewed xtables RPM build with DB-IP Lite country data."""

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import runpy
import shutil
import stat
import struct
import subprocess


ORIGINAL_SHA256 = '43255b0c3a545eec131191f188175ad464164c7fe8eb61684e98f505124d9b37'
DBIP_SHA256 = 'e5c8459d638a272ece7f4d7cfa49dce18d91b4f403f6940ba9249bf0db3781fd'
REVISION = '1795219200'
RANGES = re.compile(r'[A-Z]{2}\.iv[46]')
OLD_CSV = 'GeoIP-legacy.csv'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            result.update(chunk)
    return result.hexdigest()


def query(rpm, *arguments):
    return subprocess.check_output(['rpm', '-qp', *arguments, str(rpm)],
                                   stderr=subprocess.DEVNULL, text=True)


def payload_inventory(rpm):
    inventory = {}
    query_format = '[%{FILENAMES}\t%{FILEMODES:octal}\t%{FILEFLAGS}\t%{FILEUSERNAME}\t%{FILEGROUPNAME}\n]'
    for row in query(rpm, '--queryformat', query_format).splitlines():
        name, mode, flags, user, group = row.split('\t')
        path = Path(name)
        if not path.is_absolute() or '..' in path.parts or not re.fullmatch(r'/[A-Za-z0-9+_./~-]+', name):
            raise ValueError('Unexpected path in the reviewed package')
        inventory[name] = (int(mode, 8), int(flags), user, group)
    return inventory


def extract(rpm, destination):
    destination.mkdir()
    sender = subprocess.Popen(['rpm2cpio', str(rpm)], stdout=subprocess.PIPE)
    try:
        subprocess.run(['cpio', '--extract', '--make-directories', '--quiet', '--no-absolute-filenames'],
                       cwd=str(destination), stdin=sender.stdout, check=True)
    finally:
        sender.stdout.close()
        if sender.wait():
            raise ValueError('The original RPM payload could not be read')


def build_country_data(repo, source, tree, work):
    geography = runpy.run_path(str(repo / 'installer/geoip-update.py'))
    builder = tree / 'usr/share/geoip/xt_geoip_build'
    geography['verify_builder'](builder)
    csv = work / OLD_CSV
    expected = geography['convert_csv'](source, csv)
    data = work / 'packed'
    data.mkdir()
    subprocess.run([str(builder), '-D', str(data), str(csv)], check=True,
                   stdout=subprocess.DEVNULL)
    geography['validate_build'](data, expected['files'])

    # The offline seed's IPv4 and IPv6 address mappings must be equivalent in
    # both versions of the native layout. Do not change any firewall rules.
    for literal, code in [('1.1.1.1', 'AU'), ('2606:4700:4700::1111', 'US')]:
        address = ipaddress.ip_address(literal)
        for order, endian in [('BE', '>'), ('LE', '<')]:
            path = data / order / (code + '.iv' + str(address.version))
            if address.version == 4:
                bounds = struct.iter_unpack(endian + 'II', path.read_bytes())
            else:
                bounds = ((int.from_bytes(struct.pack('>4I', *entry[:4]), 'big'),
                           int.from_bytes(struct.pack('>4I', *entry[4:]), 'big'))
                          for entry in struct.iter_unpack(endian + '8I', path.read_bytes()))
            if not any(a <= int(address) <= b for a, b in bounds):
                raise ValueError('The pinned country controls differ from the generated layout')
    return csv, data, expected


def update_payload(tree, inventory, csv, data):
    old_names = {name for name in inventory if Path(name).name == OLD_CSV or RANGES.fullmatch(Path(name).name)}
    folders = {str(Path(name).parent) for name in old_names if Path(name).name != OLD_CSV}
    if {Path(path).name for path in folders} != {'BE', 'LE'}:
        raise ValueError('The reviewed native layout changed')
    for name in old_names:
        path = tree / name[1:]
        if path.is_symlink() or path.resolve() != path:
            raise ValueError('Unexpected link in the native country data')
        path.unlink()
        inventory.pop(name)
        if path.name == OLD_CSV:
            shutil.copyfile(csv, path)
            inventory[name] = (0o100644, 0, 'root', 'root')
    for name in folders:
        folder = tree / name[1:]
        for packed in sorted((data / folder.name).iterdir()):
            path = folder / packed.name
            shutil.copyfile(packed, path)
            inventory[name + '/' + path.name] = (0o100644, 0, 'root', 'root')
    notice = '/usr/share/licenses/xtables-addons/DB-IP-Country-Lite.txt'
    attribution = tree / notice[1:]
    attribution.parent.mkdir(parents=True, exist_ok=True)
    attribution.write_text(
        'IP Geolocation by DB-IP: https://db-ip.com\n'
        'DB-IP Country Lite, November 2026.\n'
        'Source: https://download.db-ip.com/free/dbip-country-lite-2026-11.csv.gz\n'
        'License: Creative Commons Attribution 4.0 International\n'
        'https://creativecommons.org/licenses/by/4.0/\n'
        'Converted to the six-column xt_geoip CSV and native binary ranges.\n',
        encoding='utf-8')
    inventory[notice] = (0o100644, 128, 'root', 'root')


def file_spec(name, record):
    mode, flags, user, group = record
    prefix = ['%%attr(%04o,%s,%s)' % (stat.S_IMODE(mode), user, group)]
    if stat.S_ISDIR(mode):
        prefix.append('%dir')
    if flags & 1:
        prefix.append('%config(noreplace)' if flags & 16 else '%config')
    if flags & 64:
        prefix.append('%ghost')
    if flags & 4096:
        prefix.append('%artifact')
    if flags & 128:
        prefix.append('%license')
    elif flags & 2:
        prefix.append('%doc')
    return ' '.join(prefix + [name])


def package_spec(rpm, inventory):
    dependencies = sorted(set(requires for requires in query(rpm, '--requires').splitlines()
                              if not requires.startswith('rpmlib(') and requires != '/bin/sh'))
    fields = [
        '%global debug_package %{nil}', '%global __os_install_post %{nil}',
        'Name: xtables-addons', 'Version: 3.18', 'Release: 1dkms.mytel.el8',
        'Summary: Xtables extensions with DB-IP Country Lite data',
        'License: GPL-2.0-or-later AND CC-BY-4.0',
        'URL: https://inai.de/projects/xtables-addons/',
        'Source0: xtables-prepared-payload.tar.gz',
        'Source1: xtables-addons-3.18.tar.xz',
        'Source2: xtables-addons-3.18-1dkms-vendor-source.tar.gz',
        'Source3: dbip-country-lite-2026-11.csv.gz',
        'AutoReqProv: no',
    ]
    fields.extend('Requires: ' + requirement for requirement in dependencies)
    fields.extend([
        '', '%description',
        'Xtables-addons 3.18 with the established kernel-module integration',
        'and DB-IP Country Lite data in the native country lookup format.',
        '', '%prep', '', '%build', '', '%install',
        'mkdir -p %{buildroot}',
        'tar -xzf %{SOURCE0} -C %{buildroot}',
        '', '%post -p /bin/sh', query(rpm, '--queryformat', '%{POSTIN}').strip(),
        '', '%preun -p /bin/sh', query(rpm, '--queryformat', '%{PREUN}').strip(),
        '', '%files',
    ])
    fields.extend(file_spec(name, record) for name, record in sorted(inventory.items()))
    return '\n'.join(fields) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_rpm', type=Path)
    parser.add_argument('country_data', type=Path)
    parser.add_argument('repo_source', type=Path)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args()
    rpm, data = args.original_rpm.resolve(), args.country_data.resolve()
    if digest(rpm) != ORIGINAL_SHA256 or digest(data) != DBIP_SHA256:
        raise ValueError('A reviewed source checksum differs')
    work = args.workspace.absolute()
    work.mkdir(mode=0o700)
    source = work / 'SOURCES'
    source.mkdir()
    specs = work / 'SPECS'
    specs.mkdir()
    tree = work / 'payload'
    inventory = payload_inventory(rpm)
    extract(rpm, tree)
    legacy, packed, expected = build_country_data(args.repo_source.resolve(), data, tree, work)
    update_payload(tree, inventory, legacy, packed)
    shutil.copyfile(data, source / 'dbip-country-lite-2026-11.csv.gz')
    subprocess.run([
        'tar', '-C', str(tree), '--format=ustar', '--sort=name', '--numeric-owner',
        '--owner=0', '--group=0', '--mtime=@' + REVISION,
        '-czf', str(source / 'xtables-prepared-payload.tar.gz'), '.',
    ], check=True)
    (specs / 'xtables-addons.spec').write_text(package_spec(rpm, inventory), encoding='utf-8')
    (work / 'country-data-verification.json').write_text(json.dumps(expected, sort_keys=True) + '\n', encoding='utf-8')
    print('DB-IP country layout verified for all {} packed files.'.format(len(expected['files'])))


if __name__ == '__main__':
    main()
