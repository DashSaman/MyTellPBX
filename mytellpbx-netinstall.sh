#!/bin/bash
# ==========================================================================
# MyTellPBX netinstall - Issabel 5 base + MyTellPBX Tabler theme
# Modeled on the official Issabel 5 netinstall script:
#   http://repo.issabel.org/issabel5-netinstall.sh
# The telephony base install (repos, packages, post-install) is identical
# to upstream; only branding and the final MyTellPBX theme step were added.
#
# Usage (download, review, then run):
#   curl -fsSL https://raw.githubusercontent.com/DashSaman/MyTellPBX/main/mytellpbx-netinstall.sh -o mytellpbx-netinstall.sh
#   bash mytellpbx-netinstall.sh
# ==========================================================================

MYTELL_GITHUB_REPO="DashSaman/MyTellPBX"
MYTELL_THEME_VERSION="v1.0.0"

BLA_metro=( 0.2 '[    ]' '[=   ]' '[==  ]' '[=== ]' '[ ===]' '[  ==]' '[   =]' )

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
  BLA_loading_animation_frame_interval="${BLA_active_loading_animation[0]}"
  unset "BLA_active_loading_animation[0]"
  tput civis
  BLA::play_loading_animation_loop &
  BLA_loading_animation_pid="${!}"
}

BLA::stop_loading_animation() {
  kill "${BLA_loading_animation_pid}" &> /dev/null
  printf "\n"
  tput cnorm
  reset
}

#trap BLA::stop_loading_animation SIGINT

function generate_files
{
cat > /tmp/inst1.txt <<EOF
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

cat > /tmp/inst2.txt <<EOF
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
  BACKTITLE="MyTellPBX 5 netinstall (Issabel 5 base)"
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
  yum -y install issabel-config_helpers &> /dev/null
  BLA::stop_loading_animation
  echo -e "\n"
}

function welcome
{
  echo "welcome" >>/tmp/netinstall.log
  dialog --stdout --sleep 2 --backtitle "$BACKTITLE" \
         --infobox " O @ @\n @ @ O\n @ O O\n   O\nMyTellPBX" \
        7 12
}

function sel_astver
{
  ASTVER=$(dialog --no-items --backtitle "$BACKTITLE" \
           --radiolist "Select Asterisk version:" 10 40 2 \
           16  on \
           18  off \
           3>&1 1>&2 2>&3)
  if [ $? -ne 0 ]
  then
    dialog --stdout --sleep 3 --backtitle "$BACKTITLE" \
           --infobox "Install cancelled by user\n\n:(" \
          7 31
    clear
    cleanup
    exit
  fi
}

function add_repos
{
cat > /etc/yum.repos.d/Issabel.repo <<EOF
[issabel-base]
name=Base RPM Repository for Issabel
mirrorlist=http://mirror.issabel.org/?release=4&arch=\$basearch&repo=base
#baseurl=http://repo.issabel.org/issabel/4/base/\$basearch/
gpgcheck=0
enabled=1
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-updates]
name=Updates RPM Repository for Issabel
mirrorlist=http://mirror.issabel.org/?release=4&arch=\$basearch&repo=updates
#baseurl=http://repo.issabel.org/issabel/4/updates/\$basearch/
gpgcheck=0
enabled=1
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-updates-sources]
name=Updates RPM Repository for Issabel
mirrorlist=http://mirror.issabel.org/?release=4&arch=\$basearch&repo=updates
#baseurl=http://repo.issabel.org/issabel/4/updates/SRPMS/
gpgcheck=0
enabled=0
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-beta]
name=Beta RPM Repository for Issabel
mirrorlist=http://mirror.issabel.org/?release=4&arch=\$basearch&repo=beta
baseurl=http://repo.issabel.org/issabel/4/beta/\$basearch/
#gpgcheck=1
enabled=0
#gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-extras]
name=Extras RPM Repository for Issabel
mirrorlist=http://mirror.issabel.org/?release=4&arch=\$basearch&repo=extras
#baseurl=http://repo.issabel.org/issabel/4/extras/\$basearch/
gpgcheck=1
enabled=0
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel
EOF

cat > /etc/yum.repos.d/Issabel5.repo <<EOF
[issabel-cinco]
name=Base RPM Repository for Issabel 5
mirrorlist=http://mirror.issabel.org/?release=5&arch=\$basearch&repo=base
gpgcheck=1
enabled=1
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-noarch]
name=Base RPM Repository for Issabel 5 (noarch)
mirrorlist=http://mirror.issabel.org/?release=5&arch=noarch&repo=base
gpgcheck=1
enabled=1
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-updates]
name=Updates RPM Repository for Issabel 5
mirrorlist=http://mirror.issabel.org/?release=5&arch=\$basearch&repo=updates
gpgcheck=1
enabled=1
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-updates-noarch]
name=Updates RPM Repository for Issabel 5 (noarch)
mirrorlist=http://mirror.issabel.org/?release=5&arch=noarch&repo=updates
gpgcheck=1
enabled=1
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-extras]
name=Extras RPM Repository for Issabel 5
mirrorlist=http://mirror.issabel.org/?release=5&arch=\$basearch&repo=extras
gpgcheck=1
enabled=1
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-extras-noarch]
name=Extras RPM Repository for Issabel 5 (noarch)
mirrorlist=http://mirror.issabel.org/?release=5&arch=noarch&repo=extras
gpgcheck=1
enabled=1
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel

[issabel-cinco-beta]
name=Beta RPM Repository for Issabel 5
mirrorlist=http://mirror.issabel.org/?release=5&arch=\$basearch&repo=beta
#gpgcheck=1
enabled=0
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel
EOF

cat > /etc/yum.repos.d/commercial-addons.repo <<EOF
[commercial-addons]
name=Commercial-Addons RPM Repository for Issabel
mirrorlist=http://mirror.issabel.org/?release=5&arch=\$basearch&repo=commercial_addons
gpgcheck=1
enabled=1
gpgkey=http://repo.issabel.org/issabel/RPM-GPG-KEY-Issabel
EOF

}

function centos8_tweaks {

ROCKY_VERSION=$(cat /etc/redhat-release | awk '{print $4}' | awk -F. '{print $1}')

echo "centos $ROCKY_VERSION tweaks start" >>/tmp/netinstall.log
grep -qxF 'fastestmirror=True' /etc/dnf/dnf.conf || echo "fastestmirror=True" >> /etc/dnf/dnf.conf
dnf install -y https://rpms.remirepo.net/enterprise/remi-release-${ROCKY_VERSION}.rpm  &>>/tmp/netinstall.log
dnf module enable php:remi-7.4 -y &>>/tmp/netinstall.log
dnf config-manager --set-enabled remi &>>/tmp/netinstall.log
dnf config-manager --set-enabled powertools &>>/tmp/netinstall.log
dnf config-manager --set-enabled devel &>>/tmp/netinstall.log
dnf -y check-upgrade &>>/tmp/netinstall.log
echo "centos $ROCKY_VERSION tweaks end" >>/tmp/netinstall.log
}

function additional_packages
{
  ADDPKGS=""
  OPTS=$(dialog --backtitle "$BACKTITLE" --no-tags \
        --checklist "Choose additional package(s) to install:" 0 0 0 \
        1 "Issabel Network Licensed modules(http://issabel.guru)" on \
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
    exit
  fi
  for i in $OPTS
  do
    case $i in
      1)
      ADDPKGS="$ADDPKGS issabel-license webconsole issabel-wizard issabel-packet_capture issabel-upnpc \
      issabel-two_factor_auth issabel-theme_designer issabel-network-agent"
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
  echo "start yum gauge" >>/tmp/netinstall.log
  PACKAGES=$1 #Space separated list of packages.
  TITLE=$2 #Window title
  YUMCMD=$3 #install / update
  dialog --backtitle "$BACKTITLE" --title "$TITLE" --gauge "Installing..." 10 75 < <(
   # Get total number of packages
  n=$(echo $PACKAGES | wc -w);

   # set counter - it will increase every-time a rpm install
   i=0

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
      if ! yum $BETAREPO --nogpg -y $YUMCMD $p &>>/tmp/netinstall.log
      then
         echo "$p: ERROR installing package" >> /tmp/netinstall_errors.txt
         echo "$p: ERROR installing package" >> /tmp/netinstall.log
      fi
    fi
  done
)
echo "end yum gauge" >>/tmp/netinstall.log
}
function update_os
{
  echo "start update os" >>/tmp/netinstall.log
  PACKAGES=$(yum $BETAREPO -d 0 list updates | tail -n +2 | cut -d' ' -f1) &>>/tmp/netinstall.log
  if [ "$PACKAGES" = "" ]; then
  echo "no package to upgrade" >>/tmp/netinstall.log
  else
      yum_gauge "$PACKAGES" "Yum update" update
  fi
  echo "end update os" >>/tmp/netinstall.log
}

function clean_yum
{
  echo "Cleaning yum" >>/tmp/netinstall.log
  yum clean all &>>/tmp/netinstall.log
}

function install_packages
{
  echo "install packages 1" >>/tmp/netinstall.log
  yum clean all &>>/tmp/netinstall.log
  echo "install packages 2" >>/tmp/netinstall.log
  PACKAGES=$(cat /tmp/inst1.txt)
  echo "install packages 3" >>/tmp/netinstall.log
  yum_gauge "$PACKAGES" "(1/2) Please wait..." install
  echo "install packages 4" >>/tmp/netinstall.log
  PACKAGES=$(cat /tmp/inst2.txt)
  echo "install packages 5" >>/tmp/netinstall.log
  yum_gauge "$PACKAGES $ADDPKGS" "(2/2) Please wait..." install
  echo "install packages 6" >>/tmp/netinstall.log
}

function post_install
{
  (
  systemctl enable mariadb.service
  systemctl start mariadb
  mysql -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('iSsAbEl.2o17')"
  #Shut off SElinux and Firewall. Be sure to configure it in Issabel!
  setenforce 0
  sed -i 's/\(^SELINUX=\).*/\SELINUX=disabled/' /etc/selinux/config
  cp -a /etc/sysconfig/iptables /etc/sysconfig/iptables.org-issabel-"$(/bin/date "+%Y-%m-%d-%H-%M-%S")"
  systemctl enable httpd
  systemctl disable firewalld
  systemctl stop firewalld
  firewall-cmd --zone=public --add-port=443/tcp --permanent
  firewall-cmd --reload
  rm -f /etc/issabel.conf
  mysql -piSsAbEl.2o17 -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('')"

  #patch config files
  echo "noload => cdr_mysql.so" >> /etc/asterisk/modules_additional.conf
  mkdir -p /var/log/asterisk
  mkdir -p /var/log/asterisk/cdr-csv
  mv /etc/asterisk/extensions_custom.conf.sample /etc/asterisk/extensions_custom.conf
  /usr/sbin/amportal chown
  ) &> /dev/null
}

function install_mytellpbx_theme
{
  echo "start install_mytellpbx_theme" >>/tmp/netinstall.log
  local DL=""
  local URLS=(
    "https://github.com/${MYTELL_GITHUB_REPO}/releases/download/${MYTELL_THEME_VERSION}/mytellpbx-theme-1.0.0.tgz"
    "https://github.com/${MYTELL_GITHUB_REPO}/releases/latest/download/mytellpbx-theme-1.0.0.tgz"
  )
  for u in "${URLS[@]}"; do
    if curl -fsl --max-time 180 "$u" -o /root/mytellpbx-theme.tgz; then
      DL="$u"
      break
    fi
  done

  if [ -z "$DL" ]; then
    echo "theme download failed" >>/tmp/netinstall.log
    dialog --backtitle "$BACKTITLE" --timeout 6 --msgbox \
      "MyTellPBX theme download failed.\nIssabel was installed with the default theme.\nInstall the theme later from:\ngithub.com/${MYTELL_GITHUB_REPO}" 9 62 || true
    return 0
  fi

  if ! tar tzf /root/mytellpbx-theme.tgz &>/dev/null; then
    echo "theme tarball invalid" >>/tmp/netinstall.log
    return 0
  fi

  rm -rf /var/www/html/themes/mytellpbx
  mkdir -p /var/www/html/themes
  tar xzf /root/mytellpbx-theme.tgz -C /var/www/html/themes/
  chown -R asterisk:asterisk /var/www/html/themes/mytellpbx
  find /var/www/html/themes/mytellpbx -type d -exec chmod 755 {} +
  find /var/www/html/themes/mytellpbx -type f -exec chmod 644 {} +

  php <<'PHP'
<?php
$db = new SQLite3('/var/www/db/settings.db');
if ($db) {
    $db->exec("DELETE FROM settings WHERE key = 'theme'");
    $db->exec("INSERT INTO settings (key, value) VALUES ('theme', 'mytellpbx')");
}
PHP

  systemctl reload httpd &>/dev/null || true
  /usr/sbin/amportal chown &>/dev/null || true
  echo "end install_mytellpbx_theme" >>/tmp/netinstall.log

  dialog --backtitle "$BACKTITLE" --sleep 2 --infobox \
"MyTellPBX theme installed and activated." 5 50 || true
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
    yum -y install dialog &>/dev/null
    BLA::stop_loading_animation
    echo -e "\n"
    if [ $? -ne 0 ]
    then
      echo -e "\n***yum install dialog FAILED***\n\n"
    fi
    if ! dialog > /dev/null
    then
      echo -e "Dialog is requiered\n"
      exit
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
  /usr/bin/issabel-admin-passwords --init
}

function select_language()
{
  /usr/bin/issabel-change-language
}

function cleanup()
{
(
  rm -f /tmp/inst1.txt
  rm -f /tmp/inst2.txt
  /usr/sbin/amportal chown
) &> /dev/null
}

function bye()
{
  dialog --stdout --sleep 2 --backtitle "$BACKTITLE" --infobox \
"             O @ @\n             @ @ O\n             @ O O\n               O\n            MyTellPBX \n\nRebooting server, log back in in a minute..." \
  10 35
}

check_dialog
add_repos
settings
welcome
select_language
sel_astver
additional_packages
generate_files
#if enable_beta
#then
#    BETAREPO="--enablerepo=issabel-beta"
#fi
welcome
centos8_tweaks
clean_yum
update_os
install_packages
post_install
set_passwords
install_mytellpbx_theme
cleanup
bye
reboot
