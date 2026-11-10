/* Request-owned Apply feedback. No catch-all XHR hooks or page-wide lock. */
(function () {
    'use strict';
    var active = false, confirming = false, started = 0, timer = null;
    var panel = null, host = document, disabled = [];
    var STORAGE = 'mt-pbx-apply-pending';
    var TIMEOUT = 120000;

    function remember(value) {
        try {
            if (value) sessionStorage.setItem(STORAGE, String(value));
            else sessionStorage.removeItem(STORAGE);
        } catch (e) { /* Private storage may be unavailable. */ }
    }

    function node(tag, name, text) {
        var element = host.createElement(tag);
        if (name) element.className = name;
        if (text) element.textContent = text;
        return element;
    }

    function ensurePanel() {
        try {
            if (window.parent !== window && window.parent.location.origin === location.origin) host = window.parent.document;
        } catch (e) { host = document; }
        var previous = host.getElementById('mt-apply-status');
        if (panel && previous === panel) return panel;
        if (previous) previous.remove();
        if (!host.getElementById('mt-apply-style')) {
            var style = node('link');
            style.id = 'mt-apply-style'; style.rel = 'stylesheet';
            style.href = '/admin/assets/mytel/apply.css?v=752';
            host.head.appendChild(style);
        }
        panel = node('section', 'mt-apply-status');
        panel.id = 'mt-apply-status'; panel.dir = 'rtl';
        panel.setAttribute('aria-label', 'وضعیت اعمال تنظیمات');
        var icon = node('span', 'mt-apply-icon'); icon.setAttribute('aria-hidden', 'true');
        var content = node('div', 'mt-apply-content');
        var live = node('div', 'mt-apply-live');
        live.setAttribute('role', 'status'); live.setAttribute('aria-live', 'polite'); live.setAttribute('aria-atomic', 'true');
        live.appendChild(node('strong', 'mt-apply-title'));
        live.appendChild(node('p', 'mt-apply-description'));
        content.appendChild(live);
        var elapsed = node('span', 'mt-apply-elapsed'); elapsed.setAttribute('aria-hidden', 'true');
        content.appendChild(elapsed);
        var details = node('details', 'mt-apply-details');
        details.appendChild(node('summary', '', 'جزئیات نتیجه'));
        details.appendChild(node('pre')); details.hidden = true;
        content.appendChild(details);
        var close = node('button', 'mt-apply-close', '×');
        close.type = 'button'; close.setAttribute('aria-label', 'بستن پیام نتیجه');
        close.addEventListener('click', function () { if (!active) panel.remove(); });
        panel.appendChild(icon); panel.appendChild(content); panel.appendChild(close);
        host.body.appendChild(panel);
        return panel;
    }

    function render(state, title, description, detail) {
        var element = ensurePanel();
        element.dataset.state = state;
        element.querySelector('.mt-apply-title').textContent = title;
        element.querySelector('.mt-apply-description').textContent = description;
        element.querySelector('.mt-apply-icon').textContent = state === 'applying' ? '' : state === 'success' ? '✓' : '!';
        element.querySelector('.mt-apply-close').hidden = state === 'applying';
        var more = element.querySelector('details');
        more.hidden = !detail;
        more.querySelector('pre').textContent = detail || '';
        if (!detail) more.open = false;
    }

    function elapsed() {
        if (!panel) return;
        var seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
        panel.querySelector('.mt-apply-elapsed').textContent = 'زمان سپری‌شده: ' + seconds.toLocaleString('fa-IR') + ' ثانیه';
        if (seconds >= 30 && panel.dataset.state === 'applying') {
            var description = panel.querySelector('.mt-apply-description');
            var message = 'هنوز در انتظار پاسخ سرور هستیم. درخواست دوباره ارسال نمی‌شود.';
            if (description.textContent !== message) description.textContent = message;
        }
    }

    function setBusy(busy) {
        var button = document.getElementById('button_reload');
        if (button) {
            button.classList.toggle('mt-apply-busy', busy);
            button.classList.remove('is-loading');
            button.setAttribute('aria-disabled', String(busy));
            button.setAttribute('aria-busy', String(busy));
        }
        if (busy) {
            // Advanced Settings saves on change, without a form submit.
            // Freeze editable controls too, preserving their previous state.
            document.querySelectorAll('input:not([type="hidden"]), select, textarea, button[type="submit"], #mainformsubmit').forEach(function (control) {
                if (!disabled.some(function (item) { return item.control === control; })) disabled.push({ control: control, value: control.disabled });
                control.disabled = true;
            });
        } else {
            disabled.forEach(function (item) { item.control.disabled = item.value; });
            disabled = [];
        }
    }

    function detailText(data) {
        return [data.message, data.retrieve_conf].filter(function (text) { return typeof text === 'string'; }).join('\n\n').slice(0, 12000);
    }

    function unknown(message) {
        render('unknown', 'نتیجهٔ اعمال تنظیمات هنوز مشخص نیست', message ||
            'پاسخ نهایی دریافت نشد؛ ممکن است سرور همچنان در حال کار باشد. پیش از ارسال دوباره، وضعیت مرکز تلفن را بررسی کنید.');
    }

    function apply() {
        if (active) return;
        active = true; started = Date.now(); remember(started);
        setBusy(true);
        render('applying', 'در حال اعمال تنظیمات…', 'تنظیمات ذخیره‌شده در حال ارسال به مرکز تلفن است. می‌توانید صفحه را بخوانید و پیمایش کنید.');
        elapsed(); timer = window.setInterval(elapsed, 1000);
        function complete() {
            active = false; confirming = false;
            clearInterval(timer); timer = null; setBusy(false);
        }
        try {
            window.jQuery.ajax({
                type: 'POST', url: location.pathname, data: { handler: 'reload' },
                dataType: 'json', timeout: TIMEOUT, global: false,
                success: function (data) {
                    if (!data || typeof data.status !== 'boolean') { unknown(); return; }
                    remember(null);
                    if (!data.status) {
                        window.ipbx.conf.reload_needed = true;
                        window.toggle_reload_button('show');
                        render('error', 'تنظیمات اعمال نشد', 'تغییرات همچنان در انتظار اعمال هستند. جزئیات خطا را بررسی کنید.', detailText(data));
                        return;
                    }
                    window.ipbx.conf.reload_needed = false;
                    if (window.ipbx.conf.DEVELRELOAD !== 'true' && window.ipbx.conf.DEVELRELOAD !== true) window.toggle_reload_button('hide');
                    var warnings = Number(data.num_errors) > 0;
                    render(warnings ? 'warning' : 'success', warnings ? 'تنظیمات با هشدار اعمال شد' : 'تنظیمات با موفقیت اعمال شد',
                        warnings ? 'سرور اعمال تنظیمات را تأیید کرد، اما نتیجه نیاز به بررسی دارد.' : 'مرکز تلفن اعمال تغییرات ذخیره‌شده را تأیید کرد.', warnings ? detailText(data) : '');
                    elapsed();
                },
                error: function (xhr, status) {
                    window.ipbx.conf.reload_needed = true;
                    window.toggle_reload_button('show');
                    var loginPage = /name=["'](?:input_user|submit_login)["']/.test(xhr.responseText || '');
                    if (xhr.status === 401 || xhr.status === 403 || loginPage) {
                        remember(null);
                        render('permission', 'ورود دوباره لازم است', 'نشست شما معتبر نیست یا مجوز این عملیات را ندارید. صفحهٔ ورود را باز کنید و پس از ورود، وضعیت تنظیمات را بررسی کنید.');
                    } else if (xhr.status === 409) {
                        remember(null);
                        render('warning', 'یک درخواست دیگر در حال اجراست', 'برای جلوگیری از تداخل، این درخواست اجرا نشد. پایان عملیات قبلی را بررسی کنید.');
                    } else {
                        unknown(status === 'timeout' ? 'زمان انتظار به پایان رسید؛ این به معنی توقف عملیات در سرور نیست. درخواست به‌طور خودکار تکرار نمی‌شود.' : undefined);
                    }
                },
                complete: complete
            });
        } catch (error) {
            unknown('ارسال یا پردازش درخواست کامل نشد. وضعیت مرکز تلفن را پیش از تلاش دوباره بررسی کنید.');
            complete();
        }
    }

    function init() {
        if (!window.jQuery || !window.ipbx) return;
        window.ipbx_reload = apply;
        window.ipbx_reload_confirm = function () {
            if (active || confirming) return;
            var setting = window.ipbx.conf.RELOADCONFIRM;
            if (setting !== true && setting !== 1 && setting !== 'true' && setting !== '1') return apply();
            confirming = true;
            Promise.resolve(window.sweet_confirm(window.ipbx.msg.framework.confirmreload)).then(function (response) {
                confirming = false;
                if (response === 1 || response === true) apply();
            }, function () { confirming = false; });
        };
        if (window.__mtApplyReady) { if (active) setBusy(true); return; }
        window.__mtApplyReady = true;
        new MutationObserver(function (changes) {
            if (active && changes.some(function (change) { return change.addedNodes.length; })) setBusy(true);
        }).observe(document.body, {childList:true, subtree:true});
        document.addEventListener('submit', function (event) {
            if (active) { event.preventDefault(); event.stopImmediatePropagation(); }
        }, true);
        document.addEventListener('click', function (event) {
            if (active && event.target.closest('#button_reload, #mainformsubmit, #action-bar a, #action-bar button')) {
                event.preventDefault(); event.stopImmediatePropagation();
            }
        }, true);
        document.addEventListener('keydown', function (event) {
            if (event.target.id === 'button_reload' && event.key === ' ') {
                event.preventDefault(); window.ipbx_reload_confirm();
            }
        });
        window.addEventListener('beforeunload', function (event) {
            if (active) { event.preventDefault(); event.returnValue = ''; }
        });
        var button = document.getElementById('button_reload');
        if (button) { button.setAttribute('role', 'button'); button.setAttribute('aria-label', 'اعمال تنظیمات ذخیره‌شده'); }
        try {
            if (sessionStorage.getItem(STORAGE)) unknown('پاسخ نهایی درخواست قبلی در این مرورگر ثبت نشده است. پیش از اعمال دوباره، وضعیت مرکز تلفن را بررسی کنید.');
        } catch (e) { /* Storage is optional. */ }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
    document.addEventListener('up:fragment:inserted', init);
})();
