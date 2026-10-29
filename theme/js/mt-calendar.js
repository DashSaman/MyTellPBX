(function (window, document) {
    'use strict';

    var VERSION = '1.0.0';

    if (window.MTCalendar && window.MTCalendar.version === VERSION) {
        window.MTCalendar.start();
        return;
    }

    if (window.MTCalendar &&
        typeof window.MTCalendar.destroy === 'function') {
        window.MTCalendar.destroy();
    }

    var state = { jy: null, jm: null };
    var binding = null;
    var applyTimer = null;
    var pollTimer = null;
    var pollGeneration = 0;
    var pollDeadline = 0;
    var pendingDate = null;
    var sideSync = null;
    var sideOwner = null;
    var lastObserved = '';
    var lastRender = '';
    var applying = false;

    var APPLY_MS = 1500;
    var POLL_MS = 125;
    var POLL_LIMIT_MS = 12000;

    var weekdayIndexes = [6, 0, 1, 2, 3, 4, 5];
    var weekdayLetters = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];
    var gregorianMonths = [
        'ژانویه', 'فوریه', 'مارس', 'آوریل',
        'مه', 'ژوئن', 'ژوئیه', 'اوت',
        'سپتامبر', 'اکتبر', 'نوامبر', 'دسامبر'
    ];

    function mt() {
        return window.MTJalali;
    }

    function fa(value) {
        return mt().faNum(String(value));
    }

    function pad(value) {
        return String(value).padStart(2, '0');
    }

    function node(tag, className, text) {
        var el = document.createElement(tag);
        if (className) el.className = className;
        if (text !== undefined) el.textContent = text;
        return el;
    }

    function button(className, text, action) {
        var el = node('button', className, text);
        el.type = 'button';
        if (action) el.dataset.action = action;
        return el;
    }

    /*
     * Preserve FullCalendar/Moment calendar fields rather than converting
     * an ambiguously-zoned Moment through toDate().
     */
    function parts(value) {
        if (!value) return null;

        if (typeof value.year === 'function' &&
            typeof value.month === 'function' &&
            typeof value.date === 'function') {
            if (typeof value.isValid === 'function' && !value.isValid()) {
                return null;
            }

            return {
                y: value.year(),
                m: value.month(),
                d: value.date(),
                h: typeof value.hours === 'function' ? value.hours() : 0,
                min: typeof value.minutes === 'function' ? value.minutes() : 0,
                s: typeof value.seconds === 'function' ? value.seconds() : 0,
                ms: typeof value.milliseconds === 'function'
                    ? value.milliseconds() : 0
            };
        }

        var date;

        if (value instanceof Date) {
            date = value;
        } else if (typeof value === 'string') {
            var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);

            if (match) {
                date = new Date(+match[1], +match[2] - 1, +match[3], 12);
                return {
                    y: date.getFullYear(),
                    m: date.getMonth(),
                    d: date.getDate(),
                    h: 0, min: 0, s: 0, ms: 0
                };
            }

            if (window.moment) {
                return parts(window.moment(value));
            }

            date = new Date(value);
        } else {
            date = new Date(value);
        }

        if (!Number.isFinite(date.getTime())) return null;

        return {
            y: date.getFullYear(),
            m: date.getMonth(),
            d: date.getDate(),
            h: date.getHours(),
            min: date.getMinutes(),
            s: date.getSeconds(),
            ms: date.getMilliseconds()
        };
    }

    function civilDate(value) {
        var p = parts(value);
        return p ? new Date(p.y, p.m, p.d, 12) : null;
    }

    function dateKey(value) {
        var p = parts(value);
        return p ? p.y + '-' + pad(p.m + 1) + '-' + pad(p.d) : '';
    }

    /*
     * Calendar-field timestamps: midnight boundaries remain correct even
     * where a historical timezone transition made local midnight invalid.
     */
    function dayStamp(value) {
        var p = parts(value);
        return p ? Date.UTC(p.y, p.m, p.d) : NaN;
    }

    function eventStamp(value) {
        var p = parts(value);
        return p
            ? Date.UTC(p.y, p.m, p.d, p.h, p.min, p.s, p.ms)
            : NaN;
    }

    function addDays(date, amount) {
        return new Date(
            date.getFullYear(),
            date.getMonth(),
            date.getDate() + amount,
            12
        );
    }

    function monthAt(jy, jm, amount) {
        var index = jy * 12 + jm - 1 + amount;
        return {
            jy: Math.floor(index / 12),
            jm: ((index % 12) + 12) % 12 + 1
        };
    }

    function monthWindow() {
        var next = monthAt(state.jy, state.jm, 1);
        var first = civilDate(mt().toGregorian(state.jy, state.jm, 1));
        var end = civilDate(mt().toGregorian(next.jy, next.jm, 1));

        var length = mt().j2d(next.jy, next.jm, 1) -
            mt().j2d(state.jy, state.jm, 1);

        var leading = (first.getDay() + 1) % 7;
        var count = Math.ceil((leading + length) / 7) * 7;
        var gridStart = addDays(first, -leading);

        return {
            first: first,
            end: end,
            last: addDays(end, -1),
            startStamp: dayStamp(first),
            endStamp: dayStamp(end),
            gridStart: gridStart,
            count: count
        };
    }

    function call(method) {
        var args = Array.prototype.slice.call(arguments, 1);
        return binding.$el.fullCalendar.apply(
            binding.$el,
            [method].concat(args)
        );
    }

    function viewName(view) {
        return view ? String(view.name || view.type || '') : '';
    }

    function isMonth(view) {
        return viewName(view) === 'month';
    }

    function context() {
        if (!binding) return null;

        try {
            var view = call('getView');
            var date = civilDate(call('getDate'));

            if (!view || !date) return null;

            return {
                view: view,
                date: date,
                name: viewName(view),
                start: dateKey(view.start),
                end: dateKey(view.end)
            };
        } catch (error) {
            return null;
        }
    }

    function contextKey(ctx) {
        return [
            ctx.name, ctx.start, ctx.end, dateKey(ctx.date)
        ].join('|');
    }

    function targetReady(ctx) {
        if (!pendingDate) return true;
        if (dateKey(ctx.date) !== pendingDate) return false;

        var start = dayStamp(ctx.view.start);
        var end = dayStamp(ctx.view.end);
        var selected = dayStamp(ctx.date);

        /*
         * A changed view.start signals a new range. Navigation within the
         * same Gregorian month legitimately leaves view.start unchanged.
         * In both cases, the selected date must belong to the rendered view.
         */
        return !Number.isFinite(start) || !Number.isFinite(end) ||
            (selected >= start && selected < end);
    }

    function option(name) {
        try {
            return call('option', name);
        } catch (error) {
            return binding.instance.options
                ? binding.instance.options[name] : undefined;
        }
    }

    function defaultDuration(allDay) {
        var value = option(
            allDay ? 'defaultAllDayEventDuration' : 'defaultTimedEventDuration'
        );

        if (value !== undefined && value !== null && window.moment) {
            var duration = window.moment.duration(value).asMilliseconds();
            if (Number.isFinite(duration) && duration > 0) return duration;
        }

        return allDay ? 86400000 : 7200000;
    }

    function hash(text) {
        var result = 0;
        for (var i = 0; i < text.length; i++) {
            result = ((result * 31) + text.charCodeAt(i)) >>> 0;
        }
        return result;
    }

    function eventsForMonth(win) {
        var cached;

        try {
            cached = call('clientEvents') || [];
        } catch (error) {
            cached = [];
        }

        var result = [];

        cached.forEach(function (event, index) {
            var startParts = parts(event.start);
            var start = eventStamp(event.start);

            if (!startParts || !Number.isFinite(start)) return;

            var allDay = !!event.allDay;
            var end = event.end
                ? eventStamp(event.end)
                : start + defaultDuration(allDay);

            if (!Number.isFinite(end) || end <= start) return;

            // FullCalendar ends are exclusive.
            if (start >= win.endStamp || end <= win.startStamp) return;

            var title = String(event.title || 'بدون عنوان');
            var identity = String(
                event._id !== undefined ? event._id :
                event.id !== undefined ? event.id : title
            );

            var time = allDay
                ? ''
                : fa(pad(startParts.h) + ':' + pad(startParts.min));

            var startDate = new Date(
                startParts.y, startParts.m, startParts.d, 12
            );

            var j = mt().toJalali(startDate);
            var startLabel = fa(j.jy) + '/' + fa(pad(j.jm)) +
                '/' + fa(pad(j.jd));

            result.push({
                start: start,
                end: end,
                allDay: allDay,
                title: title,
                time: time,
                startDate: dateKey(startDate),
                key: identity + '|' + start + '|' + end + '|' + index,
                variant: hash(identity) % 3,
                tooltip: title + ' — ' + startLabel + '، ' +
                    (allDay ? 'تمام روز' : time)
            });
        });

        result.sort(function (a, b) {
            if (a.allDay !== b.allDay) return a.allDay ? -1 : 1;
            if (a.start !== b.start) return a.start - b.start;
            if (a.title < b.title) return -1;
            if (a.title > b.title) return 1;
            return a.key < b.key ? -1 : a.key > b.key ? 1 : 0;
        });

        return result;
    }

    function gregorianLabel(date) {
        return fa(date.getDate()) + ' ' +
            gregorianMonths[date.getMonth()] + ' ' +
            fa(date.getFullYear());
    }

    function makeRoot() {
        var root = node('section', 'mt-jmonth');
        root.lang = 'fa';
        root.dir = 'rtl';
        root.setAttribute('aria-label', 'تقویم ماهانه شمسی');

        var header = node('div', 'mt-jmonth-header');
        var heading = node('div', 'mt-jmonth-heading');

        var title = node('h2', 'mt-jmonth-title');
        title.id = 'mt-jmonth-title';

        var range = node('p', 'mt-jmonth-range');
        heading.append(title, range);

        var nav = node('nav', 'mt-jmonth-nav');
        nav.setAttribute('aria-label', 'جابجایی ماه');

        nav.append(
            button('mt-jnav mt-jnav-today', 'امروز', 'today'),
            button('mt-jnav', 'ماه قبل', 'prev'),
            button('mt-jnav', 'ماه بعد', 'next')
        );

        nav.children[1].prepend(node('span', 'mt-jarrow', '›'));
        nav.children[2].append(node('span', 'mt-jarrow', '‹'));

        header.append(heading, nav);

        var status = node('p', 'mt-jmonth-status');
        status.setAttribute('role', 'status');
        status.setAttribute('aria-live', 'polite');

        var scroller = node('div', 'mt-jmonth-scroll');
        var table = node('table', 'mt-jmonth-table');
        table.setAttribute('aria-labelledby', title.id);

        var thead = node('thead');
        var row = node('tr');

        weekdayIndexes.forEach(function (weekday, index) {
            var th = node(
                'th',
                index === 6 ? 'mt-jweekday mt-jfriday' : 'mt-jweekday'
            );
            th.scope = 'col';

            var fullName = mt().JDAYS[weekday];
            th.append(
                node('span', 'mt-jweekday-letter', weekdayLetters[index]),
                node('span', 'mt-jsr-only', fullName)
            );
            th.title = fullName;
            row.appendChild(th);
        });

        thead.appendChild(row);
        table.append(thead, node('tbody'));
        scroller.appendChild(table);
        root.append(header, status, scroller);

        root.addEventListener('click', handleClick);

        return {
            root: root,
            title: title,
            range: range,
            status: status,
            tbody: table.tBodies[0]
        };
    }

    function activeFocusKey() {
        var active = document.activeElement;
        return active && binding.root.contains(active)
            ? active.getAttribute('data-focus-key') : null;
    }

    function restoreFocus(key) {
        if (!key) return;

        var buttons = binding.root.querySelectorAll('[data-focus-key]');

        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].getAttribute('data-focus-key') === key) {
                buttons[i].focus({ preventScroll: true });
                return;
            }
        }
    }

    function render(ctx) {
        var win = monthWindow();
        var events = eventsForMonth(win);
        var todayKey = dateKey(new Date());

        var signature = JSON.stringify([
            state.jy,
            state.jm,
            todayKey,
            events.map(function (event) {
                return [
                    event.key, event.title, event.time,
                    event.start, event.end, event.allDay, event.variant
                ];
            })
        ]);

        binding.title.textContent =
            mt().JMONTHS[state.jm - 1] + ' ' + fa(state.jy);

        binding.range.textContent =
            gregorianLabel(win.first) + ' تا ' +
            gregorianLabel(win.last) + ' (میلادی)';

        if (signature === lastRender && binding.tbody.children.length) return;

        var focusKey = activeFocusKey();
        var fragment = document.createDocumentFragment();
        var row;

        for (var i = 0; i < win.count; i++) {
            if (i % 7 === 0) {
                row = node('tr');
                fragment.appendChild(row);
            }

            var date = addDays(win.gridStart, i);
            var key = dateKey(date);
            var j = mt().toJalali(date);
            var holiday = mt().holidayName(j.jy, j.jm, j.jd);
            var current = j.jy === state.jy && j.jm === state.jm;
            var today = key === todayKey;
            var friday = date.getDay() === 5;

            var classes = 'mt-jcell';
            if (!current) classes += ' mt-joutside';
            if (today) classes += ' mt-jtoday';
            if (friday) classes += ' mt-jfriday';
            if (holiday) classes += ' mt-jholiday';

            var cell = node('td', classes);
            cell.dataset.date = key;

            var body = node('div', 'mt-jcell-body');
            var dates = node('div', 'mt-jdates');

            var dayButton = button('mt-jday-open');
            dayButton.dataset.focusKey = 'day:' + key;
            dayButton.setAttribute(
                'aria-label',
                mt().JDAYS[date.getDay()] + ' ' + fa(j.jd) + ' ' +
                mt().JMONTHS[j.jm - 1] + ' ' + fa(j.jy) +
                (holiday ? '، ' + holiday : '') +
                '؛ باز کردن نمای روز'
            );

            if (today) dayButton.setAttribute('aria-current', 'date');

            dayButton.appendChild(node('span', 'mt-jday-number', fa(j.jd)));

            if (today) {
                dayButton.appendChild(node('span', 'mt-jtoday-label', 'امروز'));
            }

            var gregorian = node('span', 'mt-jgregorian', String(date.getDate()));
            gregorian.dir = 'ltr';
            gregorian.title = gregorianLabel(date);

            dates.append(dayButton, gregorian);
            body.appendChild(dates);

            var holidayLine = node(
                'div',
                'mt-jholiday-label',
                holiday || '\u00a0'
            );

            if (holiday) holidayLine.title = holiday;
            else holidayLine.setAttribute('aria-hidden', 'true');

            body.appendChild(holidayLine);

            var eventList = node('div', 'mt-jevents');
            var dayStart = dayStamp(date);
            var dayEnd = dayStamp(addDays(date, 1));

            events.forEach(function (event) {
                if (event.start >= dayEnd || event.end <= dayStart) return;

                var chip = button(
                    'mt-jevent mt-jevent-v' + event.variant
                );

                chip.dataset.eventStart = event.startDate;
                chip.dataset.focusKey = 'event:' + key + ':' + event.key;
                chip.title = event.tooltip;
                chip.setAttribute('aria-label', event.tooltip);

                if (event.start < dayStart) {
                    chip.classList.add('mt-jevent-continuation');
                }

                var dot = node('span', 'mt-jevent-dot');
                dot.setAttribute('aria-hidden', 'true');
                chip.appendChild(dot);

                if (!event.allDay) {
                    var time = node('bdi', 'mt-jevent-time', event.time);
                    time.dir = 'ltr';
                    chip.appendChild(time);
                }

                var label = node('bdi', 'mt-jevent-title', event.title);
                label.dir = 'auto';
                chip.appendChild(label);

                eventList.appendChild(chip);
            });

            body.appendChild(eventList);
            cell.appendChild(body);
            row.appendChild(cell);
        }

        binding.tbody.replaceChildren(fragment);
        lastRender = signature;
        restoreFocus(focusKey);
    }

    function dayViewName() {
        /*
         * Keep the portal's actual view name. Standard FC2 commonly uses
         * agendaDay/basicDay; this portal may expose its own "day" alias.
         */
        var names = ['day', 'agendaDay', 'basicDay'];

        for (var i = 0; i < names.length; i++) {
            var name = names[i];
            if (binding.el.querySelector(
                '.fc-' + name + '-button, .fc-button-' + name
            )) {
                return name;
            }
        }

        return 'day';
    }

    function openDay(key) {
        var date = civilDate(key);
        if (!date || !binding) return;

        call('gotoDate', date);
        call('changeView', dayViewName());
        apply();
    }

    function navigate(amount) {
        var next = monthAt(state.jy, state.jm, amount);
        call('gotoDate', civilDate(mt().toGregorian(next.jy, next.jm, 1)));
    }

    function handleClick(event) {
        if (!binding || !binding.root.contains(event.target)) return;

        var action = event.target.closest('[data-action]');
        var chip = event.target.closest('.mt-jevent');
        var cell = event.target.closest('.mt-jcell');

        if (!action && !chip && !cell) return;

        event.preventDefault();
        event.stopPropagation();

        if (action) {
            if (action.dataset.action === 'today') {
                call('gotoDate', civilDate(new Date()));
            } else {
                navigate(action.dataset.action === 'prev' ? -1 : 1);
            }
            return;
        }

        if (chip) {
            openDay(chip.dataset.eventStart);
            return;
        }

        // Do not navigate when the user was selecting text inside a cell.
        var selection = window.getSelection();
        if (selection && !selection.isCollapsed) return;

        openDay(cell.dataset.date);
    }

    function cancelPolling() {
        pollGeneration++;
        if (pollTimer !== null) window.clearTimeout(pollTimer);
        pollTimer = null;
        pendingDate = null;
    }

    function beginPolling(target) {
        cancelPolling();

        pendingDate = target ? dateKey(target) : null;
        pollDeadline = Date.now() + POLL_LIMIT_MS;

        var generation = pollGeneration;

        function poll() {
            if (generation !== pollGeneration || !binding) return;

            apply(true);

            if (generation !== pollGeneration || !binding) return;

            if (Date.now() < pollDeadline) {
                pollTimer = window.setTimeout(poll, POLL_MS);
            } else {
                pollTimer = null;

                if (pendingDate) {
                    binding.status.textContent =
                        'همگام‌سازی تاریخ کامل نشد؛ دوباره تلاش کنید.';
                    binding.root.setAttribute('aria-busy', 'false');
                }

                pendingDate = null;
            }
        }

        pollTimer = window.setTimeout(poll, POLL_MS);
    }

    function afterNavigation(target) {
        if (!binding) return;
        beginPolling(target);
        apply(true);
    }

    function attach(el, instance, $el) {
        var ui = makeRoot();

        binding = {
            el: el,
            instance: instance,
            $el: $el,
            root: ui.root,
            title: ui.title,
            range: ui.range,
            status: ui.status,
            tbody: ui.tbody,
            originalGotoDate: instance.gotoDate,
            originalChangeView: instance.changeView,
            wrappedGotoDate: null,
            wrappedChangeView: null,
            monthActive: false
        };

        var attached = binding;

        if (typeof attached.originalGotoDate === 'function') {
            attached.wrappedGotoDate = function () {
                var args = Array.prototype.slice.call(arguments);
                var target = null;

                /*
                 * Compatibility adapter for the surviving side panel:
                 * gotoDate(year, zeroBasedMonth, day) -> gotoDate(Date).
                 */
                if (args.length >= 3 &&
                    typeof args[0] === 'number' &&
                    typeof args[1] === 'number' &&
                    typeof args[2] === 'number') {
                    target = new Date(args[0], args[1], args[2], 12);
                    args = [target];
                } else if (args.length) {
                    target = civilDate(args[0]);
                }

                var result = attached.originalGotoDate.apply(this, args);

                if (binding === attached) afterNavigation(target);
                return result;
            };

            instance.gotoDate = attached.wrappedGotoDate;
        }

        if (typeof attached.originalChangeView === 'function') {
            attached.wrappedChangeView = function () {
                var result = attached.originalChangeView.apply(this, arguments);

                if (binding === attached) {
                    var ctx = context();
                    afterNavigation(ctx ? ctx.date : null);
                }

                return result;
            };

            instance.changeView = attached.wrappedChangeView;
        }

        el.appendChild(ui.root);
        lastObserved = '';
        lastRender = '';
    }

    function detach() {
        cancelPolling();
        if (!binding) return;

        var old = binding;
        binding = null;

        if (old.instance.gotoDate === old.wrappedGotoDate) {
            old.instance.gotoDate = old.originalGotoDate;
        }

        if (old.instance.changeView === old.wrappedChangeView) {
            old.instance.changeView = old.originalChangeView;
        }

        old.el.classList.remove('mt-jmonth-active');
        old.root.remove();
        lastObserved = '';
        lastRender = '';
    }

    function ensureBinding() {
        var $ = window.jQuery;
        var el = document.getElementById('calendar_main');

        if (!$ || !$.fn.fullCalendar || !mt() || !el) {
            detach();
            return false;
        }

        var $el = $(el);
        var instance = $el.data('fullCalendar');

        if (!instance) {
            detach();
            return false;
        }

        if (binding &&
            (binding.el !== el || binding.instance !== instance)) {
            detach();
        }

        if (!binding) attach(el, instance, $el);

        // Full module renders may clear children without replacing the node.
        if (!binding.root.isConnected) {
            el.appendChild(binding.root);
            lastRender = '';
        }

        return true;
    }

    function runSideSync() {
        if (!sideSync) return;

        if (sideOwner && !sideOwner.isConnected) {
            sideSync = null;
            sideOwner = null;
            return;
        }

        try {
            sideSync();
        } catch (error) {
            // The side panel must not prevent the main view from updating.
            if (window.console) {
                console.warn('MTCalendar: side-panel sync failed', error);
            }
        }
    }

    function apply(fromPoll) {
        if (applying) return;

        applying = true;

        try {
            if (!ensureBinding()) return;

            var ctx = context();
            if (!ctx) return;

            var month = isMonth(ctx.view);
            var wasMonth = binding.monthActive;

            binding.monthActive = month;
            binding.el.classList.toggle('mt-jmonth-active', month);
            binding.root.hidden = !month;

            /*
             * Stock week/day may have rendered while its container was
             * hidden. Recalculate dimensions after restoring it.
             */
            if (wasMonth && !month) {
                if (typeof binding.instance.updateSize === 'function') {
                    binding.instance.updateSize();
                } else {
                    call('render');
                }
            }

            var observed = contextKey(ctx);
            var changed = observed !== lastObserved;
            lastObserved = observed;

            if (!month) {
                pendingDate = null;
                binding.status.textContent = '';
                binding.root.setAttribute('aria-busy', 'false');
                runSideSync();
                return;
            }

            if (!targetReady(ctx)) {
                binding.status.textContent = 'در حال همگام‌سازی تاریخ…';
                binding.root.setAttribute('aria-busy', 'true');
                return;
            }

            pendingDate = null;
            binding.status.textContent = '';
            binding.root.setAttribute('aria-busy', 'false');

            var j = mt().toJalali(ctx.date);
            state.jy = j.jy;
            state.jm = j.jm;

            render(ctx);
            runSideSync();

            /*
             * Detect navigation that bypassed the patched public methods,
             * including a module-driven rerender.
             */
            if (changed && !fromPoll) beginPolling(ctx.date);
        } finally {
            applying = false;
        }
    }

    function start() {
        if (applyTimer !== null) return;

        apply();
        applyTimer = window.setInterval(function () {
            apply();
        }, APPLY_MS);
    }

    function destroy() {
        if (applyTimer !== null) window.clearInterval(applyTimer);
        applyTimer = null;
        detach();
        sideSync = null;
        sideOwner = null;
    }

    window.MTCalendar = {
        version: VERSION,
        state: state,
        start: start,
        apply: function () { apply(); },
        render: function () {
            lastRender = '';
            apply();
        },
        getDate: function () {
            var ctx = context();
            return ctx ? civilDate(ctx.date) : civilDate(new Date());
        },
        setSideSync: function (callback, owner) {
            sideSync = typeof callback === 'function' ? callback : null;
            sideOwner = owner || null;
            runSideSync();
        },
        destroy: destroy
    };

    start();

})(window, document);
