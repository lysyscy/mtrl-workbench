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
import { getOilInvoices, readOilReceipt, receiveOilInvoice, saveOilInvoiceRemark } from './oilcard-invoice-api';
import type { OilInvoice, OilInvoices } from './oilcard-invoice-api';
import { useCellSaveQueue } from './use-cell-save';

type Row = OilInvoice & { project: string; account: string; total?: boolean };
type Draft = { id: number; original: string; value: string; error: string };
const InvoiceCells = createContext<{ drafts: Record<string, Draft>; disabled: boolean; change: (row: Row, value: string) => void; save: (id: number) => void } | null>(null);
function RemarkCell({ data: row, node }: ICellRendererParams<Row>) {
  const state = useContext(InvoiceCells)!;
  if (!row || node.rowPinned) return '';
  const draft = state.drafts[String(row.id)];
  return <Input aria-label={`发票备注：${row.invoice_no || `待核 #${row.id}`}`} className="record-value" value={draft?.value ?? row.remark} disabled={state.disabled} status={draft?.error ? 'error' : ''} onChange={e => state.change(row, e.target.value)} onBlur={() => state.save(row.id)} onKeyDown={e => { if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }} />;
}

export function OilInvoiceSheet({ me, archives, projects, active, blocked, scale, locked, onWriteLock, onUncertain }: {
  me: Identity | null; archives: OilArchives; projects: Project[]; active: boolean; blocked: boolean; scale: number; locked: boolean;
  onWriteLock: (value: boolean) => void; onUncertain: (value: boolean) => void;
}) {
  const client = useQueryClient(), input = useRef<HTMLInputElement | null>(null);
  const [selected, setSelected] = useState(0), [originalId, setOriginalId] = useState(0), [preparing, setPreparing] = useState(false);
  const [filters, setFilters] = useState<Record<string, ValueFilterModel>>({}), [result, setResult] = useState('');
  const [downloadError, setDownloadError] = useState(''), [downloading, setDownloading] = useState(false);
  const downloadRequest = useRef<AbortController | null>(null), alive = useRef(true), upload = useRef<{ file: File; digest: string } | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; downloadRequest.current?.abort(); }; }, []);
  useEffect(() => { if (!active || blocked) downloadRequest.current?.abort(); }, [active, blocked]);
  const query = useQuery({ queryKey: ['oilcard-invoices'], enabled: active && !blocked, queryFn: ({ signal }) => getOilInvoices(signal) });
  const current = useRef(query.data); current.current = query.data;
  const saves = useCellSaveQueue<Draft, OilInvoices>({
    enabled: active && !blocked && Boolean(me), canWrite: Boolean(query.data && !query.isError && !locked), read: reload,
    write: async (draft, signal) => {
      const row = current.current?.invoices.find(r => r.id === draft.id);
      if (!row || row.remark !== draft.original) throw new ApiError('发票备注已变化，请重读核对保留输入。', 409);
      await saveOilInvoiceRemark(row, draft.value, signal);
    },
    acknowledge: (present, submitted) => present.value === submitted.value ? undefined : { ...present, original: submitted.value },
    saved: () => '',
  }, { key: 'oilcard-invoices', label: '油卡发票', pending: preparing });
  async function reload() {
    await client.invalidateQueries({ refetchType: 'none' });
    await client.cancelQueries({ queryKey: ['oilcard-invoices'], exact: true });
    const data = await client.fetchQuery({ queryKey: ['oilcard-invoices'], staleTime: 0, queryFn: ({ signal }) => getOilInvoices(signal) });
    current.current = data;
    if (upload.current) {
      const received = await readOilReceipt(upload.current.digest);
      const original = data.invoices.flatMap(row => row.originals).find(o => o.sha256 === upload.current?.digest);
      if (received !== Boolean(original)) throw new ApiError('收票回执与台账尚未一致，请重读核对。');
      setResult(received ? original?.reason || '原件已接收，请核对发票登记结果。' : '本次原件尚未登记，可再次收票。');
    }
    await client.fetchQuery({ queryKey: ['oilcard-reconciliation'], staleTime: 0, queryFn: ({ signal }) => getOilReconciliation(signal) });
    if (me) await client.fetchQuery({ queryKey: ['history', `${me.id}:${me.account}`], staleTime: 0, queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
    return data;
  }
  const { drafts, busy, uncertain, verified, error } = saves;
  useEffect(() => { onWriteLock(busy || uncertain || preparing); }, [busy, uncertain, preparing, onWriteLock]);
  useEffect(() => { onUncertain(uncertain); }, [uncertain, onUncertain]);
  const disabled = blocked || !active || !me || locked || uncertain || preparing || !query.data || query.isError;
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
    keepVisible: (row: Row) => Boolean(draftRef.current[String(row.id)]),
    ...(field === 'amount' ? { format: (value: string | number) => money(String(value)) } : {}),
  } as ValueFilterOptions<Row>])), []);
  const total = useMemo(() => decimal(rows.filter(row => row.status === 'registered' && Object.entries(filters).every(([field, model]) => {
    const options = filterOptions[field]; return !options || valueFilterPasses(model, options.value(row), options.kind);
  })).reduce((sum, row) => sum + cents(row.amount!), 0n)), [rows, filters, filterOptions]);
  const amountWidth = fullTextWidth([money(query.data?.total_amount ?? '0.00'), ...rows.map(row => row.amount === null ? '' : money(row.amount))], scale).minWidth;
  const columns = useMemo<ColDef<Row>[]>(() => ([
    { field: 'invoice_date', headerName: '开票日期', ...contentWidth(120, 180, scale), valueFormatter: p => p.node?.rowPinned ? '合计' : p.value || '待核' },
    { field: 'invoice_no', headerName: '发票号', ...contentWidth(210, 280, scale), cellRenderer: ({ data, node }: ICellRendererParams<Row>) => !data || node.rowPinned ? '' : <span>{data.invoice_no || '票号待核'}{data.status === 'pending' && <small className="muted">（待确认）</small>}</span> },
    { field: 'project', headerName: '项目', ...contentWidth(160, 300, scale, 1) },
    { field: 'account', headerName: '用卡账户', ...contentWidth(150, 260, scale, 1) },
    { field: 'amount', headerName: '价税合计', cellClass: 'money', ...contentWidth(Math.max(130, amountWidth / scale), 200, scale), valueFormatter: p => p.value === null || p.value === undefined ? '待核' : money(p.value) },
    { field: 'remark', headerName: '备注', ...contentWidth(160, 360, scale, 1), cellRenderer: RemarkCell },
  ] satisfies ColDef<Row>[]).map(column => valueFilterColumn<Row>(column, filterOptions[column.field!]!)), [scale, amountWidth, filterOptions]);
  const totals = useMemo<Row[]>(() => query.data ? [{ id: -1, invoice_no: null, invoice_date: null, amount: total, card_no: null, status: 'registered', reason: '', remark: '', version: '', allocations: [], originals: [], project: '', account: '', total: true }] : [], [query.data, total]);
  function change(row: Row, value: string) {
    if (disabled) return;
    const original = current.current?.invoices.find(r => r.id === row.id)?.remark ?? row.remark, key = String(row.id);
    saves.update((ds, writing) => { const next = { ...ds }; if (value === original && !writing) delete next[key]; else next[key] = { id: row.id, original: ds[key]?.original ?? original, value, error: '' }; return next; });
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
        setResult(result.original.reason || (result.item.status === 'registered' ? '原件已接收并登记。' : result.item.reason));
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
  const pending = rows.filter(row => row.status === 'pending').length, conflicts = rows.reduce((n, r) => n + r.originals.filter(o => o.outcome === 'conflict').length, 0);
  return <section className="oilcard-ledger-pane" aria-label="发票台账">
    <div data-page-chrome className="oilcard-toolbar"><h2>发票</h2><div><input ref={input} type="file" accept="application/pdf,.pdf" hidden aria-label="上传发票PDF" onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void receive(file); }} />
      <Button type="primary" disabled={structuralDisabled} loading={busy || preparing} onClick={() => input.current?.click()}>收票</Button>
      {row && original && <><Button href={`/api/m13/invoices/originals/${original.id}`} target="_blank" rel="noopener noreferrer" disabled={disabled}>查看发票</Button><Button disabled={disabled || busy || downloading} onClick={() => void download(`/api/m13/invoices/originals/${original.id}?download=true`)}>下载原件</Button></>}
      <Button disabled={disabled || busy || downloading} onClick={() => void download('/api/m13/invoices/export')}>导出全部已保存发票</Button>
      <Button disabled={blocked || busy || !Object.keys(drafts).length} onMouseDown={e => e.preventDefault()} onClick={() => saves.update(() => ({}))}>取消未保存修改</Button></div></div>
    {(pending > 0 || conflicts > 0) && <p className="oilcard-pending-hint">{pending > 0 && `${pending}张待确认，尚未计入开票合计。`}{conflicts > 0 && `${conflicts}份同票号冲突原件待核，原已确认金额保持。`}</p>}
    {(error || query.isError) && <p className="notice" role="alert">{error || query.error?.message}<Button disabled={blocked || busy} onClick={() => void saves.reread()}>重读核对</Button></p>}
    {result && <p className="oilcard-pending-hint" role="status">{result}</p>}
    {downloadError && <p className="notice" role="alert">{downloadError}</p>}
    {(uncertain || verified && Object.keys(drafts).length > 0) && <p className="notice" role="alert">{uncertain ? '请先重读核对刚才的收票或备注保存结果。' : '已读取当前发票，请核对保留输入。'}<Button disabled={!verified || blocked || busy} onClick={() => { saves.confirm(); upload.current = null; saves.update(ds => Object.fromEntries(Object.entries(ds).flatMap(([key, draft]) => { const actual = current.current?.invoices.find(r => r.id === draft.id); return actual?.remark === draft.value ? [] : [[key, { ...draft, original: actual?.remark ?? draft.original, error: '' }]]; }))); }}>已核对，保留输入继续</Button></p>}
    {Object.entries(drafts).filter(([, d]) => d.error).map(([key, d]) => <p className="oilcard-draft-error" key={key}>发票 #{d.id}：{d.error}<Button disabled={disabled || busy} onClick={() => saves.save(key, true)}>重试保存</Button></p>)}
    {query.isPending ? <p role="status" data-page-loading>正在读取发票台账…</p> : query.data && <InvoiceCells.Provider value={{ drafts, disabled, change, save: id => saves.save(String(id)) }}><div onContextMenuCapture={e => { if (e.target instanceof Element && e.target.closest('input')) e.stopPropagation(); }}><Dropdown trigger={['contextMenu']} menu={{ items: [{ key: 'view', label: '查看发票', disabled: disabled || !original }, { key: 'download', label: '下载原件', disabled: disabled || !original }], onClick: ({ key }) => { if (original && !disabled) { if (key === 'view') window.open(`/api/m13/invoices/originals/${original.id}`, '_blank', 'noopener'); else void download(`/api/m13/invoices/originals/${original.id}?download=true`); } } }}><div><BusinessGrid table="oilcard-invoices" label="油卡发票台账" rows={rows} columns={columns} totals={totals} rowId={row => String(row.id)} scale={scale} domLayout="normal" style={{ height: '62dvh', minHeight: '300px' }} grid={{ enableFilterHandlers: true, popupParent: document.body, onFilterChanged: e => setFilters(e.api.getFilterModel() as Record<string, ValueFilterModel>), onRowClicked: e => { if (e.data && !e.node.rowPinned) { setSelected(e.data.id); setOriginalId(0); } }, onCellContextMenu: e => { if (e.data && !e.node.rowPinned) { setSelected(e.data.id); setOriginalId(0); } }, rowClassRules: { 'oilcard-selected': p => p.data?.id === selected } }} /></div></Dropdown></div></InvoiceCells.Provider>}
    {row && <div className="oilcard-invoice-detail">{row.reason && <p className="notice">{row.reason}</p>}{row.originals.length > 1 && <label>原件<Select aria-label="选择发票原件" value={original?.id ?? null} options={row.originals.map((o, i) => ({ value: o.id, label: `${i === 0 ? '主原件' : o.outcome === 'conflict' ? '冲突原件待核' : '补档原件'} #${o.id}` }))} onChange={value => setOriginalId(value)} /></label>}{original?.outcome === 'conflict' && <p className="notice">{original.reason}</p>}</div>}
  </section>;
}
