# Apply, controls and Jalali calendar repair

The settings UI now distinguishes the selected boolean option with a solid fill,
checkmark and keyboard outline. Restored workspace assets fix the expanded mobile
PBX menu, wide forms/tables and missing shared shell styling. Queues stack form
rows at narrow widths; Voicemail removes its obsolete fixed-sidebar width.
Security switches keep their native plugin behavior with readable ON/OFF colors
and one visible track. PBX settings remain
LTR; Persian shell and calendar remain RTL. Changed asset URLs are versioned.

Apply uses a single request-owned status panel with elapsed time, explicit success,
warning, failure, permission and uncertain-result states. Unrelated AJAX requests
cannot dismiss it. Editable controls are temporarily disabled, including dynamically
inserted autosave fields; navigation and reading are not globally pointer-locked.
The server requires the existing Apply privilege and same-origin XHR proof, serializes
reloads with a lock, releases the authenticated session lock and checks the AMI result
before clearing pending changes. A timeout never automatically repeats a reload.

Calendar month queries cover the complete Jalali grid. Week/day use responsive agenda
cards built from raw civil dates, so a browser's timezone/DST cannot move an event.
Open an event to edit it; use a day's `+` to prepare a new event for that day.
Date entry accepts Persian/Arabic digits, validates actual Jalali month lengths and
uses 24-hour time. Existing IDs, colors and server wall times are preserved. The
configured server timezone is displayed and is not changed by this release.
Save accepts the API's create/update status contract; login HTML is not success.
Explicitly disabling email notifications clears the list; omitted partial-update
fields remain omitted. No database schema, account or telephony setting is migrated.

The unsourced historical holiday list was removed. Friday styling is separate from
official annual holiday coverage; no authoritative holiday dataset is claimed.

## Verification

- Python regressions: 70 tests, 68 passed and 2 platform/tool skips on Windows.
- JavaScript regressions: 11 civil-calendar tests and 5 chart tests passed.
- Intercepted browser Apply: 13 cases passed, including duplicate activation,
  autosave controls, malformed responses, permissions and timeout.
- Intercepted browser calendar: 44 cases passed in Asia/Tehran and
  America/Los_Angeles, including DST gaps, stale responses, invalid dates,
  positive duration, selected views, mutation status and mobile dialog bounds.
- Isolated PHP on the installed runtime: 5 reload-result, 12 guard/permission and
  5 calendar notification-contract tests passed. All persistence/call operations
  are mocked in these tests.
- Detached security-switch fixture: all four theme/width variants passed
  OFF/ON, keyboard focus, one change per click, disabled state and zero writes.
- Changed PHP syntax, both shell script syntax checks and 14 synthetic Smarty
  renders passed. Installer wiring is inspected and syntax-checked; a complete
  new-host installation has not been rehearsed.
- The broad page audit covered 143 routes × four variants (572 documents),
  all HTTP 200 with no page exceptions or document horizontal overflow. The
  mail iframe returned 401; 488 background requests were intentionally blocked.
  This is a render inventory, not a complete functional pass.
- The broad page audit is read-only: GET routes are inspected in light/dark at
  desktop/mobile sizes. Mutating AJAX, actions and WebSockets are blocked, so
  dynamic reports and call operations are not claimed as functionally tested.

See `apply-browser.json`, `calendar-browser.json` and `design-evidence.json`.
Screenshots contain synthetic calendar fixtures. Private host snapshots, credentials,
customer data and the deployment artifact are deliberately excluded from Git.

## Reproduce

```sh
python3 -m unittest discover -s tests -v
node --test tests/ui/charts.test.cjs tests/ui/calendar-core.test.cjs
php tests/ui/reload-guard.php admin-fixes/reload-guard.php
# An installed-source candidate is required for these isolated legacy tests:
php tests/ui/reload-result.php /private/candidate/admin/functions.inc.php
php tests/ui/calendar-rest.php /private/candidate/CalendarEvent.class.php
```

Browser checks require Playwright/Chrome and environment variables `MT_TEST_URL`,
`MT_TEST_USER`, `MT_TEST_PASSWORD`. `apply-flow.cjs` optionally reads
`MT_ADMIN_CANDIDATE`; `calendar-flow.cjs` optionally reads `MT_CANDIDATE` and
`MT_TEST_OUTPUT`. With no candidate override they verify deployed assets while
still intercepting every Apply/calendar mutation.

## Scoped rollout and recovery

`scripts/ui/prepare-scoped.py` builds from private installed-source snapshots and
records every previous/candidate hash. It validates patch anchors before producing
an artifact. Supply the exact Git tree and actual check records; no live write is
performed by preparation. Only the explicit `panel-apply-calendar-v752` profile
permits the named Apply/calendar backend paths. The older UI-only profile remains
unable to write them.

`scripts/ui/rollout.py` requires an independent `TREE` and `READY sha256:` receipt
for the exact manifest and the expected hostname. It backs up every changed file
outside served roots, checks drift again, replaces files atomically and verifies
all hashes. Recovery uses `--rollback /private/backup --expect-hostname HOST`.
Rollback refuses unrelated edits and removes only new manifest files. No service
restart, database mutation or telephony reload is part of asset rollout.

The installer bundle includes the restored workspace assets and the scoped repair
hook. This source update does not publish an untested full installer release.

The detached `tests/ui/security-switch.cjs` check uses `MT_OWNER_ASSETS` for
private copies of the installed jQuery/iButton files and `MT_TEST_OUTPUT` for
its screenshots. It never loads the module autosave script or contacts a server.
