#!/usr/bin/env python3
"""Rebrand the pinned native Issabel ISO and append sealed Mytel add-ons.

The original RPM depot, package groups, storage policy, /installamp trigger and
native firstboot/password initializer remain the installation engine. This is
not the former Rocky-plus-custom-core ISO builder. Build only on the Linux lab.
"""
import argparse
import bz2
import copy
import configparser
import gzip
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET

VENDOR_ISO_SHA256 = 'c63b7512d3ba05af645e144c58bf00c87353ddf2b3318e2fda8c262c057c07f9'
VENDOR_ISO_BYTES = 3682598912
VENDOR_LABEL = 'Issabel5-x86_64'
VENDOR_KS_SHA256 = '503a1d065d1382355553ca337d0ca99946970fe3c81eaa22c160728d1dbf390e'
VENDOR_COMPS_SHA256 = '1718aa060cb2b5d63df62e1efb8a47f2b4a16a3d757c623c42b2901974618a43'
VENDOR_OUTER_GRUB_SHA256 = 'e5f4765d89e5835b75d864763c1aaa3d29c831b2248a3ca004ab4bcd2a487414'
VENDOR_EMBEDDED_GRUB_SHA256 = '1cdcf9e23e018bb1cd2d1f39206392beba1ac3eb574cedb65eb337855618243b'
REPO_NS = '{http://linux.duke.edu/metadata/repo}'
GROUP_TYPES = {'group', 'group_gz'}
ONLINE_POST_LINES = (
    'chroot /mnt/sysimage dnf -y module enable php:remi-7.4\n',
    'chroot /mnt/sysimage dnf -y check-upgrade\n',
)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def command(args):
    result = subprocess.run([str(value) for value in args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(Path(str(args[0])).name + ' failed: ' + result.stderr.decode('utf-8', 'replace')[-2000:])
    return result.stdout


def extract(iso, member, target):
    command(['xorriso', '-osirrox', 'on', '-indev', iso, '-extract', '/' + member, target])


def kickstart(source):
    if hashlib.sha256(source.encode('utf-8')).hexdigest() != VENDOR_KS_SHA256:
        raise ValueError('Unknown native Issabel kickstart')
    result = source.replace('issabel.local', 'mytelpbx.local')
    for line in ONLINE_POST_LINES:
        if result.count(line) != 1:
            raise ValueError('Native offline post boundary changed')
        result = result.replace(line, '')
    return result.rstrip('\n') + '''
# MYTEL_NATIVE_ADDONS_BEGIN
# Native packages and /installamp above are unchanged. This only prepares a
# success-only post-firstboot add-on; no native initializer runs in this section.
%post --nochroot --erroronfail
set -euo pipefail
umask 077
target=/mnt/sysimage
source=/run/install/repo/mytelpbx
test -d "$target/etc"
test ! -e "$target/var/lib/mytelpbx-media"
test ! -L "$target/var/lib/mytelpbx-media"
install -d -m 0700 "$target/var/lib/mytelpbx-media"
cp -a "$source/depot/." "$target/var/lib/mytelpbx-media/"
install -d -m 0755 "$target/usr/local/libexec/mytelpbx"
install -m 0755 "$source/run-offline.sh" "$target/usr/local/libexec/mytelpbx/run-offline.sh"
install -m 0644 "$source/media.py" "$target/usr/local/libexec/mytelpbx/media.py"
install -m 0644 "$source/brand-native-dialogs.py" "$target/usr/local/libexec/mytelpbx/brand-native-dialogs.py"
install -m 0600 "$source/native-media.json" "$target/etc/mytelpbx-native-media.json"
install -d -m 0755 "$target/etc/systemd/system/issabel-firstboot.service.d"
install -m 0644 "$source/20-mytel-addons.conf" "$target/etc/systemd/system/issabel-firstboot.service.d/20-mytel-addons.conf"
# Native labels/startup guard and optional completion UX; core PHP --init stays intact.
chroot "$target" /usr/libexec/platform-python -I -S -B /usr/local/libexec/mytelpbx/brand-native-dialogs.py --tool passwords
chroot "$target" /usr/libexec/platform-python -I -S -B /usr/local/libexec/mytelpbx/brand-native-dialogs.py --tool completion
chroot "$target" /usr/libexec/platform-python -I -S -B /usr/local/libexec/mytelpbx/brand-native-dialogs.py --tool language
chroot "$target" /usr/libexec/platform-python -I -S -B /usr/local/libexec/mytelpbx/brand-native-dialogs.py --tool sip
chroot "$target" /usr/libexec/platform-python -I -S -B /usr/local/libexec/mytelpbx/brand-native-dialogs.py --tool certificate
# Validate sealed bytes before allowing installation to complete; no PBX action.
chroot "$target" /bin/bash /usr/local/libexec/mytelpbx/run-offline.sh --verify-media
%end
'''


def firstboot_dropin():
    # Native ExecStart changes back to VT1. Show add-on progress on its existing
    # TTY2 and retain that screen on failure. systemd runs this only after success.
    return ('[Service]\n'
            'ExecStartPost=/bin/bash -c "chvt 2 && /bin/bash /usr/local/libexec/mytelpbx/run-offline.sh && chvt 1"\n')


def boot_config(source, label, version):
    if VENDOR_LABEL not in source or '/ks/issabel.ks' not in source:
        raise ValueError('Unknown native boot configuration')
    result = source.replace(VENDOR_LABEL, label).replace('/ks/issabel.ks', '/ks/mytelpbx.ks')
    # The offline profile must not contact Fedora's geolocation service.
    # Keep native timezone/storage/package settings and all other boot options.
    result = result.replace(' inst.geoloc=provider_fedora_geoip', '')
    result = result.replace(' inst.geoloc-use-with-ks', '')
    if 'inst.geoloc' in result:
        raise ValueError('Unknown native geolocation option in offline boot configuration')
    result = result.replace('Issabel 5', 'MytelPBX ' + version + ' / Mytel.one')
    result = result.replace('Issabel', 'MytelPBX')
    if 'menu title MytelPBX' in result and 'Mytel.one' not in result:
        raise ValueError('Missing boot product attribution')
    return result


def buildstamp(source, version):
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(source)
    if (config.get('Main', 'Product') != 'Issabel' or config.get('Main', 'Version') != '5'
            or config.get('Main', 'UUID') != '2024.x86_64'
            or config.get('Compose', 'Lorax') != '28.14.71-1'):
        raise ValueError('Unknown native installer buildstamp')
    # Preserve the case used by the native Lorax reader.
    return (source.replace('Product=Issabel', 'Product=MytelPBX')
            .replace('Version=5\n', 'Version=' + version + '\n')
            .replace('BugURL=http://www.issabel.org', 'BugURL=https://mytel.one'))


def product_config():
    return ('[Product]\nproduct_name = MytelPBX\n\n'
            '[Base Product]\nproduct_name = Issabel\n\n'
            '[User Interface]\ncustom_stylesheet = /usr/share/anaconda/pixmaps/mytelpbx.css\n')


def debugfs_dump(image, name, target):
    command(['debugfs', '-R', 'dump -p /' + name + ' ' + str(target), image])
    if not target.is_file():
        raise ValueError('Missing native runtime file: ' + name)


def runtime_image(repo, source, stage, version):
    original = stage / 'original-install.img'
    extract(source, 'images/install.img', original)
    superblock = command(['unsquashfs', '-s', original]).decode('utf-8')
    compression = re.search(r'(?m)^Compression (\w+)\s*$', superblock)
    block = re.search(r'(?m)^Block size (\d+)\s*$', superblock)
    if not compression or not block or compression.group(1) not in ('xz', 'gzip', 'zstd', 'lzo', 'lz4'):
        raise ValueError('Unknown native squashfs format')
    squash = stage / 'squash'
    command(['unsquashfs', '-no-progress', '-d', squash, original])
    rootfs = squash / 'LiveOS/rootfs.img'
    if rootfs.is_symlink() or not rootfs.is_file():
        raise ValueError('Native LiveOS/rootfs.img missing')
    stamp = stage / 'native-buildstamp'
    policy = stage / 'native-issabel.conf'
    debugfs_dump(rootfs, '.buildstamp', stamp)
    debugfs_dump(rootfs, 'etc/anaconda/product.d/issabel.conf', policy)
    original_policy = policy.read_bytes()
    if b'product_name = Issabel' not in original_policy:
        raise ValueError('Native inherited Anaconda policy changed')
    patches = {
        '.buildstamp': buildstamp(stamp.read_text(encoding='utf-8'), version).encode(),
        'etc/anaconda/product.d/mytelpbx.conf': product_config().encode(),
        'usr/share/anaconda/pixmaps/mytelpbx.css': (repo / 'installer/iso/product/usr/share/anaconda/pixmaps/mytelpbx.css').read_bytes(),
        'usr/share/anaconda/pixmaps/mytelpbx-wordmark.svg': (repo / 'installer/iso/product/usr/share/anaconda/pixmaps/mytelpbx-wordmark.svg').read_bytes(),
    }
    for index, (name, data) in enumerate(patches.items()):
        asset = stage / ('runtime-patch-' + str(index))
        asset.write_bytes(data)
        command(['debugfs', '-w', '-R', 'rm /' + name, rootfs])
        command(['debugfs', '-w', '-R', 'write ' + str(asset) + ' /' + name, rootfs])
        command(['debugfs', '-w', '-R', 'set_inode_field /' + name + ' mode 0100644', rootfs])
        checked = stage / ('runtime-checked-' + str(index))
        debugfs_dump(rootfs, name, checked)
        if checked.read_bytes() != data:
            raise ValueError('Runtime display patch readback differs')
    preserved = stage / 'preserved-issabel.conf'
    debugfs_dump(rootfs, 'etc/anaconda/product.d/issabel.conf', preserved)
    if preserved.read_bytes() != original_policy:
        raise ValueError('Native inherited Anaconda policy was modified')
    command(['e2fsck', '-f', '-n', rootfs])
    output = stage / 'install.img'
    command(['mksquashfs', squash, output, '-noappend', '-comp', compression.group(1),
             '-b', block.group(1), '-processors', '2', '-no-progress'])
    return output, {name: hashlib.sha256(data).hexdigest() for name, data in patches.items()}


def efi_image(source, stage, label, version, splash):
    image = stage / 'efiboot.img'
    extract(source, 'images/efiboot.img', image)
    listing = command(['mdir', '-i', image, '-b', '-/', '::']).decode('utf-8')
    paths = [path.strip() for path in listing.splitlines() if path.strip()]
    configs = [path for path in paths if path.lower().endswith(('.cfg', '.conf'))]
    expected = {'::/efi/boot/grub.cfg', '::/efi/boot/boot.conf'}
    if len(configs) != 2 or {path.lower() for path in configs} != expected:
        raise ValueError('Unknown or incomplete embedded EFI configuration pair')
    outer = stage / 'native-outer-efi.cfg'
    extract(source, 'EFI/BOOT/grub.cfg', outer)
    if digest(outer) != VENDOR_OUTER_GRUB_SHA256:
        raise ValueError('Pinned outer native EFI configuration changed')
    replacement = boot_config(outer.read_text(encoding='utf-8'), label, version).encode('utf-8')
    checked_configs = []
    for index, path in enumerate(configs):
        config = stage / ('efi-config-' + str(index))
        command(['mcopy', '-i', image, path, config])
        if digest(config) != VENDOR_EMBEDDED_GRUB_SHA256:
            raise ValueError('Unknown embedded EFI configuration bytes: ' + path)
        checked_configs.append((path, config))
    # This exact original FAT pair has a stale Rocky menu without the vendor KS.
    # Derive both from the pinned outer native menu; never reinterpret unknown input.
    binaries = {}
    for index, path in enumerate(path for path in paths if path.lower().endswith('.efi')):
        if not path.startswith('::/') or '..' in path:
            raise ValueError('Unknown embedded EFI binary path')
        binary = stage / ('efi-binary-before-' + str(index))
        command(['mcopy', '-i', image, path, binary])
        binaries[path] = digest(binary)
    for path, config in checked_configs:
        config.write_bytes(replacement)
        command(['mcopy', '-o', '-i', image, config, path])
    for path in paths:
        if path.lower() == '::/efi/boot/splash.png':
            command(['mcopy', '-o', '-i', image, splash, path])
    for index, (path, _config) in enumerate(checked_configs):
        actual = stage / ('efi-config-readback-' + str(index))
        command(['mcopy', '-i', image, path, actual])
        if actual.read_bytes() != replacement:
            raise ValueError('Embedded EFI configuration readback differs: ' + path)
    for index, (path, checksum) in enumerate(binaries.items()):
        actual = stage / ('efi-binary-after-' + str(index))
        command(['mcopy', '-i', image, path, actual])
        if digest(actual) != checksum:
            raise ValueError('Native EFI binary changed: ' + path)
    return image, len(checked_configs)


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            result[relative] = {'link': os.readlink(str(path))}
        elif stat.S_ISREG(info.st_mode):
            result[relative] = {'bytes': info.st_size, 'sha256': digest(path)}
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError('Unexpected native payload member')
    return result


def xml_structure(node, omit_labels=False):
    """Compare metadata values without XML namespace-prefix/formatting noise."""
    children = tuple(xml_structure(child, omit_labels) for child in node
                     if not (omit_labels and child.tag in ('name', 'description')))
    return node.tag, tuple(sorted(node.attrib.items())), (node.text or '').strip(), children


def comps_blocks(source):
    comments = [(match.start(), match.end()) for match in re.finditer(r'<!--.*?-->', source, re.S)]
    return [match for match in re.finditer(r'(?ms)^[ \t]*<(group|environment)>\n.*?^[ \t]*</\1>', source)
            if not any(start <= match.start() < end for start, end in comments)]


def derive_comps(original, available_package_names):
    """Add only missing environment16 and human branding to exact native comps."""
    if hashlib.sha256(original).hexdigest() != VENDOR_COMPS_SHA256:
        raise ValueError('Unknown native comps source')
    before = ET.fromstring(original)
    groups = {node.findtext('id'): node for node in before.findall('group')}
    environments = {node.findtext('id'): node for node in before.findall('environment')}
    if set(environments) != {'issabelast20', 'issabelast18'}:
        raise ValueError('Unexpected native Asterisk environments')
    for major in ('16', '18', '20'):
        group = groups.get('asterisk' + major)
        if group is None:
            raise ValueError('Native Asterisk group missing; no synthetic group is authorized')
        required = {item.text for item in group.findall('packagelist/packagereq')
                    if item.get('type') == 'mandatory'}
        missing = required - set(available_package_names)
        if not required or missing:
            raise ValueError('Original ISO lacks Asterisk ' + major + ' packages: ' + ', '.join(sorted(missing)))
    source = original.decode('utf-8')
    blocks = comps_blocks(source)
    if len(blocks) != len(groups) + len(environments):
        raise ValueError('Unknown native comps layout')
    template = next(match.group(0) for match in blocks
                    if ET.fromstring(match.group(0)).findtext('id') == 'issabelast18')
    environment16 = (template.replace('<id>issabelast18</id>', '<id>issabelast16</id>')
                     .replace('<groupid>asterisk18</groupid>', '<groupid>asterisk16</groupid>')
                     .replace('Asterisk 18', 'Asterisk 16')
                     .replace('<display_order>2</display_order>', '<display_order>3</display_order>'))
    source = source.replace('</comps>', environment16 + '\n</comps>')
    neutral_names = {
        'guru': 'Optional upstream licensed add-ons',
        'rbl': 'Community RBL (Realtime Blackhole List)',
        'contactcenter': 'Upstream Contact Center -DEMO-',
    }
    def brand_block(match):
        block = match.group(0)
        identity = ET.fromstring(block).findtext('id')
        def label(item):
            tag, attributes, value = item.group(1), item.group(2) or '', item.group(3)
            if tag == 'name' and identity in neutral_names:
                value = neutral_names[identity]
            else:
                value = value.replace('Issabel', 'MytelPBX')
            return '<' + tag + attributes + '>' + value + '</' + tag + '>'
        return re.sub(r'<(name|description)(\s+[^>]*)?>(.*?)</\1>', label, block, flags=re.S)
    for block in reversed(comps_blocks(source)):
        source = source[:block.start()] + brand_block(block) + source[block.end():]
    result = source.encode('utf-8')
    after = ET.fromstring(result)
    after_groups = {node.findtext('id'): node for node in after.findall('group')}
    after_environments = {node.findtext('id'): node for node in after.findall('environment')}
    if set(after_groups) != set(groups) or set(after_environments) != set(environments) | {'issabelast16'}:
        raise ValueError('Native comps identities changed')
    for identity, node in list(groups.items()) + list(environments.items()):
        actual = (after_groups if identity in groups else after_environments)[identity]
        if xml_structure(node, True) != xml_structure(actual, True):
            raise ValueError('Native group/environment data changed: ' + identity)
    expected16 = copy.deepcopy(environments['issabelast18'])
    expected16.find('id').text = 'issabelast16'
    expected16.find('display_order').text = '3'
    for group in expected16.findall('grouplist/groupid'):
        if group.text == 'asterisk18':
            group.text = 'asterisk16'
    if xml_structure(expected16, True) != xml_structure(after_environments['issabelast16'], True):
        raise ValueError('Asterisk 16 environment differs from the native template')
    if any('issabel' in (node.text or '').lower()
           for item in after for node in item if node.tag in ('name', 'description')):
        raise ValueError('Unbranded native human label remains')
    return result


def uncompressed_metadata(raw):
    if raw.startswith(b'\x1f\x8b'):
        return gzip.decompress(raw)
    if raw.startswith(b'BZh'):
        return bz2.decompress(raw)
    if raw.startswith(b'\xfd7zXZ\x00'):
        return lzma.decompress(raw)
    return raw


def repository_records(repodata):
    repodata = Path(repodata).absolute()
    if repodata.resolve() != repodata or not repodata.is_dir():
        raise ValueError('Noncanonical repodata directory')
    index = repodata / 'repomd.xml'
    if index.is_symlink() or not index.is_file():
        raise ValueError('Invalid repomd index')
    root = ET.fromstring(index.read_bytes())
    if (root.tag != REPO_NS + 'repomd' or any('{http://www.w3.org/XML/1998/namespace}base' in node.attrib
                                            for node in root.iter())):
        raise ValueError('Unknown repository index or XML base URI')
    records, paths = {}, set()
    for record in root.findall(REPO_NS + 'data'):
        kind = record.get('type')
        locations = record.findall(REPO_NS + 'location')
        if (not kind or kind in records or len(locations) != 1
                or set(locations[0].attrib) != {'href'}):
            raise ValueError('Duplicate or missing repository metadata identity')
        href = locations[0].get('href', '')
        relative = PurePosixPath(href)
        if (str(relative) != href or len(relative.parts) != 2 or relative.parts[0] != 'repodata'
                or not re.fullmatch(r'[A-Za-z0-9_.+-]+', relative.parts[1])
                or relative.parts[1] in ('.', '..') or href in paths):
            raise ValueError('Unsafe or duplicate metadata location')
        paths.add(href)
        path = repodata / relative.parts[1]
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024 * 1024:
            raise ValueError('Missing or unsafe repository metadata file')
        raw = path.read_bytes()
        checksum = record.find(REPO_NS + 'checksum')
        algorithm = checksum.get('type', '') if checksum is not None else ''
        if algorithm == 'sha':
            algorithm = 'sha1'
        if (checksum is None or hashlib.new(algorithm, raw).hexdigest() != checksum.text
                or int(record.findtext(REPO_NS + 'size', '-1')) != len(raw)):
            raise ValueError('Repository metadata checksum/size differs: ' + kind)
        opened = uncompressed_metadata(raw)
        open_checksum = record.find(REPO_NS + 'open-checksum')
        if open_checksum is not None and hashlib.new(open_checksum.get('type', ''), opened).hexdigest() != open_checksum.text:
            raise ValueError('Repository open-checksum differs: ' + kind)
        open_size = record.findtext(REPO_NS + 'open-size')
        if open_size is not None and int(open_size) != len(opened):
            raise ValueError('Repository open-size differs: ' + kind)
        if kind == 'group' and opened != raw:
            raise ValueError('Native group metadata must stay uncompressed')
        if kind == 'group_gz' and (not raw.startswith(b'\x1f\x8b')
                                   or open_checksum is None or open_size is None):
            raise ValueError('Native group_gz format/open integrity fields changed')
        records[kind] = {'node': record, 'filename': relative.parts[1], 'raw': raw,
                         'open': opened, 'sha256': hashlib.sha256(raw).hexdigest()}
    if not records or not GROUP_TYPES.issubset(records):
        raise ValueError('Native group and group_gz records are required')
    return records


def verify_repository_delta(before, after, expected_comps):
    original, modified = repository_records(before), repository_records(after)
    if set(original) != set(modified):
        raise ValueError('Repository metadata types changed')
    allowed = {'repomd.xml'}
    for kind in original:
        if kind in GROUP_TYPES:
            allowed.update((original[kind]['filename'], modified[kind]['filename']))
            if modified[kind]['open'] != expected_comps:
                raise ValueError('Stale or unexpected comps variant: ' + kind)
        elif (record_identity(original[kind]['node']) != record_identity(modified[kind]['node'])
              or original[kind]['sha256'] != modified[kind]['sha256']):
            raise ValueError('Protected metadata changed: ' + kind)
    old_inventory, new_inventory = inventory(Path(before)), inventory(Path(after))
    changed = {name for name in set(old_inventory) | set(new_inventory)
               if old_inventory.get(name) != new_inventory.get(name)}
    if not changed or not changed.issubset(allowed):
        raise ValueError('Unlisted repository changes outside comps/repomd')
    return {name: new_inventory.get(name) for name in sorted(changed)}


def record_identity(record):
    structure = xml_structure(record)
    return structure[:3] + (tuple(sorted(structure[3])),)


def prepare_native_choices(source, stage):
    before, after = stage / 'before-repodata', stage / 'choice-repodata'
    extract(source, 'repodata', before)
    shutil.copytree(str(before), str(after))
    records = repository_records(before)
    if records['group']['open'] != records['group_gz']['open']:
        raise ValueError('Original native comps variants differ')
    primary = ET.fromstring(records['primary']['open'])
    namespace = '{http://linux.duke.edu/metadata/common}'
    names = {node.findtext(namespace + 'name') for node in primary.findall(namespace + 'package')}
    if not names or None in names:
        raise ValueError('Original native primary package inventory is invalid')
    result = derive_comps(records['group']['open'], names)
    comps = stage / 'mytel-native-comps.xml'
    comps.write_bytes(result)
    batch = stage / 'native-comps.batch'
    batch.write_text('[mytel-native-group]\npath=' + str(comps) + '\ntype=group\ncompress=false\n'
                     'checksum=sha256\nunique-md-filenames=true\nnew-name=comps.xml\n\n'
                     '[mytel-native-group-gz]\npath=' + str(comps) + '\ntype=group_gz\ncompress=true\n'
                     'compress-type=gz\nchecksum=sha256\nunique-md-filenames=true\nnew-name=comps.xml\n', encoding='utf-8')
    command(['modifyrepo_c', '--batchfile', batch, after])
    changes = verify_repository_delta(before, after, result)
    return after, result, changes


def bundle_member(archive, version, name):
    expected = 'mytelpbx-bundle-' + version + '/' + name
    with tarfile.open(archive, 'r:gz') as source:
        members = [member for member in source if member.name == expected]
        if len(members) != 1 or not members[0].isfile() or members[0].size > 1024 * 1024:
            raise ValueError('Missing or ambiguous bundle helper: ' + name)
        return source.extractfile(members[0]).read()


def work_directory(value, default):
    path = Path(value).absolute() if value else default
    if path.resolve() != path or not path.is_dir():
        raise ValueError('Work directory must be an existing canonical directory')
    for item in (path,) + tuple(path.parents):
        info = item.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022):
            raise ValueError('Work directory ancestry must be owned by root and not writable by others')
    if value and path.stat().st_mode & 0o077:
        raise ValueError('Explicit work directory must be private (0700)')
    return path


def publish_candidate(candidate, output, expected_sha256):
    # Staging may live on another filesystem. Copy into an exclusive private
    # file beside the output, fsync and hash it, then publish by no-overwrite link.
    fd, name = tempfile.mkstemp(prefix='.mytel-native-output-', suffix='.iso', dir=str(output.parent))
    temporary = Path(name)
    try:
        checksum = hashlib.sha256()
        with os.fdopen(fd, 'wb') as outgoing, candidate.open('rb') as incoming:
            for block in iter(lambda: incoming.read(1024 * 1024), b''):
                outgoing.write(block)
                checksum.update(block)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if checksum.hexdigest() != expected_sha256 or digest(temporary) != expected_sha256:
            raise ValueError('Output candidate copy changed')
        temporary.chmod(0o644)
        os.link(str(temporary), str(output))
        if os.name == 'posix':
            directory_fd = os.open(str(output.parent), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        candidate.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()


def plan(args):
    repo = Path(args.repo).resolve()
    source = Path(args.source_iso).absolute()
    if (source.is_symlink() or not source.is_file() or source.stat().st_size != VENDOR_ISO_BYTES
            or VENDOR_ISO_SHA256 == '0' * 64 or digest(source) != VENDOR_ISO_SHA256):
        raise ValueError('Pinned native Issabel ISO differs or source pin is not configured')
    helpers = load('iso_output_helpers', repo / 'scripts/build-installer-iso.py')
    output = helpers.output_path(args.output)
    for path in (output, output.with_suffix('.iso.json'), output.with_suffix('.iso.sha256')):
        if path.exists() or path.is_symlink():
            raise FileExistsError('An output already exists')
    version = (repo / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Invalid release version')
    label = 'MytelPBX-' + version + '-x86_64'
    if len(label) > 32:
        raise ValueError('ISO label too long')
    media = load('supplemental_media', repo / 'installer/media.py').load(Path(args.depot).resolve(), args.manifest_sha256)
    bootstrap = media.asset('bootstrap').read_bytes()
    bundle_sha = media.manifest['files'][media.manifest['bundle']]['sha256']
    if (bootstrap.count(('MYTELLPBX_BUNDLE_SHA256="' + bundle_sha + '"').encode()) != 1
            or re.findall(rb'(?m)^MYTELLPBX_VERSION="([0-9.]+)"$', bootstrap) != [version.encode()]):
        raise ValueError('Supplemental bootstrap/bundle/version mismatch')
    return repo, source, output, version, label, media, helpers


def build(args):
    if os.name != 'posix' or os.geteuid() != 0:
        raise ValueError('Build on the Linux root lab host')
    repo, source, output, version, label, media, helpers = plan(args)
    for tool in ('xorriso', 'unsquashfs', 'mksquashfs', 'debugfs', 'e2fsck', 'mdir', 'mcopy',
                 'implantisomd5', 'checkisomd5', 'rsvg-convert', 'modifyrepo_c'):
        if not shutil.which(tool):
            raise ValueError('Required build tool missing: ' + tool)
    scratch = work_directory(args.work_dir, output.parent)
    with tempfile.TemporaryDirectory(prefix='.mytel-native-iso-', dir=str(scratch)) as directory:
        stage = Path(directory)
        choice_repodata, choice_comps, _metadata_changes = prepare_native_choices(source, stage)
        payload = stage / 'mytelpbx'
        payload.mkdir()
        # Only these validated helper bytes are copied into Anaconda's target.
        for name, relative in [('run-offline.sh', 'installer/vendor-native/run-offline.sh'),
                               ('brand-native-dialogs.py', 'installer/vendor-native/brand-native-dialogs.py'),
                               ('media.py', 'installer/media.py')]:
            raw = bundle_member(media.asset('bundle'), version, relative)
            if raw != (repo / relative).read_bytes():
                raise ValueError('Bundled and reviewed helper differ: ' + relative)
            (payload / name).write_bytes(raw)
        configuration = {'schema': 1, 'root': '/var/lib/mytelpbx-media',
                         'manifest_sha256': args.manifest_sha256,
                         'validator_sha256': digest(payload / 'media.py')}
        (payload / 'native-media.json').write_text(json.dumps(configuration, sort_keys=True) + '\n', encoding='utf-8')
        (payload / '20-mytel-addons.conf').write_text(firstboot_dropin(), encoding='utf-8')
        ks = stage / 'mytelpbx.ks'
        extract(source, 'ks/issabel.ks', ks)
        ks.write_text(kickstart(ks.read_text(encoding='utf-8')), encoding='utf-8')
        bios, grub = stage / 'isolinux.cfg', stage / 'grub.cfg'
        extract(source, 'isolinux/isolinux.cfg', bios)
        extract(source, 'EFI/BOOT/grub.cfg', grub)
        for path in (bios, grub):
            path.write_text(boot_config(path.read_text(encoding='utf-8'), label, version), encoding='utf-8')
        splash = helpers.boot_splash(repo, stage)
        efi, efi_count = efi_image(source, stage, label, version, splash)
        runtime, runtime_hashes = runtime_image(repo, source, stage, version)
        discinfo = stage / 'discinfo'
        extract(source, '.discinfo', discinfo)
        disc_lines = discinfo.read_text().splitlines()
        if len(disc_lines) != 4 or disc_lines[1] != 'Rocky Linux 8.10' or disc_lines[2] != 'x86_64':
            raise ValueError('Unknown native disc identity')
        disc_lines[1] = 'MytelPBX ' + version
        discinfo.write_text('\n'.join(disc_lines) + '\n', encoding='utf-8')
        media_repo = stage / 'media.repo'
        extract(source, 'media.repo', media_repo)
        text = media_repo.read_text()
        if text.count('name=Rocky Linux 8.10') != 1:
            raise ValueError('Unknown native media repository')
        media_repo.write_text(text.replace('name=Rocky Linux 8.10', 'name=MytelPBX ' + version), encoding='utf-8')
        boot_message = stage / 'boot.msg'
        boot_message.write_text('MytelPBX ' + version + ' - Mytel.one\nPress ENTER to begin the native installation.\n', encoding='ascii')
        candidate = stage / 'candidate.iso'
        args_map = ['xorriso', '-indev', source, '-outdev', candidate, '-volid', label,
                    '-map', payload, '/mytelpbx', '-map', media.root, '/mytelpbx/depot',
                    '-map', choice_repodata, '/repodata',
                    '-map', ks, '/ks/mytelpbx.ks', '-map', bios, '/isolinux/isolinux.cfg',
                    '-map', grub, '/EFI/BOOT/grub.cfg', '-map', splash, '/isolinux/splash.png',
                    '-map', splash, '/EFI/BOOT/splash.png', '-map', efi, '/images/efiboot.img',
                    '-map', runtime, '/images/install.img', '-map', discinfo, '/.discinfo',
                    '-map', media_repo, '/media.repo', '-map', boot_message, '/isolinux/boot.msg',
                    '-boot_image', 'any', 'replay']
        print('MytelPBX: writing native ISO with unchanged Issabel RPM depot', flush=True)
        command(args_map)
        command(['implantisomd5', '--force', candidate])
        command(['checkisomd5', candidate])
        # Strong preservation check: every original RPM stays byte-identical;
        # metadata may differ only in the explicitly derived comps and repomd.
        native_inventory = {}
        for name in ('Issabel',):
            before, after = stage / ('before-' + name), stage / ('after-' + name)
            extract(source, name, before)
            extract(candidate, name, after)
            original_files = inventory(before)
            if original_files != inventory(after):
                raise ValueError('Native depot or metadata changed: ' + name)
            native_inventory[name] = original_files
        checked_repodata = stage / 'after-repodata'
        extract(candidate, 'repodata', checked_repodata)
        actual_changes = verify_repository_delta(stage / 'before-repodata', checked_repodata, choice_comps)
        if ((checked_repodata / 'repomd.xml').read_bytes()
                != (choice_repodata / 'repomd.xml').read_bytes()):
            raise ValueError('ISO repomd readback differs from validated choices')
        native_inventory['repodata'] = inventory(stage / 'before-repodata')
        for name in ('modules.yaml', 'LICENSE'):
            before, after = stage / ('before-' + name), stage / ('after-' + name)
            extract(source, name, before)
            extract(candidate, name, after)
            if digest(before) != digest(after):
                raise ValueError('Native payload changed: ' + name)
        readback = stage / 'checked-depot'
        extract(candidate, 'mytelpbx/depot', readback)
        load('remastered_media', repo / 'installer/media.py').load(readback, args.manifest_sha256)
        for name, original in [('ks/mytelpbx.ks', ks), ('isolinux/isolinux.cfg', bios),
                               ('EFI/BOOT/grub.cfg', grub), ('images/install.img', runtime),
                               ('images/efiboot.img', efi)]:
            actual = stage / ('checked-' + name.replace('/', '-'))
            extract(candidate, name, actual)
            if digest(actual) != digest(original):
                raise ValueError('Remastered display/handoff readback differs')
        if digest(source) != VENDOR_ISO_SHA256:
            raise ValueError('Source ISO changed during build')
        receipt = {'schema': 1, 'product': 'MytelPBX', 'version': version, 'label': label,
                   'source_iso_sha256': VENDOR_ISO_SHA256, 'iso_sha256': digest(candidate),
                   'iso_bytes': candidate.stat().st_size, 'media_manifest_sha256': args.manifest_sha256,
                   'native_engine': 'issabel-original-iso-firstboot', 'native_packages_preserved': True,
                   'native_non_group_metadata_preserved': True,
                   'native_asterisk_choices': ['16', '18', '20'], 'native_asterisk_default': '20',
                   'native_comps_sha256': hashlib.sha256(choice_comps).hexdigest(),
                   'native_metadata_changes': actual_changes,
                   'native_inventory_sha256': hashlib.sha256(json.dumps(native_inventory, sort_keys=True).encode()).hexdigest(),
                   'native_files': sum(len(value) for value in native_inventory.values()),
                   'runtime_display_files': runtime_hashes, 'embedded_efi_configs': efi_count,
                   'success_hook': 'issabel-firstboot.service ExecStartPost', 'boot_acceptance': False}
        publish_candidate(candidate, output, receipt['iso_sha256'])
        with output.with_suffix('.iso.json').open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
        with output.with_suffix('.iso.sha256').open('x', encoding='ascii') as stream:
            stream.write(receipt['iso_sha256'] + '  ' + output.name + '\n')
    print(json.dumps(receipt, sort_keys=True))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--source-iso', required=True)
    parser.add_argument('--depot', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--work-dir', help='Existing root-owned private staging directory, possibly on another filesystem')
    parser.add_argument('--build', action='store_true')
    args = parser.parse_args()
    if args.build:
        return build(args)
    _repo, _source, output, version, label, media, _helpers = plan(args)
    print(json.dumps({'plan_only': True, 'output': str(output), 'version': version,
                      'label': label, 'supplemental_files': len(media.manifest['files']),
                      'engine': 'issabel-native-iso'}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        raise SystemExit('MytelPBX native remaster refused: ' + str(error))
