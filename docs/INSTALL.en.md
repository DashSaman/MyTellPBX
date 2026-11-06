# MyTellPBX Installation Guide (English)

## One-line install

On a **fresh Rocky Linux 8.10 (x86_64)** server with root access and
internet, download, review, then run the installer — never pipe a remote
script straight into bash without review:

```
curl -fsSL -o install-mytellpbx.sh \
  https://github.com/DashSaman/MyTellPBX/releases/download/v7.4.0/install-mytellpbx.sh
```

```
bash install-mytellpbx.sh
```

On success the panel URL and the credentials-file path are printed.

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
   - Unique random passwords in a root-only credentials file

The install is staged and resumable: if interrupted, re-running the same
command continues from the completed stage and **never rotates existing
credentials**.

## Credentials

- The panel password (user `admin`) and the MariaDB root password are
  **generated randomly** during install and stored in:

```
/root/mytelpbx-credentials.txt
```

- The file is mode 0600, root only.
- On an interactive terminal the passwords are printed at the end; in a
  headless run only the file path is shown.
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
- There are no default passwords; everything is generated at install time.
- The base telephony packages come from the upstream open-source
  distribution's repositories; functional package and repository
  identities are preserved unchanged for dependency resolution and
  updates (see THIRD_PARTY_NOTICES.md).

## Troubleshooting

- **Full install log**: `/var/log/mytelpbx-install.log`
- **Resume an interrupted install**: run the same command again; finished
  stages are skipped.
- **"existing PBX packages detected"**: the server is not fresh; see
  Removal below.
- **"bundle checksum mismatch"**: delete `/tmp/mytelpbx-bundle-7.4.0.tgz`
  and run again.
- **Panel not loading**: check `systemctl status httpd mariadb asterisk`.
- **Login fails**: `cat /root/mytelpbx-credentials.txt`.

## Removal

The reliable removal path is **reimaging the server** (or restoring a
snapshot). Package removal does not return the system to factory state;
for lab servers a cleanup helper exists at
`scripts/mytelpbx-teardown.sh` (it does not guarantee a perfectly fresh
system).
