(function mtDateIcons(window, document) {
    'use strict';

    if (window.MTDateIcons) {
        window.MTDateIcons.wire();
        return;
    }

    var serial = 0;

    function nextId() {
        var id;
        do {
            serial++;
            id = 'mt-date-mirror-' + serial;
        } while (document.getElementById(id));
        return id;
    }

    function fieldName(real) {
        var explicit = real.getAttribute('aria-label');
        if (explicit) return explicit;

        if (real.labels && real.labels.length) {
            var label = real.labels[0].textContent.replace(/\s+/g, ' ').trim();
            if (label) return label;
        }

        var key = String(real.id || real.name || '').toLowerCase();
        if (/start|from/.test(key)) return 'تاریخ شروع';
        if (/end|until|to_date/.test(key)) return 'تاریخ پایان';
        return 'تاریخ';
    }

    function makeIcon() {
        var ns = 'http://www.w3.org/2000/svg';
        var svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('width', '20');
        svg.setAttribute('height', '20');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('stroke-width', '1.8');
        svg.setAttribute('stroke-linecap', 'round');
        svg.setAttribute('stroke-linejoin', 'round');
        svg.setAttribute('aria-hidden', 'true');
        svg.setAttribute('focusable', 'false');

        var frame = document.createElementNS(ns, 'rect');
        frame.setAttribute('x', '3');
        frame.setAttribute('y', '5');
        frame.setAttribute('width', '18');
        frame.setAttribute('height', '16');
        frame.setAttribute('rx', '3');

        var lines = document.createElementNS(ns, 'path');
        lines.setAttribute('d', 'M7 3v4M17 3v4M3 10h18M8 14h2M14 14h2M8 17h2');

        svg.appendChild(frame);
        svg.appendChild(lines);
        return svg;
    }

    function hideStockTriggers(real) {
        /*
         * Only inspect this field's adjacent date controls.
         * Never hide another field's trigger by searching its whole cell.
         */
        var sibling = real.nextElementSibling;

        while (sibling) {
            if (
                sibling.classList.contains('mt-date-mirror') ||
                sibling.classList.contains('mt-date-icon')
            ) {
                sibling = sibling.nextElementSibling;
                continue;
            }

            if (sibling.matches('img.ui-datepicker-trigger, button.ui-datepicker-trigger')) {
                sibling.classList.add('mt-date-stock-hidden');
                sibling.hidden = true;
                sibling.setAttribute('aria-hidden', 'true');
                sibling.setAttribute('tabindex', '-1');
                sibling.style.setProperty('display', 'none', 'important');
                sibling = sibling.nextElementSibling;
                continue;
            }

            break;
        }
    }

    function wire() {
        document.querySelectorAll('input.mt-date-real').forEach(function (real) {
            var mirror = real.nextElementSibling;

            if (!mirror || !mirror.classList.contains('mt-date-mirror')) return;

            if (!mirror.id) mirror.id = nextId();

            var name = fieldName(real);
            if (
                !mirror.hasAttribute('aria-label') &&
                !mirror.hasAttribute('aria-labelledby')
            ) {
                mirror.setAttribute('aria-label', name);
            }

            mirror.disabled = real.disabled;

            var icon = mirror.nextElementSibling;

            if (!icon || !icon.classList.contains('mt-date-icon')) {
                icon = document.createElement('button');
                icon.type = 'button';
                icon.className = 'mt-date-icon';
                icon.appendChild(makeIcon());

                icon.addEventListener('click', function (event) {
                    event.preventDefault();
                    event.stopPropagation();

                    if (real.disabled || mirror.disabled || !mirror.isConnected) return;

                    /*
                     * Use exactly the mirror's click path.
                     * Calling focus() first would also invoke its focus opener.
                     */
                    mirror.click();
                });

                mirror.insertAdjacentElement('afterend', icon);
            }

            icon.disabled = real.disabled;
            icon.setAttribute('aria-label', 'انتخاب ' + name);
            icon.setAttribute('aria-controls', mirror.id);
            icon.title = 'انتخاب ' + name;

            hideStockTriggers(real);
        });
    }

    window.MTDateIcons = { wire: wire };
    wire();

})(window, document);
