/* Observe native SIP form POSTs. Never serializes settings or repeats a request. */
(function () {
    'use strict';
    if (window.__mtNativeSave) return;
    window.__mtNativeSave = true;

    var KEY = 'mt-pbx-save-pending-v1';
    var active = null, feedback = null;

    function display() {
        return new URLSearchParams(location.search).get('display');
    }

    function pending() {
        try {
            var value = JSON.parse(sessionStorage.getItem(KEY));
            if (value && /^[0-9a-f]{32}$/.test(value.id) &&
                typeof value.started === 'number' && Number.isFinite(value.started) &&
                value.started > 0 && value.path === '/admin/config.php' && value.display === 'sipsettings') return value;
        } catch (error) { /* Storage is optional; the parent also owns the attempt. */ }
        return null;
    }

    function remember(attempt) {
        try { sessionStorage.setItem(KEY, JSON.stringify(attempt)); }
        catch (error) { /* The native POST must still work with storage disabled. */ }
    }

    function forget(id) {
        var current = pending();
        if (!current || current.id !== id) return;
        try { sessionStorage.removeItem(KEY); } catch (error) { /* Optional storage. */ }
    }

    function eligible(form) {
        if (!form || form.tagName !== 'FORM' || form.id !== 'mainform' ||
            form.name !== 'editSip' || form.method.toLowerCase() !== 'post' ||
            form.hasAttribute('up-submit') || display() !== 'sipsettings') return false;
        var target = new URL(form.getAttribute('action') || location.href, location.href);
        return target.origin === location.origin && target.pathname === '/admin/config.php';
    }

    function finish(attempt, state, title, description) {
        forget(attempt.id);
        if (typeof feedback.finishSave === 'function') feedback.finishSave(attempt.id, state, title, description);
        else {
            feedback.render('save', state, title, description);
            feedback.busy('save', false);
            feedback.elapsed('save', attempt.started);
        }
    }

    function completePrevious() {
        var attempt = pending();
        if (!attempt) return;
        var marker = document.getElementById('mt-save-result');
        var matches = marker && marker.dataset.attempt === attempt.id &&
            marker.dataset.display === attempt.display && display() === attempt.display &&
            location.pathname === attempt.path;
        if (matches && marker.dataset.status === 'success') {
            finish(attempt, 'success', 'تنظیمات ذخیره شد', 'برای فعال شدن تغییرات، Apply را بزنید.');
        } else if (matches && marker.dataset.status === 'validation-error') {
            finish(attempt, 'error', 'تنظیمات ذخیره نشد', 'فیلدهای علامت‌دار را بررسی و اصلاح کنید.');
        } else {
            finish(attempt, 'unknown', 'نتیجهٔ ذخیره مشخص نیست', 'پاسخ معتبر این درخواست دریافت نشد. درخواست خودکار تکرار نمی‌شود؛ پیش از تلاش دوباره، مقادیر ذخیره‌شده را بررسی کنید.');
        }
    }

    function block(event) {
        event.preventDefault();
        event.stopImmediatePropagation();
    }

    function applyRunning() {
        return feedback.state('apply') === 'applying';
    }

    function observeSubmit(event) {
        var form = event.target;
        if (!eligible(form) || event.isDefaultPrevented()) return;
        if (active || applyRunning() || feedback.state('save') === 'saving') {
            block(event);
            return;
        }
        // Native requestSubmit already validates. The stock external action bar
        // uses jQuery.trigger('submit'), which otherwise bypasses HTML validity.
        if (!form.noValidate && !event.originalEvent?.submitter?.formNoValidate && !form.checkValidity()) {
            block(event);
            form.reportValidity();
            return;
        }
        var bytes = new Uint8Array(16);
        crypto.getRandomValues(bytes);
        var id = Array.from(bytes, function (byte) { return byte.toString(16).padStart(2, '0'); }).join('');
        active = {id: id, started: Date.now(), path: '/admin/config.php', display: 'sipsettings'};
        var token = form.querySelector('input[name="mt_save_attempt"]');
        if (!token) {
            token = document.createElement('input');
            token.type = 'hidden'; token.name = 'mt_save_attempt';
            form.appendChild(token);
        }
        token.value = id;
        form.setAttribute('aria-busy', 'true');
        remember(active);
        feedback.render('save', 'saving', 'در حال ذخیرهٔ تنظیمات…', 'درخواست ارسال شد؛ منتظر پاسخ سرور هستیم. ارسال دوباره لازم نیست.');
        feedback.busy('save', true);
        feedback.elapsed('save', active.started);
        if (typeof feedback.watchSave === 'function') feedback.watchSave(active, window);
        // No disabled fields, custom fetch, preventDefault or form.submit here:
        // the original native submission retains its exact successful controls.
    }

    function init(api) {
        feedback = api;
        completePrevious();
        if (!window.jQuery) return;
        // Delegation observes both native submits and the stock synthetic jQuery
        // submit. Form-level validation runs before this document-level handler.
        window.jQuery(document).on('submit.mtNativeSave', '#mainform', observeSubmit);
        window.addEventListener('mt:save-finished', function (event) {
            var result = event.detail;
            if (!active || !result || result.id !== active.id ||
                ['success', 'error', 'permission', 'unknown'].indexOf(result.state) < 0) return;
            var id = active.id;
            active = null;
            forget(id);
            var form = document.getElementById('mainform');
            if (eligible(form)) form.removeAttribute('aria-busy');
            // HTTP204 or a stalled response can leave this document alive.
            // Release only this completed attempt; retry always needs user input.
        });
        document.addEventListener('click', function (event) {
            var button = event.target.closest('#mainformsubmit, #button_reload, button[type="submit"], input[type="submit"]');
            if (!button) return;
            var form = button.form || document.getElementById('mainform');
            if (!eligible(form)) return;
            if (active || (button.id !== 'button_reload' && applyRunning())) block(event);
        }, true);
        window.addEventListener('pageshow', function (event) {
            if (!event.persisted) return;
            var previous = active;
            active = null;
            var form = document.getElementById('mainform');
            if (eligible(form)) form.removeAttribute('aria-busy');
            // Back can revive the old JavaScript heap. Only its still-pending
            // request is uncertain; a completed or newer attempt is untouched.
            var stored = pending();
            if (previous && stored && previous.id === stored.id) {
                finish(previous, 'unknown', 'نتیجهٔ ذخیره مشخص نیست', 'صفحه از تاریخچهٔ مرورگر بازگشته است. پیش از ارسال دوباره، مقادیر ذخیره‌شده را بررسی کنید.');
            }
        });
    }

    function ready() {
        if (!window.MTPBXFeedback || typeof window.MTPBXFeedback.ready !== 'function') return;
        window.MTPBXFeedback.ready().then(init).catch(function () {
            // Feedback bootstrap failure must not replace native form behavior.
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready, {once: true});
    else ready();
})();
