import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import test from 'node:test';
import { setTimeout as delay } from 'node:timers/promises';

// Exercise the page and dialog with fake HTTP responses and grid rendering.
const hooks = { cells: [], index: 0, effects: [], session: null };
globalThis.__noticePrintHooks = hooks;
const data = source => ({ url: 'data:text/javascript,' + encodeURIComponent(source), shortCircuit: true });
const placeholder = 'export default props => ({type: "button", props});';
const pageComponents = {
  './workspace-motion': ['DialogPresence'], './notice-fetch': ['NoticeFetch'],
  './notice-paste': ['NoticePaste'], './notice-auto-link': ['AutoLinkDialog'],
  './notice-maintenance': ['DraftField', 'manualDraft', 'NoticeDeleteDialog', 'NoticeDraftDisabled'],
  './notice-contract': ['ContractDialog'], './notice-payment': ['NoticePayment', 'PayAmountCell', 'paymentValue', 'amount'],
  './ownership': ['OwnershipDialog', 'OwnershipPending', 'refreshNoticeOwnershipPending'],
  './ledger-controls': ['ProjectPicker'], './enum-tag': ['EnumTag'],
  './notice-flows': ['NoticeFlows'], './notice-todos': ['resetNoticeTodos'],
};
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === 'react/jsx-runtime') return data(
      'export const Fragment = "fragment"; export const jsx = (type, props) => ({type, props}); export const jsxs = jsx;',
    );
    if (specifier === 'react') return data(
      'const h = globalThis.__noticePrintHooks;' +
      'const cell = () => h.cells[h.index++] ??= {};' +
      'export function useState(value) {const s = cell(); if (!("value" in s)) s.value = typeof value === "function" ? value() : value; return [s.value, next => s.value = typeof next === "function" ? next(s.value) : next];}' +
      'export function useRef(current) {const s = cell(); return s.ref ??= {current};}' +
      'export function useEffect(fn, deps) {const s = cell(); if (s.deps && deps.every((v, i) => Object.is(v, s.deps[i]))) return; s.deps = deps; h.effects.push(() => {s.cleanup?.(); s.cleanup = fn();});}' +
      'export function useMemo(fn, deps) {const s = cell(); if (!s.deps || !deps.every((v, i) => Object.is(v, s.deps[i]))) {s.deps = deps; s.value = fn();} return s.value;}' +
      'export const createContext = () => ({Provider: "provider"}); export const useContext = () => null;' +
      'export const useLayoutEffect = useEffect;',
    );
    if (specifier === './i8-session') return data(
      'export const useI8Session = () => globalThis.__noticePrintHooks.session;' +
      'export const I8ConnectionWaitStatus = () => null;' +
      'export const useI8ActionWait = () => ({waiting: false, cancelWaiting() {}, runWhenReady: issue => issue(globalThis.__noticePrintHooks.session)});',
    );
    if (specifier === './business-modal') return data('export const BusinessModal = props => props.children;');
    if (specifier === './business-grid') return data('export const ReadGrid = "grid";');
    if (specifier === './bounded-grid') return data('export const BoundedGrid = "grid";');
    if (specifier === './grid') return data('export const numberColumnWidth = () => ({}); export const fullTextWidth = numberColumnWidth;' +
      'export const cacheFontMeasurement = fn => fn; export const cachedNumberColumnWidths = () => () => ({minWidth: 40});' +
      'export const contentWidth = numberColumnWidth, fixedWidth = numberColumnWidth, textWidth = numberColumnWidth, gridTheme = {};');
    if (specifier === './dialog-close') return data('export const DialogContents = props => props.children; export const useDialogClose = ({close}) => ({requestClose: close});');
    if (specifier === 'react-router') return data('export const Link = "link"; export const useSearchParams = () => [new URLSearchParams()];');
    if (specifier === 'antd/es/app') return data('export default {useApp: () => ({message: {info() {}, error() {}, success() {}}})};');
    if (specifier.startsWith('antd/es/')) return data(placeholder);
    if (specifier === '@tanstack/react-query') return data('export const useQueryClient = () => ({});');
    if (specifier === './history') return data('export const useHistoryGuard = () => {}; export const readHistory = () => {};');
    if (specifier === './use-amount-comparator') return data('export const useAmountComparator = () => undefined;');
    if (specifier === './grid-search') return data('export const useGridSearch = () => ({applied: "", pending: false, reset() {}}); export const searchWithinRows = rows => () => rows;');
    if (specifier === './grid-text') return data('export const completeColumnWidth = () => 40; export const EllipsisText = "ellipsis";');
    if (specifier === './notice-cell-save') return data('export const NoticeCells = {Provider: "provider"}, PublishedNotices = NoticeCells;' +
      'export const useNoticeCellSaves = () => ({drafts: {}}); export const PaidAmountCell = "paid", StatCell = "stat";');
    if (specifier === './read-region') return data('export const readPhase = () => "ready", FirstReadRegion = "read-region", ReadFailure = "error", ReadPlaceholder = "placeholder", ReadStatusLane = "lane";');
    if (specifier === './grid-presentation') return data('export const PreparedGrid = "prepared-grid", useGridPresentation = props => ({...props, state: "ready"});');
    if (specifier === './time-picker') return data('export const TimePicker = "TimePicker", timeMatches = () => true, timeRange = () => ({});');
    if (specifier in pageComponents) return data(pageComponents[specifier].map(name => name === 'NoticeDraftDisabled'
      ? `export const ${name} = {Provider: "provider"};` : `export const ${name} = "${name}";`).join(''));
    return nextResolve(specifier, context);
  },
});

const { NoticePrint, recoverNoticePrint } = await import('../../src/notice-print.tsx');
const { NoticesPage } = await import('../../src/notices.tsx');
const rows = [1, 2, 3].map(notice_id => ({notice_id, bill_no: 'PN-' + notice_id, amount_approved: '1.00'}));
const root = '/api/m03/print-batches';

function walk(value) {
  if (Array.isArray(value)) return value.flatMap(walk);
  return value?.props ? [value, ...walk(value.props.children), ...walk(value.props.footer)] : [];
}

function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  if (value?.props) return text(value.props.children) + text(value.props.footer);
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

function mountNotices(t, handle) {
  const pageCells = [];
  let dialogCells = [];
  const storage = new Map();
  const browser = new EventTarget();
  browser.sessionStorage = {setItem: (key, value) => storage.set(key, value), getItem: key => storage.get(key)};
  t.mock.method(globalThis, 'fetch', async (path, request) => {
    const result = path === root + '/active' ? null : await handle(path, request);
    return result instanceof Response ? result : Response.json(result);
  });
  globalThis.window = browser;
  globalThis.requestAnimationFrame = () => 0;
  hooks.session = {mode: 'browser', connected: true};
  function removeDialog() {
    dialogCells.forEach(cell => cell.cleanup?.());
    dialogCells = [];
  }
  t.after(() => {
    pageCells.forEach(cell => cell.cleanup?.());
    removeDialog();
    delete globalThis.window;
    delete globalThis.requestAnimationFrame;
  });

  const query = {isSuccess: true, data: rows.map(row => ({...row, ownership_id: null,
    pay_status: '未付清', amount_paid: '0.00', pay_amount: '1.00', stat_settle: '1.00', stat_paid: '0.00'}))};
  const projects = {isSuccess: true, data: []};
  const me = {account: 'notice-test-owner'};
  function render(cells, component) {
    hooks.cells = cells;
    hooks.index = 0;
    hooks.effects = [];
    const tree = component();
    for (const effect of hooks.effects) effect();
    return tree;
  }
  function page() {
    return render(pageCells, () => NoticesPage({me, active: true, blocked: false, query, projects}));
  }
  function dialog() {
    const props = walk(page()).find(node => node.type === NoticePrint)?.props;
    if (!props) { removeDialog(); return null; }
    return render(dialogCells, () => NoticePrint(props));
  }
  function grid() { return walk(page()).find(node => node.type === 'prepared-grid').props; }
  function checkbox(id) {
    const {presentation} = grid();
    const control = presentation.columns.find(column => column.colId === 'pick');
    return control.cellRenderer({node: {}, data: query.data.find(row => row.notice_id === id)}).props;
  }
  function click(label, surface = page) {
    const button = walk(surface()).find(node => node.props.onClick && text(node) === label);
    assert.ok(button, 'missing button: ' + label);
    assert.equal(Boolean(button.props.disabled), false, label);
    button.props.onClick();
    if (surface === dialog) dialog();
  }
  return {
    page, dialog, click, checkbox,
    check: (id, checked) => checkbox(id).onChange({target: {checked}}),
    count: () => text(walk(page()).find(node => node.props.className === 'notice-selection').props.children[0]),
    paste(ids) {
      click('粘贴单据号勾选');
      const paste = walk(page()).find(node => node.type === 'NoticePaste');
      assert.ok(paste, 'the paste dialog opens when requested');
      paste.props.apply(ids);
      paste.props.close();
    },
    visibleOrder() {
      const {grid: options, presentation} = grid();
      const nodes = presentation.rows.map(data => ({data}));
      options.postSortRows({nodes});
      return nodes.map(({data}) => data.notice_id);
    },
  };
}

test('Excel export downloads directly and keeps a failure at the toolbar', async t => {
  const replies = [Response.json({ ok: false, message: '合成导出错误' }, {status: 503}),
    { ok: true, rows: 3, filename: 'notices.xlsx', content_b64: 'c2FtcGxl' }];
  const downloads = [];
  globalThis.document = {createElement: () => ({click() { downloads.push(this.download); }})};
  t.after(() => { delete globalThis.document; });
  const ui = mountNotices(t, (path, request) => {
    assert.equal(path, '/api/m03/notices/export');
    assert.deepEqual(JSON.parse(request.body), {ids: [1, 2, 3]});
    return replies.shift();
  });
  ui.click('导出 Excel');
  assert.equal(walk(ui.page()).find(node => text(node) === '导出 Excel' && node.props.onClick).props.loading, true);
  await until(() => text(ui.page()).includes('Excel 导出失败。合成导出错误'));
  assert.equal(walk(ui.page()).filter(node => node.props.titleId === 'notice-export-title').length, 0);
  ui.click('导出 Excel');
  await until(() => downloads.length === 1);
  assert.deepEqual(downloads, ['notices.xlsx']);
  assert.doesNotMatch(text(ui.page()), /合成导出错误/);
});

for (const closeDuringDispatch of [false, true]) {
  test('accepted single print clears the original checkbox and paste priority' + (closeDuringDispatch ? ' after closing' : ''), async t => {
    const terminal = Promise.withResolvers();
    const ready = view('single', 'print', {total: 1, status: 'ready', stage: 'preparing', items: [item(2)]});
    const running = {...ready, status: 'running', stage: 'dispatching'};
    const complete = {...running, status: 'complete', dispatched_count: 1,
      items: [item(2, {delivery_status: 'accepted', channel: 'ipp', job_id: 123})]};
    let reads = 0;
    const page = mountNotices(t, async (path, request) => {
      if (path === root + '/prepare') {
        assert.deepEqual(JSON.parse(request.body).ids, [2]);
        return ready;
      }
      if (path === root + '/single/dispatch') return running;
      if (path === root + '/single') {
        const firstRead = ++reads === 1;
        const receipt = await terminal.promise;
        return firstRead && !closeDuringDispatch ? {...receipt, status: 'running'} : receipt;
      }
      assert.fail(path);
    });
    page.paste([2]);
    assert.deepEqual(page.visibleOrder(), [2, 1, 3]);
    page.click('批量打印');
    page.click('确认本批', page.dialog);
    await until(() => text(page.dialog()).includes('投递打印机'));
    assert.equal(page.count(), '已勾选 1 行');
    if (closeDuringDispatch) {
      page.click('关闭', page.dialog);
      assert.equal(page.dialog(), null);
      page.check(1, true);
    }
    terminal.resolve(complete);
    await until(() => !page.checkbox(2).checked);
    assert.equal(page.count(), closeDuringDispatch ? '已勾选 1 行' : '已勾选 0 行');
    assert.deepEqual(page.visibleOrder(), [1, 2, 3]);
    if (!closeDuringDispatch) page.click('关闭', page.dialog);
    page.check(2, true);
    page.click('查看打印批次');
    await until(() => text(page.dialog()).includes('PN-2：打印机已接收'));
    assert.equal(page.checkbox(2).checked, true);
    assert.equal(page.checkbox(1).checked, closeDuringDispatch);
  });
}

for (const [status, label] of [['failed', '明确失败'], ['unknown', '结果待核实'], ['accepted', '打印机已接收']]) {
  test('single print preserves ' + (status === 'accepted' ? 'a fresh recheck' : 'selection after ' + status), async t => {
    const ready = view('single', 'print', {total: 1, status: 'ready', stage: 'preparing', items: [item(2)]});
    const running = {...ready, status: 'running', stage: 'dispatching'};
    const page = mountNotices(t, path => {
      if (path === root + '/prepare') return ready;
      if (path === root + '/single/dispatch') return running;
      if (path === root + '/single') return {...running, status: 'complete',
        items: [item(2, {delivery_status: status})]};
      assert.fail(path);
    });
    page.paste([2]);
    page.click('批量打印');
    page.click('确认本批', page.dialog);
    await until(() => text(page.dialog()).includes('投递打印机'));
    if (status === 'accepted') {
      page.click('关闭', page.dialog);
      page.check(2, false);
      page.check(2, true);
      page.click('查看打印批次');
    }
    await until(() => text(page.dialog()).includes('PN-2：' + label));
    assert.equal(page.count(), '已勾选 1 行');
    assert.equal(page.checkbox(2).checked, true);
    assert.deepEqual(page.visibleOrder(), [2, 1, 3]);
  });
}

test('recovering the original single batch clears its checkbox after acceptance is confirmed', async t => {
  const ready = view('single', 'print', {total: 1, status: 'ready', stage: 'preparing', items: [item(2)]});
  const page = mountNotices(t, path => {
    if (path === root + '/prepare') return ready;
    if (path === root + '/single/dispatch') return Response.json({message: '暂时无法读取投递状态'}, {status: 503});
    if (path === root + '/single') return {...ready, stage: 'done', status: 'complete',
      dispatched_count: 1, items: [item(2, {delivery_status: 'accepted'})]};
    assert.fail(path);
  });
  page.paste([2]);
  page.click('批量打印');
  page.click('确认本批', page.dialog);
  await until(() => text(page.dialog()).includes('暂时无法读取投递状态'));
  assert.equal(page.checkbox(2).checked, true);
  page.click('关闭', page.dialog);
  page.click('查看打印批次');
  await until(() => text(page.dialog()).includes('PN-2：打印机已接收'));
  assert.equal(page.checkbox(2).checked, false);
  assert.deepEqual(page.visibleOrder(), [1, 2, 3]);
});

test('a multi-notice print narrowed to one preserves both original checkboxes', async t => {
  const failed = view('original', 'print', {total: 2, status: 'failed', stage: 'preparing',
    failed_notice_id: 1, items: [item(1, {status: 'failed'}), item(2, {status: 'skipped'})]});
  const ready = view('remaining', 'print', {total: 1, status: 'ready', stage: 'preparing', items: [item(2)]});
  const page = mountNotices(t, (path, request) => {
    if (path === root + '/prepare') return JSON.parse(request.body).ids.length === 2 ? failed : ready;
    if (path === root + '/remaining/dispatch') return {...ready, stage: 'dispatching', status: 'complete',
      dispatched_count: 1, items: [item(2, {delivery_status: 'accepted'})]};
    assert.fail(path);
  });
  page.paste([2, 1]);
  page.click('批量打印');
  page.click('确认本批', page.dialog);
  await until(() => text(page.dialog()).includes('已投递 0 张'));
  page.click('移出异常单并重新确认剩余批次', page.dialog);
  page.click('确认本批', page.dialog);
  await until(() => text(page.dialog()).includes('PN-2：打印机已接收'));
  assert.equal(page.count(), '已勾选 2 行');
  assert.equal(page.checkbox(2).checked, true);
  assert.deepEqual(page.visibleOrder(), [2, 1, 3]);
});

test('canceling before confirmation and exporting a single PDF both preserve selection', async t => {
  const page = mountNotices(t, path => {
    if (path === root + '/prepare') return view('pdf', 'pdf', {total: 1, status: 'complete', stage: 'preparing',
      result: {total: 1, success: 1, failed: 0, items: [{notice_id: 2, bill_no: 'PN-2',
        ok: true, unverified: false, reason: '', download_url: '/api/m03/pdf/token'}]}});
    if (path === '/api/m03/pdf/token') return new Response('pdf', {headers: {
      'Content-Type': 'application/pdf', 'X-Export-Filename': 'PN-2.pdf',
    }});
    assert.fail(path);
  });
  page.paste([2]);
  page.click('批量打印');
  page.click('关闭', page.dialog);
  assert.equal(page.count(), '已勾选 1 行');
  page.click('导出 PDF');
  page.click('确认本批', page.dialog);
  await until(() => text(page.dialog()).includes('在新窗口预览 PDF'));
  assert.equal(page.count(), '已勾选 1 行');
  assert.deepEqual(page.visibleOrder(), [2, 1, 3]);
});

test('print cancellation reports failed revocation and blocks the stale confirm handler', async t => {
  const revocation = Promise.withResolvers();
  const dialog = mount(t, 'print', ({path}) => path === root + '/prepare' ? Response.json({
    code: 'i8_online_conflict', message: '已有在线会话', detail: {kick_token: 'print-cancel'},
  }, {status: 409}) : revocation.promise, {mode: 'http', connected: false});
  dialog.click('确认本批');
  await until(() => text(dialog.render()).includes('已有在线会话'));
  const confirm = walk(dialog.render()).find(node => text(node.props.children) === '让现有会话下线并继续');
  dialog.click('取消下线确认');
  confirm.props.onClick();
  assert.doesNotMatch(text(dialog.render()), /让现有会话下线并继续/);
  revocation.resolve(Response.json({message: 'unavailable'}, {status: 503}));
  await until(() => walk(dialog.render()).some(node => node.props.role === 'status' && /令牌撤回未确认/.test(text(node))));
  assert.deepEqual(dialog.calls.map(call => call.path), [root + '/prepare', '/api/m02/session/kick-cancel']);
});

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
  await until(() => text(dialog.render()).includes('准备 PDF 1/3，当前单据 PN-2'));
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
  const buttons = walk(dialog.render()).filter(node => node.props.onClick);
  assert.equal(buttons.find(node => text(node) === '导出本批 PDF').props.type, 'default');
  assert.deepEqual(buttons.filter(node => node.props.type === 'primary').map(text), ['下载 prepared.pdf']);
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
  assert.match(text(dialog.render()), /投递打印机 1\/3，当前单据 PN-2/);
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
  assert.match(displayed, /PN-1：打印机已接收，通道 IPP，作业号 123/);
  assert.match(displayed, /PN-2：明确失败.*第一通道拒绝.*第二通道拒绝/);
  assert.match(displayed, /PN-3：结果待核实.*勿盲目重打/);
  assert.equal(dialog.calls.filter(call => call.method === 'POST').length, 0);

  const recent = await recoverNoticePrint(dialog.owner);
  assert.equal(recent.status, 'complete');
  dialog.remount(recent);
  assert.match(text(dialog.render()), /PN-3：结果待核实/);
});


test('print preparation binds the owner and kick retry preserves the entire request', async t => {
  const conflict = {code: 'i8_online_conflict', message: '已有在线会话', detail: {kick_token: 'print-token'}};
  let attempts = 0;
  const dialog = mount(t, 'pdf', ({path}) => {
    assert.equal(path, root + '/prepare');
    return ++attempts === 1 ? Response.json(conflict, {status: 409}) : view('new', 'pdf', {status: 'complete'});
  }, {mode: 'http', connected: false});
  dialog.click('确认本批');
  await until(() => text(dialog.render()).includes(conflict.message));
  dialog.click('让现有会话下线并继续');
  await until(() => dialog.calls.length === 2);
  assert.deepEqual(dialog.calls[0].payload, {ids: [1, 2, 3], mode: 'pdf', expected_account: dialog.owner, session_mode: 'http'});
  assert.deepEqual(dialog.calls[1].payload, {...dialog.calls[0].payload, kick_token: 'print-token'});
});

for (const label of ['取消下线确认', '关闭']) {
  test('print revokes a pending kick when clicking ' + label, async t => {
    const dialog = mount(t, 'pdf', ({path}) => path === root + '/prepare' ? Response.json({
      code: 'i8_online_conflict', message: '已有在线会话', detail: {kick_token: 'print-cancel'},
    }, {status: 409}) : {ok: true}, {mode: 'http', connected: false});
    dialog.click('确认本批');
    await until(() => text(dialog.render()).includes('已有在线会话'));
    dialog.click(label);
    assert.deepEqual(dialog.calls.at(-1), {
      path: '/api/m02/session/kick-cancel', method: 'POST', payload: {kick_token: 'print-cancel'},
    });
    assert.equal(text(dialog.render()).includes('让现有会话下线并继续'), false);
  });
}

test('recovered ready batch renders only its original bill numbers before allowing dispatch', async t => {
  const ready = view('saved', 'print', {status: 'ready', stage: 'preparing', total: 2, prepared_count: 2,
    items: [item(8), item(5)]});
  const dialog = mount(t, 'print', ({path}) => {
    assert.equal(path, root + '/saved/dispatch');
    return {...ready, status: 'complete', stage: 'done'};
  });
  dialog.remount(ready);
  const grid = walk(dialog.render()).find(node => node.type === 'grid');
  assert.deepEqual(grid.props.rows, [{notice_id: 8, bill_no: 'PN-8'}, {notice_id: 5, bill_no: 'PN-5'}]);
  assert.equal(dialog.calls.length, 0);
  dialog.click('投递原批');
  await until(() => dialog.calls.length === 1);
  assert.equal(dialog.calls[0].method, 'POST');
});

for (const removeFailed of [false, true]) {
  test('recovered failed preparation needs confirmation for ' + (removeFailed ? 'remaining scope' : 'original scope'), async t => {
    const failed = view('saved', 'print', {status: 'failed', stage: 'preparing', failed_notice_id: 2,
      items: [item(8), item(2, {status: 'failed'}), item(5, {status: 'skipped'})]});
    const dialog = mount(t, 'print', ({path}) => {
      assert.equal(path, root + '/prepare');
      return view('new', 'print', {status: 'failed', stage: 'preparing'});
    });
    dialog.remount(failed);
    if (removeFailed) dialog.click('移出异常单并重新确认剩余批次');
    assert.equal(dialog.calls.length, 0);
    dialog.click(removeFailed ? '确认本批' : '重试全批');
    await until(() => dialog.calls.length === 1);
    assert.deepEqual(dialog.calls[0].payload.ids, removeFailed ? [8, 5] : [8, 2, 5]);
  });
}

test('missing remembered batch never falls back to another active batch', async t => {
  globalThis.window = {sessionStorage: {getItem: () => 'missing'}};
  t.after(() => { delete globalThis.window; });
  const dialog = mount(t, 'print', ({path}) => {
    assert.equal(path, root + '/missing');
    return Response.json({detail: 'not found'}, {status: 404});
  });
  assert.equal(await recoverNoticePrint(dialog.owner), null);
  assert.deepEqual(dialog.calls.map(call => call.path), [root + '/missing']);
});


test('a recovered in-progress batch updates numeric placeholders to bill numbers before dispatch', async t => {
  const preparing = view('saved', 'print', {stage: 'connecting', total: 2,
    items: [item(8, {bill_no: '8'}), item(5, {bill_no: '5'})]});
  const ready = {...preparing, stage: 'preparing', status: 'ready', prepared_count: 2, items: [item(8), item(5)]};
  const dialog = mount(t, 'print', ({path, method}) => {
    assert.equal(path, root + '/saved');
    assert.equal(method, 'GET');
    return ready;
  });
  dialog.remount(preparing);
  assert.equal(text(dialog.render()).includes('投递原批'), false);
  await until(() => text(dialog.render()).includes('投递原批'));
  const grid = walk(dialog.render()).find(node => node.type === 'grid');
  assert.deepEqual(grid.props.rows.map(row => row.bill_no), ['PN-8', 'PN-5']);
  assert.equal(dialog.calls.length, 1);
});
