#!/bin/bash
# Shared MytelPBX output for SSH and the local installation console.

mytel_terminal_init() {
  MYTEL_UI_BLUE= MYTEL_UI_AMBER= MYTEL_UI_GREEN= MYTEL_UI_RED= MYTEL_UI_RESET=
  if [[ -t 1 && -n ${TERM:-} && $TERM != dumb && ! ${NO_COLOR+x} ]]; then
    MYTEL_UI_BLUE=$'\033[1;94m'
    MYTEL_UI_AMBER=$'\033[1;33m'
    MYTEL_UI_GREEN=$'\033[1;32m'
    MYTEL_UI_RED=$'\033[1;31m'
    MYTEL_UI_RESET=$'\033[0m'
  fi
}

mytel_terminal_banner() {
  mytel_terminal_init
  local mode='Online installation on Rocky Linux 8.10 · Asterisk 20'
  if [[ ${1:-} == offline ]]; then mode='Offline installation from ISO · Asterisk 20'; fi
  printf '\n%s  Mytel%sPBX%s   /   Mytel.one\n%s  ──────────────────────────────%s\n  %s\n' \
    "$MYTEL_UI_BLUE" "$MYTEL_UI_AMBER" "$MYTEL_UI_RESET" "$MYTEL_UI_BLUE" "$MYTEL_UI_RESET" "$mode"
}

mytel_terminal_offline_phase() {
  printf '\n%s  [%s/%s]  %s%s\n' "$MYTEL_UI_BLUE" "$1" "$2" "$3" "$MYTEL_UI_RESET"
}

mytel_terminal_offline_ready() {
  printf '\n%s  MytelPBX · Installation complete%s\n' "$MYTEL_UI_GREEN" "$MYTEL_UI_RESET"
  mytel_panel_address
}

mytel_panel_address() {
  local client client_port server server_port address
  read -r client client_port server server_port <<< "${SSH_CONNECTION:-}"
  # Prefer the SSH destination if it is actually assigned. For a local console,
  # use the first global IPv4 address reported by the installed network stack.
  address=$(ip -o -4 addr show up scope global 2>/dev/null | awk -v preferred="$server" '
    { split($4, net, "/"); if (!first) first=net[1]; if (net[1]==preferred) found=net[1] }
    END { print found ? found : first }') || address=''
  if [[ $address =~ ^[0-9.]+$ ]]; then
    printf '  Web panel  https://%s/   ·   Sign in as admin\n\n' "$address"
  else
    printf '  Open the server HTTPS address and sign in as admin.\n\n'
  fi
}

mytel_terminal_phase() {
  local number= label
  MYTEL_UI_ACTIVE_STEP=
  case "$1" in
    check_tools)         number=01; label='Checking setup tools' ;;
    add_repos)                      label='Registering package repositories' ;;
    settings)                       label='Preparing the base system' ;;
    select_language)     number=02; label='Setting language defaults' ;;
    additional_packages)            label='Preparing the community package set' ;;
    generate_files)                 label='Preparing package lists' ;;
    centos8_tweaks)       number=03; label='Preparing the package manager' ;;
    update_os)           number=04; label='Updating the operating system' ;;
    install_packages)    number=05; label='Installing MytelPBX packages' ;;
    post_install)        number=06; label='Setting up base services' ;;
    set_passwords)       number=07; label='Applying passwords and SIP driver' ;;
    mytel_addons)        number=08; label='Setting up MytelPBX and MytelDesk' ;;
    cleanup)                       label='Cleaning up temporary setup files' ;;
    mytel_verify_addons) number=09; label='Checking installed services' ;;
    *) return 0 ;;
  esac
  MYTEL_UI_ACTIVE_STEP=$1
  if [[ -n $number ]]; then
    printf '\n%s  [%s/09]  %s%s\n' "$MYTEL_UI_BLUE" "$number" "$label" "$MYTEL_UI_RESET"
  else
    printf '    %s\n' "$label"
  fi
}

mytel_terminal_result() {
  [[ ${MYTEL_UI_ACTIVE_STEP:-} == "$1" ]] || return 0
  if (( $2 == 0 )); then
    printf '    %sDone%s · %ss\n' "$MYTEL_UI_GREEN" "$MYTEL_UI_RESET" "$3"
  else
    printf '    %sStopped%s · %ss · exit %s\n' "$MYTEL_UI_RED" "$MYTEL_UI_RESET" "$3" "$2" >&2
  fi
}

mytel_terminal_success() {
  local seconds
  printf '\n%s  MytelPBX · Installation complete%s\n' "$MYTEL_UI_GREEN" "$MYTEL_UI_RESET"
  mytel_panel_address
  for seconds in 5 4 3 2 1; do
    if [[ -t 1 && ${TERM:-dumb} != dumb ]]; then
      printf '\r  Server reboots in %d seconds…' "$seconds"
    else
      printf '  Server reboots in %d seconds…\n' "$seconds"
    fi
    sleep 1
  done
  printf '\n'
}

mytel_run_dnf() {
  local kind=$1 logger="${MYTEL_BUNDLE_ROOT}/installer/dnf-progress.py"
  local log="${MYTEL_NATIVE_WORK}/netinstall.log"
  local -a statuses
  shift
  "${MYTEL_PYTHON}" -B "$logger" --log "$log" --kind "$kind" --check-log || return 1
  LC_ALL=C PYTHONUNBUFFERED=1 "$@" 2>&1 | MYTELL_CONSOLE_ENGLISH=1 PYTHONIOENCODING=utf-8 "${MYTEL_PYTHON}" -B "$logger" --log "$log" --kind "$kind" --detail
  statuses=("${PIPESTATUS[@]}")
  (( statuses[0] == 0 )) || return "${statuses[0]}"
  return "${statuses[1]}"
}

mytel_package_batch() {
  local package status title
  local -a packages=() missing=() repository_options=()
  IFS=$' \t\n' read -r -d '' -a packages <<< "$1" || :
  IFS=$' \t\n' read -r -a repository_options <<< "${BETAREPO:-}" || :
  case "$2" in
    core) title='Base packages' ;;
    product) title='Product packages' ;;
    *) return 2 ;;
  esac
  for package in "${packages[@]}"; do
    if [[ ! $package =~ ^[A-Za-z0-9][A-Za-z0-9_.+:%-]{0,179}$ ]]; then
      printf 'MytelPBX · Invalid package name. Package phase stopped.\n' >&2
      return 2
    fi
    if ! rpm --quiet -q "$package"; then
      missing+=("$package")
    fi
  done
  printf '    %s · %d to install · %d already installed\n' "$title" "${#missing[@]}" "$((${#packages[@]} - ${#missing[@]}))"
  (( ${#missing[@]} )) || return 0
  if mytel_run_dnf packages yum "${repository_options[@]}" -y install "${missing[@]}"; then
    return 0
  else
    status=$?
  fi
  printf '%s transaction failed (exit %d), requested: %s\n' "$title" "$status" "${missing[*]}" >> "${MYTEL_NATIVE_WORK}/netinstall_errors.txt"
  printf '    %s transaction failed · exit %d\n' "$title" "$status" >&2
  return "$status"
}

mytel_terminal_init
