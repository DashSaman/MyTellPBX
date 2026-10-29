#!/usr/bin/env bash
# MyTel rebrand + Persian error layer for the OpDesk frontend (server-side).
# Idempotent, anchored replacements with a full pre-change backup; aborts
# before the build if any anchor is missing.
set -uo pipefail
F=/opt/opdesk/frontend
B=/opt/opdesk/backend
BRAND_FA="میز کار اپراتور مای‌تل"
BRAND_EN="MyTel Operator Desk"
STAMP=$(date +%Y%m%dT%H%M%SZ)
BACKUP=/root/opdesk-rebrand-backup-$STAMP.tar.gz

fail=0
ok(){ echo "OK  $*"; }
miss(){ echo "MISS $*" >&2; fail=1; }

echo "=== backup -> $BACKUP"
tar -czf "$BACKUP" "$F/src" "$F/index.html" "$F/dist" 2>/dev/null
ls -la "$BACKUP"

echo "=== assets"
cp -a /var/www/html/themes/mytel/images/mytel-emblem.svg "$F/public/mytel-emblem.svg"
cp -a /var/www/html/themes/mytel/images/mytel-emblem.svg "$F/public/favicon.svg"
ok "emblem + favicon"

echo "=== index.html"
python3 - "$F/index.html" <<'PY' || fail=1
import sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
t2 = t.replace('<html lang="en">', '<html lang="fa" dir="rtl">')
t2 = t2.replace('<title>OpDesk</title>', '<title>میز کار اپراتور مای‌تل</title>')
if t2 == t:
    sys.exit("no change to index.html")
open(p, "w", encoding="utf-8", newline="\n").write(t2)
print("index.html rebranded")
PY

echo "=== fa translation"
python3 - "$F/src/i18n/locales/fa/translation.json" <<'PY' || fail=1
import json, sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
n = t.count("اپدسک")
t = t.replace("اپدسک", "میز کار مای‌تل")
t = t.replace('"title": "میز کار مای‌تل"', '"title": "میز کار اپراتور مای‌تل"')
open(p, "w", encoding="utf-8", newline="\n").write(t)
json.loads(open(p, encoding="utf-8").read())
left = open(p, encoding="utf-8").read().count("اپدسک")
print("fa rebranded:", n, "leftover:", left)
if left:
    sys.exit("اپدسک still present in fa.json")
PY

echo "=== en translation"
python3 - "$F/src/i18n/locales/en/translation.json" <<'PY' || fail=1
import json, sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
n = t.count("OpDesk")
t = t.replace("OpDesk", "MyTel Operator Desk")
open(p, "w", encoding="utf-8", newline="\n").write(t)
json.loads(open(p, encoding="utf-8").read())
print("en rebranded:", n)
PY

echo "=== tsx defaults"
python3 - "$F/src" <<'PY' || fail=1
import os, sys
root = sys.argv[1]
fixes = {
 "components/PauseReasonsPanel.tsx": [("Used by OpDesk itself;", "Used by MyTel Operator Desk itself;")],
 "components/CrmConfigForm.tsx": [("Where OpDesk reaches your CRM", "Where MyTel Operator Desk reaches your CRM")],
 "components/ProfilePanel.tsx": [
   ("The language OpDesk is shown in", "The language MyTel Operator Desk is shown in"),
   ("The password you sign in to OpDesk with.", "The password you sign in to MyTel Operator Desk with.")],
 "components/MobileWakePanel.tsx": [("OpDesk pushes it, holds the call", "MyTel Operator Desk pushes it, holds the call")],
 "components/ChangePasswordModal.tsx": [("Current OpDesk password", "Current MyTel Operator Desk password")],
 "components/UsersPanel.tsx": [("For signing in to OpDesk only.", "For signing in to MyTel Operator Desk only.")],
 "components/RecordingSettings.tsx": [("but OpDesk is not the one recording", "but MyTel Operator Desk is not the one recording")],
}
for rel, subs in fixes.items():
    p = os.path.join(root, rel)
    t = open(p, encoding="utf-8").read()
    for old, new in subs:
        if new in t and old not in t:
            continue
        if t.count(old) < 1:
            sys.exit("anchor missing in " + rel + ": " + old)
        t = t.replace(old, new)
    open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("rebranded", rel)
PY

echo "=== Login.tsx logo + site link"
python3 - "$F/src/components/Login.tsx" <<'PY' || fail=1
import sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
logo_anchor = '  return (\n    <div className="login-page">\n'
logo_new = ('  return (\n    <div className="login-page">\n'
 '      <a href="https://mytel.one" target="_blank" rel="noopener" title="mytel.one"\n'
 '         style={{ position: "fixed", top: 18, left: 0, right: 0, margin: "0 auto", width: 84, display: "block" }}>\n'
 '        <img src={(import.meta.env.BASE_URL || "/").replace(/\\/$/, "") + "/mytel-emblem.svg"}\n'
 '             alt="MyTel" style={{ width: 84, height: 84, display: "block", margin: "0 auto" }} />\n'
 '      </a>\n')
foot_anchor = '        </form>\n      </Card>'
foot_new = ('        </form>\n'
 '        <a href="https://mytel.one" target="_blank" rel="noopener"\n'
 '           style={{ display: "flex", justifyContent: "center", gap: 6, marginTop: 14,\n'
 '                    fontSize: 13, textDecoration: "none", color: "inherit", opacity: 0.75 }}>\n'
 '          <img src={(import.meta.env.BASE_URL || "/").replace(/\\/$/, "") + "/mytel-emblem.svg"}\n'
 '               alt="" style={{ width: 16, height: 16 }} />\n'
 '          <span>وب‌سایت مای‌تل — mytel.one</span>\n'
 '        </a>\n'
 '      </Card>')
if logo_anchor not in t:
    sys.exit("login logo anchor missing")
t = t.replace(logo_anchor, logo_new, 1)
if foot_anchor not in t:
    sys.exit("login footer anchor missing")
t = t.replace(foot_anchor, foot_new, 1)
open(p, "w", encoding="utf-8", newline="\n").write(t)
print("Login.tsx: logo + site link applied")
PY

echo "=== App.tsx header logo"
python3 - "$F/src/App.tsx" <<'PY' || fail=1
import sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
anchor = '<div className="header-logo"><Radio size={16} /></div>'
new = ('<a className="header-logo" href="https://mytel.one" target="_blank" rel="noopener"\n'
 '           title="mytel.one" style={{ display: "flex", alignItems: "center" }}>\n'
 '            <img src={(import.meta.env.BASE_URL || "/").replace(/\\/$/, "") + "/mytel-emblem.svg"}\n'
 '                 alt="MyTel" style={{ width: 22, height: 22 }} />\n'
 '          </a>')
if anchor not in t:
    sys.exit("app header anchor missing")
t = t.replace(anchor, new, 1)
open(p, "w", encoding="utf-8", newline="\n").write(t)
print("App.tsx header logo applied")
PY

echo "=== api.ts persian error layer"
python3 - "$F/src/lib/api.ts" <<'PY' || fail=1
import sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
t = t.replace("import { getToken, removeToken } from '../auth';",
 "import { getToken, removeToken } from '../auth';\n"
 "import { CODE_FA, MSG_FA, looksEnglish } from './errors-fa';", 1)
old_from = ('export function messageFrom(body: unknown, fallback: string): string {\n'
 '  const env = (body as { error?: { message?: string } } | null | undefined)?.error;\n'
 '  if (env && typeof env.message === "string" && env.message) return env.message;\n'
 '  return fallback;\n'
 '}')
old_from2 = ('export function messageFrom(body: unknown, fallback: string): string {\n'
 '  const env = (body as { error?: { message?: string } } | null | undefined)?.error;\n'
 '  if (env && typeof env.message === \'string\' && env.message) return env.message;\n'
 '  return fallback;\n'
 '}')
new_from = ('/** The interface language of this browser session. */\n'
 'function uiLang(): string {\n'
 '  try { return localStorage.getItem("opdesk-lang") || "fa"; } catch { return "fa"; }\n'
 '}\n'
 '\n'
 '/** Persian copy for a server error envelope, or null when it does not map. */\n'
 'function persianForError(env?: { code?: unknown; message?: unknown }): string | null {\n'
 '  if (uiLang() !== "fa") return null;\n'
 '  const code = typeof env?.code === "string" ? env.code : "";\n'
 '  const message = typeof env?.message === "string" ? env.message : "";\n'
 '  if (code && CODE_FA[code]) return CODE_FA[code];\n'
 '  if (message && MSG_FA[message]) return MSG_FA[message];\n'
 '  if (code) {\n'
 '    const family = code.split(".").slice(0, 2).join(".");\n'
 '    if (CODE_FA[family]) return CODE_FA[family];\n'
 '  }\n'
 '  if (message && looksEnglish(message)) return "خطا در انجام عملیات؛ لطفاً دوباره تلاش کنید.";\n'
 '  return null;\n'
 '}\n'
 '\n'
 'export function messageFrom(body: unknown, fallback: string): string {\n'
 '  const env = (body as { error?: { code?: string; message?: string } } | null | undefined)?.error;\n'
 '  const fa = persianForError(env);\n'
 '  if (fa) return fa;\n'
 '  if (env && typeof env.message === "string" && env.message) return env.message;\n'
 '  return fallback;\n'
 '}')
if old_from in t:
    t = t.replace(old_from, new_from, 1)
elif old_from2 in t:
    t = t.replace(old_from2, new_from, 1)
else:
    sys.exit("messageFrom anchor missing")
old_of = ('export function messageOf(e: unknown, fallback: string): string {\n'
 '  if (e instanceof ApiError) return e.message;\n'
 '  if (e instanceof Error && e.message) return e.message;\n'
 '  return fallback;\n'
 '}')
new_of = ('export function messageOf(e: unknown, fallback: string): string {\n'
 '  if (uiLang() === "fa") {\n'
 '    if (e instanceof TypeError) return "ارتباط با سرور برقرار نشد؛ اتصال شبکه را بررسی کنید.";\n'
 '    if (e instanceof ApiError) {\n'
 '      const code = (e as unknown as { code?: string }).code;\n'
 '      const fa = persianForError({ code, message: e.message });\n'
 '      if (fa) return fa;\n'
 '      if (e.message && looksEnglish(e.message)) return "خطا در انجام عملیات؛ لطفاً دوباره تلاش کنید.";\n'
 '    } else if (e instanceof Error && e.message && looksEnglish(e.message)) {\n'
 '      return "خطا در انجام عملیات؛ لطفاً دوباره تلاش کنید.";\n'
 '    }\n'
 '  }\n'
 '  if (e instanceof ApiError) return e.message;\n'
 '  if (e instanceof Error && e.message) return e.message;\n'
 '  return fallback;\n'
 '}')
if old_of not in t:
    sys.exit("messageOf anchor missing")
t = t.replace(old_of, new_of, 1)
open(p, "w", encoding="utf-8", newline="\n").write(t)
print("api.ts persian layer applied")
PY

echo "=== errors-fa.ts present?"
ls -la "$F/src/lib/errors-fa.ts" 2>/dev/null || { echo "errors-fa.ts MISSING" >&2; fail=1; }

if [[ $fail -ne 0 ]]; then
  echo "PATCH-FAILED (backup kept at $BACKUP)" >&2
  exit 1
fi

echo "=== build"
export PATH=/opt/node24/bin:$PATH
cd "$F" || exit 1
npm run build 2>&1 | tail -12
rc=${PIPESTATUS[0]}
[[ $rc -eq 0 ]] || { echo "BUILD-FAILED" >&2; exit 1; }

echo "=== restart backend"
systemctl restart mytellpbx-opdesk
sleep 4
systemctl is-active mytellpbx-opdesk
ss -lnt | grep -q 8765 && echo "PORT-8765-UP"

echo "=== live spot checks"
curl -sk https://127.0.0.1/opdesk/ | grep -o '<title>[^<]*</title>'
curl -sk -o /dev/null -w 'emblem: %{http_code}\n' https://127.0.0.1/opdesk/mytel-emblem.svg
curl -sk -o /dev/null -w 'app js: %{http_code}\n' "https://127.0.0.1$(curl -sk https://127.0.0.1/opdesk/ | grep -oE '/opdesk/assets/index-[^\"]+\.js' | head -1)"
echo "REBRAND-DONE"
