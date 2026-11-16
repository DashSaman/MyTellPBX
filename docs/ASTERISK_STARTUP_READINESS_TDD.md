# Native Asterisk cold-start readiness (unreleased patch)

A pristine Rocky 8.10 / Asterisk 20.12 installation exposed a first-start race: the native `Type=simple` unit became active before its control socket existed. The installer made one immediate CLI request and stopped. Roughly one second later the same daemon was reachable, with no restart. This patch waits for actual readiness while keeping the native service lifecycle unchanged.

`stage_framework_init` still starts the native unit once. Its inline Python check uses a monotonic 180-second deadline, caps each read-only unit/CLI subprocess at five seconds, pauses for at most two seconds, and reports elapsed time every 15 seconds. It requires a stable active/running native PID/cgroup with no automatic restart, a recognized Asterisk20 version and the exact supported `core waitfullybooted` success response. Unsupported/empty responses and any zero-exit stderr are rejected. Only CLI clients time out; the helper never starts a second daemon or restarts Asterisk. Framework initialization remains behind successful readiness.

The actual installed CLI help documented `core waitfullybooted`; its measured ready-state response was exit0, empty stderr and `Asterisk has fully booted.`. That observation establishes the command contract, not a measured cold-start duration. The optional prebootstrap `amportal chown` now runs only when its executable exists; an optional command failure retains the prior nonfatal behavior.

## Test-first evidence

- `375a4dd`: the real framework-stage fixture reproduces the old one-shot error when its first synthetic control-socket request fails. Every OS/service/DB operation is intercepted. Expected intercepted bootstrap exit42; old source exits1.
- `b84d39d`: executing the actual optional chown line against an absent local fixture reproduces the missing-executable log noise; the present optional-failure continuation control passes.
- `f3de2ab`: the bounded-wait candidate passes the delayed-start case, while three new strict-response controls reproduce false success for unit/version/full-boot exit0 plus stderr. The final guard rejects those cases.

Validation commands:

```text
python -B -m unittest discover -s tests -p test_installer_asterisk*.py -v
python -B -m unittest discover -s tests -p test_installer_optional_amportal.py -v
python -B -m unittest discover -s tests -p test_*.py
bash -n install-mytellpbx.sh
git diff --check
```

The focused cohort passes21/21 locally. It covers delayed/immediate readiness, blocking full-boot client timeouts, total deadline, elapsed feedback, inactive/unavailable unit, changed PID, automatic restart, wrong cgroup, missing CLI executable, unsupported/empty commands, stderr and log failures, plus one native start before bootstrap. The full local Windows/Python/Git Bash cohort discovers447 tests:364 pass and83 platform-specific cases skip. Bash syntax and diff checks pass.

Standard-library tracing of the actual extracted inline Python across its12 pure probe tests covers65/77 executable source lines (84.42%). This is source-line coverage only, not branch, shell, application or native-environment coverage; separate child-process entry handling is not credited to that figure.

No production/VM action or publication was performed by these tests. Public7.6.1 assets remain immutable. A reviewed private continuation on the already provisioned diagnostic machine, native targeted checks, and a later pristine public patch installation/reboot/rerun are separate acceptance gates. The version and published hashes are intentionally unchanged until the next release candidate is finalized. No Asterisk16/18, PSTN or complete-feature claim follows from this change.
