# Unified MyTell workspace

## Scope and acceptance

Owner-authorized UI-only redesign of Issabel panel, LTR PBX console, MyTellDesk
and WebPhone. No telephony, authentication policy or production data changes.

Acceptance is an explicit inventory of installed pages, captured in both themes
at 1440px and 390px, with no newly introduced document overflow, unreadable
controls, broken theme icons or uncaught UI exceptions. Menus, focus, theme
persistence, calendars, dropdowns and representative non-submitting forms receive
interaction checks. Modules that are unavailable are reported, not silently passed.

## Design direction

**A calm signal workspace.** Operators need to distinguish a ringing line from a
navigation accent immediately; decorative orange glows on every control dilute
that signal. Use a disciplined navy navigation rail, cool porcelain work surfaces,
clear blue selection and warm orange only as a restrained brand/signaling accent.

| Role | Light | Dark |
| --- | --- | --- |
| Canvas | `#F3F6FA` | `#0C1422` |
| Surface | `#FFFFFF` | `#131F30` |
| Secondary surface | `#F7F9FC` | `#19283C` |
| Primary ink | `#18283E` | `#EAF0FA` |
| Navigation | `#112239` | `#101D2F` |
| Selection / brand accent | `#245CC5` / `#FF9A3C` | `#A9C9FF` / `#FFBB7A` |

- Vazirmatn for Persian and UI labels; existing local Latin fonts for technical
  values. Tabular numerals for metrics. No tracking on joined Persian letters.
- 14px reading floor for normal copy, 12–13px only for secondary metadata.
- 8px control corners, 12–16px content containers, no repetitive glow or gradient.
- Color alone does not convey status; retain existing text/icon state labels.
- High-contrast keyboard focus, 44px touch targets and reduced-motion support.
- The PBX console remains natively LTR, including technical forms. Persian help
  remains isolated text, not a direction override on the console.

```text
Persian panel / operator desk (RTL)
┌─────────────────────────────────────────┬───────────────┐
│ profile / theme       page context       │ brand         │
├─────────────────────────────────────────┤ search        │
│ breadcrumb                              │ navigation    │
│ page title / relevant actions           │               │
│ working surface (table / form / monitor) │               │
│                                         │               │
└─────────────────────────────────────────┴───────────────┘

PBX settings (LTR, original layout preserved)
┌─────────────────────────────────────────────────────────┐
│ brand / native navigation / theme                       │
├───────────────────────────────────────┬─────────────────┤
│ native labels and form controls       │ record nav      │
│                                       │                 │
└───────────────────────────────────────┴─────────────────┘
```

### Self-critique before implementation

Reject a generic dashboard hero, identical decorative cards and repeated
statistic gradients. This is an operational telephone system, not a marketing
landing page. Keep existing information architecture and spend visual emphasis
on current navigation, active work and genuine call/status signals. Login screens
can carry a quiet, static signal motif; live working screens should not animate.

## Delivery strategy

1. Capture live baseline and reconcile deployed/source differences.
2. Build token-driven component layers, loaded after legacy module styles.
3. Preview candidate responses in isolated browser contexts; inventory every
   installed page rather than a hand-picked module subset.
4. Run syntax, patcher regression, build and real-browser acceptance checks.
5. Obtain independent review, publish the exact reviewed tree and deploy only
   the scoped manifest with backups and automatic failure rollback.
6. Verify actual live responses, service health and unchanged PBX configuration.

Evidence and final coverage are recorded with the release; no credentials or
production session artifacts belong in this document.

## Installed-source reconciliation

The resumed read-only preflight confirmed GitHub `main` at
`dbc3f143fd733913013efaa445507c22577d5185`, matching the local base. The
authorized installation still matches the original private UI snapshots; it
has not received the candidate. HTTP, Asterisk and operator-desk services were
active. Hashes of 165 Asterisk configuration files were captured privately as
unchanged-content guards, not as deployment inputs or write targets.

Four installed panel files differ from that GitHub base: `_shortcut.tpl`,
`popup.tpl`, `help.tpl` and `help.css`. Their installed list navigation,
Persian popup, dynamic help title and help-frame behavior are preserved in the
candidate rather than replacing them with the retired Tabler equivalents.
New workspace assets are additive. Admin and desk changes are planned against
the installed source/toolchain, not an assumed clean upstream installation.

The earlier 175-page / 700-case candidate audit is historical evidence, not a
passing final-artifact receipt. Its findings were narrowed with targeted runs;
the newest saved targeted run contains 12 completed cases with no detected
contrast, overflow or page-exception findings. Exact release-artifact coverage,
interaction results and known unavailable paths must still be recorded with
the reviewed release.

## Verified pre-release evidence

- The standard-library regression suite passed on Linux/Python 3.6.8 without
  skips, including extended-attribute preservation and symlink rejection.
  Windows passed with only those two platform-dependent checks skipped.
- Five chart runtime tests, nine JavaScript syntax checks, Python 3.6 syntax
  checks and the scoped Ruff checks passed. Fourteen synthetic renders using
  installed Smarty 3.1.48 completed without stderr.
- The isolated artifact build passed TypeScript, login ESLint, workspace
  Stylelint, Vite and both PHP syntax checks. Its manifest contains 29 changed
  UI files and 148 read-only input guards. Source and generated-payload secret
  scans found no matches. Bundles, original installed files and screenshots stay
  private; they are not release attachments.
- Apply and rollback of all 29 files were exercised on private copies of the
  actual installed UI bytes. Live before-hashes still matched afterwards.
  This used an independent **fixture-only** review, removed from the remote
  after the test; it is not production approval.

### Browser coverage and honest failures

The first artifact inventory completed 175 pages / 700 cases. It exposed three
presentation issues: mobile firewall table overflow, dark email-variable chip
contrast and the dark loading overlay. The fixes received 20 targeted cases
without overflow, contrast or page-exception findings. An additional four email
cases explicitly waited for the deferred template card before checking its
variable chips; all four passed, with no blocked writes.

The updated broad audit completed 350 desktop cases and 261 mobile cases.
The mobile run stopped on an upstream request timeout in `sec_fb_banned`;
**it did not complete or pass all 350 mobile cases**. Completed cases had no
navigation errors. The broad audit was not restarted to repeat completed work.
Unchanged surface payloads can reuse earlier evidence only after hash comparison;
later scoped changes require their own targeted check.

All 28 interaction behavior assertions passed: keyboard theme persistence,
mobile drawer/focus return, Jalali navigation, report date focus/Escape,
export-menu opening, native LTR PBX field order and phone theming without
registration. Only 24 aggregate checks passed: four desk checks remained failed
because of the pre-existing audio-resource 404s below. Resource checks were not
disabled or exempted. The mobile report filter was also reviewed visually;
its remaining legacy table minimum is removed only within that form below
700px. The exact final artifact must pass a scoped filter-geometry/date-focus
check before approval.

Read-only baseline reproduction confirmed these existing limitations:

| Area | Observed limitation |
| --- | --- |
| Control panel | `t.removeClass is not a function` |
| GeoIP navigation | Leaving `sec_geoip_map` can reject a pending request with `visualLatitude`; reproduced with and without candidate overrides |
| Embedded webmail | `/mail/` returns 401; authenticated mailbox operation is not covered |
| Asternic reports | `/admin/themes/default/css/mytel.css` returns 404 |
| Desk settings | `/MytellDesk/api/codecs` returns 404 |
| Desk audio | `/sounds/ringtone.wav` and `/sounds/dialing.wav` return 404 on reload in both baseline and candidate |

Fax/firewall pages also attempt automatic POSTs. The harness blocks them and
records their synthetic 405 responses; no configuration submission was allowed.
WebSockets remain blocked, so connected SIP/AMI behavior, actual calls, audio
playback and unavailable backend features are **not passed** by this UI release.
Consequently the raw full-audit and interaction commands intentionally return
nonzero rather than hiding these failures. The final review must assess the
documented UI scope, not interpret those commands as an all-green PBX audit.

### Reproduction and delivery gate

```text
python -B -m unittest discover -s tests -v
node --test tests/ui/charts.test.cjs
node --check tests/ui/audit.cjs
node --check tests/ui/interactions.cjs
```

Browser checks use the existing external session/password-file setup, never
credentials in this repository. Set `MT_ARTIFACT_ROOT` to the private built
artifact and `MT_EVIDENCE_DIR` to a new private directory; run `audit.cjs` or
`interactions.cjs`. `MT_INCLUDE`, `MT_WIDTHS` and `MT_THEMES` bound an audit.
Non-GET and WebSocket protections must remain enabled.

Panel/admin candidate responses mirror the changed template fragments over
the real installed documents; desk/phone use the artifact documents directly.
Template rendering is separately checked with Smarty. After deployment, live
pages must be checked **without candidate overrides** to verify the actual
installed templates and assets.

The final source tree, manifest hash, final checks and deployment result belong
in the release receipt. A documentation/harness-only source change is not an
excuse to claim a new runtime pass: preserve the earlier receipt and compare
payload hashes explicitly. Publication and UI-only apply still require a saved
independent `READY` tied to the exact final tree and manifest. Back up every
manifest path, preserve the journal outside served roots, and use its scoped
rollback on any introduced post-deployment failure. Never reload telephony or
change PBX configuration as part of this delivery.
