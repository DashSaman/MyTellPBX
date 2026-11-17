# Native installer test migration

The 7.7.0 installer uses the supplied, SHA-256-pinned Issabel netinstaller and
original Issabel ISO installation engine. The former custom bootstrap functions,
embedded Python programs, stage markers, password initializer and SIP/GeoIP
adapters are no longer called or shipped. Tests that execute those removed
functions cannot describe the current release. This migration removes their
obsolete contracts explicitly; unittest discovery and CI remain unchanged.

## Recovery

Before removal, the test originals were copied byte-for-byte to the owner's
private `vendor-native-20261117-r1/ci-test-migration-originals` backup. Its
`recovery.json` records every original SHA-256 and the source HEAD commit
`88e2491e22876285bc05a515f6eb78969c9b102d`. The existing
`before-vendor-native.bundle` is the separate all-refs source backup. These private
backups are not release inputs and are not committed.

## Retired whole suites and replacement contracts

All filenames below are relative to `tests/`. Their underlying custom shell
implementation was removed, rather than repaired or simulated inside a test.

| Retired suites | Current responsibility and checks |
| --- | --- |
| `test_installer_asterisk_identity.py`, `test_installer_asterisk_readiness.py`, `test_installer_bootstrap.py`, `test_installer_native_completion.py`, `test_installer_native_platform.py`, `test_installer_optional_amportal.py` | Vendor core owns accounts, database/bootstrap, services and completion. `test_vendor_native_online.py` verifies byte-exact provenance, reproducible derivation, native stage order and stop-before-reboot behavior. `test_native_function_failures.py` injects failures into the actual package/dialog/update, essential post-install and repository functions. `test_native_addons.py` checks actual native identity and pre-existing state before the add-on layer. Native database migrations and call readiness still require target acceptance. |
| `test_installer_credentials.py`, `test_installer_firstboot.py`, `test_installer_hostname.py` | The original native wizard owns password input/validation and native host setup; the custom two-password and hosts-file programs do not exist in this release. Exact dialog-source pins and reversible display-only substitutions are tested by `test_vendor_native_online.py`. `test_native_addons.py` verifies literal read-only credential parsing, stdin-only database credential transport and preservation of unrelated settings. These local tests do not establish real native authentication or hostname resolution. |
| `test_installer_cli_status_wiring.py`, `test_installer_repositories.py`, `test_installer_repository_wiring.py` | The old custom CLI patch, repository catalog and dead-mirror probes are not shipped. Pinned native repository derivation and the current bundle allowlist are tested in `test_vendor_native_online.py` and `test_installer_bundle.py`. The still-used narrow Remi transport helper retains its component tests, and `test_native_function_failures.py` proves it runs before native module operations and that failure is fatal. |
| `test_installer_media_wiring.py` | The native offline path owns the original installation engine. Current `test_vendor_native_iso.py` owns its integration contract. The shared add-on shell carries the sealed media identity unchanged, tested by `test_native_hook_contract.py`; `test_installer_media.py` retains manifest/path/hash validation. Online and ISO use the same post-native add-on hook. |
| `test_installer_native_consumers_wiring.py`, `test_installer_native_geoip_wiring.py`, `test_installer_offline_geoip_wiring.py` | The new product does not run the former SIP/DTLS/GeoIP mutation adapters. The bundle tests require their exclusion. `test_native_geoip_ui.py` verifies the default read-only native evidence path and its explicit unverified lookup/firewall status. Historical custom GeoIP and SIP helper units remain available and are not evidence that those helpers run in 7.7.0. |

## Mixed suites retained and adapted

- `test_installer_desk.py` keeps every standalone Desk helper, archive, identity,
  launcher, upgrade and recovery test. Its eight removed-shell stage/resume tests
  are retired. `test_native_hook_contract.py` instead executes the real native
  hook and exact shared shell for all three Asterisk choices, carries the sealed
  offline identity/public origin, and proves a failed add-on prevents continuation.
- `test_installer_dnf_progress.py` keeps standalone logger parsing, privacy,
  bounds and file-safety units. Four old wrapper/bundler tests are retired because
  the native engine uses its own gauge. Actual native package/dialog failure and
  private log behavior are covered in `test_native_function_failures.py`.
- `test_installer_native_start.py` keeps all helper unit checks. Only the removed
  custom-shell orchestration test is retired; current native flow/provenance and
  failure checks replace that integration assertion.
- `test_installer_repository_transport.py` keeps the helper transform, backup,
  idempotence, drift and symlink checks, plus the current bundle inclusion check.
  Its two removed-shell stage-order tests are replaced by causal native Remi
  ordering/failure tests in `test_native_function_failures.py`.
- `test_installer_bundle.py` now checks exact native/shared-hook payload bytes,
  Desk and license dependencies, exclusion of the retired custom core, and the
  existing clean-source, private-file and CRLF/committed-byte contracts.
- `test_installer_bundle_extraction.py` now executes the current bootstrap's
  `download_bundle` and `extract_bundle`. It retains outer/internal checksum,
  unsafe/duplicate/file-parent/link/special/sparse header, expanded-size,
  pre-existing-output and safe ownership/mode contracts.
- `test_installer_workspace.py` now checks the actual fresh `mktemp` lifecycle,
  refusal to adopt an inherited workspace, preservation of private logs on
  failure, native-child lock lifetime, unchanged local input and source symlink
  refusal. The production entry point creates its own workspace; the removed
  custom workspace-adoption API is not recreated in tests.

Helper unit suites for CLI status, native start/include order, GeoIP, platform
repositories, TLS, WebRTC DTLS, PJSIP, media collection and the historical offline
GeoIP bridge are retained while their source remains. Their passing tests must
not be reported as product wiring or completed installation evidence.

## Verification limits

All replacement execution fixtures use temporary files and stub only host
commands/native execution. They perform no package, service, database, network or
production actions. POSIX ownership, modes, symlinks, flock and GNU bundle build
checks run on Linux; Windows cannot establish those properties. Capability
guards remain specific to those tests. No broad skips or discovery exclusions
were added.

Local test completion is separate from real fresh Rocky 8.10 online installation,
original-ISO offline installation, native password screens/authentication,
service stability, Desk/CPU-VAD doctor checks and real two-way telephony tests.
Those outcomes require recorded checks on the authorized targets before release.

On 2026-11-17, the complete local Windows `python -B -m unittest discover -s
tests -v` run discovered 547 tests: 447 passed, 100 skipped for their recorded
capability requirements, with no failures/errors (39.344 seconds). The private
`ci-test-migration-windows.log` retains the complete output. Native POSIX/root
ownership, flock and real GNU bundle assembly are not established by that run;
they remain Linux checks.
