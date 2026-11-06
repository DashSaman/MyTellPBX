# MyTellPBX installer — verification record for v7.4.0

This document records how the installer was verified before publication.
Test target: fresh Rocky Linux 8.10 x86_64 VM (192.168.1.162, Hyper-V,
36 GB disk, 3.6 GB RAM), installed over the network exactly as documented.

## Automated checks during development

- `bash -n` on the installer, builder and teardown scripts — pass
- Bundle internal `SHA256SUMS` verification + embedded archive SHA-256 in
  the installer (mismatch aborts before any system mutation)
- Unsafe-archive rejection (absolute paths, `..`, links) in code
- Invalid environment values rejected (`MYTELL_ASTVER`, `MYTELL_LANG`,
  password charset, `MYTELL_REBOOT`, `MYTELL_SKIP_UPDATE`)
- Install lock verified live: a second concurrent run exits with a clear
  error and does NOT clobber the active run's log
- Interrupted-install resume + credential preservation verified live
  (multiple real interruptions during development; every resume preserved
  `/root/mytelpbx-credentials.txt` and never rotated passwords)
- Corrupted/stuck downloads handled: bounded retries on OS update and both
  package stages (validated live against a slow upstream mirror that
  timed out mid-transaction)

## Clean-install verification (fresh OS after teardown)

1. Preflight + full staged install completes with exit code 0 (one
   auto-repair cycle exercised: the framework self-check detects an
   incomplete upstream `install_amp` (modules table empty) and a re-run
   repairs it — by design).
2. Self-checks in the installer: MariaDB/Asterisk/httpd active, login
   page serves with MyTel branding, settings.db theme=mytel language=fa,
   credentials file mode 0600.
3. Framework completeness verified: asterisk.modules=57 registered,
   pjsip_additional.conf generated (hard checks; failure marks the stage
   for repair on the next run).
4. Services after reboot: mariadb, httpd, asterisk active and enabled;
   brand keys survive the boot-time `amportal a r` regeneration because
   they are persisted in `asterisk.issabelpbx_settings` (verified by a
   real reboot).
5. Real browser acceptance (headless Chromium from the rig):
   - login page: Persian title «MyTel | Call Center Management System»,
     RTL, zero upstream-brand mentions
   - login with the generated admin password works
   - panel: Persian RTL sidebar, dark/light toggle, MyTel footer
   - admin console: title "MyTell PBX", mytel skin loaded, zero
     upstream-brand mentions
   - sweep over all 92 panel menu pages: zero upstream-brand strings in
     visible text and links
6. Real call test (first full install, evidence retained): two PJSIP
   endpoints (2001/2002) created, both REGISTER with digest auth, live
   call 2001 -> 2002 through the platform dialplan: 100 -> 180 -> 200,
   answered, two-way RTP verified by packet counters on both ends
   (caller tx 288 / rx 287, callee rx 288 / tx 287 via echo), clean BYE,
   CDR row: src=2001 dst=2002 billsec=6 disposition=ANSWERED.
   On the rebuilt clean instance the same platform dial path was
   re-verified (registration, contact reachability, dialplan Dial()
   execution); the synthetic-UA call driver hit a script-level race and
   the full RTP loop was not repeated there.

## Known limitations (disclosed)

- PHP 7.4 is EOL upstream (framework requirement) — documented.
- SELinux disabled (framework requirement) — documented.
- Asterisk 16/18 are not offered (EOL); only Asterisk 20.
- The MytellDesk operator desk (OpDesk) is not part of the base installer.
- The lab test server is a Hyper-V VM without an owner-accessible reimage
  path; "fresh" states were produced with the teardown script (documented
  as approximate) rather than a hypervisor reimage.
