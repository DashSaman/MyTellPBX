# Adapted from the publisher's asterisk18.centos8.spec.
Name: asterisk20
Version: 20.12.0
Release: 3.mytel%{?dist}
Summary: Asterisk 20 telephony platform for MytelPBX
License: GPLv2 and other compatible licenses (see LICENSE)
URL: https://www.asterisk.org/
Source0: asterisk-%{version}.tar.gz
Source1: asterisk-logrotate
Source2: asterisk8.odbc.ini
Source3: cdr_adaptive_odbc.conf
Source4: cdr.conf
Source5: cdr_sqlite3_custom.conf
Source6: asterisk.service
Source7: native-layout.tsv
Source8: package-layout.py
Source9: mytel-asterisk20-mp3.tar.gz
Source10: pjproject-2.15.1.tar.bz2
Source11: jansson-2.14.tar.bz2
Source12: libjwt-1.15.3.tar.gz
Patch0: mytel-asterisk20-native.patch
Provides: asterisk
Provides: asterisk18
Conflicts: asterisk11, asterisk13, asterisk16
BuildRequires: gcc gcc-c++ make binutils patch
BuildRequires: ncurses-devel libxml2-devel libxslt-devel libuuid-devel openssl-devel
BuildRequires: lua-devel iksemel-devel portaudio-devel neon-devel spandsp-devel libical-devel libsrtp-devel
BuildRequires: jack-audio-connection-kit-devel libresample-devel openldap-devel sqlite-devel unixODBC-devel libtool-ltdl-devel
BuildRequires: libopenr2-devel libpri-devel libss7-devel libtonezone-devel dahdi-devel
BuildRequires: libcurl-devel libvorbis-devel libogg-devel speexdsp-devel speex-devel mariadb-connector-c-devel bluez-libs-devel
BuildRequires: freeradius-client-devel codec2-devel unbound-devel libedit-devel libcap-devel
BuildRequires: pkgconfig(gmime-3.0)
BuildRequires: python3 systemd-devel libtool pkgconfig libuv-devel newt-devel bzip2 tar curl xmlstarlet
Requires(post): util-linux
Requires: asterisk-sounds-en-gsm
Requires: asterisk20-addons = %{version}-%{release}
Requires: asterisk20-configs = %{version}-%{release}
Requires: asterisk20-core = %{version}-%{release}
Requires: asterisk20-dahdi = %{version}-%{release}
Requires: asterisk20-doc = %{version}-%{release}
Requires: asterisk20-odbc = %{version}-%{release}
Requires: asterisk20-resample = %{version}-%{release}
Requires: asterisk20-voicemail = %{version}-%{release}
Requires: freeradius
Requires: iksemel
Requires: jack-audio-connection-kit
Requires: libical
Requires: libresample
Requires: libsrtp
Requires: libtool-ltdl
Requires: libxml2
Requires: lua
Requires: neon
Requires: openldap
Requires: portaudio
Requires: spandsp
Requires: sqlite
Requires: unixODBC

%description
Asterisk 20 PBX with MytelPBX package integration and open-source media modules.

%package addons
Summary: Asterisk-addons package.
Requires: asterisk20-addons-bluetooth = %{version}-%{release}
Requires: asterisk20-addons-core = %{version}-%{release}
Requires: asterisk20-addons-mysql = %{version}-%{release}
Requires: asterisk20-addons-ooh323 = %{version}-%{release}
Requires: asterisk20-core = %{version}-%{release}
Requires: bluez-libs
Requires: mariadb

%description addons
Asterisk-addons package..

%package addons-bluetooth
Summary: bluetooth modules for Asterisk
Requires: asterisk20-core = %{version}-%{release}
Requires: bluez-libs

%description addons-bluetooth
bluetooth modules for Asterisk.

%package addons-core
Summary: Asterisk-addons core package.
Requires: asterisk20-core = %{version}-%{release}

%description addons-core
Asterisk-addons core package..

%package addons-mysql
Summary: mysql modules for Asterisk
Requires: asterisk20-addons-core = %{version}-%{release}
Requires: asterisk20-core = %{version}-%{release}
Requires: mariadb

%description addons-mysql
mysql modules for Asterisk.

%package addons-ooh323
Summary: chan_ooh323 module for Asterisk
Requires: asterisk20-core = %{version}-%{release}

%description addons-ooh323
chan_ooh323 module for Asterisk.

%package configs
Requires(post): util-linux
Summary: Basic configuration files for Asterisk
Requires: asterisk20-core = %{version}-%{release}

%description configs
Basic configuration files for Asterisk.

%package core
Requires(pre): shadow-utils
Requires(post): util-linux
Summary: Asterisk core package without any "extras".
Requires: asterisk20 = %{version}-%{release}
Requires: libxml2

%description core
Asterisk core package without any "extras"..

%package curl
Summary: cURL application module for Asterisk
Requires: asterisk20-core = %{version}-%{release}
Requires: curl

%description curl
cURL application module for Asterisk.

%package dahdi
Summary: DAHDI channel driver for Asterisk
Requires: asterisk20-core = %{version}-%{release}
Requires: dahdi-linux
Requires: libopenr2
Requires: libpri
Requires: libss7
Requires: libtonezone

%description dahdi
DAHDI channel driver for Asterisk.

%package devel
Summary: Static libraries and header files for Asterisk development
Requires: asterisk20-core = %{version}-%{release}

%description devel
Static libraries and header files for Asterisk development.

%package doc
Summary: Documentation files for Asterisk
Requires: asterisk20-core = %{version}-%{release}

%description doc
Documentation files for Asterisk.

%package odbc
Summary: Open Database Connectivity (ODBC) drivers for Asterisk
Requires: asterisk20-core = %{version}-%{release}
Requires: mariadb-connector-odbc >= 3.1.12
Requires: unixODBC

%description odbc
Open Database Connectivity (ODBC) drivers for Asterisk.

%package resample
Summary: resampling codec module for Asterisk
Requires: asterisk20-core = %{version}-%{release}
Requires: libresample

%description resample
resampling codec module for Asterisk.

%package voicemail
Summary: Voicemail with file storage module for Asterisk
Requires: asterisk20-core = %{version}-%{release}

%description voicemail
Voicemail with file storage module for Asterisk.

%prep
%setup -q -n asterisk-%{version}
%patch -P 0 -p1
tar -xzf %{SOURCE9}
mkdir -p .build-cache
cp %{SOURCE10} %{SOURCE11} %{SOURCE12} .build-cache/

%build
echo %{version} > .version
export AST_DOWNLOAD_CACHE="$PWD/.build-cache"
./configure --libdir=%{_libdir} --with-pjproject-bundled --with-jansson-bundled --with-libjwt-bundled
make menuselect.makeopts
python3 %{SOURCE8} select %{SOURCE7}
make OPT=-fPIC %{?_smp_mflags}

%install
export AST_DOWNLOAD_CACHE="$PWD/.build-cache"
for target in install samples install-headers; do
    make DESTDIR="%{buildroot}" "$target"
done
# Set the intended fresh-install default in the RPM payload. The configs
# scriptlet may run before the core package owns /etc/asterisk.
sample="%{buildroot}/etc/asterisk/asterisk.conf"
test "$(grep -c '^;execincludes = yes\([[:space:]]\|$\)' "$sample")" = 1
sed -i 's/^;execincludes = yes/execincludes = yes/' "$sample"
grep -q '^execincludes = yes\([[:space:]]\|$\)' "$sample"
install -Dpm0644 %{SOURCE6} %{buildroot}/usr/lib/systemd/system/asterisk.service
install -Dpm0644 %{SOURCE1} %{buildroot}/etc/logrotate.d/asterisk
install -Dpm0644 %{SOURCE2} %{buildroot}/etc/asterisk8.odbc.ini
install -pm0644 %{SOURCE3} %{buildroot}/etc/asterisk/cdr_adaptive_odbc.conf
install -pm0644 %{SOURCE4} %{buildroot}/etc/asterisk/cdr.conf
install -pm0644 %{SOURCE5} %{buildroot}/etc/asterisk/cdr_sqlite3_custom.conf
install -d %{buildroot}/etc/sysconfig
printf '%s\n' AST_USER=asterisk AST_GROUP=asterisk COREDUMP=yes COLOR=yes > %{buildroot}/etc/sysconfig/asterisk
# These upstream helpers are Python 3 compatible. Verify them with the
# installed interpreter before EL8's normal brp-mangle-shebangs pass.
for name in reflocks refstats refcounter; do
    script="%{buildroot}/var/lib/asterisk/scripts/$name.py"
    grep -qx '#!/usr/bin/env python' "$script"
    sed -i '1s|^#!/usr/bin/env python$|#!/usr/bin/python3|' "$script"
    python3 -B "$script" --help >/dev/null
done
python3 %{SOURCE8} stage %{SOURCE7} %{buildroot} %{_builddir}

%pre core
getent group asterisk >/dev/null || groupadd -r asterisk
getent passwd asterisk >/dev/null || useradd -r -g asterisk -c "Asterisk PBX" -s /bin/bash -d /var/lib/asterisk asterisk

%post core
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl enable asterisk >/dev/null 2>&1 || :
if [ ! -e /var/log/asterisk ]; then install -d -o asterisk -g asterisk /var/log/asterisk; fi
runuser -u asterisk -- mkdir -p /var/spool/asterisk/monitor /var/log/asterisk/cdr-csv /var/log/asterisk/cdr-custom

%post
runuser -u asterisk -- /bin/sh <<'AST_POST'
for saved in /etc/asterisk/*.rpmsave; do
    [ -f "$saved" ] || continue
    [ -e "${saved%.rpmsave}" ] || mv -n -- "$saved" "${saved%.rpmsave}"
done
modules=/etc/asterisk/modules_additional.conf
grep -qxF 'noload => cdr_mysql.so' "$modules" 2>/dev/null || printf '%s\n' 'noload => cdr_mysql.so' >> "$modules"
AST_POST
if [ "$1" = 1 ] && [ ! -f /tmp/issabelinstall ]; then systemctl start asterisk.service || :; fi

%post configs
runuser -u asterisk -- /bin/sh <<'AST_CONFIG'
if [ -f /etc/asterisk/modules_custom.conf ] && ! grep -qxF 'noload => cdr_mysql.so' /etc/asterisk/modules_custom.conf; then
    printf '%s\n' 'noload => cdr_mysql.so' >> /etc/asterisk/modules_custom.conf
fi
AST_CONFIG

%post odbc
if [ -f /etc/asterisk8.odbc.ini ]; then
    for section in MySQL-asteriskcdrdb asterisk; do
        if ! grep -Fxq "[$section]" /etc/odbc.ini 2>/dev/null; then
            awk -v wanted="[$section]" '/^\[/{active=($0 == wanted)} active {print}' /etc/asterisk8.odbc.ini >> /etc/odbc.ini
        fi
    done
fi

%files -f %{_builddir}/asterisk20.files

%files addons -f %{_builddir}/asterisk20-addons.files

%files addons-bluetooth -f %{_builddir}/asterisk20-addons-bluetooth.files

%files addons-core -f %{_builddir}/asterisk20-addons-core.files

%files addons-mysql -f %{_builddir}/asterisk20-addons-mysql.files

%files addons-ooh323 -f %{_builddir}/asterisk20-addons-ooh323.files

%files configs -f %{_builddir}/asterisk20-configs.files

%files core -f %{_builddir}/asterisk20-core.files
%license COPYING LICENSE
%doc CREDITS

%files curl -f %{_builddir}/asterisk20-curl.files

%files dahdi -f %{_builddir}/asterisk20-dahdi.files

%files devel -f %{_builddir}/asterisk20-devel.files

%files doc -f %{_builddir}/asterisk20-doc.files

%files odbc -f %{_builddir}/asterisk20-odbc.files

%files resample -f %{_builddir}/asterisk20-resample.files

%files voicemail -f %{_builddir}/asterisk20-voicemail.files
