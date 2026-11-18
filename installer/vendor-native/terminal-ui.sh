#!/bin/bash
# Installer output for an ordinary SSH terminal. Source only in the online flow.

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
  printf '\n%s  Mytel%sPBX%s   /   Mytel.one\n%s  ──────────────────────────────%s\n  Online installation on Rocky Linux 8.10 · Asterisk 20\n' \
    "$MYTEL_UI_BLUE" "$MYTEL_UI_AMBER" "$MYTEL_UI_RESET" "$MYTEL_UI_BLUE" "$MYTEL_UI_RESET"
}

mytel_terminal_phase() {
  local number= label
  MYTEL_UI_ACTIVE_STEP=
  case "$1" in
    check_dialog)        number=01; label='Preparing setup tools' ;;
    add_repos)                      label='Registering package repositories' ;;
    settings)                       label='Preparing the base system' ;;
    select_language)     number=02; label='Setting language defaults' ;;
    additional_packages)            label='Preparing the community package set' ;;
    generate_files)                 label='Preparing package lists' ;;
    centos8_tweaks)       number=03; label='Preparing the package manager' ;;
    clean_yum)                      label='Refreshing repository cache' ;;
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
  printf '\n%s  MytelPBX · Installation complete%s\n\n' "$MYTEL_UI_GREEN" "$MYTEL_UI_RESET"
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
  local operation=$2 kind package total current=0 status first_error=0
  local -a packages=() repository_options=()
  IFS=$' \t\n' read -r -d '' -a packages <<< "$1" || :
  IFS=$' \t\n' read -r -a repository_options <<< "${BETAREPO:-}" || :
  case "$operation" in
    install) kind=packages ;;
    update)  kind=update ;;
    *) return 2 ;;
  esac
  for package in "${packages[@]}"; do
    if [[ ! $package =~ ^[A-Za-z0-9][A-Za-z0-9_.+:%-]{0,179}$ ]]; then
      printf 'MytelPBX · Invalid package name. Package phase stopped.\n' >&2
      return 2
    fi
  done
  case "$3" in
    core)    printf '    Base packages · batch 1 of 2\n' ;;
    product) printf '    Product packages · batch 2 of 2\n' ;;
  esac
  total=${#packages[@]}
  for package in "${packages[@]}"; do
    current=$((current + 1))
    if [[ $operation == install ]] && rpm --quiet -q "$package"; then
      printf '    [%d/%d] %s  ·  Already installed\n' "$current" "$total" "$package"
      continue
    fi
    printf '    %s[%d/%d]%s %s  ·  Running\n' "$MYTEL_UI_AMBER" "$current" "$total" "$MYTEL_UI_RESET" "$package"
    mytel_run_dnf "$kind" yum "${repository_options[@]}" -y "$operation" "$package"
    status=$?
    if (( status == 0 )); then
      printf '      %sReady%s\n' "$MYTEL_UI_GREEN" "$MYTEL_UI_RESET"
    else
      printf '%s: ERROR installing package (exit %d)\n' "$package" "$status" >> "${MYTEL_NATIVE_WORK}/netinstall_errors.txt"
      printf '%s: ERROR installing package (exit %d)\n' "$package" "$status" >> "${MYTEL_NATIVE_WORK}/netinstall.log"
      printf '      %sPackage operation failed%s · exit %d\n' "$MYTEL_UI_RED" "$MYTEL_UI_RESET" "$status" >&2
      if (( first_error == 0 )); then first_error=$status; fi
    fi
  done
  return "$first_error"
}

mytel_terminal_init
