#!/usr/bin/env python3
"""Rebrand the pinned native Issabel ISO and append sealed Mytel add-ons.

The original RPM depot, package groups, storage policy, /installamp trigger and
native firstboot/password initializer remain the installation engine. This is
not the former Rocky-plus-custom-core ISO builder. Build only on the Linux lab.
"""
import argparse
import configparser
import hashlib
import importlib.util
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

VENDOR_ISO_SHA256 = '0000000000000000000000000000000000000000000000000000000000000000'
VENDOR_ISO_BYTES = 3682598912
VENDOR_LABEL = 'Issabel5-x86_64'
VENDOR_KS_SHA256 = '503a1d065d1382355553ca337d0ca99946970fe3c81eaa22c160728d1dbf390e'
ONLINE_POST_LINES = (
    'chroot /mnt/sysimage dnf -y module enable php:remi-7.4\n',
    'chroot /mnt/sysimage dnf -y config-manager --set-enabled remi\n',
    'chroot /mnt/sysimage dnf -y config-manager --set-enabled powertools\n',
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
# Display labels only; the vendor PHP program and its native --init stay intact.
chroot "$target" /usr/libexec/platform-python -I -S -B /usr/local/libexec/mytelpbx/brand-native-dialogs.py --tool passwords
chroot "$target" /usr/libexec/platform-python -I -S -B /usr/local/libexec/mytelpbx/brand-native-dialogs.py --tool completion
chroot "$target" /usr/libexec/platform-python -I -S -B /usr/local/libexec/mytelpbx/brand-native-dialogs.py --tool language
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
    count = 0
    for index, path in enumerate(listing.splitlines()):
        path = path.strip()
        if not path.lower().endswith('/grub.cfg'):
            continue
        if not path.startswith('::/') or '..' in path:
            raise ValueError('Unknown embedded EFI path')
        config = stage / ('efi-config-' + str(index))
        command(['mcopy', '-i', image, path, config])
        config.write_text(boot_config(config.read_text(encoding='utf-8'), label, version), encoding='utf-8')
        command(['mcopy', '-o', '-i', image, config, path])
        count += 1
    for path in listing.splitlines():
        if path.strip().lower() == '::/efi/boot/splash.png':
            command(['mcopy', '-o', '-i', image, splash, path.strip()])
    if not count:
        raise ValueError('No native embedded EFI boot configuration found')
    return image, count


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
                 'implantisomd5', 'checkisomd5', 'rsvg-convert'):
        if not shutil.which(tool):
            raise ValueError('Required build tool missing: ' + tool)
    scratch = work_directory(args.work_dir, output.parent)
    with tempfile.TemporaryDirectory(prefix='.mytel-native-iso-', dir=str(scratch)) as directory:
        stage = Path(directory)
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
        # Strong preservation check: compare every original package and native
        # repository-metadata byte, not merely the build command's return code.
        native_inventory = {}
        for name in ('Issabel', 'repodata'):
            before, after = stage / ('before-' + name), stage / ('after-' + name)
            extract(source, name, before)
            extract(candidate, name, after)
            original_files = inventory(before)
            if original_files != inventory(after):
                raise ValueError('Native depot or metadata changed: ' + name)
            native_inventory[name] = original_files
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
