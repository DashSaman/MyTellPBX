#!/usr/bin/env python3
"""MyTellPBX OpDesk patch 2: Persian WebSocket notifications.

Translates the two hardcoded useWebSocket notification strings. Idempotent;
single backup (.bak-fa). Apply inside /opt/opdesk after patch-fa-enable.py.

Usage:
    python3 patch-fa-notif.py
"""
import shutil, sys, pathlib

PATH = pathlib.Path("/opt/opdesk/frontend/src/hooks/useWebSocket.ts")
PAIRS = [
    ("addNotification('Connected to server');",
     "addNotification('اتصال با سرور برقرار شد');"),
    ("addNotification('Not connected to server');",
     "addNotification('اتصال با سرور برقرار نیست');"),
]

if not PATH.exists():
    print(f"MISS {PATH}: file not found (wrong tree?)")
    sys.exit(1)

text = PATH.read_text(encoding="utf-8")
changed = False
for old, new in PAIRS:
    if new in text:
        print("ALREADY:", new[:40])
        continue
    if old not in text:
        print("MISS:", old[:50])
        continue
    if not changed:
        bak = PATH.with_suffix(PATH.suffix + ".bak-fa")
        if not bak.exists():
            shutil.copy2(PATH, bak)
            print("BACKUP", bak)
    text = text.replace(old, new, 1)
    changed = True
    print("PATCHED:", new[:44])
if changed:
    PATH.write_text(text, encoding="utf-8")
print("DONE")
