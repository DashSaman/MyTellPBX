# Verification and test scope

The current release record is [7.6.2 verification](releases/7.6.2/verification.md).
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

- Final uninterrupted cold installation: **NOT VERIFIED**; an existing ISO
  firstboot-service failure remains under investigation.
- Final-release SIP registration, decoded two-way audio, hold/mute/BYE,
  recorded-call automatic VAD and recording UI/native byte parity: **NOT VERIFIED**.
- Current Asterisk 16/18 runtime/media matrix: **NOT VERIFIED**; the full installer selects 20 only.
- Read-only page inspection does not certify configuration writes, all roles,
  external trunks, fax delivery or other integrations.

The [7.6.0 record](releases/7.6.0/verification.md) remains historical. Its route
counts, fixtures and product versions must not be presented as 7.6.2 results.
Private credentials, logs, sessions, backups and customer data are not release assets.
