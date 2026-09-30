# ISSABEL 5 → MyTellPBX TABLER THEME — TECHNICAL NOTES

Date: 2026-09-29
Server: 192.168.8.176 (issabel.local, Rocky Linux 8.8)

## Versions

- ISSABEL VERSION: 5.0.0-1 (issabel-framework 5.0.0-1, issabelPBX 2.12.0)
- OS: Rocky Linux 8.8, Apache 2.4.37, PHP 7.4.33 (remi), Asterisk 18.19.0
- TABLER SOURCE: https://github.com/tabler/tabler
- TABLER VERSION/TAG: 1.6.1 (npm @tabler/core@1.6.1, published 2026-09-28)
- TABLER ICONS: 3.48.0 (@tabler/icons-webfont, MIT)
- FONT: Inter variable (@fontsource-variable/inter, SIL OFL 1.1)
- THEME NAME: mytellpbx
- THEME PATH: /var/www/html/themes/mytellpbx
- REPO: https://github.com/DashSaman/MyTellPBX

## Selected layout

Tabler "vertical navigation" (navbar-vertical sidebar + page header +
breadcrumb + page body + footer), matching Tabler's layout-vertical
pattern.

Why: Issabel has 9 top-level menu groups with deeply nested children
(91 menu entries in menu.db plus the issabelPBX pages). A persistent
vertical sidebar with collapsible groups scales with that many items,
keeps the content area as wide as possible for data-heavy CDR/report
tables and long PBX forms, and preserves the existing Issabel mental
model (sidebar navigation), so admin workflows do not change.

Alternatives considered:
- Horizontal navbar layout: rejected — 90+ entries overflow horizontal nav.
- Compact icon-only sidebar: rejected — nested submenus need labels.
- Double-column / vertical-right: rejected — unnecessary for desktop-first
  PBX administration and costs horizontal space.

## What was changed on the server

ADDED:
- /var/www/html/themes/mytellpbx/ (the whole theme; new files only)
- /root/issabel-before-tabler-20260929-223533/ (pre-change backup)
- /root/rollback-issabel-tabler.sh (rollback script)
- /root/mytellpbx-theme-1.0.0.tgz (installed package copy)

MODIFIED (data only, no code):
- settings.db `settings` table: key `theme` = `mytellpbx`
  (the framework's own mechanism, same as the built-in theme selector)

BACKEND/PBX LOGIC CHANGES: NONE
- No PHP under /var/www/html outside themes/mytellpbx was touched.
- No Asterisk config, dialplan, database schema or module code changed.
- Original themes `tenant` and `farsi_rtl` remain installed and selectable.

## Theme internals

- css/tabler.min.css  Tabler 1.6.1 distribution CSS (unmodified)
- css/fonts.css       Inter @font-face (local file, no CDN)
- css/shell.css       Tabler vertical shell tuning (sidebar, header, panels)
- css/compat.css      compatibility layer: BS3-JS interplay patches
                      (.fade.in, .modal.in, .open>.dropdown-menu,
                      .tooltip.in, .collapse.in), removed-BS3 utility
                      classes (.pull-*, .label, .btn-default, .form-group,
                      .input-group-addon, .panel, .well, .nav-tabs li>a,
                      .pagination li>a), legacy skinning for bare inputs,
                      framework grid toolbar and old tables
- js/shell.js         vanilla JS: dropdowns, sidebar groups, module search
                      filter, dark/light toggle, About-dialog branding.
                      Deliberately NO Bootstrap 5 JS so issabel's
                      Bootstrap 3 JS keeps working.
- themesetup.php      same contract as the tenant theme; Tabler icon map
- _common/*.tpl       Tabler shells for index/menu/login/popup/help/listcsv/
                      _shortcut; _list.tpl and listcsv.tpl kept byte-equal
                      to the tenant theme (zero risk)

Load order: fonts.css → tabler.min.css → shell.css → {$HEADER_LIBS_JQUERY}/
{$HEADER}/{$HEADER_MODULES} (module CSS/JS) → compat.css (last).

## Dependency compatibility

- jQuery comes from the framework ({$HEADER_LIBS_JQUERY}) exactly as before.
- FontAwesome webfont still loaded by the framework for legacy module icons.
- Tabler CSS + compat.css restyle legacy BS3 markup; the five BS3-JS patch
  rules keep modals/tooltips/dropdowns/collapse working (verified in browser).
- DataTables, Select2, jQuery-UI datepickers: verified rendering on CDR,
  monitoring, agenda, time_config pages.

## Dark / light

- Light is the default. A shell-only dark mode exists (toggle in the header,
  persisted in localStorage); legacy module content intentionally stays on a
  light background so old widgets remain readable.

## RTL

- Persian/RTL was explicitly NOT requested; the UI is English LTR.
  System language is `en` (settings.db). farsi_rtl theme remains available.

## Backup & rollback

- Backup: /root/issabel-before-tabler-20260929-223533 (themes, index.php,
  configs, lang, langmenus, sqlite DBs, rpm list; owners/permissions kept)
- Rollback: bash /root/rollback-issabel-tabler.sh
- ROLLBACK VERIFIED: YES — executed on this server; the original tenant
  theme and settings were restored, then MyTellPBX was reinstalled.

## Tests performed (real browser, 1920/1366/390 viewports)

- Login flow (correct + wrong-password path renders alert)
- Dashboard widgets (CPU/RAM/disk/processes/traffic - real data)
- Sidebar: group toggling, active states, module search filter
- 15 module pages smoke-tested: monitoring, userlist, grouplist,
  backup_restore, voicemail, conference, my_extension, sec_rules, language,
  themes_system, agenda, email_accounts, asterisk_log, preferences,
  time_config — all render, no theme asset 404s
- CDR Report: filters, DataTables, export toolbar, chart
- PBX Configuration (issabelPBX framed UI) loads inside the shell
- REAL PBX functional test: created PJSIP extension 9999 (TESTTHEME),
  deleted it through the UI (SweetAlert confirm), applied dialplan config
- User menu, info menu, notifications markup, logout
- Dark mode toggle, 1366x768 and 390x844 layouts
- One pre-existing 404 (datatables.en.json, issabelPBX language file)
  unrelated to the theme

## Known limitations

- issabelPBX (FreePBX fork) configuration UI keeps its own purple branding
  (separate application inside a frame).
- The framework hardcodes THEMENAME=tenant on the two-factor-auth page,
  so that page keeps the tenant look.
- The dashboard's legacy widgets use fixed desktop widths; on very narrow
  phones they scroll horizontally (pre-existing module behavior).
- "News" widget links point to Issabel community sites (server-provided
  data, not theme content).

## Phase 2 — dashboard & reports polish (v1.1.0, 2026-09-30)

Updates on the test server (192.168.8.176) and in the theme, superseding
the limitations above where noted:

- Dashboard: News and Issabel Network applets removed from dashboard.db;
  gauges and flot charts wrapped by shell.js (`MYTELL_GAUGE`, `MYTELL_PALETTE`)
  so they render in MyTellPBX blue; flat applet cards.
- Report sweep (real browser, every page screenshotted): CDR Report,
  Channels Usage, Billing (rates/report/dest distribution/setup), Asterisk
  Logs, Graphic Report, Summary, Missed Calls, Recordings. Buttons, search
  fields, filters, DataTables pagination (1.9 + 1.10 markup) and export
  toolbars verified; Bootstrap 3 glyphicon webfont bundled for the legacy
  DataTables button icons.
- compat.css additions: jQuery-UI datepicker skin (blue header, white
  prev/next, styled selects), blue SVG calendar trigger icon via
  `content:url()`, dark text on date inputs (beats the inline `color:#840`),
  and the framework utility `.neo-display-none` (its absence left the
  missed-calls export menu permanently visible).
- About dialog: `modules/_issabelutils/themes/default/_aboutus.tpl`
  rebranded (static MyTellPBX logo, project link; legacy lottie animation
  and issabel.org link removed). Original saved in the phase-2 backup.
- 404 clean-up: `lottie.min.js` request (About dialog), `animIssabel.json`
  (stale Smarty compile — cache file removed), missing
  `datatables.en.json` for cdrreport/monitoring (shipped as `theme/extras/`
  and installed without overwriting existing files).
- Server brand backup: `/root/mytell-brand-backup-20260930-001844` +
  `/root/rollback-mytell-brand.sh`.
- Theme tarball for this release: `mytellpbx-theme-1.1.0.tgz`
  (md5 `6a9921a6b065221b2ea2e7a92ad814b6`).
