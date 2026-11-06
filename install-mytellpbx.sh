#!/bin/bash
# ==========================================================================
# MyTellPBX one-line installer for Rocky Linux 8.10 (x86_64)
# Version: 7.4.0
#
# Installs the complete MyTellPBX contact-center platform:
#   - telephony base (Asterisk 20, MariaDB, Apache, PHP 7.4, framework)
#   - the MyTellPBX Persian RTL theme for the panel and admin console
#   - full MyTel branding, dark/light themes, Persian language
#
# Quick start (download, review, run — never pipe straight into bash):
#   curl -fsSL -o install-mytellpbx.sh \
#     https://github.com/DashSaman/MyTellPBX/releases/download/v7.4.0/install-mytellpbx.sh
#   bash install-mytellpbx.sh
#
# Environment overrides (all optional):
#   MYTELL_ASTVER          Asterisk major version; only "20" is supported.
#   MYTELL_LANG            Panel language; only "fa" is supported.
#   MYTELL_REBOOT          1 = reboot automatically after success (default 0).
#   MYTELL_MYSQL_ROOT_PASS Predefined MariaDB root password (allowed chars:
#                          A-Z a-z 0-9 space . @ = _ ! - ; generated if unset).
#   MYTELL_ADMIN_PASS      Predefined panel admin password (same rules).
#   MYTELL_SKIP_UPDATE     1 = skip the initial OS update step.
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

MYTELLPBX_VERSION="7.5.0"
MYTELLPBX_BUNDLE="mytelpbx-bundle-7.5.0.tgz"
# Expected SHA-256 of the bundle asset (filled in by the release builder).
MYTELLPBX_BUNDLE_SHA256="1c6d81c591f1a66774ca3ecbc0ec84d6aa1bb36b61ee9bfdc41a96590bf84193"
MYTELLPBX_GITHUB="https://github.com/DashSaman/MyTellPBX"
MYTELLPBX_RELEASE_TAG="v7.5.0"
MYTELLPBX_BUNDLE_URL="${MYTELL_BUNDLE_URL:-${MYTELLPBX_GITHUB}/releases/download/${MYTELLPBX_RELEASE_TAG}/${MYTELLPBX_BUNDLE}}"

LOG="/var/log/mytelpbx-install.log"
STATE_DIR="/var/lib/mytelpbx-installer"
LOCK_FILE="/var/run/mytelpbx-install.lock"
CRED_FILE="/root/mytelpbx-credentials.txt"
BUNDLE_TMP="/tmp/${MYTELLPBX_BUNDLE}.part"
BUNDLE_FINAL="/tmp/${MYTELLPBX_BUNDLE}"
BUNDLE_ROOT="/tmp/mytelpbx-bundle"
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
mark_stage() { mkdir -p "${STATE_DIR}/stages"; touch "${STATE_DIR}/stages/$1.done"; log "STAGE-COMPLETE: $1"; }

run_logged() { "$@" >>"$LOG" 2>&1; }

# mysql helper: works whether root is passwordless or already passworded
# (credentials file is loaded before use; safe to call after ensure_credentials)
mysql_any() {
    if mysql -N -e "SELECT 1" >/dev/null 2>&1; then
        mysql "$@"
    else
        mysql -p"${MYSQL_ROOT_PASS:-}" "$@"
    fi
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

# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------
preflight() {
    step "بررسی پیش‌نیازها"

    [ "$(id -u)" -eq 0 ] || die "root required"

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
        local conflicting=0 p
        for p in issabel httpd mariadb-server asterisk20 elastix; do
            rpm --quiet -q "$p" && conflicting=1
        done
        [ "${conflicting}" = "0" ] || die "existing PBX packages detected; this installer targets a fresh Rocky 8.10 system"
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

    # Network: DNS + TLS to GitHub and exact bundle asset availability
    # (skipped when an internal local bundle file is provided)
    if [ -z "${MYTELL_BUNDLE_FILE:-}" ]; then
        curl -fsS --max-time 30 -o /dev/null "${MYTELLPBX_GITHUB}" \
            || die "cannot reach github.com (DNS/TLS)"
        local http_code
        http_code=$(curl -fsSL --max-time 60 -o /dev/null -w '%{http_code}' -r 0-0 \
            "${MYTELLPBX_BUNDLE_URL}" 2>>"$LOG" || echo 000)
        [ "${http_code}" = "206" ] || [ "${http_code}" = "200" ] \
            || die "release bundle not reachable (HTTP ${http_code}): ${MYTELLPBX_BUNDLE_URL}"
    fi

    # Telephony repo metadata + php module repository availability
    curl -fsS --max-time 30 -o /dev/null \
        "http://mirror.issabel.org/?release=5&arch=x86_64&repo=base" \
        || die "telephony base repository mirror unreachable"
    curl -fsSI --max-time 30 -o /dev/null \
        "https://rpms.remirepo.net/enterprise/remi-release-8.rpm" \
        || die "php module repository unreachable"

    say "پیش‌نیازها تأیید شد"
}

acquire_lock() {
    exec 9>"${LOCK_FILE}"
    flock -n 9 || die "another installer run holds ${LOCK_FILE}"
}

# --------------------------------------------------------------------------
# Bundle download + verification (before any system mutation)
# --------------------------------------------------------------------------
verify_bundle() {
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

    # Verify a random sample of shipped hashes (quick integrity re-check)
    ( cd "${BUNDLE_DIR}" && head -5 SHA256SUMS | sha256sum -c --quiet ) >>"$LOG" 2>&1 \
        || die "bundle internal checksums failed"
}

# --------------------------------------------------------------------------
# Stage 1: repositories + PHP module stream
# --------------------------------------------------------------------------
stage_repos() {
    stage_done repos && return 0
    step "پیکربندی مخازن بسته‌ها"

    local repo_src="${BUNDLE_DIR}/installer/repos/mytelpbx-base.repo.in"
    [ -f "${repo_src}" ] || die "repo template missing from bundle"
    cp -f "${repo_src}" /etc/yum.repos.d/mytelpbx-base.repo
    chmod 644 /etc/yum.repos.d/mytelpbx-base.repo

    grep -qxF 'fastestmirror=True' /etc/dnf/dnf.conf 2>/dev/null || echo 'fastestmirror=True' >> /etc/dnf/dnf.conf

    # Remi repo + explicit PHP stream selection
    run_logged dnf install -y dnf-plugins-core || die "dnf-plugins-core install failed"
    run_logged dnf install -y https://rpms.remirepo.net/enterprise/remi-release-8.rpm \
        || die "remi-release install failed"
    run_logged dnf module reset -y php || true
    run_logged dnf module enable -y php:remi-7.4 || die "php:remi-7.4 module enable failed"
    run_logged dnf config-manager --set-enabled remi || true
    run_logged dnf config-manager --set-enabled powertools || true
    run_logged dnf config-manager --set-enabled devel || true

    run_logged dnf -q makecache || die "dnf makecache failed"
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
        if run_logged dnf -y update; then ok=1; break; fi
        warn "به‌روزرسانی ناموفق (تلاش ${attempt}/3) — میرور جایگزین آزمایش می‌شود"
        sleep 5
    done
    [ "${ok}" = "1" ] || die "OS update failed after retries (see ${LOG})"
    mark_stage update
}

install_pkg() {
    dnf -y install "$@" >>"$LOG" 2>&1
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

stage_packages1() {
    stage_done packages1 && return 0
    step "نصب بسته‌های پایه (Asterisk 20 / MariaDB / Apache / PHP)"
    local list="${BUNDLE_DIR}/installer/packages/rocky8-stage1.txt"
    [ -f "${list}" ] || die "stage-1 package list missing from bundle"
    local pkgs
    pkgs=$(tr '\n' ' ' < "${list}")
    install_with_retry "stage-1 package install" ${pkgs}
    mark_stage packages1
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

    /usr/sbin/groupadd -f -r asterisk >/dev/null 2>&1 || true
    if ! grep -q 'asterisk:' /etc/passwd; then
        /usr/sbin/useradd -r -g asterisk -c "Asterisk PBX" -s /bin/bash -d /var/lib/asterisk asterisk >/dev/null 2>&1 || true
    fi

    systemctl enable mariadb.service >>"$LOG" 2>&1 || die "mariadb enable failed"
    systemctl start  mariadb           >>"$LOG" 2>&1 || die "mariadb start failed"
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

    # Normalize MariaDB root access for the framework initializer:
    # set a temporary random password, then clear it (upstream-tested flow,
    # with a random temp instead of a shipped constant).
    local tmp_pwd
    tmp_pwd=$(openssl rand -hex 12)
    mysql -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('${tmp_pwd}')" >>"$LOG" 2>&1 || true
    mysql -p"${tmp_pwd}" -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('')" >>"$LOG" 2>&1 \
        || die "mariadb root password normalization failed"

    # Framework marker: remove any stale config so the initializer writes fresh
    rm -f /etc/issabel.conf

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
ensure_credentials() {
    if [ -s "${CRED_FILE}" ]; then
        say "رمزهای موجود حفظ شد (اجرای مجدد)"
        # shellcheck disable=SC1090
        . "${CRED_FILE}"
        return 0
    fi
    # shellcheck disable=SC2154
    MYSQL_ROOT_PASS="${MYTELL_MYSQL_ROOT_PASS:-$(openssl rand -hex 24)}"
    ADMIN_PASS="${MYTELL_ADMIN_PASS:-$(openssl rand -hex 24)}"
    local orig_mysql="${MYSQL_ROOT_PASS}" orig_admin="${ADMIN_PASS}"
    (
        umask 077
        # single-quoted assignments: the allowed charset (alnum, space,
        # .@=_!-) never contains a single quote, so this is inject-safe
        cat > "${CRED_FILE}" <<EOF
# MyTellPBX credentials - $(date '+%Y-%m-%d %H:%M:%S')
# Keep this file secret (mode 0600, root only).
MYSQL_ROOT_PASS='${MYSQL_ROOT_PASS}'
ADMIN_PASS='${ADMIN_PASS}'
EOF
        chmod 600 "${CRED_FILE}"
    )
    # round-trip verification: sourcing must restore the exact originals
    unset MYSQL_ROOT_PASS ADMIN_PASS
    . "${CRED_FILE}"
    [ "${MYSQL_ROOT_PASS}" = "${orig_mysql}" ] && [ "${ADMIN_PASS}" = "${orig_admin}" ] \
        || die "credential file round-trip verification failed"
    [ -s "${CRED_FILE}" ] || die "credential file creation failed"
}

# --------------------------------------------------------------------------
# Stage 6: framework first-boot initialization + passwords
# --------------------------------------------------------------------------
ensure_admin_credentials() {
    # Admin console (FreePBX ampusers, sha1) + panel login (acl.db acl_user,
    # md5 + administrator membership). Idempotent: safe on every run.
    local my_args=()
    if ! mysql -N -e "SELECT 1" >/dev/null 2>&1; then
        my_args=(-p"${MYSQL_ROOT_PASS}")
    fi
    mysql "${my_args[@]}" -N -e "UPDATE asterisk.ampusers SET password_sha1=SHA1('${ADMIN_PASS}') WHERE username='admin';" >>"$LOG" 2>&1 \
        || die "cannot update ampusers admin password"
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

    # install_amp requires a running Asterisk (upstream start_asterisk helper).
    # Daemons must NOT inherit the installer lock fd — close it in subshells.
    if ! asterisk -rx 'core show version' >/dev/null 2>&1; then
        if [ -x /usr/src/issabelPBX/framework/start_asterisk ]; then
            ( exec 9>&-; run_logged /usr/src/issabelPBX/framework/start_asterisk start ) || true
        fi
        ( exec 9>&-; systemctl start asterisk >>"$LOG" 2>&1 ) || true
        sleep 3
        asterisk -rx 'core show version' >>"$LOG" 2>&1 \
            || die "asterisk failed to start for framework init"
    fi

    # Framework first-boot install. Run when flagged OR when the framework
    # is verifiably absent — a previously failed run removes the flag file
    # before install_amp succeeds, so the flag alone is not resume-safe.
    local need_install=0
    [ -f /installamp ] && need_install=1
    [ -f /etc/amportal.conf ] || need_install=1
    if ! mysql_any -N -e "SHOW TABLES FROM asterisk LIKE 'ampusers'" 2>/dev/null | grep -q ampusers; then
        need_install=1
    fi
    # a half-finished framework install (DB briefly down during install_amp)
    # can leave the modules table empty — that must re-run too
    local mod_count=0
    mod_count=$(mysql_any -N -e "SELECT COUNT(*) FROM asterisk.modules" 2>/dev/null | tr -d '[:space:]')
    [ -n "${mod_count}" ] && [ "${mod_count}" -gt 5 ] || need_install=1
    if [ "${need_install}" = "1" ]; then
        # install_amp's first-boot flow needs passwordless MariaDB root
        if ! mysql -N -e "SELECT 1" >/dev/null 2>&1; then
            mysql -p"${MYSQL_ROOT_PASS}" -N \
                -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('')" >>"$LOG" 2>&1 \
                || die "cannot normalize mariadb root access"
        fi
        rm -f /installamp
        run_logged /usr/src/issabelPBX/framework/install_amp \
            --dbuser=root --installdb --scripted --language="${LANG_SEL}" \
            || die "framework install_amp failed (see ${LOG})"
        [ -f /etc/amportal.conf ] || die "install_amp produced no /etc/amportal.conf"
        mysql_any -N -e "SHOW TABLES FROM asterisk LIKE 'ampusers'" 2>>"$LOG" | grep -q ampusers \
            || die "framework database missing ampusers after install_amp"
        mod_count=$(mysql_any -N -e "SELECT COUNT(*) FROM asterisk.modules" 2>/dev/null | tr -d '[:space:]')
        { [ -n "${mod_count}" ] && [ "${mod_count}" -gt 5 ]; } \
            || die "framework modules table empty after install_amp (upstream tool misreported success)"
        # generate device/dialplan configs from the freshly registered modules
        run_logged /var/lib/asterisk/bin/retrieve_conf \
            || die "retrieve_conf failed after framework install"
    fi

    # Non-interactive password initialization (sets MariaDB/Cyrus root,
    # panel admin password, applies pending DB scripts, saves /etc/issabel.conf).
    # The upstream tool can print internal errors yet exit 0 — verify outcomes.
    run_logged /usr/bin/issabel-admin-passwords --ensure-jwt-secret \
        || die "jwt secret init failed"
    run_logged /usr/bin/issabel-admin-passwords --cli init \
        "${MYSQL_ROOT_PASS}" "${ADMIN_PASS}" \
        || die "password initialization failed (see ${LOG})"
    grep -q "^mysqlrootpwd=${MYSQL_ROOT_PASS}$" /etc/issabel.conf 2>/dev/null \
        || die "password init did not persist mysqlrootpwd (upstream tool misreported success)"

    # The upstream --cli init skips its whole web-password step when its key
    # file already exists ("Password configuration already present"), which
    # leaves the panel (acl_user, md5) and admin console (ampusers, sha1)
    # credentials unset. Idempotently enforce the credential-file password
    # on BOTH auth stores, then verify for real.
    ensure_admin_credentials

    # hard verification: the admin password must actually be in force
    local amp_ok=""
    for try in 1 2 3 4 5; do
        amp_ok=$(mysql_any -N -e "SELECT COUNT(*) FROM asterisk.ampusers WHERE username='admin' AND password_sha1=SHA1('${ADMIN_PASS}')" 2>/dev/null || true)
        [ "${amp_ok}" = "1" ] && break
        sleep 2
    done
    [ "${amp_ok}" = "1" ] || die "admin password not in force on ampusers"
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

stage_mytel_layer() {
    stage_done mytel_layer && return 0
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

    # 6) Admin theme patchers (restore-then-apply, create .bak-mt backups)
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

    # 8) Clear known caches + ownership + validate Apache config
    find "${WEB_ROOT}" -name '*.tplc' -delete 2>/dev/null || true
    rm -rf "${WEB_ROOT}/themes/mytel/cache" 2>/dev/null || true
    /usr/sbin/amportal chown >>"$LOG" 2>&1 || true
    httpd -t >>"$LOG" 2>&1 || die "apache configuration invalid after patching"
    systemctl enable httpd >>"$LOG" 2>&1 || true
    systemctl restart httpd >>"$LOG" 2>&1 || die "httpd restart failed"

    mark_stage mytel_layer
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
    mod_count=$(mysql_any -N -e "SELECT COUNT(*) FROM asterisk.modules" 2>/dev/null | tr -d '[:space:]')
    if ! { [ -n "${mod_count}" ] && [ "${mod_count}" -gt 5 ]; } || [ ! -f /etc/asterisk/pjsip_additional.conf ]; then
        rm -f "${STATE_DIR}/stages/framework.done"
        die "framework incomplete (modules=${mod_count:-0}); run the installer again to repair"
    fi

    systemctl is-active --quiet mariadb || die "self-check: mariadb not active"
    systemctl is-active --quiet httpd   || die "self-check: httpd not active"
    sleep 8
    systemctl is-active --quiet asterisk || warn "asterisk unit not active yet (may start on first config load)"

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
    if [ -t 1 ]; then
        echo "   رمز پنل:        ${ADMIN_PASS}"
        echo "   رمز MariaDB:    ${MYSQL_ROOT_PASS}"
    else
        echo "   رمز‌ها:          ${CRED_FILE} (فقط root)"
    fi
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
    acquire_lock

    # Truncate only AFTER the lock is ours (a refused run must not clobber
    # the active run's log).
    : >"${LOG}"
    chmod 600 "${LOG}"
    echo "MyTellPBX ${MYTELLPBX_VERSION} installer — $(date)" >>"${LOG}"

    verify_bundle

    stage_repos
    stage_update
    stage_packages1
    stage_packages2
    stage_post_base
    stage_framework_init
    stage_mytel_layer
    stage_selfcheck
    finish
}

main "$@"
