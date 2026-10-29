#!/usr/bin/env python3
"""MyTellPBX admin-fix: Apply Config (انجام تغییرات) root-cause repair.

Symptoms fixed:
  - clicking «انجام تغییرات» (Apply Config) left the red bar on top forever
    and never showed a success message.

Root causes (all three verified live on 192.168.8.171):
  1) modules/dashboard/page.index.php injected $.ajaxSetup({timeout:10000})
     GLOBALLY. The reload POST (handler=reload) legitimately takes 8-15s, so
     jQuery aborted it at exactly 10s (status=0) — success never ran.
  2) theme skin.css forced `display: inline-flex !important` on
     #button_reload, so jQuery .hide() could never hide the bar.
  3) no success feedback existed for the Persian UI.

Fixes:
  1) remove the global timeout; give the dashboard's own polling calls
     per-call timeout:10000 instead.
  2) pbxlib ipbx_reload(): explicit timeout:120000 — reload immune to any
     module's global ajax timeout.
  3) skin.css: #button_reload display:none by default (stock contract);
     pbxlib shows it only when the server flags reload_needed.
  4) mytel sub.js: green Persian toast «تغییرات مرکز تلفن با موفقیت
     اعمال شد» when the reload POST returns OK.

Run as root on the Issabel box (paths are absolute):
    python3 fix-apply-config.py
Idempotent; one-time backups with .bak-mt suffix.
"""
import pathlib
import shutil
import sys

BASE = pathlib.Path("/var/www/html/admin")

PATCHES = [
    (BASE / "modules/dashboard/page.index.php", [
        (
            "    $(document).ready(function(){\n"
            "    $.ajaxSetup({\n"
            "      timeout:10000\n"
            "    });\n",
            "    $(document).ready(function(){\n"
            "    /* mytellpbx fix: no global $.ajaxSetup timeout — it aborted the\n"
            "       Apply Config reload POST at 10s; per-call timeouts below */\n",
        ),
        (
            "    function updateInfo() {\n"
            "        $.ajax({\n"
            "            type: 'GET',\n",
            "    function updateInfo() {\n"
            "        $.ajax({\n"
            "            timeout: 10000,\n"
            "            type: 'GET',\n",
        ),
        (
            "    function updateStats() {\n"
            "        $.ajax({\n"
            "            type: 'GET',\n",
            "    function updateStats() {\n"
            "        $.ajax({\n"
            "            timeout: 10000,\n"
            "            type: 'GET',\n",
        ),
    ]),
    (BASE / "assets/js/pbxlib.js", [
        (
            "    $.ajax({\n"
            "        type: 'POST',\n"
            "        url: document.location.pathname,\n"
            "        data: \"handler=reload\",\n",
            "    $.ajax({\n"
            "        timeout: 120000, /* mytellpbx: reload legitimately exceeds 10s;\n"
            "                            immune to any module's global ajaxSetup timeout */\n"
            "        type: 'POST',\n"
            "        url: document.location.pathname,\n"
            "        data: \"handler=reload\",\n",
        ),
    ]),
    (BASE / "assets/mytel/skin.css", [
        # keep the pill look for all three selectors, but drop the !important
        # on display (with it, the button could never be hidden)
        (
            "    display: inline-flex !important;\n"
            "    flex-direction: column !important;",
            "    display: inline-flex;\n"
            "    flex-direction: column !important;",
        ),
    ]),
]

# appended once at end of skin.css — hides ONLY the reload button by default
# (stock contract), so .navbar-item.is-warning/.is-danger keep their display
SKIN_APPEND = ("\n/* mytellpbx: Apply Config hidden by default; pbxlib shows it "
               "when the server flags reload_needed */\n"
               "#button_reload { display: none; }\n")

TOAST = """

/* ============ MyTellPBX: Persian success toast for Apply Config ============ */
(function () {
    if (!window.jQuery) return;
    window.jQuery(document).on('ajaxComplete.mtReloadToast', function (ev, xhr, settings) {
        if (!settings || settings.type !== 'POST') return;
        var d = settings.data || '';
        if (typeof d === 'string' && d.indexOf('handler=reload') === -1) return;
        if (!xhr || xhr.status !== 200) return;
        /* success ONLY on confirmed application-level success:
           valid JSON with status === true (upstream contract); failures
           keep the upstream Swal error flow */
        var ok = false;
        try { ok = (JSON.parse(xhr.responseText) || {}).status === true; } catch (e) { ok = false; }
        if (!ok) return;
        var t = document.createElement('div');
        t.setAttribute('role', 'status');
        t.style.cssText = 'position:fixed;bottom:22px;inset-inline-start:22px;z-index:9500;'
            + 'background:#0F7B4F;color:#fff;padding:13px 22px;border-radius:12px;'
            + 'font-family:Vazirmatn,Tahoma,sans-serif;font-size:14.5px;font-weight:700;'
            + 'box-shadow:0 12px 34px rgba(6,50,32,.45);opacity:0;'
            + 'transform:translateY(12px);transition:opacity .3s ease,transform .3s ease';
        t.textContent = 'تغییرات مرکز تلفن با موفقیت اعمال شد';
        document.body.appendChild(t);
        requestAnimationFrame(function () {
            t.style.opacity = '1';
            t.style.transform = 'translateY(0)';
        });
        setTimeout(function () {
            t.style.opacity = '0';
            setTimeout(function () { if (t.parentNode) t.remove(); }, 350);
        }, 4200);
    });
})();
"""

TOAST_MARK = "Persian success toast for Apply Config"


def main():
    fail = False
    for path, pairs in PATCHES:
        if not path.exists():
            print("MISS file:", path)
            fail = True
            continue
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            if new in text:
                print("ALREADY", path.name, new.strip().splitlines()[0][:60])
                continue
            if old not in text:
                print("MISS   ", path.name, "pattern:", old.strip().splitlines()[0][:60])
                fail = True
                continue
            bak = path.with_suffix(path.suffix + ".bak-mt")
            if not bak.exists():
                shutil.copy2(path, bak)
                print("BACKUP ", bak.name)
            text = text.replace(old, new, 1)
            path.write_text(text, encoding="utf-8")
            print("PATCHED", path.name, "->", new.strip().splitlines()[0][:60])

    sub = BASE / "assets/mytel/sub.js"
    stext = sub.read_text(encoding="utf-8")
    if TOAST_MARK in stext:
        print("ALREADY sub.js toast")
    else:
        bak = sub.with_suffix(sub.suffix + ".bak-mt")
        if not bak.exists():
            shutil.copy2(sub, bak)
            print("BACKUP ", bak.name)
        sub.write_text(stext + TOAST, encoding="utf-8")
        print("PATCHED sub.js toast appended")

    skin = BASE / "assets/mytel/skin.css"
    ktext = skin.read_text(encoding="utf-8")
    if "#button_reload { display: none; }" in ktext:
        print("ALREADY skin.css button rule")
    else:
        skin.write_text(ktext.rstrip("\n") + "\n" + SKIN_APPEND.lstrip("\n"), encoding="utf-8")
        print("PATCHED skin.css button rule appended")

    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
