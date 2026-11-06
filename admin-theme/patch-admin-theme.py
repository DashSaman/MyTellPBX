#!/usr/bin/env python3
"""MyTellPBX v7.3.2 — admin frame theme patch (refresh-safe + upgrade-safe).

Strategy: always restore header.php and footer.php from their .bak-mt
pristine backups, then apply fresh. This makes upgrades from any prior
version (7.3.0/7.3.1) clean — no stale injections, no double toggles,
no PHP corruption. First run creates the .bak-mt; subsequent runs reset.

- header.php: pre-paint script + toggle button creation (DOMContentLoaded)
- footer.php: restored pristine (no injection needed — toggle is in header)
- skin.css: dark block (marker-scoped, refreshed each run)

Usage (root):  python3 patch-admin-theme.py
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
$html .= '<script>'
. "(function(){"
. "var btn=null;"
. "var SUN='<svg viewBox=\\\"0 0 24 24\\\" width=\\\"20\\\" height=\\\"20\\\" fill=\\\"none\\\" stroke=\\\"currentColor\\\" stroke-width=\\\"2\\\" stroke-linecap=\\\"round\\\" stroke-linejoin=\\\"round\\\" aria-hidden=\\\"true\\\"><circle cx=\\\"12\\\" cy=\\\"12\\\" r=\\\"4.4\\\"/><path d=\\\"M12 2.5v2.2M12 19.3v2.2M4.3 4.3l1.6 1.6M18.1 18.1l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.3 19.7l1.6-1.6M18.1 5.9l1.6-1.6\\\"/></svg>';"
. "var MOON='<svg viewBox=\\\"0 0 24 24\\\" width=\\\"20\\\" height=\\\"20\\\" fill=\\\"none\\\" stroke=\\\"currentColor\\\" stroke-width=\\\"2\\\" stroke-linecap=\\\"round\\\" stroke-linejoin=\\\"round\\\" aria-hidden=\\\"true\\\"><path d=\\\"M20.6 13.2A8.6 8.6 0 0 1 10.8 3.4a8.6 8.6 0 1 0 9.8 9.8Z\\\"/></svg>';"
. "function paint(t){if(!btn)return;var dark=t==='dark';"
. "btn.setAttribute('aria-pressed',dark?'true':'false');"
. "btn.title=dark?'تغییر به حالت روشن':'تغییر به حالت تاریک';"
. "btn.innerHTML=dark?SUN:MOON;}"
. "function init(){"
. "btn=document.createElement('button');btn.type='button';"
. "btn.className='mt-admin-theme-toggle navbar-item';"
. "btn.style.cssText='margin-inline-start:10px;align-self:center;display:inline-flex;"
. "align-items:center;justify-content:center;width:40px;height:40px;border-radius:9px;"
. "cursor:pointer;background:transparent;border:1px solid rgba(255,255,255,.25);"
. "color:rgba(255,255,255,.75);font-size:0;transition:color .12s,border-color .12s';"
. "btn.addEventListener('click',function(){"
. "var next=document.documentElement.getAttribute('data-mt-theme')==='dark'?'light':'dark';"
. "document.documentElement.setAttribute('data-mt-theme',next);"
. "document.documentElement.style.colorScheme=next;"
. "try{localStorage.setItem('mt-theme',next);}catch(e){}"
. "paint(next);"
. "try{var fr=document.querySelectorAll('iframe');"
. "for(var i=0;i<fr.length;i++){try{fr[i].contentDocument.documentElement.setAttribute('data-mt-theme',next);}catch(e){}}}catch(e){}"
. "});"
. "window.addEventListener('storage',function(ev){"
. "if(ev.key==='mt-theme'&&(ev.newValue==='dark'||ev.newValue==='light')){"
. "document.documentElement.setAttribute('data-mt-theme',ev.newValue);"
. "document.documentElement.style.colorScheme=ev.newValue;paint(ev.newValue);}});"
. "paint(document.documentElement.getAttribute('data-mt-theme'));"
. "var nav=document.querySelector('.navbar-end')||document.querySelector('.navbar')||document.body;"
. "nav.appendChild(btn);"
. "}"
. "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',init);}"
. "else{init();}"
. "})();"
. '</script>';
"""

SKIN_MARK = "/* ==== MyTellPBX v7.3.0 admin dark theme (marker) ==== */"


def restore_backup(path):
    """Restore from .bak-mt if it exists (upgrade path). Returns True if restored."""
    bak = path.with_suffix(path.suffix + ".bak-mt")
    if bak.exists():
        shutil.copy2(bak, path)
        return True
    return False


def create_backup(path):
    bak = path.with_suffix(path.suffix + ".bak-mt")
    if not bak.exists():
        shutil.copy2(path, bak)
        print("BACKUP", bak.name)


def main():
    for p in (HEADER, FOOTER, SKIN):
        if not p.exists():
            raise SystemExit("MISSING %s" % p)

    # 1) Restore pristine files (upgrade-safe: strips ALL prior injections)
    for p in (HEADER, FOOTER):
        if restore_backup(p):
            print("RESTORED", p.name, "from backup")
        else:
            create_backup(p)

    # 2) Apply header patch fresh (pre-paint + toggle)
    header = HEADER.read_text(encoding="utf-8")
    if HEAD_ANCHOR not in header:
        raise SystemExit("ANCHOR-MISS header.php")
    i = header.index(HEAD_ANCHOR) + len(HEAD_ANCHOR)
    header = header[:i] + "\n" + HEAD_INJECT + "\n" + header[i:]
    HEADER.write_text(header, encoding="utf-8")
    print("PATCHED header.php (pre-paint + toggle)")

    # 3) Apply skin.css dark block (refresh-safe)
    skin = SKIN.read_text(encoding="utf-8")
    create_backup(SKIN)
    if SKIN_MARK in skin:
        skin = skin[: skin.index(SKIN_MARK)].rstrip("\n")
    dark = DARK_CSS.read_text(encoding="utf-8")
    SKIN.write_text(skin + "\n\n" + SKIN_MARK + "\n" + dark, encoding="utf-8")
    print("APPLIED skin.css dark block")

    sys.exit(0)


if __name__ == "__main__":
    main()
