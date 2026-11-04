#!/usr/bin/env python3
"""Refresh owned UI blocks without restoring over unrelated live PHP edits.

Python 3.6 compatible. All anchors are validated before the first write.
Existing .bak-mt files are never restored or overwritten by this patcher.
"""
import argparse
import os
import pathlib
import re
import shutil
import tempfile

SOURCE = pathlib.Path(__file__).resolve().parent
SKIN_MARK = "/* ==== MyTellPBX v7.3.0 admin dark theme (marker) ==== */"
SKIN_START = "/* MyTellPBX legacy coverage v740 BEGIN */"
SKIN_END = "/* MyTellPBX legacy coverage v740 END */"
START = "/* MyTellPBX workspace v740 BEGIN */"
END = "/* MyTellPBX workspace v740 END */"
HEAD = """/* MyTellPBX workspace v740 BEGIN */
$html .= '<script src="assets/mytel/workspace.js?v=740"></script>';
/* MyTellPBX workspace v740 END */
"""
STYLE = """/* MyTellPBX workspace v740 BEGIN */
$html .= '<link rel="stylesheet" href="assets/mytel/workspace.css?v=740">';
/* MyTellPBX workspace v740 END */
"""


def remove_current(text):
    text = text.replace("\n" + HEAD, "").replace(STYLE, "")
    if START in text or END in text:
        raise ValueError("Workspace PHP marker changed; refusing to discard edits")
    return text


def strip_legacy_header(text):
    mark = "$html .= '<!-- MyTellPBX theme pre-paint (marker) -->';"
    if mark not in text:
        return text
    start = text.index(mark)
    cursor = start + len(mark)
    count = 0
    # v7.3.0 adds one statement; v7.3.2 adds two. Consume only those exact
    # PHP concatenation statements, never the space up to some later anchor.
    statement = re.compile(r"\s*\$html \.= '<script>'\r?\n(?:\.[^\n]*\r?\n)*?\. '</script>';\r?\n?")
    while count < 2:
        match = statement.match(text, cursor)
        if not match:
            break
        if count and "mt-admin-theme-toggle" not in match.group(0):
            break  # An adjacent owner script is not a theme injection.
        cursor = match.end()
        count += 1
    if not count:
        raise ValueError("Unrecognized legacy theme injection; refusing to replace PHP")
    return text[:start] + text[cursor:]


def transform_header(text):
    text = strip_legacy_header(remove_current(text))
    for anchor in ("$html .= '<head>';", "$html .= '</head>'; "):
        if anchor.rstrip() not in text:
            raise ValueError("Missing header anchor: " + anchor.rstrip())
    text = text.replace("$html .= '<head>';", "$html .= '<head>';\n" + HEAD, 1)
    text = text.replace("$html .= '</head>';", STYLE + "$html .= '</head>';", 1)
    # Local icon font is already shipped by Issabel. No CDN is required.
    text = text.replace("https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css", "/libs/font-icons/font-awesome/css/font-awesome.min.css")
    return text


def transform_footer(text):
    # v7.3.0 footer script only. Preserve all other footer content verbatim.
    pattern = r"<script>/\* MyTellPBX standalone theme toggle[^*]*\*/.*?</script>\r?\n?"
    return re.sub(pattern, "", text, flags=re.DOTALL)


def plan(admin):
    header = admin / "views/header.php"
    footer = admin / "views/footer.php"
    skin = admin / "assets/mytel/skin.css"
    for path in (header, footer, skin):
        if not path.is_file():
            raise ValueError("Missing required path: " + str(path))
    header_text = header.read_text(encoding="utf-8")
    footer_text = footer.read_text(encoding="utf-8")
    skin_text = skin.read_text(encoding="utf-8")
    dark_css = (SOURCE / "mt-admin-dark.css").read_text(encoding="utf-8").rstrip("\n")
    if SKIN_START in skin_text or SKIN_END in skin_text:
        if skin_text.count(SKIN_START) != 1 or skin_text.count(SKIN_END) != 1:
            raise ValueError("Ambiguous skin coverage markers")
        before, rest = skin_text.split(SKIN_START, 1)
        _, after = rest.split(SKIN_END, 1)
        skin_text = before + SKIN_START + "\n" + dark_css + "\n" + SKIN_END + after
    elif dark_css not in skin_text:
        # Older releases treated their marker as terminal. Never discard an
        # owner's appended CSS; retain it and add our bounded coverage block.
        skin_text = skin_text.rstrip("\n") + "\n\n" + SKIN_START + "\n" + dark_css + "\n" + SKIN_END + "\n"
    return {
        header: transform_header(header_text),
        footer: transform_footer(footer_text),
        skin: skin_text,
        admin / "assets/mytel/workspace.css": (SOURCE / "workspace.css").read_text(encoding="utf-8"),
        admin / "assets/mytel/workspace.js": (SOURCE / "workspace.js").read_text(encoding="utf-8"),
    }


def write_atomic(path, text):
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return False
    previous = path.stat() if path.exists() else path.parent.stat()
    if path.exists():
        backup = path.with_name(path.name + ".v740.bak-mt")
        if not backup.exists():
            shutil.copy2(str(path), str(backup))
    fd, temporary = tempfile.mkstemp(prefix=".mt-ui-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temporary, (previous.st_mode & 0o777) if old is not None else 0o644)
        if hasattr(os, "chown"):
            os.chown(temporary, previous.st_uid, previous.st_gid)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-root", type=pathlib.Path, default=pathlib.Path("/var/www/html/admin"))
    parser.add_argument("--check", action="store_true", help="Validate anchors without writing")
    args = parser.parse_args()
    changes = plan(args.admin_root)
    for path, text in changes.items():
        changed = not path.exists() or path.read_text(encoding="utf-8") != text
        if changed and not args.check:
            write_atomic(path, text)
        print(("WOULD UPDATE " if args.check and changed else "UPDATED " if changed else "UNCHANGED ") + str(path))


if __name__ == "__main__":
    main()
