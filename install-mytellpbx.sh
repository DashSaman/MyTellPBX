#!/bin/bash
# MytelPBX / Mytel.one - verified native Issabel installer bootstrap.
# Run in an interactive root terminal on fresh Rocky Linux 8.10 x86_64.
# Installs Asterisk 20 only. Native dialogs select language and optional
# packages, followed by four password screens. Native completion reboots the server.
# Verified source and logs remain in the printed private workspace.
set -u
set -o pipefail

MYTELLPBX_VERSION="7.7.0"
MYTELLPBX_BUNDLE="mytelpbx-bundle-7.7.0.tgz"
# Immutable payload pin from the reviewed clean-source bundle assembly.
MYTELLPBX_BUNDLE_SHA256="16324e63ef660a27d79c49ba9380ecf28e177d5cda56c95943b3be6d129bcdc3"
MYTELLPBX_GITHUB="https://github.com/DashSaman/MyTellPBX"
MYTELLPBX_RELEASE_TAG="v7.7.0-r2"
MYTELLPBX_BUNDLE_URL="${MYTELL_BUNDLE_URL:-${MYTELLPBX_GITHUB}/releases/download/${MYTELLPBX_RELEASE_TAG}/${MYTELLPBX_BUNDLE}}"

die() { printf '\nMytelPBX: %s\n' "$*" >&2; exit 1; }

preflight() {
    [ "$#" = 0 ] || die 'This installer accepts no command arguments.'
    [ "$(id -u)" = 0 ] || die 'Run from an interactive root terminal.'
    [ -t 0 ] && [ -t 1 ] || die 'Native dialogs require a terminal; download this script, then run bash install-mytellpbx.sh.'
    grep -qx 'Rocky Linux release 8.10 (Green Obsidian)' /etc/redhat-release \
        || die 'Fresh Rocky Linux 8.10 is required.'
    [ "$(uname -m)" = x86_64 ] || die 'x86_64 is required.'
    [[ "${MYTELLPBX_BUNDLE_SHA256}" =~ ^[0-9a-f]{64}$ ]] \
        && [ "${MYTELLPBX_BUNDLE_SHA256}" != "$(printf '%064d' 0)" ] \
        || die 'This source bootstrap has no reviewed release bundle pin yet.'
    local path
    for path in /etc/asterisk /etc/issabel.conf /etc/amportal.conf /var/www/html/admin \
                /etc/myteldesk /opt/myteldesk /var/lib/myteldesk; do
        [ ! -e "$path" ] && [ ! -L "$path" ] \
            || die "Existing PBX data found at $path; use a fresh server."
    done
    for path in curl sha256sum flock mktemp; do
        command -v "$path" >/dev/null 2>&1 || die "Required OS tool is missing: $path"
    done
    if command -v python3 >/dev/null 2>&1; then
        MYTEL_PYTHON=$(command -v python3)
    elif [ -x /usr/libexec/platform-python ]; then
        MYTEL_PYTHON=/usr/libexec/platform-python
    else
        die 'Rocky platform-python or Python 3 is required.'
    fi
    "$MYTEL_PYTHON" -B -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,6) else 1)' \
        || die 'Python 3.6 or later is required.'
}

download_bundle() {
    if [ -n "${MYTELL_BUNDLE_FILE:-}" ]; then
        [ -f "$MYTELL_BUNDLE_FILE" ] && [ ! -L "$MYTELL_BUNDLE_FILE" ] \
            || die 'The local bundle must be a regular file.'
        cp -- "$MYTELL_BUNDLE_FILE" "$MYTEL_NATIVE_WORK/bundle.tgz" \
            || die 'Cannot copy local bundle.'
    else
        case "$MYTELLPBX_BUNDLE_URL" in https://*) ;; *) die 'Bundle downloads require HTTPS.';; esac
        curl --fail --show-error --location --proto '=https' --proto-redir '=https' \
            --connect-timeout 30 --max-time 600 --retry 2 \
            --output "$MYTEL_NATIVE_WORK/bundle.tgz" "$MYTELLPBX_BUNDLE_URL" \
            || die 'Bundle download failed.'
    fi
    local actual
    actual=$(sha256sum "$MYTEL_NATIVE_WORK/bundle.tgz") || die 'Cannot hash bundle.'
    [ "${actual%% *}" = "$MYTELLPBX_BUNDLE_SHA256" ] || die 'Bundle checksum differs from the reviewed release pin.'
}

extract_bundle() {
    # Validate all headers before writing; never extract links or archive owners.
    "$MYTEL_PYTHON" -B - "$MYTEL_NATIVE_WORK/bundle.tgz" "$MYTEL_NATIVE_WORK/payload" \
        "mytelpbx-bundle-${MYTELLPBX_VERSION}" <<'PY_EXTRACT' || die 'Bundle extraction failed.'
import pathlib, sys, tarfile
archive, target, prefix = sys.argv[1:]
destination = pathlib.Path(target)
if destination.exists() or destination.is_symlink():
    raise ValueError('Existing extraction directory refused')
with tarfile.open(archive, 'r:gz') as source:
    members, names, total = [], {}, 0
    for item in source:
        if len(members) >= 10000:
            raise ValueError('Bundle member limit exceeded')
        if item.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE) or item.sparse is not None:
            raise ValueError('Bundle links, sparse and special files refused')
        name = item.name[:-1] if item.isdir() and item.name.endswith('/') else item.name
        relative = pathlib.PurePosixPath(name)
        if (not name or relative.is_absolute() or str(relative) != name
                or '..' in relative.parts or '\\' in name or ':' in name
                or any(ord(c) < 32 or ord(c) == 127 for c in name) or name in names
                or relative.parts[0] != prefix):
            raise ValueError('Noncanonical, duplicate or unexpected bundle path')
        if item.size < 0 or item.size > 128 * 1024 * 1024 or (item.isdir() and item.size):
            raise ValueError('Bundle member size exceeded')
        total += item.size
        if total > 512 * 1024 * 1024:
            raise ValueError('Bundle expanded size exceeded')
        names[name] = item
        members.append((item, relative))
    if not members:
        raise ValueError('Empty bundle refused')
    for item, relative in members:
        if any(str(parent) in names and not names[str(parent)].isdir()
               for parent in relative.parents if str(parent) != '.'):
            raise ValueError('Bundle file is a parent directory')
    destination.mkdir(mode=0o700)
    for item, relative in members:
        output = destination.joinpath(*relative.parts)
        if item.isdir():
            output.mkdir(parents=True, exist_ok=True)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(item) as incoming, output.open('xb') as outgoing:
                remaining = item.size
                while remaining:
                    block = incoming.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError('Bundle file is truncated')
                    outgoing.write(block)
                    remaining -= len(block)
            output.chmod(0o755 if item.mode & 0o111 else 0o644)
PY_EXTRACT
    MYTEL_BUNDLE_ROOT="$MYTEL_NATIVE_WORK/payload/mytelpbx-bundle-${MYTELLPBX_VERSION}"
    [ -f "$MYTEL_BUNDLE_ROOT/SHA256SUMS" ] && [ -f "$MYTEL_BUNDLE_ROOT/manifest.json" ] \
        || die 'Bundle integrity manifests are missing.'
    (cd "$MYTEL_BUNDLE_ROOT" && sha256sum --check --quiet SHA256SUMS) \
        || die 'Bundle internal checksums failed.'
    "$MYTEL_PYTHON" -B "$MYTEL_BUNDLE_ROOT/installer/vendor-native/derive-native.py" --check \
        || die 'Pinned native source or its reviewed derivation differs.'
}

main() {
    preflight "$@"
    exec 9>/var/run/mytelpbx-native-install.lock
    flock -n 9 || die 'Another native installation is running.'
    umask 077
    MYTEL_NATIVE_WORK=$(mktemp -d /var/tmp/mytelpbx-native.XXXXXXXX) \
        || die 'Cannot create a private workspace.'
    printf 'MytelPBX %s / Mytel.one\nNative source and logs: %s\n' \
        "$MYTELLPBX_VERSION" "$MYTEL_NATIVE_WORK"
    download_bundle
    extract_bundle
    export MYTEL_BUNDLE_ROOT MYTEL_NATIVE_WORK MYTEL_PYTHON
    if [ -n "${MYTEL_MEDIA_ROOT:-}" ]; then
        bash "$MYTEL_BUNDLE_ROOT/installer/vendor-native/run-offline.sh"
    else
        bash "$MYTEL_BUNDLE_ROOT/installer/vendor-native/mytelpbx-netinstall.sh"
    fi
    local status=$?
    [ "$status" = 0 ] || die "Native installation stopped (status $status). Inspect $MYTEL_NATIVE_WORK/netinstall.log."
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
