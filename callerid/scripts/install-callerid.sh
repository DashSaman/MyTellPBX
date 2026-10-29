#!/bin/bash
# ==========================================================================
# MyTellPBX Caller-ID integration installer (feature A)
# Subcommands:
#   install        deploy AGI + dialplan markers + globals (default DISABLED)
#   enable         set MYTELLPBX_CIDNORM=1 in runtime + saved config
#   disable        set MYTELLPBX_CIDNORM=0 (baseline routing preserved)
#   quirks on|off  toggle provider-quirk profile
#   status         JSON: installed/enabled(loaded)/quirks/last-verify
#   verify         check LOADED dialplan + AGI exec as asterisk user
#   uninstall      remove ONLY owned markers/agi/globals; keep other edits
#   fixtures on|off  add/remove local TEST fixtures (testcaller ctx + PJSIP
#                    test endpoint 69001) for real-SIP-channel tests
# Idempotent + rerun-safe. All edits marker-scoped; backups under
# /root/mytellpbx-callerid/backups/ before first touch.
# ==========================================================================
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SHARE_DIR=/usr/local/share/mytellpbx/callerid
EXT_CUSTOM=/etc/asterisk/extensions_custom.conf
GLOBALS_CUSTOM=/etc/asterisk/globals_custom.conf
PJSIP_CUSTOM=/etc/asterisk/pjsip_custom.conf
AGI_DIR=/var/lib/asterisk/agi-bin/mytellpbx
STATE_DIR=/etc/mytellpbx
STATE_FILE=$STATE_DIR/callerid-state.json
BACKUP_DIR=/root/mytellpbx-callerid/backups
MARK_BEGIN='─── BEGIN MyTellPBX CallerID'
MARK_END='─── END MyTellPBX CallerID'
FIX_BEGIN='─── BEGIN MyTellPBX CallerID TEST FIXTURES'
FIX_END='─── END MyTellPBX CallerID TEST FIXTURES'

log() { echo "[mytellpbx-callerid] $*"; }
die() { echo "[mytellpbx-callerid] ERROR: $*" >&2; exit 1; }

need_root() { [ "$(id -u)" = 0 ] || die "root required"; }

backup_once() {
    local f=$1
    [ -f "$f" ] || touch "$f"
    if [ ! -f "$BACKUP_DIR/$(basename "$f").pre-install" ]; then
        mkdir -p "$BACKUP_DIR"
        cp -a "$f" "$BACKUP_DIR/$(basename "$f").pre-install"
        log "backup saved: $BACKUP_DIR/$(basename "$f").pre-install"
    fi
}

write_state() { # key value … → JSON ساده
    mkdir -p "$STATE_DIR"
    # پوشهٔ مشترک با پل اپدسک است (رمز پل در opdesk-bridge.pw)؛ دسترسی پیمایش
    # وب‌کاربر asterisk باید حفظ شود — هرگز به 0700 برگردانده نمی‌شود.
    chown root:asterisk "$STATE_DIR" 2>/dev/null || true
    chmod 750 "$STATE_DIR"
    python3 - "$@" <<'PY'
import json, sys, pathlib
p = pathlib.Path('/etc/mytellpbx/callerid-state.json')
d = json.loads(p.read_text()) if p.exists() and p.read_text().strip() else {}
for i in range(1, len(sys.argv), 2):
    d[sys.argv[i]] = sys.argv[i + 1]
p.write_text(json.dumps(d, ensure_ascii=False, indent=1))
PY
    # خودِ فایل وضعیت، داخلیِ نرمال‌ساز است و ربطی به وب‌کاربر ندارد
    chown root:root "$STATE_FILE" 2>/dev/null || true
    chmod 600 "$STATE_FILE"
}

reload_dialplan() { asterisk -rx 'dialplan reload' >/dev/null; }

loaded_enabled() {
    asterisk -rx 'dialplan show globals' 2>/dev/null \
        | grep -qE '^[[:space:]]*MYTELLPBX_CIDNORM[[:space:]]*=[[:space:]]*1[[:space:]]*$' \
        && echo 1 || echo 0
}

check_drift() {
    # تشخیص جابه‌جایی زنجیرهٔ شامل‌های اصلی from-pstn (تصمیم داور)
    local includes
    includes=$(asterisk -rx 'dialplan show from-pstn' 2>/dev/null \
        | grep -oP "(?<=Include =>        ')[^']+" | tr '\n' ' ')
    case "$includes" in
        "from-pstn-custom ext-did ext-did-post-custom from-did-direct ext-did-catchall ")
            return 0 ;;
        *) log "WARNING: from-pstn include chain changed: $includes"
           write_state drift "$includes"
           return 1 ;;
    esac
}

inject_block() { # file begin_marker end_marker blockfile
    local f=$1 b=$2 e=$3 blk=$4 tmp
    backup_once "$f"; touch "$f"
    tmp=$(mktemp)
    # بخش پیش از نشان آغاز (بدون بلوک قبلی)
    awk -v B="$b" 'index($0, B) {exit} {print}' "$f" > "$tmp"
    cat "$blk" >> "$tmp"
    # بخش پس از نشان پایان
    awk -v E="$e" 'f {print} index($0, E) {f=1}' "$f" >> "$tmp"
    # اگر بلوک قبلی آخرِ فایل نبود، بخش میانی قدیم دور ریخته می‌شود (عمداً: جایگزینی نشان‌دار)
    chmod --reference="$f" "$tmp"; chown --reference="$f" "$tmp"
    mv "$tmp" "$f"
}

set_global() { # name value
    backup_once "$GLOBALS_CUSTOM"; touch "$GLOBALS_CUSTOM"
    local tmp; tmp=$(mktemp)
    grep -v "^$1 *=" "$GLOBALS_CUSTOM" > "$tmp" || true
    echo "$1 = $2" >> "$tmp"
    chmod --reference="$GLOBALS_CUSTOM" "$tmp" 2>/dev/null || chmod 644 "$tmp"
    chown --reference="$GLOBALS_CUSTOM" "$tmp" 2>/dev/null || true
    mv "$tmp" "$GLOBALS_CUSTOM"
}

cmd_install() {
    need_root
    [ -d /var/lib/asterisk/agi-bin ] || die "agi-bin not found"
    [ -x /usr/sbin/asterisk ] || die "asterisk not found"
    # زنجیرهٔ پشتیبانی‌شده الزامی است؛ ادامهٔ نصب روی زنجیرهٔ ناشناس، مسیریابی
    # سرور را می‌شکند (ادامهٔ انتقال در dialplan/mytellpbx-cid.conf ثابت است)
    check_drift || die "from-pstn include chain is not the supported baseline; refusing to install (drift recorded in state). Resolve the chain or extend mytellpbx-from-pstn-rest first."

    # منبعِ عمومیِ خوانا برای اجرای آزمون‌ها با کاربر آستریسک
    mkdir -p "$SHARE_DIR"
    cp -a "$SRC_DIR"/. "$SHARE_DIR"/
    chmod 755 "$SHARE_DIR" "$SHARE_DIR/scripts"
    find "$SHARE_DIR" -type d -exec chmod 755 {} +
    find "$SHARE_DIR" -type f -exec chmod 644 {} +
    chmod 755 "$SHARE_DIR/scripts/"*.sh "$SHARE_DIR/agi/"*.php

    mkdir -p "$AGI_DIR" /var/lib/asterisk/agi-bin/lib
    # AGI: …/agi-bin/mytellpbx/mytellpbx-cidnorm.php → require ../lib/CidNorm.php
    #      = …/agi-bin/lib/CidNorm.php
    install -m 755 "$SRC_DIR/agi/mytellpbx-cidnorm.php" "$AGI_DIR/mytellpbx-cidnorm.php"
    install -m 644 "$SRC_DIR/lib/CidNorm.php" /var/lib/asterisk/agi-bin/lib/CidNorm.php
    chown -R asterisk:asterisk "$AGI_DIR" /var/lib/asterisk/agi-bin/lib

    inject_block "$EXT_CUSTOM" "$MARK_BEGIN" "$MARK_END" \
        "$SRC_DIR/dialplan/mytellpbx-cid.conf"

    set_global MYTELLPBX_CIDNORM 0
    set_global MYTELLPBX_CIDNORM_QUIRKS 0

    reload_dialplan
    cmd_verify
    write_state installed "$(date -Is)" revision "$(cd "$SRC_DIR" && git rev-parse --short HEAD 2>/dev/null || echo workspace)"
    log "install complete (ENABLED=0 by default — safety step)"
}

cmd_enable()  { need_root; set_global MYTELLPBX_CIDNORM 1; reload_dialplan
                [ "$(loaded_enabled)" = 1 ] || die "enable did not reach loaded dialplan"
                write_state enabled "$(date -Is)"; log "enabled (loaded)"; }
cmd_disable() { need_root; set_global MYTELLPBX_CIDNORM 0; reload_dialplan
                write_state enabled "0"; log "disabled — baseline routing"; }
cmd_quirks()  { need_root
    # AGI فقط '1' را فعال می‌داند؛ ورودی انسانی on/off به 1/0 نگاشت می‌شود
    local v
    case "$1" in
        1|on|ON|true)    v=1 ;;
        0|off|OFF|false) v=0 ;;
        *) die "usage: install-callerid.sh quirks on|off" ;;
    esac
    set_global MYTELLPBX_CIDNORM_QUIRKS "$v"; reload_dialplan
    write_state quirks "$v"; log "quirks=$v"; }

cmd_status() {
    local inst=0
    grep -q "$MARK_BEGIN" "$EXT_CUSTOM" 2>/dev/null && inst=1
    printf '{"installed":%s,"enabled_loaded":%s,"quirks_file":"%s","drift":%s}\n' \
      "$inst" "$(loaded_enabled)" \
      "$(grep -oP '(?<=^MYTELLPBX_CIDNORM_QUIRKS = ).*' "$GLOBALS_CUSTOM" 2>/dev/null || echo 0)" \
      "\"$(grep -oP '(?<=drift": ")[^"]*' "$STATE_FILE" 2>/dev/null || echo '')\""
}

cmd_verify() {
    local ok=1
    check_drift || { log "verify: from-pstn chain drifted from supported baseline"; ok=0; }
    asterisk -rx 'dialplan show from-pstn-custom' | grep -q '_\[0-9\]!' || { log "verify: hook pattern not loaded"; ok=0; }
    asterisk -rx 'dialplan show mytellpbx-cidnorm'  | grep -q 'AGI'        || { log "verify: gosub not loaded"; ok=0; }
    asterisk -rx 'dialplan show mytellpbx-from-pstn-rest' | grep -q 'ext-did' || { log "verify: continuation missing"; ok=0; }
    # آزمون‌ها از منبع نصب‌شده؛ فایل مستقرِ AGI فقط بررسی نحوی/اجرا
    runuser -u asterisk -- php "$SHARE_DIR/agi/mytellpbx-cidnorm.php" --selftest >/dev/null 2>&1 \
        || { log "verify: AGI selftest as asterisk user FAILED"; ok=0; }
    runuser -u asterisk -- php "$SHARE_DIR/tests/CidNormTest.php" >/dev/null 2>&1 \
        || { log "verify: lib tests as asterisk user FAILED"; ok=0; }
    runuser -u asterisk -- php -l "$AGI_DIR/mytellpbx-cidnorm.php" >/dev/null 2>&1 \
        || { log "verify: deployed AGI syntax FAILED"; ok=0; }
    [ "$ok" = 1 ] && { write_state last_verify "PASS $(date -Is)"; log "verify PASS"; } \
                  || { write_state last_verify "FAIL $(date -Is)"; die "verify FAIL"; }
}

cmd_uninstall() {
    need_root
    backup_once "$EXT_CUSTOM"; backup_once "$GLOBALS_CUSTOM"
    local tmp; tmp=$(mktemp)
    awk -v B="$MARK_BEGIN" -v E="$MARK_END" 'index($0,B),index($0,E){next} {print}' "$EXT_CUSTOM" > "$tmp"
    chmod --reference="$EXT_CUSTOM" "$tmp"; chown --reference="$EXT_CUSTOM" "$tmp"; mv "$tmp" "$EXT_CUSTOM"
    set_global_removed() { grep -v "^$1 *=" "$GLOBALS_CUSTOM" > "$tmp" || true; mv "$tmp" "$GLOBALS_CUSTOM"; }
    set_global_removed MYTELLPBX_CIDNORM; set_global_removed MYTELLPBX_CIDNORM_QUIRKS
    rm -rf "$AGI_DIR" /var/lib/asterisk/agi-bin/lib/CidNorm.php "$SHARE_DIR"
    cmd_fixtures off || true
    reload_dialplan
    asterisk -rx 'dialplan show from-pstn-custom' | grep -q 'No Context' \
        && log "uninstall clean (context removed)" || log "uninstall: custom ctx may retain foreign entries"
    write_state installed "removed"
}

cmd_fixtures() {
    need_root
    local FIXBLOCK=/tmp/mytellpbx-fixtures-block.conf
    case $1 in
    on)
        cat > "$FIXBLOCK" <<'EOF'
; ─── BEGIN MyTellPBX CallerID TEST FIXTURES ───
[mytellpbx-testcaller]
; مبدأ آزمون: با کانتکست استاندارد و بدون هیچ تغییری وارد مسیر واقعی می‌شود
; ۶۰۰۱: +۹۸ موبایل | ۶۰۰۲: ۱۰رقمی بدون صفر | ۶۰۰۳: خارجی | ۶۰۰۴: ناشناس
exten => 6001,1,Set(CALLERID(num)=+989123456789)
 same => n,Goto(from-trunk,${EXTEN},1)
exten => 6002,1,Set(CALLERID(num)=9123456789)
 same => n,Set(CALLERID(name)=9123456789)
 same => n,Goto(from-trunk,${EXTEN},1)
exten => 6003,1,Set(CALLERID(num)=+442071234567)
 same => n,Set(CALLERID(name)=Rayan Clinic)
 same => n,Goto(from-trunk,${EXTEN},1)
exten => 6004,1,Set(CALLERID(num)=)
 same => n,Goto(from-trunk,${EXTEN},1)
; ─── END MyTellPBX CallerID TEST FIXTURES ───
EOF
        inject_block "$EXT_CUSTOM" "$FIX_BEGIN" "$FIX_END" "$FIXBLOCK"
        reload_dialplan
        log "test fixtures ON (testcaller context)"
        ;;
    off)
        for f in "$EXT_CUSTOM" "$PJSIP_CUSTOM"; do
            [ -f "$f" ] || continue
            awk -v B="$FIX_BEGIN" -v E="$FIX_END" 'index($0,B),index($0,E){next} {print}' "$f" > "$FIXBLOCK"
            chmod --reference="$f" "$FIXBLOCK"; chown --reference="$f" "$FIXBLOCK"; mv "$FIXBLOCK" "$f"
        done
        reload_dialplan
        log "test fixtures OFF"
        ;;
    esac
}

case "${1:-}" in
    install) cmd_install ;;
    enable) cmd_enable ;;
    disable) cmd_disable ;;
    quirks) [ "${2:-}" = on ] || [ "${2:-}" = off ] || die "quirks on|off"; cmd_quirks "$2" ;;
    status) cmd_status ;;
    verify) cmd_verify ;;
    uninstall) cmd_uninstall ;;
    fixtures) [ "${2:-}" = on ] || [ "${2:-}" = off ] || die "fixtures on|off"; cmd_fixtures "$2" ;;
    *) grep -m1 '^#.*Subcommands' "$0" | head -8; die "usage: $0 install|enable|disable|quirks on/off|status|verify|uninstall|fixtures on/off" ;;
esac
