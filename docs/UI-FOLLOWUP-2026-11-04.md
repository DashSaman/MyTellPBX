# UI completion follow-up (v7.4.1)

The owner requested completion of the previously reported limitations without
repeating successful work. The production contract remains UI-only.

## Root causes and bounded changes

| Finding | Cause / resolution |
| --- | --- |
| Four aggregate Desk interaction failures | Dynamic `new Audio('/sounds/...')` URLs ignored Vite's `/MytellDesk/` base. All four ringtone/dialing/hangup URL sites now use `import.meta.env.BASE_URL`; the existing WAVs already return 200 at the correct base. Call and autoplay behavior are untouched. |
| Control-panel `t.removeClass` | colResizable stores tables in an array and enumerates inherited Ember methods on resize. Only its resize loop is changed to visit own registry entries; registered tables still resize. |
| GeoIP `visualLatitude` | The asynchronous home-location fallback dereferenced a missing/removed polygon. Both fallback branches return when no polygon is available, without inventing coordinates. |
| Asternic stylesheet 404 | The sheet's relative import resolved against `/admin/config.php?handler=file`. The existing module stylesheet is now referenced by its actual absolute path. |
| Codec API 404 | The authenticated response explicitly states “Codec settings are only available on FreePBX”. This Issabel installation does not expose that capability; no fake success or backend codec/reload implementation is added. |
| Webmail 401 | The embedded response is Roundcube's independent login form. Mailbox authentication/operation needs a designated test mailbox; panel credentials are not reused or reset. |

Only two exact legacy paths are added to the rollout allowlist under the HTML
root: `libs/js/jquery/jquery-upl-colResizable-1.5.min.js` and
`modules/sec_geoip_map/themes/default/map.tpl`. The admin root also permits the
one Asternic CSS file; the Desk root permits the audio URL source patch. Backend
PHP, credentials, Asterisk configuration and call-control paths remain excluded.
Installed customizations outside the exact replacement anchors are preserved;
unrecognized anchors fail closed.

## Reproducible checks and evidence policy

```text
python -B -m unittest discover -s tests -v
node --check tests/ui/audit.cjs
node --check tests/ui/interactions.cjs
```

`scripts/ui/prepare.py` builds an incremental artifact from installed hash-guarded
inputs with the existing toolchain. It also checks the patched legacy JavaScript
syntax. Offline regressions cover Ember-style inherited array entries, actual
table visits, both GeoIP fallbacks, idempotence, Vite audio paths, incremental
artifact preview and safe failure recording on document-fetch timeout.

Use the existing external browser credentials; never publish sessions, raw logs,
screenshots or installed-source copies. Candidate tests must use the exact
artifact's browser-local response overrides. Scope the legacy audit with
`MT_INCLUDE=panel:control_panel,panel:sec_geoip_map,panel:fail2ban,panel:asternic_cdr`.
Select only the four previously failed Desk checks with
`MT_INTERACTION_INCLUDE=desk keyboard theme and persistence` when running
`tests/ui/interactions.cjs`. An empty selection, any actual resource/JavaScript
failure, write attempt or route error still fails the command.

The previous mobile audit completed 261 of 350 cases. Its exact remaining 89
dark/390 cases are derived from the saved inventory and case keys, not a newly
expanded inventory. Run only that missing set, plus targeted checks needed for
these changed assets. Distinguish completed coverage from passing coverage and
do not relabel historical receipts as an all-green final-artifact audit.

Publication/apply requires an independent READY for the exact final tree and
manifest, passing CI, before-hash validation and backups. Verify actual live
pages without overrides and every changed hash after apply. Existing safeguards
block non-GET and WebSockets; actual calls, SIP/AMI connectivity and authenticated
mailbox operation remain untested unless separately authorized and provisioned.
