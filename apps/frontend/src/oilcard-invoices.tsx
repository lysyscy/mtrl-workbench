import Button from 'antd/es/button';
import Dropdown from 'antd/es/dropdown';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { ApiError, cents, decimal, money, projectLabel, requestFile, requestJson } from './api';
import type { Identity, Project } from './api';
import { BusinessGrid } from './business-grid';
import { contentWidth, fullTextWidth } from './grid';
import { valueFilterColumn } from './grid-value-filter';
import type { ValueFilterOptions } from './grid-value-filter';
import { valueFilterPasses } from './grid-value-filter-model';
import type { ValueFilterModel } from './grid-value-filter-model';
import { readHistory } from './history';
import type { OilArchives } from './oilcard-api';
import { getOilReconciliation } from './oilcard-ledger-api';
import { changeOilInvoice, getOilInvoices, readOilReceipt, receiveOilInvoice, saveOilInvoiceRemark } from './oilcard-invoice-api';
import type { OilInvoice, OilInvoices } from './oilcard-invoice-api';
import { OilInvoiceDialog } from './oilcard-invoice-dialogs';
import type { InvoiceAction } from './oilcard-invoice-dialogs';
import { OilReceiveDialog } from './oilcard-receive';
import { useCellSaveQueue } from './use-cell-save';

type Row = OilInvoice & { project: string; account: string; total?: boolean };
type Draft = { id: number; field: 'remark' | 'allocation'; original: string; value: string; project_id: number; account_id: number; error: string };
const InvoiceCells = createContext<{ drafts: Record<string, Draft>; disabled: boolean; archives: OilArchives; projects: Project[]; change: (row: Row, field: 'remark' | 'project_id' | 'account_id', value: string) => void; save: (key: string) => void } | null>(null);
function RemarkCell({ data: row, node }: ICellRendererParams<Row>) {
  const state = useContext(InvoiceCells)!;
  if (!row || node.rowPinned) return '';
  const key = `remark:${row.id}`, draft = state.drafts[key];
  return <Input aria-label={`发票备注：${row.invoice_no || `待核 #${row.id}`}`} className="record-value" value={draft?.value ?? row.remark} disabled={state.disabled} status={draft?.error ? 'error' : ''} onChange={e => state.change(row, 'remark', e.target.value)} onBlur={() => state.save(key)} onKeyDown={e => { if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }} />;
}

function AttributionCell({ data: row, node, colDef }: ICellRendererParams<Row>) {
  const state = useContext(InvoiceCells)!;
  if (!row || node.rowPinned) return '';
  const field = colDef?.field === 'project' ? 'project_id' : 'account_id', saved = row.allocations[0];
  if (row.allocations.length > 1) return row[field === 'project_id' ? 'project' : 'account'];
  const draft = state.drafts[`allocation:${row.id}`], project = draft?.project_id ?? saved?.project_id ?? 0, account = draft?.account_id ?? saved?.account_id ?? 0;
  const canAssign = row.status !== 'voided' && row.invoice_no && row.invoice_date && row.amount !== null && (row.kind === 'credit' || cents(row.amount) > 0n);
  const options = field === 'project_id' ? state.projects.filter(p => p.project_type !== 'shell').map(p => ({ value: p.id, label: projectLabel(p) })) : state.archives.accounts.filter(a => a.project_id === project || a.id === account).map(a => ({ value: a.id, label: `${a.name}${a.status === 'archived' ? '（归档）' : ''}` }));
  return <Select aria-label={`${field === 'project_id' ? '发票项目' : '发票账户'}：${row.invoice_no || `待核 #${row.id}`}`} value={(field === 'project_id' ? project : account) || null} disabled={state.disabled || !canAssign} placeholder={canAssign ? '请选择' : '先核对票面'} options={options} showSearch={{ optionFilterProp: 'label' }} status={draft?.error ? 'error' : ''} onChange={value => state.change(row, field, String(value))} />;
}
const pairKey = (row: OilInvoice) => row.allocations.length === 1 ? `${row.allocations[0]!.project_id}:${row.allocations[0]!.account_id}` : '';

function sameAttributionValue(a: Row | undefined, b: Row | undefined, field: 'project' | 'account') {
  if (!a || !b) return a === b;
  return a[field] === b[field] && a.status === b.status && a.kind === b.kind &&
    a.invoice_no === b.invoice_no && a.invoice_date === b.invoice_date && a.amount === b.amount &&
    a.allocations.length === b.allocations.length && pairKey(a) === pairKey(b);
}

export function OilInvoiceSheet({ me, archives, projects, active, blocked, scale, locked, onWriteLock, onUncertain }: {
  me: Identity | null; archives: OilArchives; projects: Project[]; active: boolean; blocked: boolean; scale: number; locked: boolean;
  onWriteLock: (value: boolean) => void; onUncertain: (value: boolean) => void;
}) {
  const client = useQueryClient(), input = useRef<HTMLInputElement | null>(null);
  const [selected, setSelected] = useState(0), [originalId, setOriginalId] = useState(0), [preparing, setPreparing] = useState(false);
  const [filters, setFilters] = useState<Record<string, ValueFilterModel>>({}), [result, setResult] = useState('');
  const [downloadError, setDownloadError] = useState(''), [downloading, setDownloading] = useState(false);
  const [dialog, setDialog] = useState<{ mode: InvoiceAction; row: OilInvoice; sourceId: number | null } | null>(null);
  const [receiveOpen, setReceiveOpen] = useState(false), [batchLocked, setBatchLocked] = useState(false), [batchUncertain, setBatchUncertain] = useState(false);
  const downloadRequest = useRef<AbortController | null>(null), alive = useRef(true), upload = useRef<{ file: File; digest: string } | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; downloadRequest.current?.abort(); }; }, []);
  useEffect(() => { if (!active || blocked) downloadRequest.current?.abort(); }, [active, blocked]);
  const query = useQuery({ queryKey: ['oilcard-invoices'], enabled: active && !blocked, queryFn: ({ signal }) => getOilInvoices(signal) });
  const current = useRef(query.data); current.current = query.data;
  const saves = useCellSaveQueue<Draft, OilInvoices>({
    enabled: active && !blocked && Boolean(me), canWrite: Boolean(query.data && !query.isError && !locked), read: reload,
    write: async (draft, signal) => {
      const row = current.current?.invoices.find(r => r.id === draft.id);
      if (!row || (draft.field === 'remark' ? row.remark : pairKey(row)) !== draft.original) throw new ApiError('发票字段已变化，请重读核对保留输入。', 409);
      if (draft.field === 'remark') await saveOilInvoiceRemark(row, draft.value, signal);
      else await changeOilInvoice(row, 'allocations', { allocations: [{ project_id: draft.project_id, account_id: draft.account_id, amount: row.amount }] }, signal);
    },
    acknowledge: (present, submitted) => present.value === submitted.value && present.project_id === submitted.project_id && present.account_id === submitted.account_id ? undefined : { ...present, original: submitted.field === 'remark' ? submitted.value : `${submitted.project_id}:${submitted.account_id}` },
    saved: () => '',
  }, { key: 'oilcard-invoices', label: '油卡发票', pending: preparing || Boolean(dialog) || receiveOpen });
  async function reload() {
    await client.invalidateQueries({ refetchType: 'none' });
    await client.cancelQueries({ queryKey: ['oilcard-invoices'], exact: true });
    const data = await client.fetchQuery({ queryKey: ['oilcard-invoices'], staleTime: 0, queryFn: ({ signal }) => getOilInvoices(signal) });
    current.current = data;
    if (upload.current) {
      const received = await readOilReceipt(upload.current.digest);
      const invoice = data.invoices.find(row => row.originals.some(o => o.sha256 === upload.current?.digest));
      const original = invoice?.originals.find(o => o.sha256 === upload.current?.digest);
      if (received !== Boolean(original)) throw new ApiError('收票回执与台账尚未一致，请重读核对。');
      setResult(received ? original?.resolution || (original?.outcome === 'conflict' ? original.reason : invoice?.status === 'registered' ? '原件已接收并登记。' : invoice?.reason || '原件已接收。') : '本次原件尚未登记，可再次收票。');
    }
    await client.fetchQuery({ queryKey: ['oilcard-reconciliation'], staleTime: 0, queryFn: ({ signal }) => getOilReconciliation(signal) });
    if (me) await client.fetchQuery({ queryKey: ['history', `${me.id}:${me.account}`], staleTime: 0, queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
    return data;
  }
  const { drafts, busy, uncertain, verified, error } = saves;
  useEffect(() => { onWriteLock(busy || uncertain || preparing || batchLocked); }, [busy, uncertain, preparing, batchLocked, onWriteLock]);
  useEffect(() => { onUncertain(uncertain || batchUncertain); }, [uncertain, batchUncertain, onUncertain]);
  const receiveDisabled = blocked || !active || !me || locked || uncertain || preparing || !query.data || query.isError;
  const disabled = receiveDisabled || batchLocked;
  const structuralDisabled = disabled || busy || Object.keys(drafts).length > 0;
  const row = query.data?.invoices.find(item => item.id === selected);
  const original = row?.originals.find(o => o.id === originalId) ?? row?.originals[0];
  const rows = useMemo<Row[]>(() => (query.data?.invoices ?? []).map(row => ({ ...row,
    project: [...new Set(row.allocations.map(a => { const p = projects.find(p => p.id === a.project_id); return p ? projectLabel(p) : `项目 #${a.project_id}`; }))].join('、') || '待确认',
    account: row.allocations.map(a => archives.accounts.find(account => account.id === a.account_id)?.name || `账户 #${a.account_id}`).join('、') || '待确认',
  })), [query.data, archives, projects]);
  const draftRef = useRef(drafts); draftRef.current = drafts;
  const filterOptions = useMemo<Record<string, ValueFilterOptions<Row>>>(() => Object.fromEntries(['invoice_date', 'invoice_no', 'project', 'account', 'amount', 'remark'].map(field => [field, {
    kind: field === 'invoice_date' ? 'date' : field === 'amount' ? 'number' : 'text',
    value: (row: Row) => row[field as keyof Row] as string | null,
    keepVisible: (row: Row) => Boolean(draftRef.current[`remark:${row.id}`] || draftRef.current[`allocation:${row.id}`]),
    ...(field === 'amount' ? { format: (value: string | number) => money(String(value)) } : {}),
  } as ValueFilterOptions<Row>])), []);
  const total = useMemo(() => decimal(rows.filter(row => row.status === 'registered' && Object.entries(filters).every(([field, model]) => {
    const options = filterOptions[field]; return !options || valueFilterPasses(model, options.value(row), options.kind);
  })).reduce((sum, row) => sum + cents(row.amount!), 0n)), [rows, filters, filterOptions]);
  const amountWidth = fullTextWidth([money(query.data?.total_amount ?? '0.00'), ...rows.map(row => row.amount === null ? '' : money(row.amount))], scale).minWidth;
  const columns = useMemo<ColDef<Row>[]>(() => ([
    { field: 'invoice_date', headerName: '开票日期', ...contentWidth(120, 180, scale), valueFormatter: p => p.node?.rowPinned ? '合计' : p.value || '待核' },
    // Renderer metadata is part of the native value comparison. A plain field
    // value would leave these cells stale when status changes without new text.
    { field: 'invoice_no', headerName: '发票号', ...contentWidth(210, 280, scale),
      valueGetter: p => p.data, valueFormatter: p => p.value?.invoice_no || '',
      equals: (a: Row | undefined, b: Row | undefined) => a?.invoice_no === b?.invoice_no && a?.status === b?.status && a?.kind === b?.kind,
      cellRenderer: ({ data, node }: ICellRendererParams<Row>) => !data || node.rowPinned ? '' : <span>{data.invoice_no || '票号待核'}{(data.status === 'pending' || data.status === 'voided' || data.kind === 'credit') && <small className="muted">（{data.status === 'pending' ? '待确认' : data.status === 'voided' ? '作废' : '红冲'}）</small>}</span> },
    { field: 'project', headerName: '项目', ...contentWidth(160, 300, scale, 1), valueGetter: p => p.data,
      valueFormatter: p => p.value?.project || '', equals: (a, b) => sameAttributionValue(a, b, 'project'), cellRenderer: AttributionCell },
    { field: 'account', headerName: '用卡账户', ...contentWidth(150, 260, scale, 1), valueGetter: p => p.data,
      valueFormatter: p => p.value?.account || '', equals: (a, b) => sameAttributionValue(a, b, 'account'), cellRenderer: AttributionCell },
    { field: 'amount', headerName: '价税合计', cellClass: 'money', ...contentWidth(Math.max(130, amountWidth / scale), 200, scale), valueFormatter: p => p.value === null || p.value === undefined ? '待核' : money(p.value) },
    { field: 'remark', headerName: '备注', ...contentWidth(160, 360, scale, 1), valueGetter: p => p.data,
      valueFormatter: p => p.value?.remark || '', equals: (a: Row | undefined, b: Row | undefined) => a?.remark === b?.remark && a?.invoice_no === b?.invoice_no, cellRenderer: RemarkCell },
  ] satisfies ColDef<Row>[]).map(column => valueFilterColumn<Row>(column, filterOptions[column.field!]!)), [scale, amountWidth, filterOptions]);
  const totals = useMemo<Row[]>(() => query.data ? [{ id: -1, invoice_no: null, invoice_date: null, amount: total, card_no: null, status: 'registered', kind: 'normal', related_invoice_id: null, void_date: null, change_note: '', reason: '', remark: '', version: '', allocations: [], originals: [], project: '', account: '', total: true }] : [], [query.data, total]);
  function change(row: Row, field: 'remark' | 'project_id' | 'account_id', value: string) {
    if (disabled) return;
    const actual = current.current?.invoices.find(r => r.id === row.id) ?? row, kind = field === 'remark' ? 'remark' : 'allocation', key = `${kind}:${row.id}`;
    const original = kind === 'remark' ? actual.remark : pairKey(actual);
    saves.update((ds, writing) => {
      const next = { ...ds }, existing = ds[key], saved = actual.allocations[0];
      const draft: Draft = existing ? { ...existing, error: '' } : { id: row.id, field: kind, original, value: actual.remark, project_id: saved?.project_id ?? 0, account_id: saved?.account_id ?? 0, error: '' };
      if (field === 'remark') draft.value = value;
      else if (field === 'project_id') { draft.project_id = Number(value); const candidates = archives.accounts.filter(a => a.project_id === draft.project_id); draft.account_id = candidates.length === 1 ? candidates[0]!.id : 0; }
      else draft.account_id = Number(value);
      if ((kind === 'remark' ? draft.value : `${draft.project_id}:${draft.account_id}`) === original && !writing) delete next[key]; else next[key] = draft;
      draftRef.current = next; return next;
    });
    const draft = draftRef.current[key];
    if (kind === 'allocation' && draft?.project_id && draft.account_id) saves.save(key);
  }
  async function receive(file: File) {
    if (structuralDisabled) return;
    setResult(''); saves.clearFeedback();
    if (file.size > 20 * 1024 * 1024) { setResult('请选择不超过20 MiB的PDF原件。'); return; }
    setPreparing(true);
    try {
      const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))].map(n => n.toString(16).padStart(2, '0')).join('');
      if (!alive.current) return;
      upload.current = { file, digest };
      const outcome = await saves.run(async signal => {
        const result = await receiveOilInvoice(file, digest, signal);
        setSelected(result.item.id); setOriginalId(result.original.id);
        setResult(result.item.originals.find(o => o.id === result.original.id)?.resolution || (result.original.outcome === 'conflict' ? result.original.reason : result.item.status === 'registered' ? '原件已接收并登记。' : result.item.reason));
      }, () => '', '收票：');
      if (outcome !== 'uncertain') upload.current = null;
    } catch (failure) { if (alive.current) setResult(failure instanceof Error ? failure.message : '原件读取失败，请重新选择PDF。'); }
    finally { if (alive.current) setPreparing(false); }
  }
  async function download(path: string) {
    if (disabled || busy || downloading) return;
    const controller = new AbortController(); downloadRequest.current = controller; setDownloading(true); setDownloadError('');
    try {
      const file = await requestFile(path, controller.signal);
      if (controller.signal.aborted || !alive.current) return;
      const url = URL.createObjectURL(file.blob), link = document.createElement('a'); link.href = url; link.download = file.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) { if (!controller.signal.aborted && alive.current) setDownloadError(failure instanceof Error ? failure.message : '文件下载失败，请重试。'); }
    finally { if (alive.current) setDownloading(false); }
  }
  function open(mode: InvoiceAction, sourceId: number | null = null) { if (!row || structuralDisabled) return; saves.clearFeedback(); setResult(''); setDialog({ mode, row, sourceId }); }
  const pending = rows.filter(row => row.status === 'pending').length, conflicts = rows.reduce((n, r) => n + r.originals.filter(o => o.outcome === 'conflict' && !o.resolution).length, 0);
  return <section className="oilcard-ledger-pane" aria-label="发票台账">
    <div data-page-chrome className="oilcard-toolbar"><h2>发票</h2><div><input ref={input} type="file" accept="application/pdf,.pdf" hidden aria-label="上传发票PDF" onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void receive(file); }} />
      <Dropdown trigger={['click']} menu={{ items: [{ key: 'links', label: '交付链接收票' }, { key: 'pdf', label: '上传PDF' }], onClick: ({ key }) => { if (!structuralDisabled) { if (key === 'pdf') input.current?.click(); else setReceiveOpen(true); } } }}><Button type="primary" disabled={structuralDisabled} loading={busy || preparing}>收票</Button></Dropdown>
      {row && original && <><Button href={`/api/m13/invoices/originals/${original.id}`} target="_blank" rel="noopener noreferrer" disabled={disabled}>查看发票</Button><Button disabled={disabled || busy || downloading} onClick={() => void download(`/api/m13/invoices/originals/${original.id}?download=true`)}>下载原件</Button></>}
      {row && row.status !== 'voided' && <><Button disabled={structuralDisabled} onClick={() => open(row.kind === 'credit' ? 'credit' : 'correct')}>{row.kind === 'credit' ? '更正红冲信息' : '更正票面信息'}</Button><Button disabled={structuralDisabled || !row.invoice_no || !row.invoice_date || row.amount === null || row.kind === 'normal' && cents(row.amount) <= 0n} onClick={() => open('allocate')}>{row.allocations.length > 1 ? '更改整体分配' : '分给多个项目'}</Button></>}
      {row && row.status !== 'voided' && row.kind === 'normal' && <Button disabled={structuralDisabled} onClick={() => open('credit')}>登记红冲</Button>}
      {row?.status === 'registered' && row.kind === 'normal' && <Button disabled={structuralDisabled} onClick={() => open('void')}>登记作废</Button>}
      <Button disabled={disabled || busy || downloading} onClick={() => void download('/api/m13/invoices/export')}>导出全部已保存发票</Button>
      <Button disabled={blocked || busy || !Object.keys(drafts).length} onMouseDown={e => e.preventDefault()} onClick={() => saves.update(() => ({}))}>取消未保存修改</Button></div></div>
    {(pending > 0 || conflicts > 0) && <p className="oilcard-pending-hint">{pending > 0 && `${pending}张待确认，尚未计入开票合计。`}{conflicts > 0 && `${conflicts}份同票号冲突原件待核，原已确认金额保持。`}</p>}
    {(error || query.isError) && <p className="notice" role="alert">{error || query.error?.message}<Button disabled={blocked || busy} onClick={() => void saves.reread()}>重读核对</Button></p>}
    {result && <p className="oilcard-pending-hint" role="status">{result}</p>}
    {downloadError && <p className="notice" role="alert">{downloadError}</p>}
    {(uncertain || verified && Object.keys(drafts).length > 0) && <p className="notice" role="alert">{uncertain ? '请先重读核对刚才的发票保存结果。' : '已读取当前发票，请核对保留输入。'}<Button disabled={!verified || blocked || busy} onClick={() => { saves.confirm(); upload.current = null; saves.update(ds => Object.fromEntries(Object.entries(ds).flatMap(([key, draft]) => { const actual = current.current?.invoices.find(r => r.id === draft.id); const original = actual ? draft.field === 'remark' ? actual.remark : pairKey(actual) : draft.original; return original === (draft.field === 'remark' ? draft.value : `${draft.project_id}:${draft.account_id}`) ? [] : [[key, { ...draft, original, error: '' }]]; }))); }}>已核对，保留输入继续</Button></p>}
    {Object.entries(drafts).filter(([, d]) => d.error).map(([key, d]) => <p className="oilcard-draft-error" key={key}>发票 #{d.id}：{d.error}<Button disabled={disabled || busy} onClick={() => saves.save(key, true)}>重试保存</Button></p>)}
    {query.isPending ? <p role="status" data-page-loading>正在读取发票台账…</p> : query.data && <InvoiceCells.Provider value={{ drafts, disabled, archives, projects, change, save: key => saves.save(key) }}><div onContextMenuCapture={e => { if (e.target instanceof Element && e.target.closest('input,.ant-select')) e.stopPropagation(); }}><Dropdown trigger={['contextMenu']} menu={{ items: [{ key: 'view', label: '查看发票', disabled: disabled || !original }, { key: 'download', label: '下载原件', disabled: disabled || !original }, { key: 'correct', label: '更正票面信息', disabled: structuralDisabled || !row || row.status === 'voided' }, { key: 'allocate', label: '更改整体分配', disabled: structuralDisabled || !row || row.status === 'voided' }, { key: 'credit', label: row?.kind === 'credit' ? '更正红冲信息' : '登记红冲', disabled: structuralDisabled || !row || row.status === 'voided' }, { key: 'void', label: '登记作废', disabled: structuralDisabled || row?.status !== 'registered' || row.kind !== 'normal' }], onClick: ({ key }) => { if (original && !disabled) { if (key === 'view') window.open(`/api/m13/invoices/originals/${original.id}`, '_blank', 'noopener'); else if (key === 'download') void download(`/api/m13/invoices/originals/${original.id}?download=true`); else open(key === 'correct' && row?.kind === 'credit' ? 'credit' : key as InvoiceAction); } } }}><div><BusinessGrid table="oilcard-invoices" label="油卡发票台账" rows={rows} columns={columns} totals={totals} rowId={row => String(row.id)} scale={scale} domLayout="normal" style={{ height: '62dvh', minHeight: '300px' }} grid={{ enableFilterHandlers: true, popupParent: document.body, onFilterChanged: e => setFilters(e.api.getFilterModel() as Record<string, ValueFilterModel>), onRowClicked: e => { if (e.data && !e.node.rowPinned) { setSelected(e.data.id); setOriginalId(0); } }, onCellContextMenu: e => { if (e.data && !e.node.rowPinned) { setSelected(e.data.id); setOriginalId(0); } }, rowClassRules: { 'oilcard-selected': p => p.data?.id === selected } }} /></div></Dropdown></div></InvoiceCells.Provider>}
    {row && <div className="oilcard-invoice-detail">{row.reason && <p className="notice">{row.reason}</p>}{row.kind === 'credit' && <p>红冲关联原票：{query.data?.invoices.find(r => r.id === row.related_invoice_id)?.invoice_no || `#${row.related_invoice_id}`}</p>}{row.change_note && <p>{row.void_date ? `作废日期 ${row.void_date}，` : ''}{row.change_note}</p>}{row.originals.length > 1 && <label>原件<Select aria-label="选择发票原件" value={original?.id ?? null} options={row.originals.map((o, i) => ({ value: o.id, label: `${i === 0 ? '主原件' : o.outcome === 'conflict' ? o.resolution ? '已核冲突原件' : '冲突原件待核' : '补档原件'} #${o.id}` }))} onChange={value => setOriginalId(value)} /></label>}{original?.outcome === 'conflict' && <><p className={original.resolution ? '' : 'notice'}>{original.resolution || original.reason}</p>{!original.resolution && <div className="oilcard-toolbar"><Button disabled={structuralDisabled} onClick={() => open('resolve', original.id)}>确认保留原票</Button><Button disabled={structuralDisabled || row.status === 'voided'} onClick={() => open(row.kind === 'credit' || original.recognized.amount !== null && cents(original.recognized.amount) < 0n ? 'credit' : 'correct', original.id)}>采用此原件更正</Button></div>}</>}</div>}
    {dialog && <OilInvoiceDialog row={dialog.row} mode={dialog.mode} source={dialog.sourceId ? dialog.row.originals.find(o => o.id === dialog.sourceId) ?? null : null} all={query.data?.invoices ?? []} archives={archives} projects={projects} disabled={disabled} busy={busy} error={error} close={() => setDialog(null)} submit={async fields => {
      const action = dialog.mode === 'allocate' ? 'allocations' : dialog.mode === 'resolve' ? `originals/${dialog.sourceId!}/resolve` as const : dialog.mode;
      const outcome = await saves.run(async signal => { await changeOilInvoice(dialog.row, action, fields, signal); }, () => '', `发票 ${dialog.row.invoice_no || dialog.row.id}：`);
      if (outcome === 'saved' || outcome === 'uncertain') setDialog(null);
    }} />}
    {receiveOpen && <OilReceiveDialog active={active} disabled={receiveDisabled || busy} scale={scale} close={() => setReceiveOpen(false)} onUpdated={reload} onLock={setBatchLocked} onUncertain={setBatchUncertain} onOpenInvoice={item => {
      void reload().then(() => {
        const actual = current.current?.invoices.find(row => row.id === item.invoice_id);
        if (!actual) throw new ApiError('发票尚未读到，请重新读取核对。');
        setSelected(actual.id); setOriginalId(item.original_id ?? 0);
        if (actual.status === 'pending') setDialog({ mode: actual.kind === 'credit' || actual.amount !== null && cents(actual.amount) < 0n ? 'credit' : 'correct', row: actual, sourceId: null });
      }).catch(failure => setDownloadError(failure instanceof Error ? failure.message : '发票读取失败，请重试。'));
    }} />}
  </section>;
}
