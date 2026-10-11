/* ============================================================
   MyTel module-page loader (mytel.one design, theme-owned)
   Replaces the inherited iframe-show-loader.js + LoadingOverlay
   combination for module (iframe) pages only. Parent-document
   overlay over the content region; sidebar/topbar stay usable.
   Loaded from _common/index.tpl BEFORE neon-custom.js.
   ============================================================ */
(function () {
    "use strict";
    var SHOW_DELAY = 150;      /* ms — no flash on fast loads */
    var SLOW_AT = 10000;       /* ms — «بیش از معمول» */
    var STUCK_AT = 30000;      /* ms — non-blocking warning */

    var overlay = null;
    var overlayText = null;
    var timers = [];
    var activeFrame = null;
    var childHookFrame = null;

    function clearTimers() {
        timers.forEach(clearTimeout);
        timers = [];
    }

    function buildOverlay(host) {
        var o = document.createElement("div");
        o.className = "mt-page-loader";
        o.setAttribute("role", "status");
        var ring = document.createElement("div");
        ring.className = "mt-page-loader-ring";
        ring.setAttribute("aria-hidden", "true");
        var label = document.createElement("div");
        label.className = "mt-page-loader-label";
        var brand = document.createElement("b");
        brand.textContent = "مای‌تل";
        var status = document.createElement("span");
        status.textContent = "در حال بارگذاری…";
        label.appendChild(brand);
        label.appendChild(status);
        o.appendChild(ring);
        o.appendChild(label);
        overlayText = status;
        host.appendChild(o);
        var content = host.querySelector("#myframe") ? host : null;
        if (content) content.setAttribute("aria-busy", "true");
        return o;
    }

    function host() {
        /* the smallest parent region that contains the module frame */
        var frame = document.getElementById("myframe");
        if (!frame) return null;
        return frame.closest("#neo-contentbox") || frame.parentElement;
    }

    function setBusy(on) {
        var frame = document.getElementById("myframe");
        var region = frame ? frame.closest("#neo-contentbox") : null;
        if (region) {
            if (on) region.setAttribute("aria-busy", "true");
            else region.removeAttribute("aria-busy");
        }
    }

    function show() {
        if (overlay || !document.body) return;
        var h = host();
        if (!h) return;
        var frame = document.getElementById("myframe");
        var rect = frame.getBoundingClientRect();
        if (rect.width < 40 || rect.height < 40) return; /* not visibly loading */
        overlay = buildOverlay(h);
    }

    function hide() {
        clearTimers();
        if (overlay) {
            overlay.remove();
            overlay = null;
            overlayText = null;
        }
        setBusy(false);
    }

    function schedule() {
        clearTimers();
        timers.push(setTimeout(function () {
            show();
            timers.push(setTimeout(function () {
                if (overlayText) overlayText.textContent =
                    "بارگذاری بیش از معمول طول کشیده است…";
            }, SLOW_AT - SHOW_DELAY));
            timers.push(setTimeout(function () {
                hide();
                showStuckNotice();
            }, STUCK_AT));
        }, SHOW_DELAY));
    }

    function showStuckNotice() {
        if (document.getElementById("mt-load-stuck")) return;
        var n = document.createElement("div");
        n.id = "mt-load-stuck";
        n.className = "mt-load-stuck";
        n.setAttribute("role", "alert");
        var text = document.createElement("span");
        text.textContent = "بارگذاری هنوز کامل نشده است؛ اتصال یا پاسخ سرور را بررسی کنید.";
        var close = document.createElement("button");
        close.type = "button";
        close.className = "mt-load-stuck-close";
        close.setAttribute("aria-label", "بستن هشدار");
        close.textContent = "×";
        close.addEventListener("click", function () { n.remove(); });
        n.appendChild(text);
        n.appendChild(close);
        var h = host();
        (h || document.body).appendChild(n);
    }

    function clearStuck() {
        var n = document.getElementById("mt-load-stuck");
        if (n) n.remove();
    }

    function onFrameLoad(frame) {
        hide();
        clearStuck();
        hookChild(frame);
    }

    function hookChild(frame) {
        /* same-origin child documents: catch internal navigation/unload so
           the overlay restarts before the new page paints */
        if (childHookFrame === frame) return;
        try {
            var win = frame.contentWindow;
            var doc = frame.contentDocument;
            if (!win || !doc) return;
            win.removeEventListener("unload", childUnload);
            win.addEventListener("unload", childUnload);
            childHookFrame = frame;
        } catch (e) { /* cross-origin child: parent overlay still covers it */ }
    }

    function childUnload() {
        schedule();
        childHookFrame = null;
        var frame = document.getElementById("myframe");
        if (frame) {
            frame.addEventListener("load", function once() {
                frame.removeEventListener("load", once);
                onFrameLoad(frame);
            });
        }
    }

    function frameInitialComplete(frame) {
        /* "complete" alone is NOT completion: a pending initial navigation
           still exposes the initial about:blank document whose readyState is
           already "complete". The initial document is distinguishable by its
           about:blank URL (and an empty body). Only a real, settled
           destination document counts as loaded. */
        try {
            var doc = frame.contentDocument;
            if (!doc) return false; /* cross-origin: assume still busy */
            if (doc.readyState !== "complete") return false;
            var url = doc.location ? doc.location.href : "";
            if (url === "about:blank") return false;
            return true;
        } catch (e) {
            return false; /* inaccessible: assume still busy */
        }
    }

    function watch(frame) {
        if (activeFrame === frame) return;
        activeFrame = frame;
        /* Establish the initial frame state FIRST: the script runs at body end,
           so an early iframe may already have finished loading its destination
           by now — its load event will never fire again. A frame whose current
           document is the initial about:blank (even with readyState complete)
           is PENDING and must schedule the overlay. */
        var initialReady = frameInitialComplete(frame);
        frame.addEventListener("load", function () {
            onFrameLoad(frame);
        });
        if (initialReady) {
            /* completed before us: nothing is pending — arm child hooks only */
            hookChild(frame);
        } else {
            schedule();
        }
        /* any later src change (attribute-driven navigation happens while the
           document is already interactive — the observer must be armed
           immediately, not after the first load) */
        new MutationObserver(function (muts) {
            muts.forEach(function (m) {
                if (m.attributeName === "src") schedule();
            });
        }).observe(frame, { attributes: true, attributeFilter: ["src"] });
    }

    function init() {
        var frame = document.getElementById("myframe");
        if (!frame) return; /* inline pages: no module overlay */
        watch(frame);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
        init();
    }
})();
