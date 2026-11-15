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
import hashlib

SOURCE = pathlib.Path(__file__).resolve().parent
SKIN_MARK = "/* ==== MyTellPBX v7.3.0 admin dark theme (marker) ==== */"
SKIN_START = "/* MyTellPBX legacy coverage v740 BEGIN */"
SKIN_END = "/* MyTellPBX legacy coverage v740 END */"
START = "/* MyTellPBX workspace v740 BEGIN */"
END = "/* MyTellPBX workspace v740 END */"
HEAD = """/* MyTellPBX workspace v740 BEGIN */
$html .= '<script src="assets/mytel/workspace.js?v=760"></script>';
/* MyTellPBX workspace v740 END */
"""
STYLE = """/* MyTellPBX workspace v740 BEGIN */
$html .= '<link rel="stylesheet" href="assets/mytel/workspace.css?v=760">';
/* MyTellPBX workspace v740 END */
"""
ASSET_START = '/* MyTellPBX asset query v761 BEGIN */'
ASSET_END = '/* MyTellPBX asset query v761 END */'
ASSET_HELPER = """
/* MyTellPBX asset query v761 BEGIN */
if (!function_exists('mytell_asset_attr_v761')) {
    function mytell_asset_attr_v761($url, $version_tag) {
        $fragment = '';
        $hash = strpos($url, '#');
        if ($hash !== false) {
            $fragment = substr($url, $hash);
            $url = substr($url, 0, $hash);
        }
        $keys = array();
        $question = strpos($url, '?');
        if ($question !== false) {
            foreach (explode('&', substr($url, $question + 1)) as $part) {
                $pair = explode('=', $part, 2);
                if ($pair[0] !== '') $keys[rawurldecode($pair[0])] = true;
            }
        }
        foreach (explode('&', ltrim($version_tag, '?&') . '&mt-ui=761') as $part) {
            $pair = explode('=', $part, 2);
            $key = rawurldecode($pair[0]);
            if ($key === '' || isset($keys[$key])) continue;
            $last = substr($url, -1);
            $url .= strpos($url, '?') === false ? '?' : (($last === '?' || $last === '&') ? '' : '&');
            $url .= $part;
            $keys[$key] = true;
        }
        return htmlspecialchars($url . $fragment, ENT_QUOTES, 'UTF-8');
    }
}
/* MyTellPBX asset query v761 END */
"""


def transform_asset_url(text, key):
    """Change only the two known brand renderer expressions, never settings."""
    if text.count(ASSET_HELPER) > 1:
        raise ValueError('Duplicate branded asset helper blocks')
    text = text.replace(ASSET_HELPER, '')
    if ASSET_START in text or ASSET_END in text:
        raise ValueError('Branded asset helper block drift; preserve owner edits')
    raw = r"\$amp_conf\['" + re.escape(key) + r"'\]\s*\.\s*\$version_tag"
    if key == 'BRAND_ALT_JS':
        # Only the previously owned suffix is migrated. Unknown additions to
        # this statement need review instead of duplicate cache parameters.
        text = re.sub('(' + raw + r")\s*\.\s*'&mt-ui=752(?=\")", lambda m: m.group(1) + " . '", text)
        if re.search(raw + r"\s*\.\s*'&mt-ui=", text):
            raise ValueError('Unknown branded script cache suffix')
    expression = "mytell_asset_attr_v761($amp_conf['" + key + "'], $version_tag)"
    old_count = len(re.findall(raw, text))
    new_count = text.count(expression)
    if old_count + new_count == 0:
        if key in text or 'mytell_asset_attr_v761' in text:
            raise ValueError('Unknown branded asset rendering expression')
        return text
    if old_count + new_count != 1:
        raise ValueError('Duplicate branded asset rendering expression')
    if old_count:
        text = re.sub(raw, lambda _match: expression, text, count=1)
    if text.count('mytell_asset_attr_v761') != 1:
        raise ValueError('Unknown branded asset helper call')
    # Each view also works in isolation; the guarded function is defined only
    # once when the normal request includes both header and footer.
    if not text.startswith('<?php'):
        raise ValueError('Unknown branded asset PHP view prefix')
    return text[:5] + ASSET_HELPER + text[5:]


def remove_current(text):
    for version in ('740', '752', '760'):
        text = text.replace("\n" + HEAD.replace('?v=760', '?v=' + version), "")
        text = text.replace(STYLE.replace('?v=760', '?v=' + version), "")
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
    text = transform_asset_url(text, 'BRAND_CSS_CUSTOM')
    for anchor in ("$html .= '<head>';", "$html .= '</head>'; "):
        if anchor.rstrip() not in text:
            raise ValueError("Missing header anchor: " + anchor.rstrip())
    text = text.replace("$html .= '<head>';", "$html .= '<head>';\n" + HEAD, 1)
    text = text.replace("$html .= '</head>';", STYLE + "$html .= '</head>';", 1)
    # Local icon font is already shipped by Issabel. No CDN is required.
    text = text.replace("https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css", "/libs/font-icons/font-awesome/css/font-awesome.min.css")
    # Render-blocking external fonts delayed the containing frame's load event.
    text = re.sub(r'<link[^>]+href="https://fonts\.(?:googleapis|gstatic)\.com[^"\n]*"[^>]*>\n?', '', text)
    apply_head = "/* MyTellPBX Apply v753 BEGIN */\n$html .= '<link id=\"mt-apply-style\" rel=\"stylesheet\" href=\"assets/mytel/apply.css?v=753\">';\n$html .= '<script src=\"assets/mytel/feedback.js?v=753\"></script>';\n$html .= '<script defer src=\"assets/mytel/apply.js?v=753\"></script>';\n$html .= '<script defer src=\"assets/mytel/save.js?v=753\"></script>';\n/* MyTellPBX Apply v753 END */\n"
    old_apply_head = apply_head.replace('v753', 'v752').replace('?v=753', '?v=752')
    old_apply_head = old_apply_head.replace("$html .= '<script src=\"assets/mytel/feedback.js?v=752\"></script>';\n", '').replace("$html .= '<script defer src=\"assets/mytel/save.js?v=752\"></script>';\n", '')
    if text.count(old_apply_head) + text.count(apply_head) > 1:
        raise ValueError('Duplicate Apply UI blocks; refusing ambiguous replacement')
    text = text.replace(old_apply_head, '').replace(apply_head, '')
    if re.search(r'MyTellPBX Apply v\d+ (?:BEGIN|END)', text):
        raise ValueError('Apply UI block drift; refusing duplicate controllers')
    text = text.replace("$html .= '</head>';", apply_head + "$html .= '</head>';", 1)
    return text


def transform_footer(text):
    # v7.3.0 footer script only. Preserve all other footer content verbatim.
    pattern = r"<script>/\* MyTellPBX standalone theme toggle[^*]*\*/.*?</script>\r?\n?"
    text = re.sub(pattern, "", text, flags=re.DOTALL)
    return transform_asset_url(text, 'BRAND_ALT_JS')


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
    changes = {
        header: transform_header(header_text),
        footer: transform_footer(footer_text),
        skin: skin_text,
        admin / "assets/mytel/workspace.css": (SOURCE / "workspace.css").read_text(encoding="utf-8"),
        admin / "assets/mytel/workspace.js": (SOURCE / "workspace.js").read_text(encoding="utf-8"),
        admin / "assets/mytel/feedback.js": (SOURCE / "feedback.js").read_text(encoding="utf-8"),
        admin / "assets/mytel/save.js": (SOURCE / "save.js").read_text(encoding="utf-8"),
        admin / "assets/mytel/apply.js": (SOURCE / "apply.js").read_text(encoding="utf-8"),
        admin / "assets/mytel/apply.css": (SOURCE / "apply.css").read_text(encoding="utf-8"),
    }
    subtitle = admin / "assets/mytel/sub.js"
    if subtitle.exists():
        changes[subtitle] = transform_subtitle(subtitle.read_text(encoding="utf-8"))
    return changes


def transform_subtitle(text):
    """Remove only the known catch-all Apply overlay; retain all translations."""
    start = '    /* ============ Apply-Config overlay v3 (bulletproof dismissal) ============ */'
    end = '    /* ============ admin console footer: append mytel.one link ============ */'
    if start in text:
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError('Ambiguous legacy Apply overlay anchors')
        left, rest = text.split(start, 1)
        _, right = rest.split(end, 1)
        text = left + '    /* Apply feedback is owned by apply.js and its actual request. */\n\n' + end + right
    # Old installers appended an independent global ajaxComplete success toast.
    toast = '/* ============ MyTellPBX: Persian success toast for Apply Config ============ */'
    if toast in text:
        pattern = re.escape(toast) + r'\s*\(function \(\) \{.*?\n\}\)\(\);'
        text, count = re.subn(pattern, '', text, count=1, flags=re.DOTALL)
        if count != 1:
            raise ValueError('Unrecognized legacy Apply toast')
    return text


def write_atomic(path, text, backup_root=None):
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return False
    previous = path.stat() if path.exists() else path.parent.stat()
    if path.exists():
        if backup_root is not None:
            backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            backup = backup_root / (hashlib.sha256(str(path).encode()).hexdigest()[:20] + '-' + path.name)
        else:
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
    parser.add_argument("--backup-root", type=pathlib.Path, default=pathlib.Path('/var/backups/mytellpbx/theme-v752'))
    args = parser.parse_args()
    changes = plan(args.admin_root)
    for path, text in changes.items():
        changed = not path.exists() or path.read_text(encoding="utf-8") != text
        if changed and not args.check:
            write_atomic(path, text, args.backup_root)
        print(("WOULD UPDATE " if args.check and changed else "UPDATED " if changed else "UNCHANGED ") + str(path))


if __name__ == "__main__":
    main()
