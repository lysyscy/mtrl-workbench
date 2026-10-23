import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link, useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { ApiError, projectLabel, readProjects, record, requestJson } from './api';
import type { Identity } from './api';
import { ProjectPicker } from './ledger-controls';
import { fixedWidth, gridTheme, textWidth } from './grid';
import { archiveLabel, body, categories, cents, live, money, moneyKeys, readNotices, receipt, searchKey, selectable, total } from './notices-api';
import type { MoneyKey, NoticeRow } from './notices-api';
import { NoticeFetch } from './notice-fetch';
import { AutoLinkDialog } from './notice-auto-link';
import { DraftField, manualDraft, NoticeDialog, OwnershipPending, StatCell } from './notice-maintenance';
import type { Draft, NoticeDialogState } from './notice-maintenance';
import { NoticePayment, PayAmountCell, paymentValue } from './notice-payment';
import type { PayOverride } from './notice-payment';
import { NoticePrint, PrinterSettings } from './notice-print';
import './notices.css';
import { TimePicker, timeMatches, timeRange } from './time-picker';
import { DialogContents, useDialogClose } from './dialog-close';
interface Filters { period: string; projects: number[]; category: string; approval: string; paid: string; link: string }
const defaults = (): Filters => ({ period: '全部', projects: [], category: '', approval: '', paid: '未付清', link: '' });
interface RenderState { unavailable: boolean; shown: NoticeRow[]; picked: Set<number>; action: (path: string, payload: unknown, clear?: boolean) => Promise<boolean>; pick: (id: number, checked: boolean) => void; chooseAll: (checked: boolean) => void; draft: Draft | null; begin: (row?: NoticeRow) => void; saveDraft: () => Promise<void>; cancelDraft: () => void; open: (kind: NoticeDialogState['kind'], row: NoticeRow) => void; payOverrides: Record<number,PayOverride>; setPay: (row: NoticeRow, value: string) => void; moneyDrafts: Record<string,string>; draftCell: (row: NoticeRow, field: keyof Draft, label: string) => React.ReactNode; }
const amountNames: Record<MoneyKey, string> = { amount_approved: '审批金额', pay_amount: '付款金额', amount_paid: '已付金额', stat_settle: '统计结算金额', stat_paid: '统计付款金额' };
function inTime(r: NoticeRow, f: Filters): boolean { return timeMatches(f.period, r.doc_date); }
function scopeHit(r: NoticeRow, f: Filters): boolean {
  const arch = f.category === 'exclude';
  return inTime(r, f) && (!f.projects.length || f.projects.includes(r.ownership_id ?? 0)) &&
    (arch ? r.is_excluded || r.is_revoked : live(r) && (!f.category || f.category === r.category) && (!f.approval || f.approval === r.approve_status) && (!f.paid || f.paid === r.pay_status) && (!f.link || r.category === 'jc' && (f.link === 'yes' ? r.has_link : !r.has_link)));
}
function readHistory(value: unknown) {
  if (!record(value)) throw new ApiError('操作历史读取失败，请重试。');
  function item(x: unknown) { if (x === null) return null; if (!record(x) || typeof x.id !== 'number' || typeof x.label !== 'string') throw new ApiError('操作历史读取不完整，请重试。'); return { id: x.id, label: x.label }; }
  return { undo: item(value.undo), redo: item(value.redo), notice: typeof value.notice === 'string' ? value.notice : '' };
}
export function NoticesPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const client = useQueryClient(), api = useRef<GridApi<NoticeRow> | null>(null), lock = useRef(false), mounted = useRef(true);
  const [filters, setFilters] = useState(defaults), [search, setSearch] = useState(''), [picked, setPicked] = useState<Set<number>>(() => new Set());
  const [busy, setBusy] = useState(false), [feedback, setFeedback] = useState(''), [error, setError] = useState(''), [fetchOpen, setFetchOpen] = useState(false), [exportOpen, setExportOpen] = useState(false), [find, setFind] = useState('');
  const [print,setPrint] = useState<{mode:'pdf'|'print';rows:NoticeRow[]}|null>(null),[printerOpen,setPrinterOpen] = useState(false);
  const [params] = useSearchParams();
  const [payIds,setPayIds] = useState<number[]|null>(null), [payOverrides,setPayOverrides] = useState<Record<number,PayOverride>>({});
  function setPay(row: NoticeRow, value: string) { setPayOverrides(old => ({ ...old, [row.notice_id]: { value, basis: `${row.amount_approved}:${row.amount_paid}` } })); }
  function paid(ids: number[]) { setPayOverrides(old => Object.fromEntries(Object.entries(old).filter(([id]) => !ids.includes(Number(id))))); setPicked(new Set()); }
  useEffect(() => { const listener=(event:Event)=> { const id=Number((event as CustomEvent<number>).detail);setPayOverrides(old=>Object.fromEntries(Object.entries(old).filter(([key])=>Number(key)!==id))); };window.addEventListener('payment-revoked',listener);return()=>window.removeEventListener('payment-revoked',listener); },[]);
  const [autoIds,setAutoIds] = useState<number[]|null>(null);
  const dialog = useRef<HTMLDialogElement>(null), draftRef = useRef<Draft | null>(null), moneyDrafts = useRef<Record<string,string>>({}), pendingFocus = useRef(0);
  const [draft, setDraft] = useState<Draft | null>(null), [maintenance, setMaintenance] = useState<NoticeDialogState | null>(null), [focusId,setFocusId] = useState(0);
  useEffect(() => { if (!active) return; const id=Number(params.get('notice'));if(id>0){pendingFocus.current=id;setFocusId(id);setFilters({...defaults(),period:'全部',paid:''});setSearch('');} }, [params.get('notice'), active]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const query = useQuery({ queryKey: ['notices'], enabled: !blocked && active, queryFn: async ({ signal }) => readNotices(await requestJson('/api/m03/notice-list?period=', { signal })), refetchOnMount: 'always' });
  useEffect(() => { if (query.data) setPayOverrides(old => { const entries=Object.entries(old).filter(([id,draft]) => query.data.some(row => row.notice_id===Number(id) && draft.basis===`${row.amount_approved}:${row.amount_paid}`));return entries.length===Object.keys(old).length ? old : Object.fromEntries(entries); }); }, [query.data]);
  const projects = useQuery({ queryKey: ['projects', 'all'], enabled: !blocked && active, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const history = useQuery({ queryKey: ['notice-history'], enabled: !blocked && active && Boolean(me), queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
  useEffect(() => { if (active && !blocked) { void query.refetch(); void projects.refetch(); if (me) void history.refetch(); } }, [active]);
  const rows = useMemo(() => (query.data ?? []).map(r => { const p = projects.data?.find(p => p.id === r.ownership_id); return { ...r, pay_amount: paymentValue(r,payOverrides), project_display: p ? projectLabel(p) : r.ownership_id ? r.project_display : '未建档' }; }), [query.data, projects.data, payOverrides]);
  const scope = useMemo(() => rows.filter(r => scopeHit(r, filters)), [rows, filters]);
  const needle = searchKey(search);
  const shown = useMemo(() => scope.filter(r => !needle || [r.doc_date,r.bill_no,r.project_display,r.project_name,r.category_label,r.bill_name,r.biz_type,r.payee,r.jc_supplier,r.input_by,r.approve_status,r.pay_status,archiveLabel(r),r.is_manual ? '手动' : '',r.is_overpaid ? '超付' : '',...moneyKeys.map(k => r[k])].some(x => searchKey(x).includes(needle))), [scope, needle]);
  // Business scope changes trim selection; searching and virtual windows never do.
  useEffect(() => { const valid = new Set(scope.filter(selectable).map(r => r.notice_id)); setPicked(old => { const next = new Set([...old].filter(id => valid.has(id))); return next.size === old.size ? old : next; }); }, [filters]);
  useEffect(() => { const valid = new Set(rows.filter(selectable).map(r => r.notice_id)); setPicked(old => { const next = new Set([...old].filter(id => valid.has(id))); return next.size === old.size ? old : next; }); }, [rows]);
  const selected = rows.filter(r => picked.has(r.notice_id)), hidden = selected.filter(r => !shown.some(x => x.notice_id === r.notice_id)).length;
  const selectedPay = selected.filter(r => !r.is_excluded && !r.is_revoked);
  const liveShown = shown.filter(live);
  const summary = liveShown.length ? [{ notice_id: -1, bill_no: '合计', ...Object.fromEntries(moneyKeys.map(k => [k, total(liveShown, k)])) } as NoticeRow] : [];
  const unavailable = blocked || !active || !me || busy || query.isPending || query.isError || query.isFetching;
  const batchUnavailable = unavailable || !picked.size || hidden > 0;
  const batchReason = hidden ? '当前列表外还有勾选，请先清空搜索核对' : !picked.size ? '请先勾选通知书' : !me ? '请先登录' : '';
  async function refresh() { await client.invalidateQueries({ predicate: query => query.queryKey[0] !== 'notice-maintenance' }, { throwOnError: true }); }
  function cancelDraft() { draftRef.current = null; setDraft(null); }
  function begin(row?: NoticeRow) {
    if (unavailable || draftRef.current) return;
    const next = manualDraft(row); if (!row && filters.period !== '全部') next.doc_date = timeRange(filters.period).dateFrom; draftRef.current = next; setDraft(next);
    setFilters(f => ({ ...f, period: next.doc_date.slice(0,7), category: '', approval: '', paid: '', link: '' })); setSearch('');
    if (row) { pendingFocus.current=row.notice_id;setFocusId(row.notice_id); api.current?.ensureNodeVisible(node => node.data?.notice_id === row.notice_id, 'middle'); }
    api.current?.refreshCells({ force: true });
  }
  async function saveDraft() {
    const currentDraft = draftRef.current; if (!currentDraft || unavailable || lock.current) return;
    lock.current = true;setBusy(true);setError('');setFeedback('');let saved = false;
    try {
      const value = await requestJson('/api/m03/actions/manual-save',{ method: 'POST', ...body(currentDraft) }); saved = true;
      const id = record(value) ? Number(value.row_id) : 0; cancelDraft();
      setFeedback(receipt(value));
      setFilters(f => ({ ...f, period: currentDraft.doc_date.slice(0,7), category: '', approval: '', paid: '', link: '', projects: f.projects.length && !f.projects.includes(Number(currentDraft.ownership_id)) ? [...f.projects,Number(currentDraft.ownership_id)] : f.projects })); setSearch('');pendingFocus.current=id;setFocusId(id);
      await refresh();
    } catch (failure) { setError(`${saved ? '已保存，但列表尚待重读核对，勿重复新增。' : '保存失败，草稿已保留。'}${failure instanceof Error ? failure.message : '请重试。'}`); }
    finally { lock.current=false;setBusy(false); }
  }
  function draftCell(_row: NoticeRow, field: keyof Draft, label: string) { return <DraftField key={`${draftRef.current?.row_id || 'new'}:${field}`} draft={draftRef.current!} field={field} label={label} disabled={busy || blocked} projects={projects.data ?? []} />; }
  useEffect(() => { if (focusId && pendingFocus.current === focusId && active && !query.isFetching) requestAnimationFrame(() => { const node=api.current?.getRowNode(String(focusId));if(node){api.current?.ensureNodeVisible(node,'middle');pendingFocus.current=0;} }); }, [focusId,shown,query.isFetching,active]);
  async function action(path: string, payload: unknown, clear = false): Promise<boolean> {
    if (unavailable || lock.current) return false;
    lock.current = true; setBusy(true); setError(''); setFeedback(''); let saved = false;
    try {
      const value = await requestJson(path, { method: 'POST', ...body(payload) }); saved = true;
      if (!mounted.current) return false;
      setFeedback(receipt(value)); if (clear) setPicked(new Set()); await refresh(); return true;
    } catch (failure) { if (mounted.current) setError(`${saved ? '操作已完成，但读取失败；请重读核对，勿重复操作。' : ''}${failure instanceof Error ? failure.message : '操作未完成，请重试。'}`); return saved; }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function replay(direction: 'undo' | 'redo') {
    if (unavailable) return;
    try { const latest = await history.refetch({ throwOnError: true }); const item = latest.data?.[direction]; if (item) await action(`/api/history/${direction}`, { operation_id: item.id }); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '操作历史读取失败，请重试。'); }
  }
  function pick(id: number, checked: boolean) { setPicked(old => { const next = new Set(old); if (checked) next.add(id); else next.delete(id); return next; }); }
  function chooseAll(checked: boolean) { setPicked(old => { const next = new Set(old); for (const r of shown.filter(selectable)) { if (checked) next.add(r.notice_id); else next.delete(r.notice_id); } return next; }); }
  function locate() { if (!find.trim()) return; let hit = false; api.current?.forEachNodeAfterFilterAndSort(node => { if (!hit && node.data?.bill_no.includes(find.trim()) && node.rowIndex !== null) { api.current?.ensureIndexVisible(node.rowIndex, 'middle'); api.current?.setFocusedCell(node.rowIndex, 'bill_no'); hit = true; } }); if (!hit) setFeedback('当前筛选中没有该单据号，请调整条件。'); }
  const scale = Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1;
  const current = useRef<RenderState>(null!); current.current = { unavailable, shown, picked, action, pick, chooseAll, draft, begin, saveDraft, cancelDraft, open: (kind,row) => setMaintenance({kind,row}), payOverrides, setPay, moneyDrafts: moneyDrafts.current, draftCell };
  useEffect(() => { api.current?.refreshCells({ force: true }); api.current?.refreshHeader(); }, [picked, shown, busy, blocked, query.isFetching, draft]);
  const columns = useMemo<ColDef<NoticeRow>[]>(() => ([
    { colId: 'pick', headerName: '', pinned: 'left', ...fixedWidth(48, scale), sortable: false, headerComponent: () => { const ids = current.current.shown.filter(selectable).map(r => r.notice_id), count = ids.filter(id => current.current.picked.has(id)).length; return <input type="checkbox" aria-label="全选当前筛选结果" checked={ids.length > 0 && count === ids.length} ref={el => { if (el) el.indeterminate = count > 0 && count < ids.length; }} disabled={current.current.unavailable || !ids.length} onChange={e => current.current.chooseAll(e.target.checked)} />; }, cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : <input type="checkbox" aria-label={`勾选${p.data!.bill_no}`} disabled={current.current.unavailable || !selectable(p.data!)} checked={current.current.picked.has(p.data!.notice_id)} onChange={e => current.current.pick(p.data!.notice_id, e.target.checked)} /> },
    { field: 'doc_date', headerName: '单据日期', pinned: 'left', ...fixedWidth(130, scale) }, { field: 'bill_no', headerName: '单据编码', pinned: 'left', ...fixedWidth(185, scale) },
    { field: 'project_display', headerName: '付款项目', ...textWidth(170, 280, scale), tooltipField: 'project_name', wrapText: true, autoHeight: true, cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : p.data!.ownership_id ? p.data!.project_display : <button className="project-link" disabled={current.current.unavailable} onClick={() => current.current.open('ownership',p.data!)}>待指定归属</button> },
    { field: 'category_label', headerName: '分类', ...fixedWidth(130, scale), cellRenderer: (p: ICellRendererParams<NoticeRow>) => { if (p.node.rowPinned) return ''; const r = p.data!, label = archiveLabel(r); return label ? <span className={`notice-tag ${r.is_excluded ? r.exclude_source : 'revoked'}`} title={r.exclude_rule_hint}>{label}</span> : <select aria-label={`${r.bill_no}分类`} value={r.category} disabled={current.current.unavailable} onChange={e => void current.current.action('/api/m03/actions/category', { ids: [r.notice_id], category: e.target.value })}>{Object.entries(categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>; } },
    ...(['bill_name','biz_type','payee','jc_supplier','input_by'] as const).map((key, index): ColDef<NoticeRow> => ({ field: key, headerName: ['单据名称','业务类型','收款单位','集采实际供应商','录入人'][index]!, ...(index === 0 || index === 2 || index === 3 ? textWidth(200, 360, scale) : fixedWidth(120, scale)), wrapText: true, autoHeight: true,
      ...(key === 'jc_supplier' ? { cellRenderer: (p: ICellRendererParams<NoticeRow>) => { const r=p.data!; if(p.node.rowPinned || r.category !== 'jc' || r.is_excluded || r.is_revoked) return '—'; return <div className="notice-supplier"><span>{r.jc_supplier || '未录入'}</span><div><button disabled={current.current.unavailable} onClick={() => current.current.open('supplier',r)}>{r.jc_supplier ? '修改' : '录入'}</button><button disabled={current.current.unavailable} onClick={() => current.current.open('match',r)}>自动匹配</button><button disabled={current.current.unavailable} onClick={() => current.current.open('link',r)}>{r.has_link ? '查看 / 更改关联' : '关联集采合同'}</button></div></div>; } } : {}) })),
    ...moneyKeys.map((key): ColDef<NoticeRow> => ({ field: key, headerName: amountNames[key], ...fixedWidth(155, scale), cellClass: 'money', comparator: (a: string, b: string) => cents(a) < cents(b) ? -1 : cents(a) > cents(b) ? 1 : 0,
      cellRenderer: (p: ICellRendererParams<NoticeRow>) => !p.node.rowPinned && key === 'pay_amount' ? <PayAmountCell row={p.data!} override={current.current.payOverrides[p.data!.notice_id]} change={current.current.setPay} disabled={current.current.unavailable || p.data!.is_excluded || p.data!.is_revoked} /> : !p.node.rowPinned && (key === 'stat_settle' || key === 'stat_paid' || key === 'amount_approved' && p.data!.is_manual) ? <StatCell drafts={current.current.moneyDrafts} row={p.data!} field={key} disabled={current.current.unavailable || p.data!.is_excluded || p.data!.is_revoked} save={(path,payload) => current.current.action(path,payload)} /> : <span>{money(p.data![key])}{!p.node.rowPinned && key === 'amount_paid' && p.data!.is_overpaid && <span className="notice-tag rule">超付</span>}</span> })),
    { field: 'approve_status', headerName: '审批状态', ...fixedWidth(105, scale) }, { field: 'pay_status', headerName: '付款状态', ...fixedWidth(110, scale) },
    { colId: 'actions', headerName: '操作', ...fixedWidth(175, scale), sortable: false, cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : <div className="notice-row-actions">{cents(p.data!.amount_paid)>0n && <Link className="text-link" to={`/ledger?notice=${p.data!.notice_id}`}>撤销付款</Link>}{p.data!.is_manual && <><span className="notice-tag">手动</span><button disabled={current.current.unavailable || Boolean(current.current.draft)} onClick={() => current.current.begin(p.data!)}>编辑</button><button className="danger" disabled={current.current.unavailable || Boolean(current.current.draft)} onClick={() => current.current.open('delete',p.data!)}>删除</button></>}</div> },
  ] as ColDef<NoticeRow>[]).map((column: ColDef<NoticeRow>): ColDef<NoticeRow> => {
    const original = column.cellRenderer;
    const mapping: Record<string,keyof Draft> = { doc_date:'doc_date',bill_no:'bill_no',project_display:'ownership_id',category_label:'category',bill_name:'bill_name',biz_type:'biz_type',payee:'payee',amount_approved:'amount_approved',stat_settle:'stat_settle',stat_paid:'stat_paid',approve_status:'approve_status' };
    return { ...column, cellRenderer: (p: ICellRendererParams<NoticeRow>) => {
      const d = current.current.draft, editing = d && (p.data?.notice_id === -2 || String(p.data?.notice_id) === d.row_id);
      if (p.data?.notice_id === -2 && !d) return '';
      if (!editing) return original ? original(p) : p.value ?? '';
      if (column.colId === 'pick') return <span className="notice-tag">草稿</span>;
      if (column.colId === 'actions') return <div className="notice-row-actions"><button disabled={current.current.unavailable} onClick={() => void current.current.saveDraft()}>保存</button><button disabled={current.current.unavailable} onClick={current.current.cancelDraft}>取消</button></div>;
      const field = mapping[column.field ?? '']; return field ? current.current.draftCell(p.data!,field,column.headerName ?? '') : '—';
    } };
  }), [scale]);
  useEffect(() => { if (exportOpen && active && !blocked) dialog.current?.showModal(); else dialog.current?.close(); }, [exportOpen, active, blocked]);
  const exportClosing = useDialogClose({ busy, dirty: false, close: () => setExportOpen(false) });
  async function exportExcel() {
    if (unavailable || !shown.length || lock.current) return;
    const ids: number[] = []; api.current?.forEachNodeAfterFilterAndSort(node => { if (node.data) ids.push(node.data.notice_id); });
    lock.current = true; setBusy(true); setError('');
    try { const value = await requestJson('/api/m03/notices/export', { method: 'POST', ...body({ ids }) }); if (!record(value) || typeof value.filename !== 'string' || typeof value.content_b64 !== 'string') throw new ApiError('导出结果不完整，请重试。'); const blob = new Blob([Uint8Array.from(atob(value.content_b64), c => c.charCodeAt(0))], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }); const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = value.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setExportOpen(false); setFeedback(`已导出 ${value.rows} 条通知书。`); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '导出失败，请重试。'); }
    finally { lock.current = false; setBusy(false); }
  }
  return <div className="notices-page">
    {active && document.getElementById('history-controls') && createPortal(<div className="ledger-tools">{(['undo','redo'] as const).map(dir => <button key={dir} disabled={unavailable || !history.data?.[dir]} title={history.data?.[dir]?.label || history.data?.notice || '当前没有适用操作'} onClick={() => void replay(dir)}>{dir === 'undo' ? '撤销' : '重做'}</button>)}</div>, document.getElementById('history-controls')!)}
    <div className="notice-selection" role="status"><span>已勾选 <b>{picked.size}</b> 行</span><span>已勾选审批金额 <b>{money(total(selectedPay, 'amount_approved'))}</b> 元</span><span>已勾选本次应付 <b>{money(total(selectedPay, 'pay_amount'))}</b> 元</span>{hidden > 0 && <span className="notice-tag rule">当前列表外 {hidden} 条</span>}{picked.size > 0 && <button onClick={() => setPicked(new Set())}>清空勾选</button>}<span className="notice-selection-actions"><button disabled={unavailable || !picked.size || Boolean(draft)} onClick={()=>setPrint({mode:'print',rows:rows.filter(r=>picked.has(r.notice_id))})}>批量打印</button><button disabled={unavailable || !picked.size || Boolean(draft)} onClick={()=>setPrint({mode:'pdf',rows:rows.filter(r=>picked.has(r.notice_id))})}>只导出 PDF</button><button disabled={unavailable} onClick={()=>setPrinterOpen(true)}>打印机设置</button><button className="primary" disabled={batchUnavailable || !selectedPay.length || Boolean(draft)} title={batchReason} onClick={() => { if (!batchUnavailable) setPayIds([...picked]); }}>付款{selectedPay.length ? ` · ${selectedPay.length} 条` : ''}</button></span></div>
    <section className="notice-card"><div className="notice-tools"><div className="notice-batch" role="group" aria-label="已勾选通知书的批量处理"><span>批量改分类</span>{Object.entries(categories).map(([key, label]) => <button key={key} disabled={batchUnavailable} title={batchReason} onClick={() => { if (!hidden) void action('/api/m03/actions/category', { ids: [...picked], category: key }); }}>→ {label}</button>)}<button className="danger" disabled={batchUnavailable} title={batchReason || '标记保留，默认隐藏，不销毁数据'} onClick={() => { if (!hidden) void action('/api/m03/actions/exclude', { ids: [...picked] }, true); }}>批量剔除</button><button disabled={batchUnavailable} title={batchReason || '仅恢复已勾选的剔除行'} onClick={() => { if (!hidden) void action('/api/m03/actions/restore', { ids: [...picked] }, true); }}>恢复剔除</button></div><div className="notice-toolbar"><button disabled={unavailable} onClick={() => setFetchOpen(true)}>抓取 i8 付款通知书（按月）</button><button disabled={unavailable||!shown.some(r=>live(r)&&r.category==='jc'&&!r.has_link)} onClick={()=>setAutoIds(shown.filter(r=>live(r)&&r.category==='jc'&&!r.has_link).map(r=>r.notice_id))}>一键关联集采合同</button><button disabled={unavailable || Boolean(draft)} onClick={() => begin()}>＋ 手动新增通知书</button><button disabled={unavailable || !shown.length} onClick={() => setExportOpen(true)}>导出 Excel…</button></div></div>
      <div className="notice-filters"><div className="time-picker-field"><span>单据时间</span><TimePicker label="单据时间" value={filters.period} modes={['月','跨月','年','全部']} onChange={period => setFilters(f => ({ ...f, period }))} /></div>
      <div className="notice-project"><span>项目</span><ProjectPicker projects={projects.data ?? []} selected={filters.projects} pick={projects => setFilters(f => ({ ...f, projects }))} multiple emptyLabel="全部项目" label="项目筛选" disabled={projects.isPending || projects.isError} /></div>
      <label>分类<select value={filters.category} onChange={e => setFilters(f => ({ ...f, category: e.target.value, link: '' }))}><option value="">全部</option>{Object.entries(categories).map(([v,t]) => <option key={v} value={v}>{t}</option>)}<option value="exclude">剔除</option></select></label><label>合同关联（集采）<select disabled={!['','jc'].includes(filters.category)} value={filters.link} onChange={e => setFilters(f => ({ ...f, link: e.target.value }))}><option value="">全部</option><option value="no">未关联</option><option value="yes">已关联</option></select></label>
      <label>审批状态<select disabled={filters.category === 'exclude'} value={filters.approval} onChange={e => setFilters(f => ({ ...f, approval: e.target.value }))}><option value="">全部</option><option>已批</option><option>未批</option></select></label><label>付款状态<select disabled={filters.category === 'exclude'} value={filters.paid} onChange={e => setFilters(f => ({ ...f, paid: e.target.value }))}><option value="">全部</option><option>已付清</option><option>未付清</option></select></label><label>搜索<input type="search" placeholder="搜索各列内容" value={search} onChange={e => setSearch(e.target.value)} /></label><button onClick={() => { setFilters(defaults()); setSearch(''); }}>重置</button>
      <form onSubmit={e => { e.preventDefault(); locate(); }}><label>定位单据<input value={find} onChange={e => setFind(e.target.value)} /></label><button>定位</button></form></div>
      {feedback && <p className="notice-feedback" role="status">{feedback}</p>}{error && <p className="notice" role="alert">{error}<button disabled={busy} onClick={() => void refresh().then(() => setError('')).catch(e => setError(e.message))}>重读核对</button></p>}
      {query.isError && query.data && <p className="notice" role="alert">列表更新失败，保留上次结果。{query.error.message}<button onClick={() => void query.refetch()}>重试读取</button></p>}{query.isPending ? <p className="state" role="status">正在读取付款通知书…</p> : query.isError && !query.data ? <p className="notice" role="alert">{query.error.message}<button onClick={() => void query.refetch()}>重试</button></p> : <><p className="notice-count">显示 {shown.length} 条 · 当前时间范围有效 {rows.filter(r => inTime(r, filters) && live(r)).length} 条 · 剔除 {rows.filter(r => inTime(r, filters) && r.is_excluded).length} 条 · i8 已撤单 {rows.filter(r => inTime(r, filters) && r.is_revoked).length} 条（切「分类＝剔除」查看）</p>{busy && <p className="notice-feedback" role="status">正在保存，请稍候…</p>}<div className="notice-grid" role="region" aria-label="付款通知书列表"><AgGridReact<NoticeRow> theme={gridTheme} rowData={shown} columnDefs={columns} pinnedBottomRowData={draft && !draft.row_id ? [{ notice_id: -2 } as NoticeRow,...summary] : summary} getRowId={p => String(p.data.notice_id)} getRowClass={p => p.data?.notice_id === focusId ? 'notice-focused' : ''} defaultColDef={{ sortable: true, resizable: false, suppressMovable: true, wrapHeaderText: true, autoHeaderHeight: true }} rowHeight={40 * scale} headerHeight={38 * scale} suppressScrollOnNewData animateRows={false} onGridReady={e => { api.current = e.api; }} overlayNoRowsTemplate="当前筛选条件下没有付款通知书，请调整条件或按月抓取。" /></div></>}
      {draft && <p role="status" className="notice-feedback">{draft.row_id ? `正在编辑 ${draft.bill_no}` : '新增草稿位于表尾'} · 尚未保存，返回本页可继续填写。<button disabled={unavailable} onClick={() => void saveDraft()}>保存草稿</button><button disabled={unavailable} onClick={cancelDraft}>取消草稿</button></p>}
      <OwnershipPending blocked={blocked || !active} open={row => setMaintenance({kind:'ownership',row})} />
      {autoIds&&<AutoLinkDialog ids={autoIds} blocked={blocked||!active} close={()=>setAutoIds(null)} refresh={refresh} announce={setFeedback} />}
      {maintenance && <NoticeDialog state={maintenance} projects={projects.data ?? []} blocked={blocked || !active} close={() => setMaintenance(null)} refresh={refresh} announce={setFeedback} />}
      {projects.isError && <p className="notice" role="alert">{projects.error.message}<button onClick={() => void projects.refetch()}>重读项目</button></p>}{history.isError && <p className="notice" role="alert">{history.error.message}<button onClick={() => void history.refetch()}>重读操作历史</button></p>}
    </section>
    {print && <NoticePrint rows={print.rows} mode={print.mode} blocked={blocked || !active} close={()=>setPrint(null)} />}
    {printerOpen && <PrinterSettings blocked={blocked || !active} close={()=>setPrinterOpen(false)} />}
    {payIds && <NoticePayment ids={payIds} overrides={payOverrides} blocked={blocked || !active} remove={id => { pick(id,false);setPayIds(ids => ids?.filter(x => x !== id) ?? null); }} close={() => setPayIds(null)} paid={paid} refresh={refresh} announce={setFeedback} />}
    {fetchOpen && <NoticeFetch me={me} blocked={blocked || !active} close={() => setFetchOpen(false)} refresh={refresh} />}
    <dialog ref={dialog} className="project-dialog" aria-labelledby="notice-export-title" {...exportClosing.dialogProps}><DialogContents titleId="notice-export-title" title="导出付款通知书台账" closing={exportClosing}><p>导出当前筛选的 {shown.length} 条通知书，按表格显示顺序排列。</p>{error && <p className="notice" role="alert">{error}</p>}<div className="dialog-actions"><button disabled={busy} onClick={exportClosing.requestClose}>取消</button><button className="primary" disabled={unavailable || !shown.length} onClick={() => void exportExcel()}>保存到本地</button></div></DialogContents></dialog>
  </div>;
}
