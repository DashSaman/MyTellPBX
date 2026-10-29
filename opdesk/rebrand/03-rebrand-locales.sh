#!/usr/bin/env bash
# Rebrand the remaining locales (ar/es/pt/uk) and rebuild.
set -uo pipefail
F=/opt/opdesk/frontend
export PATH=/opt/node24/bin:$PATH

python3 - <<'PY' || exit 1
import json
for code in ("ar", "es", "pt", "uk"):
    p = f"/opt/opdesk/frontend/src/i18n/locales/{code}/translation.json"
    t = open(p, encoding="utf-8").read()
    n = t.count("OpDesk")
    t = t.replace("OpDesk", "MyTel Operator Desk")
    open(p, "w", encoding="utf-8", newline="\n").write(t)
    json.loads(open(p, encoding="utf-8").read())
    print(code, "rebranded:", n)
PY

cd "$F" || exit 1
npm run build 2>&1 | tail -6
rc=${PIPESTATUS[0]}
[[ $rc -eq 0 ]] || { echo BUILD-FAILED >&2; exit 1; }
systemctl restart mytellpbx-opdesk
sleep 8
systemctl is-active mytellpbx-opdesk
JS=$(ls "$F"/dist/assets/index-*.js | head -1)
echo "bundle OpDesk count: $(grep -o 'OpDesk' "$JS" | wc -l)"
echo "bundle اپدسک count: $(grep -c 'اپدسک' "$JS")"
curl -sk https://127.0.0.1/opdesk/ | grep -o '<title>[^<]*</title>'
echo "LOCALES-DONE"
