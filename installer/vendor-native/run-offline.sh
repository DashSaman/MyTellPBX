#!/bin/bash
# Success-only ExecStartPost of the unmodified native Issabel firstboot unit.
# This installs Mytel presentation and Desk only; native core/password setup has
# already completed. It never invokes another PBX initializer or GeoIP engine.
set -euo pipefail
umask 077
fail() { printf '\nMytelPBX offline add-ons: %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || fail 'Root is required.'
[ "$#" = 0 ] || { [ "$#" = 1 ] && [ "$1" = --verify-media ]; } || fail 'Unknown argument.'
MYTEL_PYTHON=/usr/libexec/platform-python
[ -x "$MYTEL_PYTHON" ] || MYTEL_PYTHON=/usr/bin/python3
[ -x "$MYTEL_PYTHON" ] || fail 'Native Python is unavailable.'

# The installed configuration is root-owned and pins the entire sealed depot.
# The companion validator is copied from the release bundle by native KS post.
profile=$("$MYTEL_PYTHON" -I -S -B - /etc/mytelpbx-native-media.json <<'PY_MEDIA'
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
) || fail 'Sealed media verification failed; native PBX state retained.'
if [ "${1:-}" = --verify-media ]; then
    printf 'MytelPBX native supplemental media verified.\n'
    exit 0
fi
mapfile -t values <<<"$profile"
[ "${#values[@]}" = 4 ] || fail 'Incomplete supplemental media profile.'
MYTEL_MEDIA_ROOT="${values[0]}"
MYTEL_MEDIA_MANIFEST_SHA256="${values[1]}"
bootstrap="${values[2]}"
MYTELL_BUNDLE_FILE="${values[3]}"

# Sourcing the reviewed bootstrap only defines its download/extraction helpers.
# Its fresh-server main and the native installation engine are not called.
source "$bootstrap"
MYTEL_NATIVE_WORK=$(mktemp -d /var/tmp/mytelpbx-native-addons.XXXXXXXX) \
    || fail 'Cannot create a private add-on workspace.'
printf 'MytelPBX / Mytel.one - native installation complete; checking add-ons.\nWorkspace: %s\n' "$MYTEL_NATIVE_WORK"
download_bundle
extract_bundle
version=$(asterisk -V) || fail 'Native Asterisk is unavailable.'
[[ "$version" =~ ^Asterisk\ (16|18|20)\. ]] || fail 'Unsupported native Asterisk version.'
ASTVER="${BASH_REMATCH[1]}"
export MYTEL_BUNDLE_ROOT MYTEL_NATIVE_WORK MYTEL_PYTHON ASTVER
export MYTEL_MEDIA_ROOT MYTEL_MEDIA_MANIFEST_SHA256
bash "$MYTEL_BUNDLE_ROOT/installer/install-mytel-addons.sh" \
    || fail 'Add-ons incomplete; native credentials and PBX state retained. Review the private recovery receipt.'
