/* Shared panel theme, independent of jQuery/Unpoly. Never changes LTR forms. */
(function () {
    'use strict';
    var root = document.documentElement;
    var theme = 'light';
    try { if (localStorage.getItem('mt-theme') === 'dark') theme = 'dark'; } catch (e) {}
    root.setAttribute('data-mt-theme', theme);
    root.style.colorScheme = theme;
    if (window.__mtAdminWorkspace) return;
    window.__mtAdminWorkspace = true;

    var sun = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>';
    var moon = '<path d="M20.6 13.2A8.6 8.6 0 0 1 10.8 3.4a8.6 8.6 0 1 0 9.8 9.8Z"/>';

    function paint() {
        var button = document.querySelector('.mt-admin-theme-toggle');
        if (!button) return;
        var dark = root.getAttribute('data-mt-theme') === 'dark';
        var label = dark ? 'تغییر به حالت روشن' : 'تغییر به حالت تاریک';
        button.setAttribute('aria-label', label);
        button.setAttribute('aria-pressed', String(dark));
        button.title = label;
        button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (dark ? sun : moon) + '</svg>';
    }

    function init() {
        /* An embedded console uses the shell's single visible control. */
        if (window.top === window.self && !document.querySelector('.mt-admin-theme-toggle')) {
            var nav = document.querySelector('.navbar-end') || document.querySelector('.navbar-brand');
            if (nav) {
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'mt-admin-theme-toggle';
                nav.appendChild(button);
            }
        }
        // Keep native table order and LTR geometry; only add a local scroll area
        // to standalone record tables which do not already have one.
        document.querySelectorAll('.content > table.table, .content #set_table').forEach(function (table) {
            if (table.closest('.mt-admin-table-scroll, .table-container, form')) return;
            var scroll = document.createElement('div');
            scroll.className = 'mt-admin-table-scroll';
            scroll.tabIndex = 0;
            scroll.setAttribute('role', 'region');
            scroll.setAttribute('aria-label', 'PBX table');
            table.parentNode.insertBefore(scroll, table);
            scroll.appendChild(table);
        });
        paint();
    }

    document.addEventListener('click', function (event) {
        if (!event.target.closest('.mt-admin-theme-toggle')) return;
        var next = root.getAttribute('data-mt-theme') === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-mt-theme', next);
        root.style.colorScheme = next;
        try { localStorage.setItem('mt-theme', next); } catch (e) {}
    });
    window.addEventListener('storage', function (event) {
        if (event.key === 'mt-theme' && /^(dark|light)$/.test(event.newValue)) {
            root.setAttribute('data-mt-theme', event.newValue);
            root.style.colorScheme = event.newValue;
        }
    });
    new MutationObserver(paint).observe(root, { attributes: true, attributeFilter: ['data-mt-theme'] });
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
    /* Native Unpoly can replace the navbar without re-running head scripts. */
    document.addEventListener('up:fragment:inserted', init);
})();
