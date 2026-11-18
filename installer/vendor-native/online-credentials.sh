# MytelPBX installer credential collection over an interactive terminal.

mytel_online_password_valid() {
    local LC_ALL=C
    (( ${#1} <= 1024 )) && [[ "$1" =~ ^[A-Za-z0-9.@=_!-]+$ ]]
}

mytel_prompt_online_password_pair() {
    local label=$1 target=$2 visibility=$3
    local -a read_args=(-r -u 8)
    local password confirmation
    [ "$visibility" = visible ] || read_args+=(-s)
    while :; do
        printf '  %s › ' "$label" >&8
        IFS= read "${read_args[@]}" password || return 1
        [ "$visibility" = visible ] || printf '\n' >&8
        if ! mytel_online_password_valid "$password"; then
            printf '  Use letters, numbers or .@=_!- (no spaces).\n\n' >&8
            continue
        fi
        printf '  Confirm password › ' >&8
        IFS= read "${read_args[@]}" confirmation || return 1
        [ "$visibility" = visible ] || printf '\n' >&8
        if [ "$password" = "$confirmation" ]; then
            printf -v "$target" '%s' "$password"
            printf '  Confirmed.\n\n' >&8
            return 0
        fi
        printf '  The two entries differ. Enter this password again.\n\n' >&8
    done
}

mytel_collect_online_passwords() (
    set +x
    set +a
    local visibility db_password admin_password accent reset sip_choice
    if ! { exec 8<>/dev/tty; } 2>/dev/null; then
        printf '\nMytelPBX requires an interactive terminal.\n' >&2
        return 1
    fi
    accent='' reset=''
    if [ "${TERM:-dumb}" != dumb ] && [ -z "${NO_COLOR+x}" ]; then
        accent=$'\033[1;36m' reset=$'\033[0m'
    fi
    printf '\n%s  MytelPBX  ·  ACCESS SETUP%s\n' "$accent" "$reset" >&8
    if [ "${MYTEL_HIDE_PASSWORDS:-0}" = 1 ]; then
        visibility=hidden
        printf '  Password entry is hidden.\n\n' >&8
    else
        visibility=visible
        printf '  Passwords are visible as you type. Use a private terminal.\n\n' >&8
    fi
    mytel_prompt_online_password_pair 'MariaDB root password' db_password "$visibility" || return 1
    mytel_prompt_online_password_pair 'Web panel admin password' admin_password "$visibility" || return 1
    printf '  SIP channel driver\n  1) PJSIP (default)\n  2) SIP\n' >&8
    while :; do
        printf '  Select driver [1] › ' >&8
        IFS= read -r -u 8 sip_choice || return 1
        case "$sip_choice" in
            ''|1) sip_choice=pjsip; break ;;
            2) sip_choice=sip; break ;;
            *) printf '  Enter 1 or 2.\n' >&8 ;;
        esac
    done
    printf '\n' >&8
    printf '%s\n%s\n%s\n' "$db_password" "$admin_password" "$sip_choice"
)

mytel_receive_online_passwords() {
    set +x
    set +a
    unset _mytel_db_password _mytel_admin_password MYTEL_ONLINE_SIP_DRIVER
    local sip_driver extra
    if { IFS= read -r -u 3 _mytel_db_password && IFS= read -r -u 3 _mytel_admin_password \
            && IFS= read -r -u 3 sip_driver \
            && ! IFS= read -r -u 3 extra && [ -z "$extra" ]; } 2>/dev/null \
            && mytel_online_password_valid "$_mytel_db_password" \
            && mytel_online_password_valid "$_mytel_admin_password" \
            && [[ "$sip_driver" = pjsip || "$sip_driver" = sip ]]; then
        exec 3<&-
        export MYTEL_ONLINE_SIP_DRIVER="$sip_driver"
        return 0
    fi
    exec 3<&-
    unset _mytel_db_password _mytel_admin_password
    printf '\nMytelPBX access setup was cancelled or incomplete.\n' >&2
    return 1
}

mytel_apply_online_passwords() {
    set +x
    set +a
    local helper="$MYTEL_NATIVE_WORK/online-password-init.php" status
    if "$MYTEL_PYTHON" -I -B "$MYTEL_BUNDLE_ROOT/installer/vendor-native/online-passwords.py" "$helper"; then
        if /usr/bin/php -d zend.exception_ignore_args=1 "$helper" --init \
                3< <(printf '%s\n%s\n' "$_mytel_db_password" "$_mytel_admin_password"); then
            status=0
        else
            status=$?
        fi
    else
        status=$?
    fi
    unset _mytel_db_password _mytel_admin_password
    rm -f -- "$helper"
    return "$status"
}
