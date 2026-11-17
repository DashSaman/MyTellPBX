# MytelPBX 7.6.2 installation

## One-line install

Use a **fresh Rocky Linux 8.10 x86_64 server**, root access, an interactive terminal
and working Internet access to the official package repositories and release assets:

```bash
curl -fsSL -o install-mytellpbx.sh https://github.com/DashSaman/MyTellPBX/releases/download/v7.6.2/install-mytellpbx.sh && bash install-mytellpbx.sh
```

The download URL is pinned to `v7.6.2`. The installer verifies its payload checksum
before using it. Read [the current verification limits](releases/7.6.2/verification.md)
before deployment; a complete final cold-install or real call-media pass is not claimed.

## Requirements and scope

- Rocky Linux 8.10 exactly, x86_64; Minimal is suitable.
- A fresh server with no existing PBX installation.
- Root access and HTTPS access to package repositories, GitHub, nodejs.org,
  files.pythonhosted.org and the country-data providers.
- The preflight floors are 8 GB free disk and approximately 1.5 GB RAM. These floors
  are not a capacity guarantee for Desk/VAD or production call load.
- The full installer supplies **Asterisk 20 only**. Current Asterisk 16/18 runtime
  and media acceptance are not verified by this release.

The installed components include MariaDB, Apache, PHP 7.4, the native PBX modules,
the Mytel panel/admin theme and pinned MytelDesk 1.1.2. The panel/desk navigation
is Persian RTL; technical PBX forms remain LTR. Included modules are not a claim
that every queue, fax, trunk or external integration has been exercised.

## Passwords

Near the start, enter the panel `admin` password and MariaDB root password in
**two hidden terminal inputs**. Press Enter to generate either value. Allowed
characters are ASCII `A-Z`, `a-z`, `0-9`, space and `. @ = _ ! -`; Persian letters
are not accepted by the native password adapter.

Successful selection is saved root-only, mode 0600, in:

```text
/root/mytelpbx-credentials.txt
```

Use unique passwords. Keep this file and installation logs private. An accepted
same-release resume reuses saved values without rotation. For unattended use,
missing values are generated; optional preset values use ASCII placeholders:

```bash
MYTELL_ADMIN_PASS='REPLACE_WITH_UNIQUE_ADMIN_PASSWORD' MYTELL_MYSQL_ROOT_PASS='REPLACE_WITH_UNIQUE_DATABASE_PASSWORD' bash install-mytellpbx.sh
```

## Panel, Desk and recording

After success, open the printed `https://<server-ip>/` address and sign in as
`admin`. The fresh certificate contains the detected hostname/interface addresses
and is self-signed; browsers do not trust it automatically. A valid existing
certificate/key pair is preserved. Configure trusted domain TLS for public use.

MytelDesk is available at `/MytellDesk/`. Choose **Panel account** for authorized
native panel credentials. A separate local Desk administrator has its own password
at `/etc/myteldesk/initial-admin.txt`, readable only by root.

`myteldesk doctor` checks the Desk service and real CPU model inference. It does
not prove SIP registration, two-way audio, or automatic VAD on a recorded call.
Provision valid SIP/WebRTC extensions separately. Recording and retention policy
are not enabled or changed automatically by installing the VAD runtime.

An optional `MYTELL_DESK_PUBLIC_URL=https://pbx.example.com` selects the Desk public
origin. It does not issue a certificate or configure SIP trunks. Country data uses
DB-IP Country Lite and GeoNames attribution; source availability is required.
Updates retain the previous valid data if download/conversion fails and do not
change firewall rules.

## Resume and diagnosis

Wait until the previous installer has ended before using the same pinned command
again. Recognized completed stages can be reused with the **same release and
payload hash**. A partly initialized native framework or unknown/cross-version
state can be refused. Preserve the existing state, credentials and log; do not
remove markers or force a reset to bypass that refusal.

- Installer log: `/var/log/mytelpbx-install.log`
- Service status: `systemctl status httpd mariadb asterisk myteldesk`
- `bundle checksum mismatch`: check the official release asset/checksum and
  network; do not bypass integrity checks.
- Existing PBX/source-ownership refusal: stop the base installer and investigate
  scoped maintenance. Reimaging or a known backup is the recovery path when a
  genuinely fresh server is needed.

After a successful installation, a planned reboot is recommended. Optional
`MYTELL_REBOOT=1` requests it only after successful checks and saved credentials.
A service-health result alone is not full call-center acceptance.

## Network and security

| Port | Purpose |
|------|---------|
| 22 | Existing SSH management; unchanged |
| 80/443 TCP | Web panel |
| 5060 TCP/UDP, 5061 TCP | SIP signaling |
| 10000–20000 UDP | RTP media |

firewalld remains enabled. The installer **disables SELinux** and uses PHP 7.4,
which is upstream end-of-life. Restrict panel access appropriately and keep
supported system components updated. Package/repository identities and required
third-party notices are preserved; see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

The custom ISO is a separate local deliverable and is not uploaded with the
GitHub release. Older reports do not certify the current installer; use the
[7.6.2 record](releases/7.6.2/verification.md).
