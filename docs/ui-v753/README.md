# Native SIP Submit and persistent Apply feedback

The parent shell retained an Apply success card after the PBX iframe navigated,
but its close callback belonged to the destroyed iframe. The regression test
reproduced this after both ordinary iframe navigation and native SIP Submit.
Feedback rendering, close events, elapsed timers and save watchdogs now execute
in the document that owns the card. A singleton Apply adapter retains single-flight
requests and treats an interrupted result as unknown without automatic retries.

SIP Settings continues to use its native POST, validators and successful controls.
A save adapter adds progress, duplicate protection and Save/Apply mutual exclusion.
It does not disable fields before serialization or store form values. The response
must carry a fresh marker matching the random attempt token; HTTP 200, an old
flash message or an unrelated document is insufficient to report success. The
parent watchdog handles login, absent results and timeouts, including a native
204 response that leaves the old document alive. Completed feedback is dismissible
after iframe navigation; starting a new save removes stale completed Apply feedback.

A real pre-change native Submit took about 6.9 seconds to return. It sent one
POST; no duplicate native handlers were established by the read-only trace.
The opaque iframe loader and lack of immediate save feedback explain the visible
wait. This release suppresses that loader only during the owned SIP save.

The installed SIP table uses InnoDB and contains 77 rows. PEAR executeMultiple
executes rows individually under autocommit, making repeated durable writes a
plausible latency contributor. The existing DELETE/INSERT table replacement now
takes one transaction only when InnoDB, driver autocommit and server transaction
state prove ownership. It leaves existing transactions and unverified engines
under their previous owner. Raw COMMIT preserves its actual result; the installed
PEAR commit wrapper could replace that result with a later SET. An owned failure
rolls back the table replacement and never reports success. No global database
durability or server configuration is changed.

## TDD and verification

- `fccddbf`: lifecycle RED, two expected failures after native navigation/Submit.
- `ec7d203`: native-save RED, 11 expected failures in 14 initial cases.
- `d90fa28`: parent feedback/native save implementation; lifecycle 12/12,
  Save 18/18 with the real feedback component, and existing Apply 13/13 passed.
- `3a8304e`: transaction RED adapter demonstrated absent atomic replacement and
  owned-commit guarantees; nine of 20 contract cases passed before the helper.
  The new helper passes 20/20 on isolated PHP 7.4 using a fake DB. This is not
  fault injection against production, nor a claim that the legacy sql() wrapper
  ignored every DELETE error simulated by the simplified adapter.
- Attempt-result boundaries: eight isolated PHP cases passed. Patcher/profile,
  existing rollback and UI contracts: 76 Python cases, 74 passed and two Windows
  platform/tool skips. Node calendar/chart regressions: 16 passed.
- Save-specific V8 executed source-offset coverage measured 93.22%; this is not
  a branch or statement coverage figure for the application.

Browser/native test scripts: `tests/ui/toast-lifecycle.cjs`, `save-flow.cjs` and
`apply-flow.cjs`. They intercept configuration writes and reloads. Set Playwright
through NODE_PATH if needed; credentials are process environment inputs only.
The detached Save test requires MT_SAVE_JQUERY, MT_TEST_OUTPUT and
MT_SAVE_REAL_FEEDBACK=1. Isolated PHP checks:

```sh
php tests/ui/save-result.php admin-fixes/patch-submit.py
php tests/ui/sip-save-transaction.php admin-fixes/sip-save-transaction.php
```

`scripts/ui/prepare-submit.py` produces a private, eight-path artifact from current
installed snapshots. The opt-in `panel-submit-apply-v753` profile requires native
save, lifecycle and transaction evidence in addition to existing checks. It cannot
write trunks, credentials, unrelated PBX backends, calendars, desk or phone files.
Independent READY binds its exact tree/manifest before publication/deployment;
rollout preserves hash drift checks, private backups and journaled rollback.

The target acceptance record must separately include native NAT Submit/Apply,
closing feedback after iframe navigation, original-settings restoration and
service health. Local tests or a merged PR do not establish those outcomes.
