# Main installer and MytelDesk integration evidence

Journeys were derived from the owner's request to ship the current operator
workspace and automatic CPU VAD with the complete PBX installer, while preserving
the existing production system. The base-OS installer is for a fresh supported
server or an exact-source interrupted installation, not an arbitrary PBX updater.

## Executed RED checkpoints

- `431c2fd`: `python -m unittest discover -s tests -p test_installer_desk.py -v`
  executed sixteen cases. Missing stages/source/network contracts produced seven
  assertion failures and ten references to the deliberately missing new bootstrap.
  The Bash stage and source-identity reproducers ran against the real functions;
  all commands that could mutate a host were replaced by disposable sentinels.
- `1509eee`: isolated POSIX tests exercised the real old bundle function. Four
  expected failures reproduced a destination-symlink clobber, an out-of-workspace
  write, adoption of a world-writable workspace and the missing private initializer.
  The valid private-bundle control and all seventy-six existing Python tests passed.
- `6243f01`: `php tests/ui/desk-launcher.php modules/mytellpbxopdesk/launcher-access.php`
  executed under PHP7.4 in a disposable unprivileged sandbox and returned255 for
  the intentionally missing access helper. The existing12 Apply,8 save-result and
 20 SIP-transaction cases passed before this new-feature RED.

## Implementation contracts

| Journey | Reproducer / verification target | Guarantee |
|---|---|---|
| Exact-source retry | `tests/test_installer_desk.py` | Same version/bundle receipt resumes; absent, foreign or older receipts cannot reach mutating stages |
| Bounded verified Desk install | helper tests in the same module | Fixed repository/release pins, full manifest verification, no unsafe tar members, retry after interrupted downloads, no command execution after an unverified download |
| Automatic voice analysis | upstream installer invocation plus `myteldesk doctor` | Reuses the released product's isolated Python/model provisioning and real inference checks; no duplicate VAD implementation |
| Honest progress/success | Bash stage tests | Actual child progress reaches the terminal; failure propagates through tee and never writes a completed-stage marker |
| Scoped root workspace | `tests/test_installer_workspace.py` | Bundle copy/download/extraction stay in a fresh private workspace; ownership, mode, path and symlink checks precede writes; cleanup is scoped |
| Native panel launcher | `tests/ui/desk-launcher.php` | Administrator-only fixed local redirect, explicit guest/denial/unavailable states, read-only ACL handle and parameterized identity lookup; no implicit shared-admin login |

GREEN executed against frozen Git tree `4cf2b0499821c82ac7c79e0197121493b431e6a2`:
Python3.6 passed118/118 with0skips, including the six actual POSIX workspace cases;
PHP7.4 passed54 checks, including fourteen new launcher/readonly-SQLite cases.
The Linux runner was UID65534 with loopback-only networking and PBX/application/
database paths inaccessible. These are isolated fixture checks, not production
mutation or a whole-OS installation. The private source/archive/evidence hashes
are retained by the independent verification lane.

Additional executed RED/GREEN cycles closed cached-execution and source-downgrade
boundaries: the POSIX mutable-payload test and sixth-checksum test initially failed;
`13cb3c2` reproduced a forged cached manifest, implicit newer/foreign Desk takeover
and missing failed-attempt provenance. `3bc5ed8` reproduced treating zero child
exit codes as success without the pinned ready state. The final candidate tree
`e8ffc65b5bf7c259af8f297ba88d14241bb270b6` passed125/125 Python tests with0skips
and all54 PHP checks. This tree also included the release builder's fixture tests.
The actual published Desk archive was extracted and all12938 files verified in
the isolated Linux filesystem, including cache reuse; no downloaded code executed.

The cache's manifest must match the SHA-verified archive manifest; its own rewritten
hash list is not accepted as a trust anchor. Executable cached descendants must
have the effective installer owner's UID and no group/world write permissions.
The real CLI requires root. Newer, unknown or same-version/different-source Desk
states fail before download or command execution. Only explicitly pinned known
older sources may upgrade. A failed ordinary child run records its source intent
and state hash; only that unchanged partial state may resume. Ready-source checks
after doctor prevent false success from exit status alone.

## Operational scope

The complete base-OS installer was not run on the existing production PBX or the
shared test PBXs. No disposable fresh Rocky host was provided for a destructive
whole-OS installation. Stage/command fixtures, syntax checks and isolated runtime
tests establish their documented contracts; they do not establish a fresh OS
installation. Production UI deployment and the already deployed Desk product have
separate hash-bound acceptance receipts.
