#!/usr/bin/env bash
# The build must emit /opdesk/-rooted asset URLs (the app lives behind the
# Issabel Apache /opdesk/ proxy). Add base:'/opdesk/' to vite.config.ts and
# rebuild; then verify the live page end to end.
set -uo pipefail
F=/opt/opdesk/frontend
export PATH=/opt/node24/bin:$PATH

python3 - "$F/vite.config.ts" <<'PY' || exit 1
import sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
if "base:" in t:
    print("base already set")
else:
    old = "export default defineConfig({"
    new = "export default defineConfig({\n  base: '/opdesk/',"
    if old not in t:
        sys.exit("defineConfig anchor missing")
    t = t.replace(old, new, 1)
    open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("base:/opdesk/ added")
PY

cd "$F" || exit 1
npm run build 2>&1 | tail -5
rc=${PIPESTATUS[0]}
[[ $rc -eq 0 ]] || { echo BUILD-FAILED >&2; exit 1; }
systemctl restart mytellpbx-opdesk
sleep 8
systemctl is-active mytellpbx-opdesk
echo "--- served index asset tags"
curl -sk https://127.0.0.1/opdesk/ | grep -oE '(src|href)="[^"]*(assets|favicon|emblem)[^"]*"' | head -6
curl -sk -o /dev/null -w 'app js: %{http_code}\n' "https://127.0.0.1$(curl -sk https://127.0.0.1/opdesk/ | grep -oE 'src="[^"]*index-[^\"]+\.js' | sed 's/src="//;s/"//')"
echo "BASE-FIX-DONE"
