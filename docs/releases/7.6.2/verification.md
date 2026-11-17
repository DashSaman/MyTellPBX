# 7.6.2 verification scope

This record distinguishes executed checks from unverified product paths.
It contains no private lab addresses, credentials, session data or raw logs.

## Executed checks

| Scope | Recorded result | Limit |
|-------|-----------------|-------|
| Installer regression checkpoint | 672 tests: 566 passed, 106 platform skips, 0 failures/errors | A source/fixture checkpoint, not a full live install or final call matrix |
| Launcher-directory fix | 30 native filesystem fixtures passed, 0 skips; old umask 077 case reproduced the failure | Isolated fixtures; separate live scoped repair described below |
| TLS certificate fix | 15 native OpenSSL fixtures passed, 0 skips; old case retained as RED | Generated server certificate and preservation contracts, not browser/SIP media acceptance |
| ISO branding contract checkpoint | 9 focused source checks passed; native SVG rendering and artifact readback completed | Presentation-only correction; no new boot/installation was run for this correction |
| ISO structure/integrity | Native build, embedded-media checksum, depot readback and BIOS/UEFI boot-record metadata checked | Does not prove OS/firstboot installation completion |

The branding correction changes the BIOS splash, Anaconda wordmark/CSS and
human-readable boot-menu labels. Kickstart storage choices, root-password input,
firstboot units, payload and signed dependency depot are preserved. The ISO
binary is retained as a local deliverable and is not a GitHub release asset.

## Installed-system evidence

A diagnostic installation exercised native framework setup, WebRTC/DTLS,
GeoIP, Desk 1.1.2 and CPU VAD readiness. An owned launcher directory created with
mode 0700 caused the native login page to return 500. A scoped, backed-up repair
changed only the verified directory to 0755; public PHP bytes were unchanged and
login returned 200. A separate post-repair verifier returned 0 and confirmed the
recorded credentials, service keys and source identity were preserved. The
original failed result remains preserved.

This is a diagnostic continuation plus scoped repair, **not an uninterrupted
fresh-OS pass of the final release**. Subsequent source fixes have regression
coverage; source checks do not replace a completed cold installation.

An existing ISO rehearsal stopped at the **offline vendor GeoIP handoff**,
after native package installation and before framework initialization. The
default online installer uses a separate native GeoIP handoff branch; this
offline result does not establish an online failure. The precise offline guard
remains under investigation, and that rehearsal is not a successful install.

## Not verified for the current release

- A complete uninterrupted cold installation of the final public installer.
- Real current-release SIP registrations and decoded two-way audio, hold/resume,
  mute/unmute and BYE in the product UI.
- Automatic VAD from an actual newly recorded call, plus native WAV and UI
  playback/download byte equality. Model inference alone is not this test.
- The current Asterisk 16/18 runtime/media matrix. The full installer supports 20 only.
- All configuration Save/Apply transactions, all panel routes, user roles,
  external trunks/PSTN, queues, fax delivery, SMTP and other external integrations.

Older [7.6.0 evidence](../7.6.0/verification.md) and older standalone Desk results
retain their own product/version scope. They are not current-release PASS results.

The [installation guides](../../INSTALL.en.md) describe the supported
fresh Rocky 8.10 x86_64 workflow, two hidden ASCII-password inputs and the exact
pinned release command. SHA checks, native ownership guards and preserved
credentials remain required when diagnosing an interrupted installation.
