# Optional DAHDI card firmware

The MytelPBX software profile supplies the `dahdi-firmware` package as a
manufacturer firmware importer. The RPM installs the importer and its
verification manifest. The card's firmware files come from the manufacturer.

For a physical card, list the supported releases with
`mytel-dahdi-firmware-install --list`. Obtain the archive for the exact model
from the [Digium firmware downloads](https://downloads.digium.com/pub/telephony/firmware/releases/)
under the manufacturer's terms. Run the importer as root during scheduled
maintenance:

```bash
mytel-dahdi-firmware-install --install /path/to/dahdi-fw-a4a-a0017.tar.gz
```

The importer checks the archive layout and the firmware SHA-256. It places
the verified file in the standard Linux firmware updates directory and
preserves an existing file if its contents differ. Activate the card
according to its manufacturer instructions.

## Build from source

On a Rocky Linux 8 build machine, put `dahdi-firmware.spec` in the
`SPECS` directory of your RPM build tree. Put the importer, `firmware-map.json`
and the repository `LICENSE` renamed to `COPYING` in `SOURCES`. Run
`rpmbuild -ba SPECS/dahdi-firmware.spec` from the build tree with the
`_topdir` macro pointing at that tree. The output includes the binary
and source RPMs. Release signing uses the MytelPBX RPM signing key.
