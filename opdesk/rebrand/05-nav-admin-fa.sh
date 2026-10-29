#!/usr/bin/env bash
# Finalize: translate the nav.admin key to Persian in fa.json, rebuild, restart,
# then re-run the wrong-password alert check with proper React input events.
set -uo pipefail
F=/opt/opdesk/frontend
export PATH=/opt/node24/bin:$PATH

python3 - "$F/src/i18n/locales/fa/translation.json" <<'PY' || exit 1
import json, sys
p = sys.argv[1]
j = json.load(open(p, encoding="utf-8"))
nav = j.get("nav") or {}
nav["admin"] = "مدیریت"
j["nav"] = nav
open(p, "w", encoding="utf-8", newline="\n").write(
    json.dumps(j, ensure_ascii=False, indent=2))
print("nav.admin fa set; keys:", len(json.dumps(j)))
PY

cd "$F" || exit 1
npm run build 2>&1 | tail -3
rc=${PIPESTATUS[0]}
[[ $rc -eq 0 ]] || { echo BUILD-FAILED >&2; exit 1; }
systemctl restart mytellpbx-opdesk
sleep 8
systemctl is-active mytellpbx-opdesk
echo "FINALIZE-DONE"
