// 前端公共工具测试（零依赖：用最小 DOM stub，不引入 jsdom）
// 运行：node --test tests/js/
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const COMMON = path.join(__dirname, '..', '..', 'app', 'static', 'pages', 'common.js');

// 构造最小运行环境：只需 window + document.getElementById + document.createElement
// 关键：让 window 指向全局对象本身（模拟浏览器 window===globalThis），
// 否则 common.js 里的 `window.App = ...` 不会让 `App` 成为 vm 全局变量，
// 后续 `App.esc = ...` 会抛 ReferenceError（预存测试 bug，2026-09-10 修复）。
function loadApp(selects) {
  const document = {
    getElementById: (id) => (selects && selects[id]) || null,
    createElement: () => ({ value: '', textContent: '', disabled: false }),
  };
  const sandbox = { document };
  sandbox.window = sandbox;                       // window === 全局对象
  sandbox.window.document = document;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(COMMON, 'utf8'), sandbox);
  return sandbox.App;
}

function mockSelect() {
  return {
    innerHTML: '',
    value: '',
    _options: [],
    appendChild(o) { this._options.push(o); },
  };
}

test('esc: 转义 5 个危险字符，中文保留', () => {
  const App = loadApp({});
  assert.equal(App.esc('<script>&"\'</script>'), '&lt;script&gt;&amp;&quot;&#39;&lt;/script&gt;');
  assert.equal(App.esc('内蒙石灰窑项目'), '内蒙石灰窑项目');
  assert.equal(App.esc(null), '');
  assert.equal(App.esc(undefined), '');
  assert.equal(App.esc(0), '0');
});

test('fmt: 千分位 + 2 位小数；空值/非数字 → —', () => {
  const App = loadApp({});
  assert.equal(App.fmt(1234567.891), '1,234,567.89');
  assert.equal(App.fmt(0), '0.00');
  assert.equal(App.fmt(-2000.5), '-2,000.50');
  assert.equal(App.fmt(null), '—');
  assert.equal(App.fmt(''), '—');
  assert.equal(App.fmt('abc'), '—');
});

test('fillSelectWithDisable: 选项保留 + 无数据置灰', () => {
  const sel = mockSelect();
  const App = loadApp({ 'x-sel': sel });
  App.fillSelectWithDisable('x-sel', ['2026-08', '2026-09'], ['2026-09'], '全部');
  // 全量 2 项都保留，其中 08 无数据被置灰
  assert.equal(sel._options.length, 2);
  assert.equal(sel._options[0].value, '2026-08');
  assert.equal(sel._options[0].disabled, true);
  assert.equal(sel._options[1].value, '2026-09');
  assert.equal(sel._options[1].disabled, false);
});

test('fillSelectWithDisable: 选中值被置灰 → 回落全部', () => {
  const sel = mockSelect();
  sel.value = '2026-08';
  const App = loadApp({ 'y-sel': sel });
  App.fillSelectWithDisable('y-sel', ['2026-08', '2026-09'], ['2026-09'], '全部');
  assert.equal(sel.value, '');
});

test('fillSelectWithDisable: 元素缺失时静默跳过不抛错', () => {
  const App = loadApp({});
  assert.doesNotThrow(() => App.fillSelectWithDisable('not-exist', ['a'], ['a'], '全部'));
});

test('beijingNow: 返回北京时间年月日 + 格式化字符串', () => {
  const App = loadApp({});
  const bn = App.beijingNow();
  assert.ok(bn && typeof bn === 'object', '应返回对象');
  assert.equal(typeof bn.year, 'number');
  assert.equal(typeof bn.month, 'number');
  assert.equal(typeof bn.day, 'number');
  assert.ok(bn.month >= 1 && bn.month <= 12, '月份应在 1-12');
  assert.ok(bn.day >= 1 && bn.day <= 31, '日期应在 1-31');
  // yyyyMM / yyyyMMdd 格式：YYYY-MM / YYYY-MM-DD
  assert.match(bn.yyyyMM, /^\d{4}-\d{2}$/);
  assert.match(bn.yyyyMMdd, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(bn.yyyyMM, `${bn.year}-${String(bn.month).padStart(2, '0')}`);
  assert.equal(bn.yyyyMMdd, `${bn.yyyyMM}-${String(bn.day).padStart(2, '0')}`);
});
