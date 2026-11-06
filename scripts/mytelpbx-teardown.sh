#!/bin/bash
# ==========================================================================
# MyTellPBX lab teardown helper — approximates a fresh Rocky 8.10 system
# after a MyTellPBX install, for RE-TESTING the installer in a lab.
#
# This is NOT a supported uninstall and does NOT guarantee factory state:
# the reliable reset path is reimaging the server (see docs/INSTALL.en.md).
#
# Usage (root, understood risks):  bash scripts/mytelpbx-teardown.sh
# ==========================================================================
set -u

say() { printf '[teardown] %s\n' "$*"; }
die() { printf '[teardown] FATAL: %s\n' "$*" 1>&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "root required"
grep -q "Rocky Linux release 8.10" /etc/redhat-release || die "rocky 8.10 only"

read -r -p "This removes the PBX stack, web tree and databases. Type YES to continue: " ok
[ "${ok}" = "YES" ] || die "aborted"

say "stopping services"
systemctl stop asterisk httpd mariadb fop2 2>/dev/null || true

say "removing PBX package groups"
dnf -y remove \
    'issabel*' 'asterisk*' fop2 'xtables-addons*' RoundCubeMail \
    'php*remi*' php php-common 'php-*' \
    httpd httpd-tools 'mariadb*' certbot 'dhcp-server' \
    2>/dev/null | tail -1 || true

say "removing data and configuration"
rm -rf /var/www/html /var/www/db /var/lib/mysql /var/lib/asterisk \
       /etc/asterisk /etc/httpd /etc/amportal.conf /etc/issabel.conf \
       /usr/local/fop2 /usr/src/issabelPBX /var/spool/issabel-mysqldbscripts \
       /var/lib/mytelpbx-installer /var/log/mytelpbx-install.log \
       /root/mytelpbx-credentials.txt /tmp/mytelpbx-bundle* /installamp \
       2>/dev/null || true
rm -f /etc/yum.repos.d/mytelpbx-base.repo /etc/yum.repos.d/Issabel*.repo \
      /etc/yum.repos.d/commercial-addons.repo /var/run/mytelpbx-install.lock \
      2>/dev/null || true

say "resetting php module stream"
dnf module reset -y php 2>/dev/null || true

say "teardown complete (approximate fresh state; reimage for a true reset)"
