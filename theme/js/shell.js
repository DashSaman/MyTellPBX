/* ==========================================================================
   MyTellPBX theme - shell interactivity (vanilla JS, no new dependencies)
   Dropdowns, sidebar groups, module search, dark/light toggle.
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

    /* ---- Branding: present the legacy About dialog as MyTellPBX ---- */
    /* base.js serves the old dialog content; swap the name client-side only. */
    var brandObserver = new MutationObserver(function () {
        ['neo-modal-issabel-popup-content', 'modal-content'].forEach(function (cls) {
            document.querySelectorAll('.' + cls).forEach(function (box) {
                if (box.dataset.brandFixed === '1') { return; }
                if (!/Issabel/.test(box.textContent || '')) { return; }
                box.dataset.brandFixed = '1';
                (function walk(node) {
                    node.childNodes.forEach(function (n) {
                        if (n.nodeType === 3 && /Issabel/.test(n.nodeValue)) {
                            n.nodeValue = n.nodeValue.replace(/Issabel( \d| 5|PBX)/g, 'MyTell$1').replace(/Issabel/g, 'MyTellPBX');
                        } else if (n.nodeType === 1) {
                            walk(n);
                        }
                    });
                })(box);
            });
        });
    });
    brandObserver.observe(document.body, { childList: true, subtree: true, characterData: false });
})();
