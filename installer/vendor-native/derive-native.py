#!/usr/bin/env python3
"""Derive the MytelPBX display layer from the exact owner-supplied netinstaller.

The vendor functions, package lists, version selection and password initialization
remain the installation engine. The finite changes below are intentionally
reviewable: display text, reachable official HTTPS transport, removal of global
signature bypass, private temporary files, checked failures and the add-on hook.
Python 3.6 compatible.
"""
import argparse
import hashlib
from pathlib import Path
import re

SOURCE_SHA256 = 'd0793041a422981293d74153f1aa56b29ff9803d18ee3319a53865b5b6132d46'


def replace(source, old, new, count=1):
    if source.count(old) != count:
        raise ValueError('Unexpected native boundary: ' + old[:80])
    return source.replace(old, new)


def derive(original):
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unknown vendor netinstaller; refusing derivation')
    source = original.decode('utf-8')
    source = replace(source, '#!/bin/bash\n', '#!/bin/bash\n'
                     '# Generated from the pinned Issabel native installer; do not edit.\n'
                     '# MytelPBX / Mytel.one - see provenance.json and derive-native.py.\n'
                     'set -o pipefail\n')
    source = replace(source, 'BACKTITLE="Issabel 5 netinstall"',
                     'BACKTITLE="MytelPBX netinstall - Mytel.one"')
    source = replace(source, r'\nIssabel"', r'\nMytelPBX\nMytel.one"')
    source = replace(source, '        7 11\n', '        8 15\n')
    source = replace(source, '            Issabel ', '       MytelPBX / Mytel.one ')
    source = replace(source, 'Issabel Network Licensed modules(http://issabel.guru)',
                     'Optional upstream licensed add-ons')
    source = re.sub(r'(?m)^name=(.*)Issabel(.*)$', r'name=\1MytelPBX\2', source)

    # The official primary and mirrorlist hosts currently refuse HTTPS. The
    # official US mirror serves the same native layout and signing key via TLS.
    def mirror(match):
        release, arch, repo = match.groups()
        if release == '4' and repo == 'beta':
            return '# Native mirrorlist replaced by the HTTPS baseurl below.'
        return 'baseurl=https://repo.us.issabel.org/issabel/' + release + '/' + repo + '/' + arch + '/'
    source, count = re.subn(r'mirrorlist=http://mirror\.issabel\.org/\?release=(4|5)&arch=(\\\$basearch|noarch)&repo=([a-z_]+)', mirror, source)
    if count != 13:
        raise ValueError('Unexpected native repository set')
    source = source.replace('http://repo.issabel.org/', 'https://repo.us.issabel.org/')
    source = replace(source, 'yum $BETAREPO --nogpg -y $YUMCMD $p', 'yum $BETAREPO -y $YUMCMD $p')

    for filename in ('inst1.txt', 'inst2.txt', 'netinstall.log', 'netinstall_errors.txt'):
        source = source.replace('/tmp/' + filename, '"${MYTEL_NATIVE_WORK}/' + filename + '"')
    for command in ('cat > "${MYTEL_NATIVE_WORK}/inst1.txt" <<EOF',
                    'cat > "${MYTEL_NATIVE_WORK}/inst2.txt" <<EOF',
                    'cat > /etc/yum.repos.d/Issabel.repo <<EOF',
                    'cat > /etc/yum.repos.d/Issabel5.repo <<EOF',
                    'cat > /etc/yum.repos.d/commercial-addons.repo <<EOF'):
        source = replace(source, command, command + ' || return 1')
    source = replace(source, '  yum -y install issabel-config_helpers &> /dev/null',
                     '  if ! yum -y install issabel-config_helpers &>>"${MYTEL_NATIVE_WORK}/netinstall.log"; then\n'
                     '    BLA::stop_loading_animation\n    return 1\n  fi')
    source = replace(source, '    yum -y install dialog &>/dev/null',
                     '    if ! yum -y install dialog &>>"${MYTEL_NATIVE_WORK}/netinstall.log"; then\n'
                     '      BLA::stop_loading_animation\n      return 1\n    fi')
    source = replace(source, '      exit\n', '      return 1\n')
    source = replace(source, '    exit\n', '    exit 1\n', 2)

    for command in (
        'dnf install -y https://rpms.remirepo.net/enterprise/remi-release-${ROCKY_VERSION}.rpm ',
        'dnf module enable php:remi-7.4 -y',
        'dnf config-manager --set-enabled remi',
        'dnf config-manager --set-enabled powertools',
        'dnf config-manager --set-enabled devel',
    ):
        old = command + ' &>>"${MYTEL_NATIVE_WORK}/netinstall.log"'
        source = replace(source, old, old + ' || return 1')
    remi = 'dnf module enable php:remi-7.4 -y'
    source = replace(source, remi, '"${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/repair-repository-transport.py" || return 1\n' + remi)
    source = replace(source, 'dnf -y check-upgrade &>>"${MYTEL_NATIVE_WORK}/netinstall.log"',
                     'dnf -y check-upgrade &>>"${MYTEL_NATIVE_WORK}/netinstall.log"\n'
                     'local update_status=$?\n[ "$update_status" = 0 ] || [ "$update_status" = 100 ] || return "$update_status"')
    source = replace(source, 'echo "end yum gauge"',
                     'local dialog_status=$?\n[ "$dialog_status" = 0 ] || return "$dialog_status"\n'
                     '[ ! -s "${MYTEL_NATIVE_WORK}/netinstall_errors.txt" ] || return 1\necho "end yum gauge"')
    source = replace(source, 'PACKAGES=$(yum $BETAREPO -d 0 list updates | tail -n +2 | cut -d\' \' -f1) &>>"${MYTEL_NATIVE_WORK}/netinstall.log"',
                     'PACKAGES=$(yum $BETAREPO -d 0 list updates | tail -n +2 | cut -d\' \' -f1) 2>>"${MYTEL_NATIVE_WORK}/netinstall.log" || return 1')
    source = replace(source, 'yum_gauge "$PACKAGES" "Yum update" update',
                     'yum_gauge "$PACKAGES" "Yum update" update || return 1')
    source = replace(source, 'yum_gauge "$PACKAGES" "(1/2) Please wait..." install',
                     'yum_gauge "$PACKAGES" "(1/2) Please wait..." install || return 1')
    source = replace(source, 'yum_gauge "$PACKAGES $ADDPKGS" "(2/2) Please wait..." install',
                     'yum_gauge "$PACKAGES $ADDPKGS" "(2/2) Please wait..." install || return 1')
    for command in ('systemctl enable mariadb.service', 'systemctl start mariadb',
                    'mysql -e "SET PASSWORD FOR \'root\'@\'localhost\' = PASSWORD(\'iSsAbEl.2o17\')"',
                    'systemctl enable httpd',
                    'mysql -piSsAbEl.2o17 -e "SET PASSWORD FOR \'root\'@\'localhost\' = PASSWORD(\'\')"'):
        source = replace(source, '  ' + command + '\n', '  ' + command + ' || exit 1\n')
    source = replace(source, '''  echo "noload => cdr_mysql.so" >> /etc/asterisk/modules_additional.conf
  mkdir -p /var/log/asterisk
  mkdir -p /var/log/asterisk/cdr-csv
  mv /etc/asterisk/extensions_custom.conf.sample /etc/asterisk/extensions_custom.conf
  /usr/sbin/amportal chown
  ) &> /dev/null''', '''  # RPMs can precede native --init: missing pre-init files are not a failure.
  [ -d /etc/asterisk ] && [ ! -L /etc/asterisk ] || exit 1
  for MYTEL_NATIVE_PATH in /etc/asterisk/modules_additional.conf /etc/asterisk/extensions_custom.conf.sample /etc/asterisk/extensions_custom.conf /etc/amportal.conf; do
    if [ -L "$MYTEL_NATIVE_PATH" ] || { [ -e "$MYTEL_NATIVE_PATH" ] && [ ! -f "$MYTEL_NATIVE_PATH" ]; }; then
      printf 'Invalid native configuration path: %s\\n' "$MYTEL_NATIVE_PATH" >&2
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
  ) &>>"${MYTEL_NATIVE_WORK}/netinstall.log"''')
    source = replace(source, 'function set_passwords()\n{\n',
                     'function set_passwords()\n{\n'
                     '  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool completion || return 1\n'
                     '  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool passwords || return 1\n'
                     '  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool sip || return 1\n'
                     '  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool certificate || return 1\n')
    source = replace(source, 'function select_language()\n{\n',
                     'function select_language()\n{\n'
                     '  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/brand-native-dialogs.py" --tool language || return 1\n')

    footer = source.index('\ncheck_dialog\nadd_repos\n')
    definitions, flow = source[:footer], source[footer:]
    flow = flow.replace('\nset_passwords\n', '\nset_passwords\nmytel_addons\n')
    flow = re.sub(r'(?m)^(check_dialog|add_repos|settings|welcome|select_language|sel_astver|additional_packages|generate_files|centos8_tweaks|clean_yum|update_os|install_packages|post_install|set_passwords|mytel_addons|cleanup|bye|reboot)$',
                  r'mytel_native_step \1', flow)
    helpers = '''
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
    printf '\\nMytelPBX stopped at %s (status %s). No automatic reboot.\\n' "$1" "$status" >&2
    printf 'Native log: %s/netinstall.log\\n' "${MYTEL_NATIVE_WORK}" >&2
    exit "$status"
  fi
}
'''
    return (definitions + helpers + '\n# MYTEL_NATIVE_FLOW\n' + flow.lstrip('\n')).encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    result = derive((root / 'issabel5-netinstall.sh').read_bytes())
    target = root / 'mytelpbx-netinstall.sh'
    if args.check:
        if target.read_bytes() != result:
            raise SystemExit('Derived native installer differs; regenerate and review it')
        print('Pinned vendor source and native derivation verified')
    else:
        target.write_bytes(result)


if __name__ == '__main__':
    main()
