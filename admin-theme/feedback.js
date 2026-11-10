/* Persistent feedback executes in the document that owns the card. No settings. */
(function (win) {
    'use strict';
    if (win.MTPBXFeedback) return;
    var doc = win.document, clocks = {}, saves = {}, ready;
    function node(tag, cls, text) {
        var e = doc.createElement(tag); if (cls) e.className = cls;
        if (text) e.textContent = text; return e;
    }
    function panel(kind) {
        var id = kind === 'save' ? 'mt-save-status' : 'mt-apply-status';
        var e = doc.getElementById(id); if (e) return e;
        var style = doc.getElementById('mt-apply-style');
        if (!style) { style = node('link'); style.id = 'mt-apply-style'; style.rel = 'stylesheet'; doc.head.appendChild(style); }
        style.href = '/admin/assets/mytel/apply.css?v=753';
        e = node('section', 'mt-apply-status'); e.id = id; e.dir = 'rtl'; e.dataset.kind = kind;
        e.setAttribute('aria-label', kind === 'save' ? 'وضعیت ذخیره تنظیمات' : 'وضعیت اعمال تنظیمات');
        var icon = node('span', 'mt-apply-icon'); icon.setAttribute('aria-hidden', 'true');
        var body = node('div', 'mt-apply-content'), live = node('div', 'mt-apply-live');
        live.setAttribute('role', 'status'); live.setAttribute('aria-live', 'polite'); live.setAttribute('aria-atomic', 'true');
        live.appendChild(node('strong', 'mt-apply-title')); live.appendChild(node('p', 'mt-apply-description'));
        body.appendChild(live); body.appendChild(node('span', 'mt-apply-elapsed'));
        var details = node('details', 'mt-apply-details'); details.hidden = true;
        details.appendChild(node('summary', '', 'جزئیات نتیجه')); details.appendChild(node('pre')); body.appendChild(details);
        var close = node('button', 'mt-apply-close', '×'); close.type = 'button'; close.setAttribute('aria-label', 'بستن پیام نتیجه');
        e.appendChild(icon); e.appendChild(body); e.appendChild(close); doc.body.appendChild(e); return e;
    }
    function state(kind) { var e = doc.getElementById(kind === 'save' ? 'mt-save-status' : 'mt-apply-status'); return e && e.dataset.state; }
    function isBusy(kind) { return ['applying', 'saving'].indexOf(state(kind)) >= 0; }
    function stop(kind) { if (clocks[kind]) { win.clearInterval(clocks[kind].timer); delete clocks[kind]; } }
    function render(kind, status, title, description, detail) {
        if (kind === 'apply' && status === 'applying') {
            var old = doc.getElementById('mt-save-status'); if (old && !isBusy('save')) old.remove();
        }
        if (kind === 'save' && status === 'saving') {
            var applied = doc.getElementById('mt-apply-status'); if (applied && !isBusy('apply')) applied.remove();
        }
        var e = panel(kind); e.dataset.state = status;
        if (kind === 'save') doc.documentElement.classList.toggle('mt-native-save-pending', status === 'saving');
        e.querySelector('.mt-apply-title').textContent = title;
        e.querySelector('.mt-apply-description').textContent = description || '';
        e.querySelector('.mt-apply-icon').textContent = isBusy(kind) ? '' : status === 'success' ? '✓' : '!';
        e.querySelector('.mt-apply-close').hidden = isBusy(kind);
        var details = e.querySelector('details'); details.hidden = !detail;
        details.querySelector('pre').textContent = detail || '';
        if (!isBusy(kind)) stop(kind);
        return e;
    }
    function elapsed(kind, started) {
        function tick() {
            var seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
            var e = panel(kind); e.querySelector('.mt-apply-elapsed').textContent = 'زمان سپری‌شده: ' + seconds.toLocaleString('fa-IR') + ' ثانیه';
            if (seconds >= 30 && isBusy(kind)) e.querySelector('.mt-apply-description').textContent = 'هنوز در انتظار پاسخ سرور هستیم. درخواست دوباره ارسال نمی‌شود.';
        }
        tick();
        if (isBusy(kind) && !clocks[kind]) clocks[kind] = {timer: win.setInterval(tick, 1000)};
    }
    function busy(kind, value) { if (!value) stop(kind); }
    // This handler belongs to this window, including cards left by older frames.
    doc.addEventListener('click', function (event) {
        var close = event.target.closest && event.target.closest('.mt-apply-close');
        if (!close) return;
        var e = close.closest('.mt-apply-status');
        if (e && ['applying', 'saving'].indexOf(e.dataset.state) < 0) {
            stop(e.dataset.kind || 'apply'); e.remove();
        }
    });
    function watchSave(attempt, source) {
        if (saves[attempt.id]) return;
        var frame = source.frameElement, done = false, timer;
        function finish(status, title, text) {
            if (done) return; done = true; win.clearTimeout(timer);
            if (frame) frame.removeEventListener('load', loaded);
            delete saves[attempt.id]; render('save', status, title, text);
            try { source.dispatchEvent(new source.CustomEvent('mt:save-finished', {detail:{id:attempt.id,state:status}})); } catch (error) {}
            // DOMContentLoaded may confirm persistence before fonts/images finish.
            // Keep the legacy opaque loader out until this navigation settles.
            if (frame && frame.contentDocument && frame.contentDocument.readyState !== 'complete') {
                doc.documentElement.classList.add('mt-native-save-pending');
                function settled() {
                    if (!isBusy('save')) doc.documentElement.classList.remove('mt-native-save-pending');
                    frame.removeEventListener('load', settled);
                }
                frame.addEventListener('load', settled);
                win.setTimeout(settled, 10000);
            }
            try { win.sessionStorage.removeItem('mt-pbx-save-pending-v1'); } catch (e) {}
        }
        function loaded() {
            try {
                var next = frame.contentDocument;
                var marker = next.querySelector('#mt-save-result');
                if (marker && marker.dataset.attempt === attempt.id && marker.dataset.display === attempt.display) {
                    if (marker.dataset.status === 'success') return finish('success', 'تنظیمات ذخیره شد', 'برای فعال‌شدن تنظیمات ذخیره‌شده، اعمال تنظیمات را بزنید.');
                    if (marker.dataset.status === 'validation-error') return finish('error', 'تنظیمات ذخیره نشد', 'موارد مشخص‌شده در فرم را اصلاح کنید.');
                }
                if (next.querySelector('[name="input_user"], [name="input_pass"]')) return finish('permission', 'ورود دوباره لازم است', 'نشست معتبر نیست؛ نتیجهٔ ذخیره تأیید نشد.');
                finish('unknown', 'نتیجهٔ ذخیره تأیید نشد', 'پاسخ نهایی معتبر دریافت نشد. مقادیر ذخیره‌شده را بررسی کنید؛ درخواست تکرار نمی‌شود.');
            } catch (e) { finish('unknown', 'نتیجهٔ ذخیره تأیید نشد', 'پاسخ صفحه قابل بررسی نیست؛ پیش از ارسال دوباره وضعیت تنظیمات را بررسی کنید.'); }
        }
        saves[attempt.id] = finish;
        if (frame) frame.addEventListener('load', loaded);
        timer = win.setTimeout(function () { finish('unknown', 'نتیجهٔ ذخیره هنوز مشخص نیست', 'پاسخ نهایی دریافت نشد؛ درخواست به‌طور خودکار تکرار نمی‌شود.'); }, 120000);
    }
    function finishSave(id, status, title, text) {
        if (saves[id]) saves[id](status, title, text);
        else render('save', status, title, text);
    }
    var api = {panel: panel, render: render, busy: busy, elapsed: elapsed, state: state, isBusy: isBusy, watchSave: watchSave, finishSave: finishSave,
        ready: function () { return ready; }};
    var existingStyle = doc.getElementById('mt-apply-style');
    if (existingStyle) existingStyle.href = '/admin/assets/mytel/apply.css?v=753';
    win.MTPBXFeedback = api;
    ready = win.Promise.resolve(api);
    try {
        if (win.parent !== win && win.parent.location.origin === win.location.origin) {
            var parent = win.parent;
            if (parent.MTPBXFeedback) ready = win.Promise.resolve(parent.MTPBXFeedback);
            else ready = new win.Promise(function (resolve) {
                var script = parent.document.getElementById('mt-pbx-feedback-script');
                function loaded() { resolve(parent.MTPBXFeedback || api); }
                win.setTimeout(loaded, 5000);
                if (!script) {
                    script = parent.document.createElement('script'); script.id = 'mt-pbx-feedback-script';
                    script.src = '/admin/assets/mytel/feedback.js?v=753';
                    script.addEventListener('load', loaded, {once:true});
                    script.addEventListener('error', function () { resolve(api); }, {once:true});
                    parent.document.head.appendChild(script);
                } else { script.addEventListener('load', loaded, {once:true}); }
            });
        }
    } catch (error) { /* Standalone/popover retains its own document renderer. */ }
})(window);
