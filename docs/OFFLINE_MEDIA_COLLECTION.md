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
