#!/usr/bin/env python3
"""MyTellPBX v7.3.5 — debrand IssabelPBX → MyTellPBX in the admin console.

1) views/footer_content.php: replace IssabelPBX/issabel.org with MyTellPBX/mytel.one
2) assets/mytel/sub.js: append runtime text-node replacement for any
   remaining "IssabelPBX"/"Issabel" visible text (belt+suspenders, additive)
3) Asternic CDR Report menu subtitle "گزارش پیشرفته" via sub.js additive layer

Usage (root): python3 patch-debrand.py
Idempotent; .bak-mt backups.
"""
import pathlib
import shutil
import sys

ADMIN = pathlib.Path("/var/www/html/admin")

FOOTER_CONTENT = ADMIN / "views/footer_content.php"
SUB_JS = ADMIN / "assets/mytel/sub.js"

# ---- footer_content.php replacements ----
FC_REPLACEMENTS = [
    ('issabel.org', 'mytel.one'),
    ('IssabelPBX', 'MyTellPBX'),
]

# ---- sub.js additive block ----
DEBRAND_JS = """

/* ============ MyTellPBX v7.3.5: debrand IssabelPBX → MyTellPBX ============ */
(function () {
    'use strict';
    if (window.__mtDebrandDone) return;
    window.__mtDebrandDone = true;

    /* Replace text nodes containing IssabelPBX / Issabel brand references
       (case-insensitive). Presentation text only: script/style/textarea/
       noscript/code/pre are skipped so functional identifiers, config
       samples and editable values stay verbatim; no length cap so long
       visible paragraphs are covered too. */
    var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1, CODE: 1, PRE: 1 };
    /* reject text nodes inside skipped containers at ANY depth */
    function inSkipped(el) {
        while (el) {
            if (SKIP_TAGS[el.tagName]) return true;
            el = el.parentElement;
        }
        return false;
    }
    function acceptNode(node) {
        return inSkipped(node.parentElement) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
    }
    function debrandNode(root) {
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: acceptNode }, false);
        var node;
        while ((node = walker.nextNode())) {
            var txt = node.nodeValue;
            if (!txt) continue;
            var orig = txt;
            txt = txt.replace(/issabelpbx/gi, 'MyTellPBX');
            txt = txt.replace(/issabel/gi, 'MyTellPBX');
            if (txt !== orig) node.nodeValue = txt;
        }
    }

    /* Rewrite only external http(s) links whose HOSTNAME contains issabel
       (query strings and fragments are not part of the host); internal
       fragment/relative targets are left untouched. */
    function debrandLinks(root) {
        root.querySelectorAll('a[href]').forEach(function (a) {
            var href = a.getAttribute('href') || '';
            if (/^https?:\/\/[^\/?#]*issabel/i.test(href)) {
                a.setAttribute('href', 'https://mytel.one');
            }
        });
    }

    function debrandTitle() {
        if (document.title && /issabel/i.test(document.title)) {
            document.title = document.title.replace(/issabelpbx/gi, 'MyTellPBX').replace(/issabel/gi, 'MyTellPBX');
        }
    }

    function run() {
        debrandNode(document.body);
        debrandLinks(document.body);
        debrandTitle();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }
    /* re-run after ajax (unpoly navigations) */
    if (window.jQuery) {
        jQuery(document).on('ajaxComplete.mtDebrand', function () { setTimeout(run, 100); });
    }
    /* also observe mutations (module content loads) */
    if (window.MutationObserver) {
        var obs = new MutationObserver(function (muts) {
            for (var i = 0; i < muts.length; i++) {
                for (var j = 0; j < muts[i].addedNodes.length; j++) {
                    var n = muts[i].addedNodes[j];
                    if (n.nodeType === 1) {
                        debrandNode(n);
                        debrandLinks(n);
                    }
                }
            }
        });
        if (document.body) {
            obs.observe(document.body, { childList: true, subtree: true });
        }
    }
})();

/* ============ Asternic CDR Report subtitle "گزارش پیشرفته" ============ */
(function () {
    'use strict';
    if (window.__mtAsternicSubDone) return;
    window.__mtAsternicSubDone = true;

    function isAsternicLabel(t) {
        return /Asternic CDR Report/i.test(t) || /گزارش آسترنیک/.test(t);
    }

    function addAsternicSubtitle() {
        /* leaf menu items only: short text, no nested anchors, no subtitle yet */
        document.querySelectorAll('a, .navbar-item, .nav-item').forEach(function (el) {
            if (el.querySelector('.mt-sub') || el.querySelector('a')) return;
            var txt = (el.textContent || '').trim();
            if (!isAsternicLabel(txt) || txt.length > 40) return;
            var host = el.tagName === 'A' ? el : (el.querySelector('span, div') || el);
            var sub = document.createElement('span');
            sub.className = 'mt-sub';
            sub.style.cssText = 'display:block;font-size:10px;color:rgba(255,138,0,.92);margin-top:1px;line-height:1.3;white-space:nowrap';
            sub.textContent = 'گزارش پیشرفته';
            host.appendChild(sub);
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function(){setTimeout(addAsternicSubtitle, 300);});
    } else {
        setTimeout(addAsternicSubtitle, 300);
    }
    if (window.jQuery) {
        jQuery(document).on('ajaxComplete.mtAstSub', function(){setTimeout(addAsternicSubtitle, 200);});
    }
})();
"""

DEBRAND_MARK = "MyTellPBX v7.3.5: debrand IssabelPBX"


def patch_file(path, replacements):
    text = path.read_text(encoding="utf-8")
    changed = False
    for old, new in replacements:
        if old in text:
            if not changed:
                bak = path.with_suffix(path.suffix + ".bak-mt")
                if not bak.exists():
                    shutil.copy2(path, bak)
                    print("BACKUP", bak.name)
            text = text.replace(old, new)
            changed = True
            print("REPLACED", old, "->", new)
    if changed:
        path.write_text(text, encoding="utf-8")
    else:
        print("ALREADY", path.name)


def append_js(path, marker, block):
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print("ALREADY", path.name)
        return
    bak = path.with_suffix(path.suffix + ".bak-mt")
    if not bak.exists():
        shutil.copy2(path, bak)
        print("BACKUP", bak.name)
    path.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")
    print("APPENDED", path.name)


def restore_js(path):
    """Restore sub.js from its .bak-mt (upgrade path: drop the previously
    appended debrand block, keep everything else from the clean backup)."""
    bak = path.with_suffix(path.suffix + ".bak-mt")
    if bak.exists():
        shutil.copy2(bak, path)
        print("RESTORED", path.name, "from .bak-mt")
        return True
    return False


def main():
    for p in (FOOTER_CONTENT, SUB_JS):
        if not p.exists():
            raise SystemExit("MISSING %s" % p)

    # 1) footer_content.php
    patch_file(FOOTER_CONTENT, FC_REPLACEMENTS)

    # 2) sub.js debrand + asternic subtitle (restore-then-apply, upgrade safe)
    restore_js(SUB_JS)
    append_js(SUB_JS, DEBRAND_MARK, DEBRAND_JS)

    sys.exit(0)


if __name__ == "__main__":
    main()
