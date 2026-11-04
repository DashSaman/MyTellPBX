/* Pre-paint theme for legacy popup/help documents and their same-origin frames. */
(function () {
    'use strict';
    var root = document.documentElement;
    var theme = 'light';
    try { if (localStorage.getItem('mt-theme') === 'dark') theme = 'dark'; } catch (e) {}

    function apply(next) {
        root.setAttribute('data-mt-theme', next);
        root.style.colorScheme = next;
        document.querySelectorAll('frame, iframe').forEach(function (frame) {
            try {
                if (!frame.contentDocument) return;
                frame.contentDocument.documentElement.setAttribute('data-mt-theme', next);
                frame.contentDocument.documentElement.style.colorScheme = next;
            } catch (e) { /* Cross-origin help is not modified. */ }
        });
    }
    apply(theme);
    document.addEventListener('load', function (event) {
        if (/^(FRAME|IFRAME)$/.test(event.target.tagName)) apply(root.getAttribute('data-mt-theme'));
    }, true);
    window.addEventListener('storage', function (event) {
        if (event.key === 'mt-theme' && /^(light|dark)$/.test(event.newValue)) apply(event.newValue);
    });
})();
