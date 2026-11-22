#!/usr/bin/env python3
"""Derive the MytelPBX display layer from the exact owner-supplied netinstaller.

The vendor functions, package lists and password initialization remain the
installation engine, with the product fixed to Asterisk 20. Changes are intentionally
reviewable: display text, verified GitHub packages, removal of global
signature bypass, private temporary files, checked failures and the add-on hook.
Python 3.6 compatible.
"""
import argparse
import hashlib
from pathlib import Path
import re

SOURCE_SHA256 = 'd0793041a422981293d74153f1aa56b29ff9803d18ee3319a53865b5b6132d46'

# issabel-5.0.0-1.noarch ships no files or scriptlet bodies. Install its
# actual module requirements directly so the paid-license broker stays off.
# The base batch already selects the required asterisk provider (asterisk20).
NATIVE_MODULES = ('issabel-addons', 'issabel-agenda', 'issabel-email_admin',
                  'issabel-extras', 'issabel-fax', 'issabel-framework',
                  'issabel-my_extension', 'issabel-pbx', 'issabel-reports',
                  'issabel-security', 'issabel-system')


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
    source = replace(source, 'Issabel Network Licensed modules(http://issabel.guru)',
                     'Optional upstream licensed add-ons')

    animation = source[source.index('BLA_metro='):source.index('function generate_files')]
    source = replace(source, animation, '')
    modules = [name + '>=5.0.0-1' for name in NATIVE_MODULES] + ['issabelPBX>=2.12.0-1']
    source = replace(source, '\nissabel-geoip\nissabel\nissabel-prosody-auth\n',
                     '\nissabel-geoip\n' + '\n'.join(modules) + '\nissabel-prosody-auth\n')

    source = replace(source, '\nlibnsl\nfop2\nEOF', '\nlibnsl\nEOF')
    source = replace(source, '\nasterisk-es-sounds\nasterisk-fr-sounds\nasterisk-sounds-en-gsm\nasterisk-pt_BR-sounds\n',
                     '\nasterisk-pr-sounds\nasterisk-sounds-en-gsm\n')
    # The upstream G.729 binary package contains no Asterisk 20 module.
    source = replace(source, '\nasterisk-codec-g729\n', '\n')

    for filename in ('inst1.txt', 'inst2.txt', 'netinstall.log', 'netinstall_errors.txt'):
        source = source.replace('/tmp/' + filename, '"${MYTEL_NATIVE_WORK}/' + filename + '"')
    for command in ('cat > "${MYTEL_NATIVE_WORK}/inst1.txt" <<EOF',
                    'cat > "${MYTEL_NATIVE_WORK}/inst2.txt" <<EOF'):
        source = replace(source, command, command + ' || return 1')
    # Replace the vendor repository writer as a unit. Both source checks and
    # native RPM transactions use only the pinned MytelPBX GitHub asset.
    repo_writer = source[source.index('function add_repos\n'):source.index('function centos8_tweaks {')]
    source = replace(source, repo_writer,
                     '''function add_repos
{
  local repo_dir="${1:-$MYTEL_NATIVE_WORK/approved-vendor-repos}"
  local state_dir="$repo_dir/.mytel-vendor"
  if [ "$#" = 0 ]; then
    mkdir -m 0700 "$repo_dir" || return 1
    state_dir=/var/lib/mytelpbx/repository-snapshots/r9
  fi
  "$MYTEL_PYTHON" -I -B "$MYTEL_BUNDLE_ROOT/installer/vendor-native/vendor-mirror.py" \\
    --repo-dir "$repo_dir" --state-dir "$state_dir" --workdir "$MYTEL_NATIVE_WORK" || return $?
  if [ "$#" = 0 ]; then
    local backup="$MYTEL_NATIVE_WORK/vendor-repos-before" file
    mkdir -m 0700 "$backup" || return 1
    for file in Issabel.repo Issabel5.repo commercial-addons.repo; do
      if [ -e "/etc/yum.repos.d/$file" ] || [ -L "/etc/yum.repos.d/$file" ]; then
        [ -f "/etc/yum.repos.d/$file" ] && [ ! -L "/etc/yum.repos.d/$file" ] || return 1
        cp -p -- "/etc/yum.repos.d/$file" "$backup/$file" || return 1
      fi
    done
    MYTEL_APPROVED_VENDOR_REPOS="$repo_dir"
    mytel_restore_vendor_repos || return $?
  fi
}

''')
    settings_tail = source[source.index('  echo -en "        Installing base packages '):source.index('\nfunction sel_astver')]
    source = replace(source, settings_tail,
                     '  mytel_run_dnf repositories yum -y install issabel-config_helpers dialog\n}\n')
    dialog = source[source.index('function check_dialog'):source.index('\nfunction enable_beta')]
    source = replace(source, dialog, '''function check_tools
{
  command -v yum >/dev/null && command -v dnf >/dev/null && command -v rpm >/dev/null
}
''')
    version_start = source.index('function sel_astver\n{\n')
    version_end = source.index('\nfunction add_repos\n', version_start)
    source = replace(source, source[version_start:version_end],
                     'function sel_astver\n{\n'
                     '  # MytelPBX installs the supported Asterisk 20 product only.\n'
                     '  ASTVER=20\n}\n')
    packages = source[source.index('function additional_packages'):source.index('function yum_gauge')]
    source = replace(source, packages, '''function additional_packages
{
  # Install the community SIP block list without selecting licensed add-ons.
  ADDPKGS=issabel-packetbl
}

''')
    beta = source[source.index('function enable_beta'):source.index('function set_passwords()')]
    source = replace(source, beta, '')

    remi = 'dnf module enable php:remi-7.4 -y'
    for command in ('dnf install -y https://rpms.remirepo.net/enterprise/remi-release-${ROCKY_VERSION}.rpm ', remi):
        source = replace(source, command + ' &>>"${MYTEL_NATIVE_WORK}/netinstall.log"',
                         'mytel_run_dnf repositories ' + command.rstrip() + ' || return $?')
    for command in (
        'dnf config-manager --set-enabled remi',
        'dnf config-manager --set-enabled powertools',
        'dnf config-manager --set-enabled devel',
    ):
        old = command + ' &>>"${MYTEL_NATIVE_WORK}/netinstall.log"'
        source = replace(source, old, old + ' || return 1')
    remi_progress = 'mytel_run_dnf repositories ' + remi
    source = replace(source, remi_progress,
                     '"${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/repair-repository-transport.py" || return 1\n'
                     'mytel_check_repository_sources --enable remi --enable powertools --enable devel || return $?\n'
                     + remi_progress)
    source = replace(source, 'dnf -y check-upgrade &>>"${MYTEL_NATIVE_WORK}/netinstall.log"\n', '')
    transactions = source[source.index('function yum_gauge'):source.index('function post_install')]
    source = replace(source, transactions, '''function update_os
{
  local -a repository_options=()
  IFS=$' \\t\\n' read -r -a repository_options <<< "${BETAREPO:-}" || :
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

''')
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
    source = replace(source, '  /usr/bin/issabel-change-language\n',
                     '  # The later online initializer applies the fixed Persian locale.\n')
    source = replace(source, '  /usr/bin/issabel-admin-passwords --init\n',
                     '  "${MYTEL_PYTHON}" -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/online-sip.py" "${MYTEL_NATIVE_WORK}" || return 1\n'
                     '  mytel_apply_online_passwords\n')
    bye = source[source.index('function bye()'):source.index('\ncheck_dialog\nadd_repos\n')]
    source = replace(source, bye, 'function bye()\n{\n  mytel_terminal_success\n}\n')

    footer = source.index('\ncheck_dialog\nadd_repos\n')
    definitions, flow = source[:footer], source[footer:]
    flow = replace(flow, '\ncheck_dialog\n', '\ncheck_tools\n')
    flow = replace(flow, '\nclean_yum\n', '\n')
    flow = replace(flow, '\nwelcome\n', '\n', count=2)
    flow = replace(flow, '#if enable_beta\n#then\n#    BETAREPO="--enablerepo=issabel-beta"\n#fi\n', '')
    flow = flow.replace('\nset_passwords\n', '\nset_passwords\nmytel_addons\n')
    flow = replace(flow, '\ncleanup\n', '\ncleanup\nmytel_verify_addons\n')
    flow = re.sub(r'(?m)^(check_tools|add_repos|settings|select_language|sel_astver|additional_packages|generate_files|centos8_tweaks|update_os|install_packages|post_install|set_passwords|mytel_addons|cleanup|mytel_verify_addons|bye|reboot)$',
                  r'mytel_native_step \1', flow)
    helpers = '''
function mytel_restore_vendor_repos()
{
  # Native RPM scriptlets can rewrite these three files. Restore the checked
  # definitions before the next DNF stage and after the product RPM transaction.
  local file
  for file in Issabel.repo Issabel5.repo commercial-addons.repo; do
    if ! cmp -s -- "$MYTEL_APPROVED_VENDOR_REPOS/$file" "/etc/yum.repos.d/$file"; then
      install -T -m 0644 -- "$MYTEL_APPROVED_VENDOR_REPOS/$file" "/etc/yum.repos.d/$file" || return 1
    fi
  done
}

function mytel_check_repository_sources()
{
  local dnf_python=/usr/libexec/platform-python
  [ -x "$dnf_python" ] || dnf_python="$MYTEL_PYTHON"
  if [ "${MYTEL_KEEP_DNF_CACHE:-0}" = 1 ]; then set -- --keep-cache "$@"; fi
  "$dnf_python" -I -B "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/repository-preflight.py" "${MYTEL_NATIVE_WORK}" "$@"
}

function mytel_check_install_repositories()
{
  local staged
  check_tools || return 1
  staged=$(mktemp -d "${MYTEL_NATIVE_WORK}/planned-repos.XXXXXXXX") || return 1
  add_repos "$staged" || return $?
  mytel_check_repository_sources --staged-repos "$staged" --enable powertools --enable devel \
    --package-url https://rpms.remirepo.net/enterprise/remi-release-8.rpm
}

function mytel_addons()
{
  [ "${ASTVER:-}" = 20 ] || { printf 'MytelPBX requires native Asterisk 20.\\n' >&2; return 1; }
  export ASTVER
  MYTEL_NATIVE_FRESH_SETUP=1 bash "${MYTEL_BUNDLE_ROOT}/installer/install-mytel-addons.sh"
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
    printf '\\nMytelPBX stopped at %s (status %s). No automatic reboot.\\n' "$1" "$status" >&2
    printf 'Native log: %s/netinstall.log\\n' "${MYTEL_NATIVE_WORK}" >&2
    exit "$status"
  fi
}
'''
    load_online = '''if [ "$#" = 1 ] && [ "$1" = --check-repositories ]; then
  mytel_check_install_repositories
  exit $?
fi
[ "$#" = 0 ] || exit 1
source "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/terminal-ui.sh" || exit 1
source "${MYTEL_BUNDLE_ROOT}/installer/vendor-native/online-credentials.sh" || exit 1
mytel_receive_online_passwords || exit 1
'''
    return (definitions + helpers + '\n# MYTEL_NATIVE_FLOW\n' + load_online + flow.lstrip('\n')).encode('utf-8')


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
