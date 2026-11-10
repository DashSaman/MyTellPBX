/* Civil dates are intentionally independent of the browser's timezone. */
'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const theme = fs.readFileSync(path.join(root,'theme/js/theme.js'),'utf8');
const context = {window:{}, Date, Intl, console};
vm.createContext(context);
vm.runInContext(theme.slice(theme.indexOf('var MT = window.MTJalali'), theme.indexOf('$(document).ready')),context);
vm.runInContext(fs.readFileSync(path.join(root,'theme/js/calendar-core.js'),'utf8'),context);
const core = context.window.MTCalendarCore;
test('Nowruz round trip and Persian digits',()=>{
  assert.equal(core.fromJalali('۱۴۰۵/۰۱/۰۱','۰۹:۰۵'),'2026-03-21 09:05');
  assert.equal(core.toJalali('2026-03-21 09:05').date,'1405/01/01');
});
test('Arabic digits are normalized',()=>assert.equal(core.fromJalali('١٤٠٥/٠٨/٢٤','١٠:٣٠'),'2026-11-15 10:30'));
test('Leap Esfand is validated, not normalized',()=>{
  assert.equal(core.fromJalali('1403/12/30','23:59'),'2025-03-20 23:59');
  assert.equal(core.fromJalali('1404/12/30','10:00'),null);
});
test('Impossible months, days, times and empty values are rejected',()=>{
  for(const d of ['', '1405/13/01','1405/07/31','1405/00/01','1405/01/00','abc','9999/01/01']) assert.equal(core.fromJalali(d,'10:00'),null,d);
  for(const t of ['', '24:00','10:60','-1:30','1pm']) assert.equal(core.fromJalali('1405/01/01',t),null,t);
});
test('Gregorian validation is strict',()=>{
  assert.equal(core.serialize('2026-02-31 10:00'),null);
  assert.equal(core.serialize('2024-02-29 10:00'),'2024-02-29 10:00:00');
});
test('ISO offset does not change server wall fields',()=>{
  assert.equal(core.serialize('2026-11-15T00:15:00+01:00'),'2026-11-15 00:15:00');
  assert.equal(core.toJalali('2026-11-15T10:00:00+01:00').time,'10:00');
});
test('Dragged Date serializes local calendar fields, without UTC conversion',()=>{
  assert.equal(core.serialize(new Date(2026,10,15,10,30)),'2026-11-15 10:30:00');
});
test('Month range covers the entire Aban grid, including November 15',()=>{
  const r=core.monthRange(1405,8);
  assert.equal(r.start,'2026-10-17'); assert.equal(r.end,'2026-11-28');
  assert.equal(r.count,42); assert.equal(r.length,30);
});
test('Month range crosses Gregorian and Jalali year boundaries',()=>{
  const r=core.monthRange(1404,12);
  assert.equal(r.length,29); assert.ok(r.start<'2026-03-01');assert.ok(r.end>='2026-03-21');
});
test('Valid year boundary remains reversible',()=>{
  for(const d of ['1404/12/29','1405/01/01','1405/06/31','1405/07/01']) assert.equal(core.toJalali(core.fromJalali(d,'12:00')).date,d);
});
test('Civil arithmetic crosses midnight and browser DST independently',()=>{
 assert.equal(core.addMinutes('2026-12-31 23:30',60),'2027-01-01 00:30');
 assert.equal(core.addMinutes('2027-03-14 01:30',60),'2027-03-14 02:30');
});
