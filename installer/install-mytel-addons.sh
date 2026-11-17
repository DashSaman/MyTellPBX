#!/bin/bash
# Shared post-native hook for the official online installer and Issabel ISO.
set -euo pipefail
umask 077
MYTEL_BUNDLE_ROOT="${MYTEL_BUNDLE_ROOT:-$(cd -- "$(dirname -- "$0")/.." && pwd -P)}"
export MYTEL_BUNDLE_ROOT
exec "${MYTEL_PYTHON:-/usr/bin/python3}" -B "${MYTEL_BUNDLE_ROOT}/installer/native-addons.py" "$@"
