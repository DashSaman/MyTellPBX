# MytelPBX offline installation ISO

The ISO installs a pure Rocky Linux8.10 Minimal system first. It stages verified
PBX media as files, then runs the ordinary fresh installer on the first real
systemd boot. PBX packages, databases and `install_amp` never run inside Anaconda's
chroot. Disk selection and the OS root password remain normal Anaconda choices;
there is no automatic disk erase or embedded default credential.

The firstboot console asks the normal two hidden panel/database passwords. A
failed run creates no completion receipt. On the next boot the same installer
resumes its owned stages and preserves saved credentials. A small vendor-unit
condition suppresses the redundant interactive Issabel firstboot only while the
real persistent MytelPBX media depot is present. It does not manufacture framework
stages, reset configuration or disable the native reload service.

## Inputs

Use the pinned `Rocky-8.10-x86_64-minimal.iso`:

```
SHA256 231d21db029e900b305d8e23ff7a61d06bb4e873cb170bd4a85f4e6dd896748f
bytes  3368943616
```

Provide a separately prepared, root-owned offline depot using `installer/media.py`
schema1: owner`MyTellPBX`, platform`rocky8.10-x86_64`, exact files hashes/sizes,
bootstrap/bundle/Desk/Node paths, the complete wheel set, GeoIP month/data, and local
GPG-checked RPM repositories. Every repository package, metadata file and public
key is in the locked manifest. PHP Remi module metadata and the installed kernel's
matching headers/devel must be included. The builder never invents missing files
or downloads dependencies. An ISO containing only the PBX bundle is not offline.

Prepare the depot with `scripts/collect-installer-media.py`; see
[offline media collection](OFFLINE_MEDIA_COLLECTION.md). Run it on disposable
Rocky Linux with empty private installroots. It performs no RPM transaction and
must retain all repository, package-signature and local-closure checks.

The reviewed `php-magpierss-0.72-3.fc17` package requires the legacy Elastix key.
In a **private copied** repository configuration, append the official HTTPS key
to `[issabel-updates]`'s `gpgkey` list while retaining its existing Issabel key:
`https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Elastix`.
Verify the full fingerprint `5EB0CFE0BC7459B15956A1B14BFE99F4D05C057C`;
keys belong only in the collector's private RPM database, not system trust.
Never disable GPG or TLS verification to complete collection.

The supported `--cache-dir` accepts licensed public cached assets. Bind cached
DB-IP data with `--geoip-sha256` and its actual `--geoip-month`; bind GeoNames
`countryInfo.txt` separately with `--country-info-sha256`. Retain both providers'
CC BY 4.0 attribution and the exact accepted file hashes in the depot manifest.
A DB-IP HTTP403 is a failed fetch, not evidence that its month is unpublished.
Use an independently verified available cache or stop; identify cached inputs
honestly rather than claiming a fresh download. Do not ignore the failed fetch.

The extracted native installer `.buildstamp` must match Rocky8.10,
UUID`202606221745.x86_64`, Lorax`28.14.71-1`. The product image preserves base
variant/configuration while adding MytelPBX graphics and the product name. Original
signed boot binaries and kernel/Stage2 remain unchanged; BIOS, visible UEFI and
embedded FAT boot configurations share the new volume label.

## Build on Linux

Required tools: Python3, `xorriso`, GNU`cpio`, `mtools` (`mdir`/`mcopy`),
`implantisomd5`, `checkisomd5` and librsvg's `rsvg-convert`. Root access is used for `/root/iso` and verified
root-owned input metadata. Keep the original ISO read-only.

The owned `installer/iso/boot-splash.svg` renders to a 640×480 PNG, matching the
pinned ISO's Syslinux screen. The builder checks the PNG header/dimensions and
rehashes its actual ISO copy. The square application logo is not a boot splash;
actual BIOS menu readability remains a boot acceptance check.

```
python3 scripts/build-installer-iso.py \
  --source-iso /root/iso/Rocky-8.10-x86_64-minimal.iso \
  --depot /path/to/verified-depot \
  --manifest-sha256 <locked-manifest-sha256> \
  --base-buildstamp /path/to/extracted-native.buildstamp \
  --output /root/iso/MytelPBX-<version>-x86_64.iso
```

The command above validates and prints a plan only. Add`--build` to produce the
ISO. The bootstrap version must equal repository`VERSION`, and its literal bundle
pin must match the depot. Outputs are exclusively under`/root/iso`; existing files
are never replaced. The ISO, companion hash and build manifest stay on that host
and are not GitHub release assets. The build manifest records source hashes and
`boot_acceptance:false`; building alone is not installation acceptance.

## Acceptance

Test the exact resulting SHA in disposable BIOS and UEFI VMs. Install with no
external network route, while retaining a host-only management path. Prove all
packages/assets resolve locally; two hidden product prompts; real chosen/negative
database and panel authentication; native service ownership/readiness; HTTPS and
separate DTLS; WSS and supported recording hook; GeoIP kernel/data readiness;
Save/Apply preservation; actual internal audio and automatic VAD; authenticated
recording-byte parity; reboot and same-source rerun preservation. A model CPU
doctor or an ISO media checksum is not a substitute for those checks. Record
actual supported versions and failures; do not infer Asterisk16/18/PSTN coverage.

The media cache persists after ejection for safe resume and offline maintenance.
Its GeoIP snapshot has an explicit month; refreshing an offline dataset requires
new verified media inputs. Online installation retains its separate network/update
behavior. No debug `-g` override or private lab SSH key is shipped in this ISO.
