'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture() {
  let theme = 'light';
  const callbacks = [], instances = new Map(), observers = [];
  const colors = {
    light: { text: '#18283E', 'text-muted': '#52647C', 'text-faint': '#607089', border: '#DFE6F0', surface: '#FFFFFF', 'primary-fg': '#245CC5', 'primary-fg-hover': '#194BA9', 'blue-fg': '#1469B2', 'success-fg': '#176B43', 'warning-fg': '#805300', 'danger-fg': '#B42338', 'accent-fg': '#9C4D00', 'info-fg': '#2459C4', 'violet-fg': '#6741B4', 'pink-fg': '#A52272' },
    dark: { text: '#EAF0FA', 'text-muted': '#B1BED2', 'text-faint': '#A1B1C9', border: '#2B3B51', surface: '#131F30', 'primary-fg': '#A9C9FF', 'primary-fg-hover': '#D0E2FF', 'blue-fg': '#8DCBFF', 'success-fg': '#83D8AD', 'warning-fg': '#FFD084', 'danger-fg': '#FFADB2', 'accent-fg': '#FFBB7A', 'info-fg': '#A4C5FF', 'violet-fg': '#C7B7FF', 'pink-fg': '#F5A5D1' },
  };
  const context = {
    document: { documentElement: {}, fonts: { ready: Promise.resolve() } },
    getComputedStyle: () => ({ getPropertyValue: name => colors[theme][name.replace('--mt-', '')] || '' }),
    matchMedia: () => ({ matches: true }),
    MutationObserver: class { constructor(callback) { callbacks.push(callback); } observe() {} },
    ResizeObserver: class { constructor() { this.disconnected = false; observers.push(this); } observe() {} disconnect() { this.disconnected = true; } },
    echarts: {
      graphic: { LinearGradient: class { constructor(x, y, x2, y2, stops) { this.colorStops = stops; } } },
      getInstanceByDom: dom => instances.get(dom),
      init: dom => {
        const inst = { calls: [], disposed: false, resize() {}, isDisposed() { return this.disposed; }, dispose() { this.disposed = true; instances.delete(dom); }, setOption(option, merge) { this.calls.push({ option, merge }); this.option = option; } };
        instances.set(dom, inst);
        return inst;
      },
    },
  };
  context.window = context;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../theme/js/mytel-charts.js'), 'utf8'), context);
  return {
    api: context.MyTelCharts, observers, instances, colors,
    dom: () => ({ id: '', isConnected: true, getAttribute: () => null }),
    setTheme: next => { theme = next; callbacks.forEach(fn => fn()); },
  };
}

test('line axes, legends and series follow both themes without resetting interaction state', async () => {
  const f = fixture();
  const inst = f.api.line(f.dom(), null, ['00:00', '01:00'], [{ name: 'SIP', data: [1, 2] }], { zoom: true });
  await Promise.resolve();
  assert.equal(inst.option.xAxis.axisLabel.color, f.colors.light['text-muted']);
  f.setTheme('dark');
  assert.equal(inst.option.xAxis.axisLabel.color, f.colors.dark['text-muted']);
  assert.equal(inst.option.yAxis.splitLine.lineStyle.color, f.colors.dark.border);
  assert.equal(inst.option.legend.textStyle.color, f.colors.dark['text-muted']);
  assert.equal(inst.option.color[0], f.colors.dark['blue-fg']);
  assert.equal(inst.calls.at(-1).merge.notMerge, false);
  assert.equal(inst.option.legend.selected, undefined);
  assert.equal(inst.option.dataZoom[0].start, undefined);
  assert.equal(inst.option.animation, false);
  f.setTheme('light');
  assert.equal(inst.option.xAxis.axisLabel.color, f.colors.light['text-muted']);
  assert.equal(inst.option.color[0], f.colors.light['blue-fg']);
});

test('anonymous charts created together each receive theme updates', () => {
  const f = fixture();
  const one = f.api.bar(f.dom(), null, ['a'], [{ name: 'one', data: [2] }]);
  const two = f.api.bar(f.dom(), null, ['b'], [{ name: 'two', data: [3] }]);
  f.setTheme('dark');
  assert.equal(one.option.xAxis.axisLabel.color, f.colors.dark['text-muted']);
  assert.equal(two.option.xAxis.axisLabel.color, f.colors.dark['text-muted']);
});

test('nested donut colors, gauge progress and utilization gradients are repainted', () => {
  const f = fixture();
  const donut = f.api.donut(f.dom(), null, [{ name: 'SIP', value: 1 }]);
  const gauge = f.api.gauge(f.dom(), null, [{ name: 'CPU', value: 10 }]);
  const bars = f.api.bars(f.dom(), null, [{ name: '/', used: 1, total: 4 }]);
  f.setTheme('dark');
  assert.equal(donut.option.series[0].data[0].itemStyle.color, f.colors.dark['blue-fg']);
  assert.equal(donut.option.series[0].itemStyle.borderColor, f.colors.dark.surface);
  assert.equal(gauge.option.series[0].progress.itemStyle.color, f.colors.dark['primary-fg']);
  assert.equal(bars.option.series[0].itemStyle.color.colorStops[0].color, f.colors.dark['primary-fg']);
});

test('empty data remains an honest empty state after font loading and theme change', async () => {
  const f = fixture();
  const inst = f.api.line(f.dom(), null, [], [{ name: 'SIP', data: [] }]);
  await Promise.resolve();
  f.setTheme('dark');
  assert.equal(inst.option.title.text, f.api.EMPTY_MSG);
  assert.equal(inst.option.title.textStyle.color, f.colors.dark['text-faint']);
  assert.equal(inst.option.series.length, 0);
});

test('detached or explicitly disposed charts release resize observers', () => {
  const f = fixture();
  const dom = f.dom();
  const inst = f.api.bar(dom, null, ['a'], [{ name: 'a', data: [1] }]);
  dom.isConnected = false;
  f.setTheme('dark');
  assert.equal(inst.disposed, true);
  assert.equal(f.observers[0].disconnected, true);
  const other = f.dom();
  f.api.bar(other, null, ['a'], [{ name: 'b', data: [1] }]);
  f.api.disposeAll({ querySelectorAll: () => [other] });
  assert.equal(f.observers[1].disconnected, true);
});
