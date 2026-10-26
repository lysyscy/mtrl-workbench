import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import Checkbox from 'antd/es/checkbox';
import { EnumTag } from './enum-tag';
import Button from 'antd/es/button';
import { useHistoryGuard } from './history';
import { BusinessModal } from './business-modal';
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { ApiError, confirmWrite, uncertainWrite, projectLabel, readProjects, record, requestJson } from './api';
import type { Identity } from './api';
import { ProjectPicker } from './ledger-controls';
import { pageGridGeometry, fitGridColumns, contentWidth, fixedWidth, gridTheme, numberColumnWidth } from './grid';
import { archiveLabel, body, categories, cents, live, money, moneyKeys, readNotices, receipt, searchKey, selectable, total } from './notices-api';
import type { MoneyKey, NoticeRow } from './notices-api';
import { NoticeFetch } from './notice-fetch';
import { NoticePaste } from './notice-paste';
import { AutoLinkDialog } from './notice-auto-link';
import { DraftField, manualDraft, NoticeDialog, OwnershipPending, StatCell } from './notice-maintenance';
import type { Draft, NoticeDialogState } from './notice-maintenance';
import { NoticePayment, PayAmountCell, paymentValue } from './notice-payment';
import type { PayOverride } from './notice-payment';
import { NoticePrint, PrinterSettings } from './notice-print';
import { NoticeFlows } from './notice-flows';
import './notices.css';
import { TimePicker, timeMatches, timeRange } from './time-picker';
import { DialogContents, useDialogClose } from './dialog-close';
interface Filters { period: string; projects: number[]; category: string; approval: string; paid: string; link: string; pending: '' | 'ownership' | 'void' }
const defaults = (): Filters => ({ period: '全部', projects: [], category: '', approval: '', paid: '未付清', link: '', pending: '' });
interface RenderState { viewFlows: (row: NoticeRow) => void; unavailable: boolean; shown: NoticeRow[]; picked: Set<number>; action: (path: string, payload: unknown, clear?: boolean) => Promise<boolean>; pick: (id: number, checked: boolean) => void; chooseAll: (checked: boolean) => void; draft: Draft | null; begin: (row?: NoticeRow) => void; saveDraft: () => Promise<void>; cancelDraft: () => void; open: (kind: NoticeDialogState['kind'], row: NoticeRow) => void; payOverrides: Record<number,PayOverride>; setPay: (row: NoticeRow, value: string) => void; moneyDrafts: Record<string,string>; draftCell: (row: NoticeRow, field: keyof Draft, label: string) => React.ReactNode; }
const amountNames: Record<MoneyKey, string> = { amount_approved: '审批金额', pay_amount: '付款金额', amount_paid: '已付金额', stat_settle: '统计结算金额', stat_paid: '统计付款金额' };
const heightUpdates = new WeakSet<GridApi>();
const defaultColumn: ColDef<NoticeRow> = { cellDataType: false, sortable: true, resizable: false, suppressMovable: true, wrapHeaderText: true, autoHeaderHeight: true };

function NoticeAutoHeight({ params, children }: { params: ICellRendererParams<NoticeRow>; children: import('react').ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const element = ref.current, cell = element?.closest<HTMLElement>('.ag-cell');
    if (!element || !cell || params.api.isDestroyed()) return;
    const css = getComputedStyle(cell);
    const height = element.offsetHeight + [css.paddingTop, css.paddingBottom, css.borderTopWidth, css.borderBottomWidth].reduce((sum, value) => sum + (parseFloat(value) || 0), 0);
    if (height <= (params.node.rowHeight ?? 0)) return;
    params.node.setRowHeight(height);
    // Coalesce public row-height updates after the render stack, before the first paint.
    if (!heightUpdates.has(params.api)) {
      heightUpdates.add(params.api);
      queueMicrotask(() => { heightUpdates.delete(params.api); if (!params.api.isDestroyed()) params.api.onRowHeightChanged(); });
    }
  });
  return <div ref={ref} style={{ width: '100%', minWidth: 0 }}>{children}</div>;
}

function inTime(r: NoticeRow, f: Filters): boolean { return timeMatches(f.period, r.doc_date); }
function scopeHit(r: NoticeRow, f: Filters): boolean {
  const arch = f.category === 'exclude';
  return inTime(r, f) && (!f.projects.length || f.projects.includes(r.ownership_id ?? 0)) &&
    (!f.pending || (f.pending === 'ownership' ? !r.ownership_id : r.is_revoked)) &&
    (arch ? r.is_excluded || r.is_revoked : live(r) && (!f.category || f.category === r.category) && (!f.approval || f.approval === r.approve_status) && (!f.paid || f.paid === r.pay_status) && (!f.link || r.category === 'jc' && (f.link === 'yes' ? r.has_link : !r.has_link)));
}
export function NoticesPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const client = useQueryClient(), api = useRef<GridApi<NoticeRow> | null>(null), gridRoot = useRef<HTMLDivElement>(null), lock = useRef(false), mounted = useRef(true);
  const [filters, setFilters] = useState(defaults), [search, setSearch] = useState(''), [picked, setPicked] = useState<Set<number>>(() => new Set());
  const [busy, setBusy] = useState(false), [feedback, setFeedback] = useState(''), [error, setError] = useState(''), [fetchOpen, setFetchOpen] = useState(false), [exportOpen, setExportOpen] = useState(false), [pasteOpen,setPasteOpen] = useState(false), [pasteTop,setPasteTop] = useState<Set<number>>(() => new Set()), [pasteScope,setPasteScope] = useState<number[] | null>(null);
  const printLock = useRef(false);
  const [flowNotice,setFlowNotice] = useState<NoticeRow|null>(null);
  const [print,setPrint] = useState<{mode:'pdf'|'print';rows:NoticeRow[]}|null>(null),[printerOpen,setPrinterOpen] = useState(false);
  const [params] = useSearchParams();
  const [payIds,setPayIds] = useState<number[]|null>(null), [payOverrides,setPayOverrides] = useState<Record<number,PayOverride>>({});
  function setPay(row: NoticeRow, value: string) { setPayOverrides(old => ({ ...old, [row.notice_id]: { value, basis: `${row.amount_approved}:${row.amount_paid}` } })); }
  function paid(ids: number[]) { setPayOverrides(old => Object.fromEntries(Object.entries(old).filter(([id]) => !ids.includes(Number(id))))); setPicked(new Set()); }
  useEffect(() => { const listener=(event:Event)=> { const id=Number((event as CustomEvent<number>).detail);setPayOverrides(old=>Object.fromEntries(Object.entries(old).filter(([key])=>Number(key)!==id))); };window.addEventListener('payment-revoked',listener);return()=>window.removeEventListener('payment-revoked',listener); },[]);
  const [autoIds,setAutoIds] = useState<number[]|null>(null);
  const draftRef = useRef<Draft | null>(null), moneyDrafts = useRef<Record<string,string>>({}), pendingFocus = useRef(0);
  const [draftUncertain, setDraftUncertain] = useState(false), [draftChecked, setDraftChecked] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null), [maintenance, setMaintenance] = useState<NoticeDialogState | null>(null), [focusId,setFocusId] = useState(0);
  useEffect(() => { if (!active) return; const id=Number(params.get('notice'));if(id>0){pendingFocus.current=id;setFocusId(id);setFilters({...defaults(),period:'全部',paid:''});setSearch('');} }, [params.get('notice'), active]);
  // Home todo tiles land here with ?todo=: conflicting old filters are reset so the
  // landed scope matches the tile count exactly (jc via plain filters, the other two
  // via the removable pending chip).
  useEffect(() => { if (!active) return; const kind = params.get('todo'); if (kind === 'jc') { setFilters({ ...defaults(), category: 'jc', link: 'no' }); setSearch(''); setPasteScope(null); } else if (kind === 'ownership' || kind === 'void') { setFilters({ ...defaults(), period: '全部', paid: '', pending: kind }); setSearch(''); setPasteScope(null); } }, [params.get('todo'), active]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const query = useQuery({ queryKey: ['notices'], enabled: !blocked && active, queryFn: async ({ signal }) => readNotices(await requestJson('/api/m03/notice-list?period=', { signal })), refetchOnMount: 'always' });
  useEffect(() => { if (query.data) setPayOverrides(old => { const entries=Object.entries(old).filter(([id,draft]) => query.data.some(row => row.notice_id===Number(id) && draft.basis===`${row.amount_approved}:${row.amount_paid}`));return entries.length===Object.keys(old).length ? old : Object.fromEntries(entries); }); }, [query.data]);
  const projects = useQuery({ queryKey: ['projects', 'all'], enabled: !blocked && active, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const rows = useMemo(() => (query.data ?? []).map(r => { const p = projects.data?.find(p => p.id === r.ownership_id); return { ...r, pay_amount: paymentValue(r,payOverrides), project_display: p ? projectLabel(p) : r.ownership_id ? r.project_display : '未建档' }; }), [query.data, projects.data, payOverrides]);
  const scope = useMemo(() => rows.filter(r => (!pasteScope || pasteScope.includes(r.notice_id)) && scopeHit(r, filters)), [rows, filters, pasteScope]);
  const needle = searchKey(search);
  const shown = useMemo(() => scope.filter(r => !needle || [r.doc_date,r.bill_no,r.project_display,r.project_name,r.category_label,r.bill_name,r.biz_type,r.payee,r.jc_supplier,r.input_by,r.approve_status,r.pay_status,archiveLabel(r),r.is_manual ? '手动' : '',r.is_overpaid ? '超付' : '',r.category === 'jc' ? r.has_link ? '已关联 查看 / 更改关联' : '关联集采合同' : '',...moneyKeys.map(k => r[k])].some(x => searchKey(x).includes(needle))), [scope, needle]);
  // Business scope changes trim selection; searching and virtual windows never do.
  useEffect(() => { const valid = new Set(scope.filter(selectable).map(r => r.notice_id)); setPicked(old => { const next = new Set([...old].filter(id => valid.has(id))); return next.size === old.size ? old : next; }); }, [filters]);
  useEffect(() => { const valid = new Set(rows.filter(selectable).map(r => r.notice_id)); setPicked(old => { const next = new Set([...old].filter(id => valid.has(id))); return next.size === old.size ? old : next; }); }, [rows]);
  const selected = rows.filter(r => picked.has(r.notice_id)), hidden = selected.filter(r => !shown.some(x => x.notice_id === r.notice_id)).length;
  const selectedPay = selected.filter(r => !r.is_excluded && !r.is_revoked);
  const liveShown = shown.filter(live);
  const summary = liveShown.length ? [{ notice_id: -1, bill_no: '合计', ...Object.fromEntries(moneyKeys.map(k => [k, total(liveShown, k)])) } as NoticeRow] : [];
  const unavailable = draftUncertain || blocked || !active || !me || busy || query.isPending || query.isError || query.isFetching;
  useHistoryGuard('notices', () => busy || lock.current ? '付款通知书正在处理，请稍候。' : draftRef.current || Object.keys(moneyDrafts.current).length ? '付款通知书有未保存输入，请先处理。' : '');
  const batchUnavailable = unavailable || !picked.size || hidden > 0;
  const batchReason = hidden ? '当前列表外还有勾选，请先清空搜索核对' : !picked.size ? '请先勾选通知书' : !me ? '请先登录' : '';
  async function refresh() { await client.invalidateQueries({ predicate: query => query.queryKey[0] !== 'notice-maintenance' }, { throwOnError: true }); }
  function cancelDraft() { draftRef.current = null; setDraft(null); setDraftUncertain(false); setDraftChecked(false); }
  function begin(row?: NoticeRow) {
    if (unavailable || draftRef.current) return;
    const next = manualDraft(row); if (!row && filters.period !== '全部') next.doc_date = timeRange(filters.period).dateFrom; draftRef.current = next; setDraft(next);
    setFilters(f => ({ ...f, period: next.doc_date.slice(0,7), category: '', approval: '', paid: '', link: '' })); setSearch('');
    if (row) { pendingFocus.current=row.notice_id;setFocusId(row.notice_id); api.current?.ensureNodeVisible(node => node.data?.notice_id === row.notice_id, 'middle'); }
    api.current?.refreshCells({ force: true });
  }
  async function saveDraft() {
    const currentDraft = draftRef.current; if (!currentDraft || draftUncertain || unavailable || lock.current) return;
    lock.current = true;setBusy(true);setError('');setFeedback('');let saved = false;
    try {
      const value = await requestJson('/api/m03/actions/manual-save',{ method: 'POST', ...body(currentDraft) });
      if (!mounted.current) return;
      confirmWrite(record(value) && value.ok === true && typeof value.row_id === 'string' && /^[1-9]\d*$/.test(value.row_id) && Number.isSafeInteger(Number(value.row_id)) && typeof value.message === 'string', '保存结果待核实，请重读列表核对，勿重复新增。'); saved = true;
      const id = record(value) ? Number(value.row_id) : 0; cancelDraft();
      setFeedback(receipt(value));
      setFilters(f => ({ ...f, period: currentDraft.doc_date.slice(0,7), category: '', approval: '', paid: '', link: '', projects: f.projects.length && !f.projects.includes(Number(currentDraft.ownership_id)) ? [...f.projects,Number(currentDraft.ownership_id)] : f.projects })); setSearch('');pendingFocus.current=id;setFocusId(id);
      await refresh();
    } catch (failure) { if (!mounted.current) return; const unknown = !saved && uncertainWrite(failure); setDraftUncertain(unknown); setDraftChecked(false); setError(`${saved ? '已保存，但列表尚待重读核对，勿重复新增。' : unknown ? '保存结果待核实，草稿已保留；勿重复新增。' : '保存失败，草稿已保留。'}${failure instanceof Error ? failure.message : '请重试。'}`); }
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
  function startPrint(mode: 'print'|'pdf') { if (unavailable || printLock.current || !picked.size || draft) return; printLock.current=true;setPrint({mode,rows:rows.filter(r=>picked.has(r.notice_id))}); }
  function pick(id: number, checked: boolean) { setPicked(old => { const next = new Set(old); if (checked) next.add(id); else next.delete(id); return next; }); }
  function chooseAll(checked: boolean) { setPicked(old => { const next = new Set(old); for (const r of shown.filter(selectable)) { if (checked) next.add(r.notice_id); else next.delete(r.notice_id); } return next; }); }
  const scale = Number(me?.ui_scale_css) || 1;
  const current = useRef<RenderState>(null!); current.current = { viewFlows: setFlowNotice, unavailable, shown, picked, action, pick, chooseAll, draft, begin, saveDraft, cancelDraft, open: (kind,row) => setMaintenance({kind,row}), payOverrides, setPay, moneyDrafts: moneyDrafts.current, draftCell };
  useEffect(() => { if (!active) return; api.current?.refreshCells({ force: true }); api.current?.refreshHeader(); }, [active, picked, shown, busy, blocked, query.isFetching, draft]);
  const moneyWidth=useMemo(()=>{
    const data=query.data??[];
    const values=moneyKeys.flatMap(key=>[...data.map(row=>row[key]),total(data.filter(row=>cents(row[key])>=0n),key),total(data.filter(row=>cents(row[key])<0n),key)]);
    return numberColumnWidth(values.map(money), 1, true).minWidth;
  },[query.data]);
  const columns = useMemo<ColDef<NoticeRow>[]>(() => ([
    { colId: 'pick', headerName: '', pinned: 'left', ...fixedWidth(36, scale), sortable: false, headerComponent: () => { const ids = current.current.shown.filter(selectable).map(r => r.notice_id), count = ids.filter(id => current.current.picked.has(id)).length; return <Checkbox aria-label="全选当前筛选结果" checked={ids.length > 0 && count === ids.length} indeterminate={count > 0 && count < ids.length} disabled={current.current.unavailable || !ids.length} onChange={e => current.current.chooseAll(e.target.checked)} />; }, cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : <Checkbox aria-label={`勾选${p.data!.bill_no}`} disabled={current.current.unavailable || !selectable(p.data!)} checked={current.current.picked.has(p.data!.notice_id)} onChange={e => current.current.pick(p.data!.notice_id, e.target.checked)} /> },
    { field: 'doc_date', headerName: '单据日期', pinned: 'left', ...contentWidth(70, 120, scale), wrapText: true, autoHeight: true }, { field: 'bill_no', tooltipField: 'bill_no', headerName: '单据编码', pinned: 'left', ...contentWidth(112, 200, scale), wrapText: true, autoHeight: true },
    { field: 'project_display', headerName: '付款项目', ...contentWidth(80, 200, scale, 1), tooltipField: 'project_name', wrapText: true, autoHeight: true, cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : p.data!.ownership_id ? p.data!.project_display : <Button htmlType="submit" className="project-link" disabled={current.current.unavailable} onClick={() => current.current.open('ownership',p.data!)}>待指定归属</Button> },
    { field: 'category_label', headerName: '分类', ...contentWidth(60, 100, scale), wrapText: true, autoHeight: true, cellRenderer: (p: ICellRendererParams<NoticeRow>) => { if (p.node.rowPinned) return ''; const r = p.data!, label = archiveLabel(r); return label ? <span><span className={`notice-tag ${r.is_excluded ? r.exclude_source : 'revoked'}`} title={r.exclude_rule_hint}>{label}</span>{r.is_revoked && (cents(r.amount_paid) > 0n || r.has_link) && <span className="notice-tag rule notice-revoke-hint">请先撤销付款 / 解绑关联</span>}</span> : <Select className="notice-category-select" aria-label={`${r.bill_no}分类`} value={r.category} disabled={current.current.unavailable} onChange={value => void current.current.action('/api/m03/actions/category', { ids: [r.notice_id], category: value })} options={Object.entries(categories).map(([value,label])=>({value,label}))} popupMatchSelectWidth={false} labelRender={option=><EnumTag kind="category" value={String(option.label)}/>}/>; } },
    ...(['bill_name','biz_type','payee','jc_supplier','input_by'] as const).map((key, index): ColDef<NoticeRow> => ({ field: key, headerName: ['单据名称','业务类型','收款单位','集采实际供应商','录入人'][index]!, ...(index === 3 ? contentWidth(128, 260, scale, 1) : index === 0 || index === 2 ? contentWidth(96, 260, scale, 1) : contentWidth(index === 4 ? 44 : 60, 160, scale)), wrapText: true, autoHeight: true,
      ...(key === 'jc_supplier' ? { cellRenderer: (p: ICellRendererParams<NoticeRow>) => { const r=p.data!; if(p.node.rowPinned || (r.category !== 'jc' || r.is_excluded || r.is_revoked) && !r.has_link) return '—'; return <Button data-contract-notice={r.notice_id} className="notice-association-trigger" htmlType="button" aria-label={`${r.bill_no}供应商与合同关联`} disabled={current.current.unavailable} onClick={() => current.current.open('link',r)}><span>{r.jc_supplier || '选择供应商与合同'}</span><small>{r.has_link ? '已关联合同' : '未关联合同'}</small></Button>; } } : {}) })),
    ...moneyKeys.map((key): ColDef<NoticeRow> => ({ field: key, headerName: amountNames[key], ...contentWidth(moneyWidth, Math.max(moneyWidth,220), scale), cellClass: 'money', comparator: (a: string, b: string) => cents(a) < cents(b) ? -1 : cents(a) > cents(b) ? 1 : 0,
      cellRenderer: (p: ICellRendererParams<NoticeRow>) => !p.node.rowPinned && key === 'pay_amount' ? <PayAmountCell row={p.data!} override={current.current.payOverrides[p.data!.notice_id]} change={current.current.setPay} disabled={current.current.unavailable || p.data!.is_excluded || p.data!.is_revoked} /> : !p.node.rowPinned && (key === 'stat_settle' || key === 'stat_paid' || key === 'amount_approved' && p.data!.is_manual) ? <StatCell drafts={current.current.moneyDrafts} row={p.data!} field={key} disabled={current.current.unavailable || p.data!.is_excluded || p.data!.is_revoked} save={(path,payload) => current.current.action(path,payload)} /> : <span>{money(p.data![key])}{!p.node.rowPinned && key === 'amount_paid' && p.data!.is_overpaid && <span className="notice-tag rule">超付</span>}</span> })),
    { field: 'approve_status', headerName: '审批状态', ...contentWidth(68, 100, scale), cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : <Tag className={`status-tag ${p.value === '已批' ? 'status-positive' : 'status-pending'}`}>{p.value || '—'}</Tag> }, { field: 'pay_status', headerName: '付款状态', ...contentWidth(68, 105, scale), cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : <Tag className={`status-tag ${p.value === '已付清' ? 'status-positive' : 'status-pending'}`}>{p.value || '—'}</Tag> },
    { colId: 'actions', headerName: '操作', ...contentWidth(88, 175, scale), wrapText: true, autoHeight: true, sortable: false, cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : <div className="notice-row-actions">{p.data!.has_any_flow && <Button htmlType="submit" disabled={current.current.unavailable} onClick={() => current.current.viewFlows(p.data!)}>查看流水</Button>}{cents(p.data!.amount_paid)>0n && <Link className="row-button danger" to={`/ledger?notice=${p.data!.notice_id}`}>撤销付款</Link>}{p.data!.is_manual && <><span className="notice-tag">手动</span><Button htmlType="submit" disabled={current.current.unavailable || Boolean(current.current.draft)} onClick={() => current.current.begin(p.data!)}>编辑</Button><Button htmlType="submit" className="danger" disabled={current.current.unavailable || Boolean(current.current.draft)} onClick={() => current.current.open('delete',p.data!)}>删除</Button></>}</div> },
  ] as ColDef<NoticeRow>[]).map((column: ColDef<NoticeRow>): ColDef<NoticeRow> => {
    const original = column.cellRenderer;
    const mapping: Record<string,keyof Draft> = { doc_date:'doc_date',bill_no:'bill_no',project_display:'ownership_id',category_label:'category',bill_name:'bill_name',biz_type:'biz_type',payee:'payee',amount_approved:'amount_approved',stat_settle:'stat_settle',stat_paid:'stat_paid',approve_status:'approve_status' };
    return { ...column, cellRenderer: (p: ICellRendererParams<NoticeRow>) => {
      const d = current.current.draft, editing = d && (p.data?.notice_id === -2 || String(p.data?.notice_id) === d.row_id);
      if (p.data?.notice_id === -2 && !d) return '';
      if (!editing) { const content = original ? original(p) : p.value ?? ''; return column.autoHeight ? <NoticeAutoHeight params={p}>{content}</NoticeAutoHeight> : content; }
      if (column.colId === 'pick') return <span className="notice-tag">草稿</span>;
      if (column.colId === 'actions') return <div className="notice-row-actions"><Button htmlType="submit" disabled={current.current.unavailable} onClick={() => void current.current.saveDraft()}>保存</Button><Button htmlType="submit" disabled={current.current.unavailable} onClick={current.current.cancelDraft}>取消</Button></div>;
      const field = mapping[column.field ?? '']; return field ? current.current.draftCell(p.data!,field,column.headerName ?? '') : '—';
    } };
  }), [scale,moneyWidth]);
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
    <div className="notice-selection" role="status"><span>已勾选 <b>{picked.size}</b> 行</span><span>审批金额 <b>{money(total(selectedPay, 'amount_approved'))}</b> 元</span><span>本次应付 <b>{money(total(selectedPay, 'pay_amount'))}</b> 元</span>{hidden > 0 && <span className="notice-tag rule">当前列表外 {hidden} 条</span>}{picked.size > 0 && <Button htmlType="submit" onClick={() => setPicked(new Set())}>清空勾选</Button>}<span className="notice-selection-actions"><Button htmlType="submit" disabled={unavailable || Boolean(print) || !picked.size || Boolean(draft)} onClick={()=>startPrint('print')}>批量打印</Button><Button htmlType="submit" disabled={unavailable || Boolean(print) || !picked.size || Boolean(draft)} onClick={()=>startPrint('pdf')}>导出 PDF</Button><Button htmlType="submit" disabled={unavailable} onClick={()=>setPrinterOpen(true)}>打印机设置</Button><Button htmlType="submit" type="primary" className="notice-pay-action" disabled={batchUnavailable || !selectedPay.length || Boolean(draft)} title={batchReason} onClick={() => { if (!batchUnavailable) setPayIds([...picked]); }}>付款{selectedPay.length ? `（${selectedPay.length} 条）` : ''}</Button></span></div>
    <section className="notice-card"><div className="notice-tools"><div className="notice-batch" role="group" aria-label="已勾选通知书的批量处理"><span>批量改分类</span>{Object.entries(categories).map(([key, label]) => <Button htmlType="submit" key={key} disabled={batchUnavailable} title={batchReason} onClick={() => { if (!hidden) void action('/api/m03/actions/category', { ids: [...picked], category: key }); }}>{label}</Button>)}<Button htmlType="submit" className="danger" disabled={batchUnavailable} title={batchReason || '标记保留，默认隐藏，不销毁数据'} onClick={() => { if (!hidden) void action('/api/m03/actions/exclude', { ids: [...picked] }, true); }}>批量剔除</Button><Button htmlType="submit" disabled={batchUnavailable} title={batchReason || '仅恢复已勾选的剔除行'} onClick={() => { if (!hidden) void action('/api/m03/actions/restore', { ids: [...picked] }, true); }}>恢复剔除</Button></div><div className="notice-toolbar"><Button htmlType="submit" disabled={unavailable} onClick={() => setFetchOpen(true)}>按月抓取 i8</Button><Button htmlType="submit" disabled={unavailable||!shown.some(r=>live(r)&&r.category==='jc'&&!r.has_link)} onClick={()=>setAutoIds(shown.filter(r=>live(r)&&r.category==='jc'&&!r.has_link).map(r=>r.notice_id))}>批量关联集采合同</Button><Button type="primary" htmlType="submit" disabled={unavailable || Boolean(draft)} onClick={() => begin()}>手动新增</Button><Button htmlType="submit" disabled={unavailable || !shown.length} onClick={() => setExportOpen(true)}>导出 Excel</Button></div></div>
      <div className="notice-filters"><div className="time-picker-field"><span>单据时间</span><TimePicker singleEntry label="单据时间" value={filters.period} modes={['月','跨月','年','全部']} onChange={period => setFilters(f => ({ ...f, period }))} /></div>
      <div className="notice-project"><span>项目</span><ProjectPicker projects={projects.data ?? []} selected={filters.projects} pick={projects => setFilters(f => ({ ...f, projects }))} multiple emptyLabel="全部项目" label="项目筛选" disabled={projects.isPending || projects.isError} /></div>
      <label>分类<Select aria-label="通知书分类" disabled={false} value={filters.category} onChange={value=>setFilters(f=>({...f,category:value, link: ''}))} options={[{value:'',label:'全部'},...Object.entries(categories).map(([value,label])=>({value,label})),{value:'exclude',label:'剔除'}]}/></label><label>合同关联（集采）<Select aria-label="合同关联" disabled={!['','jc'].includes(filters.category)} value={filters.link} onChange={value=>setFilters(f=>({...f,link:value}))} options={[{value:'',label:'全部'},{value:'no',label:'未关联'},{value:'yes',label:'已关联'}]}/></label>
      <label>审批状态<Select aria-label="审批状态" disabled={filters.category === 'exclude'} value={filters.approval} onChange={value=>setFilters(f=>({...f,approval:value}))} options={[{value:'',label:'全部'},...['已批','未批'].map(value=>({value,label:value}))]}/></label><label>付款状态<Select aria-label="付款状态" disabled={filters.category === 'exclude'} value={filters.paid} onChange={value=>setFilters(f=>({...f,paid:value}))} options={[{value:'',label:'全部'},...['已付清','未付清'].map(value=>({value,label:value}))]}/></label>{filters.pending && <span className="notice-pending-chip">只看{filters.pending === 'ownership' ? '待指定归属' : '撤单有牵涉'}<Button htmlType="submit" aria-label="清除待办筛选" onClick={() => setFilters(f => ({ ...f, pending: '' }))}>×</Button></span>}<label className="notice-search-field">搜索<Input aria-label="通知书搜索" type="search" allowClear placeholder="搜索各列内容" value={search} onChange={e => setSearch(e.target.value)} /></label><Button htmlType="submit" onClick={() => { setFilters(defaults()); setSearch(''); setPasteScope(null); }}>重置</Button>
      <Button htmlType="submit" disabled={unavailable || Boolean(draft)} onClick={() => setPasteOpen(true)}>粘贴单据号勾选</Button></div>
      <NoticePaste open={pasteOpen} blocked={blocked || !active} close={() => setPasteOpen(false)} read={async () => { const latest = await query.refetch({ throwOnError: true }); return latest.data!; }} apply={ids => { setPasteScope(null); setFilters({ ...defaults(), paid: '' }); setSearch(''); setPicked(new Set(ids)); setPasteTop(new Set(ids)); requestAnimationFrame(() => api.current?.ensureIndexVisible(0, 'top')); }} process={ids => { setPicked(new Set()); setPasteScope(ids); setFilters({ ...defaults(), paid: '', category: 'exclude' }); setSearch(''); }} />
      {pasteScope && <p className="notice-feedback">仅显示本次已剔除或撤单单据<Button htmlType="submit" onClick={() => setPasteScope(null)}>清除此筛选</Button></p>}
      {feedback && <p className="notice-feedback" role="status">{feedback}</p>}{error && <p className="notice" role="alert">{error}<Button htmlType="submit" disabled={busy} onClick={() => void refresh().then(() => setError('')).catch(e => setError(e.message))}>重读核对</Button></p>}
      {query.isError && query.data && <p className="notice" role="alert">列表更新失败，保留上次结果。{query.error.message}<Button htmlType="submit" onClick={() => void query.refetch()}>重试读取</Button></p>}{query.isPending ? <p className="state" role="status">正在读取付款通知书…</p> : query.isError && !query.data ? <p className="notice" role="alert">{query.error.message}<Button htmlType="submit" onClick={() => void query.refetch()}>重试</Button></p> : <><p className="notice-count">显示 {shown.length} 条；当前时间范围有效 {rows.filter(r => inTime(r, filters) && live(r)).length} 条；剔除 {rows.filter(r => inTime(r, filters) && r.is_excluded).length} 条；i8 已撤单 {rows.filter(r => inTime(r, filters) && r.is_revoked).length} 条（切「分类＝剔除」查看）</p>{busy && <p className="notice-feedback" role="status">正在保存，请稍候…</p>}<div className="notice-grid" ref={gridRoot} role="region" aria-label="付款通知书列表"><AgGridReact<NoticeRow> theme={gridTheme} rowBuffer={2} onFirstDataRendered={e => fitGridColumns(e.api, gridRoot.current, true)} onGridSizeChanged={e => fitGridColumns(e.api, gridRoot.current)} onNewColumnsLoaded={e => fitGridColumns(e.api, gridRoot.current, true)} suppressColumnVirtualisation enableCellTextSelection ensureDomOrder rowData={shown} columnDefs={columns} pinnedBottomRowData={draft && !draft.row_id ? [{ notice_id: -2 } as NoticeRow,...summary] : summary} getRowId={p => String(p.data.notice_id)} getRowClass={p => p.data?.notice_id === focusId ? 'notice-focused' : ''} defaultColDef={defaultColumn} rowHeight={pageGridGeometry(scale).rowHeight} headerHeight={pageGridGeometry(scale).headerHeight} suppressScrollOnNewData animateRows={false} postSortRows={params => { const top = params.nodes.filter(node => pasteTop.has(node.data!.notice_id)), rest = params.nodes.filter(node => !pasteTop.has(node.data!.notice_id)); params.nodes.splice(0,params.nodes.length,...top,...rest); }} onGridReady={e => { api.current = e.api; }} overlayNoRowsTemplate="当前筛选条件下没有付款通知书，请调整条件或按月抓取。" /></div></>}
      {draftUncertain && <p role="alert" className="notice">新增结果待核实。<Button disabled={blocked || busy} onClick={() => { setBusy(true); void refresh().then(() => setDraftChecked(true)).catch(failure => setError(failure instanceof Error ? failure.message : '重读失败，请重试。')).finally(() => setBusy(false)); }}>重读核对新增结果</Button><Button disabled={blocked || busy || !draftChecked} onClick={cancelDraft}>已核对，关闭草稿</Button></p>}
      {draft && <p role="status" className="notice-feedback">{draft.row_id ? `正在编辑 ${draft.bill_no}` : '新增草稿位于表尾'}，尚未保存，返回本页可继续填写。<Button htmlType="submit" disabled={unavailable} onClick={() => void saveDraft()}>保存草稿</Button><Button htmlType="submit" disabled={unavailable} onClick={cancelDraft}>取消草稿</Button></p>}
      <OwnershipPending blocked={blocked || !active} open={row => setMaintenance({kind:'ownership',row})} />
      {autoIds&&<AutoLinkDialog ids={autoIds} blocked={blocked||!active} close={()=>setAutoIds(null)} refresh={refresh} announce={setFeedback} />}
      {maintenance && <NoticeDialog state={maintenance} projects={projects.data ?? []} blocked={blocked || !active} close={() => { const id=maintenance.row.notice_id, linking=maintenance.kind === 'link'; setMaintenance(null); if(linking) requestAnimationFrame(() => gridRoot.current?.querySelector<HTMLButtonElement>(`[data-contract-notice="${id}"]`)?.focus({preventScroll:true})); }} refresh={refresh} announce={setFeedback} />}
      {projects.isError && <p className="notice" role="alert">{projects.error.message}<Button htmlType="submit" onClick={() => void projects.refetch()}>重读项目</Button></p>}
    </section>
    {print && <NoticePrint rows={print.rows} mode={print.mode} blocked={blocked || !active} close={()=>{printLock.current=false;setPrint(null);}} />}
    {flowNotice && <NoticeFlows notice={flowNotice} blocked={blocked || !active} close={()=>setFlowNotice(null)} />}
    {printerOpen && <PrinterSettings blocked={blocked || !active} close={()=>setPrinterOpen(false)} />}
    {payIds && <NoticePayment projects={projects.data ?? []} ids={payIds} overrides={payOverrides} blocked={blocked || !active} remove={id => { pick(id,false);setPayIds(ids => ids?.filter(x => x !== id) ?? null); }} close={() => setPayIds(null)} paid={paid} refresh={refresh} announce={setFeedback} />}
    {fetchOpen && <NoticeFetch me={me} blocked={blocked || !active} close={() => setFetchOpen(false)} refresh={refresh} />}
    <BusinessModal open={exportOpen && active && !blocked} className="project-dialog" titleId="notice-export-title" requestClose={exportClosing.requestClose}><DialogContents titleId="notice-export-title" title="导出付款通知书台账" closing={exportClosing}><p>导出当前筛选的 {shown.length} 条通知书，按表格显示顺序排列。</p>{error && <p className="notice" role="alert">{error}</p>}<div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={exportClosing.requestClose}>取消</Button><Button htmlType="submit" className="primary" disabled={unavailable || !shown.length} onClick={() => void exportExcel()}>保存到本地</Button></div></DialogContents></BusinessModal>
  </div>;
}
