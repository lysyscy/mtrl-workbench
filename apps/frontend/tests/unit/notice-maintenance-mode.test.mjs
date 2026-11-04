/**
 * 「查询 i8 仓库名单」也属于一次 i8 取数（`TAIL-476` S1a 的行为检查）。
 *
 * 为什么单列一个文件：这个按钮曾经**完全不带会话来源**，选了「浏览器已有会话」
 * 之后它还是会去登录 i8、可能把账号顶下线 —— 而这在源码里看不出来（它只是少拼一个字段）。
 * 这里真的渲染 `MaintenanceDialog` 并点一下按钮，断言发出去的 body 里到底有什么。
 *
 * 覆盖：
 *   1. 选了浏览器方式且已连接 ⇒ `session_mode=browser` + 本页 `device_id`，⛔ 不带强踢；
 *   2. 选了直连 ⇒ `session_mode=http` + 原来的 `allow_kick=true` 逐字节不变；
 *   3. 选了浏览器方式但连接不在 ⇒ 按钮禁用、**零请求**（⛔ 不退回登录）。
 *
 * 运行：`node --import=tsx --test tests/unit/notice-maintenance-mode.test.mjs`
 */

import test, { beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

const cells = { list: [], index: 0, overrides: {} };
const stub = source => ({ url: `data:text/javascript,${encodeURIComponent(source)}`, shortCircuit: true });

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === 'react/jsx-runtime') {
      return stub("export const Fragment = 'fragment'; export const jsx = (type, props) => ({ type, props }); export const jsxs = (type, props) => ({ type, props });");
    }
    if (specifier === 'react') {
      return stub(`
        export const Fragment = 'fragment';
        const cell = () => { const at = globalThis.__notCells.index++; return globalThis.__notCells.list[at] ??= { value: undefined, set: false }; };
        export function useState(initial) {
          const slot = cell();
          const index = globalThis.__notCells.index - 1;
          if (!slot.set) { slot.set = true; slot.value = typeof initial === 'function' ? initial() : initial; }
          if (index in globalThis.__notCells.overrides) slot.value = globalThis.__notCells.overrides[index];
          return [slot.value, next => { slot.value = next; }];
        }
        export function useRef(initial) { const slot = cell(); if (!slot.set) { slot.set = true; slot.value = { current: initial }; } return slot.value; }
        export function useEffect() {}
        export function useMemo(factory) { return factory(); }
        export function useCallback(fn) { return fn; }
      `);
    }
    if (specifier === '@tanstack/react-query') {
      return stub("export function useQuery() { return globalThis.__notQuery; } export function useQueryClient() { return { invalidateQueries() {} }; }");
    }
    if (specifier === 'antd/es/button') {
      return stub('export default function Button(p) { return { type: "button", props: p }; }');
    }
    if (specifier === 'react-router') {
      return stub("export function Link(p) { return { type: 'link', props: p }; }");
    }
    if (specifier === './business-modal') {
      return stub("export function BusinessModal(p) { return { type: 'wrapper', props: { children: p.children } }; }");
    }
    if (specifier === './dialog-close') {
      return stub("export function DialogContents(p) { return { type: 'wrapper', props: { children: p.children } }; } export function useDialogClose() { return { requestClose() {} }; }");
    }
    if (specifier === './time-picker') {
      return stub("export function BusinessDate(p) { return { type: 'date', props: p }; }");
    }
    if (specifier === './ledger-controls') {
      return stub("export function ProjectPicker(p) { return { type: 'picker', props: p }; }");
    }
    if (specifier === './notice-contract') {
      return stub("export function ContractDialog() { return { type: 'contract', props: {} }; }");
    }
    if (specifier === './notices-api') {
      return stub(`
        export const categories = {};
        export const currentMonth = () => '2026-11';
        export const money = value => String(value);
        export const receipt = () => '';
        export const body = payload => ({ body: JSON.stringify(payload), headers: { 'Content-Type': 'application/json' } });
      `);
    }
    if (specifier === './i8-session') {
      return stub("export function useI8Session() { return globalThis.__notSession; }");
    }
    return nextResolve(specifier, context);
  },
});

const { NoticeDialog } = await import('../../src/notice-maintenance.tsx');

class MemoryStorage {
  #m = new Map();
  getItem(key) { return this.#m.has(key) ? this.#m.get(key) : null; }
  setItem(key, value) { this.#m.set(String(key), String(value)); }
  removeItem(key) { this.#m.delete(key); }
  clear() { this.#m.clear(); }
  get length() { return this.#m.size; }
  key(index) { return [...this.#m.keys()][index] ?? null; }
}

const row = { notice_id: 7, bill_no: 'ZD-7', bill_name: '钢材采购', project_name: '第四工程公司', project_display: '第四工程公司' };
let restored;

beforeEach(() => {
  restored = { fetch: globalThis.fetch, sessionStorage: globalThis.sessionStorage, window: globalThis.window };
  globalThis.sessionStorage = new MemoryStorage();
  globalThis.window = { dispatchEvent() {} };
  globalThis.__notCells = cells;
  globalThis.__notQuery = {
    isPending: false,
    isFetching: false,
    isError: false,
    error: null,
    refetch: async () => {},
    data: { reason: '请指定归属', candidates: [], shell_id: 0 },
  };
  globalThis.__notSession = { mode: 'http', connected: false, state: null, busy: false, notice: '', extensionReady: true, halted: false };
  cells.list = [];
  cells.index = 0;
  // useRef(lock)=0 → useState(newName)=1 … useState(value)=7；只在这次渲染里塞这两个格子。
  cells.overrides = { 1: '新建仓库A', 7: 'new' };
});

afterEach(() => {
  globalThis.fetch = restored.fetch;
  globalThis.sessionStorage = restored.sessionStorage;
  globalThis.window = restored.window;
  delete globalThis.__notCells;
  delete globalThis.__notQuery;
  delete globalThis.__notSession;
});

/**
 * 走一遍元素树，把所有命中条件的节点收起来。
 *
 * 这里比 `notice-fetch-submit.test.mjs` 多做一步：`NoticeDialog` 返回的是
 * `<MaintenanceDialog {...props} />` 这个**元素**（不是渲染结果），所以在命中判定之后
 * 还要把函数型组件真的调用一次，才能看到它里面的按钮 —— 否则"按钮不存在"只是因为没渲染。
 */
function walk(node, hit, found = []) {
  if (node === null || node === undefined || typeof node === 'boolean') return found;
  if (Array.isArray(node)) { for (const child of node) walk(child, hit, found); return found; }
  if (typeof node === 'object' && node.type !== undefined) {
    if (hit(node)) found.push(node);
    if (typeof node.type === 'function') walk(node.type(node.props ?? {}), hit, found);
    else walk(node.props?.children, hit, found);
  }
  return found;
}

function render(mode, connected) {
  cells.index = 0;
  cells.list = [];
  globalThis.__notSession = { mode, connected, state: null, busy: false, notice: '', extensionReady: true, halted: false };
  return NoticeDialog({ state: { kind: 'ownership', row }, projects: [], blocked: false, close() {}, refresh: async () => {}, announce() {} });
}

function warehouseButton(tree) {
  const [button] = walk(tree, node => node.props?.children === '查询 i8 仓库名单');
  return button;
}

function recorder() {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, method: init.method ?? 'GET', body: init.body ? JSON.parse(init.body) : null });
    return { status: 200, ok: true, headers: { get: () => 'application/json' }, json: async () => ({ found: true, degraded: false, message: '已取到名单', from_cache: false, cached_at: '', owners: ['第四工程公司'] }) };
  };
  return calls;
}

async function click(button) {
  button.props.onClick();
  for (let i = 0; i < 40; i += 1) await new Promise(resolve => setTimeout(resolve, 5));
}

test('仓库名单：选了浏览器方式且已连接 ⇒ 带 session_mode=browser 与本页 device_id，⛔ 不带强踢', async () => {
  const calls = recorder();
  const button = warehouseButton(render('browser', true));
  assert.ok(button, '必须渲染出「查询 i8 仓库名单」按钮');
  assert.equal(button.props.disabled, false);
  await click(button);
  assert.equal(calls.length, 1, '点一次只发一次');
  assert.equal(calls[0].url, '/api/m03/notices/warehouse-check');
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].body.session_mode, 'browser', '⛔ 漏掉这个字段就会退回登录、可能顶号');
  assert.match(calls[0].body.device_id, /^dev-[0-9a-f-]{36}$/);
  assert.equal(calls[0].body.warehouse_name, '新建仓库A');
  assert.equal('allow_kick' in calls[0].body, false, '浏览器方式不得请求强踢');
});

test('仓库名单：选了直连 ⇒ session_mode=http 且保留原来的强踢授权', async () => {
  const calls = recorder();
  await click(warehouseButton(render('http', false)));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].body.session_mode, 'http');
  assert.equal(calls[0].body.allow_kick, true, '直连保持改动前的授权语义');
  assert.equal(calls[0].body.warehouse_name, '新建仓库A');
  assert.equal('device_id' in calls[0].body, false);
});

test('仓库名单：选了浏览器方式但连接不在 ⇒ 按钮禁用、零请求（⛔ 不退回登录）', async () => {
  const calls = recorder();
  const button = warehouseButton(render('browser', false));
  assert.ok(button, '按钮仍要显示，好让用户知道该去哪儿重连');
  assert.equal(button.props.disabled, true, '没连接时必须禁用');
  await click(button);
  assert.equal(calls.length, 0, '⛔ 连接不在时一个字都不发');
});
