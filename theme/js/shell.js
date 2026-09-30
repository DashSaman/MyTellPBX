/* ==========================================================================
   MyTellPBX theme - shell interactivity (vanilla JS, no new dependencies)
   Dropdowns, sidebar groups, module search, dark/light toggle,
   dashboard gauge/chart recoloring, legacy Issabel asset rebranding.
   Deliberately avoids Bootstrap 5 JS so legacy Bootstrap 3 JS keeps working.
   ========================================================================== */
(function () {
    'use strict';

    /* ---- Theme (dark/light) toggle: shell-only dark, content stays light ---- */
    var THEME_KEY = 'mytellpbx-theme';
    function applyTheme(t) {
        document.documentElement.setAttribute('data-bs-theme', t);
        var icon = document.querySelector('[data-theme-icon]');
        if (icon) {
            icon.classList.remove('ti-moon', 'ti-sun');
            icon.classList.add(t === 'dark' ? 'ti-sun' : 'ti-moon');
        }
    }
    try {
        var saved = localStorage.getItem(THEME_KEY);
        applyTheme(saved === 'dark' ? 'dark' : 'light');
    } catch (e) { /* storage unavailable */ }
    var themeToggle = document.getElementById('mytell-theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function (e) {
            e.preventDefault();
            var cur = document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
            applyTheme(cur);
            try { localStorage.setItem(THEME_KEY, cur); } catch (err) { /* ignore */ }
        });
    }

    /* ---- Sidebar: collapsible menu groups ---- */
    document.querySelectorAll('.navbar-vertical a[data-menu-group]').forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            var target = document.getElementById(link.getAttribute('data-menu-group'));
            if (!target) { return; }
            var isOpen = target.classList.contains('show');
            target.classList.toggle('show', !isOpen);
            link.classList.toggle('show', !isOpen);
            link.setAttribute('aria-expanded', String(!isOpen));
        });
    });

    /* ---- Sidebar: mobile collapse (Tabler navbar-collapse) ---- */
    var mobileBtn = document.getElementById('sidebar-collapse-mobile');
    var sidebarMenu = document.getElementById('sidebar-menu');
    if (mobileBtn && sidebarMenu) {
        mobileBtn.addEventListener('click', function () {
            sidebarMenu.classList.toggle('show');
        });
    }

    /* ---- Topbar dropdowns (data-bs-toggle="dropdown") ---- */
    function closeAllDropdowns(except) {
        document.querySelectorAll('.dropdown.show').forEach(function (dd) {
            if (dd !== except) {
                dd.classList.remove('show');
                var menu = dd.querySelector('.dropdown-menu');
                if (menu) { menu.classList.remove('show'); }
                var t = dd.querySelector('[data-bs-toggle="dropdown"]');
                if (t) { t.setAttribute('aria-expanded', 'false'); }
            }
        });
    }
    document.querySelectorAll('[data-bs-toggle="dropdown"]').forEach(function (trigger) {
        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            var dd = trigger.closest('.dropdown');
            if (!dd) { return; }
            var willOpen = !dd.classList.contains('show');
            closeAllDropdowns(dd);
            dd.classList.toggle('show', willOpen);
            var menu = dd.querySelector('.dropdown-menu');
            if (menu) { menu.classList.toggle('show', willOpen); }
            trigger.setAttribute('aria-expanded', String(willOpen));
        });
    });
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.dropdown')) { closeAllDropdowns(null); }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { closeAllDropdowns(null); }
    });

    /* ---- Sidebar module search filter (desktop + mobile) ---- */
    function bindModuleFilter(inputId) {
        var input = document.getElementById(inputId);
        if (!input) { return; }
        input.addEventListener('input', function () {
            var q = input.value.trim().toLowerCase();
            var groups = document.querySelectorAll('#main-menu > li.nav-item');
            groups.forEach(function (li) {
                var items = li.querySelectorAll('.dropdown-item');
                var anyMatch = false;
                items.forEach(function (it) {
                    var text = (it.textContent || '').trim().toLowerCase();
                    var match = q === '' || text.indexOf(q) !== -1;
                    it.classList.toggle('menu-filter-hidden', !match);
                    if (match) { anyMatch = true; }
                });
                var groupBtn = li.querySelector('a[data-menu-group]');
                var groupText = groupBtn ? (groupBtn.textContent || '').trim().toLowerCase() : '';
                if (q !== '' && !anyMatch && groupText.indexOf(q) === -1) {
                    li.classList.add('menu-filter-hidden');
                } else {
                    li.classList.remove('menu-filter-hidden');
                    if (q !== '' && anyMatch) {
                        var menu = li.querySelector('.dropdown-menu');
                        if (menu) { menu.classList.add('show'); }
                    }
                }
            });
        });
        /* submit must never navigate away */
        var form = input.closest('form');
        if (form) {
            form.addEventListener('submit', function (e) { e.preventDefault(); });
        }
    }
    bindModuleFilter('search_module_issabel');
    bindModuleFilter('search_module_issabel_mobile');

    /* ======================================================================
       Dashboard widget recoloring (JustGage gauges + flot charts)
       The framework applets create their widgets on $(document).ready,
       which fires after this script, so wrapping the constructors here
       recolors every gauge/chart without touching module code.
       ====================================================================== */
    var MYTELL_GAUGE = {
        gaugeColor: '#eef2f7',
        levelColors: ['#206bc4'],
        valueFontColor: '#206bc4',
        titleFontColor: '#667382',
        labelFontColor: '#8a94a6'
    };

    function wrapJustGage() {
        if (!window.JustGage || window.JustGage.__mytellWrapped) { return; }
        var Real = window.JustGage;
        var Wrapped = function (opts) {
            opts = opts || {};
            /* colors are always forced: applets ship hard-coded legacy palettes */
            Object.keys(MYTELL_GAUGE).forEach(function (k) {
                opts[k] = MYTELL_GAUGE[k];
            });
            opts.relativeGaugeSize = ('relativeGaugeSize' in opts) ? opts.relativeGaugeSize : true;
            return new Real(opts);
        };
        Wrapped.__mytellWrapped = true;
        window.JustGage = Wrapped;
    }
    wrapJustGage();

    /* recolor gauges created before this script ran (defensive) */
    document.addEventListener('DOMContentLoaded', function () {
        wrapJustGage();
        if (window.jQuery) {
            window.jQuery('[id^="dashboard-applet-"]').each(function () {
                var g = window.jQuery(this).data('justgage');
                if (g && g.refresh && g.displayValue) { /* instance exists; colors stay applied */ }
            });
        }
    });

    /* flot charts: Tabler palette, clean lines instead of heavy fills */
    if (window.jQuery && window.jQuery.plot && !window.jQuery.plot.__mytellWrapped) {
        var MYTELL_PALETTE = ['#206bc4', '#2fb344', '#d63939', '#f76707', '#4299e1', '#a55eea'];
        var realPlot = window.jQuery.plot;
        var wrappedPlot = function (target, data, options) {
            try {
                options = options || {};
                if (!options.colors) { options.colors = MYTELL_PALETTE.slice(); }
                (data || []).forEach(function (series, i) {
                    series.color = MYTELL_PALETTE[i % MYTELL_PALETTE.length];
                    if (series.lines) {
                        series.lines.fill = false;
                        series.lines.lineWidth = 2;
                    }
                });
                if (options.series && options.series.lines) {
                    options.series.lines.fill = false;
                    options.series.lines.lineWidth = 2;
                }
                (options.yaxes || []).forEach(function (axis, i) {
                    if (axis && axis.font) {
                        axis.font.color = MYTELL_PALETTE[i % MYTELL_PALETTE.length];
                    }
                });
                options.grid = window.jQuery.extend({}, options.grid || {}, { borderColor: '#dce0e6' });
            } catch (e) { /* never break the original plot call */ }
            return realPlot(target, data, options);
        };
        wrappedPlot.__mytellWrapped = true;
        /* carry flot's plugin registry and metadata: flot 0.8 reads
           $.plot.plugins inside Plot(), so replacing the function without
           these properties breaks every chart */
        Object.keys(realPlot).forEach(function (k) { wrappedPlot[k] = realPlot[k]; });
        window.jQuery.plot = wrappedPlot;
    }

    /* ======================================================================
     * Legacy asset rebranding: swap framework-provided Issabel images
     * (loading spinners, logos) wherever they appear, whenever they appear.
     * ====================================================================== */
    function rebrandLegacyImages(root) {
        (root || document).querySelectorAll('img[src*="issabel_logo"], img[src*="tango.png"], img[src*="issabelpbx_small"]').forEach(function (img) {
            if (/logo_pattern|issabel_logo_mini/.test(img.getAttribute('src') || '')) {
                img.setAttribute('src', '/themes/mytellpbx/images/logo.svg');
            }
        });
    }
    rebrandLegacyImages(document);

    /* ---- Branding: present legacy dialogs as MyTellPBX ---- */
    /* base.js serves old dialog content; swap the name client-side only. */
    var BRAND_TITLE_RE = /Issabel( \d| 5|PBX)/g;
    var brandObserver = new MutationObserver(function () {
        ['.neo-modal-issabel-popup-content', '.neo-modal-issabel-popup-title', '.modal-content'].forEach(function (cls) {
            document.querySelectorAll(cls).forEach(function (box) {
                if (box.dataset.brandFixed === '1') { return; }
                if (!/Issabel/.test(box.textContent || '') && !/Issabel/.test(box.getAttribute('title') || '')) { return; }
                box.dataset.brandFixed = '1';
                (function walk(node) {
                    node.childNodes.forEach(function (n) {
                        if (n.nodeType === 3 && /Issabel/.test(n.nodeValue)) {
                            n.nodeValue = n.nodeValue.replace(BRAND_TITLE_RE, 'MyTell$1').replace(/Issabel/g, 'MyTellPBX');
                        } else if (n.nodeType === 1) {
                            walk(n);
                        }
                    });
                })(box);
            });
        });
        rebrandLegacyImages(document);
    });
    brandObserver.observe(document.body, { childList: true, subtree: true, characterData: false });
})();
