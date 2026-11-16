#!/bin/bash
# ==========================================================================
# MyTellPBX one-line installer for Rocky Linux 8.10 (x86_64)
# Version: 7.6.1
#
# Installs the complete MyTellPBX contact-center platform:
#   - telephony base (Asterisk 20, MariaDB, Apache, PHP 7.4, framework)
#   - Persian RTL panel navigation with the PBX technical settings console LTR
#   - full MyTel branding, dark/light themes, Persian language
#   - pinned MytelDesk 1.1.1 with automatic verified CPU VAD
#
# Quick start (download, review, run — never pipe straight into bash):
#   curl -fsSL -o install-mytellpbx.sh \
#     https://github.com/DashSaman/MyTellPBX/releases/download/v7.6.1/install-mytellpbx.sh
#   bash install-mytellpbx.sh
#
# Environment overrides (all optional):
#   MYTELL_ASTVER          Asterisk major version; only "20" is supported.
#   MYTELL_LANG            Panel language; only "fa" is supported.
#   MYTELL_REBOOT          1 = reboot automatically after success (default 0).
#   MYTELL_MYSQL_ROOT_PASS Predefined MariaDB root password (allowed chars:
#                          A-Z a-z 0-9 space . @ = _ ! -).
#   MYTELL_ADMIN_PASS      Predefined panel admin password (same rules).
#                          Missing passwords are requested once on a terminal;
#                          Enter generates a password. Unattended runs generate
#                          missing values. Saved credentials are never rotated.
#   MYTELL_SKIP_UPDATE     1 = skip the initial OS update step.
#   MYTELL_DESK_PUBLIC_URL HTTPS origin for the desk (optional; defaults to
#                          the server address, preserves an owned Desk URL).
#   MYTELL_BUNDLE_URL      Internal/test override of the bundle download URL.
#   MYTELL_BUNDLE_FILE     Internal/test path to a pre-downloaded bundle
#                          (skips the network checks for offline lab runs).
#
# Logs:      /var/log/mytelpbx-install.log
# State:     /var/lib/mytelpbx-installer/
# Credentials (0600, root only): /root/mytelpbx-credentials.txt
#
# Security notes (documented in docs/INSTALL.en.md):
#   - SELinux is set to disabled (required by the telephony framework).
#   - firewalld is KEPT ENABLED; web (80/443), SIP (5060) and RTP
#     (10000-20000/udp) ports are opened. SSH access is preserved.
# ==========================================================================

set -u
set -o pipefail

MYTELLPBX_VERSION="7.6.1"
MYTELLPBX_BUNDLE="mytelpbx-bundle-7.6.1.tgz"
# Expected SHA-256 of the bundle asset (filled in by the release builder).
MYTELLPBX_BUNDLE_SHA256="2f995ca8fedfdb5f133cbd8225072c93af4f8376066494b729f30a3573ac3c30"
MYTELLPBX_GITHUB="https://github.com/DashSaman/MyTellPBX"
MYTELLPBX_RELEASE_TAG="v7.6.1"
MYTELLPBX_BUNDLE_URL="${MYTELL_BUNDLE_URL:-${MYTELLPBX_GITHUB}/releases/download/${MYTELLPBX_RELEASE_TAG}/${MYTELLPBX_BUNDLE}}"

LOG="/var/log/mytelpbx-install.log"
STATE_DIR="/var/lib/mytelpbx-installer"
LOCK_FILE="/var/run/mytelpbx-install.lock"
CRED_FILE="/root/mytelpbx-credentials.txt"
WORK_DIR=""
WORK_DIR_OWNED=""
WORK_DIR_FINGERPRINT=""
BUNDLE_TMP=""
BUNDLE_FINAL=""
BUNDLE_ROOT=""
BUNDLE_DIR=""

ASTVER="${MYTELL_ASTVER:-20}"
LANG_SEL="${MYTELL_LANG:-fa}"
REBOOT_AFTER="${MYTELL_REBOOT:-0}"
SKIP_UPDATE="${MYTELL_SKIP_UPDATE:-0}"

WEB_ROOT="/var/www/html"
THEME_DST="${WEB_ROOT}/themes/mytel"
ADMIN_ASSETS="${WEB_ROOT}/admin/assets/mytel"
SETTINGS_DB="/var/www/db/settings.db"
FA_LANG="${WEB_ROOT}/lang/fa.lang"
PASS_RE='^[A-Za-z0-9 ._@=!-]+$'

log()   { printf '%s\n' "$*" >>"$LOG"; }
say()   { printf '\033[1;36m[MyTellPBX]\033[0m %s\n' "$*"; log "INFO: $*"; }
step()  { printf '\033[1;35m==> %s\033[0m\n' "$*"; log "STEP: $*"; }
warn()  { printf '\033[1;33m[!] %s\033[0m\n' "$*"; log "WARN: $*"; }
die()   {
    printf '\n\033[1;31m[MyTellPBX] نصب در مرحله «%s» متوقف شد\033[0m\n' "$*" 1>&2
    printf '\033[1;31mگزارش کامل: %s\033[0m\n' "$LOG" 1>&2
    log "FATAL: $*"
    exit 1
}

stage_done() { [ -f "${STATE_DIR}/stages/$1.done" ]; }
mark_stage() {
    mkdir -p "${STATE_DIR}/stages" || die "cannot create installer stage directory"
    touch "${STATE_DIR}/stages/$1.done" || die "cannot persist installer stage marker: $1"
    log "STAGE-COMPLETE: $1" || die "cannot persist installer stage completion log: $1"
}

run_logged() { "$@" >>"$LOG" 2>&1; }

# DNF alone has a public, rate-limited counter stream. Never pass password
# initialization or arbitrary commands through this logger.
run_dnf_logged() {
    local kind="$1"; shift
    PYTHONIOENCODING=utf-8 "${PY_BIN}" -u -B "${BUNDLE_DIR}/installer/dnf-progress.py" --log "${LOG}" --kind "${kind}" --check-log 9>&- || return 1
    LC_ALL=C dnf "$@" 9>&- 2>&1 | PYTHONIOENCODING=utf-8 "${PY_BIN}" -u -B "${BUNDLE_DIR}/installer/dnf-progress.py" --log "${LOG}" --kind "${kind}" 9>&-
    local statuses=("${PIPESTATUS[@]}")
    [ "${statuses[0]}" = "0" ] || return "${statuses[0]}"
    return "${statuses[1]}"
}

# mysql helper: works whether root is passwordless or already passworded
# (credentials file is loaded before use; safe to call after ensure_credentials)
mysql_any() {
    if mysql -N -e "SELECT 1" </dev/null >/dev/null 2>&1; then
        mysql "$@"
    else
        mysql_with_password "${MYSQL_ROOT_PASS:-}" "$@"
    fi
}

mysql_with_password() {
    local password="$1"; shift
    MYSQL_PWD="${password}" mysql "$@"
}

normalize_framework_mysql() {
    local tmp_pwd
    tmp_pwd=$(openssl rand -hex 12)
    printf "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('%s');\n" "${tmp_pwd}" | mysql >>"$LOG" 2>&1 || true
    printf "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('');\n" | mysql_with_password "${tmp_pwd}" >>"$LOG" 2>&1 \
        || die "mariadb root password normalization failed"
}

ensure_amp_admin_password() {
    printf "UPDATE asterisk.ampusers SET password_sha1=SHA1('%s') WHERE username='admin';\n" "${ADMIN_PASS}" | mysql_any -N >>"$LOG" 2>&1 \
        || die "cannot update ampusers admin password"
}

initialize_framework_passwords() {
    [ -f "${BUNDLE_DIR}/installer/password-init.php" ] || die "private password initialization adapter missing from bundle"
    local web_password="${1:-${ADMIN_PASS}}"
    printf '%s\n%s\n' "${MYSQL_ROOT_PASS}" "${web_password}" | run_logged php "${BUNDLE_DIR}/installer/password-init.php" \
        || die "password initialization failed (see ${LOG})"
}

verify_mysql_root_password() {
    local config="${1:-/etc/issabel.conf}"
    MYSQL_EXPECTED_PASSWORD="${MYSQL_ROOT_PASS}" "${PY_BIN}" -B - "${config}" <<'PY'
import os, sys
try:
    with open(sys.argv[1], encoding='utf-8') as source:
        values = [line.rstrip('\r\n').split('=', 1)[1] for line in source if line.startswith('mysqlrootpwd=')]
    valid = len(values) == 1 and values[0] == os.environ['MYSQL_EXPECTED_PASSWORD']
except (OSError, ValueError): valid = False
raise SystemExit(0 if valid else 1)
PY
}

verify_mysql_authentication() {
    # Ignore option files and inherited passwords: a saved config value alone
    # does not prove authentication, and unix_socket can silently ignore a key.
    printf 'SELECT 1;\n' | MYSQL_PWD="${MYSQL_ROOT_PASS}" mysql --no-defaults --user=root --protocol=socket -N \
        >/dev/null 2>&1 || die "chosen MariaDB root password does not authenticate"
    if printf 'SELECT 1;\n' | MYSQL_PWD='' mysql --no-defaults --user=root --protocol=socket -N >/dev/null 2>&1; then
        die "MariaDB root still accepts an empty password"
    fi
    local wrong_password
    wrong_password=$(openssl rand -hex 24) || die "cannot generate authentication negative control"
    [ -n "${wrong_password}" ] && [ "${wrong_password}" != "${MYSQL_ROOT_PASS}" ] \
        || die "invalid authentication negative control"
    if printf 'SELECT 1;\n' | MYSQL_PWD="${wrong_password}" mysql --no-defaults --user=root --protocol=socket -N >/dev/null 2>&1; then
        die "MariaDB root accepts an incorrect password"
    fi
}

verify_amp_admin_password() {
    local amp_ok='' try
    for try in 1 2 3 4 5; do
        amp_ok=$(printf "SELECT COUNT(*) FROM asterisk.ampusers WHERE username='admin' AND password_sha1=SHA1('%s');\n" "${ADMIN_PASS}" | mysql_any -N 2>/dev/null || true)
        [ "${amp_ok}" = "1" ] && return 0
        sleep 2
    done
    die "admin password not in force on ampusers"
}

verify_asterisk_service() {
    systemctl is-active --quiet asterisk || die "self-check: asterisk is not active"
    # The supported Asterisk20 RPM provides a native multi-user.target unit.
    # Exit 0 also covers static/generated/runtime states, which are not proof
    # that this installed service will be enabled after a cold reboot.
    local enabled_state
    enabled_state=$(systemctl is-enabled asterisk 2>>"$LOG") || die "self-check: asterisk is not enabled at boot"
    [ "${enabled_state}" = "enabled" ] || die "self-check: asterisk requires persistent enabled state"
    asterisk -rx 'core show version' >>"$LOG" 2>&1 || die "self-check: asterisk CLI is not responding"
}

# Whole-string validation (grep is line-oriented and would accept values
# whose FIRST line is valid; a negated glob class matches one character
# anywhere in the string, so a single bad character fails the check).
valid_password() {
    local s="$1"
    [ "${#s}" -gt 0 ] || return 1
    case "${s}" in
        *\'*|*$'\n'*|*$'\r'*) return 1 ;;
        *[!A-Za-z0-9._@=!\ -]*) return 1 ;;
    esac
    return 0
}

# A base-OS installer is not a general PBX updater. A directory or old stage
# marker alone is not ownership. Resume only the exact version and bundle that
# established this root-private source receipt before any package/secret work.
guard_install_source() {
    [ ! -L "${STATE_DIR}" ] || die "installer state symlink refused"
    [ -e "${STATE_DIR}" ] || return 0
    [ -d "${STATE_DIR}" ] || die "unknown installer state path"
    [ "$(stat -c '%u' -- "${STATE_DIR}")" = "0" ] && [ "$(stat -c '%a' -- "${STATE_DIR}")" = "700" ] \
        || die "installer state must be root-owned and private"
    if [ ! -e "${STATE_DIR}/source.json" ] && [ ! -L "${STATE_DIR}/source.json" ]; then
        # A process may stop between mkdir and its first atomic receipt. Recover
        # only an empty private directory on a positively inventoried fresh OS.
        [ -z "$(find "${STATE_DIR}" -mindepth 1 -maxdepth 1 -print -quit)" ] \
            || die "unknown/legacy installer state; use reviewed UI maintenance, not the fresh-system installer"
        require_fresh_base
        return 0
    fi
    [ -f "${STATE_DIR}/source.json" ] && [ ! -L "${STATE_DIR}/source.json" ] || die "invalid installer source receipt"
    [ "$(stat -c '%u' -- "${STATE_DIR}/source.json")" = "0" ] && [ "$(stat -c '%a' -- "${STATE_DIR}/source.json")" = "600" ] \
        || die "installer source receipt must be root-owned and private"
    "${PY_BIN}" -B - "${STATE_DIR}/source.json" "${MYTELLPBX_VERSION}" "${MYTELLPBX_BUNDLE_SHA256}" <<'PY' \
        || die "different or invalid installer source; use reviewed UI maintenance instead of an OS upgrade"
import json, re, sys
try:
    with open(sys.argv[1], encoding='utf-8') as source: value = json.load(source)
    expected = dict(owner='MyTellPBX', schema=1, version=sys.argv[2], bundle_sha256=sys.argv[3])
    valid = value == expected and type(value.get('schema')) is int and re.fullmatch('[0-9a-f]{64}', sys.argv[3]) is not None
except (OSError, ValueError): valid = False
if not valid: raise SystemExit(1)
PY
}

require_fresh_base() {
    local package status
    for package in issabel httpd mariadb-server asterisk20 elastix; do
        if rpm --quiet -q "${package}"; then
            die "existing PBX packages detected; use reviewed maintenance instead of the fresh-system installer"
        else
            status=$?
            [ "${status}" = "1" ] || die "cannot establish fresh-system package inventory"
        fi
    done
}

write_install_source() {
    if [ -e "${STATE_DIR}/source.json" ]; then guard_install_source; return; fi
    "${PY_BIN}" -B - "${STATE_DIR}" "${MYTELLPBX_VERSION}" "${MYTELLPBX_BUNDLE_SHA256}" <<'PY' \
        || die "cannot establish private installer source receipt"
import json, os, pathlib, re, sys, tempfile
root = pathlib.Path(sys.argv[1])
if root.is_symlink() or not root.is_dir() or list(root.iterdir()): raise SystemExit('Refusing nonempty unknown installer state')
if not re.fullmatch('[0-9a-f]{64}', sys.argv[3]): raise SystemExit('Release bundle checksum has not been finalized')
fd, name = tempfile.mkstemp(prefix='.source-', dir=str(root))
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(dict(owner='MyTellPBX', schema=1, version=sys.argv[2], bundle_sha256=sys.argv[3]), out, sort_keys=True)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    os.chmod(name, 0o600); os.replace(name, str(root / 'source.json'))
finally:
    if os.path.exists(name): os.unlink(name)
PY
}

repository_metadata_reachable() {
    # Use an official HTTPS repository directly. A dead mirror-list service
    # must not veto a healthy package mirror; HTML/empty 200s are not metadata.
    local origin
    for origin in https://repo.us.issabel.org https://repo.issabel.org; do
        if curl -fsSL --proto '=https' --proto-redir '=https' \
            --connect-timeout 8 --max-time 20 --max-filesize 1048576 \
            "${origin}/issabel/5/base/x86_64/repodata/repomd.xml" 2>>"$LOG" \
            | "${PY_BIN}" -c 'import sys, xml.etree.ElementTree as ET
try:
    document = sys.stdin.read(1048577)
    if "<!DOCTYPE" in document.upper() or "<!ENTITY" in document.upper(): raise ValueError("DTD not allowed")
    root = ET.fromstring(document)
    ns = "{http://linux.duke.edu/metadata/repo}"
    valid = root.tag == ns + "repomd" and any(item.get("type") == "primary" and item.find(ns + "location") is not None and item.find(ns + "location").get("href", "").strip() for item in root.findall(ns + "data"))
except (ValueError, ET.ParseError):
    valid = False
raise SystemExit(0 if valid else 1)' >/dev/null; then
            return 0
        fi
    done
    return 1
}

check_network_prerequisites() {
    # An offline bundle or already completed base package stages must not be
    # rejected merely because an unrelated legacy mirror is unavailable.
    [ -z "${MYTELL_BUNDLE_FILE:-}" ] || return 0
    if [ ! -f "${BUNDLE_FINAL}" ]; then
        curl -fsS --max-time 30 -o /dev/null "${MYTELLPBX_GITHUB}" \
            || die "cannot reach github.com (DNS/TLS)"
        local http_code
        http_code=$(curl -fsSL --max-time 60 -o /dev/null -w '%{http_code}' -r 0-0 \
            "${MYTELLPBX_BUNDLE_URL}" 2>>"$LOG" || echo 000)
        [ "${http_code}" = "206" ] || [ "${http_code}" = "200" ] \
            || die "release bundle not reachable (HTTP ${http_code})"
    fi
    if ! stage_done packages1 || ! stage_done packages2; then
        repository_metadata_reachable || die "official HTTPS telephony repositories unreachable or invalid"
    fi
    if ! stage_done repos; then
        curl -fsSI --max-time 30 -o /dev/null \
            "https://rpms.remirepo.net/enterprise/remi-release-8.rpm" \
            || die "php module repository unreachable"
    fi
}

# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------
preflight() {
    step "بررسی پیش‌نیازها"

    [ "$(id -u)" -eq 0 ] || die "root required"

    if command -v python3 >/dev/null 2>&1; then PY_BIN="$(command -v python3)"
    elif [ -x /usr/libexec/platform-python ]; then PY_BIN="/usr/libexec/platform-python"
    else die "python3 not available"; fi
    "${PY_BIN}" -B -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,6) else 1)' \
        || die "python >= 3.6 required"
    guard_install_source

    # Exact platform: Rocky Linux 8.10 x86_64
    grep -q "Rocky Linux release 8.10" /etc/redhat-release \
        || die "unsupported OS: this installer targets Rocky Linux 8.10 exactly (got: $(cat /etc/redhat-release))"
    [ "$(uname -m)" = "x86_64" ] || die "unsupported architecture: $(uname -m) (x86_64 required)"

    # Enough resources
    local free_gb
    free_gb=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
    [ "${free_gb}" -ge 8 ] || die "not enough disk space: ${free_gb}G free (8G required)"
    local mem_kb
    mem_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    [ "${mem_kb}" -ge 1500000 ] || die "not enough RAM (1.5G required)"

    # Option validation — only supported values
    [ "${ASTVER}" = "20" ] || die "MYTELL_ASTVER: only 20 is supported"
    [ "${LANG_SEL}" = "fa" ] || die "MYTELL_LANG: only fa is supported"
    [ "${REBOOT_AFTER}" = "0" ] || [ "${REBOOT_AFTER}" = "1" ] || die "MYTELL_REBOOT must be 0 or 1"
    [ "${SKIP_UPDATE}" = "0" ] || [ "${SKIP_UPDATE}" = "1" ] || die "MYTELL_SKIP_UPDATE must be 0 or 1"
    if [ -n "${MYTELL_MYSQL_ROOT_PASS:-}" ]; then
        valid_password "${MYTELL_MYSQL_ROOT_PASS}" || die "MYTELL_MYSQL_ROOT_PASS: invalid characters"
    fi
    if [ -n "${MYTELL_ADMIN_PASS:-}" ]; then
        valid_password "${MYTELL_ADMIN_PASS}" || die "MYTELL_ADMIN_PASS: invalid characters"
    fi

    # Fresh-server guard: refuse an unrelated pre-existing PBX install
    if [ ! -d "${STATE_DIR}" ]; then
        require_fresh_base
    fi

    # Tools required by the installer itself
    command -v curl  >/dev/null 2>&1 || die "curl not found"
    command -v php   >/dev/null 2>&1 || warn "php not present yet (expected on fresh system)"
    # Rocky minimal ships only platform-python; either interpreter works
    if command -v python3 >/dev/null 2>&1; then
        PY_BIN="$(command -v python3)"
    elif [ -x /usr/libexec/platform-python ]; then
        PY_BIN="/usr/libexec/platform-python"
    else
        die "python3 not available"
    fi
    "${PY_BIN}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,6) else 1)' \
        || die "python >= 3.6 required for theme patchers"
    command -v flock >/dev/null 2>&1 || die "flock not found"

    check_network_prerequisites

    say "پیش‌نیازها تأیید شد"
}

acquire_lock() {
    exec 9>"${LOCK_FILE}"
    flock -n 9 || die "another installer run holds ${LOCK_FILE}"
}

check_workspace() {
    [ -n "${WORK_DIR}" ] && [ -d "${WORK_DIR}" ] && [ ! -L "${WORK_DIR}" ] \
        || die "private installer workspace missing or symlinked"
    [ "$(cd -- "${WORK_DIR}" && pwd -P)" = "${WORK_DIR}" ] \
        || die "installer workspace is not a canonical absolute directory"
    [ "$(stat -c '%u' -- "${WORK_DIR}")" = "0" ] && [ "$(stat -c '%a' -- "${WORK_DIR}")" = "700" ] \
        || die "installer workspace must be root-owned and private"
    local path relative
    for path in "${BUNDLE_TMP}" "${BUNDLE_FINAL}" "${BUNDLE_ROOT}"; do
        case "${path}" in "${WORK_DIR}/"*) ;; *) die "bundle path outside private workspace";; esac
        relative="${path#"${WORK_DIR}/"}"
        case "${relative}" in ''|.|..|*/*) die "bundle path must be a direct workspace child";; esac
        [ ! -L "${path}" ] || die "bundle path symlink refused"
        if [ -e "${path}" ]; then
            [ "$(stat -c '%u' -- "${path}")" = "0" ] || die "bundle path has unsafe ownership"
            if [ "${path}" = "${BUNDLE_ROOT}" ]; then
                [ -d "${path}" ] || die "bundle extraction path has unexpected type"
            else
                [ -f "${path}" ] || die "bundle download path has unexpected type"
            fi
        fi
    done
}

cleanup_workspace() {
    [ -n "${WORK_DIR_OWNED}" ] || return 0
    # Never remove a substituted directory, symlink, or an operator's path.
    if [ -d "${WORK_DIR_OWNED}" ] && [ ! -L "${WORK_DIR_OWNED}" ] \
        && [ "$(stat -c '%d:%i:%u:%a' -- "${WORK_DIR_OWNED}")" = "${WORK_DIR_FINGERPRINT}" ]; then
        rm -rf -- "${WORK_DIR_OWNED}"
    else
        warn "private workspace changed; automatic cleanup skipped"
    fi
}

initialize_workspace() {
    [ -z "${WORK_DIR_OWNED}" ] || die "installer workspace already initialized"
    WORK_DIR=$(umask 077; mktemp -d /tmp/mytelpbx-install.XXXXXXXX) || die "cannot create private installer workspace"
    BUNDLE_TMP="${WORK_DIR}/${MYTELLPBX_BUNDLE}.part"
    BUNDLE_FINAL="${WORK_DIR}/${MYTELLPBX_BUNDLE}"
    BUNDLE_ROOT="${WORK_DIR}/bundle"
    check_workspace
    readonly WORK_DIR_OWNED="${WORK_DIR}"
    readonly WORK_DIR_FINGERPRINT="$(stat -c '%d:%i:%u:%a' -- "${WORK_DIR}")"
    trap cleanup_workspace EXIT
}

# --------------------------------------------------------------------------
# Bundle download + verification (before any system mutation)
# --------------------------------------------------------------------------
verify_bundle() {
    check_workspace
    # Internal/test affordance: a pre-downloaded bundle file skips the network
    if [ -n "${MYTELL_BUNDLE_FILE:-}" ]; then
        [ -f "${MYTELL_BUNDLE_FILE}" ] || die "MYTELL_BUNDLE_FILE not found: ${MYTELL_BUNDLE_FILE}"
        cp -f "${MYTELL_BUNDLE_FILE}" "${BUNDLE_FINAL}"
    fi
    if [ ! -f "${BUNDLE_FINAL}" ]; then
        say "دانلود بستهٔ قالب و امکانات"
        rm -f "${BUNDLE_TMP}"
        local ok=0 attempt
        for attempt in 1 2 3; do
            if curl -fSL --connect-timeout 30 --max-time 600 \
                 --retry 2 --retry-delay 3 \
                 -o "${BUNDLE_TMP}" "${MYTELLPBX_BUNDLE_URL}" >>"$LOG" 2>&1; then
                ok=1; break
            fi
            warn "دانلود ناموفق (تلاش ${attempt}/3)"
            sleep 3
        done
        [ "${ok}" = "1" ] || die "bundle download failed"
        mv -f "${BUNDLE_TMP}" "${BUNDLE_FINAL}"
    fi

    say "راستی‌آزمایی بسته"
    local got
    got=$(sha256sum "${BUNDLE_FINAL}" | awk '{print $1}')
    [ "${got}" = "${MYTELLPBX_BUNDLE_SHA256}" ] \
        || die "bundle checksum mismatch (expected ${MYTELLPBX_BUNDLE_SHA256}, got ${got})"

    # Safety checks BEFORE extraction: reject absolute paths, parent refs,
    # symlinks and hardlinks inside the archive.
    if tar -tzf "${BUNDLE_FINAL}" 2>>"$LOG" | grep -E '(^/|(^|/)\.\.($|/))' >/dev/null; then
        die "bundle contains unsafe path names"
    fi
    if tar -tvzf "${BUNDLE_FINAL}" 2>>"$LOG" | awk '{print substr($1,1,1)}' | grep -Eq '^(l|h)$'; then
        die "bundle contains links"
    fi

    rm -rf "${BUNDLE_ROOT}"
    mkdir -p "${BUNDLE_ROOT}"
    tar -xzf "${BUNDLE_FINAL}" -C "${BUNDLE_ROOT}" >>"$LOG" 2>&1 \
        || die "bundle extraction failed"
    local tops
    tops=$(ls -A "${BUNDLE_ROOT}" | wc -l)
    [ "${tops}" = "1" ] || die "bundle layout unexpected"
    BUNDLE_DIR="${BUNDLE_ROOT}/$(ls -A "${BUNDLE_ROOT}")"

    [ -f "${BUNDLE_DIR}/manifest.json" ] || die "bundle manifest.json missing"
    [ -f "${BUNDLE_DIR}/SHA256SUMS" ]    || die "bundle SHA256SUMS missing"

    # Verify every shipped checksum after extraction, not just an initial sample.
    ( cd "${BUNDLE_DIR}" && sha256sum -c --quiet SHA256SUMS ) >>"$LOG" 2>&1 \
        || die "bundle internal checksums failed"
}

# --------------------------------------------------------------------------
# Stage 1: repositories + PHP module stream
# --------------------------------------------------------------------------
repair_platform_catalog() {
    local mode="${1:-optional}" vendor args=()
    run_logged "${PY_BIN}" -B "${BUNDLE_DIR}/installer/repair-repository-transport.py" --if-present \
        || die "repository transport repair failed; existing configuration retained"
    if [ -e /etc/yum.repos.d/mytelpbx-base.repo ] || [ -L /etc/yum.repos.d/mytelpbx-base.repo ]; then
        [ "${mode}" = mandatory ] || args+=(--if-present)
        run_logged "${PY_BIN}" -B "${BUNDLE_DIR}/installer/repair-platform-repositories.py" "${args[@]}" \
            || die "platform repository repair refused; existing configuration retained (see ${LOG})"
    else
        [ "${mode}" != mandatory ] && ! stage_done repos \
            || die "reviewed platform repository catalog is missing"
        for vendor in Issabel.repo Issabel5.repo commercial-addons.repo; do
            [ ! -e "/etc/yum.repos.d/${vendor}" ] && [ ! -L "/etc/yum.repos.d/${vendor}" ] \
                || die "vendor repositories exist without the reviewed platform catalog"
        done
    fi
}

stage_cli_status() {
    step "آماده‌سازی نمایش وضعیت نصب خودکار"
    # Package updates may restore the vendor executable. Revalidate its exact
    # source on every run before framework initialization, including resumes.
    run_logged "${PY_BIN}" -B "${BUNDLE_DIR}/installer/patch-cli-status.py" \
        || die "CLI status repair refused; original executable retained (see ${LOG})"
    if command -v restorecon >/dev/null 2>&1; then
        run_logged restorecon /usr/bin/issabel-admin-passwords \
            || die "CLI status executable security context could not be restored"
    fi
}

stage_repos() {
    stage_done repos && return 0
    step "پیکربندی مخازن بسته‌ها"

    local repo_src="${BUNDLE_DIR}/installer/repos/mytelpbx-base.repo.in"
    [ -f "${repo_src}" ] || die "repo template missing from bundle"
    cp -f "${repo_src}" /etc/yum.repos.d/mytelpbx-base.repo
    chmod 644 /etc/yum.repos.d/mytelpbx-base.repo

    grep -qxF 'fastestmirror=True' /etc/dnf/dnf.conf 2>/dev/null || echo 'fastestmirror=True' >> /etc/dnf/dnf.conf

    # Remi repo + explicit PHP stream selection
    # On a resumed repo stage the RPM may already be present. Repair its
    # transport BEFORE any DNF command attempts metadata from the old HTTP URL.
    repair_platform_catalog
    run_dnf_logged repositories install -y dnf-plugins-core || die "dnf-plugins-core install failed"
    run_dnf_logged repositories install -y https://rpms.remirepo.net/enterprise/remi-release-8.rpm \
        || die "remi-release install failed"
    "${PY_BIN}" -B "${BUNDLE_DIR}/installer/repair-repository-transport.py" >>"$LOG" 2>&1 \
        || die "repository transport repair failed; review vendor repo files"
    run_dnf_logged repositories module reset -y php || true
    run_dnf_logged repositories module enable -y php:remi-7.4 || die "php:remi-7.4 module enable failed"
    run_logged dnf config-manager --set-enabled remi || true
    run_logged dnf config-manager --set-enabled powertools || true
    run_logged dnf config-manager --set-enabled devel || true

    run_dnf_logged repositories -q makecache || die "dnf makecache failed"
    mark_stage repos
}

# --------------------------------------------------------------------------
# Stage 2: OS update
# --------------------------------------------------------------------------
stage_update() {
    stage_done update && return 0
    [ "${SKIP_UPDATE}" = "1" ] && { mark_stage update; return 0; }
    step "به‌روزرسانی سیستم‌عامل"
    local attempt ok=0
    for attempt in 1 2 3; do
        if run_dnf_logged update -y update; then ok=1; break; fi
        warn "به‌روزرسانی ناموفق (تلاش ${attempt}/3) — میرور جایگزین آزمایش می‌شود"
        sleep 5
    done
    [ "${ok}" = "1" ] || die "OS update failed after retries (see ${LOG})"
    mark_stage update
}

install_pkg() {
    run_dnf_logged packages -y install "$@"
}

# --------------------------------------------------------------------------
# Stage 3/4: packages
# --------------------------------------------------------------------------
install_with_retry() {
    local label="$1"; shift
    local attempt ok=0
    for attempt in 1 2 3 4 5; do
        if install_pkg "$@"; then ok=1; break; fi
        warn "${label}: ناموفق (تلاش ${attempt}/5) — میرور جایگزین آزمایش می‌شود"
        sleep 5
    done
    [ "${ok}" = "1" ] || die "${label} failed after retries (see ${LOG})"
}

ensure_asterisk_identity() {
    local group_entry group_status account_entry account_status group_gid account_uid account_gid
    local group_pattern='^asterisk:[^:]*:([0-9]{1,9}):[^:]*$'
    local account_pattern='^asterisk:[^:]*:([0-9]{1,9}):([0-9]{1,9}):[^:]*:/var/lib/asterisk:/bin/bash$'
    group_entry=$(getent group asterisk); group_status=$?
    account_entry=$(getent passwd asterisk); account_status=$?
    case "${group_status}:${account_status}" in 0:0|0:2|2:2) ;; *) die "cannot inventory a compatible Asterisk service identity";; esac
    if [ "${group_status}" = "2" ]; then
        run_logged /usr/sbin/groupadd -r asterisk || die "cannot create Asterisk service group"
        group_entry=$(getent group asterisk) || die "Asterisk service group missing after creation"
    fi
    case "${group_entry}" in *$'\n'*) die "ambiguous Asterisk service group";; esac
    [[ "${group_entry}" =~ ${group_pattern} ]] || die "incompatible Asterisk service group"
    group_gid="${BASH_REMATCH[1]}"
    (( 10#${group_gid} > 0 && 10#${group_gid} < 1000 )) || die "Asterisk group conflicts with a non-service identity"
    if [ "${account_status}" = "2" ]; then
        run_logged /usr/sbin/useradd -r -g asterisk -c "Asterisk PBX" -s /bin/bash -d /var/lib/asterisk asterisk \
            || die "cannot create Asterisk service account"
        account_entry=$(getent passwd asterisk) || die "Asterisk service account missing after creation"
    fi
    case "${account_entry}" in *$'\n'*) die "ambiguous Asterisk service account";; esac
    [[ "${account_entry}" =~ ${account_pattern} ]] || die "incompatible Asterisk service account; existing account preserved"
    account_uid="${BASH_REMATCH[1]}"; account_gid="${BASH_REMATCH[2]}"
    (( 10#${account_uid} > 0 && 10#${account_uid} < 1000 && 10#${account_gid} == 10#${group_gid} )) \
        || die "Asterisk account conflicts with a non-service identity; existing account preserved"
}

stage_packages1() {
    stage_done packages1 && return 0
    step "نصب بسته‌های پایه (Asterisk 20 / MariaDB / Apache / PHP)"
    # RPMs assign file ownership during extraction, before post-base setup.
    ensure_asterisk_identity
    local list="${BUNDLE_DIR}/installer/packages/rocky8-stage1.txt"
    [ -f "${list}" ] || die "stage-1 package list missing from bundle"
    local pkgs
    pkgs=$(tr '\n' ' ' < "${list}")
    install_with_retry "stage-1 package install" ${pkgs}
    mark_stage packages1
}

stage_tls() {
    stage_done tls && return 0
    step "آماده‌سازی گواهی MyTellPBX برای سرویس‌های وب"
    [ -f "${BUNDLE_DIR}/installer/prepare-tls.py" ] || die "TLS preparation helper missing from bundle"
    run_logged "${PY_BIN}" -B "${BUNDLE_DIR}/installer/prepare-tls.py" \
        || die "TLS pair preparation failed; existing certificates retained (see ${LOG})"
    mark_stage tls
}

stage_packages2() {
    stage_done packages2 && return 0
    step "نصب ماژول‌های مرکز تماس"
    local list="${BUNDLE_DIR}/installer/packages/rocky8-stage2-asterisk20.txt"
    [ -f "${list}" ] || die "stage-2 package list missing from bundle"
    local pkgs
    pkgs=$(tr '\n' ' ' < "${list}")
    install_with_retry "stage-2 package install" ${pkgs}
    mark_stage packages2
}

# --------------------------------------------------------------------------
# Stage 5: base post-install
# --------------------------------------------------------------------------
stage_post_base() {
    stage_done post_base && return 0
    step "پیکربندی اولیهٔ سرویس‌های پایه"

    ensure_asterisk_identity

    systemctl enable mariadb.service >>"$LOG" 2>&1 || die "mariadb enable failed"
    systemctl start  mariadb           >>"$LOG" 2>&1 || die "mariadb start failed"
    # The RPM-initialized system tables can predate the running server
    # version; until mysql_upgrade runs, CREATE USER/GRANT can silently
    # fail to take effect (users created without working passwords),
    # which breaks the framework installer's DB user mid-run.
    run_logged mysql_upgrade --force \
        || die "mysql_upgrade failed (system tables unusable)"
    systemctl enable httpd             >>"$LOG" 2>&1 || die "httpd enable failed"

    # SELinux: the telephony framework requires it disabled (documented).
    setenforce 0 >/dev/null 2>&1 || true
    sed -i 's/\(^SELINUX=\).*/\SELINUX=disabled/' /etc/selinux/config

    # Firewall: KEEP firewalld enabled; open PBX ports, preserve SSH.
    if systemctl is-enabled --quiet firewalld 2>/dev/null || systemctl is-active --quiet firewalld; then
        systemctl enable --now firewalld >>"$LOG" 2>&1 || true
        firewall-cmd --permanent --add-service=http  >>"$LOG" 2>&1 || true
        firewall-cmd --permanent --add-service=https >>"$LOG" 2>&1 || true
        firewall-cmd --permanent --add-port=5060/tcp >>"$LOG" 2>&1 || true
        firewall-cmd --permanent --add-port=5060/udp >>"$LOG" 2>&1 || true
        firewall-cmd --permanent --add-port=5061/tcp >>"$LOG" 2>&1 || true
        firewall-cmd --permanent --add-port=10000-20000/udp >>"$LOG" 2>&1 || true
        firewall-cmd --reload >>"$LOG" 2>&1 || true
    else
        warn "firewalld not present; ports not configured"
    fi

    # Asterisk config patches (upstream flow)
    grep -q 'noload => cdr_mysql.so' /etc/asterisk/modules_additional.conf 2>/dev/null \
        || echo "noload => cdr_mysql.so" >> /etc/asterisk/modules_additional.conf
    mkdir -p /var/log/asterisk/cdr-csv
    if [ -f /etc/asterisk/extensions_custom.conf.sample ] && [ ! -f /etc/asterisk/extensions_custom.conf ]; then
        mv /etc/asterisk/extensions_custom.conf.sample /etc/asterisk/extensions_custom.conf
    fi

    /usr/sbin/amportal chown >>"$LOG" 2>&1 || true

    mark_stage post_base
}

# --------------------------------------------------------------------------
# Credentials (created BEFORE framework init; never rotated on rerun)
# --------------------------------------------------------------------------
credential_input_is_tty() { [ -t 0 ] && [ -t 2 ]; }

choose_password() {
    local variable="$1" selected="$2" prompt="$3"
    if [ -z "${selected}" ] && credential_input_is_tty; then
        printf '%s (Enter = تولید خودکار): ' "${prompt}" >&2
        IFS= read -r -s selected || { printf '\n' >&2; die "password input interrupted; no credentials saved"; }
        printf '\n' >&2
    fi
    if [ -z "${selected}" ]; then
        selected=$(openssl rand -hex 24) || die "cannot generate password"
    fi
    valid_password "${selected}" || die "password contains unsupported characters; no credentials saved"
    printf -v "${variable}" '%s' "${selected}"
}

ensure_credentials() {
    if [ -e "${CRED_FILE}" ] || [ -L "${CRED_FILE}" ]; then
        # Validate the exact data grammar before sourcing. Unknown commands,
        # duplicate keys, symlinks and non-private files are never executed.
        "${PY_BIN}" -B - "${CRED_FILE}" <<'PY' || die "saved credentials are invalid or not private; no changes made"
import os, re, stat, sys
try:
    path = sys.argv[1]
    meta = os.lstat(path)
    valid = stat.S_ISREG(meta.st_mode)
    if os.name == 'posix':
        valid = valid and meta.st_uid == os.geteuid() and stat.S_IMODE(meta.st_mode) == 0o600
    if not valid: raise ValueError('unsafe credentials')
    values = {}
    with open(path, encoding='utf-8', newline='') as source:
        for raw in source:
            line = raw.rstrip('\n')
            if not line or line.startswith('#'): continue
            match = re.fullmatch(r"(MYSQL_ROOT_PASS|ADMIN_PASS)='([A-Za-z0-9 ._@=!\-]+)'", line)
            if not match or match.group(1) in values: valid = False; break
            values[match.group(1)] = match.group(2)
    valid = valid and set(values) == {'MYSQL_ROOT_PASS', 'ADMIN_PASS'}
except (OSError, ValueError): valid = False
raise SystemExit(0 if valid else 1)
PY
        say "رمزهای موجود حفظ شد (اجرای مجدد)"
        # shellcheck disable=SC1090
        . "${CRED_FILE}"
        return 0
    fi
    # Collect and validate both before creating any final credential file.
    # At most two hidden reads; supplied environment values skip their prompt.
    choose_password ADMIN_PASS "${MYTELL_ADMIN_PASS:-}" 'رمز مدیر پنل'
    choose_password MYSQL_ROOT_PASS "${MYTELL_MYSQL_ROOT_PASS:-}" 'رمز MariaDB'
    local credential_tmp
    credential_tmp=$(umask 077; mktemp "${CRED_FILE}.tmp.XXXXXXXX") || die "cannot create private credential file"
    if ! (umask 077; cat > "${credential_tmp}" <<EOF
# MyTellPBX credentials - $(date '+%Y-%m-%d %H:%M:%S')
# Keep this file secret (mode 0600, root only).
MYSQL_ROOT_PASS='${MYSQL_ROOT_PASS}'
ADMIN_PASS='${ADMIN_PASS}'
EOF
        [ "$?" = "0" ] || exit 1
        chmod 600 "${credential_tmp}"
    ) || ! ln -- "${credential_tmp}" "${CRED_FILE}"; then
        rm -f -- "${credential_tmp}"
        die "cannot atomically save credentials; existing file preserved"
    fi
    rm -f -- "${credential_tmp}"
}

# --------------------------------------------------------------------------
# Stage 6: framework first-boot initialization + passwords
# --------------------------------------------------------------------------
bootstrap_query_count() {
    local count
    count=$(printf '%s\n' "$1" | mysql_any -N -B 2>>"$LOG") || return 1
    [[ "${count}" =~ ^[0-9]{1,9}$ ]] || return 1
    printf '%s' "${count}"
}

framework_service_config() {
    local mode="$1" root="${2:-/}" account group uid primary_gid gid
    local file="${root%/}/etc/issabel.conf"
    if [ ! -e "${file}" ] && [ ! -L "${file}" ]; then
        [ "${mode}" = digest ] || return 1
        printf absent; return 0
    fi
    account=$(getent passwd asterisk) || return 1
    [[ "${account}" =~ ^asterisk:[^:]*:([0-9]{1,9}):([0-9]{1,9}):[^:]*:/var/lib/asterisk:/bin/bash$ ]] || return 1
    uid="${BASH_REMATCH[1]}"; primary_gid="${BASH_REMATCH[2]}"
    group=$(getent group asterisk) || return 1
    [[ "${group}" =~ ^asterisk:[^:]*:([0-9]{1,9}):[^:]*$ ]] || return 1
    gid="${BASH_REMATCH[1]}"
    [ "${gid}" = "${primary_gid}" ] || return 1
    EXPECTED_MYSQL_PASSWORD="${MYSQL_ROOT_PASS}" "${PY_BIN}" -B - "${file}" "${mode}" "${uid}" "${gid}" <<'PY'
import base64, binascii, hashlib, os, re, stat, sys
try:
    path, mode = sys.argv[1:3]
    if mode not in ('digest', 'ami', 'initialized-digest'): raise ValueError('mode')
    meta = os.lstat(path)
    if not stat.S_ISREG(meta.st_mode) or os.path.realpath(path) != os.path.abspath(path) or meta.st_size > 16384:
        raise ValueError('file')
    if os.name == 'posix' and (stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_uid != int(sys.argv[3]) or meta.st_gid != int(sys.argv[4])):
        raise ValueError('metadata')
    with open(path, 'rb') as source: raw = source.read(16385)
    if not raw.endswith(b'\n') or b'\r' in raw: raise ValueError('format')
    values = {}
    for line in raw.splitlines():
        key, separator, value = line.partition(b'=')
        if not separator or key in values: raise ValueError('keys')
        values[key] = value
    expected = {b'amiadminpwd', b'pbxapijwtsecret'}
    if mode == 'initialized-digest': expected.update((b'mysqlrootpwd', b'cyrususerpwd'))
    if set(values) != expected: raise ValueError('keys')
    ami, jwt = values[b'amiadminpwd'], values[b'pbxapijwtsecret']
    if not re.fullmatch(rb'[A-Za-z0-9 .@=_!\-]{10}', ami) or not ami.strip(): raise ValueError('ami')
    decoded = base64.b64decode(jwt, validate=True)
    if len(jwt) != 44 or len(decoded) != 32 or base64.b64encode(decoded) != jwt: raise ValueError('jwt')
    if mode == 'initialized-digest':
        chosen = os.environ['EXPECTED_MYSQL_PASSWORD'].encode('utf-8')
        if values[b'mysqlrootpwd'] != chosen or values[b'cyrususerpwd'] != chosen: raise ValueError('passwords')
    if mode == 'ami': sys.stdout.write(ami.decode('ascii'))
    else: sys.stdout.write(hashlib.sha256(ami).hexdigest() + ':' + hashlib.sha256(jwt).hexdigest())
except (OSError, ValueError, KeyError, binascii.Error):
    raise SystemExit(1)
PY
}

initialize_preserving_framework_keys() {
    local root="${1:-/}" expected="${2:-}" before after web_password="${ADMIN_PASS}"
    before=$(framework_service_config digest "${root}") || die "unrecognized service-key configuration retained"
    [ -z "${expected}" ] || [ "${before}" = "${expected}" ] || die "service keys changed during bootstrap; configuration retained"
    if [ "${before}" != absent ]; then
        # The native web step also sets AMI credentials. Give it the existing
        # AMI value, then set the independently chosen panel password below.
        web_password=$(framework_service_config ami "${root}") || die "cannot validate existing AMI credentials"
    fi
    run_logged /usr/bin/issabel-admin-passwords --ensure-jwt-secret || die "jwt secret init failed"
    initialize_framework_passwords "${web_password}"
    if [ "${before}" != absent ]; then
        after=$(framework_service_config initialized-digest "${root}") || die "initialized service-key configuration is invalid; values retained"
        [ "${before}" = "${after}" ] || die "AMI/JWT preservation check failed; no automatic restoration attempted"
        log 'Existing AMI/JWT keys verified unchanged'
    fi
}

guard_empty_framework_bootstrap() {
    local root="${1:-/}" path count
    root="${root%/}"
    # An installer receipt is never evidence that an existing PBX is empty.
    # Refuse unknown/partial files, including broken symlinks, without removal.
    for path in etc/amportal.conf etc/issabelpbx.conf; do
        [ ! -e "${root}/${path}" ] && [ ! -L "${root}/${path}" ] \
            || die "existing framework configuration retained; use scoped repair instead of reinitialization"
    done
    framework_service_config digest "${root}/" >/dev/null \
        || die "unrecognized initial service-key configuration retained; bootstrap refused"
    count=$(bootstrap_query_count "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME NOT IN ('mysql','information_schema','performance_schema','sys','asterisk','asteriskcdrdb');") \
        || die "cannot inventory database schemas; bootstrap refused without changes"
    [ "${count}" = "0" ] || die "unexpected database schema retained; bootstrap refused"
    count=$(bootstrap_query_count "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA IN ('asterisk','asteriskcdrdb');") \
        || die "cannot inventory framework objects; bootstrap refused without changes"
    [ "${count}" = "0" ] || die "existing framework/CDR objects retained; use scoped repair instead of reinitialization"
}

framework_bootstrap_healthy() {
    local root="${1:-/}" modules_present users_present mod_count
    modules_present=$(bootstrap_query_count "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='asterisk' AND TABLE_NAME='modules';") \
        || die "cannot inspect framework module metadata; partial data retained"
    users_present=$(bootstrap_query_count "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='asterisk' AND TABLE_NAME='ampusers';") \
        || die "cannot inspect framework account metadata; partial data retained"
    [ "${modules_present}" = "1" ] && [ "${users_present}" = "1" ] || return 1
    mod_count=$(bootstrap_query_count 'SELECT COUNT(*) FROM asterisk.modules;') \
        || die "cannot read framework modules; partial data retained"
    [ "${mod_count}" -gt 5 ] && [ -f "${root%/}/etc/amportal.conf" ]
}

fresh_pjsip_websocket() {
    local phase="${1:-}"
    case "${phase}" in prepare|activate) ;; *) die "invalid fresh WebSocket phase" ;; esac
    [ -f "${BUNDLE_DIR}/installer/prepare-pjsip-websocket.py" ] \
        && [ -f "${BUNDLE_DIR}/installer/pjsip-websocket-native.php" ] \
        || die "fresh PJSIP WebSocket bootstrap missing from bundle"
    run_logged "${PY_BIN}" -B "${BUNDLE_DIR}/installer/prepare-pjsip-websocket.py" "${phase}" \
        --state-dir "${STATE_DIR}" --version "${MYTELLPBX_VERSION}" \
        --bundle-sha256 "${MYTELLPBX_BUNDLE_SHA256}" \
        || die "fresh PJSIP WebSocket ${phase} failed; native settings retained"
}

bootstrap_empty_framework() {
    local root="${1:-/}" attempt installer_ok
    guard_empty_framework_bootstrap "${root}"
    normalize_framework_mysql
    # Only this boot marker is disposable. No database or framework config is
    # dropped/removed, even when an initializer fails or a query is unavailable.
    rm -f "${root%/}/installamp" || die "cannot clear fresh bootstrap marker"
    for attempt in 1 2 3; do
        guard_empty_framework_bootstrap "${root}"
        installer_ok=0
        run_logged /usr/src/issabelPBX/framework/install_amp --dbuser=root --installdb --scripted --language="${LANG_SEL}" && installer_ok=1
        if framework_bootstrap_healthy "${root}"; then
            [ "${installer_ok}" = "1" ] || die "initializer reported failure; generated data retained for scoped repair"
            fresh_pjsip_websocket prepare
            run_logged /var/lib/asterisk/bin/retrieve_conf || die "retrieve_conf failed; generated data retained"
            fresh_pjsip_websocket activate
            return 0
        fi
        # Retry only if successful metadata proves that this invocation has
        # created no objects/configuration. Any partial progress is preserved.
        guard_empty_framework_bootstrap "${root}"
        if [ "${attempt}" -lt 3 ]; then
            warn "راه‌اندازی چارچوب پیشرفتی نداشت؛ تلاش ${attempt}/3"
            sleep 2
        fi
    done
    die "framework bootstrap made no progress after 3 attempts; no databases were dropped"
}

ensure_admin_credentials() {
    # Admin console (FreePBX ampusers, sha1) + panel login (acl.db acl_user,
    # md5 + administrator membership). Idempotent: safe on every run.
    ensure_amp_admin_password
    ADMIN_PASS="${ADMIN_PASS}" php <<'PHP' >>"$LOG" 2>&1 || die "cannot ensure acl admin user"
<?php
$md5 = md5(getenv('ADMIN_PASS'));
$db = new PDO('sqlite:/var/www/db/acl.db');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$uid = $db->query("SELECT id FROM acl_user WHERE name='admin'")->fetchColumn();
if ($uid) {
    $db->prepare("UPDATE acl_user SET md5_password=? WHERE id=?")->execute(array($md5, $uid));
} else {
    $db->prepare("INSERT INTO acl_user (name, description, md5_password, extension) VALUES ('admin','',?,'')")->execute(array($md5));
    $uid = $db->lastInsertId();
}
$has = $db->query("SELECT COUNT(*) FROM acl_membership WHERE id_user=" . (int)$uid . " AND id_group=1")->fetchColumn();
if (!$has) {
    $db->exec("INSERT INTO acl_membership (id_user, id_group) VALUES (" . (int)$uid . ", 1)");
}
echo "acl admin ensured (uid=$uid)\n";
PHP
}
stage_framework_init() {
    stage_done framework && return 0
    step "راه‌اندازی چارچوب مرکز تماس و رمزها"

    ensure_credentials
    local service_digest
    service_digest=$(framework_service_config digest) || die "unrecognized initial service-key configuration retained"
    guard_empty_framework_bootstrap

    # The supported RPM owns one native systemd unit. Starting a manual
    # safe_asterisk helper as well can create competing unmanaged processes.
    ( exec 9>&-; systemctl start asterisk >>"$LOG" 2>&1 ) || die "native asterisk unit failed to start"
    systemctl is-active --quiet asterisk || die "native asterisk unit is not active"
    asterisk -rx 'core show version' >>"$LOG" 2>&1 || die "asterisk CLI failed before framework init"
    systemctl enable asterisk >>"$LOG" 2>&1 || die "cannot enable asterisk at boot"

    bootstrap_empty_framework

    # Non-interactive password initialization (sets MariaDB/Cyrus root,
    # panel admin password, applies pending DB scripts, saves /etc/issabel.conf).
    # The upstream tool can print internal errors yet exit 0 — verify outcomes.
    initialize_preserving_framework_keys / "${service_digest}"
    verify_mysql_root_password \
        || die "password init did not persist mysqlrootpwd (upstream tool misreported success)"
    verify_mysql_authentication

    # The upstream --cli init skips its whole web-password step when its key
    # file already exists ("Password configuration already present"), which
    # leaves the panel (acl_user, md5) and admin console (ampusers, sha1)
    # credentials unset. Idempotently enforce the credential-file password
    # on BOTH auth stores, then verify for real.
    ensure_admin_credentials

    # hard verification: the admin password must actually be in force
    verify_amp_admin_password
    ADMIN_PASS="${ADMIN_PASS}" php <<'PHP' >>"$LOG" 2>&1 || die "acl admin verify failed"
<?php
$md5 = md5(getenv('ADMIN_PASS'));
$db = new PDO('sqlite:/var/www/db/acl.db');
$got = $db->query("SELECT md5_password FROM acl_user WHERE name='admin'")->fetchColumn();
if ($got !== $md5) { fwrite(STDERR, "acl_user md5 mismatch\n"); exit(1); }
echo "acl admin password verified\n";
PHP

    # FOP2 manager user (upstream --init step; needs manager config)
    if [ -x /usr/local/fop2/create_fop2_manager_user.pl ] && [ -f /etc/asterisk/manager.conf ]; then
        run_logged /usr/local/fop2/create_fop2_manager_user.pl || true
    fi

    mark_stage framework
}

# --------------------------------------------------------------------------
# Stage 7: MyTel layer
# --------------------------------------------------------------------------
set_amportal_key() {
    local key="$1" val="$2" file="/etc/amportal.conf"
    [ -f "${file}" ] || die "${file} missing"
    if grep -q "^${key}=" "${file}"; then
        sed -i "s|^${key}=.*|${key}=${val}|" "${file}"
    else
        echo "${key}=${val}" >> "${file}"
    fi
}

# Brand keys must ALSO live in asterisk.issabelpbx_settings: the boot
# service amportal-reload (`amportal a r`) regenerates /etc/amportal.conf
# from that table, wiping conf-only edits at every boot. Rows must keep
# their metadata columns (name/level/description/type/defaultval) — a
# value-only REPLACE breaks the settings class with "unknown type".
set_brand_db_keys() {
    BRAND_KEYS='BRAND_ALT_JS=assets/mytel/sub.js?v=24
BRAND_CSS_CUSTOM=assets/mytel/skin.css?v=27
BRAND_CSS_CUSTOM=assets/mytel/skin.css?v=27
BRAND_TITLE=MyTell PBX
BRAND_ISSABELPBX_ALT_FOOT=MyTel
BRAND_ISSABELPBX_ALT_LEFT=MyTel
BRAND_IMAGE_FAVICON=images/mytel-favicon.png
BRAND_IMAGE_ISSABELPBX_FOOT=images/mytel-foot.png
BRAND_IMAGE_TANGO_LEFT=images/mytel-emblem-48.png
BRAND_IMAGE_ISSABELPBX_LINK_FOOT=https://mytel.one
BRAND_IMAGE_ISSABELPBX_LINK_LEFT=https://mytel.one' \
    BRAND_DB_PASS="${MYSQL_ROOT_PASS}" \
    php <<'PHP' >>"$LOG" 2>&1 || die "cannot persist brand keys in framework settings"
<?php
$keys = array();
foreach (explode("\n", getenv('BRAND_KEYS')) as $line) {
    $line = trim($line);
    if ($line === '' || strpos($line, '=') === false) continue;
    list($k, $v) = explode('=', $line, 2);
    $keys[$k] = $v;
}
/* framework metadata for the brand keys (name, level, description, type,
   defaultval) — mirrors the framework's own settings definitions */
$meta = array(
    'BRAND_ALT_JS' => array('Alternate JS', 'Alternate JS file, to supplement legacy.script.js'),
    'BRAND_CSS_CUSTOM' => array('Optional Additional CSS Stylesheet', 'Optional custom CSS style sheet included after the primary one and any module specific ones are loaded, relative to admin.'),
    'BRAND_TITLE' => array('Page Title', 'HTML title of all pages'),
    'BRAND_ISSABELPBX_ALT_FOOT' => array('Alt for Footer Logo', 'alt attribute to use in place of image and title hover value.'),
    'BRAND_ISSABELPBX_ALT_LEFT' => array('Alt for Left Logo', 'alt attribute to use in place of image and title hover value.'),
    'BRAND_IMAGE_FAVICON' => array('Favicon', 'Favicon'),
    'BRAND_IMAGE_ISSABELPBX_FOOT' => array('Image: Footer', 'Logo in footer. Path is relative to admin.'),
    'BRAND_IMAGE_TANGO_LEFT' => array('Image: Left Upper', 'Left upper logo. Path is relative to admin.'),
    'BRAND_IMAGE_ISSABELPBX_LINK_FOOT' => array('Link for Footer Logo', 'link to follow when clicking on logo'),
    'BRAND_IMAGE_ISSABELPBX_LINK_LEFT' => array('Link for Left Logo', 'link to follow when clicking on logo'),
);
$my = null;
try {
    $my = new PDO('mysql:host=localhost;dbname=asterisk', 'root', '');
    $my->query('SELECT 1');
} catch (Exception $e) {
    // password was set by the password-init step on this run
    $my = new PDO('mysql:host=localhost;dbname=asterisk', 'root', getenv('BRAND_DB_PASS'));
}
$my->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$chk = $my->prepare('SELECT COUNT(*) FROM issabelpbx_settings WHERE keyword = :k');
$upd = $my->prepare('UPDATE issabelpbx_settings SET value = :v WHERE keyword = :k');
$ins = $my->prepare('INSERT INTO issabelpbx_settings (keyword, value, name, level, description, type, options, defaultval) '
    . 'VALUES (:k, :v, :n, 1, :d, :t, :o, :dv)');
foreach ($keys as $k => $v) {
    // existence check, NOT rowCount: an UPDATE that matches but does not
    // change the value reports 0 changed rows and must not trigger INSERT
    $chk->execute(array(':k' => $k));
    if ((int)$chk->fetchColumn() > 0) {
        $upd->execute(array(':v' => $v, ':k' => $k));
    } else {
        $m = isset($meta[$k]) ? $meta[$k] : array($k, '');
        $ins->execute(array(':k' => $k, ':v' => $v, ':n' => $m[0], ':d' => $m[1],
            ':t' => 'text', ':o' => '', ':dv' => ''));
    }
}
$bad = $my->query("SELECT COUNT(*) FROM issabelpbx_settings WHERE keyword LIKE 'BRAND%' AND (type IS NULL OR type = '')")->fetchColumn();
if ($bad) { fwrite(STDERR, "brand rows missing type metadata: $bad\n"); exit(1); }
echo 'brand keys persisted: ' . count($keys) . "\n";
PHP
}

repair_optional_asternic_direction() {
    local module="${WEB_ROOT}/admin/modules/asternic_cdr"
    if [ ! -e "${module}" ] && [ ! -L "${module}" ]; then
        log "OPTIONAL ASTERNIC ABSENT: no report module installed or changed"
        return 0
    fi
    [ -f "${BUNDLE_DIR}/admin-fixes/patch-asternic-direction.py" ] || die "Asternic direction repair missing from bundle"
    "${PY_BIN}" -B "${BUNDLE_DIR}/admin-fixes/patch-asternic-direction.py" --module-root "${module}" >>"$LOG" 2>&1 \
        || die "optional Asternic direction repair failed; unsupported or changed source requires review"
}

stage_mytel_layer() {
    stage_done "mytel_layer-${MYTELLPBX_VERSION}" && return 0
    step "نصب قالب و برندسازی مای‌تل"

    # credentials must be in scope on resumed runs too (framework stage skipped)
    ensure_credentials

    # 1) Panel theme (copy + module extras + ownership)
    [ -d "${BUNDLE_DIR}/theme" ] || die "theme missing from bundle"
    mkdir -p "${THEME_DST}"
    cp -a "${BUNDLE_DIR}/theme/." "${THEME_DST}/"
    chown -R asterisk:asterisk "${THEME_DST}"
    find "${THEME_DST}" -type d -exec chmod 755 {} + 2>/dev/null
    find "${THEME_DST}" -type f -exec chmod 644 {} + 2>/dev/null
    if [ -d "${THEME_DST}/extras" ]; then
        ( cd "${THEME_DST}/extras" && find . -type f | while read -r rel; do
            rel="${rel#./}"
            target="${WEB_ROOT}/modules/${rel}"
            if [ ! -f "${target}" ] && [ -d "$(dirname "${target}")" ]; then
                cp "${rel}" "${target}"
                chown asterisk:asterisk "${target}"
                chmod 644 "${target}"
            fi
          done )
    fi

    # 2) Persian language pack (golden fa.lang; stock file kept as backup)
    if [ -f "${BUNDLE_DIR}/installer/payload/lang/fa.lang" ]; then
        if [ -f "${FA_LANG}" ] && [ ! -f "${FA_LANG}.orig-mt" ]; then
            cp -a "${FA_LANG}" "${FA_LANG}.orig-mt"
        fi
        cp -f "${BUNDLE_DIR}/installer/payload/lang/fa.lang" "${FA_LANG}"
        chown asterisk:asterisk "${FA_LANG}" 2>/dev/null || true
    fi

    # 3) Panel settings: theme=mytel + language=fa (transactional + verified)
    php <<'PHP' >>"$LOG" 2>&1 || die "settings activation failed"
<?php
$db = new PDO('sqlite:/var/www/db/settings.db');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$db->beginTransaction();
foreach (array('theme'=>'mytel','language'=>'fa') as $k=>$v) {
    $db->prepare("DELETE FROM settings WHERE key = ?")->execute(array($k));
    $db->prepare("INSERT INTO settings (key, value) VALUES (?, ?)")->execute(array($k, $v));
}
$db->commit();
foreach (array('theme'=>'mytel','language'=>'fa') as $k=>$want) {
    $got = $db->query("SELECT value FROM settings WHERE key = '$k'")->fetchColumn();
    if ($got !== $want) { fwrite(STDERR, "verify failed: $k=$got\n"); exit(1); }
}
echo "settings OK: theme=mytel language=fa\n";
PHP

    # 4) Admin console assets (base skin/sub.js + fonts) and brand images
    [ -d "${BUNDLE_DIR}/installer/payload/admin/assets/mytel" ] || die "admin assets missing from bundle"
    mkdir -p "${ADMIN_ASSETS}"
    cp -a "${BUNDLE_DIR}/installer/payload/admin/assets/mytel/." "${ADMIN_ASSETS}/"
    if [ -d "${THEME_DST}/images/admin" ]; then
        mkdir -p "${WEB_ROOT}/admin/images"
        cp -a "${THEME_DST}/images/admin/." "${WEB_ROOT}/admin/images/"
    fi
    chown -R asterisk:asterisk "${ADMIN_ASSETS}" "${WEB_ROOT}/admin/images"

    # 5) Admin console brand keys (stock mechanism): conf for immediate
    #    effect + framework settings table so boot-time amportal reloads
    #    regenerate the conf WITH our values
    set_amportal_key BRAND_CSS_CUSTOM "assets/mytel/skin.css?v=27"
    set_amportal_key BRAND_ALT_JS "assets/mytel/sub.js?v=24"
    set_amportal_key BRAND_TITLE "MyTell PBX"
    set_amportal_key BRAND_ISSABELPBX_ALT_FOOT "MyTel"
    set_amportal_key BRAND_ISSABELPBX_ALT_LEFT "MyTel"
    set_amportal_key BRAND_IMAGE_FAVICON "images/mytel-favicon.png"
    set_amportal_key BRAND_IMAGE_ISSABELPBX_FOOT "images/mytel-foot.png"
    set_amportal_key BRAND_IMAGE_TANGO_LEFT "images/mytel-emblem-48.png"
    set_amportal_key BRAND_IMAGE_ISSABELPBX_LINK_FOOT "https://mytel.one"
    set_amportal_key BRAND_IMAGE_ISSABELPBX_LINK_LEFT "https://mytel.one"
    set_brand_db_keys

    # 6) Admin theme patchers (preserve owner edits, private scoped backups)
    "${PY_BIN}" "${BUNDLE_DIR}/admin-theme/patch-admin-theme.py" >>"$LOG" 2>&1 \
        || die "admin theme patcher failed"
    php -l "${WEB_ROOT}/admin/views/header.php" >>"$LOG" 2>&1 \
        || die "header.php syntax broken after patch"
    "${PY_BIN}" "${BUNDLE_DIR}/admin-theme/patch-debrand.py" >>"$LOG" 2>&1 \
        || die "debrand patcher failed"
    php -l "${WEB_ROOT}/admin/views/footer_content.php" >>"$LOG" 2>&1 \
        || die "footer_content.php syntax broken after patch"

    # 7) Apply Config fix (dashboard ajax timeout)
    if [ -f "${BUNDLE_DIR}/admin-fixes/fix-apply-config.py" ]; then
        "${PY_BIN}" "${BUNDLE_DIR}/admin-fixes/fix-apply-config.py" >>"$LOG" 2>&1 \
            || die "apply-config fix failed"
    fi
    if [ -f "${BUNDLE_DIR}/admin-fixes/install-scoped-repairs.py" ]; then
        "${PY_BIN}" "${BUNDLE_DIR}/admin-fixes/install-scoped-repairs.py" --web-root "${WEB_ROOT}" >>"$LOG" 2>&1 \
            || die "scoped Apply/calendar repair failed"
    fi
    # Optional installed Asternic1.6.6 only; never installs/vendor-copies a module.
    repair_optional_asternic_direction

    # Update presentation only; the vendor login script must never be executed
    # here because it also contains service and network first-boot actions.
    "${PY_BIN}" -B "${BUNDLE_DIR}/admin-theme/patch-login-branding.py" >>"$LOG" 2>&1 \
        || die "login branding source changed; review before continuing"

    # 8) Clear known caches + ownership + validate Apache config
    find "${WEB_ROOT}" -name '*.tplc' -delete 2>/dev/null || true
    rm -rf "${WEB_ROOT}/themes/mytel/cache" 2>/dev/null || true
    /usr/sbin/amportal chown >>"$LOG" 2>&1 || true
    httpd -t >>"$LOG" 2>&1 || die "apache configuration invalid after patching"
    systemctl enable httpd >>"$LOG" 2>&1 || true
    systemctl restart httpd >>"$LOG" 2>&1 || die "httpd restart failed"

    mark_stage "mytel_layer-${MYTELLPBX_VERSION}"
}

# The separate product owns its runtime, database, accounts and reversible
# service activation. Do not run old /opt/opdesk patchers over its release.
stage_geoip() {
    step "نصب و اعتبارسنجی خودکار پایگاه دادهٔ کشورها (بدون نیاز به کلید)"
    [ -f "${BUNDLE_DIR}/installer/geoip-update.py" ] || die "GeoIP updater missing from bundle"
    [ -f "${BUNDLE_DIR}/installer/prepare-geoip-module.py" ] || die "GeoIP kernel preparation missing from bundle"
    if ! stage_done geoip; then
        "${PY_BIN}" -B "${BUNDLE_DIR}/installer/geoip-update.py" --install \
            --status-module "${BUNDLE_DIR}/modules/mytellpbxgeoip/index.php" 2>&1 | tee -a "${LOG}" \
            || die "country database verification failed; review the reported stage"
    fi
    # Revalidate the current boot even when the dataset stage was completed.
    # This loads only the verified module; it never rewrites firewall rules.
    run_logged "${PY_BIN}" -B "${BUNDLE_DIR}/installer/prepare-geoip-module.py" \
        || die "GeoIP kernel consumer verification failed; firewall rules retained"
    mark_stage geoip
}

stage_webrtc_dtls() {
    # The native WebRTC forms use this independent Asterisk PEM. Apache TLS
    # readiness alone cannot prove DTLS media works. Revalidate on every resume.
    [ -f "${BUNDLE_DIR}/installer/prepare-webrtc-dtls.py" ] || die "WebRTC DTLS preparation missing from bundle"
    run_logged "${PY_BIN}" -B "${BUNDLE_DIR}/installer/prepare-webrtc-dtls.py" \
        --backup-root "${STATE_DIR}/webrtc-dtls" \
        || die "WebRTC DTLS certificate is not ready; existing material retained"
    mark_stage webrtc-dtls
}

stage_myteldesk() {
    step "نصب و بررسی میز کار اپراتور و تحلیل گفتار خودکار"
    [ -f "${BUNDLE_DIR}/installer/install-myteldesk.py" ] || die "pinned Desk installer missing from bundle"
    local args=(--cache-root "${STATE_DIR}/cache/myteldesk" --launcher-source "${BUNDLE_DIR}/modules/mytellpbxopdesk" --web-root "${WEB_ROOT}")
    [ -z "${MYTELL_DESK_PUBLIC_URL:-}" ] || args+=(--public-url "${MYTELL_DESK_PUBLIC_URL}")
    # Keep real upstream stages visible. pipefail preserves a failed installer
    # exit instead of treating tee's successful log write as installation success.
    "${PY_BIN}" -B "${BUNDLE_DIR}/installer/install-myteldesk.py" "${args[@]}" 2>&1 | tee -a "${LOG}" \
        || die "MytelDesk/CPU VAD verification failed; existing data retained, review the reported stage"
    mark_stage myteldesk
}

# --------------------------------------------------------------------------
# Stage 8: self-checks
# --------------------------------------------------------------------------
stage_selfcheck() {
    step "راستی‌آزمایی نهایی نصب"

    # framework completeness: modules registered + generated device configs.
    # A half-finished install_amp (DB briefly unreachable) reports success —
    # catch it here and clear the framework marker so a re-run repairs it.
    ensure_credentials
    local mod_count=""
    mod_count=$(bootstrap_query_count 'SELECT COUNT(*) FROM asterisk.modules;') \
        || die "self-check: cannot read framework modules; existing stage marker retained"
    if ! { [ -n "${mod_count}" ] && [ "${mod_count}" -gt 5 ]; } || [ ! -f /etc/asterisk/pjsip_additional.conf ]; then
        rm -f "${STATE_DIR}/stages/framework.done"
        die "framework incomplete (modules=${mod_count:-0}); run the installer again to repair"
    fi

    run_logged "${PY_BIN}" -B "${BUNDLE_DIR}/installer/prepare-webrtc-dtls.py" --check \
        || die "self-check: WebRTC DTLS certificate is not valid"
    systemctl is-active --quiet mariadb || die "self-check: mariadb not active"
    systemctl is-active --quiet httpd   || die "self-check: httpd not active"
    /usr/local/sbin/myteldesk doctor || die "self-check: MytelDesk or CPU voice analysis not ready"
    sleep 8
    verify_asterisk_service
    verify_mysql_authentication

    local body
    body=$(curl -fsSkL --max-time 30 "http://127.0.0.1/" 2>>"$LOG" || true)
    [ -n "${body}" ] || die "self-check: login page empty"
    printf '%s' "${body}" | grep -qE 'login|ورود|mytel' \
        || die "self-check: login page does not look like MyTellPBX"
    if printf '%s' "${body}" | grep -qi 'issabel'; then
        warn "self-check: login page still mentions upstream brand (check manually)"
    fi

    local theme_val
    theme_val=$(php -r '$db=new PDO("sqlite:/var/www/db/settings.db"); echo $db->query("SELECT value FROM settings WHERE key = '"'"'theme'"'"'")->fetchColumn();' 2>>"$LOG" || true)
    [ "${theme_val}" = "mytel" ] || die "self-check: active theme is '${theme_val}', expected mytel"

    [ "$(stat -c '%a' "${CRED_FILE}" 2>/dev/null)" = "600" ] \
        || die "self-check: credentials file permissions wrong"

    mark_stage selfcheck
}

finish() {
    local ip
    ip=$(hostname -I | awk '{print $1}')
    echo
    echo "=============================================================="
    echo "   نصب MyTellPBX با موفقیت کامل شد"
    echo "=============================================================="
    echo "   نشانی پنل:      https://${ip}/"
    echo "   نام کاربری:     admin"
    echo "   میز کار:        https://${ip}/MytellDesk/ (ورود با حساب پنل)"
    echo "   مدیر محلی میز کار: /etc/myteldesk/initial-admin.txt (فقط root)"
    echo "   رمز‌ها:          ${CRED_FILE} (فقط root)"
    echo "   مستندات:        github.com/DashSaman/MyTellPBX"
    echo "   پشتیبانی:       mytel.one"
    echo "=============================================================="
    echo
    if [ "${REBOOT_AFTER}" = "1" ]; then
        say "راه‌اندازی مجدد در ۵ ثانیه..."
        sync
        sleep 5
        systemctl reboot
    else
        say "برای بارگذاری کامل سرویس‌ها یک بار راه‌اندازی مجدد توصیه می‌شود."
    fi
}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
main() {
    mkdir -p "$(dirname "${LOG}")"

    echo "MyTellPBX ${MYTELLPBX_VERSION} installer — $(date)" | tee -a "${LOG}"

    # preflight FIRST: the fresh-system guard checks STATE_DIR absence, so
    # the state directory must not exist yet when preflight runs
    preflight
    mkdir -p "${STATE_DIR}"
    chmod 700 "${STATE_DIR}"
    acquire_lock
    write_install_source
    initialize_workspace

    # Truncate only AFTER the lock is ours (a refused run must not clobber
    # the active run's log).
    : >"${LOG}"
    chmod 600 "${LOG}"
    echo "MyTellPBX ${MYTELLPBX_VERSION} installer — $(date)" >>"${LOG}"

    verify_bundle
    ensure_credentials
    # Only the collector consumes inherited stdin. Later vendor commands get
    # EOF; explicit SQL/PHP pipes and heredocs keep their own input streams.
    exec </dev/null || die "cannot close inherited installer input"

    # Revalidate before stage shortcuts: RPMs can recreate their repository
    # files during an earlier interrupted package transaction.
    repair_platform_catalog
    stage_repos
    stage_update
    stage_packages1
    stage_tls
    stage_packages2
    repair_platform_catalog mandatory
    stage_cli_status
    stage_post_base
    stage_framework_init
    stage_mytel_layer
    stage_webrtc_dtls
    stage_geoip
    stage_myteldesk
    stage_selfcheck
    finish
}

main "$@"
