# Collecting the ISO depot

Run this builder only on an explicitly identified disposable Rocky Linux8.10
x86_64 lab. It never installs RPMs or changes services, live databases, repository
configuration, or an existing output. The operator prepares the native DNF4
Python bindings, `rpm`, `rpmkeys`, `createrepo_c` and `modifyrepo_c` beforehand.
Use `/usr/libexec/platform-python`; the parallel VAD Python3.11 does not normally
contain DNF's native bindings.

The bootstrap, PBX bundle and Desk archive must be the exact reviewed release
files. The collector reads the bundle checksum from the bootstrap, the Desk pin
and package lists from that bundle, and the Node/wheel pins from that Desk
archive. It does not follow a latest-release pointer. Keep the original upstream
licenses, notices and RPM identities.

First run without `--execute` to inspect the inert plan. Repeat the same command
with the final three execution flags only after reviewing the machine identity:

```sh
/usr/libexec/platform-python -B scripts/collect-installer-media.py \
  --bootstrap /root/iso/releases/install-mytellpbx.sh \
  --bundle /root/iso/releases/mytelpbx-bundle-7.6.2.tgz \
  --desk-archive /root/iso/releases/myteldesk-1.1.2.tar.gz \
  --kernel-release EXACT_ISO_INSTALLED_KERNEL_RELEASE \
  --repo baseos --repo appstream --repo extras --repo powertools \
  --repo epel --repo remi-safe --repo remi-modular \
  --repo REVIEWED_ISSABEL_REPOSITORY_ID \
  --output /root/iso/mytelpbx-depot \
  --geoip-month YYYY-MM \
  --execute --confirm-disposable-lab --lab-machine-id EXACT_LAB_MACHINE_ID
```

Repository IDs above are examples: supply the actual reviewed configured IDs,
including every repository needed by this profile. Sources must use public HTTPS
or local media, never embedded credentials or HTTP fallback. For an older ISO
kernel, expose its original signed RPM repository as an additional explicit
source; do not substitute the currently cached latest kernel. The collector
requests the exact kernel/core/modules/devel/headers versions, Python3.11/pip,
tar/xz, the minimal OS environment and both installer package lists.
DNF leaves `file://` RPMs on the original media; the collector explicitly copies
only selected stable bytes into the new depot and rejects filename collisions.
Original DVD/cache RPMs are never modified.

DNF resolves from an empty **private** installroot, not the lab's installed RPM
inventory. Both source and local-only solvers enable `install_weak_deps=True`,
matching the supported native online profile and retaining recommended feature
packages. Only the resolved dependency closure is downloaded. Packages are kept
per source repository; original modulemd and comps are added to the generated
metadata. In particular, `php:remi-7.4` must remain available. A second fresh
local-only resolve must select the same complete NEVRA set and retain the same
module/group metadata. Merely running `createrepo_c` over some RPM files is not a
successful closure proof.

All RPMs must have a real valid digital signature against the collected public
repository keys. Keys are imported only into a private RPM database. Unsigned
packages, unknown keys, bad signatures or missing dependencies stop collection;
the collector never disables checking or signs packages itself.

`--cache-dir` optionally supplies public Node/wheel files by their original
filename. Existing cache files must match the release pins; corrupt files stop
instead of being silently adopted. Cached GeoIP data additionally needs
`--geoip-sha256`; otherwise the dated public monthly source is downloaded.
Its actual month is retained. The Silero model is already inside the Desk archive.
The depot also includes `geoip/countryInfo.txt` and GeoNames CC BY 4.0 attribution.
Cached country metadata requires its own `--country-info-sha256` pin. Both public
country assets are listed and hashed by `manifest.files`; no manifest schema is
changed.

The offline installer prepares a narrowly scoped `/etc/geoip_key.conf` bridge
before the signed `issabel-geoip` RPM runs its postscript. Only the reviewed cron
and its exact DB-IP/GeoNames transport arguments receive verified cached bytes;
all other requests refuse without network fallback. The cached DB-IP month is
explicit in the receipt even if the native cron requested the current month.
There is no clock override, skipped RPM scriptlet, global command replacement or
changed RPM. Existing operator configuration is retained by refusal.

After the native converters run, `--handoff` verifies both legacy country tables
with eight real libGeoIP country controls against the pinned CSV. The native
temporary DAT outputs must have been absent before preparation and must exactly
match the activated DAT bytes; a short conversion cannot retain an old table as
success. It preserves the complete native
xtables output, and leaves an empty directory for the existing managed updater.
`--finish` requires the managed release to validate and the native legacy tables
to remain identical before restoring only the originally absent configuration.
The preserved native outputs remain in the private backup. A failed/interrupted
phase keeps its receipt and inputs for scoped repair; it is not installation proof.

The output is sealed with the agreed `manifest.json` only after all checks pass.
Its SHA-256 must be embedded literally by the ISO launcher. The private sibling
`.OUTPUT_NAME-collector` contains the resolver roots, diagnostic log and fixed
phase/status metadata. Retain failed output and diagnostics for inspection;
do not label a partial directory ready or overwrite it with a blind retry.

The manifest, NEVRA/signature inventory and source data hashes make the collected
inputs reviewable and repeatable. Updated upstream repositories may resolve a
different closure; keep the accepted depot immutable. This collector is not an
ISO boot or call-test result. The ISO must still prove a real network-disabled
installation, matching kernel/GeoIP readiness, reboot and application/media paths.
