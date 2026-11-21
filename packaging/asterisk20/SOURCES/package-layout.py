#!/usr/bin/env python3
"""Select, stage and verify the open-source modules from the native EL8 package layout."""
import argparse
from pathlib import Path
import os
import stat
import subprocess
import xml.etree.ElementTree as ET


MODULE_DIR = '/usr/lib64/asterisk/modules/'
VENDOR_CODECS = ('codec_opus', 'codec_silk', 'codec_siren7', 'codec_siren14')
PACKAGES = ('asterisk20', 'asterisk20-addons', 'asterisk20-addons-core', 'asterisk20-addons-bluetooth',
            'asterisk20-addons-mysql', 'asterisk20-addons-ooh323', 'asterisk20-core', 'asterisk20-configs',
            'asterisk20-dahdi', 'asterisk20-odbc', 'asterisk20-devel', 'asterisk20-doc', 'asterisk20-curl',
            'asterisk20-resample', 'asterisk20-voicemail')


def load_layout(path):
    rows = []
    for line in path.read_text().splitlines():
        if line.startswith('#'):
            continue
        package, target, mode, flags, user, group = line.split('\t')
        rows.append((package, target, int(mode, 8), int(flags), user, group))
    return rows


def modules(rows):
    return {Path(target).stem for _, target, _, _, _, _ in rows
            if target.startswith(MODULE_DIR) and target.endswith('.so')}


def select(rows):
    # Do not let menuselect introduce third-party download-only binaries.
    desired = modules(rows)
    tree = ET.parse('menuselect-tree')
    categories = ['MENUSELECT_CORE_SOUNDS', 'MENUSELECT_EXTRA_SOUNDS', 'MENUSELECT_MOH']
    options = set()
    for category in tree.findall('category'):
        name = category.get('name')
        entries = {item.get('name') for item in category.findall('member')}
        options.update(entries)
        if entries.intersection(desired):
            categories.append(name)
    missing = desired - options
    if missing:
        raise ValueError('Source tree lacks expected module targets: ' + ', '.join(sorted(missing)))
    args = ['menuselect/menuselect']
    for name in categories:
        args += ['--disable-category', name]
    for name in sorted(desired):
        args += ['--enable', name]
    args += ['--disable', 'BUILD_NATIVE', '--enable', 'DONT_OPTIMIZE', 'menuselect.makeopts']
    subprocess.run(args, check=True)
    subprocess.run(['menuselect/menuselect', '--check-deps', 'menuselect.makeopts'], check=True)


def prepare(rows, root, lists):
    # The publisher installs selected samples under .confnew so provisioning
    # can initialize live PBX settings without overriding the owner's choices.
    for _, target, _, _, _, _ in rows:
        if target.endswith('.confnew'):
            sample = root / target.lstrip('/')[:-3]
            installed = root / target.lstrip('/')
            if sample.is_file() and not installed.exists():
                sample.rename(installed)
    expected = set()
    missing = []
    filelists = {name: [] for name in PACKAGES}
    for package, target, mode, flags, user, group in rows:
        path = root / target.lstrip('/')
        record = []
        if stat.S_ISDIR(mode):
            path.mkdir(parents=True, exist_ok=True)
            record.append('%dir')
        elif not path.is_file() and not path.is_symlink():
            # brp-compress runs between %install and RPM file collection.
            if not (target.startswith('/usr/share/man/') and target.endswith('.gz') and path.with_suffix('').is_file()):
                missing.append(target)
        if flags & 1:
            record.append('%config(noreplace)' if flags & 16 else '%config')
        if flags & 2:
            record.append('%doc')
        if not stat.S_ISLNK(mode):
            record.append('%attr({:04o},{},{})'.format(stat.S_IMODE(mode), user, group))
        record.append(target)
        filelists[package].append(' '.join(record))
        expected.add(path)
        if target.startswith('/usr/share/man/') and target.endswith('.gz'):
            expected.add(path.with_suffix(''))
    if missing:
        raise ValueError('Missing native build outputs:\n' + '\n'.join(missing))
    for path in root.rglob('*'):
        if not (path.is_file() or path.is_symlink()) or path in expected:
            continue
        if path.parent == root / MODULE_DIR.strip('/') and path.suffix == '.so':
            raise ValueError('Unexpected compiled module: ' + path.name)
        # Keep the native runtime/devel file sets; leave test utilities and
        # unselected sample files outside the built binary packages.
        path.unlink()
    for name, lines in filelists.items():
        (lists / (name + '.files')).write_text('\n'.join(lines) + '\n')


def verify(rows, rpmroot):
    found = {}
    for path in rpmroot.rglob('*.rpm'):
        name = subprocess.check_output(['rpm', '-qp', '--qf', '%{NAME}', str(path)]).decode()
        if name not in PACKAGES:
            continue
        if name in found:
            raise ValueError('Duplicate runtime RPM: ' + name)
        found[name] = set(subprocess.check_output(['rpm', '-qpl', str(path)]).decode().splitlines())
    if set(found) != set(PACKAGES):
        raise ValueError('Missing native subpackages: ' + ', '.join(sorted(set(PACKAGES) - set(found))))
    for package in PACKAGES:
        expected = {path for name, path, _, _, _, _ in rows if name == package}
        actual = found[package]
        if not expected.issubset(actual):
            raise ValueError(package + ' missing:\n' + '\n'.join(sorted(expected - actual)))
        extra = {path for path in actual - expected if path.startswith(MODULE_DIR) and path.endswith('.so')}
        if extra:
            raise ValueError(package + ' unexpected modules: ' + ', '.join(sorted(extra)))
    print('Verified {} RPMs and {} compiled native modules.'.format(len(found), len(modules(rows))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['select', 'stage', 'verify'])
    parser.add_argument('layout', type=Path)
    parser.add_argument('paths', nargs='*', type=Path)
    args = parser.parse_args()
    layout = load_layout(args.layout)
    if args.action == 'select' and not args.paths:
        select(layout)
    elif args.action == 'stage' and len(args.paths) == 2:
        buildroot, lists = (path.resolve() for path in args.paths)
        if buildroot == Path('/') or not buildroot.is_dir() or not lists.is_dir():
            parser.error('Expected an isolated RPM buildroot and build directory')
        prepare(layout, buildroot, lists)
    elif args.action == 'verify' and len(args.paths) == 1:
        verify(layout, args.paths[0])
    else:
        parser.error('Unexpected positional arguments')
