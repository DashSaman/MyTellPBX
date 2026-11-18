#!/bin/bash
# Guided console entry point for the ISO's native firstboot unit.
set -euo pipefail
umask 077
fail() { printf '\nMytelPBX offline setup: %s\n' "$*" >&2; exit 1; }

verify_media() {
    # The installed configuration is root-owned and pins the entire sealed depot.
    "$MYTEL_PYTHON" -I -S -B - /etc/mytelpbx-native-media.json <<'PY_MEDIA'
import hashlib, importlib.util, json, os, pathlib, re, stat, sys

def trusted(path, private=False):
    path = pathlib.Path(path)
    info = path.lstat()
    if (path.resolve() != path.absolute() or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1 or info.st_uid != 0 or info.st_mode & 0o022
            or (private and info.st_mode & 0o077)):
        raise ValueError('Untrusted native media configuration or validator')
    return path

config = trusted(pathlib.Path(sys.argv[1]), private=True)
value = json.loads(config.read_text(encoding='utf-8'))
if (set(value) != {'schema', 'root', 'manifest_sha256', 'validator_sha256'}
        or type(value['schema']) is not int or value['schema'] != 1
        or value['root'] != '/var/lib/mytelpbx-media'
        or not all(re.fullmatch('[0-9a-f]{64}', value[k] or '')
                   for k in ('manifest_sha256', 'validator_sha256'))):
    raise ValueError('Unknown native supplemental media profile')
validator = trusted(pathlib.Path('/usr/local/libexec/mytelpbx/media.py'))
if hashlib.sha256(validator.read_bytes()).hexdigest() != value['validator_sha256']:
    raise ValueError('Native supplemental media validator changed')
spec = importlib.util.spec_from_file_location('sealed_native_media', str(validator))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
media = module.load(value['root'], value['manifest_sha256'])
bootstrap = media.asset('bootstrap')
bundle = media.asset('bundle')
literal = ('MYTELLPBX_BUNDLE_SHA256="' + media.manifest['files'][media.manifest['bundle']]['sha256'] + '"').encode()
if bootstrap.read_bytes().count(literal) != 1:
    raise ValueError('Bootstrap does not bind this supplemental bundle')
for item in (value['root'], value['manifest_sha256'], str(bootstrap), str(bundle)):
    if '\n' in item or '\r' in item:
        raise ValueError('Ambiguous native media profile')
    print(item)
PY_MEDIA
}

require_fresh_core() {
    [ -f /installamp ] && [ ! -L /installamp ] && [ -O /installamp ] \
        || fail 'The native firstboot marker is absent or invalid. Existing PBX state retained.'
    if [ -e /etc/issabel.conf ] || [ -L /etc/issabel.conf ]; then
        [ -f /etc/issabel.conf ] && [ ! -L /etc/issabel.conf ] && [ -r /etc/issabel.conf ] \
            || fail 'Cannot validate existing native credentials.'
        if grep -q '^mysqlrootpwd=' /etc/issabel.conf; then
            fail 'Native credentials are already configured. Existing PBX state retained.'
        else
            [ "$?" = 1 ] || fail 'Cannot validate existing native credentials.'
        fi
    fi
    systemctl is-active --quiet mariadb.service || fail 'MariaDB is not running.'
}

guided_offline_setup() {
    local version native log
    # `-V` checks the installed binary. `-rx` would require the socket which
    # native initialization prepares; the add-on checks the running service.
    version=$(asterisk -V) || fail 'Native Asterisk is unavailable.'
    [[ "$version" =~ ^Asterisk\ 20\. ]] || fail 'MytelPBX requires native Asterisk 20.'
    rpm -q --quiet issabel-packetbl || fail 'Community Realtime Block List is missing from the base install.'
    require_fresh_core
    ASTVER=20
    export MYTEL_BUNDLE_ROOT MYTEL_NATIVE_WORK MYTEL_PYTHON ASTVER
    export MYTEL_MEDIA_ROOT MYTEL_MEDIA_MANIFEST_SHA256
    native="$MYTEL_BUNDLE_ROOT/installer/vendor-native"
    log="$MYTEL_NATIVE_WORK/native-init.log"
    source "$native/terminal-ui.sh"
    source "$native/online-credentials.sh"

    mytel_terminal_banner offline
    mytel_terminal_offline_phase 1 4 'Access setup'
    "$MYTEL_PYTHON" -I -B "$native/online-sip.py" "$MYTEL_NATIVE_WORK" > "$log" 2>&1 \
        || fail "Could not prepare the native SIP setup. Log: $log"
    mytel_receive_online_passwords 3< <(mytel_collect_online_passwords) \
        || fail 'Access setup stopped before any passwords were changed.'

    mytel_terminal_offline_phase 2 4 'Initialize phone system'
    printf '    Applying the confirmed passwords, SIP driver and Persian defaults.\n'
    mytel_apply_online_passwords >> "$log" 2>&1 \
        || fail "Native initialization failed. Log: $log"
    [ ! -e /installamp ] && [ ! -L /installamp ] \
        || fail "Native initialization did not consume the firstboot marker. Log: $log"
    printf '    Native phone system configured.\n'

    mytel_terminal_offline_phase 3 4 'Install MytelPBX and Desk'
    bash "$MYTEL_BUNDLE_ROOT/installer/install-mytel-addons.sh" \
        || fail 'Add-ons incomplete; native credentials and PBX state retained. Review the private recovery receipt.'
    mytel_terminal_offline_ready
}

main() {
    local profile bootstrap
    local -a values
    [ "$(id -u)" = 0 ] || fail 'Root is required.'
    [ "$#" = 0 ] || { [ "$#" = 1 ] && [ "$1" = --verify-media ]; } || fail 'Unknown argument.'
    MYTEL_PYTHON=/usr/libexec/platform-python
    [ -x "$MYTEL_PYTHON" ] || MYTEL_PYTHON=/usr/bin/python3
    [ -x "$MYTEL_PYTHON" ] || fail 'Native Python is unavailable.'

    if [ "${1:-}" != --verify-media ]; then
        [ -t 0 ] && [ -t 1 ] || fail 'An interactive console is required.'
        printf '\n  MytelPBX / Mytel.one · Verifying offline media\n'
    fi
    profile=$(verify_media) || fail 'Sealed media verification failed; native PBX state retained.'
    if [ "${1:-}" = --verify-media ]; then
        printf 'MytelPBX native supplemental media verified.\n'
        return 0
    fi
    mapfile -t values <<<"$profile"
    [ "${#values[@]}" = 4 ] || fail 'Incomplete supplemental media profile.'
    MYTEL_MEDIA_ROOT="${values[0]}"
    MYTEL_MEDIA_MANIFEST_SHA256="${values[1]}"
    bootstrap="${values[2]}"
    MYTELL_BUNDLE_FILE="${values[3]}"

    # Only the sealed bootstrap's local file verification and extraction helpers
    # are used. Its network installer and fresh-server entry point are excluded.
    source "$bootstrap"
    MYTEL_NATIVE_WORK=$(mktemp -d /var/tmp/mytelpbx-native-addons.XXXXXXXX) \
        || fail 'Cannot create a private setup workspace.'
    download_bundle
    extract_bundle
    guided_offline_setup
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
