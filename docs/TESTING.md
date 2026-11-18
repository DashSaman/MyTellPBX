# Verification and test scope

The current release record is [7.7.0 candidate verification](releases/7.7.0/verification.md).
It separates source/fixture results, scoped installed-system checks, ISO artifact
checks and unverified call paths. It does not treat a running service, a login
page, CPU model inference or an older release report as full installation/media acceptance.

For source changes, use the relevant existing tests in `tests/`; native Bash,
PHP, filesystem and service-adapter fixtures must run on their supported platform.
Record skipped cases explicitly. From a source checkout, the existing Python suite is:

```bash
python3 -B -m unittest discover -s tests -v
```

A fixture pass is not a live SIP/RTP result.

Current limitations:

- Final fresh Rocky Linux 8.10 Minimal online installation and native ISO
  offline/UEFI installation: **PENDING** final source- and asset-bound receipts.
- Final-source SIP registration, decoded two-way audio, hold/mute/BYE,
  recorded-call automatic VAD and recording UI/native byte parity: **PENDING**
  fresh final receipts. Historical runs retain their original scope.
- Both current installation paths support **Asterisk 20 only**. Asterisk 16/18
  are unsupported, not pending acceptance targets. Native language selection remains available.
- The ISO is an owner-lab artifact and is not uploaded to GitHub.
- Read-only page inspection does not certify configuration writes, all roles,
  external trunks, fax delivery or other integrations.

The [7.6.0 record](releases/7.6.0/verification.md) and
[7.6.2 record](releases/7.6.2/verification.md) remain historical. Their route
counts, fixtures and product versions do not certify the 7.7.0 candidate.
Private credentials, logs, sessions, backups and customer data are not release assets.
