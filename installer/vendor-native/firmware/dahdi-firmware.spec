Name:           dahdi-firmware
Version:        2.11.1
Release:        2.mytel.el8
Summary:        MytelPBX optional firmware installer for DAHDI hardware
License:        GPLv2+
URL:            https://mytel.one
Source0:        mytel-dahdi-firmware-install
Source1:        firmware-map.json
Source2:        COPYING
BuildArch:      noarch
Requires:       platform-python

%description
Installs the MytelPBX firmware importer for software-only deployments. For
supported physical cards, the administrator can use the importer with a
matching original firmware archive obtained separately from the manufacturer.
Firmware images are supplied by the manufacturer and are distributed separately.

%prep
%build
%install
install -D -m 0755 %{SOURCE0} %{buildroot}%{_sbindir}/mytel-dahdi-firmware-install
install -D -m 0644 %{SOURCE1} %{buildroot}%{_datadir}/mytelpbx/dahdi/firmware-map.json
install -D -m 0644 %{SOURCE2} %{buildroot}%{_licensedir}/%{name}/COPYING

%files
%license %{_licensedir}/%{name}/COPYING
%{_sbindir}/mytel-dahdi-firmware-install
%{_datadir}/mytelpbx/dahdi/firmware-map.json

%changelog
* Sat Nov 21 2026 MytelPBX Packaging <rpm@mytel.one> - 2.11.1-2.mytel.el8
- Install the optional manufacturer firmware importer for software deployments.
