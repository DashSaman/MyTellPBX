#!/usr/bin/env python3
"""Add the isolated appearance layer, preserving the existing SIP application."""
import argparse
import os
import pathlib
import shutil
import tempfile

SOURCE = pathlib.Path(__file__).resolve().parent
START = "<!-- MyTell workspace v740 BEGIN -->"
END = "<!-- MyTell workspace v740 END -->"
PREPAINT = START + '\n<script src="theme.js?v=740"></script>\n' + END + "\n"
STYLE = START + '\n<link rel="stylesheet" href="workspace.css?v=740">\n' + END + "\n"


def transform(text):
    text = text.replace("\n" + PREPAINT, "").replace(STYLE, "")
    if START in text or END in text:
        raise ValueError("WebPhone appearance marker changed")
    if "<head>" not in text or "</head>" not in text or 'id="loginCard"' not in text:
        raise ValueError("WebPhone HTML anchors changed")
    text = text.replace("<head>", "<head>\n" + PREPAINT, 1)
    return text.replace("</head>", STYLE + "</head>", 1)


def plan(phone):
    return {
        phone / "index.html": transform((phone / "index.html").read_text(encoding="utf-8")),
        phone / "theme.js": (SOURCE / "theme.js").read_text(encoding="utf-8"),
        phone / "workspace.css": (SOURCE / "workspace.css").read_text(encoding="utf-8"),
    }


def apply(phone, check=False):
    changes = plan(phone)
    for path, text in changes.items():
        if path.exists() and path.read_text(encoding="utf-8") == text:
            print("UNCHANGED", path.name)
            continue
        if check:
            print("WOULD UPDATE", path.name)
            continue
        previous = path.stat() if path.exists() else path.parent.stat()
        if path.exists():
            backup = path.with_name(path.name + ".v740.bak-mt")
            if not backup.exists():
                shutil.copy2(str(path), str(backup))
        fd, temporary = tempfile.mkstemp(prefix=".mt-ui-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
            os.chmod(temporary, (previous.st_mode & 0o777) if path.exists() else 0o644)
            if hasattr(os, "chown"):
                os.chown(temporary, previous.st_uid, previous.st_gid)
            os.replace(temporary, str(path))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print("UPDATED", path.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone-root", type=pathlib.Path, default=pathlib.Path("/var/www/html/Phone"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    apply(args.phone_root, args.check)
