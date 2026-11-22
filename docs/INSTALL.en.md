# MytelPBX 7.7.0 revision 9 installation

Revision 9 uses tag `v7.7.0-r9`. The online installer runs in English and sets the
web panel to Persian from the first sign-in. The
[revision 3 record](releases/7.7.0/revision-3.md) covers the earlier release.

## Online installation

Use a **fresh Rocky Linux 8.10 Minimal x86_64 server**, root access, an interactive
console or SSH terminal, and working Internet access. To install the published revision, run:

```bash
curl -fsSL -o install-mytellpbx.sh https://github.com/DashSaman/MyTellPBX/releases/download/v7.7.0-r9/install-mytellpbx.sh && bash install-mytellpbx.sh
```

The script is downloaded to a file before Bash starts, so setup retains
the terminal. The bootstrap verifies the release bundle checksum before running
the pinned native installer. An existing PBX is refused; use scoped maintenance
for an installed or partly initialized server.

The native sequence includes:

1. MariaDB `root` and panel `admin` passwords and their confirmations.
2. Primary SIP driver choice. Enter selects PJSIP, or choose SIP.
3. Native repositories and OS update with terminal package progress.
4. Asterisk **20** and Community Realtime Block List (`issabel-packetbl`).
5. Native setup applies the confirmed passwords and selected SIP driver.
6. The shared Mytel branding/Desk add-on after native setup succeeds.
7. Native cleanup, an independent Desk doctor check, completion and **automatic
   reboot** on online success.

During startup the terminal reports elapsed time and pending services every 30 seconds.
Before changing the add-on state, a bounded 300-second wait checks the actual
Asterisk 20 CLI and MariaDB, httpd and Asterisk services. It neither restarts the
core nor replays initialization. An observed different Asterisk major is rejected;
unready services or CLI time out and stop the stage.

A failed checked stage stops subsequent stages and automatic reboot. Both
installation paths support Asterisk 20 only. Installation and call acceptance
are recorded separately in the release receipt.

## Passwords and private records

The online installer shows passwords as you type. Use `MYTEL_HIDE_PASSWORDS=1`
when running the script to turn off terminal echo. Choose passwords with ASCII
letters, digits and `. @ = _ ! -`. Passwords can be entered again if a confirmation differs.

Native service credentials are stored privately in `/etc/issabel.conf`. Keep that
file and recovery records private. The independent Desk administrator has a
separate root-only record at `/etc/myteldesk/initial-admin.txt`.

The terminal shows the current package, observed download and transaction counters,
and the result of each installation phase.

DNF updates the system in one transaction and resolves the base and PBX package sets
in two batches. In an interactive terminal, progress updates in place. During Desk
startup the installer reports database initialization when the service journal confirms it.
The PBX batch requests the core modules with their native minimum versions and
excludes the optional license manager, including as an indirect dependency.

## Panel, Desk and CPU VAD

After successful completion and reboot, open `https://<server-ip>/` and sign in as
`admin` with the password entered at setup. The pinned native generator
retains its existing-certificate guard and key/lifetime policy. When it generates
a new default certificate, its Organization is MytelPBX - Mytel.one and its SANs
include validated native DNS and assigned global-scope IPv4 addresses (including
LAN addresses). A self-signed default still needs explicit trust; prepare trusted
TLS for the deployment. Existing configured/custom certificates follow the unchanged native generation
guard.

MytelDesk is at `/MytellDesk/`. Choose **Panel account** to use an authorized native
panel account. The separate Desk administrator record is described above.

The add-on delegates to the pinned **MytelDesk 1.1.4** installer. The exact archive
hash and source identifiers are in [myteldesk-release.json](../installer/myteldesk-release.json).
Its dedicated runtime and CPU VAD dependencies are verified by the Desk installer
and `myteldesk doctor`; a service/model check does not establish SIP registration,
two-way audio or VAD on a recorded call. Configure valid SIP/WebRTC extensions,
trunks and recording/retention policy separately. New CEL HANGUP records can
provide the cause, dial status and source channel to Call History. Historical
calls without recorded CEL metadata continue to use CDR data.

Optional `MYTELL_DESK_PUBLIC_URL=https://pbx.example.com` selects the Desk origin
when set for the installation. It does not issue certificates or provision trunks.
See the [Desk/VAD guide](MYTELDESK_INSTALL_FA.md).

## Diagnosis and recovery

The online installer checks enabled DNF repositories and the Issabel
repositories it plans to configure before asking for passwords. It also
checks the Rocky repositories used later and the HTTPS download of the Remi
release RPM. After Remi is configured, the installer checks its repositories
before enabling PHP and installing packages.

For the nine enabled Issabel sources, DNF uses local metalink files containing
the SHA-256 of the repository index previously fetched over authenticated HTTPS.
It can use the vendor's alternate HTTP transport only for matching metadata.
Package signatures are required, including for the legacy repository. The public
signing keys ship in the checksum-verified installer bundle. A changed index
requires a newly reviewed snapshot. Active metadata transfers have a bounded
progress timeout, and a full installation reuses the verified metadata.

Run the same initial checks on a fresh server without starting installation
with `sudo bash install-mytellpbx.sh --check-repositories`. The console
lists each check and its result. Detailed DNF and download diagnostics are
under `repository-checks/` in the printed private workspace. A failed
required check stops the current stage. Retry once the reported repository
can serve valid metadata or packages again.

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

The installer downloads the PBX package snapshot from the versioned release in
DashSaman/MyTellPBX. It checks the archive size and SHA-256 before configuring
a local package source. DNF verifies the publisher signatures. Asterisk
20.12.0-3.mytel.el8 and framework 5.0.0-6 are included. Rocky Linux, EPEL, Remi
and the MytelDesk runtime dependencies still require Internet access.

The software installation includes MytelDesk and selects PJSIP by default.
Asterisk is built from the 20.12.0 sources and the distribution's module changes.
Third-party binary transcoders for Opus, SILK, Siren7 and Siren14 are optional
manufacturer downloads. Systems using the same supported codec on both legs
can pass through audio without transcoding. For a supported DAHDI card, obtain
its firmware archive from the manufacturer and run
`mytel-dahdi-firmware-install --install /path/to/original-archive.tar.gz` as root.
The importer checks the firmware against the packaged digest before writing it.

GeoIP uses the native upstream installation/data state; the Mytel page reports
that state without installing a separate GeoIP engine. Package, service, path and
database identifiers such as `issabel-*` remain unchanged for compatibility.
Visible product branding is **MytelPBX / Mytel.one**. PHP 7.4 is upstream end-of-life;
see [the third-party notices](../THIRD_PARTY_NOTICES.md).

## Owner-lab native ISO

The separate ISO uses the native **Asterisk 20** packages and installs the Community
Realtime Block List automatically. The licensed add-on group is omitted. At first
boot, the English console takes both passwords and their confirmations, then accepts
PJSIP by default or SIP as the primary driver. Setup applies the Persian defaults.
Within **native repo metadata**, only group/environment metadata, human labels
and its repository index are updated; non-group records and RPM bytes are
preserved. The ISO also includes Mytel boot/Anaconda presentation assets, the
sealed add-on depot. The guided console reports local package progress and keeps
full diagnostics in a private log. The root-protected completion marker is written
only after native initialization and the add-on complete;
`ConditionPathExists=!/var/lib/mytelpbx-native-addons/offline-complete` prevents
later firstboot invocations from rerunning native initialization and the add-on.

The ISO retains the vendor Kickstart storage policy, including `clearpart --all
--initlabel` and automatic ext4 partitioning. It is for the designated fresh lab
VM with dedicated disks. The historical cold UEFI installation of the earlier R4 ISO
completed native/password/add-on setup and passed its baseline: all four services,
Desk doctor, retained native Persian, normal CA/IP/date TLS and panel HTTP 200.
The real root-owned mode-0600 completion marker was created by the success hook;
no migration or manually created marker was used. One ordinary reboot passed:
native setup and add-ons were skipped, the single completion receipt remained,
and services, credentials, keys/certificates and owned metadata were preserved.
The earlier R3 guard migration/systemd-239 reboot proof and
BIOS20 media results retain their historical artifact/source scope. The ISO binary
stays on the owner's lab server. See the current [revision 3 record](releases/7.7.0/revision-3.md)
for the new image's acceptance status.

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
