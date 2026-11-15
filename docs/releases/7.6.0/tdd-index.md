# 7.6.0 regression checkpoints

Each meaningful reproduction was executed before its fix. Harness corrections
are recorded separately from product defects. Commit references identify source
checkpoints; final acceptance also checks that the final payload retains their
tested bytes.

| Behavior | RED checkpoint | GREEN checkpoint / check |
|---|---|---|
| Calendar/search/selected-control contrast | `e3a9081` | `c2ce6c2`,28 browser cases |
| Narrow sidebar, Chosen input and mobile keyboard | `eae3b68` | `89d04fc`,12 browser cases |
| Desktop dropdown focus and viewport edges | `e96bc68` | `ff9f78a`,16 cases plus transform/resize proof |
| Dashboard failures, empty/partial feeds, text safety and request ownership | `bfa4fba` | 44 browser cases, native formatted-number and delayed-response fixtures |
| New rollout scope | `a28d859` | `b7a3ae1`,Python policy tests |
| Optional legacy Desk/Phone roots | `d572fd9` | `0495ec4`,exact active roots required |
| ACL dependency and ordering | `e4e214b`,`c7ae5ce` | `e1375ae`,`eea49ba` |
| Native header cache keys | `00f1146` | `2b0fb21`,3 new and37 existing patcher cases |
| Snapshot-derived preparation | `fc579a2` | `05dafce`,private output and input preservation |
| Save/Apply dependency guards | `9d2f676` | `bc66b84`,guard rejection before output |
| Predictable root temporary workspace | `1509eee`,`88d2d1b` | installer private-workspace integration tests |
| Missing helpers, ignored-secret packaging and dirty input | `1294d19` | `c3d138c`,actual Linux bundle tests |
| Clean checkout line-ending drift | `2878914` | `653baa3`,actual Git-blob bundle comparison |
| Missing first-boot credential adapter in archive | `ecd55e9` | `81ea87b`,actual archive payload comparison |
| Desk pin/state/cache integration | `431c2fd`,`6243f01`,`4aa864f`,`13cb3c2`,`3bc5ed8` | `7a43190`,`b027398` |
| Credential transport and exact verification | `3f9ec17`,`b51074b` | `5a1edf7`,actual Bash recording clients and native PHP adapter |

The calendar harness initially required a mini calendar visible on mobile even
though the intended compact layout hides it, and required scrolling even when all
seven columns fitted. `088deae` changes those checks to attached/real weekday
content and fit-or-contained-scroll. Those initial harness failures are not
reported as calendar defects. The bundle CRLF fixture now uses an actual Git
checkout with path-specific attributes; a manual rewrite had a nondeterministic
stat/normalization precondition and was corrected before acceptance.

## Offline commands

Use Linux GNU tools for bundle/workspace tests; Windows skips are not an
equivalent Linux pass. CI runs these in an unprivileged Ubuntu checkout.

```bash
python3 -B -m unittest discover -s tests -v
node --test tests/ui/charts.test.cjs tests/ui/calendar-core.test.cjs
bash -n install-mytellpbx.sh
bash -n scripts/build-installer-bundle.sh
php tests/ui/reload-guard.php admin-fixes/reload-guard.php
php tests/ui/save-result.php admin-fixes/patch-submit.py
php tests/ui/sip-save-transaction.php admin-fixes/sip-save-transaction.php
php tests/ui/desk-launcher.php modules/mytellpbxopdesk/launcher-access.php
php tests/ui/password-init.php installer/password-init.php
```

Browser scripts under `tests/ui/` require authenticated access and appropriate
write-blocking/interception fixtures. Do not run a generic crawler or submit
configuration just to reproduce route coverage. Keep screenshots, native source
snapshots and credentials outside Git.
