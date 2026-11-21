#!/bin/bash
# Generated from the pinned Issabel native installer; do not edit.
# MytelPBX / Mytel.one - see provenance.json and derive-native.py.
set -o pipefail
# Based on SAM's Elastix 4 on CentOS 7 Installation and Build Script

function generate_files
{
cat > "${MYTEL_NATIVE_WORK}/inst1.txt" <<EOF || return 1
httpd
httpd-tools
mariadb
mariadb-connector-c
mariadb-connector-odbc
mariadb-server
php
php-bcmath
php-cli
php-common
php-gd
php-IDNA_Convert
php-imap
php-jpgraph
php-magpierss
php-mbstring
php-mcrypt
php-mysqlnd
php-pdo
php-pear
php-pear-DB
php-PHPMailer
php-process
php-simplepie
php-Smarty
php-soap
php-tcpdf
php-tidy
php-xml
asterisk$ASTVER
asterisk$ASTVER-devel
asterisk$ASTVER-curl
asterisk-codec-g729
asterisk-perl
asterisk-es-sounds
asterisk-fr-sounds
asterisk-sounds-en-gsm
asterisk-pt_BR-sounds
certbot
vim
jq
whois
bind-utils
dhcp-server
langpacks-es
langpacks-en
langpacks-pt
langpacks-pt_BR
langpacks-fa
langpacks-fr
mailx
EOF

cat > "${MYTEL_NATIVE_WORK}/inst2.txt" <<EOF || return 1
issabel-geoip
issabel
issabel-prosody-auth
issabel-endpointconfig2
xtables-addons
RoundCubeMail
php-ioncubeloader
libnsl
fop2
EOF
}

function settings
{
  if [ ! "$TERM" = "xterm-256color" ]
  then 
    export NCURSES_NO_UTF8_ACS=1
  fi
  BACKTITLE="MytelPBX netinstall - Mytel.one"
  #Shut off SElinux & Disable firewall if running.
  setenforce 0 &>/dev/null
  sed -i 's/\(^SELINUX=\).*/\SELINUX=disabled/' /etc/selinux/config

  # Some distros may already ship with an existing asterisk group. Create it here
  # if the group does not yet exist (with the -f flag).
  /usr/sbin/groupadd -f -r asterisk &>/dev/null

  # At this point the asterisk group must already exist
  if ! grep -q asterisk: /etc/passwd ; then
      echo -e "Adding new user asterisk..."
      /usr/sbin/useradd -r -g asterisk -c "Asterisk PBX" -s /bin/bash -d /var/lib/asterisk asterisk &>/dev/null
  fi

  mytel_run_dnf repositories yum -y install issabel-config_helpers dialog
}

function sel_astver
{
  # MytelPBX installs the supported Asterisk 20 product only.
  ASTVER=20
}

function add_repos
{
  local repo_dir="${1:-/etc/yum.repos.d}"
cat > "$repo_dir/Issabel.repo" <<EOF || return 1
[issabel-base]
name=Base RPM Repository for MytelPBX
baseurl=https://repo.us.issabel.org/issabel/4/base/\$basearch/
#baseurl=https://repo.us.issabel.org/issabel/4/base/\$basearch/
gpgcheck=0
enabled=1
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-updates]
name=Updates RPM Repository for MytelPBX
baseurl=https://repo.us.issabel.org/issabel/4/updates/\$basearch/
#baseurl=https://repo.us.issabel.org/issabel/4/updates/\$basearch/
gpgcheck=0
enabled=1
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-updates-sources]
name=Updates RPM Repository for MytelPBX
baseurl=https://repo.us.issabel.org/issabel/4/updates/\$basearch/
#baseurl=https://repo.us.issabel.org/issabel/4/updates/SRPMS/
gpgcheck=0
enabled=0
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-beta]
name=Beta RPM Repository for MytelPBX
# Native mirrorlist replaced by the HTTPS baseurl below.
baseurl=https://repo.us.issabel.org/issabel/4/beta/\$basearch/
#gpgcheck=1
enabled=0
#gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-extras]
name=Extras RPM Repository for MytelPBX
baseurl=https://repo.us.issabel.org/issabel/4/extras/\$basearch/
#baseurl=https://repo.us.issabel.org/issabel/4/extras/\$basearch/
gpgcheck=1
enabled=0
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel
EOF

cat > "$repo_dir/Issabel5.repo" <<EOF || return 1
[issabel-cinco]
name=Base RPM Repository for MytelPBX 5
baseurl=https://repo.us.issabel.org/issabel/5/base/\$basearch/
gpgcheck=1
enabled=1
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-noarch]
name=Base RPM Repository for MytelPBX 5 (noarch)
baseurl=https://repo.us.issabel.org/issabel/5/base/noarch/
gpgcheck=1
enabled=1
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-updates]
name=Updates RPM Repository for MytelPBX 5
baseurl=https://repo.us.issabel.org/issabel/5/updates/\$basearch/
gpgcheck=1
enabled=1
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-updates-noarch]
name=Updates RPM Repository for MytelPBX 5 (noarch)
baseurl=https://repo.us.issabel.org/issabel/5/updates/noarch/
gpgcheck=1
enabled=1
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-extras]
name=Extras RPM Repository for MytelPBX 5
baseurl=https://repo.us.issabel.org/issabel/5/extras/\$basearch/
gpgcheck=1
enabled=1
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-extras-noarch]
name=Extras RPM Repository for MytelPBX 5 (noarch)
baseurl=https://repo.us.issabel.org/issabel/5/extras/noarch/
gpgcheck=1
enabled=1
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-beta]
name=Beta RPM Repository for MytelPBX 5
baseurl=https://repo.us.issabel.org/issabel/5/beta/\$basearch/
#gpgcheck=1
enabled=0
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel
EOF

cat > "$repo_dir/commercial-addons.repo" <<EOF || return 1
[commercial-addons]
name=Commercial-Addons RPM Repository for MytelPBX
baseurl=https://repo.us.issabel.org/issabel/5/commercial_addons/\$basearch/
gpgcheck=1
enabled=1
gpgkey=https://repo.us.issabel.org/issabel/RPM-GPG-KEY-Issabel
EOF


}

function centos8_tweaks {

ROCKY_VERSION=$(cat /etc/redhat-release | awk '{print $4}' | awk -F. '{print $1}')

echo "centos $ROCKY_VERSION tweaks start" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
grep -qxF 'fastestmirror=True' /etc/dnf/dnf.conf || echo "fastestmirror=True" >> /etc/dnf/dnf.conf
mytel_run_dnf repositories dnf install -y https://rpms.remirepo.net/enterprise/remi-release-${ROCKY_VERSION}.rpm || return $?
"${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/repair-repository-transport.py" || return 1
mytel_check_repository_sources --enable remi --enable powertools --enable devel || return $?
mytel_run_dnf repositories dnf module enable php:remi-7.4 -y || return $?
dnf config-manager --set-enabled remi &>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1
dnf config-manager --set-enabled powertools &>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1
dnf config-manager --set-enabled devel &>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1
echo "centos $ROCKY_VERSION tweaks end" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
}

function additional_packages
{
  # Install the community SIP block list without selecting licensed add-ons.
  ADDPKGS=issabel-packetbl
}

function update_os
{
  local -a repository_options=()
  IFS=$' \t\n' read -r -a repository_options <<< "${BETAREPO:-}" || :
  mytel_run_dnf update yum "${repository_options[@]}" -y update
}

function install_packages
{
  local packages
  packages=$(cat "${MYTEL_NATIVE_WORK}/inst1.txt") || return $?
  mytel_package_batch "$packages" core || return $?
  packages=$(cat "${MYTEL_NATIVE_WORK}/inst2.txt") || return $?
  mytel_package_batch "$packages $ADDPKGS" product
}

function post_install
{
  (
  systemctl enable mariadb.service || exit 1
  systemctl start mariadb || exit 1
  mysql -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('iSsAbEl.2o17')" || exit 1
  #Shut off SElinux and Firewall. Be sure to configure it in Issabel!
  setenforce 0
  sed -i 's/\(^SELINUX=\).*/\SELINUX=disabled/' /etc/selinux/config
  cp -a /etc/sysconfig/iptables /etc/sysconfig/iptables.org-issabel-"$(/bin/date "+%Y-%m-%d-%H-%M-%S")"
  systemctl enable httpd || exit 1
  systemctl disable firewalld
  systemctl stop firewalld
  firewall-cmd --zone=public --add-port=443/tcp --permanent
  firewall-cmd --reload
  rm -f /etc/issabel.conf
  mysql -piSsAbEl.2o17 -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('')" || exit 1

  #patch config files
  # RPMs can precede native --init: missing pre-init files are not a failure.
  [ -d /etc/asterisk ] && [ ! -L /etc/asterisk ] || exit 1
  for MYTEL_NATIVE_PATH in /etc/asterisk/modules_additional.conf /etc/asterisk/extensions_custom.conf.sample /etc/asterisk/extensions_custom.conf /etc/amportal.conf; do
    if [ -L "$MYTEL_NATIVE_PATH" ] || { [ -e "$MYTEL_NATIVE_PATH" ] && [ ! -f "$MYTEL_NATIVE_PATH" ]; }; then
      printf 'Invalid native configuration path: %s\n' "$MYTEL_NATIVE_PATH" >&2
      exit 1
    fi
  done
  MYTEL_NATIVE_ADD_NOLOAD=1
  if [ -e /etc/asterisk/modules_additional.conf ]; then
    if grep -Fxq -- "noload => cdr_mysql.so" /etc/asterisk/modules_additional.conf; then
      MYTEL_NATIVE_ADD_NOLOAD=0
    else
      [ "$?" = 1 ] || exit 1
    fi
  fi
  if [ "$MYTEL_NATIVE_ADD_NOLOAD" = 1 ]; then
    echo "noload => cdr_mysql.so" >> /etc/asterisk/modules_additional.conf || exit 1
  fi
  mkdir -p /var/log/asterisk
  mkdir -p /var/log/asterisk/cdr-csv
  if [ ! -e /etc/asterisk/extensions_custom.conf ]; then
    if [ -f /etc/asterisk/extensions_custom.conf.sample ]; then
      mv -nT -- /etc/asterisk/extensions_custom.conf.sample /etc/asterisk/extensions_custom.conf || exit 1
      [ -f /etc/asterisk/extensions_custom.conf ] && [ ! -L /etc/asterisk/extensions_custom.conf ] || exit 1
    fi
  fi
  if [ -f /etc/amportal.conf ]; then
    /usr/sbin/amportal chown || exit 1
  fi
  ) &>>"${MYTEL_NATIVE_WORK}/netinstall.log"
}

function check_tools
{
  command -v yum >/dev/null && command -v dnf >/dev/null && command -v rpm >/dev/null
}

function set_passwords()
{
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool completion || return 1
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool passwords || return 1
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool sip || return 1
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool certificate || return 1
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/online-sip.py" "${MYTEL_NATIVE_WORK}" || return 1
  mytel_apply_online_passwords
}

function select_language()
{
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool language || return 1
  # The later online initializer applies the fixed Persian locale.
}

function cleanup()
{
(
  rm -f "${MYTEL_NATIVE_WORK}/inst1.txt"
  rm -f "${MYTEL_NATIVE_WORK}/inst2.txt"
  /usr/sbin/amportal chown
) &> /dev/null
}

function bye()
{
  mytel_terminal_success
}

function mytel_check_repository_sources()
{
  local dnf_python=/usr/libexec/platform-python
  [ -x "$dnf_python" ] || dnf_python="$MYTEL_PYTHON"
  "$dnf_python" -I -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/repository-preflight.py" "${MYTEL_NATIVE_WORK}" "$@"
}

function mytel_check_install_repositories()
{
  local staged
  check_tools || return 1
  staged=$(mktemp -d "${MYTEL_NATIVE_WORK}/planned-repos.XXXXXXXX") || return 1
  add_repos "$staged" || return $?
  mytel_check_repository_sources --staged-repos "$staged" --enable powertools --enable devel     --package-url https://rpms.remirepo.net/enterprise/remi-release-8.rpm
}

function mytel_addons()
{
  [ "${ASTVER:-}" = 20 ] || { printf 'MytelPBX requires native Asterisk 20.\n' >&2; return 1; }
  export ASTVER
  bash "${MYTEL_BUNDLE_ROOT}/installer/install-mytel-addons.sh"
}

function mytel_verify_addons()
{
  # Native cleanup must preserve the registered Mytel integrations and CPU VAD.
  /usr/local/sbin/myteldesk doctor >>"${MYTEL_NATIVE_WORK}/netinstall.log" 2>&1
}

function mytel_native_step()
{
  local started=$SECONDS
  mytel_terminal_phase "$1"
  "$@"
  local status=$?
  mytel_terminal_result "$1" "$status" "$((SECONDS - started))"
  if [ "$status" != 0 ]; then
    printf '\nMytelPBX stopped at %s (status %s). No automatic reboot.\n' "$1" "$status" >&2
    printf 'Native log: %s/netinstall.log\n' "${MYTEL_NATIVE_WORK}" >&2
    exit "$status"
  fi
}

# MYTEL_NATIVE_FLOW
if [ "$#" = 1 ] && [ "$1" = --check-repositories ]; then
  mytel_check_install_repositories
  exit $?
fi
[ "$#" = 0 ] || exit 1
source "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/terminal-ui.sh" || exit 1
source "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/online-credentials.sh" || exit 1
mytel_receive_online_passwords || exit 1
mytel_native_step check_tools
mytel_native_step add_repos
mytel_native_step settings
mytel_native_step select_language
mytel_native_step sel_astver
mytel_native_step additional_packages
mytel_native_step generate_files
mytel_native_step centos8_tweaks
mytel_native_step update_os
mytel_native_step install_packages
mytel_native_step post_install
mytel_native_step set_passwords
mytel_native_step mytel_addons
mytel_native_step cleanup
mytel_native_step mytel_verify_addons
mytel_native_step bye
mytel_native_step reboot
