/* MyTel theme.js — shell behaviors that replace the old neon menu JS.
   Depends on jQuery + neon-api.js (toggle_sidebar_menu) + neon-custom.js (readNoti). */
(function ($) {
    "use strict";

    /* ============ Jalali (Solar Hijri) date core ============ */
    var MT = window.MTJalali = (function () {
        var div = function (a, b) { return ~~(a / b); };
        var mod = function (a, b) { return a - ~~(a / b) * b; };
        function g2d(gy, gm, gd) {
            var d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4)
                + div(153 * mod(gm + 9, 12) + 2, 5)
                + gd - 34840408;
            d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
            return d;
        }
        function d2g(jdn) {
            var j = 4 * jdn + 139361631;
            j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
            var i = div(mod(j, 1461), 4) * 5 + 308;
            var gd = div(mod(i, 153), 5) + 1;
            var gm = mod(div(i, 153), 12) + 1;
            var gy = div(j, 1461) - 100100 + div(8 - gm, 6);
            return { gy: gy, gm: gm, gd: gd };
        }
        function jalCal(jy) {
            var breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
                1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];
            var bl = breaks.length, gy = jy + 621, leapJ = -14, jp = breaks[0], jm, jump = 0, leap, leapG, march, n, i;
            for (i = 1; i < bl; i += 1) {
                jm = breaks[i]; jump = jm - jp;
                if (jy < jm) break;
                leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
                jp = jm;
            }
            n = jy - jp;
            leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
            if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
            leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
            march = 20 + leapJ - leapG;
            if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
            leap = mod(mod(n + 1, 33) - 1, 4);
            if (leap === -1) leap = 4;
            return { leap: leap, gy: gy, march: march };
        }
        function d2j(jdn) {
            var gy = d2g(jdn).gy, jy = gy - 621;
            var r = jalCal(jy);
            var jdn1f = g2d(gy, 3, r.march);
            var k = jdn - jdn1f, jm, jd;
            if (k >= 0) {
                if (k <= 185) return { jy: jy, jm: 1 + div(k, 31), jd: mod(k, 31) + 1 };
                k -= 186;
            } else { jy -= 1; k += 179; if (r.leap === 1) k += 1; }
            jm = 7 + div(k, 30);
            jd = mod(k, 30) + 1;
            return { jy: jy, jm: jm, jd: jd };
        }
        var JMONTHS = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
        var JDAYS = ['شنبه','یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه'];
        var GDAYS_SHORT = { Sun: 'ی', Mon: 'د', Tue: 'س', Wed: 'چ', Thu: 'پ', Fri: 'ج', Sat: 'ش' };
        /* official + recurring Iranian holidays (jy, jm, jd, title) */
        var HOLIDAYS = [
            [0,1,1,'نوروز'],[0,1,2,'نوروز'],[0,1,3,'نوروز'],[0,1,4,'نوروز'],
            [0,1,12,'روز جمهوری اسلامی'],[0,1,13,'روز طبیعت'],
            [0,3,14,'رحلت امام خمینی'],[0,3,15,'قیام ۱۵ خرداد'],
            [0,11,22,'پیروزی انقلاب'],[0,12,29,'ملی شدن نفت'],
            [0,3,1,'نبرد خرمشهر'],[0,9,16,'روز دانش‌آموز'],[0,8,13,'روز دانش‌آموز'],
            [0,2,1,'روز کارگر معلم'],[0,6,31,'روز گفت‌وگو'],
            [1404,1,25,'تولد حضرت فاطمه'],[1404,2,28,'ليلة المباث'],[1404,3,3,'تولد امام حسین'],
            [1404,3,13,'ولادت امام رضا'],[1404,7,23,'تولد امام رضا'],
            [1404,10,10,'اربعین'],[1404,10,18,'وفات حضرت رسول'],[1404,11,3,'شهادت امام حسن'],
            [1404,11,20,'میلاد رسول اکرم'],[1404,12,20,'نیمه شعبان']
        ];
        function holidayName(jy, jm, jd) {
            for (var i = 0; i < HOLIDAYS.length; i++) {
                var h = HOLIDAYS[i];
                if (h[1] === jm && h[2] === jd && (h[0] === 0 || h[0] === jy)) return h[3];
            }
            return null;
        }
        function toJalali(date) {
            var jdn = g2d(date.getFullYear(), date.getMonth() + 1, date.getDate());
            var j = d2j(jdn);
            j.gwd = date.getDay();
            return j;
        }
        return { toJalali: toJalali, d2j: d2j, g2d: g2d, JMONTHS: JMONTHS, JDAYS: JDAYS, GDAYS_SHORT: GDAYS_SHORT, holidayName: holidayName, faNum: function (n) { return String(n).replace(/\d/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[d]; }); } };
    })();

    $(document).ready(function () {

        var $container = $('.page-container');

        /* burger (desktop collapse via neon helper, mobile drawer) */
        $('#mt-burger').on('click', function (e) {
            e.preventDefault();
            if (window.matchMedia('(max-width: 991px)').matches) {
                $container.toggleClass('mt-mobile-open');
            } else if (typeof toggle_sidebar_menu === 'function') {
                toggle_sidebar_menu(false);
            }
        });

        /* click outside closes the mobile drawer */
        $(document).on('click', function (e) {
            if ($container.hasClass('mt-mobile-open') &&
                !$(e.target).closest('#mt-sidebar, #mt-burger').length) {
                $container.removeClass('mt-mobile-open');
            }
        });

        /* panels drawer (original framework ids) */
        $(document).on('click', '#header_open_sidebar, a.chat-close', function (e) {
            $container.toggleClass('chat-visible');
            e.stopPropagation();
        });

        /* ---------- menu live search (filters top-level groups) ---------- */
        var norm = function (s) {
            return (s || '').replace(/[يى]/g, 'ی').replace(/ك/g, 'ک')
                     .replace(/\u200c/g, ' ').toLowerCase().trim();
        };
        var $search = $('#search_module_issabel');
        $search.on('input', function () {
            var q = norm($(this).val());
            $('#main-menu > li').each(function () {
                var $li = $(this);
                if ($li.attr('id') === 'search') return;
                var hit = q === '' || norm($li.text()).indexOf(q) !== -1;
                $li.toggle(hit);
                if (q !== '' && hit) $li.addClass('opened');
                if (q === '') $li.toggleClass('opened', $li.hasClass('active'));
            });
        });

        /* ---------- export dropdown from _list.tpl ---------- */
        $(document).on('click', '#neo-table-button-download-right', function (e) {
            e.stopPropagation();
            var $menu = $('#subMenuExport');
            var $btn = $('#export_button');
            if (!$menu.length || !$btn.length) return;
            if ($menu.hasClass('neo-display-none')) {
                var pos = $btn.position();
                var top = pos.top + $btn.outerHeight() + 2;
                var left = pos.left;
                if (left + $menu.outerWidth() > $(window).width() - 8) {
                    left = Math.max(8, $(window).width() - $menu.outerWidth() - 8);
                }
                $menu.css({ top: top + 'px', left: left + 'px' });
                $btn.addClass('exportBackground');
                $(this).addClass('exportBackground');
                $menu.removeClass('neo-display-none');
                $(this).attr('aria-expanded', 'true');
            } else {
                $menu.addClass('neo-display-none');
                $('#export_button').removeClass('exportBackground');
                $(this).removeClass('exportBackground');
                $(this).attr('aria-expanded', 'false');
            }
        });
        $(document).on('click', function (e) {
            if (!$(e.target).closest('#subMenuExport, #neo-table-button-download-right, #export_button').length) {
                $('#subMenuExport').addClass('neo-display-none');
                $('#export_button').removeClass('exportBackground');
                $('#neo-table-button-download-right').removeClass('exportBackground');
            }
        });
        $(document).on('click', '#neo-table-filter-button-arrow', function () {
            $(this).toggleClass('exportBackground');
        });

        /* guard against neon height fitting clipping the flex layout */
        var unclipTimer = null;
        var unclip = function () {
            $('.main-content.mt-main-content').css('height', 'auto');
        };
        setTimeout(unclip, 400);
        $(window).on('resize', function () {
            clearTimeout(unclipTimer);
            unclipTimer = setTimeout(unclip, 250);
        });

        /* ---------- brand spinner: replace stock logo wait images ---------- */
        var fixSpinners = function () {
            $('.appletwindow_wait img[src*="issabel_logo_pattern"], img.imageSpin[src*="issabel_logo_pattern"]')
                .attr('src', '/themes/mytel/images/mt-spinner.svg');
        };
        fixSpinners();
        $(document).ajaxComplete(fixSpinners);
        setInterval(fixSpinners, 3000);

        /* ---------- brand text substitution in module content ---------- */
        var TEXT_MAP = {
            "Elastix": "MyTel",
            "Marcar todos": "انتخاب همه",
            "Desmarcar Todos": "لغو انتخاب همه",
            "Marcartodos": "انتخاب همه",
            "DesmarcarTodos": "لغو انتخاب همه",
            /* dashboard applets */
            "Fetch directory report": "دریافت گزارش پوشه‌ها",
            "WARNING: this operation may take a long time AND impact system performance": "هشدار: این عملیات زمان‌بر است و بر کارایی سامانه اثر می‌گذارد.",
            "Hard Disk Capacity:": "ظرفیت دیسک:",
            "Mount Point:": "نقطه اتصال:",
            "Manufacturer:": "سازنده:",
            "Used": "مصرف‌شده",
            "Available": "آزاد",
            "Sim. calls": "تماس‌های همزمان",
            "(%) CPU usage": "مصرف پردازنده (٪)",
            "Mem. usage (MB)": "مصرف حافظه (مگابایت)",
            "Send": "ارسال",
            "Call history": "تاریخچه تماس",
            /* applet admin */
            "Select/Unselect All": "انتخاب/لغو انتخاب همه",
            "News:": "اخبار:",
            "Calls:": "تماس‌ها:",
            "Emails:": "ایمیل‌ها:",
            "Faxes:": "فکس‌ها:",
            "Voicemails:": "صندوق‌های صوتی:",
            "Telephony Hardware:": "تجهیزات تلفنی:",
            "System:": "سیستم:",
            "Hardware Control": "کنترل سخت‌افزار",
            /* hardware detector */
            "Port Status": "راهنمای وضعیت پورت‌ها",
            "Channel detected and not in service": "کانال شناسایی‌شده و خارج از سرویس",
            "Channel detected and in service": "کانال شناسایی‌شده و در سرویس",
            "Undetected Channel": "کانال شناسایی‌نشده",
            "Empty Channel": "کانال خالی",
            /* calendar */
            "today": "امروز",
            "month": "ماه",
            "week": "هفته",
            "day": "روز",
            "Download ical calendar": "دریافت تقویم (iCal)",
            /* email stats */
            "Incoming email by hour": "ایمیل‌های دریافتی بر اساس ساعت",
            "Incoming email by day": "ایمیل‌های دریافتی بر اساس روز",
            "Incoming email by month": "ایمیل‌های دریافتی بر اساس ماه",
            "Number of emails": "تعداد ایمیل‌ها",
            "Nothing to show yet": "هنوز داده‌ای ثبت نشده است",
            /* vacations */
            "Period": "بازه",
            "FROM": "از",
            "TO": "تا",
            "day(s)": "روز",
            /* fax clients help */
            "These IPs are allowed to send faxes through MyTel.": "فقط نشانی‌های IP زیر مجازند از این سامانه فکس ارسال کنند.",
            "You must insert one IP per row. We recommend keeping localhost and 127.0.0.1 in the configuration because some processes could need them.": "هر نشانی IP را در یک سطر جدا وارد کنید. نگه‌داشتن localhost و 127.0.0.1 ضروری است، چون برخی فرایندهای داخلی سامانه به آن‌ها نیاز دارند.",
            /* email template subjects */
            "Fax Issabel": "فکس مای‌تل",
            "Fax attached (ID: {NAME_PDF})": "فکس پیوست شد (شناسه: {NAME_PDF})",
            /* backup_restore toolbar (untranslated in module) */
            "Upload": "بارگذاری",
            "Delete backups older than": "حذف پشتیبان‌های قدیمی‌تر از",
            "New backup": "پشتیبان جدید"
        };
        var brandSwap = function (root) {
            var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
            var node, txt;
            while ((node = walker.nextNode())) {
                txt = node.nodeValue;
                if (!txt) continue;
                for (var k in TEXT_MAP) {
                    if (txt.indexOf(k) !== -1) { txt = txt.split(k).join(TEXT_MAP[k]); node.nodeValue = txt; }
                }
            }
        };
        var $content = $('.neo-module-content');
        if ($content.length) brandSwap($content[0]);
        /* late-loaded content (ajax charts, ribbons) gets swapped too */
        setInterval(function () {
            var c = document.querySelector('.neo-module-content');
            if (c) brandSwap(c);
        }, 3000);

        /* ---------- submit inputs whose label is an untranslated value:
           swap to a Persian button + a hidden input preserving name/value ---------- */
        var swapSubmitLabels = function (root) {
            root.querySelectorAll('input[type=submit], input[type=button]').forEach(function (inp) {
                var fa = TEXT_MAP[inp.value];
                if (!fa || inp.dataset.mtSwapped) return;
                inp.dataset.mtSwapped = '1';
                if (inp.type === 'button') { inp.value = fa; return; }
                var btn = document.createElement('button');
                btn.type = 'submit';
                btn.className = inp.className + ' mt-fa-submit';
                btn.textContent = fa;
                btn.name = inp.name || '';
                btn.value = inp.value;
                var hidden = document.createElement('input');
                hidden.type = 'hidden';
                hidden.name = inp.name || '';
                hidden.value = inp.value;
                inp.parentNode.insertBefore(btn, inp);
                inp.parentNode.insertBefore(hidden, inp);
                inp.remove();
            });
        };
        if ($content.length) setTimeout(function () { swapSubmitLabels($content[0]); }, 700);
        $(document).ajaxComplete(function () {
            setTimeout(function () {
                var c = document.querySelector('.neo-module-content');
                if (c) swapSubmitLabels(c);
            }, 400);
        });

        /* ---------- LTR-isolate legacy help cells (mostly-Latin text) ---------- */
        var latinRatio = function (s) {
            var latin = (s.match(/[A-Za-z0-9]/g) || []).length;
            return latin / Math.max(1, s.replace(/\s/g, '').length);
        };
        var isolateLtrCells = function (root) {
            root.querySelectorAll('td').forEach(function (td) {
                if (td.querySelector('input, select, textarea, button')) return;
                var t = td.textContent.trim();
                if (t.length > 40 && latinRatio(t) > 0.72) td.classList.add('mt-ltr');
            });
            root.querySelectorAll('.tabForm td i, .tabForm td em').forEach(function (el) {
                var t = el.textContent.trim();
                if (t.length > 20 && latinRatio(t) > 0.6) el.classList.add('mt-ltr');
            });
        };
        if ($content.length) isolateLtrCells($content[0]);

        /* ---------- flot recolor: defaults are baked inside the closure,
           so recolor the live series after each plot ---------- */
        var CHART_MAP = {
            '#00cc00': '#27965A', '#33cc33': '#27965A', '#004ce0': '#1E88E5',
            '#0000cc': '#1E88E5', '#3da8fb': '#1E88E5', '#afd8f8': '#1E88E5',
            '#cc0000': '#FF8A00', '#cb4b4b': '#FF8A00', '#cb4b16': '#FF8A00',
            '#edc240': '#FFB25C', '#e8b800': '#FFB25C'
        };
        var recolorFlot = function () {
            $('#dashboard-applet-performancegraph').each(function () {
                var plot = $(this).data('plot');
                if (!plot) return;
                var changed = false;
                var series = plot.getData();
                series.forEach(function (s) {
                    var c = (typeof s.color === 'string' ? s.color : '').toLowerCase();
                    if (CHART_MAP[c] && s.color !== CHART_MAP[c]) { s.color = CHART_MAP[c]; changed = true; }
                });
                if (changed) { try { plot.setupGrid(); plot.draw(); } catch (e) {} }
            });
        };
        $(document).ajaxComplete(function () { setTimeout(recolorFlot, 300); });
        setInterval(recolorFlot, 2500);

        /* ---------- hide the upstream hardcoded placeholder row in the
           CDR datatables template (a row of fully empty <td>s) ---------- */
        var hideEmptyPlaceholderRows = function () {
            $('.dataTables_wrapper table tbody tr').each(function () {
                var $tr = $(this);
                if ($tr.hasClass('child') || $tr.hasClass('group')) return;
                var tds = $tr.find('td').not('.dtr-control');
                if (tds.length && tds.toArray().every(function (td) { return !$(td).text().trim() && !$(td).children().length; })) {
                    $tr.addClass('mt-empty-placeholder');
                }
            });
        };
        $(document).ajaxComplete(function () { setTimeout(hideEmptyPlaceholderRows, 250); });
        setTimeout(hideEmptyPlaceholderRows, 1500);

        /* ---------- Persian language for legacy DataTables ---------- */
        var dtLang = function () {
            if (!window.jQuery || !$.fn.dataTable) return;
            $.extend(true, $.fn.dataTable.defaults, {
                oLanguage: {
                    sEmptyTable: "رکوردی یافت نشد",
                    sZeroRecords: "رکوردی یافت نشد",
                    sInfo: "نمایش _START_ تا _END_ از _TOTAL_ ردیف",
                    sInfoEmpty: "نمایش ۰ تا ۰ از ۰ ردیف",
                    sInfoFiltered: "(پالایش‌شده از _MAX_ ردیف)",
                    sLengthMenu: "نمایش _MENU_ ردیف",
                    sSearch: "جستجو:",
                    oPaginate: { sFirst: "نخست", sLast: "آخر", sNext: "بعدی", sPrevious: "قبلی" }
                }
            });
        };
        var dtTimer = setInterval(function () {
            if (window.jQuery && $.fn.dataTable) { dtLang(); clearInterval(dtTimer); }
        }, 300);
        setTimeout(function () { clearInterval(dtTimer); }, 10000);

        /* ---------- replace stock default hosts in tools (client-side only) ---------- */
        setTimeout(function () {
            $('.neo-module-content input[type=text]').each(function () {
                if (this.value === 'www.issabel.org') { this.value = ''; this.placeholder = 'mytel.one'; }
            });
        }, 800);

        /* ---------- strip server locale warnings from textarea content ---------- */
        var cleanPerlNoise = function () {
            $('.neo-module-content textarea').each(function () {
                if (this.value.indexOf('perl: warning') === -1) return;
                this.value = this.value.split('\n').filter(function (l) {
                    return !/^perl: warning|^Please check that your locale|^LANGUAGE =|^LC_ALL =|^LANG =|^are supported and installed/.test(l.trim());
                }).join('\n').replace(/^\n+/, '');
            });
        };
        setTimeout(cleanPerlNoise, 900);

        /* ---------- page helpers: contextual Persian guidance ---------- */
        var addGuide = function (menuId, html) {
            var c = document.querySelector('.neo-module-content');
            if (!c || c.querySelector('.mt-guide') || location.search.indexOf('menu=' + menuId) === -1) return;
            var d = document.createElement('div');
            d.className = 'mt-guide';
            d.innerHTML = html;
            c.insertBefore(d, c.firstChild);
        };
        setTimeout(function () {
            addGuide('betachannel', '<b>دریافت به‌روزرسانی‌های آزمایشی (کانال بتا)</b><p>با روشن‌کردن این کلید، سامانه نسخه‌های آزمایشی تازه را هم هنگام به‌روزرسانی پیشنهاد می‌دهد. این نسخه‌ها ویژگی‌های تازه دارند اما ممکن است ناپایدار باشند؛ <u>فقط روی سرورهای آزمایشی</u> روشن کنید. برای سرور عملیاتی همیشه خاموش بماند.</p>');
            addGuide('shutdown', '<b>خاموش یا ریست دستی سرور</b><p>گزینهٔ «خاموش» سرور را کامل خاموش می‌کند و «راه اندازی دوباره» سرویس‌ها را ری‌استارت می‌کند. پیش از اقدام، از تماس‌های جاری مطمئن شوید؛ این عملیات مرکز تلفن را موقتاً از دسترس خارج می‌کند.</p>');
            addGuide('faxmaster', '<b>صندوق فکس مرکزی</b><p>این بخش فکس‌های ورودی سرور را مدیریت می‌کند: صندوق پیش‌فرض سامانه که همهٔ فکس‌های بدون مقصد مشخص به آن می‌رسند و می‌توانید آن‌ها را ببینید، بگیرید یا به ایمیل تبدیل کنید.</p>');
            addGuide('faxclients', '<b>کاربران مجاز فکس</b><p>این صفحه مشخص می‌کند کدام رایانه‌ها (نشانی‌های IP) اجازه دارند از طریق سامانه فکس ارسال کنند. هر IP را در یک سطر جدا بنویسید؛ localhost و 127.0.0.1 را حذف نکنید.</p>');
            addGuide('vacations', '<b>پیام عدم حضور (تعطیلات)</b><p>با فعال‌کردن این بخش، هر کسی در بازهٔ تعیین‌شده تماس بگیرد یا ایمیل بزند، پیام «در دسترس نیستم» را به‌طور خودکار دریافت می‌کند. بازهٔ زمانی، آدرس ایمیل و متن پیام را مشخص کنید.</p>');
            addGuide('email_relay', '<b>مجوز ارسال ایمیل (Relay)</b><p>این صفحه مشخص می‌کند کدام شبکه‌ها اجازه دارند از طریق سرور شما ایمیل به بیرون بفرستند. نشانی‌ها را به‌صورت CIDR وارد کنید؛ مثلاً 127.0.0.1/32 یعنی فقط خود سرور. هر شبکه‌ای که اضافه نکنید، اجازهٔ ارسال ندارد (جلوگیری از سوءاستفاده).</p>');
            addGuide('antispam', '<b>پالایش هرزنامه</b><p>با فعال‌کردن این بخش، ایمیل‌های ورودی از نظر هرزنامه بررسی می‌شوند. «درجه» حساسیت پالایش است: عدد کمتر = سخت‌گیری بیشتر. در حالت «مبتدی» فقط سربرگ هرزنامه برچسب می‌خورد و در حالت «خبره» تصمیم‌گیری کامل به پالایش‌گر سپرده می‌شود.</p>');
        }, 600);

        /* ---------- Jalali overlay for the FullCalendar page ---------- */
        var jalaliCalendar = function () {
            var cal = document.querySelector('#calendar_main .fc, .fc');
            if (!cal) return;
            if (cal.dataset.mtJalali === '1') { return; }
            cal.dataset.mtJalali = '1';
            cal.classList.add('mt-jalali');

            var apply = function () {
                /* month title (old FullCalendar: .fc-header-title h2) */
                var title = cal.querySelector('.fc-header-title h2, .fc-center h2, .fc-toolbar .fc-title');
                var m = title ? title.textContent.match(/([A-Za-z]+)\s+(\d{4})/) : null;
                if (m && title) {
                    var monthsEn = { January:1, February:2, March:3, April:4, May:5, June:6, July:7, August:8, September:9, October:10, November:11, December:12 };
                    var gm = monthsEn[m[1]], gy = +m[2];
                    if (gm) {
                        var first = new Date(gy, gm - 1, 1);
                        var jf = MT.toJalali(first);
                        var mid = MT.toJalali(new Date(gy, gm - 1, 15));
                        var jy = jf.jm === 12 && mid.jm === 1 ? mid.jy - 1 : mid.jy;
                        title.innerHTML = MT.JMONTHS[jf.jm - 1] + ' ' + MT.faNum(jy) +
                            ' <small dir="ltr" class="mt-greg">' + m[1] + ' ' + m[2] + '</small>';
                    }
                }
                /* weekday headers */
                cal.querySelectorAll('.fc-day-header').forEach(function (th) {
                    var en = (th.textContent || '').trim();
                    var short = en.slice(0, 3);
                    if (MT.GDAYS_SHORT[short] !== undefined) th.textContent = MT.GDAYS_SHORT[short];
                });
                /* day numbers + holiday highlight */
                cal.querySelectorAll('td[data-date]').forEach(function (cell) {
                    var parts = (cell.getAttribute('data-date') || '').split('-');
                    if (parts.length !== 3) return;
                    var dt = new Date(+parts[0], +parts[1] - 1, +parts[2]);
                    var numHolder = cell.querySelector('.fc-day-number');
                    if (numHolder && !numHolder.dataset.mtJ) {
                        var j0 = MT.toJalali(dt);
                        numHolder.dataset.mtJ = '1';
                        var g = numHolder.textContent.trim();
                        numHolder.innerHTML = '<b class="mt-jday">' + MT.faNum(j0.jd) + '</b><small class="mt-gday">' + g + '</small>';
                    }
                    var jd = MT.toJalali(dt);
                    var hol = MT.holidayName(jd.jy, jd.jm, jd.jd);
                    cell.classList.toggle('mt-holiday', !!hol || dt.getDay() === 5);
                    if (hol) { cell.setAttribute('title', hol); cell.classList.add('mt-has-name'); }
                });
            };
            apply();
            setInterval(apply, 1500);
        };
        setTimeout(jalaliCalendar, 1500);

        /* ---------- email_stats: server-pixel charts get Persian captions
           (the English title band inside the image is cropped away) ---------- */
        var persianizeEmailStats = function () {
            if (location.search.indexOf('menu=email_stats') === -1) return;
            var c = document.querySelector('.neo-module-content');
            if (!c) return;
            var titles = ['ایمیل‌های دریافتی بر اساس ساعت', 'ایمیل‌های دریافتی بر اساس روز', 'ایمیل‌های دریافتی بر اساس ماه'];
            c.querySelectorAll('img[src*="email_stats"][src*="rawmode"]').forEach(function (img, idx) {
                if (img.closest('.mt-chart')) return;
                var fig = document.createElement('figure');
                fig.className = 'mt-chart';
                var cap = document.createElement('figcaption');
                cap.textContent = titles[idx] || '';
                img.parentNode.insertBefore(fig, img);
                var crop = document.createElement('div');
                crop.className = 'mt-chart-crop';
                fig.appendChild(cap);
                fig.appendChild(crop);
                crop.appendChild(img);
            });
        };
        setTimeout(persianizeEmailStats, 1500);

        /* ---------- rebuild the Communication Activity applet:
           the upstream PHP glues translation fragments in a broken
           order, so re-render it as a clean Persian table ---------- */
        var rebuildComm = function () {
            var el = document.querySelector('#Applet_CommunicationActivity');
            if (!el || el.dataset.mtRebuilt) return;
            var txt = (el.innerText || '').replace(/\s+/g, ' ');
            var grab = function (re) { var m = txt.match(re); return m ? m[1] : null; };
            var calls = grab(/تماس\s*\((\d+)\)/);
            var internal = grab(/\((\d+)\s*تماس هاي داخلي\)|\((\d+)\s*تماس های داخلی\)/);
            var external = grab(/\((\d+)\s*تماس هاي خارجي\)|\((\d+)\s*تماس های خارجی\)/);
            var channels = grab(/كل تماس ها:?\s*(\d+)|کل تماس ها:?\s*(\d+)/);
            var waiting = grab(/تماس هاي در صف انتظار:?\s*(\d+)|(\d+)\s*منتظر|تماس های در صف انتظار:?\s*(\d+)/);
            var sip = grab(/SIP داخلي هاي\s*\((\d+)\)|SIP داخلی های\s*\((\d+)\)/);
            var pjsip = grab(/PJSIP داخلي هاي\s*\((\d+)\)|PJSIP داخلی های\s*\((\d+)\)/);
            var iax = grab(/IAX داخلي هاي\s*\((\d+)\)|IAX داخلی های\s*\((\d+)\)/);
            var trunks = grab(/ترانك ها\s*\((\d+)\)|ترانک ها\s*\((\d+)\)/);
            var traffic = grab(/([\d.]+k?B\/s\)\s*=>\s*\([\d.]+k?B\/s)/);
            if (calls === null || trunks === null) return; /* data not complete yet — retry */
            var rows = [];
            if (calls !== null) rows.push(['کل تماس‌ها', calls + ' (داخلی ' + (internal || '0') + ' | خارجی ' + (external || '0') + ')']);
            if (channels !== null) rows.push(['کانال‌های فعال', channels]);
            if (waiting !== null) rows.push(['در صف انتظار', waiting]);
            var reg = function (base) {
                var after = txt.slice(txt.indexOf(base));
                var r = after.match(/\((\d+)\s*ثبت شده\)|\((\d+)\s*ثبت شده\)/) || after.match(/\((\d+)\s*ثبت شده\)/);
                var u = after.match(/\((\d+)\s*ثبت نشده\)|\((\d+)\s*ثبت نشده\)/);
                return (r ? (r[1] || r[2]) : '?') + ' / ' + (u ? (u[1] || u[2]) : '?');
            };
            if (sip !== null) rows.push(['داخلی‌های SIP', sip + ' (ثبت‌شده ' + reg('SIP داخلي').split(' / ')[0] + ' | ثبت‌نشده ' + reg('SIP داخلي').split(' / ')[1] + ')']);
            if (pjsip !== null) rows.push(['داخلی‌های PJSIP', pjsip + ' (ثبت‌شده ' + reg('PJSIP داخلي').split(' / ')[0] + ' | ثبت‌نشده ' + reg('PJSIP داخلي').split(' / ')[1] + ')']);
            if (iax !== null) rows.push(['داخلی‌های IAX', iax + ' (ثبت‌شده ' + reg('IAX داخلي').split(' / ')[0] + ' | ثبت‌نشده ' + reg('IAX داخلي').split(' / ')[1] + ')']);
            if (trunks !== null) rows.push(['ترانک‌ها', trunks]);
            if (traffic !== null) rows.push(['ترافیک شبکه', 'دریافتی ' + traffic.split('=>')[0].replace('(', '').replace(')', '').trim() + ' | ارسالی ' + traffic.split('=>')[1].replace('(', '').replace(')', '').trim()]);
            var html = '<table class="mt-comm">' + rows.map(function (r) {
                return '<tr><td>' + r[0] + '</td><td class="mt-num">' + r[1] + '</td></tr>';
            }).join('') + '</table>';
            var full = el.querySelector('.appletwindow_fullcontent') || el;
            full.innerHTML = html;
            el.dataset.mtRebuilt = '1';
        };
        var rebuildAttempts = 0;
        var rebuildLoop = function () {
            if (rebuildAttempts++ > 12) return;
            if (!document.querySelector('#Applet_CommunicationActivity[data-mt-rebuilt="1"]')) {
                rebuildComm();
                setTimeout(rebuildLoop, 2500);
            }
        };
        setTimeout(rebuildLoop, 5000);
    });
})(jQuery);
