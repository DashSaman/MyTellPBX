/* Presentation and keyboard navigation only. Never submits a PBX form. */
(function () {
    'use strict';
    if (window.__mtWorkspace || !document.body.classList.contains('mt-body')) return;
    window.__mtWorkspace = true;

    // Class-only decoration keeps legacy form ancestry and event handlers intact.
    // Real data tables retain their columns and the template's local scroll area.
    var content = document.querySelector('.mt-module-content');
    if (content) {
        content.querySelectorAll('table.tabForm, form > table, #neo-table-header-filterrow > table, table:has(> tbody > tr.filterForm), td.filterForm > table').forEach(function (table) {
            if (!table.matches('.issabel-standard-table, .dataTable, .table') && !table.closest('#calendar_main')) table.classList.add('mt-form-layout');
        });
        content.querySelectorAll('#geoiptable, #rulestable').forEach(function (table) {
            if (!table.hasAttribute('tabindex')) table.tabIndex = 0;
        });
    }

    // The bundled webmail is same-origin but owns its own document. Style only
    // that embedded document; never inspect its form values or change direction.
    var embedded = content ? content.querySelectorAll('iframe') : [];
    function syncEmbeddedTheme(frame) {
        try {
            var url = new URL(frame.contentWindow.location.href);
            if (url.origin !== window.location.origin || !/^\/mail(?:\/|$)/.test(url.pathname)) return;
            var doc = frame.contentDocument;
            if (!doc || !doc.head || !doc.body) return;
            ['css/fonts.css', 'css/tokens.css', 'css/workspace.css'].forEach(function (asset, index) {
                var id = 'mt-embedded-style-' + index;
                if (doc.getElementById(id)) return;
                var link = doc.createElement('link');
                link.id = id;
                link.rel = 'stylesheet';
                link.href = '/themes/mytel/' + asset + '?v=740';
                doc.head.appendChild(link);
            });
            doc.body.classList.add('mt-mail-embed');
            var theme = document.documentElement.getAttribute('data-mt-theme') || 'light';
            doc.documentElement.setAttribute('data-mt-theme', theme);
            doc.documentElement.style.colorScheme = theme;
        } catch (e) { /* A cross-origin or sandboxed application stays untouched. */ }
    }
    Array.prototype.forEach.call(embedded, function (frame) {
        frame.addEventListener('load', function () { syncEmbeddedTheme(frame); });
        syncEmbeddedTheme(frame);
    });

    function syncModuleTheme() {
        var application = document.getElementById('controlPanelApplication');
        if (application) application.setAttribute('data-theme', document.documentElement.getAttribute('data-mt-theme') || 'light');
        Array.prototype.forEach.call(embedded, syncEmbeddedTheme);
    }
    syncModuleTheme();
    new MutationObserver(syncModuleTheme).observe(document.documentElement, { attributes: true, attributeFilter: ['data-mt-theme'] });

    var shell = document.querySelector('.page-container');
    var sidebar = document.getElementById('mt-sidebar');
    var burger = document.getElementById('mt-burger');
    var mq = window.matchMedia('(max-width: 991px)');
    var wasOpen = false;

    function syncDrawer() {
        if (!shell || !sidebar || !burger) return;
        var open = mq.matches && shell.classList.contains('mt-mobile-open');
        sidebar.inert = mq.matches && !open;
        burger.setAttribute('aria-expanded', String(mq.matches ? open : !shell.classList.contains('sidebar-collapsed')));
        document.body.classList.toggle('mt-drawer-open', open);
        if (open && !wasOpen) {
            var search = sidebar.querySelector('input[type="text"]');
            if (search) search.focus();
        }
        if (!open && wasOpen && sidebar.contains(document.activeElement)) burger.focus();
        wasOpen = open;
    }

    function closeDrawer() {
        if (!shell) return;
        shell.classList.remove('mt-mobile-open');
        if (burger) burger.focus();
    }

    if (shell && sidebar) {
        new MutationObserver(syncDrawer).observe(shell, { attributes: true, attributeFilter: ['class'] });
        if (mq.addEventListener) mq.addEventListener('change', syncDrawer);
        else mq.addListener(syncDrawer);
        sidebar.addEventListener('click', function (event) {
            if (!mq.matches) return;
            if (event.target.closest('.sidebar-mobile-menu a, .sidebar-collapse a')) {
                event.preventDefault();
                event.stopImmediatePropagation();
                closeDrawer();
            }
        }, true);
        document.addEventListener('keydown', function (event) {
            if (!mq.matches || !shell.classList.contains('mt-mobile-open')) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                closeDrawer();
            } else if (event.key === 'Tab') {
                var focusable = Array.prototype.filter.call(sidebar.querySelectorAll('a[href], button, input, select, [tabindex="0"]'), function (el) {
                    return !el.disabled && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
                });
                if (!focusable.length) return;
                var first = focusable[0], last = focusable[focusable.length - 1];
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
                if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
            }
        });
    }
    syncDrawer();

    var breadcrumb = document.querySelector('.mt-breadcrumb');
    var context = document.getElementById('mt-page-context');
    if (breadcrumb && context) {
        var syncContext = function () {
            var current = breadcrumb.querySelector('li.active');
            var title = current ? current.textContent.trim() : '';
            if (title && context.textContent !== title) context.textContent = title;
        };
        new MutationObserver(syncContext).observe(breadcrumb, { childList: true, subtree: true, characterData: true });
        syncContext();
    }
})();
