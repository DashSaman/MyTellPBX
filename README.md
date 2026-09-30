# MyTellPBX

MyTellPBX is a complete visual rebranding of **Issabel 5** built on the
official **Tabler** design system (v1.6.1). It ships as a standard Issabel
theme plus a net-install script, so a fresh server becomes "Issabel with our
theme and our brand" in one run.

The telephony stack (Asterisk, FreePBX-style issabelPBX modules, databases,
backend APIs) is untouched: this project is **theme, layout, CSS, UI
components and branding only**.

## Features

- Tabler 1.6.1 vertical-navigation shell (sidebar + page header + breadcrumb)
- All Issabel menus rendered dynamically from the real menu DB with ACL
  filtering intact (administrator vs restricted users)
- MyTellPBX branding on login page, shell title, footer, user menu and the
  About dialog (static logo instead of the legacy animation)
- Redesigned dashboard: Tabler cards, blue gauge/line charts, legacy news
  widgets removed
- Report pages (CDR, Channels Usage, Billing suite, Asterisk Logs, Graphic
  Report, Summary, Missed Calls, Recordings) restyled: blue action buttons,
  fixed search fields, date pickers, export menus and pagination
- Tabler icons webfont (no emoji), Inter variable font, Bootstrap 3 glyphicon
  font bundled for legacy DataTables buttons — all assets local, no CDN
- Dark/light shell toggle (content area stays light for maximum legacy
  module compatibility)
- Compatibility layer that restyles legacy Bootstrap 3 module markup and
  keeps Bootstrap 3 JS (modals, tooltips, dropdowns, tabs) fully working
  alongside Tabler CSS
- The embedded issabelPBX (FreePBX fork) UI is rebranded through the
  official `BRAND_*` settings plus a custom stylesheet: dark navbar,
  blue accents, MyTellPBX logo, wordmark and footer
- Mobile-friendly collapsed navigation, desktop-first information density

## Install on an existing Issabel 5 server

Copy or download the `theme/` directory to the server, then:

```bash
bash install-theme.sh
```

`install-theme.sh` copies the theme to `/var/www/html/themes/mytellpbx`,
fixes ownership/permissions, activates it in the framework settings DB and
reloads Apache. Hard-refresh the browser (Ctrl+Shift+R) afterwards.

## Fresh server net-install

```bash
curl -fsSL https://raw.githubusercontent.com/DashSaman/MyTellPBX/main/mytellpbx-netinstall.sh -o mytellpbx-netinstall.sh
bash mytellpbx-netinstall.sh
```

The script performs the standard Issabel 5 net install (same repos and
packages as upstream, interactive Asterisk 16/18 selection) and then
downloads and activates the MyTellPBX theme from the GitHub release. If the
theme download fails, the server still ends up as a stock Issabel 5.

## Rollback

The theme is additive; nothing upstream is removed. On a server configured
by this project the pre-install backup and rollback script live in
`/root/issabel-before-tabler-*` and `/root/rollback-issabel-tabler.sh`
(created by the deployment; see `docs/ISSABEL-TABLER-THEME.md`).

## Repository layout

```
theme/                   the Issabel theme (installable as-is)
  _common/               Smarty templates (index, menu, login, popup, ...)
  css/                   Tabler 1.6.1 + fonts + shell + compatibility layer
  icons/                 Tabler Icons webfont 3.48.0
  fonts/                 Inter variable font + Bootstrap 3 glyphicons
  images/                MyTellPBX logo, wordmark, favicon
  js/shell.js            vanilla-JS shell interactivity (no new JS deps)
  extras/                optional static module fixes (missing DataTables
                         language files), installed without overwriting
  themesetup.php         menu icons + labels
  install-theme.sh       installer/activator
mytellpbx-netinstall.sh  Issabel 5 base + theme net installer
docs/                    screenshots and technical notes
```

## Known limitations

- A few deep issabelPBX (FreePBX fork) pages may still show legacy purple
  accents; the main navbar, headers, buttons and footer are rebranded.
- The two-factor authentication page is hardcoded by the framework to load
  the `tenant` theme's CSS, so it keeps the original look.
- Dark mode applies to the navigation shell; legacy module content stays on
  a light background by design.

## Licenses

MyTellPBX theme code: GPLv2 (same as Issabel, adapted from the `tenant`
theme structure). Bundled third-party assets: Tabler (MIT), Tabler Icons
(MIT), Inter (SIL OFL 1.1) — see `theme/THIRD-PARTY-LICENSES.txt`.
