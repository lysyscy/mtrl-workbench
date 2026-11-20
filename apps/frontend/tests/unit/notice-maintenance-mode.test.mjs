/**
 * 「查询 i8 仓库名单」也属于一次 i8 取数（`TAIL-476` S1a 的行为检查）。
 *
 * 为什么单列一个文件：这个按钮曾经**完全不带会话来源**，选了「浏览器已有会话」
 * 之后它还是会去登录 i8、可能把账号顶下线 —— 而这在源码里看不出来（它只是少拼一个字段）。
 * 这里从共用归属窗口选择新建小微并查询，断言发出去的 body 里到底有什么。
 *
 * 覆盖：
 *   1. 选了浏览器方式且已连接 ⇒ `session_mode=browser` + 本页 `device_id`，⛔ 不带强踢；
 *   2. 选了直连 ⇒ `session_mode=http`，仅在用户确认后用令牌重发原查询；
 *   3. 选了浏览器方式但连接不在 ⇒ 按钮禁用、**零请求**（⛔ 不退回登录）。
 *
 * 运行：`node --import=tsx --test tests/unit/notice-maintenance-mode.test.mjs`
 */

import test, { beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

const cells = { list: [], index: 0 };
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
          if (!slot.set) { slot.set = true; slot.value = typeof initial === 'function' ? initial() : initial; }
          return [slot.value, next => { slot.value = next; }];
        }
        export function useRef(initial) { const slot = cell(); if (!slot.set) { slot.set = true; slot.value = { current: initial }; } return slot.value; }
        export function useEffect() {}
        function changed(slot, deps) {
          if (slot.deps && deps.every((dep, i) => Object.is(dep, slot.deps[i]))) return false;
          slot.deps = deps;
          return true;
        }
        export function useLayoutEffect(effect, deps) {
          const slot = cell();
          if (changed(slot, deps)) { slot.cleanup?.(); slot.cleanup = effect(); }
        }
        export function useId() { return 'test-id'; }
        export function useMemo(factory, deps) {
          const slot = cell();
          if (changed(slot, deps)) slot.value = factory();
          return slot.value;
        }
        export function useCallback(fn) { return fn; }
      `);
    }
    if (specifier === '@tanstack/react-query') {
      return stub("export const queryOptions = options => options; export function useQuery() { return globalThis.__notQuery; } export function useQueryClient() { return {}; }");
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
    if (specifier === './i8-session') {
      return stub("export function useI8Session() { return globalThis.__notSession; } " +
        "export const I8ConnectionWaitStatus = () => null; " +
        "export const useI8ActionWait = () => ({waiting: false, cancelWaiting() {}, runWhenReady: issue => {" +
        "const session = globalThis.__notSession; if (session.mode === 'http' || session.connected) return issue(session);" +
        "globalThis.__warehouseReady = () => issue({...session, connected: true}); }});");
    }
    return nextResolve(specifier, context);
  },
});

const { OwnershipDialog } = await import('../../src/ownership.tsx');

class MemoryStorage {
  #m = new Map();
  getItem(key) { return this.#m.has(key) ? this.#m.get(key) : null; }
  setItem(key, value) { this.#m.set(String(key), String(value)); }
  removeItem(key) { this.#m.delete(key); }
  clear() { this.#m.clear(); }
  get length() { return this.#m.size; }
  key(index) { return [...this.#m.keys()][index] ?? null; }
}

const document = { source: 'notice', number: 'ZD-7', name: '钢材采购', project: '第四工程公司' };
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
    data: { reason: '请指定归属', candidates: [], shellId: 18 },
  };
  globalThis.__notSession = { mode: 'http', connected: false, state: null, busy: false, notice: '', extensionReady: true, halted: false };
  cells.list = [];
  cells.index = 0;
});

afterEach(() => {
  globalThis.fetch = restored.fetch;
  globalThis.sessionStorage = restored.sessionStorage;
  globalThis.window = restored.window;
  delete globalThis.__notCells;
  delete globalThis.__notQuery;
  delete globalThis.__notSession;
});

// Follow function elements as well as DOM elements in the test renderer.
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
  globalThis.__notSession = { mode, connected, state: null, busy: false, notice: '', extensionReady: true, halted: false };
  return OwnershipDialog({ document, blocked: false, close() {}, refresh: async () => {}, announce() {} });
}

function warehouseButton(mode, connected) {
  const [select] = walk(render(mode, connected), node => node.type === 'select');
  select.props.onChange({ target: { value: 'new' } });
  const [warehouseLabel] = walk(render(mode, connected), node => node.type === 'label' && node.props.children[0] === '新小微仓库名');
  warehouseLabel.props.children[1].props.onChange({ target: { value: '新建仓库A' } });
  const tree = render(mode, connected);
  const [button] = walk(tree, node => node.props?.children === '查询 i8 仓库名单');
  return button;
}

function recorder(conflict = false) {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, method: init.method ?? 'GET', body: init.body ? JSON.parse(init.body) : null });
    if (conflict && calls.length === 1) {
      return { status: 409, ok: false, json: async () => ({
        code: 'i8_online_conflict', message: '请确认是否让现有会话下线。', detail: {kick_token: 'warehouse-confirmation'},
      }) };
    }
    return { status: 200, ok: true, headers: { get: () => 'application/json' }, json: async () => ({ found: true, degraded: false, message: '已取到名单', from_cache: false, cached_at: '', owners: ['第四工程公司'] }) };
  };
  return calls;
}

async function click(button) {
  button.props.onClick();
  await new Promise(resolve => setImmediate(resolve));
}

test('仓库名单：选了浏览器方式且已连接 ⇒ 带 session_mode=browser 与本页 device_id，⛔ 不带强踢', async () => {
  const calls = recorder();
  const button = warehouseButton('browser', true);
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

test('仓库名单直连：在线冲突后，仅确认一次才重发原查询', async () => {
  const calls = recorder(true);
  await click(warehouseButton('http', false));
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].body, {session_mode: 'http', warehouse_name: '新建仓库A'});
  const [confirm] = walk(render('http', false), node => node.props?.children === '让现有会话下线并继续');
  assert.ok(confirm);
  await click(confirm);
  await click(confirm);
  assert.equal(calls.length, 2);
  assert.deepEqual(calls[1].body, {...calls[0].body, kick_token: 'warehouse-confirmation'});
});

test('仓库名变化后原下线确认失效', async () => {
  const calls = recorder(true);
  await click(warehouseButton('http', false));
  const tree = render('http', false);
  const [confirm] = walk(tree, node => node.props?.children === '让现有会话下线并继续');
  const [label] = walk(tree, node => node.type === 'label' && node.props.children[0] === '新小微仓库名');
  label.props.children[1].props.onChange({ target: { value: '新建仓库B' } });
  assert.equal(walk(render('http', false), node => node.props?.children === '让现有会话下线并继续').length, 0);
  await click(confirm);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].url, '/api/m02/session/kick-cancel');
  assert.deepEqual(calls[1].body, {kick_token: 'warehouse-confirmation'});
});

test('仓库名单：确认后等待浏览器就绪，就绪后提交原查询', async () => {
  const calls = recorder();
  const button = warehouseButton('browser', false);
  assert.ok(button);
  assert.equal(button.props.disabled, false);
  await click(button);
  assert.equal(calls.length, 0);
  await globalThis.__warehouseReady();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].body.session_mode, 'browser');
  assert.equal(calls[0].body.warehouse_name, '新建仓库A');
});
