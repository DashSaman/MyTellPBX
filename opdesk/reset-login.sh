#!/usr/bin/env bash
# mytellpbx-opdesk-passwd — reset an OpDesk user's LOGIN password (admin tool).
#
# OpDesk has TWO passwords per user:
#   1) the LOGIN password (OpDesk sign-in, bcrypt in the OpDesk DB), and
#   2) the SIP password (the Asterisk extension secret, for phones/webphone).
# Changing the SIP password does NOT change the login password. When an
# operator loses track of a login password, this tool resets it safely using
# the backend's own bcryptjs, without touching anything else.
#
# Usage:
#   mytellpbx-opdesk-passwd <username-or-extension> [new-password]
#
# Without the password argument it generates a strong random one and prints
# it once. The password is passed to node via temp files with mode 0600,
# never on a command line or in logs. After resetting, restart the backend to
# clear any login rate-limit lockout:  systemctl restart mytellpbx-opdesk
set -euo pipefail

BACKEND=/opt/opdesk/backend
NODE=/opt/node24/bin/node

if [[ $EUID -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi
command -v mysql >/dev/null || { echo "mysql client required." >&2; exit 1; }
[[ -x "$NODE" && -d "$BACKEND/node_modules" ]] || { echo "OpDesk backend not found at $BACKEND." >&2; exit 1; }

WHO="${1:?usage: mytellpbx-opdesk-passwd <username-or-extension> [new-password]}"
if [[ "$WHO" != "${WHO//[\\;\`\"\$ ]/}" ]]; then
  echo "Username/extension must not contain shell or SQL metacharacters." >&2
  exit 1
fi
M="$(grep -oP '(?<=^mysqlrootpwd=).*' /etc/issabel.conf)"

if [[ $# -ge 2 ]]; then
  PW="$2"
else
  PW="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)Aa9"
fi

D="$(mktemp -d /tmp/opdesk-pw.XXXXXX)"
chmod 700 "$D"
printf 'import { readFileSync } from "fs";\n' > "$D/hash.mjs"
printf 'import b from "%s/node_modules/bcryptjs/index.js";\n' "$BACKEND" >> "$D/hash.mjs"
printf 'const pw = readFileSync("%s/pw", "utf8").trim();\n' "$D" >> "$D/hash.mjs"
printf 'process.stdout.write(b.hashSync(pw, 10));\n' >> "$D/hash.mjs"
printf '%s' "$PW" > "$D/pw"

HASH="$("$NODE" "$D/hash.mjs")"
rm -rf -- "$D"

mysql -uroot -p"$M" OpDesk -e \
  "UPDATE users SET password_hash='${HASH}' WHERE username='${WHO}' OR extension='${WHO}';" 2>/dev/null
CHANGED=$(mysql -uroot -p"$M" OpDesk -Nse \
  "SELECT COUNT(*) FROM users WHERE (username='${WHO}' OR extension='${WHO}') AND password_hash='${HASH}';" 2>/dev/null)

if [[ "$CHANGED" == "1" ]]; then
  echo "LOGIN-PASSWORD-RESET OK for '${WHO}'"
  echo "Note: the login rate-limit lockout (if any) clears after: systemctl restart mytellpbx-opdesk"
else
  echo "No OpDesk user matched '${WHO}' (or the update failed)." >&2
  exit 1
fi
