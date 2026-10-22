import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { ApiError, readProjects, record, requestFile, requestJson } from './api';
import type { Identity } from './api';
import { amount, editable, loadLedger, payload, same, sum } from './ledger-api';
import type { Field, Ledger, LedgerRow, LedgerSide } from './ledger-api';

ModuleRegistry.registerModules([AllCommunityModule]);
const fields: Field[] = ['month', 'other_expense', 'payment', 'remark'];
const labels = { month: '月份', other_expense: '结算', payment: '付款', remark: '备注' };
const defaultColumn: ColDef<LedgerRow> = { sortable: false, resizable: false, suppressMovable: true, suppressKeyboardEvent: event => event.event.target instanceof HTMLInputElement };
const gridTheme = themeQuartz.withParams({ fontFamily: 'var(--fs)', fontSize: 'calc(14px * var(--fscale))',
  backgroundColor: 'var(--sf)', foregroundColor: 'var(--tx)', borderColor: 'var(--bd)',
  headerBackgroundColor: 'var(--sf2)', headerTextColor: 'var(--tx2)', accentColor: 'var(--pri)',
  oddRowBackgroundColor: 'var(--sf)', browserColorScheme: 'inherit', rowHoverColor: 'var(--sf2)',
  borderRadius: 0, wrapperBorderRadius: 0 });
interface Scope { key: string; owner: string; project: number; end: string }
interface Draft { text: string; base: string; version: number; queued: boolean; month: string }
interface Task extends Draft { field: Field }
interface Edit { scope: Scope; base: LedgerRow; drafts: Partial<Record<Field, Draft>>; own: Map<string, Partial<Record<Field, string>>>; queue: Task[]; saving: boolean; locked: boolean }
interface Actions {
  value(scope: Scope, row: LedgerRow, field: Field): string;
  draft(scope: Scope, row: LedgerRow, field: Field, text: string, base: string): void;
  commit(scope: Scope, row: LedgerRow, field: Field): void;
  remove(scope: Scope, row: LedgerRow): void;
  writable(): boolean;
  busy(): boolean;
}
interface GridContext { scope: Scope; actions: React.RefObject<Actions>; api: React.RefObject<GridApi<LedgerRow> | null> }

function Cell(props: ICellRendererParams<LedgerRow, string, GridContext>) {
  const { data: row, context } = props;
  const field = props.colDef?.field as Field;
  const [text, setText] = useState(() => row ? context.actions.current.value(context.scope, row, field) : '');
  const composing = useRef(false);
  const base = useRef(row?.[field] ?? '');
  useEffect(() => { if (row) setText(context.actions.current.value(context.scope, row, field)); }, [row, field, context]);
  if (!row) return null;
  if (!editable(row, field) || !context.actions.current.writable()) return <span>{field === 'month' ? row.month_label || row.month : field === 'remark' ? row.remark : amount(row[field])}</span>;
  function change(value: string) {
    if (!row) return;
    setText(value); context.actions.current.draft(context.scope, row, field, value, base.current);
  }
  function tab(event: React.KeyboardEvent<HTMLInputElement>) {
    event.stopPropagation();
    if (event.nativeEvent.isComposing || composing.current) return;
    if (event.key === 'Enter') { event.preventDefault(); event.currentTarget.blur(); return; }
    if (event.key !== 'Tab' || !row) return;
    const api = context.api.current; if (!api) return;
    const cells: { index: number; field: Field; key: string }[] = [];
    api.forEachNodeAfterFilterAndSort(node => { if (node.data && node.rowIndex !== null) for (const field of fields) if (editable(node.data, field)) cells.push({ index: node.rowIndex, field, key: node.data.key }); });
    const index = cells.findIndex(cell => cell.key === row.key && cell.field === field);
    const next = cells[index + (event.shiftKey ? -1 : 1)]; if (!next) return;
    event.preventDefault();
    const region = event.currentTarget.closest('[data-ledger-side]');
    api.ensureIndexVisible(next.index); api.ensureColumnVisible(next.field); api.setFocusedCell(next.index, next.field);
    requestAnimationFrame(() => region?.querySelector<HTMLInputElement>(`[row-id="${CSS.escape(next.key)}"] [col-id="${next.field}"] input`)?.focus());
  }
  return <input className={`ledger-input ${field === 'other_expense' || field === 'payment' ? 'money' : ''}`}
    aria-label={`${row.category === 'material' ? '辅材' : '机械'} ${row.month} ${labels[field]}`}
    type={field === 'month' ? 'month' : 'text'} max={field === 'month' ? '2025-11' : undefined}
    maxLength={field === 'remark' ? 512 : undefined} inputMode={field === 'other_expense' || field === 'payment' ? 'decimal' : undefined}
    value={text} title="离开单元格即保存" onFocus={() => { base.current = row[field]; }}
    onChange={event => change(event.target.value)} onBlur={() => { if (!composing.current) context.actions.current.commit(context.scope, row, field); }}
    onKeyDown={tab} onCompositionStart={() => { composing.current = true; }}
    onCompositionEnd={event => { composing.current = false; change(event.currentTarget.value); if (document.activeElement !== event.currentTarget) context.actions.current.commit(context.scope, row, field); }} />;
}
function DeleteCell({ data: row, context }: ICellRendererParams<LedgerRow, string, GridContext>) {
  return row?.row_kind === 'manual' && context.actions.current.writable() ? <button className="text-action" disabled={context.actions.current.busy()} title="删除历史行，可撤销" onClick={() => context.actions.current.remove(context.scope, row)}>删除</button> : null;
}
function Side({ side, scope, actions, writable, busy }: { side: LedgerSide; scope: Scope; actions: React.RefObject<Actions>; writable: boolean; busy: boolean }) {
  const api = useRef<GridApi<LedgerRow> | null>(null);
  const context = useMemo(() => ({ scope, actions, api }), [scope, actions]);
  useEffect(() => { if (writable) api.current?.refreshCells({ force: true }); }, [writable, busy]);
  const columns = useMemo<ColDef<LedgerRow>[]>(() => [
    { field: 'seq', headerName: '序号', width: 70, pinned: 'left' },
    { field: 'month', headerName: '月份', width: 145, pinned: 'left', cellRenderer: Cell },
    { field: 'other_expense', headerName: '其他支出金额', width: 185, cellRenderer: Cell, cellClass: 'money' },
    { field: 'payment', headerName: '付款', width: 175, cellRenderer: Cell, cellClass: 'money' },
    { field: 'debt', headerName: '欠款', width: 175, valueFormatter: p => typeof p.value === 'string' ? amount(p.value) : '—', cellClass: 'money' },
    { field: 'remark', headerName: '备注', width: 260, flex: 1, minWidth: 180, cellRenderer: Cell, wrapText: true, autoHeight: true },
    { colId: 'actions', headerName: '操作', width: 78, cellRenderer: DeleteCell },
  ], []);
  const visible = useMemo(() => side.rows.filter(row => row.row_kind !== 'month' || row.other_expense !== '0.00' || row.payment !== '0.00' || row.remark), [side.rows]);
  const total = useMemo<LedgerRow[]>(() => [{ key: 'total', category: side.category, seq: 0, month: '', month_label: '合计', row_kind: 'undated', record_id: null, other_expense: sum(side.rows, 'other_expense'), payment: sum(side.rows, 'payment'), debt: sum(side.rows, 'debt'), remark: '', token: '', editable: false, counts_in_total: false }], [side]);
  return <div role="region" aria-label={`${side.label}欠款台账`} data-ledger-side={side.category} className="ledger-side">
    <h2>{side.label}欠款台账</h2>
    <div className="ledger-grid"><AgGridReact<LedgerRow> theme={gridTheme}
      context={context} columnDefs={columns} rowData={visible} pinnedBottomRowData={total}
      getRowId={params => params.data.key} defaultColDef={defaultColumn}
      rowHeight={44} headerHeight={40} suppressCellFocus={true} suppressScrollOnNewData={true}
      overlayNoRowsTemplate="没有台账数据，可在辅材中新增历史行。" animateRows={false}
      onGridReady={event => { api.current = event.api; }} onFirstDataRendered={event => { if (visible.length) event.api.ensureIndexVisible(visible.length - 1, 'bottom'); }} />
    </div>
  </div>;
}
interface HistoryItem { id: number; label: string; count: number }
interface HistoryStatus { undo: HistoryItem | null; redo: HistoryItem | null; notice: string }
function readHistory(value: unknown): HistoryStatus {
  if (!record(value)) throw new ApiError('操作历史未能读取，请刷新重试。');
  function item(value: unknown): HistoryItem | null {
    if (value === null) return null;
    if (!record(value) || typeof value.id !== 'number' || !Number.isInteger(value.id) || typeof value.label !== 'string' || typeof value.count !== 'number') throw new ApiError('操作历史未能读取，请刷新重试。');
    return { id: value.id, label: value.label, count: value.count };
  }
  return { undo: item(value.undo), redo: item(value.redo), notice: typeof value.notice === 'string' ? value.notice : '' };
}
function previousMonth() { const now = new Date(); return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1)).toISOString().slice(0, 7); }

export function LedgerPage({ me, blocked }: { me: Identity | null; blocked: boolean }) {
  const client = useQueryClient();
  const [project, setProject] = useState(0); const [end, setEnd] = useState(previousMonth);
  const [choosing, setChoosing] = useState(false); const [keyword, setKeyword] = useState('');
  const [, render] = useState(0); const [controlBusy, setControlBusy] = useState(false);
  const owner = me ? `${me.id}:${me.account}` : 'anonymous';
  const scope = useMemo<Scope>(() => ({ key: `${owner}:${project}:${end}`, owner, project, end }), [owner, project, end]);
  const current = useRef({ scope, blocked, me }); current.current = { scope, blocked, me };
  const lifetime = useRef<AbortController | null>(null);
  const mounted = useRef(true); const edits = useRef(new Map<string, Edit>()); const messages = useRef(new Map<string, string>());
  const jobs = useRef(new Set<Promise<void>>()); const serial = useRef(0); const acting = useRef(false);
  const pointerDown = useRef(false);
  const body = useRef<HTMLDivElement>(null); const [display, setDisplay] = useState<{ key: string; data: Ledger } | null>(null);
  const pendingDisplay = useRef<{ key: string; data: Ledger } | null>(null);
  useEffect(() => { mounted.current = true; lifetime.current = new AbortController(); return () => { mounted.current = false; lifetime.current?.abort(); }; }, []);
  const projects = useQuery({ queryKey: ['projects', 'all', ''], enabled: !blocked,
    queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const query = useQuery({ queryKey: ['ledger', owner, project, end], enabled: !blocked && project > 0,
    queryFn: ({ signal }) => loadLedger(project, end, signal) });
  const history = useQuery({ queryKey: ['history', owner], enabled: !blocked && Boolean(me),
    queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
  const changed = () => { if (mounted.current) render(n => n + 1); };
  function message(s: Scope, text: string) { messages.current.set(s.key, text); changed(); }
  function state(s: Scope, row: LedgerRow): Edit {
    const key = `${s.key}|${row.key}`; let edit = edits.current.get(key);
    if (!edit) { edit = { scope: s, base: row, drafts: {}, own: new Map(), queue: [], saving: false, locked: false }; edits.current.set(key, edit); }
    return edit;
  }
  function accept(s: Scope, data: Ledger) {
    for (const edit of edits.current.values()) {
      if (edit.scope.owner !== s.owner || edit.scope.project !== s.project) continue;
      const row = data.sides.flatMap(side => side.rows).find(row => row.key === edit.base.key);
      if (row) { edit.base = row; edit.locked = false; }
    }
  }
  function publish() {
    if (pointerDown.current) return;
    if (body.current?.contains(document.activeElement) && document.activeElement instanceof HTMLInputElement) return;
    const next = pendingDisplay.current;
    if (next?.key === current.current.scope.key && mounted.current) { setDisplay(next); pendingDisplay.current = null; }
  }
  useEffect(() => {
    const release = () => { pointerDown.current = false; requestAnimationFrame(publish); };
    document.addEventListener('click', release, true); document.addEventListener('pointercancel', release, true);
    return () => { document.removeEventListener('click', release, true); document.removeEventListener('pointercancel', release, true); };
  }, []);
  useEffect(() => {
    if (!query.data || blocked) return;
    accept(scope, query.data); pendingDisplay.current = { key: scope.key, data: query.data }; publish(); changed();
  }, [query.data, scope, blocked]);
  async function refresh(s: Scope) {
    if (current.current.blocked || !mounted.current) throw new ApiError('账号待核实，恢复后请刷新核对。');
    await client.cancelQueries({ queryKey: ['ledger', s.owner, s.project] });
    if (current.current.blocked || !mounted.current) throw new ApiError('账号待核实，恢复后请刷新核对。');
    const full = await client.fetchQuery({ queryKey: ['ledger', s.owner, s.project, ''], queryFn: ({ signal }) => loadLedger(s.project, '', signal), staleTime: 0 });
    if (!mounted.current) return full;
    accept(s, full);
    if (!current.current.blocked) {
      await client.invalidateQueries({ queryKey: ['ledger', s.owner, s.project] });
      await client.invalidateQueries({ queryKey: ['history', s.owner] });
    }
    return full;
  }
  function clearQueue(edit: Edit) { edit.queue = []; for (const draft of Object.values(edit.drafts)) if (draft) draft.queued = false; }
  async function drain(edit: Edit) {
    if (edit.saving) return;
    edit.saving = true; changed();
    try {
      while (edit.queue.length) {
        if (!mounted.current || current.current.blocked || !current.current.me) { clearQueue(edit); return; }
        const task = edit.queue.shift(); if (!task) break;
        if (edit.locked) { clearQueue(edit); message(edit.scope, '已保存，但页面数据未能刷新。请先刷新核对；后续输入已保留。'); break; }
        if (same(task.field, edit.base[task.field], task.text)) {
          if (edit.drafts[task.field]?.version === task.version) delete edit.drafts[task.field];
          continue;
        }
        if (task.month !== edit.base.month || !same(task.field, edit.base[task.field], task.base)) {
          clearQueue(edit); message(edit.scope, '版本冲突：这一格已变化，未覆盖。请刷新核对，重新填写或放弃未保存输入。'); break;
        }
        void client.cancelQueries({ queryKey: ['ledger', edit.scope.owner, edit.scope.project] });
        const before = edit.base;
        const result = await requestJson('/api/m05/history/save', { method: 'POST', signal: lifetime.current!.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload(edit.scope.project, { ...before, [task.field]: task.text })) });
        if (!record(result) || typeof result.id !== 'number' || !Number.isInteger(result.id)) throw new ApiError('保存结果未确认，请刷新核对后再试。');
        if (edit.drafts[task.field]?.version === task.version) delete edit.drafts[task.field];
        edit.locked = true;
        try {
          const full = await refresh(edit.scope);
          const saved = full.sides.flatMap(side => side.rows).find(row => row.key === before.key);
          if (!saved) throw new ApiError('原记录已不在台账中，请刷新核对。');
          // Only our acknowledged edit advances later drafts of the same cell.
          if (same(task.field, saved[task.field], task.text)) {
            for (const other of edits.current.values()) if (other.scope.owner === edit.scope.owner && other.scope.project === edit.scope.project && other.base.key === before.key) {
              // Frozen inputs may still carry a token from before our own acknowledged save.
              for (const values of other.own.values()) values[task.field] = saved[task.field];
              const values = other.own.get(before.token) ?? {}; values[task.field] = saved[task.field]; other.own.set(before.token, values);
              if (task.field === 'month') {
                for (const draft of Object.values(other.drafts)) if (draft?.month === before.month) draft.month = saved.month;
                for (const queued of other.queue) if (queued.month === before.month) queued.month = saved.month;
              }
              const draft = other.drafts[task.field]; if (draft && same(task.field, draft.base, task.base)) draft.base = saved[task.field];
              for (const queued of other.queue) if (queued.field === task.field && same(task.field, queued.base, task.base)) queued.base = saved[task.field];
            }
          }
          edit.base = saved; edit.locked = false; message(edit.scope, '台账已保存；合计在结束连续编辑后更新。');
        } catch (error) {
          clearQueue(edit); message(edit.scope, `已保存，但页面数据未能刷新。请刷新核对，不必重复提交已保存值。${error instanceof Error ? error.message : ''}`); break;
        }
      }
    } catch (error) {
      clearQueue(edit);
      const text = error instanceof Error ? error.message : '请刷新核对后重试。';
      message(edit.scope, error instanceof ApiError && error.status === 0 ? `保存结果未确认：${text}请刷新核对，输入已保留。` : /已变化|冲突/.test(text) || (error instanceof ApiError && error.status === 409) ? `版本冲突：${text}输入已保留，请刷新核对。` : `保存被拒：${text}输入已保留，请修改后重试。`);
    } finally { edit.saving = false; changed(); }
  }
  function hasDrafts(s: Scope) { return [...edits.current.values()].some(edit => edit.scope.key === s.key && Object.keys(edit.drafts).length > 0); }
  async function control(s: Scope, action: () => Promise<void>, allowDrafts = false) {
    if (acting.current || current.current.blocked || !current.current.me) return;
    acting.current = true; setControlBusy(true);
    try {
      await Promise.all([...jobs.current]);
      if (!mounted.current || current.current.blocked || s.key !== current.current.scope.key) return;
      if (!allowDrafts && hasDrafts(s)) { message(s, '请先处理未保存输入，再执行本次操作。'); return; }
      await action();
    } catch (error) { message(s, error instanceof Error ? error.message : '操作失败，请重试。'); }
    finally { acting.current = false; if (mounted.current) setControlBusy(false); }
  }
  const actions = useRef<Actions>(null!);
  actions.current = {
    writable: () => Boolean(current.current.me) && !current.current.blocked,
    busy: () => acting.current,
    value: (s, row, field) => state(s, row).drafts[field]?.text ?? row[field],
    draft: (s, row, field, text, base) => {
      const edit = state(s, row); const own = edit.own.get(row.token);
      edit.drafts[field] = { text, base: edit.drafts[field]?.base ?? own?.[field] ?? base, version: ++serial.current, queued: false, month: edit.drafts[field]?.month ?? own?.month ?? row.month }; changed();
    },
    commit: (s, row, field) => {
      const edit = state(s, row); const draft = edit.drafts[field]; if (!draft || draft.queued) return;
      if (current.current.blocked || !current.current.me) { message(s, '输入已保留；账号恢复后重新离格保存。'); return; }
      if (same(field, draft.text, draft.base) && !edit.saving && !edit.queue.length) { delete edit.drafts[field]; changed(); return; }
      draft.queued = true; edit.queue.push({ ...draft, field });
      const job = drain(edit); jobs.current.add(job); void job.finally(() => jobs.current.delete(job));
    },
    remove: (s, row) => { void control(s, async () => {
      const edit = state(s, row);
      if (edit.locked) throw new ApiError('请先刷新核对，再删除历史行。');
      await requestJson('/api/m05/history/delete', { method: 'POST', signal: lifetime.current!.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: edit.base.record_id, token: edit.base.token }) });
      try { await refresh(s); message(s, '历史行已删除，可撤销。'); }
      catch { message(s, '已删除，但页面数据未能刷新。请刷新核对，不必重复删除。'); }
    }); },
  };
  async function replay(direction: 'undo' | 'redo') {
    const s = current.current.scope;
    await control(s, async () => {
      const latest = await client.fetchQuery({ queryKey: ['history', owner], queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })), staleTime: 0 });
      if (!mounted.current || current.current.blocked || !current.current.me) return;
      const item = latest[direction]; if (!item) { message(s, direction === 'undo' ? '暂无可撤销的操作。' : '暂无可重做的操作。'); return; }
      await requestJson(`/api/history/${direction}`, { method: 'POST', signal: lifetime.current!.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation_id: item.id }) });
      try { await refresh(s); await client.invalidateQueries({ queryKey: ['projects'] }); message(s, direction === 'undo' ? '已撤销。' : '已重做。'); }
      catch { message(s, '操作已完成，但页面数据未能刷新。请刷新核对，不必重复操作。'); }
    });
  }
  const replayRef = useRef(replay); replayRef.current = replay;
  useEffect(() => { const listener = (event: KeyboardEvent) => {
    if (!(event.ctrlKey || event.metaKey) || event.altKey || event.isComposing || (event.target instanceof Element && event.target.closest('input,textarea,select,[contenteditable="true"]'))) return;
    const key = event.key.toLowerCase(); const direction = key === 'z' ? event.shiftKey ? 'redo' : 'undo' : key === 'y' ? 'redo' : null;
    if (direction) { event.preventDefault(); void replayRef.current(direction); }
  }; window.addEventListener('keydown', listener); return () => window.removeEventListener('keydown', listener); }, []);
  const selected = projects.data?.find(item => item.id === project);
  const shown = display?.key === scope.key ? display.data : null;
  return <section aria-labelledby="ledger-title">
    <div className="card-head"><h1 id="ledger-title">历史台账</h1><div className="ledger-tools">
      <button disabled={!me || blocked || controlBusy || !history.data?.undo} title={history.data?.undo?.label ?? '暂无可撤销的操作'} onClick={() => void replay('undo')}>撤销</button>
      <button disabled={!me || blocked || controlBusy || !history.data?.redo} title={history.data?.redo?.label ?? '暂无可重做的操作'} onClick={() => void replay('redo')}>重做</button>
      <button disabled={!project || blocked || controlBusy} onClick={() => { if (!me) { void query.refetch(); return; } void control(scope, async () => { await refresh(scope); message(scope, '台账已刷新，未保存输入仍保留。'); }, true); }}>刷新台账</button>
      <button disabled={!me || !selected?.warehouse_name || !end || blocked || controlBusy} title={!end ? '请选择截止月份后导出' : '导出已保存的同项目、同截止月份台账'} onClick={() => { void control(scope, async () => {
        const result = await requestFile(`/api/m05/ledger/export?${new URLSearchParams({ projects: selected?.warehouse_name ?? '', ym: end })}`);
        if (!mounted.current || current.current.blocked || scope.key !== current.current.scope.key) return;
        const url = URL.createObjectURL(result.blob); const link = document.createElement('a'); link.href = url; link.download = result.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); message(scope, '台账已导出。');
      }); }}>导出台账</button>
    </div></div>
    <div className="filters"><button aria-expanded={choosing} aria-controls="ledger-projects" onClick={() => setChoosing(value => !value)}>选择项目</button><span>{selected?.disp || selected?.name_full || '尚未选择项目'}</span>
      <label>截止月份<input aria-label="截止月份" type="month" value={end} onChange={event => setEnd(event.target.value)} /></label>
      <button disabled={!me || !project || blocked || controlBusy} onClick={() => { void control(scope, async () => {
        const result = await requestJson('/api/m05/history/save', { method: 'POST', signal: lifetime.current!.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: project, category: 'material', entry_kind: 'manual', cutoff_ym: end && end < '2025-11' ? end : '2025-11', settle_amount: '0', paid_amount: '0', remark: '' }) });
        if (!record(result) || typeof result.id !== 'number') throw new ApiError('新增结果未确认，请刷新核对后再试。');
        try { await refresh(scope); message(scope, '已新增历史行，请直接填写。'); }
        catch { message(scope, '已新增历史行，但页面数据未能刷新。请刷新核对，不必重复新增。'); }
      }); }}>新增历史行</button>
    </div>
    {choosing && <div id="ledger-projects" className="project-picker"><label>搜索项目<input value={keyword} onChange={event => setKeyword(event.target.value)} /></label>
      {projects.isError ? <p role="alert">{projects.error.message}</p> : projects.isPending ? <p role="status">正在读取项目…</p> : projects.data.filter(item => item.project_type !== 'shell' && `${item.name_full}${item.disp}${item.warehouse_name ?? ''}`.includes(keyword.trim())).map(item => <button key={item.id} aria-pressed={item.id === project} onClick={() => { setProject(item.id); setChoosing(false); }}>{item.disp || item.name_full}</button>)}
    </div>}
    <div className="ledger-receipts"><p role="status" aria-label="保存回执">{messages.current.get(scope.key) ?? (me ? '离开单元格即保存。' : '未登录，台账只读。')}{[...edits.current.values()].some(edit => edit.scope.key === scope.key && edit.saving) ? ' 正在保存…' : ''}</p>
      {hasDrafts(scope) && <button onClick={() => { for (const edit of edits.current.values()) if (edit.scope.key === scope.key && !edit.saving) { edit.drafts = {}; clearQueue(edit); } if (query.data) { pendingDisplay.current = { key: scope.key, data: query.data }; publish(); } message(scope, '已放弃未保存输入。'); changed(); }}>放弃未保存输入</button>}
      {history.isError && <p role="alert">操作历史未能读取，请刷新重试。</p>}{history.data?.notice && <p>{history.data.notice}</p>}
    </div>
    {project === 0 ? <p className="state">请选择项目查看台账。</p> : query.isError ? <p className="notice" role="alert">{shown ? '页面数据未能刷新，保留上次结果。' : ''}{query.error.message}</p> : !shown ? <p className="state" role="status">正在读取台账…</p> : null}
    {shown && <div ref={body} className="ledger-sides" onPointerDownCapture={() => { pointerDown.current = true; }} onPointerCancelCapture={() => { pointerDown.current = false; requestAnimationFrame(publish); }} onClickCapture={() => { pointerDown.current = false; requestAnimationFrame(publish); }} onBlurCapture={() => requestAnimationFrame(publish)}>{shown.sides.map(side => <Side key={`${scope.key}:${side.category}`} side={side} scope={scope} actions={actions} writable={Boolean(me) && !blocked} busy={controlBusy} />)}</div>}
  </section>;
}
