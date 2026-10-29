#!/usr/bin/env bash
# MyTellPBX v7.1.3 — OpDesk rebrand + Persian error layer (one-shot installer).
#
# Run on the PBX server as root, from the extracted release folder:
#   bash opdesk/rebrand/00-apply-all.sh
#
# Steps (each idempotent): stop on first failure, rebuild, restart the backend.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
F=/opt/opdesk/frontend
export PATH=/opt/node24/bin:$PATH
fail=0

echo "== 0/6 backup current frontend"
tar -czf /root/opdesk-rebrand-backup-$(date +%Y%m%dT%H%M%SZ).tar.gz \
    "$F/src" "$F/index.html" "$F/dist" 2>/dev/null && echo backup-ok

echo "== 1/6 persian error map into the frontend"
install -m 644 "$HERE/../frontend-src/lib/errors-fa.ts" "$F/src/lib/errors-fa.ts"

echo "== 2/6 rebrand + guard rule order + fa defaults"
if ! bash "$HERE/01-apply-rebrand.sh"; then
  echo "01 failed" >&2; fail=1
fi

echo "== 3/6 vite base path (assets under /opdesk/)"
if ! bash "$HERE/02-fix-vite-base.sh"; then
  echo "02 failed" >&2; fail=1
fi

echo "== 4/6 remaining locales (ar/es/pt/uk)"
if ! bash "$HERE/03-rebrand-locales.sh"; then
  echo "03 failed" >&2; fail=1
fi

echo "== 5/6 last visible strings"
if ! bash "$HERE/04-fix-remaining-strings.sh"; then
  echo "04 failed" >&2; fail=1
fi

echo "== 6/6 nav labels persian"
if ! bash "$HERE/05-nav-admin-fa.sh"; then
  echo "05 failed" >&2; fail=1
fi

if [[ $fail -ne 0 ]]; then
  echo "APPLY-FAILED (backup kept)" >&2
  exit 1
fi
echo "APPLY-ALL-DONE — panel rebranded to میز کار اپراتور مای‌تل with Persian errors"
