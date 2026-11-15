# 7.6.0 verification scope

This record distinguishes executed source/browser checks from a fresh operating
system installation. Private screenshots, ACL records, installed PHP snapshots,
sessions, customer data and credentials are not release assets.

## Interface coverage

The installed panel exposed 149 default routes: 90 panel menus and 59 native PBX
displays. A write-blocked browser sweep examined each at 1440px and 390px, in light
and dark themes: 596 default page states. The same matrix was repeated with the
frozen candidate assets loaded through local response overrides. The final
candidate matrix completed with no JavaScript/navigation errors or page-wide
horizontal overflow. This is route coverage, not every possible record, dialog,
authorization role or business transaction.

Focused executed checks additionally cover:

- Sixteen read-only existing-record views: a configured PJSIP extension, trunk,
  queue and ringgroup, each at both sizes and in both themes. The installed PHP
  source was reviewed before allowing their no-action `extdisplay` GET requests.
  No configured SIP/IVR edit link was available for this extra sample.
- Selection styling, contrast, calendar Today/hover states, native search-icon
  clearance and the selected AMI-manager radio label.
- The mobile Asterisk information sidebar and Chosen search-field width.
- Native menu keyboard focus, Space/Escape behavior, focus return, desktop child
  links and dropdown containment at 390, 700, 701, 768, 1023, 1024 and 1440px.
- Forty-six dashboard cases cover server/login-HTML failures, empty/partial
  feeds, recovery, unchanged readings, native formatted numbers, delayed and
  out-of-order responses, replaced dashboard/grid ownership, missing applets,
  bounded loading, literal system text and unrelated disk responses. Feedback
  observes existing native polls; it does not create retries or call actions.
- Repeated fitting/resizing without changing the original native transform or
  vertical translate. The PBX technical console remains LTR.
- Native Save/Apply feedback through intercepted requests: real native forms and
  installed feedback controllers, with configuration writes/reloads blocked.
- Existing Jalali calendar algorithms and browser navigation. Gregorian storage,
  Tehran dates and native event semantics are retained; this release corrects
  presentation rather than replacing the stored calendar.
- Forty-four calendar browser cases run with Tehran and Los Angeles browser
  timezones against an explicit Berlin server-civil fixture. Four additional
  standalone Phone login/UI states were read-only: no signaling, microphone,
  registration or audio capability is inferred from that UI check.

Webmail returns a separate authentication challenge; that is conditional access,
not proof of a working mailbox. Unconfigured external SMTP, fax delivery, CRM and
provider integrations are not counted as completed end-to-end transactions. The
legacy operator connection error is deliberately exercised with its connection
blocked. Read-only sweeps never save PBX settings or originate calls.

## Installer and native server checks

The Linux suite executes the actual Bash functions against owned disposable
files/recording commands and tests the Python Desk adapter, source ownership,
download integrity, cache permissions, resume guards and rollback policies.
The final installer-source checkpoint passed 135 Python tests with zero skips,
62 native PHP assertions and Bash syntax checks. The chart/calendar Node suite
passed 16 tests; JavaScript syntax passed for 36 source and browser-test files.
Bundle assembly runs with actual GNU tools and Git, including clean CRLF checkout
versus committed-source bytes. Ignored secrets and dirty tracked sources are
rejected. The private workspace regression reproduces the former predictable
temporary-path symlink clobber without touching a real PBX file.

Isolated native PHP checks use owned fake database/vendor fixtures. They exercise
the Apply guard, Save result marker, SIP transaction ownership, read-only native
ACL launcher and fixed-target credential stdin adapter. They do not execute the
distribution's password-reset tool or modify production ACL/database state.
The existing vendor tool still internally constructs password-bearing commands;
the outer installer transport change is not a complete vendor security rewrite.

The independent target sandbox uses UID 65534, read-only source, a private
loopback-only network and inaccessible PBX/database/application paths. The real
published MytelDesk 1.1.0 archive was downloaded and all 12,938 manifest files were
verified there without executing downloaded product code.

The new Desk adapter's measured executable source-line coverage is 255/310
(82.26%, stdlib trace). This is neither branch nor whole-application coverage.
Reproducible commands and RED/GREEN checkpoint references are in
[tdd-index.md](tdd-index.md), [installer-desk.tdd.md](installer-desk.tdd.md) and
[installer-credentials.tdd.md](installer-credentials.tdd.md).

## Product and deployment boundaries

The main installer supports a fresh Rocky 8.10/Asterisk 20 system, or resuming the
same owned release and bundle hash. **A complete fresh-OS installation of 7.6.0
has not been rehearsed.** Existing operational PBX servers were not reimaged or
used for base-OS setup/teardown. The historical 7.5.1 installation record remains
historical and does not establish a new 7.6.0 full-install pass.

The independently released [MytelDesk 1.1.0](https://github.com/DashSaman/MytelDesk/releases/tag/v1.1.0)
has its own real Asterisk 16/18/20 call, two-way decoded audio, call-control,
recording and CPU VAD evidence. Its product source is unchanged by this release.
This wrapper's integrity/command fixtures do not constitute a repeated call test.
Installing VAD does not enable recording or alter retention policy.

For an existing PBX, the supported procedure used by this work is a separately
reviewed presentation/Desk-entry rollout, not the full installer. The narrow
`panel-polish-desk-entry-v760` profile rejects dialplan, SIP configuration, AMI
permissions, database, Desk-runtime and Phone writes. It binds native Save/Apply
dependencies read-only, orders the ACL helper before its entrypoint, checks live
drift before replacing anything, and retains a hash-checked scoped rollback.

An independent READY receipt must match the exact Git tree and private UI
manifest before production writes. Final deployment observations and the public
asset checksums belong to the external release receipt `release.json`, published
with the release assets, so they can bind the final source without a hash cycle.
Neither HTTP 200 nor service health alone is accepted as operational proof.
