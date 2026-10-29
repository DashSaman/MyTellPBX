#!/usr/bin/env python3
"""MyTellPBX OpDesk patch 1: enable fa in supported languages + make it default.

Apply inside /opt/opdesk (pinned OpDesk source). Idempotent; backs up each
target once (.bak-fa). Pairs with fa-translation.json (copied over the
stock locales/fa/translation.json) and patch-fa-notif.py.

Usage:
    python3 patch-fa-enable.py
"""
import shutil, sys, pathlib

BASE = pathlib.Path("/opt/opdesk/frontend/src")
TARGETS = {
    BASE / "i18n/index.ts": [
        (
            "const SUPPORTED_LANGUAGES = ['en', 'ar', 'es', 'pt', 'uk'] as const;",
            "const SUPPORTED_LANGUAGES = ['fa', 'en', 'ar', 'es', 'pt', 'uk'] as const;",
        ),
        (
            "  : 'en';",
            "  : 'fa';",
        ),
    ],
    BASE / "components/ProfilePanel.tsx": [
        (
            "const LANGUAGE_OPTIONS = ['en', 'ar', 'es', 'pt', 'uk'] as const;",
            "const LANGUAGE_OPTIONS = ['fa', 'en', 'ar', 'es', 'pt', 'uk'] as const;",
        ),
    ],
}

fail = False
for path, pairs in TARGETS.items():
    if not path.exists():
        print(f"MISS   {path}: file not found (wrong tree?)")
        fail = True
        continue
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if new in text:
            print(f"ALREADY {path.name}: {new[:50]}")
            continue
        if old not in text:
            print(f"MISS   {path.name}: pattern not found: {old[:60]}")
            fail = True
            continue
        bak = path.with_suffix(path.suffix + ".bak-fa")
        if not bak.exists():
            shutil.copy2(path, bak)
            print(f"BACKUP {bak}")
        text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")
        print(f"PATCHED {path.name}: {old[:40]} -> {new[:40]}")

sys.exit(1 if fail else 0)
