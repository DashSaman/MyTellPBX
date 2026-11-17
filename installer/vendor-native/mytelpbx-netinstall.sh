#!/bin/bash
# Generated from the pinned Issabel native installer; do not edit.
# MytelPBX / Mytel.one - see provenance.json and derive-native.py.
set -o pipefail
# Based on SAM's Elastix 4 on CentOS 7 Installation and Build Script

BLA_metro=( 0.2 '[    ]' '[=   ]' '[==  ]' '[=== ]' '[ ===]' '[  ==]' '[   =]' )

declare -a BLA_active_loading_animation

BLA::play_loading_animation_loop() {
  while true ; do
    for frame in "${BLA_active_loading_animation[@]}" ; do
      printf "\r%s" "${frame}"
      sleep "${BLA_loading_animation_frame_interval}"
    done
  done
}

BLA::start_loading_animation() {
  BLA_active_loading_animation=( "${@}" )
  # Extract the delay between each frame from array BLA_active_loading_animation
  BLA_loading_animation_frame_interval="${BLA_active_loading_animation[0]}"
  unset "BLA_active_loading_animation[0]"
  tput civis # Hide the terminal cursor
  BLA::play_loading_animation_loop &
  BLA_loading_animation_pid="${!}"
}

BLA::stop_loading_animation() {
  kill "${BLA_loading_animation_pid}" &> /dev/null
  printf "\n"
  tput cnorm # Restore the terminal cursor
  reset
}

#trap BLA::stop_loading_animation SIGINT

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

  echo -en "        Installing base packages "
  BLA::start_loading_animation "${BLA_metro[@]}"
  if ! yum -y install issabel-config_helpers &>>"${MYTEL_NATIVE_WORK}/netinstall.log"; then
    BLA::stop_loading_animation
    return 1
  fi
  BLA::stop_loading_animation
  echo -e "\n"
}

function welcome
{
  echo "welcome" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  dialog --stdout --sleep 2 --backtitle "$BACKTITLE" \
         --infobox " O @ @\n @ @ O\n @ O O\n   O\nMytelPBX\nMytel.one" \
        8 15
}

function sel_astver
{
  ASTVER=$(dialog --no-items --backtitle "$BACKTITLE" \
           --radiolist "Select Asterisk version:" 10 40 3 \
           16  off \
           18  on \
           20  off \
           3>&1 1>&2 2>&3)
  if [ $? -ne 0 ]
  then
    dialog --stdout --sleep 3 --backtitle "$BACKTITLE" \
           --infobox "Install cancelled by user\n\n:(" \
          7 31
    clear
    cleanup
    exit 1
  fi
}

function add_repos
{
cat > /etc/yum.repos.d/Issabel.repo <<EOF || return 1
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

cat > /etc/yum.repos.d/Issabel5.repo <<EOF || return 1
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

cat > /etc/yum.repos.d/commercial-addons.repo <<EOF || return 1
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
dnf install -y https://rpms.remirepo.net/enterprise/remi-release-${ROCKY_VERSION}.rpm  &>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1
"${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/repair-repository-transport.py" || return 1
dnf module enable php:remi-7.4 -y &>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1
dnf config-manager --set-enabled remi &>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1
dnf config-manager --set-enabled powertools &>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1
dnf config-manager --set-enabled devel &>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1
dnf -y check-upgrade &>>"${MYTEL_NATIVE_WORK}/netinstall.log"
local update_status=$?
[ "$update_status" = 0 ] || [ "$update_status" = 100 ] || return "$update_status"
echo "centos $ROCKY_VERSION tweaks end" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
}

function additional_packages
{
  ADDPKGS=""
  OPTS=$(dialog --backtitle "$BACKTITLE" --no-tags \
        --checklist "Choose additional package(s) to install:" 0 0 0 \
        1 "Optional upstream licensed add-ons" on \
        2 "Community Realtime Block List(block SIP attacks from known offenders)" on \
        3 "Sangoma wanpipe drivers" off \
        3>&1 1>&2 2>&3)
  if [ $? -ne 0 ]
  then
    dialog --stdout --sleep 3 --backtitle "$BACKTITLE" \
           --infobox "Install cancelled by user\n\n:(" \
          7 31
    clear
    cleanup
    exit 1
  fi
  for i in $OPTS
  do
    case $i in
      1)
      ADDPKGS="$ADDPKGS issabel-license webconsole issabel-wizard issabel-packet_capture issabel-upnpc \
      issabel-two_factor_auth issabel-theme_designer issabel-network-agent issabel-webphone"
      ;;
      2)
      ADDPKGS="$ADDPKGS issabel-packetbl"
      ;;
      3)
      ADDPKGS="$ADDPKGS wanpipe-utils wanpipe"
      ;;
    esac
  done
}

function yum_gauge
{
  echo "start yum gauge" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  PACKAGES=$1 #Space separated list of packages.
  TITLE=$2 #Window title
  YUMCMD=$3 #install / update
  dialog --backtitle "$BACKTITLE" --title "$TITLE" --gauge "Installing..." 10 75 < <(
   # Get total number of packages
  n=$(echo $PACKAGES | wc -w); 

   # set counter - it will increase every-time a rpm install
   i=0

   #
   # Start the for loop 
   #
   # read each package from $PACKAGES array 
   # $f has filename 
   for p in $PACKAGES
   do
      # calculate progress
      PCT=$(( 100*(++i)/n ))

      # update dialog box 
cat <<EOF
XXX
$PCT
Installing "$p"...
XXX
EOF
    rpm --quiet -q $p
    if [ $? -ne 0 ] || [ "$YUMCMD" = "update" ]
    then
      if ! yum $BETAREPO -y $YUMCMD $p &>>"${MYTEL_NATIVE_WORK}/netinstall.log"
      then
         echo "$p: ERROR installing package" >> "${MYTEL_NATIVE_WORK}/netinstall_errors.txt"
         echo "$p: ERROR installing package" >> "${MYTEL_NATIVE_WORK}/netinstall.log"
      fi
    fi
  done
)
local dialog_status=$?
[ "$dialog_status" = 0 ] || return "$dialog_status"
[ ! -s "${MYTEL_NATIVE_WORK}/netinstall_errors.txt" ] || return 1
echo "end yum gauge" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
}
function update_os
{
  echo "start update os" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  PACKAGES=$(yum $BETAREPO -d 0 list updates | tail -n +2 | cut -d' ' -f1) 2>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1
  if [ "$PACKAGES" = "" ]; then
  echo "no package to upgrade" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  else
      yum_gauge "$PACKAGES" "Yum update" update || return 1
  fi
  echo "end update os" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
}

function clean_yum
{
  echo "Cleaning yum" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  yum clean all &>>"${MYTEL_NATIVE_WORK}/netinstall.log"
}

function install_packages
{
  echo "install packages 1" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  yum clean all &>>"${MYTEL_NATIVE_WORK}/netinstall.log"
  echo "install packages 2" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  PACKAGES=$(cat "${MYTEL_NATIVE_WORK}/inst1.txt")
  echo "install packages 3" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  yum_gauge "$PACKAGES" "(1/2) Please wait..." install || return 1
  echo "install packages 4" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  PACKAGES=$(cat "${MYTEL_NATIVE_WORK}/inst2.txt")
  echo "install packages 5" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
  yum_gauge "$PACKAGES $ADDPKGS" "(2/2) Please wait..." install || return 1
  echo "install packages 6" >>"${MYTEL_NATIVE_WORK}/netinstall.log"
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

function check_dialog
{
  clear
  echo -en "Looking for dialog..."
  if ! dialog  &> /dev/null
  then
    echo -e "[not found]"
    echo -en "        Installing dialog..."
    BLA::start_loading_animation "${BLA_metro[@]}"
    if ! yum -y install dialog &>>"${MYTEL_NATIVE_WORK}/netinstall.log"; then
      BLA::stop_loading_animation
      return 1
    fi
    BLA::stop_loading_animation
    echo -e "\n"
    if [ $? -ne 0 ]
    then
      echo -e "\n***yum install dialog FAILED***\n\n"
    fi
    if ! dialog > /dev/null
    then
      echo -e "Dialog is requiered\n"
      return 1
    fi
  else
    echo -e "[found]"
  fi
}

function enable_beta()
{
  dialog --title "Are you feeling brave?" --defaultno \
  --backtitle "$BACKTITLE" \
  --yesno "Enable Beta repository?(not recommended for production)" 7 60
  if [ $? -eq 0 ]
  then
      return 0
  fi
  return 1
}

function set_passwords()
{
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool completion || return 1
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool passwords || return 1
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool sip || return 1
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool certificate || return 1
  /usr/bin/issabel-admin-passwords --init
}

function select_language()
{
  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool language || return 1
  /usr/bin/issabel-change-language
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
  dialog --stdout --sleep 2 --backtitle "$BACKTITLE" --infobox \
"             O @ @\n             @ @ O\n             @ O O\n               O\n       MytelPBX / Mytel.one \n\nRebooting server, log back in in a minute..." \
  10 35
}
function mytel_addons()
{
  export ASTVER
  bash "${MYTEL_BUNDLE_ROOT}/installer/install-mytel-addons.sh"
}

function mytel_native_step()
{
  "$@"
  local status=$?
  if [ "$status" != 0 ]; then
    printf '\nMytelPBX stopped at %s (status %s). No automatic reboot.\n' "$1" "$status" >&2
    printf 'Native log: %s/netinstall.log\n' "${MYTEL_NATIVE_WORK}" >&2
    exit "$status"
  fi
}

# MYTEL_NATIVE_FLOW
mytel_native_step check_dialog
mytel_native_step add_repos
mytel_native_step settings
mytel_native_step welcome
mytel_native_step select_language
mytel_native_step sel_astver
mytel_native_step additional_packages
mytel_native_step generate_files
#if enable_beta
#then
#    BETAREPO="--enablerepo=issabel-beta"
#fi
mytel_native_step welcome
mytel_native_step centos8_tweaks
mytel_native_step clean_yum
mytel_native_step update_os
mytel_native_step install_packages
mytel_native_step post_install
mytel_native_step set_passwords
mytel_native_step mytel_addons
mytel_native_step cleanup
mytel_native_step bye
mytel_native_step reboot
