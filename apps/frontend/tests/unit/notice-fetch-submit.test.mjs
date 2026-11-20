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
        export function createContext() { return {}; }
        export function useContext() { return globalThis.__relaySession; }
        const cell = () => { const at = globalThis.__relayCells.index++; return globalThis.__relayCells.list[at] ??= { value: undefined, set: false }; };
        export function useState(initial) {
          const slot = cell();
          if (!slot.set) { slot.set = true; slot.value = typeof initial === 'function' ? initial() : initial; }
          const index = globalThis.__relayCells.index - 1;
          if (index === 0 && globalThis.__relayCells.month !== null) slot.value = globalThis.__relayCells.month;
          return [slot.value, next => { slot.value = typeof next === 'function' ? next(slot.value) : next; }];
        }
        export function useRef(initial) { const slot = cell(); if (!slot.set) { slot.set = true; slot.value = { current: initial }; } return slot.value; }
        export function useEffect(effect, deps) {
          const slot = cell();
          if (slot.deps && deps.every((dep, index) => Object.is(dep, slot.deps[index]))) return;
          slot.cleanup?.();
          slot.deps = deps;
          slot.cleanup = effect();
        }
        export function useMemo(factory, deps) {
          const slot = cell();
          if (!slot.deps || !deps.every((dep, index) => Object.is(dep, slot.deps[index]))) {
            slot.deps = deps;
            slot.value = factory();
          }
          return slot.value;
        }
        export function useId() { return 'fixture-id'; }
        export const useLayoutEffect = useEffect;
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
      return stub("export const BusinessModalTitle = {}; export function BusinessModal(p) { return { type: 'wrapper', props: p }; }");
    }
    if (specifier === 'motion/react') return stub('export const useIsPresent = () => true;');
    if (specifier === './history') {
      return stub('export function useHistoryGuard() {}');
    }
    if (specifier === './read-region') {
      return stub('export function ReadFailure() {}');
    }
    if (specifier === './time-picker') {
      return stub("export const TimePicker = 'time-picker'; export const BusinessDate = 'business-date';");
    }
    if (specifier === './workspace-motion') return stub("export const DialogPresence = 'presence';");
    if (specifier === './business-grid') return stub("export const ReadGrid = 'grid';");
    if (specifier === './ownership') return stub(
      "export const OwnershipDialog = 'ownership'; export const OwnershipProjectLink = 'project-link';" +
      "export function useContractOwnershipPending() {return {read: {}, omit() {}};}",
    );
    if (specifier === 'react-router') return stub("export const Link = 'link';");
    if (specifier === './grid') return stub("export const numberColumnWidth = () => ({}); export const textWidth = numberColumnWidth;");
    if (specifier === './grid-text') return stub("export const EllipsisText = 'ellipsis';");
    if (specifier === './mechanical-details') return stub("export const MechanicalDialog = 'mechanical-dialog';");
    if (specifier === 'antd') return stub("export const Button = 'button'; export const Checkbox = 'checkbox'; export const Input = {}; export const Select = 'select';");
    if (specifier.startsWith('antd/es/')) {
      return stub('export default function Stub(p) { return { type: "antd", props: p }; }');
    }
    return nextResolve(specifier, context);
  },
});

const { NoticeFetch } = await import('../../src/notice-fetch.tsx');
const { I8ReportFetch } = await import('../../src/i8-report-fetch.tsx');
const { ContractFetch } = await import('../../src/contract-tools.tsx');
const { MechanicalWork } = await import('../../src/mechanical-work.tsx');
const { useI8KickConfirmation } = await import('../../src/i8-kick-confirmation.tsx');
const { ApiError } = await import('../../src/api.ts');
const { I8FetchActions, I8FetchStatus, useI8FetchAction } = await import('../../src/i8-fetch.tsx');
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
  assert.equal((await first).summary.kept_manual, 3);
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

test('抓取已确认但重读失败保留回执，重读台账只发本地读请求', async () => {
  let calls = 0, reads = 0;
  globalThis.fetch = async () => {calls += 1; return response(reportResponse);};
  const refresh = async () => {if (++reads === 1) throw new Error('read failed');};
  const value = await action(refresh).run(fetchRequest);
  assert.equal(value.summary.total, 4);
  const controller = action(refresh);
  assert.equal(controller.pending, false);
  assert.equal(controller.error, '');
  assert.equal(controller.refreshError, 'read failed');
  await controller.reread();
  assert.equal(action().refreshError, '');
  assert.equal(reads, 2);
  assert.equal(calls, 1);
});

test('后端明确空结果沿requestJson显示原原因，不误报成功或未知', async () => {
  globalThis.fetch = async () => response({ok: false, empty: true, ym: '2026-10', message: '没有明细，未改动本地数据'});
  assert.equal(await action().run(fetchRequest), undefined);
  assert.equal(action().pending, false);
  assert.match(action().error, /未改动本地数据/);
});

test('按月回执区分库存调整保留和收发结存手工保留', () => {
  assert.equal(readReportFetchResult('settlement', '2026-10', reportResponse).summary.kept_manual, 3);
  assert.throws(() => readReportFetchResult('inventory', '2026-10', reportResponse));
  assert.equal(readReportFetchResult('inventory', '2026-10', {...reportResponse, stats: {...reportResponse.stats, kept_with_adjustment: 2}}).summary.kept_with_adjustment, 2);
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
function render({ mode = 'http', connected = false, owner = 'tester001', waitForBrowser = async () => connected } = {}) {
  cells.index = 0;
  globalThis.__relaySession = { mode, connected, state: null, busy: false, notice: '',
    actionKey: JSON.stringify([owner, mode]), extensionReady: true, waitForBrowser };
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
  assert.equal('allow_kick' in calls[0].body, false);
  assert.equal('kick_token' in calls[0].body, false);
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

test('浏览器连接就绪前零提交，就绪后只发送确认过的月份一次', async () => {
  const calls = recorder();
  const ready = Promise.withResolvers();
  let waits = 0;
  const options = {mode: 'browser', waitForBrowser: () => {waits += 1; return ready.promise;}};
  const tree = render(options);
  const submitButton = confirmButton(tree);
  assert.equal(submitButton.props.disabled, false);
  submitButton.props.onClick();
  submitButton.props.onClick();
  assert.equal(waits, 1);
  assert.equal(actionsOf(render(options)).action.waiting, true);
  assert.equal(calls.length, 0);
  ready.resolve(true);
  await settle();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].body.session_mode, 'browser');
  assert.equal(calls[0].body.year_month, '2026-11');
});

for (const invalidation of ['cancel', 'close', 'scope', 'mode', 'owner']) {
  test(`${invalidation} 解除连接等待，迟到的就绪事件不能提交`, async () => {
    const calls = recorder();
    const ready = Promise.withResolvers();
    let signal;
    const options = {mode: 'browser', waitForBrowser: value => {signal = value; return ready.promise;}};
    confirmButton(render(options)).props.onClick();
    const waiting = render(options);
    if (invalidation === 'cancel') kickButton(waiting, '取消等待').props.onClick();
    if (invalidation === 'close') waiting.props.requestClose();
    if (invalidation === 'scope') {cells.month = '2026-10'; render(options);}
    if (invalidation === 'mode') render({mode: 'http'});
    if (invalidation === 'owner') render({...options, owner: 'another'});
    assert.equal(signal.aborted, true);
    ready.resolve(true);
    await settle();
    assert.equal(calls.length, 0);
  });
}

test('已发出的通知书请求失联，重开及连接就绪后仍只允许核对原结果', async () => {
  let posts = 0;
  globalThis.fetch = async () => {posts += 1; throw new TypeError('network interrupted');};
  confirmButton(render({mode: 'browser', connected: true})).props.onClick();
  await settle();
  assert.equal(posts, 1);
  assert.equal(actionsOf(render({mode: 'browser'})).action.pending, true);
  cells.list = [];
  const reopened = render({mode: 'browser', connected: true});
  assert.equal(actionsOf(reopened).action.pending, true);
  assert.equal(kickButton(reopened, '确认抓取'), undefined);
  await settle();
  assert.equal(posts, 1);
});

test('月份不合法时不发请求（原来的正则回归守卫）', async () => {
  const calls = recorder();
  cells.month = '2026-11-05';
  const tree = render({ mode: 'http' });
  assert.equal(confirmButton(tree).props.disabled, true);
  await submit(tree);
  assert.equal(calls.length, 0, '不是 YYYY-MM 的月份必须当场停，不能发出去猜');
});

function conflictRecorder({ repeat = false, topLevel = false } = {}) {
  const calls = [];
  globalThis.fetch = async (path, init) => {
    calls.push({path, body: JSON.parse(init.body)});
    if (path === '/api/m02/session/kick-cancel') return response({ok: true});
    if (calls.length === 1 || repeat) {
      const message = '该 i8 账号已有在线会话。请确认是否让现有会话下线并继续本次操作。';
      const token = {kick_token: 'one-time-confirmation'};
      return {ok: false, status: 409, json: async () => ({
        code: 'i8_online_conflict', message, ...(topLevel ? token : {detail: token}),
      })};
    }
    return response({year_month: calls.at(-1).body.year_month, fetched: 3, upserted: 3, ignored: []});
  };
  return calls;
}

const settle = () => new Promise(resolve => setImmediate(resolve));
const actionsOf = tree => walk(tree, node => node.type === I8FetchActions)[0].props;
const kickButton = (tree, label = '让现有会话下线并继续') =>
  walk(I8FetchActions(actionsOf(tree)), node => node.props?.children === label)[0];

test('在线冲突暂停，确认仅重发原请求一次并显示回执', async () => {
  const calls = conflictRecorder();
  confirmButton(render()).props.onClick();
  await settle();
  const prompting = render();
  assert.equal(actionsOf(prompting).action.pending, false);
  assert.equal(sessionStorage.getItem('i8-fetch-pending:notices:tester001'), null);
  assert.match(actionsOf(prompting).action.kickMessage, /在线会话/);
  assert.equal(calls.length, 1);
  const confirm = kickButton(prompting);
  confirm.props.onClick();
  confirm.props.onClick();
  await settle();
  const completed = render();
  assert.equal(calls.length, 2);
  assert.deepEqual(calls[1], {path: calls[0].path, body: {...calls[0].body, kick_token: 'one-time-confirmation'}});
  assert.equal(actionsOf(completed).action.sent, true);
  assert.ok(walk(completed, node => node.props?.data?.summary?.written === 3).length);
  assert.equal(actionsOf(completed).action.kickMessage, '');
});

test('已确认请求再次冲突时显示错误，原确认不能重复提交', async () => {
  const calls = conflictRecorder({repeat: true, topLevel: true});
  confirmButton(render()).props.onClick();
  await settle();
  kickButton(render()).props.onClick();
  await settle();
  const {action} = actionsOf(render());
  assert.equal(action.kickMessage, '');
  assert.equal(action.pending, false);
  assert.match(action.error, /在线会话/);
  assert.equal(calls.filter(call => call.path === '/api/m03/notices/fetch').length, 2);
  assert.equal(calls.at(-1).path, '/api/m02/session/kick-cancel');
});

for (const invalidation of ['cancel', 'month', 'mode', 'close']) {
  test(`待确认的顶号会随 ${invalidation} 失效`, async () => {
    const calls = conflictRecorder();
    confirmButton(render()).props.onClick();
    await settle();
    const prompting = render();
    const staleConfirm = kickButton(prompting);
    if (invalidation === 'cancel') kickButton(prompting, '取消').props.onClick();
    if (invalidation === 'month') {
      const [picker] = walk(prompting, node => node.props?.label === '抓取月份');
      cells.month = '2026-10';
      picker.props.onChange(cells.month);
    }
    if (invalidation === 'mode') render({mode: 'browser', connected: true});
    if (invalidation === 'close') prompting.props.requestClose();
    assert.equal(actionsOf(render()).action.kickMessage, '');
    staleConfirm.props.onClick();
    await settle();
    assert.equal(calls.length, 2);
    assert.deepEqual(calls[1], {path: '/api/m02/session/kick-cancel', body: {kick_token: 'one-time-confirmation'}});
  });
}


test('cancelled fetch confirmation cannot submit while revocation is pending or after it fails', async () => {
  const calls = [];
  const revocation = Promise.withResolvers();
  globalThis.fetch = async (path, init) => {
    calls.push([path, JSON.parse(init.body)]);
    if (calls.length === 1) return {ok: false, status: 409, json: async () => ({
      code: 'i8_online_conflict', message: '已有在线会话', detail: {kick_token: 'fixture'},
    })};
    return revocation.promise;
  };
  confirmButton(render()).props.onClick();
  await settle();
  const prompting = render();
  const staleConfirm = kickButton(prompting);
  kickButton(prompting, '取消').props.onClick();
  assert.equal(kickButton(render()), undefined);
  staleConfirm.props.onClick();
  revocation.reject(new TypeError('network failure'));
  await settle();
  staleConfirm.props.onClick();
  const [status] = walk(render(), node => node.type === I8FetchStatus);
  assert.ok(walk(I8FetchStatus(status.props), node => node.props?.role === 'status'
    && /令牌撤回未确认/.test(node.props.children)).length);
  assert.equal(confirmButton(render()).props.disabled, false);
  assert.deepEqual(calls.map(([path]) => path), ['/api/m03/notices/fetch', '/api/m02/session/kick-cancel']);
});

test('shared confirmation clears its token before a rejected revocation completes', async () => {
  const revoked = Promise.withResolvers();
  globalThis.fetch = () => revoked.promise;
  cells.month = null;
  const renderKick = () => { cells.index = 0; return useI8KickConfirmation('scope'); };
  const first = renderKick();
  first.offer(new ApiError('已有在线会话', 409, 'i8_online_conflict', {kick_token: 'fixture'}),
    () => assert.fail('cancelled confirmation submitted'));
  const prompting = renderKick();
  const cancellation = prompting.cancel();
  assert.equal(renderKick().message, '');
  prompting.confirm();
  revoked.resolve({ok: false, status: 503, json: async () => ({message: 'unavailable'})});
  await cancellation;
  assert.match(renderKick().revocationNotice, /令牌撤回未确认/);
});

test('a late kick offer is revoked after scope change or dismissal', async () => {
  const calls = recorder();
  cells.month = null;
  function renderKick(scope) {
    cells.index = 0;
    return useI8KickConfirmation(scope);
  }
  const failure = token => new ApiError('已有在线会话', 409, 'i8_online_conflict', {kick_token: token});
  const forbidden = () => assert.fail('cancelled confirmation submitted');
  const old = renderKick('first');
  old.offer(failure('first-token'), forbidden);
  const changed = renderKick('second');
  old.offer(failure('late-token'), forbidden);
  changed.offer(failure('second-token'), forbidden);
  changed.dismiss();
  changed.confirm();
  await settle();
  assert.deepEqual(calls.map(call => call.body.kick_token), ['first-token', 'late-token', 'second-token']);
  assert.ok(calls.every(call => call.path === '/api/m02/session/kick-cancel'));
});

const fetchSurfaces = [
  ['monthly report', I8ReportFetch, {source: 'settlement', month: '2026-10', paused: false, pending: false, onPending() {}},
    '/api/m07/fetch', reportResponse, p => p.data?.summary?.total === 4 && p.data?.summary?.kept_manual === 3],
  ['contract tools', ContractFetch, {blocked: false}, '/api/m11/fetch',
    {ok: true, receipt: {id: 13, matched: 2, started_at: '2026-11-20', status: 'success',
      unsettled: [{contract_no: 'CT-3', project_name: '项目甲', kind: 'needs_keyword'}]}},
    p => p.data?.id === 13 && p.pending?.[0]?.contract === 'CT-3'],
];
for (const [name, component, props, path, result, hasReceipt] of fetchSurfaces) {
  function surface(close = () => {}) {
    cells.index = 0;
    cells.month = null;
    return component({...props, me, close, refresh: async () => {}});
  }

  test(name + ' keeps the received result from a confirmed kick retry', async () => {
    const calls = [];
    globalThis.fetch = async (url, init) => {
      calls.push([url, JSON.parse(init.body)]);
      return calls.length === 1
        ? {ok: false, status: 409, json: async () => ({code: 'i8_online_conflict', message: '已有在线会话', detail: {kick_token: 'fixture'}})}
        : response(result);
    };
    actionsOf(surface()).onRun();
    await settle();
    kickButton(surface()).props.onClick();
    await settle();
    assert.deepEqual(calls.map(([url]) => url), [path, path]);
    assert.deepEqual(calls[1][1], {...calls[0][1], kick_token: 'fixture'});
    assert.ok(walk(surface(), node => node.props && hasReceipt(node.props)).length);
  });

  test(name + ' closes synchronously before a ready event can submit', async () => {
    const calls = recorder();
    const ready = Promise.withResolvers();
    let signal;
    globalThis.__relaySession = {...globalThis.__relaySession, mode: 'browser', waitForBrowser(value) {
      signal = value;
      return ready.promise;
    }};
    const close = () => assert.equal(signal.aborted, true);
    actionsOf(surface(close)).onRun();
    assert.equal(actionsOf(surface(close)).action.waiting, true);
    const modal = walk(surface(close), node => typeof node.props?.requestClose === 'function')[0];
    modal.props.requestClose();
    ready.resolve(true);
    await settle();
    assert.deepEqual(calls, []);
  });
}

for (const [name, component, props, field, next] of [
  ['notice', NoticeFetch, {blocked: false}, '抓取月份', '2026-10'],
  ['report', I8ReportFetch, fetchSurfaces[0][2], '收发结存抓取月份', '2026-09'],
  ['contract', ContractFetch, {blocked: false}, '合同抓取范围', 'all'],
]) {
  for (const exit of ['modal', 'heading']) {
    test(name + ' cancels the browser wait before the ' + exit + ' close prompts to discard', async () => {
      const calls = recorder();
      const ready = Promise.withResolvers();
      let signal;
      globalThis.__relaySession = {...globalThis.__relaySession, mode: 'browser', waitForBrowser(value) {
        signal = value;
        return ready.promise;
      }};
      function surface() {
        cells.index = 0;
        if (component !== NoticeFetch) cells.month = null;
        return component({...props, me, close: () => assert.fail('dirty dialog closed immediately'), refresh: async () => {}});
      }
      const [input] = walk(surface(), node => (node.props?.label || node.props?.['aria-label']) === field);
      if (component === NoticeFetch) cells.month = next;
      input.props.onChange(next);
      actionsOf(surface()).onRun();
      const waiting = surface();
      assert.equal(actionsOf(waiting).action.waiting, true);
      const [modal] = walk(waiting, node => typeof node.props?.requestClose === 'function');
      const [contents] = walk(waiting, node => node.props?.closing);
      const requestClose = exit === 'modal' ? modal.props.requestClose : contents.props.closing.requestClose;
      requestClose();
      assert.equal(signal.aborted, true);
      assert.equal(walk(surface(), node => node.props?.closing)[0].props.closing.confirming, true);
      ready.resolve(true);
      await settle();
      assert.deepEqual(calls, []);
    });
  }
}

test('mechanical wait keeps writes unlocked and can be closed before readiness', async t => {
  t.mock.method(globalThis, 'fetch', async () => { assert.fail('a closed dialog submitted'); });
  Object.defineProperty(globalThis, 'document', {configurable: true, value: {documentElement: {}}});
  Object.defineProperty(globalThis, 'getComputedStyle', {configurable: true, value: () => ({getPropertyValue: () => '1'})});
  t.after(() => {delete globalThis.document; delete globalThis.getComputedStyle;});
  const ready = Promise.withResolvers();
  let signal, locks = 0;
  globalThis.__relaySession = {...globalThis.__relaySession, mode: 'browser', waitForBrowser(value) {
    signal = value;
    return ready.promise;
  }};
  function surface() {
    cells.index = 0;
    cells.month = null;
    return MechanicalWork({
      me, data: {discoveries: [], warehouses: [], history_bases: []}, warehouses: [],
      label: String, writable: true, busy: false, paused: false,
      operate: async issue => {locks += 1; await issue();}, refresh: async () => true, added() {},
    });
  }
  const start = walk(surface(), node => node.props?.children === '抓取i8')[0];
  assert.equal(start.props.disabled, false);
  start.props.onClick();
  const modal = walk(surface(), node => node.type === 'mechanical-dialog')[0];
  assert.equal(modal.props.busy, false);
  const contents = modal.props.children(modal.props.close);
  assert.ok(walk(contents, node => node.props?.children === '取消等待').length);
  assert.equal(locks, 0);
  modal.props.close();
  assert.ok(signal.aborted);
  ready.resolve(true);
  await settle();
  assert.equal(locks, 0);
});
