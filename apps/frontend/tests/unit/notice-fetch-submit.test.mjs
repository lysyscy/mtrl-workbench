/**
 * 「确认抓取」这条按钮真的会发请求（`TAIL-476` P0 的行为检查）。
 *
 * 为什么要有这个文件：单纯的源码正则检查（"这行写的是 `/^\d{4}-/`"）抓不到真正的故障 ——
 * 曾经的就是这样：正则被写成 `/^\\d{4}-/`，**按钮看着可点、点了什么也不发**，
 * 而"源码里有个像模像样的正则"这条检查照样通过。这里改成**真的跑一遍提交**：
 *   渲染 `NoticeFetch` 及其共用确认按钮，点击按钮并检查
 *   `fetch` 中的 `POST /api/m03/notices/fetch` 参数。
 *
 * 运行环境没有 DOM，所以这里用 `registerHooks` 把 `react`/`jsx-runtime` 之外的东西
 * 换成最小的替身：组件照常按 JSX 调用、hook 照常按顺序取格子，**业务代码一行不改**。
 * 这不是浏览器验证（真机安装/真实 i8 仍未验），只钉"点了会不会发、发的对不对"。
 *
 * 运行：`node --import=tsx --test tests/unit/notice-fetch-submit.test.mjs`
 */

import test, { beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

/** 每次渲染重置的 hook 格子；`noticeMonth` 用来固定"抓取月份"。 */
const cells = { list: [], index: 0, month: '2026-11' };

const stub = (source) => ({ url: `data:text/javascript,${encodeURIComponent(source)}`, shortCircuit: true });

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === 'react/jsx-runtime') {
      return stub("export const Fragment = 'fragment'; export const jsx = (type, props) => ({ type, props }); export const jsxs = (type, props) => ({ type, props });");
    }
    if (specifier === 'react') {
      return stub(`
        export const Fragment = 'fragment';
        const cell = () => { const at = globalThis.__relayCells.index++; return globalThis.__relayCells.list[at] ??= { value: undefined, set: false }; };
        export function useState(initial) {
          const slot = cell();
          if (!slot.set) { slot.set = true; slot.value = typeof initial === 'function' ? initial() : initial; }
          const index = globalThis.__relayCells.index - 1;
          if (index === 0 && globalThis.__relayCells.month !== null) slot.value = globalThis.__relayCells.month;
          return [slot.value, next => { slot.value = typeof next === 'function' ? next(slot.value) : next; }];
        }
        export function useRef(initial) { const slot = cell(); if (!slot.set) { slot.set = true; slot.value = { current: initial }; } return slot.value; }
        export function useEffect() {}
        export function useMemo(factory) { return factory(); }
        export function useCallback(fn) { return fn; }
      `);
    }
    if (specifier === '@tanstack/react-query') {
      return stub(`
        export function useQuery() { return globalThis.__relayQuery; }
        export function useQueryClient() { return { invalidateQueries() {} }; }
      `);
    }
    if (specifier === './business-modal') {
      return stub("export function BusinessModal(p) { return { type: 'wrapper', props: { children: p.children } }; }");
    }
    if (specifier === './dialog-close') {
      return stub(`
        export function DialogContents(p) { return { type: 'wrapper', props: { children: p.children } }; }
        export function useDialogClose() { return { requestClose() {} }; }
      `);
    }
    if (specifier === './history') {
      return stub('export function useHistoryGuard() {}');
    }
    if (specifier === './time-picker') {
      return stub("export function TimePicker(p) { return { type: 'time-picker', props: p }; }");
    }
    if (specifier === './i8-session') {
      return stub("export function useI8Session() { return globalThis.__relaySession; }");
    }
    if (specifier.startsWith('antd/es/')) {
      return stub('export default function Stub(p) { return { type: "antd", props: p }; }');
    }
    return nextResolve(specifier, context);
  },
});

const { NoticeFetch } = await import('../../src/notice-fetch.tsx');
const { I8FetchActions, useI8FetchAction } = await import('../../src/i8-fetch.tsx');
const { readReportFetchResult } = await import('../../src/i8-report-fetch-api.ts');

class MemoryStorage {
  #m = new Map();
  getItem(key) { return this.#m.has(key) ? this.#m.get(key) : null; }
  setItem(key, value) { this.#m.set(String(key), String(value)); }
  removeItem(key) { this.#m.delete(key); }
  clear() { this.#m.clear(); }
  get length() { return this.#m.size; }
  key(index) { return [...this.#m.keys()][index] ?? null; }
}

const me = { id: 1, account: 'tester001', name: '测试员' };
const config = { ready: true, account: 'tester001', i8_user: 'tester001', message: '' };

function action(refresh = async () => {}) {
  cells.index = 0;
  cells.month = null;
  return useI8FetchAction({source: 'settlement', me, paused: false, refresh});
}
const fetchRequest = {path: '/api/m07/fetch', payload: {month: '2026-10', confirm: true}, parse: value => readReportFetchResult('settlement', '2026-10', value)};
const reportResponse = {ok: true, ym: '2026-10', rows: 4, stats: {inserted: 2, updated: 2, deleted: 1, kept_manual: 3}};
const response = value => ({ok: true, status: 200, json: async () => value});

let restored;
beforeEach(() => {
  restored = { fetch: globalThis.fetch, sessionStorage: globalThis.sessionStorage };
  globalThis.sessionStorage = new MemoryStorage();
  globalThis.__relayCells = cells;
  globalThis.__relayQuery = { isFetching: false, isError: false, error: null, data: config, refetch: async () => {} };
  globalThis.__relaySession = { mode: 'http', connected: false, state: null, busy: false, notice: '', extensionReady: true };
  cells.list = [];
  cells.index = 0;
  cells.month = '2026-11';
});
afterEach(() => {
  globalThis.fetch = restored.fetch;
  globalThis.sessionStorage = restored.sessionStorage;
  delete globalThis.__relayCells;
  delete globalThis.__relayQuery;
  delete globalThis.__relaySession;
});

test('共用抓取动作防双击，收发结存走专属端点并可靠重读', async () => {
  let finish, calls = 0, reads = 0;
  globalThis.fetch = async () => {calls += 1; return new Promise(resolve => {finish = () => resolve(response(reportResponse));});};
  const controller = action(async () => {reads += 1;});
  const first = controller.run(fetchRequest);
  const second = controller.run(fetchRequest);
  await Promise.resolve();
  assert.equal(calls, 1);
  finish();
  assert.equal(await second, undefined);
  assert.match((await first).message, /保留手工行 3/);
  assert.equal(reads, 1);
  assert.equal(action().pending, false);
});

test('回执月份不符保留未知标记，关闭再开不能重复发起', async () => {
  let calls = 0;
  globalThis.fetch = async () => {calls += 1; return response({...reportResponse, ym: '2026-09'});};
  await action().run(fetchRequest);
  assert.equal(action().pending, true);
  cells.list = [];
  const reopened = action();
  assert.equal(reopened.pending, true);
  await reopened.run(fetchRequest);
  assert.equal(calls, 1);
  reopened.acknowledge();
  assert.equal(action().pending, false);
});

test('抓取已确认但重读失败保留回执和待核对状态，不自动重投', async () => {
  let calls = 0;
  globalThis.fetch = async () => {calls += 1; return response(reportResponse);};
  const value = await action(async () => {throw new Error('read failed');}).run(fetchRequest);
  assert.match(value.message, /抓取 4 行/);
  assert.equal(action().pending, true);
  assert.match(action().error, /重读失败/);
  assert.equal(calls, 1);
});

test('后端明确空结果沿requestJson显示原原因，不误报成功或未知', async () => {
  globalThis.fetch = async () => response({ok: false, empty: true, ym: '2026-10', message: '没有明细，未改动本地数据'});
  assert.equal(await action().run(fetchRequest), undefined);
  assert.equal(action().pending, false);
  assert.match(action().error, /未改动本地数据/);
});

test('按月回执区分库存调整保留和收发结存手工保留', () => {
  assert.match(readReportFetchResult('settlement', '2026-10', reportResponse).message, /保留手工行 3/);
  assert.throws(() => readReportFetchResult('inventory', '2026-10', reportResponse));
  assert.match(readReportFetchResult('inventory', '2026-10', {...reportResponse, stats: {...reportResponse.stats, kept_with_adjustment: 2}}).message, /保留有调整的源行 2/);
});

/** 走一遍元素树，把所有命中条件的节点收起来。 */
function walk(node, hit, found = []) {
  if (node === null || node === undefined || typeof node === 'boolean') return found;
  if (Array.isArray(node)) { for (const child of node) walk(child, hit, found); return found; }
  if (typeof node === 'object') {
    if (node.type !== undefined) {
      if (hit(node)) found.push(node);
      walk(node.props?.children, hit, found);
    }
  }
  return found;
}

/** 渲染一次（不含 ReactDOM）并返回元素树；每次渲染都从头取 hook 格子。 */
function render({ mode = 'http', connected = false } = {}) {
  cells.index = 0;
  globalThis.__relaySession = { mode, connected, state: null, busy: false, notice: '', extensionReady: true };
  return NoticeFetch({ me, blocked: false, close() {}, refresh: async () => {} });
}

function confirmButton(tree) {
  const [actions] = walk(tree, node => node.type === I8FetchActions);
  assert.ok(actions, '必须渲染出共用抓取操作');
  const [button] = walk(I8FetchActions(actions.props), node => node.props?.children === '确认抓取');
  assert.ok(button, '必须存在确认抓取按钮');
  return button;
}

/** 点击共用确认按钮，再等请求和回执处理完成。 */
async function submit(tree) {
  confirmButton(tree).props.onClick();
  for (let i = 0; i < 40; i += 1) await new Promise(resolve => setTimeout(resolve, 5));
}

function recorder() {
  const calls = [];
  globalThis.fetch = async (path, init = {}) => {
    calls.push({ path, method: init.method ?? 'GET', body: init.body ? JSON.parse(init.body) : null, headers: init.headers ?? {} });
    return {
      status: 200,
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ year_month: '2026-11', fetched: 3, upserted: 3, ignored: [] }),
    };
  };
  return calls;
}

test('月份是正常值、直连方式：点「确认抓取」会真的发出 POST /api/m03/notices/fetch', async () => {
  const calls = recorder();
  const tree = render({ mode: 'http' });
  const submitButton = confirmButton(tree);
  assert.equal(submitButton.props.disabled, false, '月份合法时按钮不能是禁用状态');
  await submit(tree);
  assert.equal(calls.length, 1, '点一次必须只发一次请求');
  assert.equal(calls[0].path, '/api/m03/notices/fetch');
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].body.year_month, '2026-11', '发出去的月份必须就是界面上那个月');
  assert.equal(calls[0].body.session_mode, 'http');
  assert.equal(calls[0].body.allow_kick, true, '直连方式保持产品原有的强踢授权语义');
  assert.equal(calls[0].body.expected_account, 'tester001');
});

test('选浏览器方式且已连接：同一按钮改走浏览器通道，且不带强踢授权', async () => {
  const calls = recorder();
  const tree = render({ mode: 'browser', connected: true });
  await submit(tree);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/api/m03/notices/fetch');
  assert.equal(calls[0].body.session_mode, 'browser');
  assert.ok(calls[0].body.device_id, '浏览器方式必须带本页连接标识');
  assert.equal('allow_kick' in calls[0].body, false, '浏览器方式不得请求强踢');
});

test('选了浏览器方式但连接不在：一个字都不发（不许悄悄改用登录）', async () => {
  const calls = recorder();
  const tree = render({ mode: 'browser', connected: false });
  const submitButton = confirmButton(tree);
  assert.equal(submitButton.props.disabled, true, '没连接时按钮必须是禁用状态');
  await submit(tree);
  assert.equal(calls.length, 0, '⛔ 连接不在时绝不能退回登录再抓');
});

test('月份不合法时不发请求（原来的正则回归守卫）', async () => {
  const calls = recorder();
  cells.month = '2026-11-05';
  const tree = render({ mode: 'http' });
  assert.equal(confirmButton(tree).props.disabled, true);
  await submit(tree);
  assert.equal(calls.length, 0, '不是 YYYY-MM 的月份必须当场停，不能发出去猜');
});
