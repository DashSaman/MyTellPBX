#!/usr/bin/env python3
"""MyTellPBX v7.3.0 — dark/light theme for the IssabelPBX admin frame.

Applies three idempotent server-side changes on 192.168.8.171:
 1) views/header.php: pre-paint <script> right after <head> is emitted,
    resolving localStorage 'mt-theme' (shared with the panel shell —
    same origin) before the first paint. Embedded frames therefore load
    in the shell's theme; the standalone console keeps its own choice.
 2) views/footer.php: before </body>, injects a standalone-only toggle
    (sun/moon) into the navbar right side (window.top === window.self)
    plus a storage listener so other tabs stay in sync.
 3) assets/mytel/skin.css: appends the mt-admin-dark.css block (marked)
    — <html data-mt-theme="dark"> remaps the skin tokens and the bulma /
    framework surfaces the skin does not own.

Usage (root):  python3 patch-admin-theme.py
Idempotent (marker-scoped); one-time .bak-mt backups; nonzero exit on
missing anchors.
"""
import pathlib
import shutil
import sys

ADMIN = pathlib.Path("/var/www/html/admin")
HEADER = ADMIN / "views/header.php"
FOOTER = ADMIN / "views/footer.php"
SKIN = ADMIN / "assets/mytel/skin.css"
DARK_CSS = pathlib.Path(__file__).with_name("mt-admin-dark.css")

HEAD_ANCHOR = "$html .= '<head>';"
HEAD_MARK = "<!-- MyTellPBX theme pre-paint"
HEAD_INJECT = """$html .= '<!-- MyTellPBX theme pre-paint (marker) -->';
$html .= '<script>'
. "(function(){try{var t=localStorage.getItem('mt-theme');"
. "if(t!=='dark'&&t!=='light')t='light';"
. "document.documentElement.setAttribute('data-mt-theme',t);"
. "document.documentElement.style.colorScheme=t;}catch(e){"
. "document.documentElement.setAttribute('data-mt-theme','light');}})();"
. '</script>';
"""

FOOT_ANCHOR = "</body>"
FOOT_MARK = "/* MyTellPBX standalone theme toggle"
FOOT_INJECT = """<script>/* MyTellPBX standalone theme toggle (embedded frames take it from the shell) */
(function () {
    if (window.top !== window.self) return;
    var nav = document.querySelector('.navbar-end') || document.querySelector('.navbar') || document.body;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'mt-admin-theme-toggle navbar-item';
    btn.style.cssText = 'margin-inline-start:10px;align-self:center';
    function paint(t) {
        var dark = t === 'dark';
        btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
        btn.title = dark ? 'تغییر به حالت روشن' : 'تغییر به حالت تاریک';
        btn.innerHTML = dark ? '<i class="fa fa-sun" aria-hidden="true"></i>' : '<i class="fa fa-moon" aria-hidden="true"></i>';
    }
    btn.addEventListener('click', function () {
        var next = document.documentElement.getAttribute('data-mt-theme') === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-mt-theme', next);
        document.documentElement.style.colorScheme = next;
        try { localStorage.setItem('mt-theme', next); } catch (e) {}
        paint(next);
    });
    window.addEventListener('storage', function (ev) {
        if (ev.key === 'mt-theme' && (ev.newValue === 'dark' || ev.newValue === 'light')) {
            document.documentElement.setAttribute('data-mt-theme', ev.newValue);
            document.documentElement.style.colorScheme = ev.newValue;
            paint(ev.newValue);
        }
    });
    paint(document.documentElement.getAttribute('data-mt-theme'));
    nav.appendChild(btn);
})();
</script>
"""

SKIN_MARK = "/* ==== MyTellPBX v7.3.0 admin dark theme (marker) ==== */"


def patch_between(path, anchor, mark, inject, before_anchor):
    text = path.read_text(encoding="utf-8")
    if mark in text:
        print("ALREADY", path.name)
        return
    if anchor not in text:
        raise SystemExit("ANCHOR-MISS %s" % path)
    bak = path.with_suffix(path.suffix + ".bak-mt")
    if not bak.exists():
        shutil.copy2(path, bak)
        print("BACKUP", bak.name)
    i = text.index(anchor)
    injected = text[:i] + inject + text[i:] if before_anchor else text[: i + len(anchor)] + inject + text[i + len(anchor):]
    path.write_text(injected, encoding="utf-8")
    print("PATCHED", path.name)


def main():
    for p in (HEADER, FOOTER, SKIN):
        if not p.exists():
            raise SystemExit("MISSING %s" % p)

    # 1) pre-paint: immediately AFTER the <head> open is emitted
    patch_between(HEADER, HEAD_ANCHOR, HEAD_MARK, HEAD_INJECT, before_anchor=False)

    # 2) standalone toggle: just BEFORE </body>
    patch_between(FOOTER, FOOT_ANCHOR, FOOT_MARK, FOOT_INJECT, before_anchor=True)

    # 3) skin.css: (re)apply the dark block — the marker block is terminal,
    #    so refresh = drop old block, append the current source. Idempotent.
    skin = SKIN.read_text(encoding="utf-8")
    bak = SKIN.with_suffix(SKIN.suffix + ".bak-mt")
    if not bak.exists():
        shutil.copy2(SKIN, bak)
        print("BACKUP", bak.name)
    if SKIN_MARK in skin:
        skin = skin[: skin.index(SKIN_MARK)].rstrip("\n")
    dark = DARK_CSS.read_text(encoding="utf-8")
    SKIN.write_text(skin + "\n\n" + SKIN_MARK + "\n" + dark, encoding="utf-8")
    print("APPLIED skin.css dark block")

    sys.exit(0)


if __name__ == "__main__":
    main()
