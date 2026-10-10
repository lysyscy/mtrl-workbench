// 前端时间统一工具测试（app.js：beijingNow / monthBounds / yearBounds / rangePresets）
// 运行：node --test tests/js/time.test.js
// 背景（2026-09-10）：时间口径澄清为「点/区间」两形态，核算期=自然月（1号~月末），
//   这些纯函数是全前端时间边界计算的权威来源，需单独覆盖（含闰年、跨年边界）。
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const APP = path.join(__dirname, '..', '..', 'app', 'static', 'app.js');

// 跨 realm 对象比较：vm 上下文返回的对象原型与主 realm 不同，deepStrictEqual 会误报，
// 统一 JSON 序列化后比较（字段级，可靠）。
function eqJson(actual, expected) {
  assert.equal(JSON.stringify(actual), JSON.stringify(expected));
}

// 最小运行环境：app.js 的 IIFE 需要 location / document / fetch / window（window===全局）
function loadAppJs() {
  const document = {
    querySelectorAll: () => [],
    querySelector: () => null,
    getElementById: () => null,
    createElement: () => ({ value: '', textContent: '', disabled: false }),
  };
  const location = { pathname: '/' };
  const fetch = () => Promise.resolve({ status: 200, json: () => Promise.resolve({}) });
  const sandbox = { document, location, fetch, console, setTimeout, clearTimeout };
  sandbox.window = sandbox;   // 关键：window === 全局对象，让 window.x = y 等价于全局 x = y
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(APP, 'utf8'), sandbox);
  return sandbox;
}

test('monthBounds: 自然月 1号~月末（含闰年 2 月）', () => {
  const w = loadAppJs();
  eqJson(w.monthBounds('2026-09'), { start: '2026-09-01', end: '2026-09-30' });
  eqJson(w.monthBounds('2026-02'), { start: '2026-02-01', end: '2026-02-28' });
  eqJson(w.monthBounds('2024-02'), { start: '2024-02-01', end: '2024-02-29' }); // 闰年
  eqJson(w.monthBounds('2026-12'), { start: '2026-12-01', end: '2026-12-31' });
  eqJson(w.monthBounds([2026, 8]), { start: '2026-08-01', end: '2026-08-31' }); // 数组入参
  assert.equal(w.monthBounds('2026-13'), null);   // 非法月份 → null
  assert.equal(w.monthBounds(''), null);          // 空串 → null
});

test('yearBounds: 年初 ~ 年末', () => {
  const w = loadAppJs();
  eqJson(w.yearBounds(2026), { start: '2026-01-01', end: '2026-12-31' });
});

test('rangePresets: 本月/上月/本年 与 monthBounds/yearBounds 一致', () => {
  const w = loadAppJs();
  const bn = w.beijingNow();
  const p = w.rangePresets();

  // 本月 = 当前北京年月
  eqJson(p['本月'], w.monthBounds(bn.yyyyMM));

  // 本年
  eqJson(p['本年'], { start: bn.year + '-01-01', end: bn.year + '-12-31' });

  // 上月（跨年：1 月 → 上年 12 月）
  const prevM = bn.month === 1 ? 12 : bn.month - 1;
  const prevY = bn.month === 1 ? bn.year - 1 : bn.year;
  eqJson(p['上月'], w.monthBounds(prevY + '-' + String(prevM).padStart(2, '0')));
});

test('beijingNow: 格式与自洽性', () => {
  const w = loadAppJs();
  const bn = w.beijingNow();
  assert.match(bn.yyyyMM, /^\d{4}-\d{2}$/);
  assert.match(bn.yyyyMMdd, /^\d{4}-\d{2}-\d{2}$/);
  // 本月首日 = beijingNow 的年月 + -01
  assert.equal(w.monthBounds(bn.yyyyMM).start, bn.yyyyMM + '-01');
});
