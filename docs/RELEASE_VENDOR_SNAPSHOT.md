# MytelPBX RPM release snapshot

The online installer validates a fixed archive checksum and verifies the
individual RPM signatures. The release manifest records each RPM's NEVRA,
SHA-256, installed role, signer and corresponding source or license notice.
Publish that manifest with the archive and the referenced source assets.

## Build the archive

Use a Linux build machine with Bash, GNU tar, gzip and createrepo_c. Stage the
exact signed runtime files under `Packages/` and the release notices under
`licenses/` as plain text files. Verify the RPMs against the applicable
signing key and compare each checksum to the release manifest. Initiate the
build with the recorded source date epoch:

```bash
bash scripts/build-vendor-release.sh staged-repo \
  output/mytelpbx-vendor-el8-x86_64.tar.gz 1795219200
```

The script generates DNF metadata from the staged RPMs. It normalizes member
ownership, time, permissions and ordering. Use the same versions of GNU tar,
gzip and createrepo_c when reproducing an existing asset. A new RPM signature
changes the asset checksum.

Keep published source RPMs and source archives with the corresponding release.
The vendor snapshot includes the English fallback and Persian voice prompts
with their original notices. The project-built DAHDI firmware importer ships
under its corresponding source RPM. Administrators obtain optional physical
card firmware through the manufacturer's distribution.

## Rebuild the country-data RPM

Use Python 3, Perl with `Text::CSV_XS`, RPM build tools, `cpio` and GNU tar.
The preparation script accepts the reviewed xtables-addons binary RPM, the
November 2026 DB-IP Country Lite CSV archive, the source checkout and a new
build directory. The pinned inputs and the native range converter are
validated before the build tree is prepared.

```bash
python3 scripts/prepare-xtables-country-data.py \
  xtables-addons-3.18-1dkms.x86_64.rpm \
  dbip-country-lite-2026-11.csv.gz . xtables-build
```

Place the original `xtables-addons-3.18.tar.xz` and the release's
`xtables-addons-3.18-1dkms-vendor-source.tar.gz` in `xtables-build/SOURCES`.
Run `rpmbuild -ba` on `xtables-build/SPECS/xtables-addons.spec` with
`_topdir` set to the absolute path of `xtables-build`. The binary RPM retains
the vendor code and kernel-module scriptlets and ships the updated country
database with the DB-IP attribution. The source RPM carries the build inputs.

Use `scripts/prepare-legacy-geoip-country-data.py` with the reviewed
`issabel-geoip-1.6.12-3.x86_64.rpm` and the same DB-IP source to prepare the
legacy C library's package. Add
`geoip-vendor-source-without-legacy-data.tar.gz` to its `SOURCES` and build
`SPECS/issabel-geoip.spec` in the same way. The original converter and C
library verify IPv4 and IPv6 lookups before the package is built.
