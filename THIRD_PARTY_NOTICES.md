# Third-Party Notices — MyTellPBX

MyTellPBX is a Persian RTL theme, branding and integration layer on top of
open-source telephony software. This product includes and depends on the
following third-party software; all trademarks belong to their respective
owners. Functional package names, repository identities and license records
are preserved verbatim.

## Telephony platform (installed by the installer)

- **Asterisk 20** — PBX engine. Dual GPL/Commercial license, Sangoma
  Technologies. Functional RPM identities: `asterisk20`.
- **Issabel 5 (IssabelPBX)** — open-source unified communications platform
  (GPLv2), used as the telephony web framework underneath the MyTellPBX
  theme and branding layer. Project site: issabel.org. The MyTellPBX
  installer configures the upstream package repositories and RPM identities
  unchanged so that dependency resolution and updates keep working.
- **FreePBX modules** (framework, core, queues, IVR, ...) — GPLv3+,
  distributed by the Issabel 5 framework.
- **MariaDB 10.3** — GPLv2, database engine.
- **Apache HTTP Server (httpd)** — Apache License 2.0.
- **PHP 7.4 (Remi repository build)** — PHP License v3.01. PHP 7.4 reached
  upstream end-of-life in November 2022; it is retained here solely because
  the telephony framework requires it. See docs/INSTALL.en.md for the
  security implications.
- **FOP2** — Flash Operator Panel 2 (commercial license, free for two
  operators), installed as part of the base platform.
- **Roundcube** — GPLv3+, webmail included with the base platform.
- **certbot** — Apache/GPLv2, for Let's Encrypt certificates.

## Fonts

- **Vazirmatn** — SIL Open Font License 1.1, by Saber Rastikerdar.
  Shipped locally for both the panel theme and the admin console skin.

## Front-end libraries (bundled inside the theme)

- jQuery, Bootstrap 3 (JS), ECharts, Font Awesome 4 (subset),
  DataTables language files — MIT/GPL licenses as noted in
  `theme/THIRD-PARTY-LICENSES.txt`.

## Trademarks

"MyTellPBX" and the MyTel brand are used by the MyTel project (mytel.one).
All other product names are trademarks of their respective owners and are
used only to identify compatibility.
