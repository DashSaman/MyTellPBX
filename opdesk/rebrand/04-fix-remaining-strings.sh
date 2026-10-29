#!/usr/bin/env bash
# Fix the last visible 'OpDesk' default (apiKeys.emptyHintIntegrate) and rebuild.
set -uo pipefail
F=/opt/opdesk/frontend
export PATH=/opt/node24/bin:$PATH
python3 - "$F/src" <<'PY' || exit 1
import os, sys
root = sys.argv[1]
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d != "node_modules"]
    for name in filenames:
        if not name.endswith((".tsx", ".ts", ".json")):
            continue
        p = os.path.join(dirpath, name)
        t = open(p, encoding="utf-8", errors="replace").read()
        if "integrate with OpDesk" in t:
            t = t.replace("integrate with OpDesk", "integrate with MyTel Operator Desk")
            open(p, "w", encoding="utf-8", newline="\n").write(t)
            print("fixed:", p)
PY
cd "$F" || exit 1
npm run build 2>&1 | tail -4
rc=${PIPESTATUS[0]}
[[ $rc -eq 0 ]] || { echo BUILD-FAILED >&2; exit 1; }
systemctl restart mytellpbx-opdesk
sleep 8
systemctl is-active mytellpbx-opdesk
JS=$(ls "$F"/dist/assets/index-*.js | head -1)
echo "bundle OpDesk count: $(grep -o 'OpDesk' "$JS" | wc -l)"
echo "LAST-FIX-DONE"
