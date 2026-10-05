/* MyTel theme.js — shell behaviors that replace the old neon menu JS.
   Depends on jQuery + neon-api.js (toggle_sidebar_menu) + neon-custom.js (readNoti). */
(function ($) {
    "use strict";

    /* ---------- capture Chart.js instances at construction time
       (legacy Chart.js lacks Chart.getChart; wrap the constructor) ---------- */
    (function wrapChartJs() {
        var iv = setInterval(function () {
            if (!window.Chart || window.Chart.__mtWrapped) { if (window.Chart && window.Chart.__mtWrapped) clearInterval(iv); return; }
            try {
                var Orig = window.Chart;
                var Wrapped = function (ctx, cfg) {
                    var inst = new Orig(ctx, cfg);
                    try {
                        var cv = (ctx && ctx.canvas) ? ctx.canvas : ctx;
                        if (cv && cv.tagName === 'CANVAS') cv.__mtChart = inst;
                    } catch (e) {}
                    return inst;
                };
                Wrapped.prototype = Orig.prototype;
                Object.keys(Orig).forEach(function (k) { try { Wrapped[k] = Orig[k]; } catch (e) {} });
                Wrapped.__mtWrapped = true;
                window.Chart = Wrapped;
            } catch (e) {}
        }, 10);
        setTimeout(function () { clearInterval(iv); }, 10000);
    })();

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
        function j2d(jy, jm, jd) {
            var r = jalCal(jy);
            return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
        }
        function toGregorian(jy, jm, jd) {
            var g = d2g(j2d(jy, jm, jd));
            return new Date(g.gy, g.gm - 1, g.gd);
        }
        return { toJalali: toJalali, toGregorian: toGregorian, d2j: d2j, g2d: g2d, j2d: j2d, JMONTHS: JMONTHS, JDAYS: JDAYS, GDAYS_SHORT: GDAYS_SHORT, holidayName: holidayName, faNum: function (n) { return String(n).replace(/\d/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[d]; }); } };
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

        /* ============================================================
           ECharts migration layer — same data, better visualization.
           Targets (inventory): dashboard flot (PerformanceGraphic),
           dashboard Raphael gauges (SystemResources), HardDrives donut,
           Chart.js canvases (cdrreport/monitoring/channelusage/graphic_report).
           ============================================================ */

        var E = function () { return window.MyTelCharts && window.echarts; };

        /* ---- 0) custom MyTel dashboard ("control room") — replaces the
           legacy applet grid, which stays in the DOM only as a data source ---- */
        var mtFa = function (n) { return window.MTJalali ? MTJalali.faNum(String(n)) : String(n); };
        var mtFresh = function () {
            window.__mtFreshAt = Date.now();
            var el = document.getElementById('mt-fresh');
            if (!el) return;
            var d = new Date();
            el.textContent = 'به‌روزرسانی: ' + mtFa(('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2) + ':' + ('0' + d.getSeconds()).slice(-2));
            var wrap = el.closest('.mt-dash-fresh');
            if (wrap) wrap.classList.remove('stale');
        };
        setInterval(function () {
            var el = document.getElementById('mt-fresh');
            var wrap = el ? el.closest('.mt-dash-fresh') : null;
            if (wrap && window.__mtFreshAt && Date.now() - window.__mtFreshAt > 90000) wrap.classList.add('stale');
        }, 15000);

        var renderHealth = function () {
            var wrap = document.getElementById('mt-health-rows');
            if (!wrap) return;
            var Tk = window.MyTelCharts ? MyTelCharts.T : { primary: '#2E3194', danger: '#E5484D' };
            var sys = window.__mtSys || {};
            var rows = [['پردازنده', sys.CPU], ['حافظه', sys.RAM], ['حافظه مبادله‌ای', sys.SWAP]];
            var html = rows.map(function (r) {
                var has = typeof r[1] === 'number' && r[1] >= 0;
                var pct = has ? Math.round(r[1]) : null;
                var col = has && pct >= 85 ? Tk.danger : Tk.primary;
                return '<div class="mt-hrow"><span class="mt-hlab">' + r[0] + '</span>' +
                    '<span class="mt-hmeter"><span style="width:' + (has ? Math.min(100, pct) : 0) + '%;background:' + col + '"></span></span>' +
                    '<span class="mt-hpct">' + (has ? mtFa(pct) + '٪' : '—') + '</span></div>';
            }).join('');
            if (!wrap.innerHTML || wrap.dataset.sig !== html) { wrap.innerHTML = html; wrap.dataset.sig = html; }
            /* disk panel below the meters */
            var panel = document.getElementById('mt-disk-panel');
            var d = window.__mtDisk;
            if (panel && d && typeof d.usedPct === 'number') {
                var used = Math.round(d.total * d.usedPct / 100 * 10) / 10;
                var col = d.usedPct >= 85 ? Tk.danger : Tk.primary;
                panel.innerHTML =
                    '<div class="mt-disk-top"><span>فضای دیسک</span><b>' + mtFa(d.usedPct) + '٪</b></div>' +
                    '<span class="mt-hmeter"><span style="width:' + Math.min(100, d.usedPct) + '%;background:' + col + '"></span></span>' +
                    '<div class="mt-disk-sub" dir="ltr">' + used + ' GB / ' + d.total + ' GB</div>';
            }
        };

        var dashInit = function () {
            var grid = document.querySelector('#neo-contentbox #applet_grid');
            if (!grid || document.getElementById('mt-dash')) return;
            var parent = grid.parentNode;
            var dash = document.createElement('div');
            dash.id = 'mt-dash';
            dash.innerHTML =
                '<div class="mt-dash-head">' +
                    '<div><h1>نمای کلی مرکز تماس</h1>' +
                    '<div class="mt-dash-sub">وضعیت زندهٔ سامانهٔ تلفنی مای‌تل</div></div>' +
                    '<div class="mt-dash-fresh"><span class="mt-dot"></span><span id="mt-fresh">در حال دریافت…</span></div>' +
                '</div>' +
                '<div class="mt-hero-row">' +
                    '<section class="mt-card mt-hero-main">' +
                        '<div class="mt-hero-figs">' +
                            '<div class="mt-fig"><div class="mt-fig-num" id="mt-fig-calls">—</div><div class="mt-fig-lab">تماس‌های هم‌زمان</div></div>' +
                            '<div class="mt-fig-sep"></div>' +
                            '<div class="mt-fig"><div class="mt-fig-num mt-fig-num--sm" id="mt-fig-reg">—</div><div class="mt-fig-lab">داخلی ثبت‌شده</div></div>' +
                        '</div>' +
                        '<div class="mt-echart" id="mt-dash-calls" data-mt-keep="1" style="height:225px"></div>' +
                    '</section>' +
                    '<section class="mt-card mt-hero-health">' +
                        '<div class="mt-card-title">سلامت منابع</div>' +
                        '<div id="mt-health-rows"></div>' +
                        '<div class="mt-disk-panel" id="mt-disk-panel"></div>' +
                    '</section>' +
                '</div>' +
                '<section class="mt-card">' +
                    '<div class="mt-card-title-row"><span class="mt-card-title">عملکرد در یک ساعت گذشته</span>' +
                    '<span class="mt-card-hint" id="mt-perf-range"></span></div>' +
                    '<div class="mt-echart" id="mt-dash-perf" data-mt-keep="1" style="height:280px"></div>' +
                '</section>' +
                '<div class="mt-detail-row">' +
                    '<section class="mt-card"><div class="mt-card-title">وضعیت ارتباطات</div><div id="mt-dash-comm"></div></section>' +
                    '<section class="mt-card"><div class="mt-card-title">اطلاعات سیستم</div><div class="mt-sysinfo" id="mt-dash-sys"></div></section>' +
                '</div>';
            parent.insertBefore(dash, grid);
        };
        dashInit();

        /* ---- 1) dashboard performance chart: flot data -> ECharts line ---- */
        var mtPerf = null;
        var migratePerf = function () {
            if (!E()) return;
            var host = document.querySelector('#dashboard-applet-performancegraph');
            if (!host) return;
            var plot = window.jQuery(host).data('plot');
            if (!plot) return;
            var data = plot.getData();
            if (!data || !data.length) return;
            /* build categories from first series x-values (epoch ms) */
            var cats = [];
            var s0 = data[0].data || [];
            var span = (s0.length > 1 ? (s0[s0.length - 1][0] - s0[0][0]) : 0);
            var fmt = function (t) {
                var d = new Date(t);
                var hm = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
                if (span > 3 * 864e5) {
                    var j = window.MTJalali ? window.MTJalali.toJalali(d) : null;
                    return j ? MTJalali.JMONTHS[j.jm - 1] + ' ' + MTJalali.faNum(j.jd) : hm;
                }
                return hm;
            };
            s0.forEach(function (p) { cats.push(fmt(p[0])); });
            /* last concurrent-calls point feeds the hero figure */
            if (s0.length && s0[s0.length - 1]) window.__mtPerfNow = s0[s0.length - 1][1];
            var fig = document.getElementById('mt-fig-calls');
            if (fig && window.__mtPerfNow !== undefined) fig.textContent = mtFa(window.__mtPerfNow);
            /* hero card: orange one-hour concurrent-calls area chart */
            var callsHost = document.getElementById('mt-dash-calls');
            if (callsHost) {
                var callsSrc = data.filter(function (s) { return /sim/i.test(s.label); });
                var cs = callsSrc.length ? callsSrc[0] : data[0];
                MyTelCharts.line(callsHost, null, cats, [{
                    name: 'تماس‌های هم‌زمان',
                    data: (cs.data || []).map(function (p) { return p[1]; }),
                    color: MyTelCharts.T.accent
                }], { area: true, force: true });
            }
            /* diagnostics card: CPU% (indigo) + RAM MB (teal) */
            var perfHost = document.getElementById('mt-dash-perf');
            if (perfHost) {
                var diag = [];
                data.forEach(function (s) {
                    if (/cpu/i.test(s.label)) diag.push({ name: 'مصرف پردازنده (٪)', data: (s.data || []).map(function (p) { return p[1]; }), color: MyTelCharts.T.primary });
                    else if (/mem/i.test(s.label)) diag.push({ name: 'مصرف حافظه (MB)', data: (s.data || []).map(function (p) { return p[1]; }), color: '#318C96' });
                });
                if (diag.length) MyTelCharts.line(perfHost, null, cats, diag, { area: true });
            }
            var range = document.getElementById('mt-perf-range');
            if (range && cats.length > 1) range.textContent = 'بازه: ' + cats[0] + ' تا ' + cats[cats.length - 1];
            /* freshness only advances when the source actually moved — the
               latest sample timestamp catches rolling-window updates whose
               values happen to be unchanged */
            var sig = data.map(function (s) {
                var d = s.data || [];
                return d.length + ':' + (d.length ? d[d.length - 1][0] + '@' + d[d.length - 1][1] : '');
            }).join(';');
            if (sig !== window.__mtPerfSig) { window.__mtPerfSig = sig; mtFresh(); }
        };
        $(document).ajaxComplete(function () { setTimeout(migratePerf, 500); });
        setInterval(migratePerf, 60000); /* live applet refresh keeps data fresh */

        /* ---- 2) system resources: harvest JustGage SVG values (the applet
           grid is hidden — textContent still works) -> health-card meters ---- */
        var migrateGauges = function () {
            var full = document.querySelector('#Applet_SystemResources .appletwindow_fullcontent');
            if (!full) return;
            var svgs = full.querySelectorAll('svg');
            if (svgs.length < 3) return;
            var vals = [];
            svgs.forEach(function (svg) {
                var texts = svg.querySelectorAll('text');
                var label = null, value = null, bestSize = -1;
                texts.forEach(function (t) {
                    var txt = (t.textContent || '').trim();
                    if (!txt) return;
                    var fs = parseFloat((t.getAttribute('font-size') || t.style.fontSize || '0')) || 0;
                    if (/^[A-Za-z]{3,6}$/.test(txt) && label === null) label = txt;
                    if (/^\d+(\.\d+)?$/.test(txt) && fs > bestSize) { bestSize = fs; value = parseFloat(txt); }
                });
                if (label !== null && value !== null && bestSize > 0) vals.push({ name: label, value: value });
            });
            if (vals.length < 3) return;
            /* freshness only advances on genuinely new gauge readings */
            var gsig = vals.map(function (v) { return v.name + v.value; }).join(',');
            var gNew = gsig !== window.__mtGaugeSig;
            window.__mtGaugeSig = gsig;
            window.__mtSys = {};
            vals.forEach(function (v) { window.__mtSys[v.name] = v.value; });
            renderHealth();
            if (gNew) mtFresh();
        };
        setTimeout(function () { migrateGauges(); setTimeout(migrateGauges, 5000); }, 4000);
        $(document).ajaxComplete(function () { setTimeout(migrateGauges, 1200); });

        /* ---- 2b) system info card: Persian labels, isolated LTR values.
           Source rows live in the hidden applet grid — textContent still
           works, so every tick repaints with fresh values. ---- */
        var buildSysInfo = function () {
            var box = document.getElementById('mt-dash-sys');
            if (!box) return;
            var full = document.querySelector('#Applet_SystemResources .appletwindow_fullcontent');
            if (!full) return;
            var cpu = '', up = '', speed = '', mem = '', login = '';
            full.querySelectorAll('.neo-applet-tline').forEach(function (ln) {
                var lab = ((ln.querySelector('.neo-applet-titem') || {}).textContent || '');
                var val = ((ln.querySelector('.neo-applet-tdesc') || {}).textContent || '').trim();
                if (/پردازنده/i.test(lab) && !/سرعت/i.test(lab) && !cpu) cpu = val;
                else if (/زمان فعال|Uptime/i.test(lab) && !up) up = val;
                else if (/Speed/i.test(lab) && !speed) speed = val;
                else if (/حافظه/i.test(lab) && !mem) mem = val;
            });
            var ll = full.querySelector('#lastlogin');
            if (ll) login = (ll.textContent || '').replace(/\s+/g, ' ').replace(/Last login:\s*/i, '').trim();
            var m = up.match(/(\d+)\s*روز\(s\)\s*(\d+)\s*hour\(s\)\s*(\d+)\s*minute\(s\)/i)
                 || up.match(/(\d+)\s*day\(s\)\s*(\d+)\s*hour\(s\)\s*(\d+)\s*minute\(s\)/i);
            if (m) up = mtFa(m[1]) + ' روز، ' + mtFa(m[2]) + ' ساعت و ' + mtFa(m[3]) + ' دقیقه';
            if (!cpu && !up && !speed && !mem && !login) return;
            var row = function (label, value) {
                return '<div class="mt-sysrow"><span class="mt-syslabel">' + label + '</span>' +
                       '<span class="mt-sysval" dir="ltr">' + value + '</span></div>';
            };
            var html = '';
            if (cpu) html += row('پردازنده', cpu);
            if (speed) html += row('سرعت پردازنده', speed);
            if (up) html += row('زمان فعال بودن سیستم', up);
            if (mem) html += row('مصرف حافظه', mem);
            if (login) html += row('آخرین ورود', login.replace(/\.$/, ''));
            if (box.dataset.sig !== html) { box.innerHTML = html; box.dataset.sig = html; }
        };
        var sysTick = function () { migrateGauges(); buildSysInfo(); renderComm(); };
        setTimeout(function () { sysTick(); setTimeout(sysTick, 5000); }, 4000);
        setInterval(sysTick, 30000); /* JustGage values settle after first paint */
        $(document).ajaxComplete(function () { setTimeout(sysTick, 1200); });

        /* ---- 2c) sidebar surgery: hide the same-named first child every
           expandable item ships, drop the "میز کار" item (replaced by the
           custom dashboard), and insert faint group labels so ten root
           items read as organized sections ---- */
        document.querySelectorAll('.mt-sidebar #main-menu li.has-sub > ul').forEach(function (ul) {
            var pa = ul.parentNode.querySelector(':scope > a');
            var la = ul.querySelector(':scope > li > a');
            if (!pa || !la) return;
            var pl = (pa.querySelector('span') || pa).textContent.trim();
            var ll = (la.querySelector('span') || la).textContent.trim();
            if (pl && pl === ll) la.parentNode.style.display = 'none';
        });
        document.querySelectorAll('.mt-sidebar #main-menu li').forEach(function (li) {
            var a = li.querySelector(':scope > a');
            if (a && (a.textContent || '').trim() === 'میز کار') li.style.display = 'none';
        });
        (function menuGroups() {
            var menu = document.querySelector('.mt-sidebar #main-menu');
            if (!menu || menu.dataset.mtGroups === '1') return;
            menu.dataset.mtGroups = '1';
            var groups = {
                'سیستم': 'مرکز و عملیات',
                'ایمیل': 'ارتباطات',
                'گزارشات': 'گزارشات و تحلیل',
                'برنامه های جانبی': 'ابزارها'
            };
            document.querySelectorAll('.mt-sidebar #main-menu > li.root-level').forEach(function (li) {
                var t = ((li.querySelector(':scope > a span') || {}).textContent || '').trim();
                if (!groups[t]) return;
                var lab = document.createElement('li');
                lab.className = 'mt-menu-label';
                lab.textContent = groups[t];
                li.parentNode.insertBefore(lab, li);
            });
        })();

        /* ---- 3) hard drives: table text -> horizontal utilization bars ---- */
        /* when DOM data is stripped by module re-render, fetch fresh values
           from the applet's own getContent endpoint (presentation-only GET) */
        var mtDiskFetching = false;
        var fetchDiskData = function () {
            /* only the dashboard carries the HardDrives applet — never poll
               this endpoint from unrelated module pages */
            if (!document.querySelector('#Applet_HardDrives')) return;
            if (mtDiskFetching || window.__mtDisk) return;
            mtDiskFetching = true;
            window.jQuery.get('index.php', {
                menu: 'index', rawmode: 'yes',
                applet: 'HardDrives', action: 'getContent'
            }, function (html) {
                mtDiskFetching = false;
                var t = String(html);
                var m = t.match(/([\d.]+)\s*GB/i);
                var p = t.match(/percent=(\d{1,3})/) || t.match(/(\d{1,3})\s*%/);
                if (m && p) window.__mtDisk = { total: parseFloat(m[1]), usedPct: parseInt(p[1], 10) };
            }, 'text').fail(function () { mtDiskFetching = false; });
        };
        /* capture disk values from the applet ajax response the moment it
           arrives — the module strips this data on its own re-render */
        $(document).on('ajaxComplete', function (ev, xhr, settings) {
            try {
                var t = (xhr && xhr.responseText) || '';
                if (!t || t.indexOf('Hard Disk Capacity') === -1) return;
                var m = t.match(/Hard Disk Capacity:\s*([\d.]+)\s*GB/i);
                var used = t.match(/Used[^%]{0,120}?(\d{1,3})\s*%/i);
                var any = t.match(/(\d{1,3})\s*%/);
                if (m) {
                    var up = used ? parseInt(used[1], 10) : (any ? parseInt(any[1], 10) : null);
                    if (up === null || isNaN(up) || up < 0 || up > 100) up = any ? parseInt(any[1], 10) : null;
                    if (up !== null && !isNaN(up)) {
                        window.__mtDisk = { total: parseFloat(m[1]), usedPct: up };
                    }
                }
            } catch (e) {}
        });
        var migrateDisks = function () {
            /* harvest GB/% from the hidden applet text (first % is the
               donut center = used), then paint the health-card disk panel */
            var full = document.querySelector('#Applet_HardDrives .appletwindow_fullcontent');
            if (!full && !window.__mtDisk) return; /* not a dashboard page */
            if (full) {
                var txt = (full.textContent || '');
                var m = txt.match(/([\d.]+)\s*GB/i);
                var pct = txt.match(/(\d{1,3})\s*%/);
                if (m && pct) {
                    var up = parseInt(pct[1], 10);
                    if (up >= 0 && up <= 100) {
                        window.__mtDisk = { total: parseFloat(m[1]), usedPct: up };
                    }
                }
            }
            renderHealth();
        };
        /* keep the disk cache alive: fetch from the applet's own endpoint
           when a module re-render strips the DOM text (dashboard only) */
        var diskLoop = function () {
            if (!document.querySelector('#Applet_HardDrives')) return;
            if (!window.__mtDisk) fetchDiskData();
            migrateDisks();
        };
        setInterval(diskLoop, 3000);
        setTimeout(diskLoop, 6000);
        setTimeout(function () { migrateDisks(); setTimeout(migrateDisks, 5000); }, 4500);
        $(document).ajaxComplete(function () { setTimeout(migrateDisks, 1200); });

        /* ---- 4) Chart.js canvases (cdr/monitoring/channelusage/graphic_report):
           read the existing Chart instance data and re-render with ECharts ---- */
        var migrateChartJs = function (canvas) {
            if (!E() || canvas.dataset.mtDone === '1') return;
            if (!canvas.offsetParent) return; /* hidden — retry when visible */
            var host = null;
            try {
                var inst0 = canvas.__mtChart
                    || (window.Chart && window.Chart.getChart ? window.Chart.getChart(canvas) : null);
                if (!inst0 && window.Chart && window.Chart.instances) {
                    Object.keys(window.Chart.instances).some(function (k) {
                        var c = window.Chart.instances[k];
                        if (c && c.canvas === canvas) { inst0 = c; return true; }
                        return false;
                    });
                }
                if (!inst0 && canvas.id && window[canvas.id] && window[canvas.id].data) inst0 = window[canvas.id];
                if (!inst0 || !inst0.data) return;
                var labels = (inst0.data && inst0.data.labels) || [];
                var datasets = (inst0.data && inst0.data.datasets) || [];
                if (!labels.length || !datasets.length) return;
                var isTime = labels.length && typeof labels[0] === 'number' && labels[0] > 1e12;
                var isBars = datasets.every(function (d) { return (d.type || 'line') !== 'line'; });
                var series = datasets.map(function (d) { return { name: d.label, data: (d.data || []).slice() }; });
                host = document.createElement('div');
                host.className = 'mt-echart';
                host.style.cssText = 'width:100%;height:' + Math.max(260, canvas.offsetHeight) + 'px;direction:ltr;';
                canvas.style.display = 'none';
                canvas.parentNode.insertBefore(host, canvas);
                var opts = {};
                if (/channelusage/i.test(location.search)) { opts.area = true; opts.force = true; }
                var cats = labels.map(function (l) {
                    if (isTime) {
                        var d = new Date(l);
                        var hm = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
                        if (window.MTJalali) {
                            var j = window.MTJalali.toJalali(d);
                            return window.MTJalali.JDAYS[d.getDay()] + ' ' + hm;
                        }
                        return hm;
                    }
                    var m = String(l).match(/(\d{1,2}):(\d{2})\s*(am|pm)?/i);
                    if (m) {
                        var h = parseInt(m[1], 10) % 12;
                        if (/pm/i.test(m[3] || '')) h += 12;
                        return ('0' + h).slice(-2) + ':' + m[2];
                    }
                    return String(l);
                });
                if (isBars && datasets.length === 1) {
                    MyTelCharts.bar(host, null, cats, series, {});
                } else {
                    MyTelCharts.line(host, null, cats, series, opts);
                }
                canvas.dataset.mtDone = '1';
            } catch (e) {
                if (host && host.parentNode) host.parentNode.removeChild(host);
            }
        };
        var chartScan = function () {
            /* drop orphaned hosts whose module re-render removed their canvas
               — the ECharts canvas lives INSIDE the host, so count it */
            document.querySelectorAll('.mt-echart').forEach(function (el) {
                /* dashboard hosts are long-lived placeholders — never reap them */
                if (el.dataset.mtKeep === '1') return;
                var hasCanvas = !!el.querySelector('canvas');
                var inst = window.echarts.getInstanceByDom(el);
                if (!hasCanvas && (!inst || inst.isDisposed())) el.remove();
            });
            document.querySelectorAll('canvas').forEach(function (c) {
                if (c.id === 'myChart' || c.closest('.chart-container, #chart')) migrateChartJs(c);
            });
            /* Persian empty state for emptied chart containers (zero calls) */
            if (/cdrreport|monitoring/i.test(location.search)) {
                document.querySelectorAll('.chart-container').forEach(function (box) {
                    if (box.querySelector('canvas, .mt-echart, .mt-empty-state')) return;
                    var d = document.createElement('div');
                    d.className = 'mt-empty-state';
                    d.textContent = 'در بازه انتخاب‌شده تماسی ثبت نشده است.';
                    box.appendChild(d);
                });
            }
            /* re-run dashboard migrations after any module re-render wipe */
            if (location.search.indexOf('menu=index') !== -1 || location.pathname.endsWith('/index.php')) {
                migrateDisks(); migrateGauges();
            }
        };
        setTimeout(function () { chartScan(); setTimeout(chartScan, 5000); setTimeout(chartScan, 12000); setTimeout(chartScan, 20000); }, 5000);
        $(document).ajaxComplete(function () { setTimeout(chartScan, 800); });

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
                /* month title: big Persian line + tiny Gregorian line below */
                var title = cal.querySelector('.fc-header-title h2, .fc-center h2, .fc-toolbar .fc-title');
                var m = title ? title.textContent.match(/([A-Za-z]+)\s+(\d{4})/) : null;
                if (m && title && !title.dataset.mtT) {
                    var monthsEn = { January:1, February:2, March:3, April:4, May:5, June:6, July:7, August:8, September:9, October:10, November:11, December:12 };
                    var gm = monthsEn[m[1]], gy = +m[2];
                    if (gm) {
                        var first = new Date(gy, gm - 1, 1);
                        var jf = MT.toJalali(first);
                        var mid = MT.toJalali(new Date(gy, gm - 1, 15));
                        var jy = jf.jm === 12 && mid.jm === 1 ? mid.jy - 1 : mid.jy;
                        title.dataset.mtT = jf.jm + '-' + jy;
                        title.innerHTML = '<span>' + MT.JMONTHS[jf.jm - 1] + ' ' + MT.faNum(jy) + '</span>' +
                            '<span class="mt-greg-range">' + m[1] + ' ' + m[2] + '</span>';
                    }
                } else if (title && title.dataset.mtT) {
                    /* FullCalendar rewrote the h2 on month change — re-tag once */
                    if (title.textContent && !/mt-greg-range/.test(title.innerHTML)) title.dataset.mtT = '';
                }
                /* weekday headers (Persian short) + Friday column in red */
                cal.querySelectorAll('.fc-day-header').forEach(function (th, idx) {
                    var en = (th.textContent || '').trim();
                    var short = en.slice(0, 3);
                    if (MT.GDAYS_SHORT[short] !== undefined) th.textContent = MT.GDAYS_SHORT[short];
                    th.classList.toggle('fc-fri', idx === 5);
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
                    cell.classList.toggle('fc-fri', dt.getDay() === 5);
                    if (hol) { cell.setAttribute('title', hol); cell.classList.add('mt-has-name'); }
                });
            };
            apply();
            setInterval(apply, 1500);
        };
        setTimeout(jalaliCalendar, 1500);

        /* ---------- MyTel Jalali date picker (report date filters) ----------
           jQuery-UI datepicker ships Gregorian-only; the real input keeps the
           server format (dd M yyyy) but is hidden — the user sees a Persian
           mirror input and a native MyTel Jalali month grid. ---- */
        (function mtDatePicker() {
            var EN_M = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            var parseServer = function (v) {
                var m = String(v || '').match(/(\d{1,2})\s+([A-Za-z]{3})\w*\s+(\d{4})/);
                if (!m) return new Date();
                var mi = EN_M.indexOf(m[2].charAt(0).toUpperCase() + m[2].slice(1,3));
                var d = new Date(+m[3], mi, +m[1]);
                return isNaN(d) ? new Date() : d;
            };
            var toServer = function (d) {
                return ('0' + d.getDate()).slice(-2) + ' ' + EN_M[d.getMonth()] + ' ' + d.getFullYear();
            };
            var faD = function (j) { return MT.faNum(j.jd) + ' ' + MT.JMONTHS[j.jm - 1] + ' ' + MT.faNum(j.jy); };
            var open = null; /* current popup element */
            var lastMirror = null; /* focus returns here on close */
            var skipReopen = false; /* close → refocus must not reopen */
            var closePop = function () {
                if (!open) return;
                open.remove();
                open = null;
                if (lastMirror && lastMirror.isConnected) {
                    skipReopen = true;
                    try { lastMirror.focus({ preventScroll: true }); } catch (e) {}
                    setTimeout(function () { skipReopen = false; }, 120);
                }
            };
            document.addEventListener('keydown', function (ev) {
                if (ev.key === 'Escape' && open) closePop();
            });
            document.addEventListener('click', function (ev) {
                if (open && !open.contains(ev.target) && ev.target.className !== 'mt-date-mirror') closePop();
            }, true);

            var buildGrid = function (pop, jy, jm, selG) {
                var week = ['ش','ی','د','س','چ','پ','ج'];
                var html = '<div class="mt-dp-head">' +
                    '<button type="button" class="mt-dp-nav" data-nav="-1">›</button>' +
                    '<span class="mt-dp-title">' + MT.JMONTHS[jm - 1] + ' ' + MT.faNum(jy) + '</span>' +
                    '<button type="button" class="mt-dp-nav" data-nav="1">‹</button></div>' +
                    '<div class="mt-dp-week">' + week.map(function (w) { return '<span>' + w + '</span>'; }).join('') + '</div><div class="mt-dp-days">';
                var first = MT.toGregorian(jy, jm, 1);
                var lead = (first.getDay() + 1) % 7; /* Saturday-first */
                /* true month length via conversion round-trip (leap-safe) */
                var len = 29;
                while (len < 31 && MT.toJalali(MT.toGregorian(jy, jm, len + 1)).jm === jm) len++;
                var todayJ = MT.toJalali(new Date());
                for (var i = 0; i < lead; i++) html += '<span class="mt-dp-day out"></span>';
                for (var d = 1; d <= len; d++) {
                    var g = MT.toGregorian(jy, jm, d);
                    var cls = 'mt-dp-day';
                    if (g.getDay() === 5) cls += ' fri';
                    if (todayJ.jy === jy && todayJ.jm === jm && todayJ.jd === d) cls += ' today';
                    if (selG && g.toDateString() === selG.toDateString()) cls += ' sel';
                    html += '<button type="button" class="' + cls + '" data-jd="' + d + '">' + MT.faNum(d) + '</button>';
                }
                html += '</div><div class="mt-dp-foot">' +
                    '<button type="button" class="mt-dp-today-btn">امروز</button>' +
                    '<button type="button" class="mt-dp-clear-btn">پاک‌کردن</button>' +
                    '<span class="mt-dp-greg"></span></div>';
                pop.innerHTML = html;
                pop.dataset.jy = jy; pop.dataset.jm = jm;
                var gFirst = MT.toGregorian(jy, jm, 1);
                var gLast = MT.toGregorian(jy, jm, len);
                pop.querySelector('.mt-dp-greg').textContent = toServer(gFirst).slice(3) + ' – ' + toServer(gLast).slice(3);
            };

            var showPop = function (real, mirror) {
                closePop();
                var cur = parseServer(real.value);
                var j = MT.toJalali(cur);
                var pop = document.createElement('div');
                pop.className = 'mt-dp';
                document.body.appendChild(pop);
                var r = mirror.getBoundingClientRect();
                pop.style.top = (r.bottom + window.scrollY + 6) + 'px';
                var left = r.left + window.scrollX;
                left = Math.max(8, Math.min(left, window.scrollX + document.documentElement.clientWidth - 288));
                pop.style.left = left + 'px';
                open = pop;
                lastMirror = mirror;
                buildGrid(pop, j.jy, j.jm, real.value ? cur : null);
                /* keyboard path: focus lands inside the popup, Escape leaves */
                var focusTarget = pop.querySelector('.mt-dp-day.sel') || pop.querySelector('.mt-dp-day.today') || pop.querySelector('.mt-dp-nav');
                if (focusTarget) try { focusTarget.focus({ preventScroll: true }); } catch (e) {}
                pop.addEventListener('click', function (ev) {
                    var t = ev.target;
                    if (t.classList.contains('mt-dp-nav')) {
                        var njm = +pop.dataset.jm + (+t.dataset.nav), njy = +pop.dataset.jy;
                        if (njm < 1) { njm = 12; njy--; } if (njm > 12) { njm = 1; njy++; }
                        buildGrid(pop, njy, njm, real.value ? parseServer(real.value) : null);
                        /* innerHTML rebuild dropped the focused nav button —
                           put focus back so Enter keeps navigating */
                        var again = pop.querySelector('.mt-dp-nav[data-nav="' + t.dataset.nav + '"]');
                        if (again) try { again.focus({ preventScroll: true }); } catch (e) {}
                    } else if (t.classList.contains('mt-dp-today-btn')) {
                        var now = new Date();
                        real.value = toServer(now);
                        mirror.value = faD(MT.toJalali(now));
                        $(real).trigger('change');
                        closePop();
                    } else if (t.classList.contains('mt-dp-clear-btn')) {
                        real.value = '';
                        mirror.value = '';
                        $(real).trigger('change');
                        closePop();
                    } else if (t.classList.contains('mt-dp-day') && t.dataset.jd) {
                        var g = MT.toGregorian(+pop.dataset.jy, +pop.dataset.jm, +t.dataset.jd);
                        real.value = toServer(g);
                        mirror.value = faD(MT.toJalali(g));
                        $(real).trigger('change');
                        closePop();
                    }
                });
            };

            var wire = function () {
                document.querySelectorAll('input.hasDatepicker').forEach(function (real) {
                    if (real.dataset.mtPick === '1' || real.classList.contains('mt-date-mirror')) return;
                    real.dataset.mtPick = '1';
                    real.classList.add('mt-date-real');
                    var mirror = document.createElement('input');
                    mirror.type = 'text';
                    mirror.readOnly = true;
                    mirror.className = 'mt-date-mirror';
                    mirror.setAttribute('autocomplete', 'off');
                    mirror.placeholder = 'انتخاب تاریخ';
                    /* an empty real input must show as empty, not as today */
                    mirror.value = real.value ? faD(MT.toJalali(parseServer(real.value))) : '';
                    real.insertAdjacentElement('afterend', mirror);
                    /* keep the mirror honest when the module rewrites the real value */
                    new MutationObserver(function () {
                        mirror.value = real.value ? faD(MT.toJalali(parseServer(real.value))) : '';
                    }).observe(real, { attributes: true, attributeFilter: ['value'] });
                    var syncVal = function () { mirror.value = real.value ? faD(MT.toJalali(parseServer(real.value))) : ''; };
                    real.addEventListener('change', syncVal);
                    mirror.addEventListener('click', function (ev) {
                        ev.preventDefault();
                        showPop(real, mirror);
                    });
                    mirror.addEventListener('focus', function (ev) {
                        ev.preventDefault();
                        if (skipReopen) return;
                        this.blur();
                        showPop(real, mirror);
                    });
                });
                /* hide trigger buttons the stock picker appended next to hidden inputs */
                document.querySelectorAll('button.ui-datepicker-trigger').forEach(function (b) {
                    var prev = b.previousElementSibling;
                    if (prev && prev.classList && prev.classList.contains('mt-date-real')) b.style.display = 'none';
                });
            };
            wire();
            setInterval(wire, 2000);
            $(document).ajaxComplete(function () { setTimeout(wire, 400); });
        })();

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

        /* ---------- Communication Activity: the upstream PHP glues Persian
           fragments in broken order — parse the applet text (works hidden)
           and paint the dashboard "وضعیت ارتباطات" card instead ---------- */
        var renderComm = function () {
            var box = document.getElementById('mt-dash-comm');
            if (!box) return;
            var el = document.querySelector('#Applet_CommunicationActivity');
            if (!el) return;
            var txt = (el.textContent || el.innerText || '').replace(/\s+/g, ' ');
            var grab = function (re) { var m = txt.match(re); if (!m) return null; for (var i = 1; i < m.length; i++) { if (m[i] !== undefined) return m[i]; } return null; };
            var internal = grab(/\((\d+)\s*تماس هاي داخلي\)|\((\d+)\s*تماس های داخلی\)/);
            var external = grab(/\((\d+)\s*تماس هاي خارجي\)|\((\d+)\s*تماس های خارجی\)/);
            /* the applet mixes Arabic/Persian kaf-yeh forms inconsistently —
               anchor on the unique Latin "channels" word instead */
            var channels = grab(/(\d+)\s*channels/i) || grab(/كل تماس ها:?\s*(\d+)|کل تماس ها:?\s*(\d+)/);
            var waiting = grab(/تماس هاي در صف انتظار:?\s*(\d+)|(\d+)\s*منتظر|تماس های در صف انتظار:?\s*(\d+)/);
            var sip = grab(/SIP داخلي هاي\s*\((\d+)\)|SIP داخلی های\s*\((\d+)\)/);
            var pjsip = grab(/PJSIP داخلي هاي\s*\((\d+)\)|PJSIP داخلی های\s*\((\d+)\)/);
            var iax = grab(/IAX داخلي هاي\s*\((\d+)\)|IAX داخلی های\s*\((\d+)\)/);
            var trunks = grab(/ترانك ها\s*\((\d+)\)|ترانک ها\s*\((\d+)\)/);
            var rxT = grab(/\(([\d.]+\s*k?B\/s)\)\s*<=\s*RX/);
            var txT = grab(/TX\s*=>\s*\(([\d.]+\s*k?B\/s)\)/);
            if (channels === null && trunks === null) return; /* data not complete yet */
            var regCount = function (base) {
                var after = txt.slice(txt.indexOf(base));
                var r = after.match(/\((\d+)\s*ثبت شده\)/);
                return r ? r[1] : null;
            };
            var regSum = 0, regKnown = false;
            [['SIP داخلي', sip], ['PJSIP داخلي', pjsip], ['IAX داخلي', iax]].forEach(function (p) {
                var rc = regCount(p[0]);
                if (p[1] !== null && rc !== null) { regKnown = true; regSum += parseInt(rc, 10) || 0; }
            });
            if (regKnown) window.__mtReg = regSum;
            var fig = document.getElementById('mt-fig-reg');
            if (fig && window.__mtReg !== undefined) fig.textContent = mtFa(window.__mtReg);
            var figs = '';
            if (channels !== null) figs += '<div class="mt-cfig"><b>' + mtFa(channels) + '</b><span>کانال فعال</span></div>';
            if (waiting !== null) figs += '<div class="mt-cfig"><b>' + mtFa(waiting) + '</b><span>در صف انتظار</span></div>';
            if (trunks !== null) figs += '<div class="mt-cfig"><b>' + mtFa(trunks) + '</b><span>ترانک</span></div>';
            var regRow = function (label, base, total) {
                if (total === null) return '';
                var rc = regCount(base);
                return '<div class="mt-crow"><span>' + label + '</span><b dir="ltr">' +
                    (rc !== null ? mtFa(rc) : '—') + ' / ' + mtFa(total) + '</b></div>';
            };
            var regs = regRow('داخلی‌های SIP', 'SIP داخلي', sip) +
                       regRow('داخلی‌های PJSIP', 'PJSIP داخلي', pjsip) +
                       regRow('داخلی‌های IAX', 'IAX داخلي', iax);
            var inner = '';
            if (internal !== null || external !== null)
                inner += '<div class="mt-cmix">ترکیب تماس‌ها — داخلی ' + mtFa(internal || '0') + ' / خارجی ' + mtFa(external || '0') + '</div>';
            inner += (figs ? '<div class="mt-cfigs">' + figs + '</div>' : '') +
                     (regs ? '<div class="mt-crows">' + regs + '</div>' : '');
            if (rxT || txT) {
                inner += '<div class="mt-ctraffic"><span>ترافیک شبکه</span><b dir="ltr">↓ ' + (rxT || '—') + ' • ↑ ' + (txT || '—') + '</b></div>';
            }
            if (!inner) return;
            if (box.dataset.sig !== inner) { box.innerHTML = inner; box.dataset.sig = inner; }
        };
        setTimeout(renderComm, 5000);
        setInterval(renderComm, 30000);
    });
})(jQuery);
