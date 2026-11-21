# Asterisk 20 RPMs for Rocky Linux 8

The package recipe builds Asterisk 20.12.0 and its 15 runtime and development RPMs. The packaging inputs in `SOURCES` include the publisher's systemd service, log rotation and CDR/ODBC samples from `asterisk18-18.12.0-1.el8.src.rpm` (SHA-256 `8fa57192841c0b94eba6eb1ad7a8d673777c13fad152c84b708f0b7d88e7cd90`). The source RPM produced by this build carries its complete spec, source tarballs, patch and packaging inputs.

`native-layout.tsv` records the file owners, modes, configuration flags and subpackages from the supported native 20.12.0 RPMs. The build selects and verifies 340 source-built Asterisk modules against that inventory. The four optional manufacturer transcoders (Opus, SILK, Siren7 and Siren14) and the Ogg/Opus file helper supplied with the Opus binary are separate manufacturer products. SIP format negotiation and pass-through support for those formats remains in the open-source modules.

The release build requires an x86_64 Rocky Linux 8 environment with the dependencies declared in `asterisk20.spec`. Copy `SOURCES/*` and the following release build inputs into rpmbuild's `SOURCES` directory:

- `asterisk-20.12.0.tar.gz`
- `mytel-asterisk20-native.patch` and `mytel-asterisk20-mp3.tar.gz`
- `pjproject-2.15.1.tar.bz2`, `jansson-2.14.tar.bz2` and `libjwt-1.15.3.tar.gz`

Run the build with an absolute path to the prepared RPM workspace:

```sh
rpmbuild -ba --define "_topdir $top" packaging/asterisk20/asterisk20.spec
python3 packaging/asterisk20/SOURCES/package-layout.py verify \
  packaging/asterisk20/SOURCES/native-layout.tsv "$top/RPMS"
```

The ODBC post-install step preserves existing DSNs and adds the two missing native DSNs. PBX-owned configuration writes run as the Asterisk service account. The native package names, API version, PBX service name and configuration paths are preserved.
