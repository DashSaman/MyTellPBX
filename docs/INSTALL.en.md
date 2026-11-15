# MyTellPBX Installation Guide (English)

## One-line install

On a **fresh Rocky Linux 8.10 (x86_64)** server with root access and
internet, download, review, then run the installer — never pipe a remote
script straight into bash without review:

```
curl -fsSL -o install-mytellpbx.sh \
  https://github.com/DashSaman/MyTellPBX/releases/download/v7.6.0/install-mytellpbx.sh
```

```
bash install-mytellpbx.sh
```

On success the panel URL and the credentials-file path are printed.
An interactive terminal asks only for the panel administrator and MariaDB root
passwords near the start. Input is hidden; Enter generates that password.
An exact-release resume reuses the saved values without prompting or rotation.

## Prerequisites

- Rocky Linux 8.10 exactly (Minimal install recommended), x86_64
- root access
- Internet access to package repositories and GitHub
- At least 8 GB free disk and 1.5 GB RAM
  (tested hardware: a VM with 36 GB disk and 3.6 GB RAM)
- **A fresh server**: the installer refuses to run over an existing PBX

## What gets installed

1. **Telephony base**: Asterisk 20, MariaDB, Apache, PHP 7.4 and the
   framework modules (extensions, queues, call recording, CDR reports,
   fax, ...) from the upstream open-source telephony distribution.
2. **The MyTel layer**:
   - Persian RTL panel theme with the Vazirmatn font (light/dark modes)
   - Full admin-console skin and branding, plus the advanced-report
     subtitle
   - Persian panel language and complete debranding (no upstream brand
     name is visible anywhere in the UI)
   - The Apply Config fix
   - Two chosen or uniquely generated passwords in a root-only credentials file
3. **MytelDesk with CPU VAD**: the exact pinned public release, private Node and
   Python3.11 runtimes, hash-locked dependencies and bundled verified model.
   The product's installer and doctor run real CPU inference before success.
   Existing recording/retention policy stays unchanged.

The install is staged and resumable: if interrupted, re-running the same
command with the same release/bundle hash continues from the completed stage and
**never rotates existing credentials**. Unknown legacy or cross-version installer
state is refused. Do not delete the ownership receipt or credentials to force an
OS reinstall over an existing PBX; use separately reviewed scoped maintenance.

For a domain instead of the server's detected HTTPS address, set
`MYTELL_DESK_PUBLIC_URL=https://pbx.example.com`. Configure trusted TLS and valid
SIP/WebRTC extensions on the PBX for browser calling; setting this URL does not
issue a certificate or configure trunks. HTTPS access to GitHub, nodejs.org,
files.pythonhosted.org and official Rocky repositories is required for Desk/VAD.

Open `/MytellDesk/` and choose **Panel account**. The native launcher requires an
administrator panel session and redirects there; a first Desk visit still signs
in using panel credentials. Existing Desk tokens remain usable. A separate local
Desk admin has a unique password in `/etc/myteldesk/initial-admin.txt`. Maintenance
uses `myteldesk doctor` and the standalone product's documented rollback. Legacy
Desk deployments require reviewed migration; the base installer never resets
their accounts or patches immutable release code.

## Credentials

- Choose the panel password (user `admin`) and MariaDB root password in two
  hidden terminal inputs. Enter, or a headless run without preset values,
  generates a unique random value. Both are validated before saving:

```
/root/mytelpbx-credentials.txt
```

- The file is mode 0600, root only.
- Passwords are never printed at the end or in installer output; only the file
  path is shown. Invalid or interrupted input stops before creating the final file.
- You may pre-set them:

```
MYTELL_ADMIN_PASS='your-pass' MYTELL_MYSQL_ROOT_PASS='your-pass' bash install-mytellpbx.sh
```

Allowed characters: letters, digits, space and `.` `@` `=` `_` `!` `-`.
- Re-runs never change existing credentials.

## After installation

- Panel: `https://<server-ip>/`, sign in as `admin`
- A one-time reboot is recommended (`reboot`)
- Or automate it: `MYTELL_REBOOT=1 bash install-mytellpbx.sh`
  (reboots only after every check passes and credentials are persisted)

## Network ports

| Port | Purpose |
|------|---------|
| 22 | Server management (SSH) — untouched |
| 80 / 443 | Web panel |
| 5060 (TCP/UDP), 5061 | SIP signaling |
| 10000–20000 (UDP) | Voice (RTP) |

firewalld **stays enabled**; only these ports are opened.

## Security notes

- **SELinux is set to disabled** — the telephony framework is not
  compatible with it. This change is permanent in the server config.
- **PHP 7.4** reached upstream end-of-life (November 2022); the telephony
  framework requires it. Keep the panel on an internal network or behind
  a firewall/reverse proxy and keep the OS updated.
- There are no default passwords; choose your own values or generate unique ones.
- The base telephony packages come from the upstream open-source
  distribution's repositories; functional package and repository
  identities are preserved unchanged for dependency resolution and
  updates (see THIRD_PARTY_NOTICES.md).

## Troubleshooting

- **Full install log**: `/var/log/mytelpbx-install.log`
- **Resume an interrupted install**: run the same command again; finished
  stages are skipped.
- **"existing PBX packages detected"**: the server is not fresh; stop the base
  installer and use reviewed maintenance. Removing installer state is not a fix.
- **"different or invalid installer source"**: preserve the state/credentials;
  resume with the original exact release or review a scoped migration.
- **"bundle checksum mismatch"**: the per-run private download workspace is
  discarded; check the official release checksum/network and rerun the same
  installer. Do not bypass integrity checks or delete credential files.
- **Panel not loading**: check `systemctl status httpd mariadb asterisk`.
- **Login fails**: `cat /root/mytelpbx-credentials.txt`.

## Removal

The reliable removal path is **reimaging the server** (or restoring a
snapshot). Package removal does not return the system to factory state;
for lab servers a cleanup helper exists at
`scripts/mytelpbx-teardown.sh` (it does not guarantee a perfectly fresh
system).
