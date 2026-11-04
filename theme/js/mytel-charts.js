/* MyTelCharts — centralized Apache ECharts layer for the MyTel Issabel theme.
   One theme, one helper API, semantic colors, Persian empty/loading states,
   ResizeObserver-aware. Data always comes from the existing report sources. */
(function (global) {
    "use strict";

    /* ---------- MyTel design tokens (mirror tokens.css) ---------- */
    var T = {
        primary: "#2E3194",
        primaryStrong: "#26287C",
        blue: "#1E88E5",
        accent: "#FF8A00",
        accentStrong: "#E67A00",
        success: "#27965A",
        warning: "#F5A623",
        danger: "#E5484D",
        info: "#3E7BFA",
        navy: "#0B1526",
        text: "#232A35",
        muted: "#64708A",
        faint: "#9AA3B5",
        border: "#E3E7EE",
        surface: "#FFFFFF",
        bg: "#F3F5F9",
        /* protocol identity — consistent across every report */
        protocols: {
            "Total": "#2E3194",
            "SIP": "#1E88E5",
            "PJSIP": "#3E7BFA",
            "IAX": "#FF8A00",
            "IAX2": "#FF8A00",
            "DAHDI": "#8E44AD",
            "H323": "#E91E8C",
            "Local": "#27965A"
        },
        /* semantic status identity */
        status: {
            "پاسخ داده شده": "#27965A", "ANSWERED": "#27965A", "Answered": "#27965A",
            "مشغول": "#F5A623", "BUSY": "#F5A623", "Busy": "#F5A623",
            "ناموفق": "#E5484D", "FAILED": "#E5484D", "Failed": "#E5484D",
            "بدون پاسخ": "#E8B84B", "NO ANSWER": "#E8B84B", "No Answer": "#E8B84B",
            "همه تماس‌ها": "#2E3194", "ALL": "#2E3194", "All": "#2E3194",
            "داخلی": "#1E88E5", "خارجی": "#FF8A00"
        },
        seriesFallback: ["#2E3194", "#1E88E5", "#FF8A00", "#27965A", "#E5484D", "#3E7BFA", "#8E44AD", "#E8B84B"]
    };

    var EMPTY_MSG = "در بازه انتخاب‌شده داده‌ای برای نمایش وجود ندارد.";

    /* Canvas does not inherit CSS. Resolve role tokens and repaint existing
       charts when the shell theme changes, preserving data/selection/zoom. */
    var colorRoles = {
        '#2e3194': 'primary', '#26287c': 'primaryStrong', '#1e88e5': 'blue',
        '#ff8a00': 'accent', '#e67a00': 'accentStrong', '#27965a': 'success',
        '#f5a623': 'warning', '#e5484d': 'danger', '#3e7bfa': 'info',
        '#8e44ad': 'violet', '#e91e8c': 'pink', '#e8b84b': 'warning'
    };
    var tokenRoles = {
        primary: '--mt-primary-fg', primaryStrong: '--mt-primary-fg-hover',
        blue: '--mt-blue-fg', accent: '--mt-accent-fg', accentStrong: '--mt-accent-fg',
        success: '--mt-success-fg', warning: '--mt-warning-fg', danger: '--mt-danger-fg',
        info: '--mt-info-fg', text: '--mt-text', muted: '--mt-text-muted',
        faint: '--mt-text-faint', border: '--mt-border', surface: '--mt-surface', bg: '--mt-bg',
        violet: '--mt-violet-fg', pink: '--mt-pink-fg'
    };
    function syncTokens() {
        var css = getComputedStyle(document.documentElement);
        Object.keys(tokenRoles).forEach(function (key) {
            if (T[key]) colorRoles[T[key].toLowerCase()] = key;
            var value = css.getPropertyValue(tokenRoles[key]).trim();
            if (value) T[key] = value;
        });
    }
    function seriesColor(color) {
        return typeof color === 'string' && colorRoles[color.toLowerCase()]
            ? T[colorRoles[color.toLowerCase()]] : color;
    }
    function recolorStyle(style) {
        if (!style || !style.color) return;
        if (typeof style.color === 'string') style.color = seriesColor(style.color);
        else if (style.color.colorStops) style.color.colorStops.forEach(function (stop) { stop.color = seriesColor(stop.color); });
    }
    function themeOption(option) {
        syncTokens();
        if (option.textStyle) option.textStyle.color = T.text;
        if (option.title && option.title.textStyle) option.title.textStyle.color = T.faint;
        if (option.legend && option.legend.textStyle) option.legend.textStyle.color = T.muted;
        if (option.color) option.color = option.color.map(seriesColor);
        ['xAxis', 'yAxis'].forEach(function (key) {
            var axes = option[key] ? (Array.isArray(option[key]) ? option[key] : [option[key]]) : [];
            axes.forEach(function (axis) {
                if (axis.axisLabel) {
                    axis.axisLabel.color = T.muted;
                    if (axis.axisLabel.rich && axis.axisLabel.rich.ltr) axis.axisLabel.rich.ltr.color = T.muted;
                }
                if (axis.axisLine && axis.axisLine.lineStyle) axis.axisLine.lineStyle.color = T.border;
                if (axis.splitLine && axis.splitLine.lineStyle) axis.splitLine.lineStyle.color = T.border;
            });
        });
        if (option.toolbox) {
            option.toolbox.iconStyle = { borderColor: T.muted };
            Object.keys(option.toolbox.feature || {}).forEach(function (key) {
                option.toolbox.feature[key].iconStyle = { borderColor: T.muted };
            });
        }
        (option.series || []).forEach(function (series) {
            if (series.label) series.label.color = T.muted;
            if (series.title) series.title.color = T.muted;
            if (series.detail) series.detail.color = T.text;
            if (series.backgroundStyle) series.backgroundStyle.color = T.border;
            recolorStyle(series.itemStyle);
            recolorStyle(series.lineStyle);
            if (series.type === 'pie' && series.itemStyle) series.itemStyle.borderColor = T.surface;
            if (series.labelLine && series.labelLine.lineStyle) series.labelLine.lineStyle.color = T.border;
            if (series.progress) recolorStyle(series.progress.itemStyle);
            (series.data || []).forEach(function (point) {
                if (point && typeof point === 'object' && point.itemStyle) recolorStyle(point.itemStyle);
            });
            if (series.type === 'gauge' && series.axisLine) series.axisLine.lineStyle.color = [[1, T.border]];
        });
        option.animation = !(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
        return option;
    }
    syncTokens();

    function pick(name, fallback, idx) {
        if (name !== undefined && name !== null) {
            var n = String(name).trim();
            if (T.protocols[n]) return T.protocols[n];
            if (T.status[n]) return T.status[n];
        }
        return fallback || T.seriesFallback[(idx || 0) % T.seriesFallback.length];
    }

    function faNum(n) {
        /* keep Latin digits for chart axes/values — technical data stays readable/LTR */
        return String(n);
    }

    function fmtTick(v) {
        if (v === undefined || v === null) return "";
        if (typeof v === "number") {
            if (Math.abs(v) >= 1000) return (v / 1000).toFixed(v % 1000 === 0 ? 0 : 1) + "k";
            return (Math.round(v * 100) / 100) + "";
        }
        return v;
    }

    function baseAxis() {
        return {
            axisLine: { lineStyle: { color: T.border } },
            axisTick: { show: false },
            axisLabel: { color: T.muted, fontSize: 11, fontFamily: "Vazirmatn, Tahoma, sans-serif" },
            splitLine: { lineStyle: { color: T.border } }
        };
    }

    function emptyOption(dom) {
        return {
            title: {
                text: EMPTY_MSG,
                subtext: "",
                left: "center",
                top: "middle",
                textStyle: { color: T.faint, fontSize: 14, fontWeight: 500, fontFamily: "Vazirmatn, Tahoma, sans-serif" }
            },
            xAxis: { show: false }, yAxis: { show: false }, series: []
        };
    }

    function isEmptySeries(series) {
        if (!series || !series.length) return true;
        return series.every(function (s) {
            var d = (s.data || []).filter(function (p) {
                var v = Array.isArray(p) ? p[1] : (p && p.value !== undefined ? p.value : p);
                return v !== null && v !== undefined && v !== 0;
            });
            return d.length === 0;
        });
    }

    /* instance registry — one instance per DOM node, safe re-init, resize */
    var registry = new Map();

    function retire(dom, inst) {
        if (inst.__mtResizeObserver) inst.__mtResizeObserver.disconnect();
        if (!inst.isDisposed()) inst.dispose();
        registry.delete(dom);
    }

    function getInstance(dom) {
        var inst = global.echarts.getInstanceByDom(dom);
        if (!inst && registry.has(dom)) retire(dom, registry.get(dom));
        return inst;
    }

    function render(dom, option, meta) {
        if (!global.echarts || !dom) return null;
        var inst = getInstance(dom);
        if (!inst) {
            inst = global.echarts.init(dom, null, { renderer: "canvas" });
            registry.set(dom, inst);
            /* keep charts correct when the sidebar collapses or tabs appear */
            if (global.ResizeObserver) {
                var ro = new global.ResizeObserver(function () {
                    if (!inst.isDisposed()) { try { inst.resize(); } catch (e) {} }
                });
                ro.observe(dom);
                inst.__mtResizeObserver = ro;
            }
            /* a canvas drawn before the webfont finishes loading keeps the
               fallback font — repaint once fonts are ready */
            if (global.document && document.fonts && document.fonts.ready) {
                document.fonts.ready.then(function () {
                    if (!inst.isDisposed() && inst.__mtOption) {
                        try { inst.setOption(inst.__mtOption, true); } catch (e) {}
                    }
                });
            }
        }
        var isEmpty = isEmptySeries(meta && meta.rawSeries);
        /* remember the option actually applied — the font-ready repaint must
           not overwrite a displayed empty state with the full chart */
        inst.__mtOption = themeOption(isEmpty ? emptyOption(dom) : option);
        inst.setOption(inst.__mtOption, true);
        return inst;
    }

    /* ---------- shared option builders ---------- */

    function baseCommon(title) {
        return {
            textStyle: { fontFamily: "Vazirmatn, Tahoma, sans-serif", color: T.text },
            grid: { top: 34, left: 46, right: 18, bottom: 40, containLabel: true },
            tooltip: {
                trigger: "axis",
                backgroundColor: T.navy,
                borderWidth: 0,
                textStyle: { color: "#fff", fontSize: 12, fontFamily: "Vazirmatn, Tahoma, sans-serif" },
                axisPointer: { type: "line", lineStyle: { color: T.faint, type: "dashed" } }
            },
            toolbox: {
                right: 6, top: 0,
                feature: {
                    saveAsImage: { title: "ذخیره تصویر", iconStyle: { borderColor: T.faint } },
                    restore: { title: "بازنشانی", iconStyle: { borderColor: T.faint } }
                },
                iconStyle: { borderColor: T.faint }
            },
            legend: {
                top: 0, icon: "roundRect", itemWidth: 12, itemHeight: 8,
                textStyle: { color: T.muted, fontSize: 12, fontFamily: "Vazirmatn, Tahoma, sans-serif" }
            }
        };
    }

    function line(dom, title, categories, series, opts) {
        opts = opts || {};
        var common = baseCommon(title);
        common.grid.top = 46;
        common.legend.data = series.map(function (s) { return s.name; });
        common.tooltip.valueFormatter = function (v) { return faNum(v) + (opts.unit ? " " + opts.unit : ""); };
        var option = {
            title: undefined,
            color: series.map(function (s, i) { return pick(s.name, s.color, i); }),
            xAxis: Object.assign(baseAxis(), {
                type: "category",
                boundaryGap: opts.area !== true,
                data: categories,
                axisLabel: { color: T.muted, fontSize: 11, interval: "auto", hideOverlap: true }
            }),
            yAxis: Object.assign(baseAxis(), { type: "value" }),
            series: series.map(function (s, i) {
                return {
                    name: s.name,
                    type: "line",
                    data: s.data,
                    smooth: 0.25,
                    symbol: "circle",
                    symbolSize: 5,
                    showSymbol: (s.data || []).length <= 40,
                    lineStyle: { width: 2.5 },
                    emphasis: { focus: "series" },
                    areaStyle: opts.area ? { opacity: 0.10 } : undefined
                };
            }),
            animationDuration: 450
        };
        if (opts.zoom) {
            option.dataZoom = [
                { type: "inside" },
                { type: "slider", height: 18, bottom: 8, borderColor: T.border }
            ];
            common.grid.bottom = 66;
        }
        var full = Object.assign({}, common, option);
        /* time series with real zero values keep context — bypass empty state */
        var meta = { rawSeries: opts.force ? [{ data: [1] }] : series };
        return render(dom, full, meta);
    }

    function bar(dom, title, categories, series, opts) {
        opts = opts || {};
        var common = baseCommon(title);
        common.legend = { show: series.length > 1, top: 0, textStyle: { color: T.muted, fontSize: 12 } };
        var horizontal = opts.horizontal === true;
        var valAxis = Object.assign(baseAxis(), { type: horizontal ? "x" : "value" });
        var catAxis = Object.assign(baseAxis(), {
            type: horizontal ? "y" : "category",
            data: categories,
            axisLabel: { color: T.muted, fontSize: 11, hideOverlap: true },
            splitLine: { show: false }
        });
        var option = {
            color: series.map(function (s, i) { return pick(s.name, s.color, i); }),
            xAxis: horizontal ? valAxis : catAxis,
            yAxis: horizontal ? catAxis : valAxis,
            series: series.map(function (s, i) {
                return {
                    name: s.name, type: "bar", data: s.data,
                    barMaxWidth: 26, itemStyle: { borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
                    label: opts.showValues ? { show: true, position: horizontal ? "right" : "top", color: T.muted, fontSize: 11 } : undefined,
                    emphasis: { focus: "series" }
                };
            }),
            animationDuration: 450
        };
        var full = Object.assign({}, common, option);
        return render(dom, full, { rawSeries: series });
    }

    function donut(dom, title, items, opts) {
        opts = opts || {};
        var option = {
            textStyle: { fontFamily: "Vazirmatn, Tahoma, sans-serif", color: T.text },
            tooltip: {
                trigger: "item",
                backgroundColor: T.navy, borderWidth: 0,
                textStyle: { color: "#fff", fontSize: 12, fontFamily: "Vazirmatn, Tahoma, sans-serif" },
                formatter: function (p) { return p.name + ": " + faNum(p.value) + " (" + p.percent + "٪)"; }
            },
            legend: { bottom: 0, icon: "circle", itemWidth: 10, itemHeight: 10, textStyle: { color: T.muted, fontSize: 12, fontFamily: "Vazirmatn, Tahoma, sans-serif" } },
            series: [{
                type: "pie",
                radius: opts.radius || ["52%", "74%"],
                center: ["50%", "46%"],
                avoidLabelOverlap: true,
                itemStyle: { borderRadius: 4, borderColor: T.surface, borderWidth: 2 },
                label: { show: opts.labels !== false, color: T.muted, fontSize: 11, fontFamily: "Vazirmatn, Tahoma, sans-serif", formatter: "{b}\n{d}٪" },
                labelLine: { length: 10, length2: 8, lineStyle: { color: T.border } },
                data: items.map(function (it, i) {
                    return { name: it.name, value: it.value, itemStyle: { color: pick(it.name, it.color, i) } };
                }),
                animationDuration: 450
            }]
        };
        return render(dom, option, { rawSeries: [{ data: items.map(function (i) { return i.value; }) }] });
    }

    /* radial progress for bounded 0-100 metrics (CPU/RAM/SWAP) */
    function gauge(dom, title, items, opts) {
        opts = opts || {};
        var n = items.length;
        var radius = n <= 2 ? "62%" : "58%";
        var centers = [];
        for (var i = 0; i < n; i++) centers.push([(100 / n) * (i + 0.5) + "%", "58%"]);
        var series = items.map(function (it, i) {
            var color = it.color || T.primary;
            return {
                type: "gauge",
                center: centers[i],
                radius: radius,
                startAngle: 220, endAngle: -40,
                min: 0, max: it.max || 100,
                progress: { show: true, width: 10, roundCap: true, itemStyle: { color: color } },
                axisLine: { roundCap: true, lineStyle: { width: 10, color: [[1, "#E9EDF4"]] } },
                pointer: { show: false },
                axisTick: { show: false },
                splitLine: { show: false },
                axisLabel: { show: false },
                anchor: { show: false },
                /* gauge titles render the data name only (rich/formatter are
                   ignored in 5.5) — callers pass pure-Persian names so canvas
                   bidi never mixes scripts in one run */
                title: {
                    show: true, offsetCenter: [0, "34%"],
                    color: T.muted, fontSize: 12, fontFamily: "Vazirmatn, Tahoma, sans-serif"
                },
                detail: {
                    valueAnimation: true, offsetCenter: [0, "2%"],
                    color: T.text, fontSize: 20, fontWeight: 700,
                    fontFamily: "Vazirmatn, Tahoma, sans-serif",
                    formatter: function (v) { return faNum(Math.round(v)) + "٪"; }
                },
                data: [{ value: it.value, name: it.name }]
            };
        });
        var option = { series: series, textStyle: { fontFamily: "Vazirmatn, Tahoma, sans-serif" } };
        return render(dom, option, { rawSeries: [{ data: items.map(function (i) { return i.value; }) }] });
    }

    /* horizontal utilization bars (disks / filesystems) */
    function bars(dom, title, rows, opts) {
        /* rows: [{name, used, total, unit}] — name may be LTR path */
        opts = opts || {};
        var cats = rows.map(function (r) { return r.name; });
        var usedData = rows.map(function (r) {
            var pct = r.total > 0 ? Math.round((r.used / r.total) * 1000) / 10 : 0;
            return { value: pct, raw: r };
        });
        var option = {
            textStyle: { fontFamily: "Vazirmatn, Tahoma, sans-serif" },
            grid: { top: 8, left: 8, right: 56, bottom: 8, containLabel: true },
            tooltip: {
                trigger: "item",
                backgroundColor: T.navy, borderWidth: 0,
                textStyle: { color: "#fff", fontSize: 12, fontFamily: "Vazirmatn, Tahoma, sans-serif" },
                formatter: function (p) {
                    var r = p.data.raw;
                    return p.name + "<br/>" + faNum(r.used) + " / " + faNum(r.total) + " " + (r.unit || "") +
                        " (" + faNum(Math.round(r.total > 0 ? (r.used / r.total) * 100 : 0)) + "٪)";
                }
            },
            xAxis: { type: "value", max: 100, show: false },
            yAxis: {
                type: "category", data: cats, inverse: true,
                axisLine: { show: false }, axisTick: { show: false },
                axisLabel: { color: T.muted, fontSize: 11, fontFamily: "Vazirmatn, Tahoma, sans-serif", formatter: function (v) { return "{ltr|" + v + "}"; }, rich: { ltr: { direction: "ltr", color: T.muted, fontSize: 11 } } }
            },
            series: [{
                type: "bar", data: usedData, barMaxWidth: 14,
                itemStyle: {
                    borderRadius: 7,
                    color: new global.echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: T.primary }, { offset: 1, color: T.blue }
                    ])
                },
                backgroundStyle: { color: "#EDF0F5", borderRadius: 7 },
                label: {
                    show: true, position: "right", color: T.text, fontSize: 11,
                    fontFamily: "Vazirmatn, Tahoma, sans-serif",
                    formatter: function (p) { return faNum(p.value) + "٪"; }
                },
                animationDuration: 450
            }]
        };
        return render(dom, option, { rawSeries: [{ data: rows.map(function (r) { return r.used > 0 ? r.used : null; }) }] });
    }

    /* kpi card (plain DOM, no chart) */
    function kpiCard(container, title, value, tone) {
        var colors = { success: T.success, warning: T.warning, danger: T.danger, info: T.info, primary: T.primary };
        var d = document.createElement("div");
        d.className = "mt-kpi";
        d.innerHTML = '<span class="mt-kpi-value" style="color:' + (colors[tone] || T.primary) + '">' + value + "</span>" +
                      '<span class="mt-kpi-title">' + title + "</span>";
        container.appendChild(d);
        return d;
    }

    function disposeAll(root) {
        root = root || document;
        root.querySelectorAll("[_echarts_instance_]").forEach(function (dom) {
            var inst = global.echarts.getInstanceByDom(dom);
            if (inst) retire(dom, inst);
        });
    }

    global.MyTelCharts = {
        T: T, line: line, bar: bar, donut: donut, gauge: gauge, bars: bars,
        kpiCard: kpiCard, render: render, disposeAll: disposeAll,
        pickColor: pick, EMPTY_MSG: EMPTY_MSG
    };

    if (global.MutationObserver) {
        new MutationObserver(function () {
            registry.forEach(function (inst, dom) {
                if (!dom.isConnected || inst.isDisposed()) retire(dom, inst);
                else if (inst.__mtOption) {
                    inst.setOption(themeOption(inst.__mtOption), { notMerge: false, lazyUpdate: true });
                }
            });
        }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-mt-theme'] });
    }
})(window);
