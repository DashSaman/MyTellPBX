/* MyTel brand + Persian localization layer for the IssabelPBX admin console.
   Presentation only: text-node swaps (TreeWalker), attribute placeholders,
   document direction. No innerHTML blanket replacement, no value/name/id changes. */
(function () {
    "use strict";

    /* ---------- true RTL ---------- */
    var doc = document.documentElement;
    doc.setAttribute("dir", "rtl");
    doc.setAttribute("lang", "fa");

    /* ---------- brand (run first) ---------- */
    var BRAND = {
        "IssabelPBX": "MyTel PBX", "Issabel PBX": "MyTel PBX",
        "Issabel Foundation": "MyTel", "FreePBX": "MyTel PBX",
        "Issabel": "MyTel", "Elastix": "MyTel"
    };

    /* ---------- Persian UI dictionary (word-boundary, longest first) ----------
       Technical terms intentionally kept: PBX, SIP, PJSIP, RTP, NAT, TLS,
       Caller ID, IVR, DISA, CPU, Swap, codec names, Asterisk contexts... */
    var FA = {
        /* top navigation */
        "Apply Config": "اعمال تنظیمات",
        "Applications": "برنامه‌ها",
        "Connectivity": "ارتباطات",
        "Reports": "گزارش‌ها",
        "Settings": "تنظیمات",
        "Other": "سایر",
        "Admin": "مدیریت",
        /* dashboard panels */
        "MyTel PBX System Status": "وضعیت مرکز تلفن MyTel",
        "MyTel PBX Notices": "اعلان‌های مرکز تلفن MyTel",
        "MyTel PBX Statistics": "آمار مرکز تلفن MyTel",
        "System Statistics": "آمار سیستم",
        "System Status": "وضعیت سیستم",
        "PBX Notices": "اعلان‌های مرکز تلفن",
        "PBX Statistics": "آمار مرکز تلفن",
        "Processor": "پردازنده",
        "Load Average": "میانگین بار سیستم",
        "Memory": "حافظه",
        "Disks": "دیسک‌ها",
        "Total active calls": "مجموع تماس‌های فعال",
        "Internal calls": "تماس‌های داخلی",
        "External calls": "تماس‌های خارجی",
        "Total active channels": "مجموع کانال‌های فعال",
        "Total active channels:": "مجموع کانال‌های فعال:",
        "show all": "نمایش همه",
        /* notices / errors (technical id preserved in parentheses) */
        "retrieve_conf failed, config not applied": "خطا در دریافت پیکربندی؛ تنظیمات اعمال نشد (retrieve_conf failed)",
        "Symlink Conflict Resolved": "تداخل Symlink برطرف شد.",
        "No email address for online update checks": "برای بررسی به‌روزرسانی‌ها، آدرس ایمیل ثبت نشده است.",
        "Please update your notifications email address": "آدرس ایمیل اعلان‌ها را در تنظیمات وارد کنید.",
        /* common actions */
        "Apply Changes": "اعمال تغییرات",
        "Save Changes": "ذخیره تغییرات",
        "Submit": "ذخیره",
        "Delete": "حذف",
        "Cancel": "انصراف",
        "Reset": "بازنشانی",
        "Edit": "ویرایش",
        "Back": "بازگشت",
        "Search": "جستجو",
        "Refresh": "بازخوانی",
        "Download": "دریافت",
        "Upload": "بارگذاری",
        "Close": "بستن",
        "Install": "نصب",
        "Uninstall": "حذف نصب",
        "Enable": "فعال‌سازی",
        "Disable": "غیرفعال‌سازی",
        "Continue": "ادامه",
        "Duplicate": "کپی",
        "Quick Create Extension": "ایجاد سریع داخلی",
        /* rnav / module names */
        "Batch of Extensions": "ایجاد گروهی داخلی",
        "Asterisk SIP Settings": "تنظیمات SIP آستریس",
        "SIP Settings": "تنظیمات SIP",
        "General Settings": "تنظیمات عمومی",
        "Advanced Settings": "تنظیمات پیشرفته",
        "Module Admin": "مدیریت ماژول‌ها",
        "Inbound Routes": "مسیرهای ورودی",
        "Outbound Routes": "مسیرهای خروجی",
        "Ring Groups": "گروه‌های زنگ",
        "Time Conditions": "شرایط زمانی",
        "Time Groups": "گروه‌های زمانی",
        "Call Recording": "ضبط تماس",
        "System Recordings": "فایل‌های صوتی سیستم",
        "Music on Hold": "موسیقی انتظار",
        "Feature Codes": "کدهای ویژه",
        "Feature Code Admin": "مدیریت کدهای ویژه",
        "Parking Lot": "پارک تماس",
        "Caller ID Lookup": "جستجوی Caller ID",
        "Blacklist": "لیست سیاه",
        "Phonebook Directory": "دفترچه تلفن",
        "Directory": "دفترچه تلفن",
        "Announcements": "اطلاعیه‌های صوتی",
        "Conferences": "کنفرانس‌ها",
        "Queues": "صف‌های تماس",
        "Extensions": "داخلی‌ها",
        "Trunks": "ترانک‌ها",
        "Recordings": "ضبط‌ها",
        "Voicemail": "صندوق صوتی",
        "Users": "کاربران",
        "Dashboard": "میز کار",
        "Extension": "داخلی",
        "Trunk": "ترانک",
        "Queue": "صف تماس",
        "Ring Group": "گروه زنگ",
        "Announcement": "اطلاعیه صوتی",
        "Conference": "کنفرانس",
        /* more nav dropdown items */
        "CDR Reports": "گزارش CDR",
        "CSV Reports": "گزارش‌های CSV",
        "Asterisk Log Files": "فایل‌های لاگ آستریس",
        "Call Event Logging": "ثبت رخدادهای تماس",
        "Asterisk Info": "اطلاعات آستریس",
        "File Backup": "پشتیبان فایل‌ها",
        "User Management": "مدیریت کاربران",
        "Voicemail Admin": "مدیریت صندوق صوتی",
        "Speed Dial": "شماره‌گیری سریع",
        "Paging and Intercom": "پیجینگ و آی‌کام",
        "Print Call Logs": "چاپ گزارش تماس‌ها",
        "Call Forward": "گردش تماس",
        "Follow Me": "پیگیری تماس (Follow Me)",
        "Day Night": "روز/شب",
        "Do Not Disturb": "مزاحم نشوید (DND)",
        "Concurrency": "تماس‌های همزمان",
        "Contact Manager": "مدیریت مخاطبین",
        "Notices": "اعلان‌ها",
        "Statistics": "آمار",
        "Status": "وضعیت",
        "Advanced": "پیشرفته",
        "Basic": "پایه",
        "Uptime:": "مدت کار:",
        "Password": "گذرواژه",
        /* form words */
        "Destination": "مقصد",
        "Dial Patterns": "الگوهای شماره‌گیری",
        "Description": "شرح",
        "Enabled": "فعال",
        "Disabled": "غیرفعال",
        "Password": "گذرواژه",
        "Display Name": "نام نمایشی",
        "Secret": "گذرواژه (Secret)",
        "Add": "افزودن",
        "Delete": "حذف",
        "Save": "ذخیره"
    };

    /* dynamic sentence patterns */
    var PATTERNS = [
        [/There are (\d+) modules available for online upgrades?/g, function (m, n) {
            return n + " ماژول برای به‌روزرسانی در دسترس است.";
        }],
        [/(\d+) modules may be upgraded/g, function (m, n) { return n + " ماژول قابل به‌روزرسانی است"; }],
        [/You have (\d+) new message/g, function (m, n) { return n + " پیام جدید دارید"; }]
    ];

    var sortedKeys = function (obj) {
        return Object.keys(obj).sort(function (a, b) { return b.length - a.length; });
    };

    function swapNode(node) {
        var txt = node.nodeValue;
        if (!txt || !txt.trim()) return;
        var orig = txt;
        var brandKeys = sortedKeys(BRAND);
        for (var i = 0; i < brandKeys.length; i++) {
            var k = brandKeys[i];
            if (txt.indexOf(k) !== -1) txt = txt.split(k).join(BRAND[k]);
        }
        var faKeys = sortedKeys(FA);
        for (var j = 0; j < faKeys.length; j++) {
            var key = faKeys[j];
            if (txt.indexOf(key) === -1) continue;
            var esc = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
            /* word boundaries only for pure-ASCII keys (protects Administrator etc.) */
            var pat = /^[A-Za-z0-9 _\-]+$/.test(key) ? new RegExp("\\b" + esc + "\\b", "g") : new RegExp(esc, "g");
            txt = txt.replace(pat, FA[key]);
        }
        for (var p = 0; p < PATTERNS.length; p++) {
            txt = txt.replace(PATTERNS[p][0], PATTERNS[p][1]);
        }
        if (txt !== orig) node.nodeValue = bidiIsolate(txt);
    }

    /* wrap Latin runs in LRI..PDI so mixed Persian/English keeps logical order */
    function bidiIsolate(s) {
        if (!/[\u0600-\u06FF]/.test(s) || !/[A-Za-z]/.test(s)) return s;
        return s.replace(/([A-Za-z0-9][A-Za-z0-9 ()\u2192._\/:+-]{0,48}[A-Za-z0-9)٪%]|[A-Za-z0-9]+)/g, "\u2066$1\u2069");
    }

    function swap(root) {
        if (document.title) {
            var t = document.title;
            var bk = sortedKeys(BRAND);
            for (var i = 0; i < bk.length; i++) t = t.split(bk[i]).join(BRAND[bk[i]]);
            if (t !== document.title) document.title = t;
        }
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
            acceptNode: function (n) {
                var p = n.parentElement;
                if (!p) return NodeFilter.FILTER_REJECT;
                var tag = p.tagName;
                if (tag === "SCRIPT" || tag === "STYLE" || tag === "TEXTAREA" || tag === "INPUT") return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            }
        }, false);
        var node;
        while ((node = walker.nextNode())) swapNode(node);
        /* placeholders */
        root.querySelectorAll && root.querySelectorAll("[placeholder]").forEach(function (el) {
            var ph = el.getAttribute("placeholder");
            if (FA[ph]) el.setAttribute("placeholder", FA[ph]);
        });
    }

    function run() { swap(document.body); }

    document.addEventListener("DOMContentLoaded", run);
    window.addEventListener("load", function () { run(); setTimeout(run, 800); });
    /* late AJAX panels (module admin, freepbx ajax) */
    setInterval(run, 2500);

    /* helper tooltips for technical terms (title attribute only, no DOM changes) */
    var HELPERS = {
        "PJSIP": "نسخه جدیدتر رابط SIP در Asterisk برای مدیریت داخلی‌ها و ترانک‌ها",
        "RTP": "پروتکل انتقال صدای تماس",
        "NAT": "تنظیمات عبور ترافیک تلفنی از شبکه‌های دارای آدرس خصوصی",
        "DTMF": "تن‌های دوگانه صفحه‌کلید تماس",
        "DID": "شماره مستقیم ورودی (Direct Inward Dialing)"
    };
    window.addEventListener("load", function () {
        setTimeout(function () {
            document.querySelectorAll("b, strong, label, td, th, dt, a").forEach(function (el) {
                var t = (el.textContent || "").trim();
                if (HELPERS[t] && !el.getAttribute("title")) el.setAttribute("title", HELPERS[t]);
            });
        }, 1200);
    });
})();
