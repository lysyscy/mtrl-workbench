import Button from 'antd/es/button';
import { readHistory, useHistoryState } from './history';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { LedgerExport, ProjectPicker } from './ledger-controls';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import { fitGridColumns, contentWidth, gridTheme } from './grid';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { ApiError, projectLabel, readProjects, record, requestJson } from './api';
import type { Identity } from './api';
import { amount, editable, loadLedger, payload, same, sum } from './ledger-api';
import type { Field, Ledger, LedgerRow, LedgerSide } from './ledger-api';

const fields: Field[] = ['month', 'other_expense', 'payment', 'remark'];
const compareMoney = (a: string, b: string) => { const left = BigInt(a.replace('.', '')); const right = BigInt(b.replace('.', '')); return left < right ? -1 : left > right ? 1 : 0; };
const labels = { month: '月份', other_expense: '结算', payment: '付款', remark: '备注' };
const defaultColumn: ColDef<LedgerRow> = { sortable: true, resizable: false, suppressMovable: true, suppressKeyboardEvent: event => event.event.target instanceof HTMLInputElement };

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
function DeleteCell({ data: row, context, node }: ICellRendererParams<LedgerRow, string, GridContext>) {
  return row?.row_kind === 'manual' && context.actions.current.writable() ? <Button htmlType="submit" className="ledger-delete" disabled={context.actions.current.busy()} title="删除历史行，可撤销" onClick={() => context.actions.current.remove(context.scope, row)}>删除</Button> : node.rowPinned ? null : <span className="muted">—</span>;
}
function Side({ side, scope, actions, writable, busy, add, focusRecord, focused }: { side: LedgerSide; scope: Scope; actions: React.RefObject<Actions>; writable: boolean; busy: boolean; add: () => void; focusRecord: number | null; focused: () => void }) {
  const api = useRef<GridApi<LedgerRow> | null>(null); const root = useRef<HTMLDivElement>(null);
  const scale = Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1;
  const context = useMemo(() => ({ scope, actions, api }), [scope, actions]);
  useEffect(() => { if (writable) api.current?.refreshCells({ force: true }); }, [writable, busy]);
  const visible = useMemo(() => side.rows.filter(row => row.row_kind !== 'month' || row.editable || row.other_expense !== '0.00' || row.payment !== '0.00' || row.remark).map((row, index) => ({ ...row, seq: index + 1 })), [side.rows]);
  const months = visible.filter(row => row.row_kind === 'month'); const latest = months.at(-1);
  const upto = latest?.month || side.rows.at(-1)?.month || '—';
  const total = useMemo<LedgerRow[]>(() => side.rows.length ? [{ key: 'total', category: side.category, seq: 0, month: '', month_label: `截至 ${upto}`, row_kind: 'undated', record_id: null, other_expense: sum(side.rows, 'other_expense'), payment: sum(side.rows, 'payment'), debt: sum(side.rows, 'debt'), remark: side.category === 'material' ? '' : '当前欠款', token: '', editable: false, counts_in_total: false }] : [], [side, upto]);
  const columns = useMemo<ColDef<LedgerRow>[]>(() => [
    { field: 'seq', headerName: '序号', ...contentWidth(44, 58, scale), colSpan: p => p.node?.rowPinned ? 2 : 1, cellClass: p => p.node?.rowPinned ? 'ledger-total-label' : '', valueFormatter: p => p.node?.rowPinned ? `截至 ${upto}` : String(p.value ?? '') },
    { field: 'month', headerName: '月份（按单据日期）', ...contentWidth(110, 180, scale), cellRenderer: Cell },
    { field: 'other_expense', headerName: side.category === 'mechanical' ? '机械结算金额' : '其他支出金额', ...contentWidth(110, 190, scale), comparator: compareMoney, cellRenderer: Cell, cellClass: 'money' },
    { field: 'payment', headerName: '付款', ...contentWidth(90, 175, scale), comparator: compareMoney, cellRenderer: Cell, cellClass: 'money' },
    { field: 'debt', headerName: '欠款', ...contentWidth(90, 175, scale), comparator: compareMoney, cellRenderer: (p: ICellRendererParams<LedgerRow, string>) => <span className={p.node?.rowPinned ? '' : Number(p.value) > 0 ? 'debt-positive' : 'muted'}>{typeof p.value === 'string' ? amount(p.value) : '—'}</span>, cellClass: 'money' },
    { field: 'remark', headerName: '备注', ...contentWidth(90, 300, scale, 1), wrapText: true, autoHeight: true, cellRenderer: Cell },
    { colId: 'actions', headerName: '操作', ...contentWidth(52, 78, scale), sortable: false, cellRenderer: DeleteCell },
  ], [side.category, scale, upto]);
  useEffect(() => {
    if (!focusRecord || !api.current) return;
    const node = api.current.getRowNode(`${side.category}:manual:${focusRecord}`);
    if (node?.rowIndex === null || node?.rowIndex === undefined) return;
    api.current.ensureIndexVisible(node.rowIndex); api.current.ensureColumnVisible('month');
    requestAnimationFrame(() => {
      const input = root.current?.querySelector<HTMLInputElement>(`[row-id="${side.category}:manual:${focusRecord}"] [col-id="month"] input`);
      if (input) { input.scrollIntoView({ block: 'nearest', inline: 'nearest' }); input.focus({ preventScroll: true }); focused(); }
    });
  }, [focusRecord, visible, side.category, focused]);
  return <div ref={root} role="region" aria-label={`${side.label}欠款台账`} data-ledger-side={side.category} className="ledger-side">
    <div className="ledger-summary"><h2>{side.label}欠款台账</h2>{side.category === 'material' && <Button htmlType="submit" aria-label="新增历史行" disabled={!writable || busy} onClick={add}>＋ 新增历史行</Button>}</div>
    <div className="ledger-table-scroll"><div className="ledger-grid" style={{ height: Math.min(360 * scale, (29 + Math.max(visible.length, 1) * 38 + (total.length ? 30 : 0) + 2) * scale) }}><AgGridReact<LedgerRow> theme={gridTheme} onGridSizeChanged={e => fitGridColumns(e.api, root.current)} onNewColumnsLoaded={e => fitGridColumns(e.api, root.current, true)} suppressColumnVirtualisation enableCellTextSelection ensureDomOrder
      context={context} columnDefs={columns} rowData={visible} pinnedBottomRowData={total}
      getRowId={params => params.data.key} defaultColDef={defaultColumn}
      rowHeight={38 * scale} getRowHeight={params => params.node.rowPinned ? 30 * scale : 38 * scale} headerHeight={29 * scale} suppressCellFocus={true} suppressScrollOnNewData={true}
      overlayNoRowsTemplate="暂无台账数据。" animateRows={false}
      onGridReady={event => { api.current = event.api; }} onFirstDataRendered={event => { fitGridColumns(event.api, root.current, true); if (visible.length) event.api.ensureIndexVisible(visible.length - 1, 'bottom'); }} />
    </div></div>
  </div>;
}
export function LedgerPage({ me, blocked, project, setProject, active, onExportGuard }: { me: Identity | null; blocked: boolean; active: boolean; project: number; setProject: (project: number) => void; onExportGuard: (reason: string) => void }) {
  const client = useQueryClient();
  const { busy: historyBusy, uncertain: historyUncertain } = useHistoryState();
  const end = ''; // The established ledger follows the data's last month; report month belongs to export only.
  const [focusRecord, setFocusRecord] = useState<number | null>(null);
  const [, render] = useState(0); const [controlBusy, setControlBusy] = useState(false);
  const owner = me ? `${me.id}:${me.account}` : 'anonymous';
  const scope = useMemo<Scope>(() => ({ key: `${owner}:${project}:${end}`, owner, project, end }), [owner, project, end]);
  const current = useRef({ scope, blocked, me, active, historyBusy, historyUncertain }); current.current = { scope, blocked, me, active, historyBusy, historyUncertain };
  const lifetime = useRef<AbortController | null>(null);
  const mounted = useRef(true); const edits = useRef(new Map<string, Edit>()); const messages = useRef(new Map<string, { text: string; reload: boolean }>());
  const jobs = useRef(new Set<Promise<void>>()); const serial = useRef(0); const acting = useRef(false);
  const pointerDown = useRef(false);
  const body = useRef<HTMLDivElement>(null); const [display, setDisplay] = useState<{ key: string; data: Ledger } | null>(null);
  const pendingDisplay = useRef<{ key: string; data: Ledger } | null>(null);
  useEffect(() => { mounted.current = true; lifetime.current = new AbortController(); return () => { mounted.current = false; lifetime.current?.abort(); }; }, []);
  const projects = useQuery({ queryKey: ['projects', 'all', ''], enabled: !blocked,
    queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const candidates = useMemo(() => projects.data?.filter(item => item.project_type !== 'shell').sort((a, b) => a.ord - b.ord || projectLabel(a).localeCompare(projectLabel(b), 'zh')) ?? [], [projects.data]);
  useEffect(() => { if (!blocked && projects.data && !candidates.some(item => item.id === project)) setProject(candidates[0]?.id ?? 0); }, [blocked, projects.data, candidates, project, setProject]);
  const query = useQuery({ queryKey: ['ledger', owner, project, end], enabled: !blocked && project > 0,
    queryFn: ({ signal }) => loadLedger(project, end, signal) });
  const changed = () => { if (mounted.current) render(n => n + 1); };
  function message(s: Scope, text: string, reload = false) { messages.current.set(s.key, { text, reload }); changed(); }
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
      await client.invalidateQueries({ queryKey: ['ledger', s.owner, s.project], refetchType: 'none' });
      await client.invalidateQueries({ queryKey: ['debt'] }, { throwOnError: true });
      await client.fetchQuery({ queryKey: ['history', s.owner], queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })), staleTime: 0 });
      changed();
    }
    return full;
  }
  function clearQueue(edit: Edit) { edit.queue = []; for (const draft of Object.values(edit.drafts)) if (draft) draft.queued = false; }
  async function drain(edit: Edit) {
    if (edit.saving) return;
    edit.saving = true; changed();
    try {
      while (edit.queue.length) {
        if (!mounted.current || current.current.blocked || current.current.historyBusy || current.current.historyUncertain || !current.current.me) { clearQueue(edit); return; }
        const task = edit.queue.shift(); if (!task) break;
        if (edit.locked) { clearQueue(edit); message(edit.scope, '已保存，读取失败；后续输入已保留。', true); break; }
        if (same(task.field, edit.base[task.field], task.text)) {
          if (edit.drafts[task.field]?.version === task.version) delete edit.drafts[task.field];
          continue;
        }
        if (task.month !== edit.base.month || !same(task.field, edit.base[task.field], task.base)) {
          clearQueue(edit); message(edit.scope, '版本冲突，输入已保留。请重新加载核对。', true); break;
        }
        void client.cancelQueries({ queryKey: ['ledger', edit.scope.owner, edit.scope.project] });
        const before = edit.base;
        const remarkOnly = !before.editable && task.field === 'remark';
        const result = await requestJson(remarkOnly ? '/m05/ledger/remark' : '/api/m05/history/save', { method: 'POST', signal: lifetime.current!.signal,
          headers: { 'Content-Type': remarkOnly ? 'application/x-www-form-urlencoded' : 'application/json' },
          body: remarkOnly ? new URLSearchParams({ project_id: String(edit.scope.project), category: before.category, ym: before.month, remark: task.text.trim(), token: before.token }) : JSON.stringify(payload(edit.scope.project, { ...before, [task.field]: task.text })) });
        if (!record(result) || (!remarkOnly && (typeof result.id !== 'number' || !Number.isInteger(result.id)))) throw new ApiError('保存结果未确认，请刷新核对后再试。');
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
          edit.base = saved; edit.locked = false; message(edit.scope, '台账已保存。');
        } catch (error) {
          clearQueue(edit); message(edit.scope, `已保存，读取失败；请重新加载，不必重复提交。${error instanceof Error ? error.message : ''}`, true); break;
        }
      }
    } catch (error) {
      clearQueue(edit);
      const text = error instanceof Error ? error.message : '请刷新核对后重试。';
      message(edit.scope, error instanceof ApiError && error.status === 0 ? `保存结果未确认：${text}请刷新核对，输入已保留。` : /已变化|冲突/.test(text) || (error instanceof ApiError && error.status === 409) ? `版本冲突：${text}输入已保留，请刷新核对。` : `保存被拒：${text}输入已保留，请修改后重试。`, (error instanceof ApiError && (error.status === 0 || error.status === 409)) || /已变化|冲突/.test(text));
    } finally { edit.saving = false; changed(); }
  }
  function hasDrafts(s: Scope) { return [...edits.current.values()].some(edit => edit.scope.key === s.key && Object.keys(edit.drafts).length > 0); }
  async function control(s: Scope, action: () => Promise<void>, allowDrafts = false, exportProjects?: number[]): Promise<string | null> {
    if (current.current.historyBusy || current.current.historyUncertain) return '全局操作正在处理或结果待核实，请在顶栏重读核对。';
    if (acting.current || current.current.blocked || current.current.historyBusy || current.current.historyUncertain || !current.current.me) return '账号待核实或操作正在进行，请稍后重试。';
    acting.current = true; setControlBusy(true);
    try {
      await Promise.all([...jobs.current]);
      if (!mounted.current || current.current.blocked || s.key !== current.current.scope.key) return '账号或查看范围已变化，请重新确认。';
      if (exportProjects && (messages.current.get(s.key)?.reload || [...edits.current.values()].some(edit => edit.scope.owner === s.owner && exportProjects.includes(edit.scope.project) && edit.locked))) return '操作结果待核实，请先重新加载核对。';
      const drafts = exportProjects ? [...edits.current.values()].some(edit => edit.scope.owner === s.owner && exportProjects.includes(edit.scope.project) && Object.keys(edit.drafts).length > 0) : hasDrafts(s);
      if (!allowDrafts && drafts) { const text = '请先处理未保存输入，再执行本次操作。'; message(s, text); return text; }
      await action(); return null;
    } catch (error) { const text = error instanceof Error ? error.message : '操作失败，请重试。'; message(s, text, !exportProjects && error instanceof ApiError && (error.status === 0 || error.status === 409 || error.status >= 500)); return text; }
    finally { acting.current = false; if (mounted.current) setControlBusy(false); }
  }
  const actions = useRef<Actions>(null!);
  actions.current = {
    writable: () => Boolean(current.current.me) && !current.current.blocked && !current.current.historyBusy && !current.current.historyUncertain,
    busy: () => acting.current,
    value: (s, row, field) => state(s, row).drafts[field]?.text ?? row[field],
    draft: (s, row, field, text, base) => {
      const edit = state(s, row); const own = edit.own.get(row.token);
      edit.drafts[field] = { text, base: edit.drafts[field]?.base ?? own?.[field] ?? base, version: ++serial.current, queued: false, month: edit.drafts[field]?.month ?? own?.month ?? row.month }; changed();
    },
    commit: (s, row, field) => {
      const edit = state(s, row); const draft = edit.drafts[field]; if (!draft || draft.queued) return;
      if (current.current.blocked || current.current.historyBusy || current.current.historyUncertain || !current.current.me) { message(s, '输入已保留；账号恢复后重新离格保存。'); return; }
      if (same(field, draft.text, draft.base) && !edit.saving && !edit.queue.length) { delete edit.drafts[field]; changed(); return; }
      draft.queued = true; edit.queue.push({ ...draft, field });
      const job = drain(edit); jobs.current.add(job); void job.finally(() => jobs.current.delete(job));
    },
    remove: (s, row) => { void control(s, async () => {
      const edit = state(s, row);
      if (edit.locked) throw new ApiError('请先刷新核对，再删除历史行。');
      await requestJson('/api/m05/history/delete', { method: 'POST', signal: lifetime.current!.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: edit.base.record_id, token: edit.base.token }) });
      try { await refresh(s); message(s, '历史行已删除，可撤销。'); }
      catch { message(s, '已删除，读取失败；请重新加载，不必重复删除。', true); }
    }); },
  };
  async function add() {
    await control(scope, async () => {
      const result = await requestJson('/api/m05/history/save', { method: 'POST', signal: lifetime.current!.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: project, category: 'material', entry_kind: 'manual', cutoff_ym: '2025-11', settle_amount: '0', paid_amount: '0', remark: '' }) });
      if (!record(result) || typeof result.id !== 'number') throw new ApiError('新增结果未确认，请刷新核对后再试。');
      try { await refresh(scope); if (mounted.current && !current.current.blocked && scope.key === current.current.scope.key) setFocusRecord(result.id); message(scope, '已新增历史行，可直接填写。'); }
      catch { message(scope, '已新增，读取失败；请重新加载，不必重复新增。', true); }
    });
  }
  const shown = display?.key === scope.key ? display.data : null;
  async function reload() {
    if (!me) { void query.refetch(); return; }
    await control(scope, async () => { await refresh(scope); message(scope, '已重新加载；未保存输入仍保留。'); }, true);
  }
  const sharedGuard = [...messages.current.values()].some(item => item.reload) || [...edits.current.values()].some(edit => edit.locked) ? '台账操作结果待核实，请返回台账重新加载。' : controlBusy || [...edits.current.values()].some(edit => edit.saving) ? '台账正在保存，请稍候。' : [...edits.current.values()].some(edit => Object.keys(edit.drafts).length > 0) ? '台账有未保存输入，请返回台账处理。' : '';
  useEffect(() => { onExportGuard(sharedGuard); }, [onExportGuard, sharedGuard]);
  const receipt = messages.current.get(scope.key);
  const exportUnavailable = historyBusy || historyUncertain ? '全局操作正在处理或结果待核实，请在顶栏重读核对。' : !me ? '登录后可导出。' : blocked ? '正在核实账号，暂不能导出。' : controlBusy ? '正在处理操作，请稍候。' : receipt?.reload ? '操作结果待核实，请先重新加载核对。' : query.isError ? '台账读取失败，请先重新加载。' : projects.isError ? '项目读取失败，请先重试。' : projects.isPending ? '正在读取项目…' : '';
  const status = <div className="ledger-status">
    <span role="status" aria-label="保存回执">{receipt?.text ?? (me ? '' : '未登录，台账只读。')}{[...edits.current.values()].some(edit => edit.scope.key === scope.key && edit.saving) ? ' 正在保存…' : ''}</span>
    {(receipt?.reload) && !query.isError && <Button htmlType="submit" disabled={blocked || controlBusy} onClick={() => void reload()}>重新加载</Button>}
    {hasDrafts(scope) && <Button htmlType="submit" onClick={() => { for (const edit of edits.current.values()) if (edit.scope.key === scope.key && !edit.saving) { edit.drafts = {}; clearQueue(edit); } if (query.data) { pendingDisplay.current = { key: scope.key, data: query.data }; publish(); } message(scope, '已放弃未保存输入。'); changed(); }}>放弃未保存输入</Button>}
  </div>;
  return <>
    {active && document.getElementById('ledger-status') && createPortal(status, document.getElementById('ledger-status')!)}
    <section className="ledger-card" aria-labelledby="ledger-title">
      <div className="ledger-card-head"><h1 id="ledger-title">逐月欠款台账</h1><div className="ledger-exports">{(['ledger', 'debt'] as const).map(kind => <LedgerExport key={`${owner}:${kind}`} kind={kind} owner={owner} projects={candidates} project={project} unavailable={exportUnavailable} run={(action, ids) => control(scope, action, false, ids)} message={text => message(scope, text)} paused={blocked || !active} valid={() => mounted.current && !current.current.blocked && current.current.active && scope.key === current.current.scope.key} signal={lifetime.current?.signal} />)}{exportUnavailable && <span className="muted" role="status">{exportUnavailable}</span>}</div></div>
      <div className="ledger-card-body">
        <div className="ledger-view-project"><span className="muted">项目</span><ProjectPicker projects={candidates} selected={[project]} pick={ids => setProject(ids[0] ?? 0)} label="选择项目" disabled={blocked} /></div>
        {projects.isError && <p role="alert">{projects.error.message}<Button htmlType="submit" disabled={blocked || controlBusy} onClick={() => void projects.refetch()}>重试项目</Button></p>}
        {project === 0 ? <p className="state">请选择项目查看台账。</p> : query.isError ? <p className="notice" role="alert">{shown ? '页面数据未能刷新，保留上次结果。' : ''}{query.error.message}<Button htmlType="submit" disabled={blocked || controlBusy} onClick={() => void reload()}>重新加载</Button></p> : !shown ? <p className="state" role="status">正在读取台账…</p> : null}
        {shown && <div ref={body} className="ledger-sides" onPointerDownCapture={() => { pointerDown.current = true; }} onPointerCancelCapture={() => { pointerDown.current = false; requestAnimationFrame(publish); }} onClickCapture={() => { pointerDown.current = false; requestAnimationFrame(publish); }} onBlurCapture={() => requestAnimationFrame(publish)}>{shown.sides.map(side => <Side key={`${scope.key}:${side.category}`} side={side} scope={scope} actions={actions} writable={Boolean(me) && !blocked && !historyBusy && !historyUncertain} busy={controlBusy} add={() => void add()} focusRecord={focusRecord} focused={() => setFocusRecord(null)} />)}</div>}
      </div>
    </section>
  </>;
}
