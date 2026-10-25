import { uncertainWrite } from './api';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Tag from 'antd/es/tag';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { Identity } from './api';
import { pageGridGeometry, contentWidth, fitGridColumns, fixedWidth, gridTheme } from './grid';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { useHistoryGuard } from './history';
import { money } from './notices-api';
import { feeWrite, getFees } from './fees-api';
import type { FeeField, FeeRow } from './fees-api';
import { FeeBatch } from './fees-batch';
import './fees.css';

interface Draft { row: FeeRow; field: FeeField; value: string; error: string }
const keyOf = (id: number, field: FeeField) => `${id}:${field}`;
interface Cells {
  drafts: Record<string, Draft>; disabled: boolean; busy: boolean;
  change: (row: FeeRow, field: FeeField, value: string) => void; save: (id: number, field: FeeField, retry?: boolean) => void;
  cancel: (id: number) => void; remove: (row: FeeRow) => void;
  focus: (id: number, field: FeeField) => void;
}
const FeeCells = createContext<Cells | null>(null);
function FeeInput({ data, colDef, node, api }: ICellRendererParams<FeeRow>) {
  const cells = useContext(FeeCells)!;
  if (!data) return null;
  const field = colDef?.field as FeeField;
  if (node.rowPinned || data.kind === 'auto') return field === 'amount' ? money(data.amount) : data.item;
  const draft = cells.drafts[keyOf(data.id, field)];
  return <Input aria-label={`${data.item || '未命名'}${field === 'item' ? '项名' : '金额'}`} value={draft?.value ?? data[field]}
    disabled={cells.disabled} status={draft?.error ? 'error' : ''} title={draft?.error || (draft ? '未保存' : '')}
    className={field === 'amount' ? 'fee-money-input' : ''} onChange={event => cells.change(data, field, event.target.value)}
    onBlur={() => cells.save(data.id, field)} onKeyDown={event => {
      event.stopPropagation();
      if (event.nativeEvent.isComposing) return;
      if (event.key === 'Enter') { event.preventDefault(); cells.save(data.id, field, true); }
      if (event.key === 'Tab') {
        const sameRow = event.shiftKey ? field === 'amount' : field === 'item';
        const next = sameRow ? node : api.getDisplayedRowAtIndex((node.rowIndex ?? 0) + (event.shiftKey ? -1 : 1));
        if (next?.data?.kind === 'manual') {
          event.preventDefault(); api.ensureIndexVisible(next.rowIndex ?? 0);
          cells.focus(next.data.id, sameRow ? field === 'item' ? 'amount' : 'item' : event.shiftKey ? 'amount' : 'item');
        }
      }
    }} />;
}
function FeeActions({ data, node }: ICellRendererParams<FeeRow>) {
  const cells = useContext(FeeCells)!;
  if (!data || node.rowPinned) return null;
  if (data.kind === 'auto') return <span className="muted">自动项不可改</span>;
  const drafts = Object.values(cells.drafts).filter(d => d.row.id === data.id);
  return <div className="fee-row-actions">
    {drafts.length > 0 && <><Button size="small" disabled={cells.disabled || cells.busy} onMouseDown={e => e.preventDefault()} onClick={() => drafts.forEach(d => cells.save(data.id, d.field, true))}>保存</Button><Button size="small" disabled={cells.disabled || cells.busy} onMouseDown={e => e.preventDefault()} onClick={() => cells.cancel(data.id)}>取消修改</Button></>}
    <Button size="small" danger disabled={cells.disabled || cells.busy || drafts.length > 0} onClick={() => cells.remove(data)}>删除</Button>
  </div>;
}


export function FeeScope({ ym, project, me, blocked, active, status }: { ym: string; project: string; me: Identity | null; blocked: boolean; active: boolean; status: (ym: string, busy: boolean, dirty: boolean) => void }) {
  const writeAbort = useRef(new AbortController());
  useEffect(() => { writeAbort.current = new AbortController(); return () => writeAbort.current.abort(); }, []);
  const client = useQueryClient(), root = useRef<HTMLDivElement>(null), alive = useRef(true), lock = useRef(false), queue = useRef<string[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({}), [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState(''), [feedback, setFeedback] = useState(''), [deleting, setDeleting] = useState<FeeRow | null>(null), [batch, setBatch] = useState(false), [verified, setVerified] = useState(false);
  const queryKey = ['fees',ym,project];
  const query = useQuery({ queryKey, enabled: active && !blocked, queryFn: ({ signal }) => getFees(ym, project, signal) });
  const state = useRef({ drafts, active, blocked, uncertain, data: query.data }); state.current = { drafts, active, blocked, uncertain, data: query.data };
  function update(next: Record<string, Draft>) { state.current.drafts = next; setDrafts(next); }
  useEffect(() => { alive.current = true; return () => { alive.current = false; queue.current = []; }; }, []);
  useEffect(() => { if (!active || blocked) queue.current = []; }, [active, blocked]);
  const scopeName = `${ym} · ${query.data?.project_display ?? project}`;
  useHistoryGuard(`fees:${ym}:${project}`, () => lock.current ? '费用正在保存，请稍候。' : uncertain ? '费用保存结果待核实，请先核对。' : Object.keys(state.current.drafts).length || batch ? '费用有未保存输入，请先处理。' : '');
  async function reload() {
    await client.cancelQueries({ queryKey, exact: true });
    const data = await client.fetchQuery({ queryKey, staleTime: 0, queryFn: ({ signal }) => getFees(ym, project, signal) });
    // Other pages, including the existing three-sheet export, consume the saved facts.
    await client.invalidateQueries({ predicate: q => JSON.stringify(q.queryKey) !== JSON.stringify(queryKey) });
    return data;
  }
  function change(row: FeeRow, field: FeeField, value: string) {
    const key = keyOf(row.id, field), old = state.current.drafts[key];
    const next = { ...state.current.drafts, [key]: { row: old?.row ?? row, field, value, error: '' } };
    if (value === (old?.row ?? row)[field] && !lock.current) delete next[key];
    update(next);
  }
  async function drain() {
    if (lock.current || !state.current.active || state.current.blocked || state.current.uncertain || !me) return;
    const key = queue.current.shift(); if (!key) return;
    const draft = state.current.drafts[key]; if (!draft) { void drain(); return; }
    const row = state.current.data?.manuals.find(row => row.id === draft.row.id);
    if (!row) {
      const message = '原记录已不在当前结果中，请取消修改。';
      update({ ...state.current.drafts, [key]: { ...draft, error: message } }); setError(message); void drain(); return;
    }
    lock.current = true; setBusy(true); setError(''); setFeedback(''); let written = false;
    try {
      await feeWrite(draft.field === 'item' ? 'name' : 'amount', { ym, project, index: row.index, value: draft.value }, writeAbort.current.signal);
      written = true;
      if (!alive.current) return;
      const next = { ...state.current.drafts };
      if (next[key]?.value === draft.value) delete next[key];
      update(next); setFeedback(`${scopeName} · 已保存，正在核对合计…`);
      const data = await reload();
      if (!alive.current) return;
      const savedRow = data.manuals.find(row => row.id === draft.row.id);
      const remaining = { ...state.current.drafts };
      if (savedRow) for (const [k, d] of Object.entries(remaining)) if (d.row.id === savedRow.id) remaining[k] = { ...d, row: savedRow };
      update(remaining); setFeedback(`${scopeName} · 已保存，合计 ${money(data.total)}`);
    } catch (failure) {
      if (!alive.current) return;
      const message = failure instanceof Error ? failure.message : '保存失败，请重试。';
      if (written || uncertainWrite(failure)) { setUncertain(true); setVerified(false); state.current.uncertain = true; queue.current = []; setError(`${written ? '已保存，重读失败。' : '保存结果待核实。'}${message}请重读并核对，勿重复提交。`); }
      else { const next = { ...state.current.drafts }; if (next[key]) next[key] = { ...next[key], error: message }; update(next); setError(message); }
    } finally {
      lock.current = false; if (alive.current) { setBusy(false); void drain(); }
    }
  }
  function save(id: number, field: FeeField, retry = false) {
    const key = keyOf(id, field), draft = state.current.drafts[key];
    if (!draft || draft.error && !retry || !state.current.active || state.current.blocked || state.current.uncertain) return;
    if (!queue.current.includes(key)) queue.current.push(key); void drain();
  }
  async function structural(action: 'add' | 'delete') {
    if (lock.current || blocked || !active || !me || uncertain || Object.keys(state.current.drafts).length || query.isError || query.isFetching || !query.data?.can_edit) return;
    const row = deleting && state.current.data?.manuals.find(row => row.id === deleting.id);
    if (action === 'delete' && !row) { setDeleting(null); setError('这条手填项已不在当前结果中，请重读核对。'); return; }
    lock.current = true; setBusy(true); setError(''); setFeedback(''); let written = false;
    try {
      await feeWrite(action, { ym, project, ...(row ? { index: row.index } : {}) }, writeAbort.current.signal);
      written = true; if (!alive.current) return; setDeleting(null);
      const data = await reload(); if (alive.current) setFeedback(`${scopeName} · 已${action === 'add' ? '增加手填项' : '删除'}，合计 ${money(data.total)}`);
    } catch (failure) { if (alive.current) { setUncertain(written || uncertainWrite(failure)); setVerified(false); setError(`${written ? '已保存，重读失败。' : ''}${failure instanceof Error ? failure.message : '操作失败。'}`); } }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  async function reread() {
    if (lock.current || blocked || !active) return;
    try { await reload(); setVerified(true); setError(''); setFeedback(uncertain ? '已重读，请核对刚才的操作结果。' : '已重读，未保存输入仍保留。'); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '重读失败。'); }
  }
  const disabled = blocked || !active || !me || uncertain || !query.data?.can_edit || query.isError;
  const dirty = Object.keys(drafts).length > 0;
  useEffect(() => status(ym,busy || uncertain,dirty || batch), [status,ym,busy,uncertain,dirty,batch]);
  const closing = useDialogClose({ busy, dirty: false, close: () => setDeleting(null), active });
  const scale = Number(me?.ui_scale_css ?? 1);
  const columns = useMemo<ColDef<FeeRow>[]>(() => [
    { field: 'item', headerName: '数据项', pinned: 'left', ...contentWidth(220,480,scale,1), cellRenderer: FeeInput },
    { field: 'source', headerName: '来源', ...contentWidth(200,260,scale), cellRenderer: (p: ICellRendererParams<FeeRow>) => p.node.rowPinned ? '' : <Tag className="status-tag status-neutral">{p.data?.kind === 'auto' ? '系统生成 · CBS 安文费' : '手填'}</Tag> },
    { field: 'amount', headerName: '金额（元）', ...contentWidth(150,210,scale), cellClass: 'money', cellRenderer: FeeInput },
    { field: 'share', headerName: '占合计', ...fixedWidth(100,scale), cellClass: 'money' },
    { colId: 'actions', headerName: '操作', ...contentWidth(250,300,scale), cellRenderer: FeeActions },
  ], [scale]);
  const rows = useMemo(() => query.data ? [query.data.auto, ...query.data.manuals] : [], [query.data]);
  const totals = useMemo(() => query.data ? [{ ...query.data.auto, id: -1, item: '合计', source: '', amount: query.data.total, share: '' }] : [], [query.data]);
  return <>
    <div className="fee-toolbar"><div><Button disabled={disabled || busy || dirty || query.isFetching} onClick={() => void structural('add')}>增加手填项</Button>
      <Button disabled={disabled || busy || dirty || query.isFetching || !query.data?.manuals.length} title={!query.data?.manuals.length ? '先增加手填项' : dirty ? '先处理未保存输入' : ''} onClick={() => setBatch(true)}>批量录入（按月）…</Button></div>
      <span className="muted">随逐月欠款台账导出 · 特殊费用月报表</span>
    </div>
    {(feedback || busy) && <p role="status" className="fee-feedback">{busy ? `${scopeName} · 正在保存…` : feedback}</p>}
    {(error || query.isError) && <p className="notice" role="alert">{error || query.error?.message}<Button disabled={busy || blocked} onClick={() => void reread()}>重读核对</Button></p>}
    {uncertain && <p className="notice" role="alert">核对结果后再继续。<Button disabled={!verified || busy || query.isFetching || query.isError} onClick={() => {
      update(Object.fromEntries(Object.entries(state.current.drafts).map(([key,d]) => { const row = query.data?.manuals.find(r => r.id === d.row.id); return [key,row ? { ...d,row,error:'' } : { ...d,error:'原记录已删除，请取消修改。' }]; })));
      setUncertain(false); setError(''); setFeedback('已确认，请核对保留输入后再保存。');
    }}>已核对，保留输入继续</Button></p>}
    {Object.values(drafts).filter(d => d.error).map(d => <p className="notice" role="alert" key={keyOf(d.row.id,d.field)}>{d.row.item || '未命名'} · {d.field === 'item' ? '项名' : '金额'}：{d.error}
      <Button disabled={busy || blocked || uncertain} onMouseDown={e => e.preventDefault()} onClick={() => { const next = { ...state.current.drafts }; delete next[keyOf(d.row.id,d.field)]; update(next); }}>取消这项修改</Button></p>)}
    {query.isPending ? <p role="status">正在读取费用…</p> : query.data && <FeeCells.Provider value={{ drafts, disabled, busy, change, save, remove: setDeleting,
      focus: (id,field) => requestAnimationFrame(() => root.current?.querySelector<HTMLInputElement>(`[row-id="${id}"] [col-id="${field}"] input`)?.focus()),
      cancel: id => { update(Object.fromEntries(Object.entries(state.current.drafts).filter(([,d]) => d.row.id !== id))); } }}>
      <div ref={root} className="fees-grid"><AgGridReact<FeeRow> theme={gridTheme} domLayout="autoHeight" rowData={rows} columnDefs={columns} pinnedBottomRowData={totals}
        getRowId={p => String(p.data.id)} defaultColDef={{ resizable: true, sortable: false, suppressMovable: true, suppressKeyboardEvent: e => e.event.target instanceof HTMLInputElement }} rowHeight={pageGridGeometry(scale).rowHeight} headerHeight={pageGridGeometry(scale).headerHeight}
        suppressScrollOnNewData suppressColumnVirtualisation onGridReady={e => fitGridColumns(e.api,root.current,true)} onFirstDataRendered={e => fitGridColumns(e.api,root.current,true)} onGridSizeChanged={e => fitGridColumns(e.api,root.current)} /></div>
    </FeeCells.Provider>}
    {deleting && <BusinessModal open={active && !blocked} requestClose={closing.requestClose} className="fee-delete-dialog" titleId="fee-delete-title"><DialogContents title="删除手填项" titleId="fee-delete-title" closing={closing}>
      <p>{scopeName}</p><p>删除「{deleting.item || '未命名'}」 {money(deleting.amount)} 元？</p>{error && <p role="alert" className="notice">{error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button danger disabled={disabled || busy} onClick={() => void structural('delete')}>删除</Button></div>
    </DialogContents></BusinessModal>}
    {batch && query.data && <FeeBatch me={me} ym={ym} project={project} display={query.data.project_display} rows={query.data.manuals} paused={blocked || !active} close={() => setBatch(false)} saved={reload} />}
  </>;
}
