(function mtCDRFilters(window, document) {
    'use strict';

    if (window.MTCDRFilters) {
        window.MTCDRFilters.wire();
        return;
    }

    var current = null;
    var interval = null;
    var started = false;
    var disposed = false;
    var serial = 0;

    function asciiDigits(value) {
        return String(value == null ? '' : value)
            .replace(/[۰-۹]/g, function (digit) {
                return String(digit.charCodeAt(0) - 1776);
            })
            .replace(/[٠-٩]/g, function (digit) {
                return String(digit.charCodeAt(0) - 1632);
            });
    }

    function cleanText(value) {
        var text;

        if (value && typeof value === 'object' && value.nodeType) {
            text = value.textContent || '';
        } else {
            text = String(value == null ? '' : value);

            if (/[<&]/.test(text)) {
                /*
                 * Template contents stay inert. Never insert table data
                 * as active markup into the document.
                 */
                var template = document.createElement('template');
                template.innerHTML = text;
                text = template.content.textContent || '';
            }
        }

        return text
            .replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, '')
            .replace(/\u00a0/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function normalizeNumber(value) {
        return asciiDigits(value)
            .replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, '')
            .trim();
    }

    function readBound(value) {
        var text = normalizeNumber(value);

        if (!text) return { valid: true, value: null };

        if (!/^\d+$/.test(text)) {
            return { valid: false, value: null };
        }

        var number = Number(text);

        return {
            valid: Number.isSafeInteger(number),
            value: number
        };
    }

    function durationSeconds(value) {
        var text = asciiDigits(cleanText(value)).replace(/٫/g, '.');

        if (/^\d+(?:\.\d+)?$/.test(text)) {
            var numeric = Number(text);
            return Number.isFinite(numeric) ? numeric : null;
        }

        /*
         * Stock Issabel also renders durations in unit grammar
         * ("42s", "3m 5s", "1h 2m 3s") when the seconds toggle is off.
         * Accept the full grammar; never parseFloat the prefix —
         * "3m 5s" must be 185 seconds, not 3.
         */
        var unitMatch =
            /^(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+(?:\.\d+)?)\s*m)?\s*(?:(\d+(?:\.\d+)?)\s*s)?$/i
                .exec(text.replace(/\s+/g, ' ').trim());
        if (unitMatch && (unitMatch[1] || unitMatch[2] || unitMatch[3])) {
            var unitSeconds = 0;
            if (unitMatch[1]) unitSeconds += Number(unitMatch[1]) * 3600;
            if (unitMatch[2]) unitSeconds += Number(unitMatch[2]) * 60;
            if (unitMatch[3]) unitSeconds += Number(unitMatch[3]);
            return Number.isFinite(unitSeconds) ? unitSeconds : null;
        }

        var match = /^(\d+):([0-5]\d)(?:\:([0-5]\d)(?:\.(\d+))?)?$/.exec(text);
        if (!match) return null;

        var seconds;

        if (match[3] === undefined) {
            /* MM:SS; minutes may exceed 59. */
            seconds = Number(match[1]) * 60 + Number(match[2]);
        } else {
            /* HH:MM:SS; hours may exceed 23. */
            seconds = Number(match[1]) * 3600 +
                Number(match[2]) * 60 +
                Number(match[3]);

            if (match[4]) seconds += Number('0.' + match[4]);
        }

        return Number.isFinite(seconds) ? seconds : null;
    }

    function fa(value) {
        return String(value).replace(/\d/g, function (digit) {
            return '۰۱۲۳۴۵۶۷۸۹'.charAt(Number(digit));
        });
    }

    function element(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function emptyQuery() {
        return { min: null, max: null, number: '', status: '' };
    }

    function markPage() {
        if (!document.body) return;

        var menu = new URLSearchParams(window.location.search).get('menu');
        document.body.classList.toggle(
            'mt-cdr-page',
            menu === 'cdrreport' || !!document.getElementById('CDRreport')
        );
    }

    function makePanel() {
        serial++;

        var panel = element('details', 'mt-cdr-extra');
        panel.lang = 'fa';
        panel.dir = 'rtl';

        var summary = element('summary', '', 'فیلترهای بیشتر');
        var body = element('div', 'mt-cdr-extra-body');
        var note = element(
            'p',
            'mt-cdr-extra-note',
            'فیلتر ردیف‌های بارگذاری‌شده؛ این گزینه‌ها همراه جست‌وجوی جدول اعمال می‌شوند و گزارش تازه‌ای از سرور دریافت نمی‌کنند.'
        );

        var grid = element('div', 'mt-cdr-extra-grid');
        var error = element('p', 'mt-cdr-extra-error');
        error.id = 'mt-cdr-extra-error-' + serial;
        error.setAttribute('role', 'status');
        error.setAttribute('aria-live', 'polite');

        function field(title, control) {
            var label = element('label', 'mt-cdr-extra-field');
            label.appendChild(element('span', '', title));
            label.appendChild(control);
            grid.appendChild(label);
            return control;
        }

        function bound(title) {
            var input = document.createElement('input');
            input.type = 'text';
            input.inputMode = 'numeric';
            input.autocomplete = 'off';
            input.placeholder = 'بدون محدودیت';
            input.setAttribute('aria-describedby', error.id);
            return field(title, input);
        }

        var min = bound('حداقل مدت تماس (ثانیه)');
        var max = bound('حداکثر مدت تماس (ثانیه)');

        var number = document.createElement('input');
        number.type = 'text';
        number.inputMode = 'tel';
        number.autocomplete = 'off';
        number.placeholder = 'بخشی از تماس‌گیرنده یا مقصد';
        field('شامل شماره', number);

        var status = document.createElement('select');
        field('وضعیت', status);

        var reset = element('button', 'mt-cdr-extra-reset', 'بازنشانی این فیلترها');
        reset.type = 'button';
        grid.appendChild(reset);

        var count = element('p', 'mt-cdr-extra-count');
        count.setAttribute('role', 'status');
        count.setAttribute('aria-live', 'polite');
        count.setAttribute('aria-atomic', 'true');

        var formatNote = element(
            'p',
            'mt-cdr-extra-note',
            'بازه مدت تماس شامل دو سر بازه است. هنگام تعیین بازه، مدت خالی یا نامعتبر از نتیجه کنار گذاشته می‌شود.'
        );
        formatNote.style.marginTop = '12px';
        formatNote.style.marginBottom = '0';

        body.appendChild(note);
        body.appendChild(grid);
        body.appendChild(error);
        body.appendChild(formatNote);
        body.appendChild(count);
        panel.appendChild(summary);
        panel.appendChild(body);

        return {
            panel: panel,
            min: min,
            max: max,
            number: number,
            status: status,
            reset: reset,
            error: error,
            count: count
        };
    }

    function removePredicate(binding) {
        var index = binding.registry.indexOf(binding.predicate);
        if (index !== -1) binding.registry.splice(index, 1);
    }

    function detach() {
        if (!current) return;

        var binding = current;
        current = null;

        if (binding.inputTimer !== null) {
            window.clearTimeout(binding.inputTimer);
        }

        if (binding.reorderTimer !== null) {
            window.clearTimeout(binding.reorderTimer);
            binding.reorderTimer = null;
        }

        removePredicate(binding);
        binding.$table.off('.mtCDRExtra');
        binding.ui.panel.remove();

        /*
         * Unwrap only our own scroll container. Preserve the table and
         * any nodes DataTables may have placed beside it.
         */
        if (binding.scroll && binding.scroll.parentNode) {
            var parent = binding.scroll.parentNode;
            while (binding.scroll.firstChild) {
                parent.insertBefore(binding.scroll.firstChild, binding.scroll);
            }
            binding.scroll.remove();
        }
    }

    /*
     * Semantic columns of the stock 13-column CDR table (original order).
     * Issabel enables ColReorder, so CURRENT indexes can drift from these;
     * every accessor resolves through colReorder.transpose when present.
     */
    var SEMANTIC = {
        date: 0, caller: 1, destination: 3, status: 7, duration: 8
    };

    function columnOf(binding, semanticIndex) {
        var settings = binding.settings;

        if (
            settings &&
            settings._colReorder &&
            typeof settings._colReorder.fnTranspose === 'function'
        ) {
            var current = settings._colReorder.fnTranspose(semanticIndex, 'toCurrent');
            if (typeof current === 'number' && current >= 0) {
                return current;
            }
        }

        /* DataTables >=1.11 exposes colReorder.transpose on the API. */
        if (binding.api.colReorder &&
            typeof binding.api.colReorder.transpose === 'function') {
            try {
                var mapped = binding.api.colReorder.transpose(
                    semanticIndex, 'fromOriginal'
                );
                if (typeof mapped === 'number' && mapped >= 0) {
                    return mapped;
                }
            } catch (err) { /* untouched instance: original order */ }
        }

        return semanticIndex;
    }

    function cellText(binding, searchData, rowIndex, columnIndex) {
        var value = searchData[columnIndex];

        /*
         * Non-searchable columns can have an empty searchData entry.
         * Their actual filter-rendered cell value remains available.
         */
        if (value === undefined || value === null || value === '') {
            value = binding.api.cell(rowIndex, columnIndex).render('filter');
        }

        return cleanText(value);
    }

    function durationForRow(binding, searchData, rowIndex, columnIndex) {
        var cell = binding.api.cell(rowIndex, columnIndex).node();

        /*
         * The portal's seconds toggle may rewrite visible cell text.
         * Prefer that text when a cell node exists; otherwise use the
         * DataTables filter-rendered value.
         */
        return durationSeconds(
            cell ? cell.textContent
                 : cellText(binding, searchData, rowIndex, columnIndex)
        );
    }

    function refreshStatusOptions(binding) {
        var selected = binding.ui.status.value || binding.query.status;
        var values = new Set();

        /*
         * Some older DataTables builds do not expose column().render at
         * all; fall back to the RENDERED cell text via column nodes so
         * option labels match what the predicate compares.
         */
        var statusIndex = columnOf(binding, SEMANTIC.status);
        var colApi = null;
        try {
            colApi = binding.api.column(statusIndex);
        } catch (err) {
            colApi = null;
        }

        if (colApi && typeof colApi.render === 'function') {
            colApi.render('filter').each(function (value) {
                var status = cleanText(value);
                if (status) values.add(status);
            });
        } else {
            /*
             * Older DataTables builds do not expose column().render.
             * Derive options from the SAME filter-value accessor the
             * predicate uses (cell().render('filter')), so option values
             * always match what selecting them filters — display text and
             * filter data can legitimately differ in DataTables.
             */
            binding.api.rows().every(function () {
                var value = this.cell(this.index(), statusIndex).render('filter');
                var status = cleanText(value);
                if (status) values.add(status);
            });
        }

        /*
         * Keep a selected status available even if an Ajax refresh
         * currently has no rows with that status.
         */
        if (selected) values.add(selected);

        var ordered = Array.from(values).sort();
        var signature = JSON.stringify(ordered);

        if (signature === binding.statusSignature) return;
        binding.statusSignature = signature;

        var fragment = document.createDocumentFragment();
        var all = element('option', '', 'همه وضعیت‌ها');
        all.value = '';
        fragment.appendChild(all);

        ordered.forEach(function (value) {
            var option = element('option', '', value);
            option.value = value;
            fragment.appendChild(option);
        });

        binding.ui.status.replaceChildren(fragment);
        binding.ui.status.value = selected;
    }

    /*
     * The upstream template renders an all-empty sentinel row when the
     * server query returns no calls; the theme hides it via
     * mt-empty-placeholder. Sentinel rows are never records: they are
     * exempt from filtering AND excluded from the counts, and a zero-real
     * match shows an explicit empty-state message instead of a phantom
     * "1 matching row".
     */
    function rowIsPlaceholder(node) {
        if (!node) return false;
        if (node.classList.contains('mt-empty-placeholder')) return true;
        var tds = node.querySelectorAll('td');
        if (!tds.length) return false;
        for (var i = 0; i < tds.length; i++) {
            if (tds[i].textContent.trim() || tds[i].children.length) return false;
        }
        return true;
    }

    function updateCount(binding) {
        var total = 0;
        var matched = 0;

        binding.api.rows({ search: 'none' }).nodes().each(function (node) {
            if (!rowIsPlaceholder(node)) total++;
        });
        binding.api.rows({ search: 'applied' }).nodes().each(function (node) {
            if (!rowIsPlaceholder(node)) matched++;
        });

        if (total === 0) {
            binding.ui.count.classList.add('is-empty');
            binding.ui.count.textContent =
                'هیچ تماسی در بازهٔ انتخاب‌شده ثبت نشده است.';
            return;
        }

        if (matched === 0) {
            binding.ui.count.classList.add('is-empty');
            binding.ui.count.textContent =
                'هیچ ردیفی با فیلترهای فعلی مطابقت ندارد (۰ از ' + fa(total) +
                ' ردیف واقعی).';
            return;
        }

        binding.ui.count.classList.remove('is-empty');
        binding.ui.count.textContent =
            fa(matched) + ' ردیف از ' + fa(total) +
            ' ردیف بارگذاری‌شده با مجموع فیلترهای جدول مطابقت دارد.';
    }

    function mount(binding) {
        var table = binding.table;

        /*
         * Respect an existing DataTables scroll implementation.
         * Otherwise scroll only the table, leaving controls visible.
         */
        if (
            !binding.scroll &&
            !table.closest('.dataTables_scrollBody, .dt-scroll-body')
        ) {
            var scroll = element('div', 'mt-cdr-table-scroll');
            scroll.tabIndex = 0;
            scroll.setAttribute('role', 'region');
            scroll.setAttribute('aria-label', 'جدول گزارش تماس؛ قابل پیمایش افقی');

            table.parentNode.insertBefore(scroll, table);
            scroll.appendChild(table);
            binding.scroll = scroll;
        }

        var container = binding.api.table().container();
        var anchor = container && container !== table
            ? container
            : binding.scroll || table;

        if (anchor.parentNode && anchor.previousElementSibling !== binding.ui.panel) {
            anchor.parentNode.insertBefore(binding.ui.panel, anchor);
        }
    }

    function applyInputs(binding) {
        if (current !== binding) return;

        var min = readBound(binding.ui.min.value);
        var max = readBound(binding.ui.max.value);

        var reversed = min.valid && max.valid &&
            min.value !== null && max.value !== null &&
            min.value > max.value;

        binding.ui.min.setAttribute(
            'aria-invalid',
            String(!min.valid || reversed)
        );
        binding.ui.max.setAttribute(
            'aria-invalid',
            String(!max.valid || reversed)
        );

        if (!min.valid || !max.valid) {
            binding.ui.error.textContent =
                'مدت را با عدد صحیح صفر یا بیشتر وارد کنید؛ فیلتر معتبر قبلی همچنان اعمال می‌شود.';
            return;
        }

        if (reversed) {
            binding.ui.error.textContent =
                'حداقل مدت نباید بیشتر از حداکثر باشد؛ فیلتر معتبر قبلی همچنان اعمال می‌شود.';
            return;
        }

        binding.ui.error.textContent = '';
        binding.query = {
            min: min.value,
            max: max.value,
            number: normalizeNumber(binding.ui.number.value),
            status: binding.ui.status.value
        };

        /* Reset paging when criteria change. */
        binding.api.draw();
    }

    function attach($, table, api, settings) {
        var ui = makePanel();

        var binding = {
            table: table,
            $table: $(table),
            api: api,
            settings: settings,
            registry: $.fn.dataTable.ext.search,
            predicate: null,
            query: emptyQuery(),
            ui: ui,
            scroll: null,
            inputTimer: null,
            statusSignature: null
        };

        binding.predicate = function (candidate, searchData, rowIndex) {
            if (candidate !== binding.settings || candidate.nTable !== binding.table) {
                return true;
            }

            /*
             * Placeholder/empty rows (the server renders one all-empty row
             * when no calls match; DataTables renders its own empty-state
             * row too) must stay visible — they carry the "no calls" message
             * and are never filtered by duration/number/status.
             */
            var colDate = columnOf(binding, SEMANTIC.date);
            var colCaller = columnOf(binding, SEMANTIC.caller);
            var colDst = columnOf(binding, SEMANTIC.destination);
            var colStatus = columnOf(binding, SEMANTIC.status);
            var colDur = columnOf(binding, SEMANTIC.duration);

            if (
                !cellText(binding, searchData, rowIndex, colDate) &&
                !cellText(binding, searchData, rowIndex, colCaller) &&
                !cellText(binding, searchData, rowIndex, colDst) &&
                !cellText(binding, searchData, rowIndex, colStatus) &&
                durationForRow(binding, searchData, rowIndex, colDur) === null
            ) {
                return true;
            }

            var query = binding.query;

            if (query.status) {
                var status = cellText(
                    binding, searchData, rowIndex,
                    columnOf(binding, SEMANTIC.status)
                );
                if (status !== query.status) return false;
            }

            if (query.number) {
                var caller = normalizeNumber(
                    cellText(
                        binding, searchData, rowIndex,
                        columnOf(binding, SEMANTIC.caller)
                    )
                );
                var destination = normalizeNumber(
                    cellText(
                        binding, searchData, rowIndex,
                        columnOf(binding, SEMANTIC.destination)
                    )
                );

                if (
                    caller.indexOf(query.number) === -1 &&
                    destination.indexOf(query.number) === -1
                ) {
                    return false;
                }
            }

            if (query.min !== null || query.max !== null) {
                var duration = durationForRow(
                    binding, searchData, rowIndex,
                    columnOf(binding, SEMANTIC.duration)
                );

                if (duration === null) return false;
                if (query.min !== null && duration < query.min) return false;
                if (query.max !== null && duration > query.max) return false;
            }

            return true;
        };

        current = binding;
        binding.registry.push(binding.predicate);

        function scheduleApply() {
            if (binding.inputTimer !== null) {
                window.clearTimeout(binding.inputTimer);
            }

            binding.inputTimer = window.setTimeout(function () {
                binding.inputTimer = null;
                applyInputs(binding);
            }, 220);
        }

        [ui.min, ui.max, ui.number].forEach(function (input) {
            input.addEventListener('input', scheduleApply);

            input.addEventListener('keydown', function (event) {
                if (event.key !== 'Enter') return;
                event.preventDefault();

                if (binding.inputTimer !== null) {
                    window.clearTimeout(binding.inputTimer);
                    binding.inputTimer = null;
                }

                applyInputs(binding);
            });
        });

        ui.status.addEventListener('change', function () {
            if (binding.inputTimer !== null) {
                window.clearTimeout(binding.inputTimer);
                binding.inputTimer = null;
            }

            applyInputs(binding);
        });

        ui.reset.addEventListener('click', function () {
            if (binding.inputTimer !== null) {
                window.clearTimeout(binding.inputTimer);
                binding.inputTimer = null;
            }

            ui.min.value = '';
            ui.max.value = '';
            ui.number.value = '';
            ui.status.value = '';
            ui.min.removeAttribute('aria-invalid');
            ui.max.removeAttribute('aria-invalid');
            ui.error.textContent = '';
            binding.query = emptyQuery();
            binding.api.draw();
        });

        ui.panel.addEventListener('toggle', function () {
            if (current === binding && ui.panel.open) {
                refreshStatusOptions(binding);
            }
        });

        /*
         * Semantic cell classes travel with reordered columns: the CSS
         * bidi/weight rules target classes, never positional nth-child.
         */
        function tagSemanticCells() {
            if (current !== binding || !binding.table.isConnected) return;

            /*
             * Address cells through cell().node() instead of DOM child
             * indexes: hidden columns are removed from the row DOM while
             * data indexes keep counting them, so positional child access
             * would tag the wrong cell after any hide/show.
             */
            var rowNodes = new Set();
            binding.api.rows({ page: 'current' }).every(function () {
                var row = this.node();
                if (row) rowNodes.add(row);
                return true;
            });

            rowNodes.forEach(function (row) {
                var cells = row.querySelectorAll('td');
                for (var i = 0; i < cells.length; i++) {
                    cells[i].classList.remove(
                        'mt-c-date', 'mt-c-caller', 'mt-c-destination',
                        'mt-c-status', 'mt-c-duration'
                    );
                }
            });

            var pairs = Object.keys(SEMANTIC).map(function (key) {
                return {
                    cls: 'mt-c-' + key,
                    idx: columnOf(binding, SEMANTIC[key])
                };
            });

            binding.api.rows({ page: 'current' }).every(function () {
                pairs.forEach(function (pair) {
                    var cell = null;
                    try {
                        cell = this.cell(this.index(), pair.idx).node();
                    } catch (err) {
                        cell = null;
                    }
                    if (cell) cell.classList.add(pair.cls);
                }, this);
                return true;
            });
        }

        binding.$table.on('draw.dt.mtCDRExtra', function () {
            if (current !== binding) return;
            tagSemanticCells();
            refreshStatusOptions(binding);
            updateCount(binding);
        });

        /*
         * ColReorder emits its event on the .dt namespace; coalesce the
         * refresh/redraw with a timeout because one programmatic reorder
         * can emit several events before the order settles. The timeout
         * is cancelled in detach().
         */
        binding.reorderTimer = null;
        binding.$table.on('column-reorder.dt.mtCDRExtra', function () {
            if (current !== binding) return;
            if (binding.reorderTimer !== null) {
                window.clearTimeout(binding.reorderTimer);
            }
            binding.reorderTimer = window.setTimeout(function () {
                binding.reorderTimer = null;
                if (current !== binding || !binding.table.isConnected) return;
                tagSemanticCells();
                refreshStatusOptions(binding);
                binding.api.draw(false);
            }, 120);
        });

        binding.$table.on('destroy.dt.mtCDRExtra', function (event, destroyed) {
            if (
                current === binding &&
                (!destroyed || destroyed === binding.settings)
            ) {
                detach();
            }
        });

        mount(binding);
        /*
         * The initial draw may predate attachment (wire() runs after the
         * table initializes), so tag immediately — no extra draw needed.
         */
        tagSemanticCells();
        refreshStatusOptions(binding);
        updateCount(binding);
    }

    function wire() {
        if (disposed) return;

        markPage();

        var $ = window.jQuery;
        var table = document.getElementById('CDRreport');

        if (
            !$ ||
            !$.fn.dataTable ||
            !$.fn.dataTable.isDataTable ||
            !$.fn.dataTable.ext ||
            !$.fn.dataTable.ext.search ||
            !table ||
            !$.fn.dataTable.isDataTable(table)
        ) {
            detach();
            return;
        }

        /* Retrieve only; never initialize or reconfigure this table. */
        var api = $(table).DataTable();
        var settings = api.settings()[0];

        if (
            !settings ||
            settings.oFeatures.bServerSide ||
            !settings.oFeatures.bFilter ||
            api.columns().count() !== 13
        ) {
            detach();
            return;
        }

        if (
            current &&
            (current.table !== table || current.settings !== settings)
        ) {
            detach();
        }

        if (!current) {
            attach($, table, api, settings);
        } else {
            mount(current);
        }
    }

    function onSecondsChange(event) {
        var target = event.target;

        if (
            !current ||
            !target ||
            target.name !== 'chkoldtimeInSecs' ||
            !target.closest('#formFilter')
        ) {
            return;
        }

        var binding = current;

        /*
         * Run after the supplied inline click handler has completed.
         * The predicate reads each existing duration cell directly.
         */
        window.setTimeout(function () {
            if (current !== binding || !binding.table.isConnected) return;

            if (binding.query.min !== null || binding.query.max !== null) {
                binding.api.draw(false);
            }
        }, 0);
    }

    function start() {
        if (started || disposed) return;
        started = true;

        document.addEventListener('change', onSecondsChange);
        wire();

        /*
         * Handles delayed DataTables initialization, Ajax navigation
         * and full table replacement without accumulating bindings.
         */
        interval = window.setInterval(wire, 2000);
    }

    function destroy() {
        disposed = true;

        if (interval !== null) window.clearInterval(interval);
        document.removeEventListener('DOMContentLoaded', start);
        document.removeEventListener('change', onSecondsChange);

        var old = current;
        detach();

        if (
            old &&
            old.table.isConnected &&
            window.jQuery &&
            window.jQuery.fn.dataTable &&
            window.jQuery.fn.dataTable.isDataTable(old.table)
        ) {
            old.api.draw(false);
        }

        if (document.body) document.body.classList.remove('mt-cdr-page');

        if (window.MTCDRFilters === publicApi) {
            delete window.MTCDRFilters;
        }
    }

    var publicApi = {
        wire: wire,
        destroy: destroy
    };

    window.MTCDRFilters = publicApi;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
        start();
    }

})(window, document);
