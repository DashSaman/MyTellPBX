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
- **FOP2** — Flash Operator Panel 2 (commercial license; free/demo mode exposes
  up to 15 configured buttons), installed as part of the base platform.
  [Vendor licensing/installation reference](https://www.fop2.com/docs/installation.php).
- **Roundcube** — GPLv3+, webmail included with the base platform.
- **certbot** — Apache/GPLv2, for Let's Encrypt certificates.

## Separately installed operator workspace

- **MytelDesk 1.1.3**, a GPLv3 derivative of OpDesk, is installed as an independent
  service from its checksum-pinned [public release](https://github.com/DashSaman/MytelDesk/releases/tag/v1.1.3).
  That release includes its complete corresponding source and dependency notices.
- Its CPU VAD component retains the Silero model's MIT notice and the notices of
  the locked NumPy, ONNXRuntime, WebRTC VAD and other Python wheels. The model and
  dependencies are supplied by that separate release/runtime, not relicensed by
  the PBX theme. See [the VAD notices](https://github.com/DashSaman/MytelDesk/blob/main/docs/vad-third-party.md).

## Optional Asternic report integration

- **Asternic CDR Reports Open Source 1.6.6** is a separately installed GPLv3
  IssabelPBX module, distinct from the vendor's commercial standalone product.
  [Official download/license statement](https://www.asternic.net/cdrreports/download.php),
  [upstream source](https://github.com/asternic/asternic-cdr-module).
- The direction helper and scoped source patcher in `admin-fixes/` are GPLv3;
  retain [the accompanying license](admin-fixes/licenses/GPL-3.0.txt). The full
  customized module and any production records are not bundled here. The
  integration does not change the license of the separately maintained theme.

## Native IP country data and legacy GeoIP assets

- The 7.7.0 native installation uses the upstream GeoIP installation/data state.
  The Mytel page reports that state; it does not run the legacy DB-IP downloader
  or range converter.
- Retained legacy GeoIP tools support **DB-IP Country Lite**. The data is
  licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
  with attribution to [DB-IP](https://db-ip.com). Free data has reduced
  coverage and accuracy; an IP location is approximate.
- When used separately, those legacy tools validate and convert ranges into the
  network-byte-order files required by xtables. Their dataset provenance includes
  the source URL, SHA-256, conversion manifest and attribution notice. Retain the
  DB-IP attribution link on pages using those country results.
- The existing xtables builder and consumer retain their upstream GPL notices.
  The legacy updater does not add, remove or reload firewall rules.

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
