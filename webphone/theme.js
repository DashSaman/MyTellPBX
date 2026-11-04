/* Appearance only: no registration, credentials, device or call handling. */
(function () {
    'use strict';
    var root = document.documentElement;
    var theme = 'light';
    try { if (localStorage.getItem('mt-theme') === 'dark') theme = 'dark'; } catch (e) {}
    root.setAttribute('data-mt-theme', theme);
    root.style.colorScheme = theme;
    if (window.__mtPhoneTheme) return;
    window.__mtPhoneTheme = true;
    var button;

    function paint() {
        if (!button) return;
        var dark = root.getAttribute('data-mt-theme') === 'dark';
        button.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
        button.setAttribute('aria-label', button.title);
        button.setAttribute('aria-pressed', String(dark));
        button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (dark
            ? '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>'
            : '<path d="M20.6 13.2A8.6 8.6 0 0 1 10.8 3.4a8.6 8.6 0 1 0 9.8 9.8Z"/>') + '</svg>';
    }

    function init() {
        if (document.querySelector('.mt-phone-theme-toggle')) return;
        button = document.createElement('button');
        button.className = 'mt-phone-theme-toggle';
        button.type = 'button';
        button.addEventListener('click', function () {
            var next = root.getAttribute('data-mt-theme') === 'dark' ? 'light' : 'dark';
            root.setAttribute('data-mt-theme', next);
            root.style.colorScheme = next;
            try { localStorage.setItem('mt-theme', next); } catch (e) {}
        });
        document.body.appendChild(button);
        paint();
    }

    window.addEventListener('storage', function (event) {
        if (event.key === 'mt-theme' && /^(dark|light)$/.test(event.newValue)) {
            root.setAttribute('data-mt-theme', event.newValue);
            root.style.colorScheme = event.newValue;
        }
    });
    new MutationObserver(paint).observe(root, { attributes: true, attributeFilter: ['data-mt-theme'] });
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
