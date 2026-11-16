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
import re
import shutil
import sys

ADMIN = pathlib.Path("/var/www/html/admin")

FOOTER_CONTENT = ADMIN / "views/footer_content.php"
SUB_JS = ADMIN / "assets/mytel/sub.js"

# ---- footer_content.php replacements ----
FC_REPLACEMENTS = [
    ('>IssabelPBX<', '>MytelPBX<'),
    ('>Issabel PBX<', '>MytelPBX<'),
    ('>MyTellPBX<', '>MytelPBX<'),
    ('>MyTell PBX<', '>MytelPBX<'),
]

# ---- sub.js additive block ----
DEBRAND_JS = r"""

/* ============ MyTellPBX v7.3.5: debrand IssabelPBX → MyTellPBX ============ */
(function () {
    'use strict';
    if (window.__mtDebrandDone) return;
    window.__mtDebrandDone = true;

    /* Only known product labels in product chrome are presentation inputs.
       Record values, option text (which can be the submitted value), editable
       notes, configuration samples and legal attribution are never rewritten. */
    var PRESERVE = 'script,style,textarea,input,select,option,pre,code,noscript,table,[role="grid"],[contenteditable],[data-mt-preserve],.legal,.license,.copyright,[rel="license"]';
    var CONTEXT = '.navbar-brand,.mt-brand,.mt-footer-brand-link,.logo a,#footer a,h1,h2,h3,h4,.moduleTitle,.neo-modal-issabel-popup-title,[data-mt-brand]';
    var PRODUCT = '(?:Issabel(?:\\s*PBX)?|MyTell\\s*PBX|Mytel\\s*PBX)';
    var LABEL = new RegExp('^(?:' + PRODUCT + '(?:\\s+(?:Advanced Settings|System Status|Notices|Statistics))?|(?:About|Welcome to|Login to)\\s+' + PRODUCT + ')$', 'i');
    function knownLabel(text) { return LABEL.test((text || '').replace(/\s+/g, ' ').trim()); }
    function context(el) { return el && !el.closest(PRESERVE) ? el.closest(CONTEXT) : null; }
    function knownContext(el) {
        var host = context(el);
        return host && (knownLabel(host.textContent) || host.matches('.navbar-brand,.mt-brand,.mt-footer-brand-link,.logo a,[data-mt-brand]'));
    }
    function fixText(text) { return text.replace(/issabel(?:\s*pbx)?|mytell\s*pbx|mytel\s+pbx/gi, 'MytelPBX'); }
    function debrandNode(root) {
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: function (node) {
            var host = context(node.parentElement);
            return host && knownLabel(host.textContent) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
        } }, false);
        var node;
        while ((node = walker.nextNode())) {
            var fixed = fixText(node.nodeValue);
            if (fixed !== node.nodeValue) node.nodeValue = fixed;
        }
    }
    function debrandLinks(root) {
        root.querySelectorAll('a[href]').forEach(function (a) {
            if (!knownContext(a) || !knownLabel(a.textContent)) return;
            try {
                var url = new URL(a.getAttribute('href'), document.baseURI);
                if (/^https?:$/.test(url.protocol) && !url.username && !url.password &&
                    (url.hostname === 'issabel.org' || url.hostname === 'www.issabel.org')) {
                    a.setAttribute('href', 'https://mytel.one');
                }
            } catch (e) { /* Leave unknown links verbatim. */ }
        });
    }
    function debrandAttributes(root) {
        root.querySelectorAll('[title],[aria-label],img[alt]').forEach(function (el) {
            if (!knownContext(el)) return;
            ['title', 'aria-label', 'alt'].forEach(function (name) {
                var value = el.getAttribute(name);
                if (value && knownLabel(value)) {
                    var fixed = fixText(value);
                    if (fixed !== value) el.setAttribute(name, fixed);
                }
            });
        });
    }
    function debrandTitle() {
        if (!knownLabel(document.title)) return;
        var fixed = fixText(document.title);
        if (fixed !== document.title) document.title = fixed;
    }

    function run() {
        debrandNode(document.body);
        debrandLinks(document.body);
        debrandAttributes(document.body);
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
        var pending = null;
        var obs = new MutationObserver(function () {
            if (pending) return;
            pending = setTimeout(function () { pending = null; run(); }, 100);
        });
        if (document.body) {
            obs.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['title', 'aria-label', 'alt', 'href'] });
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
    lines = []
    for line in text.splitlines(keepends=True):
        # These source lines are attribution, not product chrome. Preserve them.
        if not re.search(r'copyright|licen[cs]e|foundation|\bGPL\b', line, re.I):
            for old, new in replacements:
                line = line.replace(old, new)
            # A quoted bare vendor homepage is known branding. Paths, source
            # links, queries, lookalike domains and PHP identifiers stay exact.
            line = re.sub(r'''(?<=["'])https?://(?:www\.)?issabel\.org/?(?=["'])''',
                          'https://mytel.one', line, flags=re.I)
        lines.append(line)
    after = ''.join(lines)
    if after == text:
        print("ALREADY", path.name)
        return
    bak = path.with_suffix(path.suffix + ".bak-mt")
    if not bak.exists():
        shutil.copy2(path, bak)
        print("BACKUP", bak.name)
    path.write_text(after, encoding="utf-8")
    print("UPDATED product footer", path.name)


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
