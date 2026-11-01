#!/usr/bin/env python3
"""MyTellPBX v7.2.0 part 1 — rename desk URL /opdesk/ -> /MytellDesk/.

Server-side (192.168.8.171):
  1) Apache: rewrite the proxy conf for the new path + permanent 301 from
     the old path, keeping root /api/, /ws, /sip-ws fallbacks and no-cache.
  2) Bridge module: redirect target /opdesk/#t= -> /MytellDesk/#t=.
  3) Rebuild the OpDesk frontend with --base=/MytellDesk/ and verify.
Idempotent; one-time .bak-mt backups."""
import pathlib
import shutil
import sys

CONF = pathlib.Path("/etc/httpd/conf.d/mytellpbx-opdesk.conf")
BRIDGE = pathlib.Path("/var/www/html/modules/mytellpbxopdesk/index.php")
FRONT = pathlib.Path("/opt/opdesk/frontend")

NEW_CONF = """ProxyPreserveHost On

# ── MyTellDesk (v7.2.0): primary desk location ─────────────────────────
ProxyPass        /MytellDesk/api/ http://127.0.0.1:8765/api/
ProxyPassReverse /MytellDesk/api/ http://127.0.0.1:8765/api/
ProxyPass        /MytellDesk/ws ws://127.0.0.1:8765/ws
ProxyPassReverse /MytellDesk/ws ws://127.0.0.1:8765/ws
ProxyPass        /MytellDesk/ http://127.0.0.1:8765/
ProxyPassReverse /MytellDesk/ http://127.0.0.1:8765/

# ریدایرکت دائمی مسیر قدیمی (بوک‌مارک‌ها و رفررها نمرند)
<LocationMatch "^/opdesk(/.*)?$">
  Header always set Cache-Control "no-store"
</LocationMatch>
RedirectMatch 301 "^/opdesk/?(.*)$" "/MytellDesk/$1"

# پشتیبان ریشه: فراخوانی بدون پیشوند هم به پس‌زمینه برسد
ProxyPass        /api/ http://127.0.0.1:8765/api/
ProxyPassReverse /api/ http://127.0.0.1:8765/api/
ProxyPass        /ws ws://127.0.0.1:8765/ws
ProxyPassReverse /ws ws://127.0.0.1:8765/ws

# ضدکش: هر بازدید نسخهٔ تازه بگیرد
<Location /MytellDesk/assets/>
  Header set Cache-Control "no-cache, must-revalidate"
</Location>
<Location /MytellDesk/>
  Header set Cache-Control "no-cache"
</Location>

# WebRTC SIP over WebSocket (Asterisk HTTP server)
ProxyPass /sip-ws ws://127.0.0.1:8088/ws
ProxyPassReverse /sip-ws ws://127.0.0.1:8088/ws
"""


def main():
    fail = False

    # 1) Apache conf
    bak = CONF.with_suffix(CONF.suffix + ".bak-mt")
    if not bak.exists():
        shutil.copy2(CONF, bak)
        print("BACKUP", bak.name)
    with open(str(CONF), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(NEW_CONF)
    print("CONF REWRITTEN for /MytellDesk/")

    # 2) bridge redirect target
    t = BRIDGE.read_text(encoding="utf-8")
    old = "var u = '/opdesk/#t=' + encodeURIComponent(t);"
    new = "var u = '/MytellDesk/#t=' + encodeURIComponent(t);"
    if new in t:
        print("ALREADY bridge target")
    elif old in t:
        bbak = BRIDGE.with_suffix(BRIDGE.suffix + ".bak-mt")
        if not bbak.exists():
            shutil.copy2(BRIDGE, bbak)
            print("BACKUP", bbak.name)
        with open(str(BRIDGE), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(t.replace(old, new, 1))
        print("BRIDGE -> /MytellDesk/#t=")
    else:
        print("MISS bridge redirect pattern")
        fail = True

    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
