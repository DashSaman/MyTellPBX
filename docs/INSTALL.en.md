# MytelPBX 7.7.0 candidate installation

This is a **release candidate**. The final bundle pin, published release assets
and lab acceptance must be recorded in the [7.7.0 verification receipt](releases/7.7.0/verification.md)
before this guide describes an accepted release. Commands below name the intended
`v7.7.0` assets; their presence here does not claim publication or runtime success.

## Online installation

Use a **fresh Rocky Linux 8.10 Minimal x86_64 server**, root access, an interactive
console or SSH terminal, and working Internet access. After the final release asset
is available, run:

```bash
curl -fsSL -o install-mytellpbx.sh https://github.com/DashSaman/MyTellPBX/releases/download/v7.7.0/install-mytellpbx.sh && bash install-mytellpbx.sh
```

The script is downloaded to a file before Bash starts, so native dialogs retain
the terminal. The bootstrap verifies the release bundle checksum before running
the pinned native installer. An existing PBX is refused; use scoped maintenance
for an installed or partly initialized server.

The native sequence includes:

1. Native language selection.
2. Asterisk **16, 18 or 20**, with **18 selected by default**.
3. Native optional package selection. Vendor licensed modules remain optional;
   choosing them is not a Mytel license or paid activation.
4. Native repositories, packages and post-install setup.
5. Native password dialogs through `issabel-admin-passwords --init`.
6. The shared Mytel branding/Desk add-on after native setup succeeds.
7. Native cleanup, completion and **automatic reboot** on online success.

A failed checked stage stops subsequent stages and automatic reboot. Version
availability follows the native selector; acceptance of each version and its
call paths is recorded separately in the release receipt.

## Passwords and private records

The native wizard has four password screens: MariaDB root password and its
confirmation, then panel `admin` password and its confirmation. Choose nonempty
passwords accepted by native validation. Its allowed characters are ASCII letters,
digits, spaces and `. @ = _ ! -`.

Native service credentials are stored privately in `/etc/issabel.conf`. Keep that
file and recovery records private. The independent Desk administrator has a
separate root-only record at `/etc/myteldesk/initial-admin.txt`.

The native optional completion prompt says that the core/password wizard has
completed and Mytel add-ons run next. That prompt is not a final product-health
or call-acceptance result.

## Panel, Desk and CPU VAD

After successful completion and reboot, open `https://<server-ip>/` and sign in as
`admin` with the password chosen in the native wizard. Web TLS follows the native
base; prepare trusted domain TLS for the deployment. The Mytel add-on does not
replace the base TLS policy.

MytelDesk is at `/MytellDesk/`. Choose **Panel account** to use an authorized native
panel account. The separate Desk administrator record is described above.

The add-on delegates to the pinned **MytelDesk 1.1.2** installer. The exact archive
hash and source identifiers are in [myteldesk-release.json](../installer/myteldesk-release.json).
Its dedicated runtime and CPU VAD dependencies are verified by the Desk installer
and `myteldesk doctor`; a service/model check does not establish SIP registration,
two-way audio or VAD on a recorded call. Configure valid SIP/WebRTC extensions,
trunks and recording/retention policy separately.

Optional `MYTELL_DESK_PUBLIC_URL=https://pbx.example.com` selects the Desk origin
when set for the installation. It does not issue certificates or provision trunks.
See the [Desk/VAD guide](MYTELDESK_INSTALL_FA.md).

## Diagnosis and recovery

The bootstrap prints a private workspace such as:

```text
/var/tmp/mytelpbx-native.XXXXXXXX/
```

The native log is `netinstall.log` within that workspace. Verified source and
logs are retained. The add-on prints its private recovery receipt; its backups
are under `/var/backups/mytellpbx/native-addons/`. Useful local checks include:

```bash
systemctl status httpd mariadb asterisk myteldesk
myteldesk doctor
```

For checksum or source-pin failure, preserve the downloaded files and compare
against the final release receipt. For a failure after native initialization,
preserve the PBX data, native credentials and add-on receipt for scoped recovery.
The base installer has no generic same-release stage-resume or unattended password
mode. Do not delete existing state to make the fresh-server guard pass.

## Network and upstream identities

The native base installs MariaDB, Apache, PHP 7.4 and the original PBX packages.
It **disables SELinux and firewalld**, following the supplied upstream installer.
Configure management, web, SIP and RTP access rules for the actual topology. The
usual ports below are planning references, not a claim that rules were installed:

| Port | Typical purpose |
|------|-----------------|
| 22 TCP | SSH management |
| 80/443 TCP | Web panel |
| 5060 TCP/UDP, 5061 TCP | SIP signaling, according to transport configuration |
| 10000–20000 UDP | RTP, according to Asterisk configuration |

Online package/release sources and Desk dependencies require network access.
GeoIP uses the native upstream installation/data state; the Mytel page reports
that state without installing a separate GeoIP engine. Package, service, path and
database identifiers such as `issabel-*` remain unchanged for compatibility.
Visible product branding is **MytelPBX / Mytel.one**. PHP 7.4 is upstream end-of-life;
see [the third-party notices](../THIRD_PARTY_NOTICES.md).

## Owner-lab native ISO

The separate ISO remasters the original **Issabel 5 ISO**, retaining its RPM bytes,
non-group repository metadata, `/installamp` trigger and native firstboot/password
command. The native **Software Selection** screen offers **MytelPBX with Asterisk
16, 18 or 20**. Open that screen from Installation Summary, select the version,
and finish the selection before beginning installation. The original **20 default**
remains available; it does not lock the choice.

The missing native 16 environment references the existing Asterisk 16 group;
existing package/group identifiers and optional `rbl`/`guru` choices remain intact.
Only the environment/human-label metadata and its repository index are updated.
The native firstboot success hook runs only the shared Mytel add-on after native
setup; it does not run another PBX core installer.

The ISO retains the vendor Kickstart storage policy, including `clearpart --all
--initlabel` and automatic ext4 partitioning. It is for the designated fresh lab
VM with dedicated disks. Its BIOS/UEFI boot and offline acceptance remain pending
the final receipt. The ISO binary stays in the owner's lab and is **not uploaded
to GitHub**.

The current builder is `scripts/remaster-vendor-iso.py`. On the authorized Linux
lab host, use the pinned original ISO and a verified sealed supplemental depot:

```bash
python3 scripts/remaster-vendor-iso.py \
  --source-iso /root/iso/issabel5-USB-DVD-x86_64-20261001.iso \
  --depot /path/to/sealed-mytel-media \
  --manifest-sha256 REPLACE_WITH_VERIFIED_MANIFEST_SHA256 \
  --work-dir /path/to/private-extra/native770-build \
  --output /root/iso/mytelpbx-7.7.0-native.iso --build
```

The explicit work directory must already be canonical, root-owned and private
(mode 0700), with enough space for image processing and native-depot readback.
Output must be a new file directly under `/root/iso`. The builder verifies the
source pin, sealed media, preserved native package bytes and output readback;
a successful build receipt is separate from a successful VM installation or call.
