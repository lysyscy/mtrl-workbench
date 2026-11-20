import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import test from 'node:test';
import { setTimeout as delay } from 'node:timers/promises';

// Exercise the actual dialog, API serializer and request helpers without mounting a grid.
const hooks = { cells: [], index: 0, effects: [], session: null };
globalThis.__noticePrintHooks = hooks;
const data = source => ({ url: 'data:text/javascript,' + encodeURIComponent(source), shortCircuit: true });
const placeholder = 'export default props => ({type: "button", props});';
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === 'react/jsx-runtime') return data(
      'export const Fragment = "fragment"; export const jsx = (type, props) => ({type, props}); export const jsxs = jsx;',
    );
    if (specifier === 'react') return data(
      'const h = globalThis.__noticePrintHooks;' +
      'const cell = () => h.cells[h.index++] ??= {};' +
      'export function useState(value) {const s = cell(); if (!("value" in s)) s.value = typeof value === "function" ? value() : value; return [s.value, next => s.value = next];}' +
      'export function useRef(current) {const s = cell(); return s.ref ??= {current};}' +
      'export function useEffect(fn, deps) {const s = cell(); if (s.deps && deps.every((v, i) => Object.is(v, s.deps[i]))) return; s.deps = deps; h.effects.push(() => {s.cleanup?.(); s.cleanup = fn();});}',
    );
    if (specifier === './i8-session') return data(
      'export const useI8Session = () => globalThis.__noticePrintHooks.session;' +
      'export const I8ConnectionWaitStatus = () => null;' +
      'export const useI8ActionWait = () => ({waiting: false, cancelWaiting() {}, runWhenReady: issue => issue(globalThis.__noticePrintHooks.session)});',
    );
    if (specifier === './business-modal') return data('export const BusinessModal = props => props.children;');
    if (specifier === './business-grid') return data('export const ReadGrid = "grid";');
    if (specifier === './grid') return data('export const numberColumnWidth = () => ({}); export const fullTextWidth = numberColumnWidth;');
    if (specifier === './dialog-close') return data('export const DialogContents = props => props.children; export const useDialogClose = ({close}) => ({requestClose: close});');
    if (specifier === 'react-router') return data('export const Link = "link";');
    if (specifier === 'antd/es/button') return data(placeholder);
    return nextResolve(specifier, context);
  },
});

const { NoticePrint, recoverNoticePrint } = await import('../../src/notice-print.tsx');
const rows = [1, 2, 3].map(notice_id => ({notice_id, bill_no: 'PN-' + notice_id, amount_approved: '1.00'}));
const root = '/api/m03/print-batches';

function walk(value) {
  if (Array.isArray(value)) return value.flatMap(walk);
  return value?.props ? [value, ...walk(value.props.children)] : [];
}

function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  if (value?.props) return text(value.props.children);
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

function item(notice_id, overrides = {}) {
  return {notice_id, bill_no: 'PN-' + notice_id, status: 'prepared', delivery_status: 'pending',
    channel: '', job_id: null, reason: '', attempts: [], ...overrides};
}

function view(batch_id, mode, overrides = {}) {
  return {
    batch_id, mode, stage: 'connecting', status: 'running', total: 3, prepared_count: 0,
    dispatch_processed_count: 0, dispatched_count: 0, current_bill_no: '', failed_bill_no: '',
    failed_notice_id: null, reason: '', session_stopped: false, kick_token: '', items: [],
    result: null, a4_blocked: null, ...overrides,
  };
}

function mount(t, mode, handler, session = {mode: 'browser', connected: true}) {
  hooks.cells = [];
  hooks.session = session;
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (path, request) => {
    const call = {path, method: request.method ?? 'GET', payload: request.body ? JSON.parse(request.body) : null};
    calls.push(call);
    const result = await handler(call);
    return result instanceof Response ? result : Response.json(result);
  });
  t.after(() => hooks.cells.forEach(cell => cell.cleanup?.()));
  let initialRows = rows, resumed;
  const owner = 'notice-test-owner';
  function render() {
    hooks.index = 0;
    hooks.effects = [];
    const tree = NoticePrint({rows: initialRows, mode, owner, resumed, blocked: false, close() {}});
    for (const effect of hooks.effects) effect();
    return tree;
  }
  function click(label) {
    const button = walk(render()).find(node => node.props.onClick && text(node) === label);
    assert.ok(button, 'missing button: ' + label);
    assert.equal(Boolean(button.props.disabled), false, label);
    button.props.onClick();
  }
  function remount(batch) {
    hooks.cells.forEach(cell => cell.cleanup?.());
    hooks.cells = [];
    resumed = batch;
    initialRows = [];
    render();
  }
  return {calls, render, click, owner, remount};
}

async function until(predicate) {
  for (let attempt = 0; attempt < 150; attempt += 1) {
    if (predicate()) return;
    await delay(15);
  }
  assert.fail('expected dialog state did not arrive');
}

test('preparation shows server counts and reconfirmation is required before sending a trimmed scope', async t => {
  let reads = 0, prepares = 0;
  const failed = view('first', 'print', {
    status: 'failed', stage: 'preparing', prepared_count: 1, failed_bill_no: 'PN-2',
    failed_notice_id: 2, reason: '签名取不到', items: [item(2, {status: 'failed'})],
  });
  const ready = view('next', 'print', {status: 'ready', stage: 'preparing', total: 2, prepared_count: 2});
  const dialog = mount(t, 'print', ({path}) => {
    if (path === root + '/prepare') return ++prepares === 1 ? view('first', 'print') : ready;
    if (path === root + '/first') return ++reads === 1
      ? view('first', 'print', {stage: 'preparing', prepared_count: 1, current_bill_no: 'PN-2'}) : failed;
    if (path === root + '/next/dispatch') return {...ready, status: 'running', stage: 'dispatching'};
    if (path === root + '/next') return {...ready, status: 'complete', stage: 'dispatching', dispatched_count: 2};
    assert.fail(path);
  });

  dialog.click('确认本批');
  await until(() => text(dialog.render()).includes('准备 PDF 1/3 · PN-2'));
  const progress = walk(dialog.render()).find(node => node.type === 'progress');
  assert.equal(progress.props.value, 1);
  assert.equal(progress.props.max, 3);
  await until(() => text(dialog.render()).includes('已投递 0 张'));
  assert.match(text(dialog.render()), /PN-2.*签名取不到/);
  assert.equal(dialog.calls.filter(call => call.path.endsWith('/dispatch')).length, 0);
  assert.deepEqual(dialog.calls[0].payload.ids, [1, 2, 3]);
  assert.equal(dialog.calls[0].payload.session_mode, 'browser');
  assert.ok(dialog.calls[0].payload.device_id);
  dialog.click('移出异常单并重新确认剩余批次');
  assert.match(text(dialog.render()), /本批 2 条/);
  assert.equal(prepares, 1);
  dialog.click('确认本批');
  await until(() => !walk(dialog.render()).find(node => node.props.onClick && text(node) === '关闭')?.props.disabled);
  assert.deepEqual(dialog.calls.filter(call => call.path.endsWith('/prepare')).map(call => call.payload.ids), [[1, 2, 3], [1, 3]]);
  assert.deepEqual(dialog.calls.filter(call => call.path.endsWith('/dispatch')).map(call => call.path), [root + '/next/dispatch']);
});

test('PDF download retries the same GET without preparing again or dispatching', async t => {
  let downloads = 0;
  const outcome = {notice_id: 1, bill_no: 'PN-1', ok: true, unverified: false, reason: '', download_url: '/api/m03/pdf/token'};
  const dialog = mount(t, 'pdf', ({path}) => {
    if (path === root + '/prepare') return view('pdf', 'pdf', {
      status: 'complete', stage: 'preparing', prepared_count: 1,
      result: {total: 1, success: 1, failed: 0, items: [outcome]},
    });
    if (path === outcome.download_url) return ++downloads === 1
      ? Response.json({message: '下载中断'}, {status: 503})
      : new Response('%PDF', {headers: {'Content-Type': 'application/pdf', 'X-Export-Filename': 'PN-1.pdf'}});
    assert.fail(path);
  });
  dialog.click('确认本批');
  await until(() => text(dialog.render()).includes('下载中断'));
  assert.match(text(dialog.render()), /PN-1：已生成/);
  dialog.click('重试下载');
  await until(() => text(dialog.render()).includes('下载 PN-1.pdf'));
  assert.deepEqual(dialog.calls.map(({method, path}) => [method, path]), [
    ['POST', root + '/prepare'], ['GET', outcome.download_url], ['GET', outcome.download_url],
  ]);
});

test('HTTP conflict confirmation reuses the frozen scope and sends its token once', async t => {
  const dialog = mount(t, 'print', ({payload}) => {
    if (!payload.kick_token) return Response.json({
      code: 'i8_online_conflict', message: '该 i8 账号已有在线会话', detail: {kick_token: 'one-time'},
    }, {status: 409});
    return view('confirmed', 'print', {status: 'failed', reason: '测试终止', session_stopped: true});
  }, {mode: 'http', connected: false});

  dialog.click('确认本批');
  await until(() => text(dialog.render()).includes('让现有会话下线并继续'));
  assert.equal(dialog.calls.length, 1);
  dialog.click('让现有会话下线并继续');
  await until(() => text(dialog.render()).includes('重试全批'));
  assert.equal(dialog.calls.length, 2);
  assert.equal(dialog.calls[0].payload.session_mode, 'http');
  assert.deepEqual(dialog.calls[1].payload, {...dialog.calls[0].payload, kick_token: 'one-time'});
});


test('A4 block exports prepared bytes and switches to IPP on the same batch', async t => {
  const path = root + '/blocked';
  const block = {code: 'a4_blocked', reason: '系统驱动无法指定 A4', can_switch_channel: true, export_action: path + '/export-pdf'};
  const ready = view('blocked', 'print', {status: 'ready', stage: 'preparing', prepared_count: 3});
  const running = {...ready, status: 'running', stage: 'dispatching', items: [item(1), item(2), item(3)]};
  const complete = {...running, status: 'complete', dispatch_processed_count: 3, dispatched_count: 3};
  const downloads = [];
  globalThis.document = {createElement: () => ({click() { downloads.push(this.download); }})};
  t.after(() => { delete globalThis.document; });
  const dialog = mount(t, 'print', ({path: url, payload}) => {
    if (url === root + '/prepare') return ready;
    if (url === path + '/dispatch') return payload ? running : {...ready, a4_blocked: block};
    if (url === path + '/export-pdf') return {download_url: '/api/m03/pdf/token'};
    if (url === '/api/m03/pdf/token') return new Response('%PDF', {
      headers: {'Content-Type': 'application/pdf', 'X-Export-Filename': 'prepared.pdf'},
    });
    if (url === path) return complete;
    assert.fail(url);
  });
  dialog.click('确认本批');
  await until(() => text(dialog.render()).includes('系统驱动无法指定 A4 已投递 0 张'));
  dialog.click('导出本批 PDF');
  await until(() => downloads.length > 0 && text(dialog.render()).includes('下载 prepared.pdf'));
  assert.deepEqual(downloads, ['prepared.pdf']);
  assert.deepEqual(dialog.calls.map(({method, path}) => [method, path]), [
    ['POST', root + '/prepare'], ['POST', path + '/dispatch'],
    ['POST', path + '/export-pdf'], ['GET', '/api/m03/pdf/token'],
  ]);
  const address = walk(dialog.render()).find(node => node.type === 'input');
  assert.ok(address);
  address.props.onChange({target: {value: 'ipp://a4-printer.example.test/ipp/print'}});
  dialog.click('切换支持 A4 的通道（IPP）');
  await until(() => text(dialog.render()).includes('打印机已接收 3 / 共 3 张'));
  assert.deepEqual(dialog.calls.filter(call => call.path.endsWith('/dispatch')).map(call => call.payload),
    [null, {mode: 'ipp', printer_uri: 'ipp://a4-printer.example.test/ipp/print'}]);
  assert.equal(dialog.calls.filter(call => call.path.endsWith('/prepare')).length, 1);
});

test('refresh finds the exact owner batch, resumes live progress and keeps the three receipt states', async t => {
  const batchPath = root + '/live';
  const setStorage = new Map();
  globalThis.window = {sessionStorage: {
    getItem: key => setStorage.get(key) ?? null,
    setItem: (key, value) => setStorage.set(key, value),
  }};
  t.after(() => { delete globalThis.window; });
  const accepted = item(1, {delivery_status: 'accepted', channel: 'ipp', job_id: 123});
  const failed = item(2, {delivery_status: 'failed', channel: 'ipp', attempts: [
    {channel: 'first-ipp', status: 'failed', job_id: null, reason: '第一通道拒绝'},
    {channel: 'ipp', status: 'failed', job_id: null, reason: '第二通道拒绝'},
  ]});
  const unknown = item(3, {delivery_status: 'unknown', channel: 'ipp'});
  const running = view('live', 'print', {stage: 'dispatching', prepared_count: 3, items: [accepted, item(2), item(3)],
    dispatch_processed_count: 1, dispatched_count: 1, current_bill_no: 'PN-2'});
  const complete = {...running, status: 'complete', dispatch_processed_count: 3, items: [accepted, failed, unknown]};
  let reads = 0;
  const dialog = mount(t, 'print', ({path, method}) => {
    assert.equal(method, 'GET');
    if (path === root + '/active') return running;
    if (path === batchPath) return ++reads === 1 ? running : complete;
    assert.fail(path);
  });

  const recovered = await recoverNoticePrint(dialog.owner);
  assert.equal(recovered.batch_id, 'live');
  dialog.remount(recovered);
  assert.match(text(dialog.render()), /投递打印机 1\/3 · PN-2/);
  assert.equal(walk(dialog.render()).find(node => node.type === 'progress').props.value, 1);
  assert.ok(text(dialog.render()).includes('待投递'));
  const exact = await recoverNoticePrint(dialog.owner);
  assert.equal(exact.batch_id, 'live');
  assert.equal(dialog.calls.at(-1).path, batchPath);
  const other = await recoverNoticePrint('other-user');
  assert.equal(other.batch_id, 'live');
  assert.equal(dialog.calls.at(-1).path, root + '/active', 'a different owner must not reuse the saved id');
  dialog.remount(exact);
  await until(() => text(dialog.render()).includes('结果待核实'));
  const displayed = text(dialog.render());
  assert.match(displayed, /PN-1：打印机已接收 · IPP · 作业号 123/);
  assert.match(displayed, /PN-2：明确失败.*第一通道拒绝.*第二通道拒绝/);
  assert.match(displayed, /PN-3：结果待核实.*勿盲目重打/);
  assert.equal(dialog.calls.filter(call => call.method === 'POST').length, 0);

  const recent = await recoverNoticePrint(dialog.owner);
  assert.equal(recent.status, 'complete');
  dialog.remount(recent);
  assert.match(text(dialog.render()), /PN-3：结果待核实/);
});
