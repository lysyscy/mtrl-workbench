import { DialogPresence } from './workspace-motion';
import Input from 'antd/es/input';
import App from 'antd/es/app';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import Checkbox from 'antd/es/checkbox';
import { EnumTag } from './enum-tag';
import Button from 'antd/es/button';
import { readHistory, useHistoryGuard } from './history';
import { BusinessModal } from './business-modal';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { AgGridReactProps } from 'ag-grid-react';
import type { ColDef, GridApi, ICellRendererParams, PostSortRowsParams } from 'ag-grid-community';
import { ApiError, confirmWrite, uncertainWrite, projectLabel, readProjects, record, requestJson } from './api';
import type { Identity } from './api';
import { ProjectPicker } from './ledger-controls';
import { cacheFontMeasurement, contentWidth, fixedWidth, gridTheme, numberColumnWidth, textWidth } from './grid';
import { completeColumnWidth, EllipsisText } from './grid-text';
import { archiveLabel, body, categories, cents, decimal, live, money, moneyKeys, readNotices, receipt, searchKey, selectable, total } from './notices-api';
import type { MoneyKey, NoticeRow } from './notices-api';
import { NoticeFetch } from './notice-fetch';
import { NoticePaste } from './notice-paste';
import { AutoLinkDialog } from './notice-auto-link';
import { DraftField, manualDraft, NoticeDeleteDialog } from './notice-maintenance';
import { OwnershipDialog, OwnershipPending, refreshNoticeOwnershipPending } from './ownership';
import type { OwnershipDocument } from './ownership';
import { NoticeCells, StatCell, useNoticeCellSaves } from './notice-cell-save';
import { ContractDialog } from './notice-contract';
import type { Draft } from './notice-maintenance';
import { NoticePayment, PayAmountCell, paymentValue, amount } from './notice-payment';
import type { PayOverride } from './notice-payment';
import { NoticePrint, PrinterSettings, recoverNoticePrint } from './notice-print';
import type { BatchView } from './notice-print';
import { ReadFailure, ReadPlaceholder, ReadStatusLane, readPhase } from './read-region';
import { NoticeFlows } from './notice-flows';
import { TimePicker, timeMatches, timeRange } from './time-picker';
import { DialogContents, useDialogClose } from './dialog-close';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
const noticeRowId = (row: NoticeRow) => String(row.notice_id);
interface Filters { period: string; projects: number[]; category: string; approval: string; paid: string; link: string; pending: '' | 'ownership' | 'void' }
type NoticeDialogState = { kind: 'delete' | 'link'; row: NoticeRow } | { kind: 'ownership'; document: OwnershipDocument };
const defaults = (): Filters => ({ period: '全部', projects: [], category: '', approval: '', paid: '未付清', link: '', pending: '' });
interface RenderState { viewFlows: (row: NoticeRow) => void; unavailable: boolean; shown: NoticeRow[]; picked: Set<number>; action: (path: string, payload: unknown, clear?: boolean) => Promise<boolean>; pick: (id: number, checked: boolean) => void; chooseAll: (checked: boolean) => void; draft: Draft | null; begin: (row?: NoticeRow) => void; saveDraft: () => Promise<void>; cancelDraft: () => void; open: (kind: NoticeDialogState['kind'], row: NoticeRow) => void; payOverrides: Record<number,PayOverride>; payDrafts: Record<number,PayOverride>; editPay: (row: NoticeRow, value: string | null) => void; setPay: (row: NoticeRow, value: string) => void; draftCell: (row: NoticeRow, field: keyof Draft, label: string) => React.ReactNode; }
const amountNames: Record<MoneyKey, string> = { amount_approved: '审批金额', pay_amount: '付款金额', amount_paid: '已付金额', stat_settle: '统计结算金额', stat_paid: '统计付款金额' };
const defaultColumn: ColDef<NoticeRow> = { cellDataType: false, sortable: true, resizable: true, suppressMovable: true, wrapHeaderText: false };

function noticeSummary(rows: NoticeRow[]): NoticeRow[] {
  const liveRows = rows.filter(live);
  return liveRows.length ? [{ notice_id: -1, bill_no: '合计', ...Object.fromEntries(moneyKeys.map(key => [key, total(liveRows, key)])) } as NoticeRow] : [];
}

function noticeWidths(shown: NoticeRow[], summary: NoticeRow[], scale: number) {
  const date = Math.max(100, numberColumnWidth(shown.map(row => row.doc_date), 1).minWidth);
  const code = Math.max(142, numberColumnWidth(shown.map(row => row.bill_no), 1).minWidth);
  const widths: Record<string, Partial<ColDef<NoticeRow>>> = {
    doc_date: contentWidth(date, 200, scale),
    bill_no: contentWidth(code, Math.max(code, 360), scale),
    category_label: completeColumnWidth([...Object.values(categories), ...shown.map(archiveLabel)], '分类', scale, 32),
    biz_type: completeColumnWidth(shown.map(row => row.biz_type), '业务类型', scale),
    input_by: completeColumnWidth(shown.map(row => row.input_by), '录入人', scale),
    approve_status: completeColumnWidth(shown.map(row => row.approve_status), '审批状态', scale, 12),
    pay_status: completeColumnWidth(shown.map(row => row.pay_status), '付款状态', scale, 12),
    actions: completeColumnWidth(shown.map(row => [row.has_any_flow ? '查看流水' : '', cents(row.amount_paid) > 0n ? '撤销付款' : '', row.is_manual ? '手动 编辑 删除' : ''].filter(Boolean).join(' ')), '操作', scale, 64),
  };
  for (const key of moneyKeys) {
    const values = [...shown, ...summary].map(row => money(row[key]));
    const editable = key === 'pay_amount' || key === 'stat_settle' || key === 'stat_paid' || key === 'amount_approved' && shown.some(row => row.is_manual);
    const display = numberColumnWidth(values, 1, false).minWidth;
    const input = editable ? numberColumnWidth(shown.map(row => row[key]), 1, true).minWidth : 0;
    const min = Math.max(display, input, completeColumnWidth([], amountNames[key], 1).minWidth);
    widths[key] = contentWidth(min, Math.max(min, 180), scale);
  }
  return widths;
}

const NoticeSelectionContext = createContext<RenderState>(null!);
function NoticeSelectionHeader() {
  const current = useContext(NoticeSelectionContext), ids = current.shown.filter(selectable).map(row => row.notice_id), count = ids.filter(id => current.picked.has(id)).length;
  return <Checkbox aria-label="全选当前筛选结果" checked={ids.length > 0 && count === ids.length} indeterminate={count > 0 && count < ids.length} disabled={current.unavailable || !ids.length} onChange={event => current.chooseAll(event.target.checked)} />;
}

function inTime(r: NoticeRow, f: Filters): boolean { return timeMatches(f.period, r.doc_date); }
function scopeHit(r: NoticeRow, f: Filters): boolean {
  const arch = f.category === 'exclude';
  return inTime(r, f) && (!f.projects.length || f.projects.includes(r.ownership_id ?? 0)) &&
    (!f.pending || (f.pending === 'ownership' ? !r.ownership_id : r.is_revoked)) &&
    (arch ? r.is_excluded || r.is_revoked : live(r) && (!f.category || f.category === r.category) && (!f.approval || f.approval === r.approve_status) && (!f.paid || f.paid === r.pay_status) && (!f.link || r.category === 'jc' && (f.link === 'yes' ? r.has_link : !r.has_link)));
}
export function NoticesPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const { message } = App.useApp();
  const client = useQueryClient(), api = useRef<GridApi<NoticeRow> | null>(null), gridRoot = useRef<HTMLDivElement>(null), pageRoot = useRef<HTMLDivElement>(null), lock = useRef(false), mounted = useRef(true);
  const [filters, setFilters] = useState(defaults), [search, setAppliedSearch] = useState(''), [picked, setPicked] = useState<Set<number>>(() => new Set());
  const [busy, setBusy] = useState(false), [warning, setWarning] = useState(''), [error, setError] = useState(''), [fetchOpen, setFetchOpen] = useState(false), [exportOpen, setExportOpen] = useState(false), [pasteOpen,setPasteOpen] = useState(false), [pasteTop,setPasteTop] = useState<Set<number>>(() => new Set()), [pasteScope,setPasteScope] = useState<number[] | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const composing = useRef(false), searchTimer = useRef(0);
  useEffect(() => () => window.clearTimeout(searchTimer.current), []);
  function setSearch(value: string) {
    window.clearTimeout(searchTimer.current);
    setSearchInput(value);
    setAppliedSearch(value);
  }
  function typeSearch(value: string) {
    window.clearTimeout(searchTimer.current);
    setSearchInput(value);
    if (composing.current) return;
    // Let a burst of keystrokes settle before publishing a new grid scope.
    searchTimer.current = window.setTimeout(() => setAppliedSearch(value), 100);
  }
  const searchBusy = searchInput !== search;
  function announce(text: string, needsAttention = false) {
    if (needsAttention) { message.destroy('notice-success'); setWarning(text); }
    else { void message.success({key: 'notice-success', content: text, duration: 3}); }
  }
  const printLock = useRef(false);
  const [flowNotice,setFlowNotice] = useState<NoticeRow|null>(null);
  const [print,setPrint] = useState<{mode:'pdf'|'print';rows:NoticeRow[];resumed?:BatchView}|null>(null),[printerOpen,setPrinterOpen] = useState(false);
  const printOwner = me?.account ?? '';
  const recoveredPrintOwner = useRef('');
  useEffect(() => {
    if (!active || blocked || !printOwner || recoveredPrintOwner.current === printOwner) return;
    const attempt = new AbortController();
    void recoverPrint(attempt.signal);
    return () => attempt.abort();
  }, [active, blocked, printOwner]);

  async function recoverPrint(signal?: AbortSignal) {
    if (!printOwner || printLock.current) return;
    try {
      const resumed = await recoverNoticePrint(printOwner, signal);
      if (signal?.aborted || !mounted.current) return;
      recoveredPrintOwner.current = printOwner;
      if (!resumed) {
        if (!signal) void message.info('当前没有可查看的打印批次。');
        return;
      }
      if (printLock.current) return;
      printLock.current = true;
      setPrint({mode: 'print', rows: [], resumed});
    } catch (failure) {
      if (signal?.aborted || !mounted.current || (failure instanceof DOMException && failure.name === 'AbortError')) return;
      if (!signal) void message.error(failure instanceof Error ? failure.message : '无法读取原打印批次，请重试。');
    }
  }
  const [params] = useSearchParams();
  const [payIds,setPayIds] = useState<number[]|null>(null), [payOverrides,setPayOverrides] = useState<Record<number,PayOverride>>({});
  const payDrafts = useRef<Record<number,PayOverride>>({});
  const [payError,setPayError] = useState('');
  function editPay(row: NoticeRow, value: string | null) {
    if (value === null) delete payDrafts.current[row.notice_id];
    else payDrafts.current[row.notice_id] = {value,basis:`${row.amount_approved}:${row.amount_paid}`};
    setPayError('');
  }
  function setPay(row: NoticeRow, value: string) { setPayOverrides(old => ({ ...old, [row.notice_id]: { value, basis: `${row.amount_approved}:${row.amount_paid}` } })); }
  function paid(ids: number[]) { setPayOverrides(old => Object.fromEntries(Object.entries(old).filter(([id]) => !ids.includes(Number(id))))); setPicked(new Set()); }
  useEffect(() => { const listener=(event:Event)=> { const id=Number((event as CustomEvent<number>).detail);delete payDrafts.current[id];setPayOverrides(old=>Object.fromEntries(Object.entries(old).filter(([key])=>Number(key)!==id))); };window.addEventListener('payment-revoked',listener);return()=>window.removeEventListener('payment-revoked',listener); },[]);
  const [autoIds,setAutoIds] = useState<number[]|null>(null);
  const draftRef = useRef<Draft | null>(null), pendingFocus = useRef(0);
  const [draftUncertain, setDraftUncertain] = useState(false), [draftChecked, setDraftChecked] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null), [maintenance, setMaintenance] = useState<NoticeDialogState | null>(null), [focusId,setFocusId] = useState(0);
  useEffect(() => { if (!active) return; const id=Number(params.get('notice'));if(id>0){pendingFocus.current=id;setFocusId(id);setFilters({...defaults(),period:'全部',paid:''});setSearch('');setPasteScope(null);} }, [params.get('notice'), active]);
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
  const shown = useMemo(() => {
    if (!needle) return scope;
    const matches = scope.filter(r => [r.doc_date,r.bill_no,r.project_display,r.project_name,r.category_label,r.bill_name,r.biz_type,r.payee,r.jc_supplier,r.input_by,r.approve_status,r.pay_status,archiveLabel(r),r.is_manual ? '手动' : '',r.is_overpaid ? '超付' : '',r.category === 'jc' ? r.has_link ? '已关联 查看 / 更改关联' : '关联集采合同' : '',...moneyKeys.map(k => r[k])].some(x => searchKey(x).includes(needle)));
    return matches.length === scope.length ? scope : matches;
  }, [scope, needle]);
  // Business scope changes trim selection; searching and virtual windows never do.
  useEffect(() => { const valid = new Set(scope.filter(selectable).map(r => r.notice_id)); setPicked(old => { const next = new Set([...old].filter(id => valid.has(id))); return next.size === old.size ? old : next; }); }, [filters]);
  useEffect(() => { const valid = new Set(rows.filter(selectable).map(r => r.notice_id)); setPicked(old => { const next = new Set([...old].filter(id => valid.has(id))); return next.size === old.size ? old : next; }); }, [rows]);
  const selected = useMemo(() => rows.filter(row => picked.has(row.notice_id)), [rows, picked]);
  const shownIds = useMemo(() => new Set(shown.map(row => row.notice_id)), [shown]);
  const hidden = useMemo(() => selected.filter(row => !shownIds.has(row.notice_id)).length, [selected, shownIds]);
  const selectedPay = useMemo(() => selected.filter(row => !row.is_excluded && !row.is_revoked), [selected]);
  const selectedAmounts = useMemo(() => ({ approved: money(total(selectedPay, 'amount_approved')), due: money(total(selectedPay, 'pay_amount')) }), [selectedPay]);
  const scale = Number(me?.ui_scale_css) || 1;
  const scopeDisplay = useMemo(() => {
    const summary = noticeSummary(scope);
    return { summary, widths: cacheFontMeasurement(() => noticeWidths(scope, summary, scale)) };
  }, [scope, scale]);
  const summary = useMemo(() => shown === scope ? scopeDisplay.summary : noticeSummary(shown), [shown, scope, scopeDisplay]);
  const cellSaves = useNoticeCellSaves({ rows: query.data, enabled: active && !blocked && Boolean(me),
    canWrite: !busy && !draft && !draftUncertain && !query.isPending && !query.isError, read: refresh });
  const cellDirty = Object.keys(cellSaves.drafts).length > 0;
  const unavailable = draftUncertain || blocked || !active || !me || busy || cellSaves.busy || cellSaves.uncertain || cellDirty || query.isPending || query.isError || query.isFetching;
  // The list owns one read state: the first read keeps a skeleton in the reserved table box,
  // a failed reread keeps the rows it already published, and only the status lane reports it.
  const readState = readPhase(query, query.data !== undefined && rows.length === 0);
  // Nothing has been published yet, so the table area holds its reserved box with a quiet skeleton.
  const placeheld = readState === 'idle' || readState === 'reading' || readState === 'error';
  useHistoryGuard('notices', () => busy || lock.current ? '付款通知书正在处理，请稍候。' : draftRef.current ? '付款通知书有未保存输入，请先处理。' : '');
  const actionsUnavailable = unavailable || searchBusy;
  const batchUnavailable = actionsUnavailable || !picked.size || hidden > 0;
  const batchReason = hidden ? '当前列表外还有勾选，请先清空搜索核对' : !picked.size ? '请先勾选通知书' : !me ? '请先登录' : '';
  function openPayment() {
    if (batchUnavailable || !selectedPay.length || draft) return;
    const next = {...payOverrides};
    for (const row of selectedPay) {
      const input = payDrafts.current[row.notice_id];
      if (!input || input.basis !== `${row.amount_approved}:${row.amount_paid}`) continue;
      const value = input.value.trim() ? amount(input.value) : decimal(cents(row.amount_approved)-cents(row.amount_paid));
      if (value === null) {
        setPayError(`${row.bill_no}：付款金额不合法，请修改后再付款。`);
        const node = api.current?.getRowNode(String(row.notice_id));
        if (node) api.current?.ensureNodeVisible(node,'middle');
        api.current?.ensureColumnVisible('pay_amount');
        requestAnimationFrame(() => pageRoot.current?.querySelector<HTMLInputElement>(`[data-pay-notice="${row.notice_id}"]`)?.focus());
        return;
      }
      next[row.notice_id] = {...input,value};
    }
    for (const row of selectedPay) delete payDrafts.current[row.notice_id];
    setPayError('');setPayOverrides(next);setPayIds([...picked]);
  }
  async function refresh(scope:'notice'|'ownership'|'fetch'='notice') {
    await client.invalidateQueries({refetchType:'none'});
    await client.cancelQueries({queryKey:['notices'],exact:true});
    const data = await client.fetchQuery({queryKey:['notices'],staleTime:0,queryFn:async({signal})=>readNotices(await requestJson('/api/m03/notice-list?period=',{signal}))});
    if(scope==='ownership')await projects.refetch({throwOnError:true});
    if(scope==='fetch')await refreshNoticeOwnershipPending(client);
    if(me){const queryKey=['history',`${me.id}:${me.account}`];await client.cancelQueries({queryKey,exact:true});await client.fetchQuery({queryKey,staleTime:0,queryFn:async({signal})=>readHistory(await requestJson('/api/history/status',{signal}))});}
    return data;
  }
  function cancelDraft() { draftRef.current = null; setDraft(null); setDraftUncertain(false); setDraftChecked(false); }
  function begin(row?: NoticeRow) {
    if (actionsUnavailable || draftRef.current) return;
    const next = manualDraft(row); if (!row && filters.period !== '全部') next.doc_date = timeRange(filters.period).dateFrom; draftRef.current = next; setDraft(next);
    setFilters(f => ({ ...f, period: next.doc_date.slice(0,7), category: '', approval: '', paid: '', link: '' })); setSearch('');
    if (row) { pendingFocus.current=row.notice_id;setFocusId(row.notice_id); api.current?.ensureNodeVisible(node => node.data?.notice_id === row.notice_id, 'middle'); }
    api.current?.refreshCells({ force: true });
  }
  async function saveDraft() {
    const currentDraft = draftRef.current; if (!currentDraft || draftUncertain || actionsUnavailable || lock.current) return;
    lock.current = true;setBusy(true);setError('');setWarning('');message.destroy('notice-success');let saved = false;
    try {
      const value = await requestJson('/api/m03/actions/manual-save',{ method: 'POST', ...body(currentDraft) });
      if (!mounted.current) return;
      confirmWrite(record(value) && value.ok === true && typeof value.row_id === 'string' && /^[1-9]\d*$/.test(value.row_id) && Number.isSafeInteger(Number(value.row_id)) && typeof value.message === 'string', '保存结果待核实，请重读列表核对，勿重复新增。'); saved = true;
      const id = record(value) ? Number(value.row_id) : 0; cancelDraft();
      const text = receipt(value);
      setFilters(f => ({ ...f, period: currentDraft.doc_date.slice(0,7), category: '', approval: '', paid: '', link: '', projects: f.projects.length && !f.projects.includes(Number(currentDraft.ownership_id)) ? [...f.projects,Number(currentDraft.ownership_id)] : f.projects })); setSearch('');pendingFocus.current=id;setFocusId(id);
      await refresh();
      announce(text);
    } catch (failure) { if (!mounted.current) return; const unknown = !saved && uncertainWrite(failure); setDraftUncertain(unknown); setDraftChecked(false); setError(`${saved ? '已保存，但列表尚待重读核对，勿重复新增。' : unknown ? '保存结果待核实，草稿已保留；勿重复新增。' : '保存失败，草稿已保留。'}${failure instanceof Error ? failure.message : '请重试。'}`); }
    finally { lock.current=false;setBusy(false); }
  }
  function draftCell(_row: NoticeRow, field: keyof Draft, label: string) { return <DraftField key={`${draftRef.current?.row_id || 'new'}:${field}`} draft={draftRef.current!} field={field} label={label} disabled={busy || blocked} projects={projects.data ?? []} />; }
  useEffect(() => { if (focusId && pendingFocus.current === focusId && active && !query.isFetching) requestAnimationFrame(() => { const node=api.current?.getRowNode(String(focusId));if(node){api.current?.ensureNodeVisible(node,'middle');pendingFocus.current=0;} }); }, [focusId,shown,query.isFetching,active]);
  async function action(path: string, payload: unknown, clear = false): Promise<boolean> {
    if (actionsUnavailable || lock.current) return false;
    lock.current = true; setBusy(true); setError(''); setWarning(''); message.destroy('notice-success'); let saved = false;
    try {
      const value = await requestJson(path, { method: 'POST', ...body(payload) }); saved = true;
      if (!mounted.current) return false;
      const text = receipt(value), attention = record(value) && typeof value.warning === 'string' ? value.warning : '';
      if (clear) setPicked(new Set()); await refresh();
      if(attention)announce(attention,true);
      else if(path!=='/api/m03/actions/stat'&&path!=='/api/m03/actions/manual-save')announce(text);
      return true;
    } catch (failure) { if (mounted.current) setError(`${saved ? '操作已完成，但读取失败；请重读核对，勿重复操作。' : ''}${failure instanceof Error ? failure.message : '操作未完成，请重试。'}`); return saved; }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  function startPrint(mode: 'print'|'pdf') { if (actionsUnavailable || printLock.current || !picked.size || draft) return; printLock.current=true;setPrint({mode,rows:rows.filter(r=>picked.has(r.notice_id))}); }
  function pick(id: number, checked: boolean) { if (searchBusy) return; setPicked(old => { const next = new Set(old); if (checked) next.add(id); else next.delete(id); return next; }); }
  function chooseAll(checked: boolean) { if (searchBusy) return; setPicked(old => { const next = new Set(old); for (const r of shown.filter(selectable)) { if (checked) next.add(r.notice_id); else next.delete(r.notice_id); } return next; }); }
  const current = useRef<RenderState>(null!); current.current = { viewFlows: setFlowNotice, unavailable, shown, picked, action, pick, chooseAll, draft, begin, saveDraft, cancelDraft, open: (kind, row) => setMaintenance(kind === 'ownership'
    ? { kind, document: { source: 'notice', number: row.bill_no, name: row.bill_name, project: row.project_name, noticeId: row.notice_id } }
    : { kind, row }), payOverrides, payDrafts:payDrafts.current, editPay, setPay, draftCell };
  const refreshed = useRef<{ grid: GridApi<NoticeRow>; rows: NoticeRow[]; draft: Draft | null; unavailable: boolean; picked: Set<number> } | null>(null);
  useEffect(() => {
    const grid = api.current, root = gridRoot.current;
    if (!active || !grid || !root) { refreshed.current = null; return; }
    // The header observes selection directly. Checking a row only changes its
    // checkbox, so keep the other cells and their editors mounted.
    const refresh = () => {
      if (grid.isDestroyed()) return;
      const prior = refreshed.current;
      if (prior?.grid === grid && prior.rows === rows && prior.draft === draft && prior.unavailable === unavailable) {
        const rowNodes = grid.getRenderedNodes().filter(node => node.data && prior.picked.has(node.data.notice_id) !== picked.has(node.data.notice_id));
        if (rowNodes.length) grid.refreshCells({ columns: ['pick'], rowNodes, force: true });
      } else {
        grid.refreshCells({ columns: ['pick', 'project_display', 'category_label', 'jc_supplier', 'actions', 'pay_amount'], force: true });
      }
      refreshed.current = { grid, rows, draft, unavailable, picked };
    };
    const editor = root.contains(document.activeElement) && document.activeElement?.matches('input:not([type="checkbox"]),select,textarea') ? document.activeElement : null;
    if (!editor) { refresh(); return; }
    // The current action guard remains authoritative while this renderer retains
    // its local input. Rebuilding any part of its row can replace the editor.
    let frame = 0;
    const released = () => { frame = requestAnimationFrame(refresh); };
    editor.addEventListener('blur', released, {once: true});
    return () => { cancelAnimationFrame(frame); editor.removeEventListener('blur', released); };
  }, [active, picked, rows, unavailable, draft]);
  const widths = useMemo(() => shown === scope
    ? scopeDisplay.widths() : noticeWidths(shown, summary, scale), [scope, scopeDisplay, shown, summary, scale]);
  // Amount blur updates the data and measured widths during the following click.
  // Keep both checkbox component types stable while the other columns resize.
  const selectionColumn = useMemo<ColDef<NoticeRow>>(() => ({
    colId: 'pick', headerName: '', pinned: 'left', ...fixedWidth(36, scale), sortable: false,
    headerComponent: NoticeSelectionHeader,
    cellRenderer: (p: ICellRendererParams<NoticeRow>) => {
      const draft = current.current.draft;
      if (draft && (p.data?.notice_id === -2 || String(p.data?.notice_id) === draft.row_id)) return <span className="notice-tag">草稿</span>;
      return p.node.rowPinned ? '' : <Checkbox aria-label={`勾选${p.data!.bill_no}`} disabled={current.current.unavailable || !selectable(p.data!)} checked={current.current.picked.has(p.data!.notice_id)} onChange={e => current.current.pick(p.data!.notice_id, e.target.checked)} />;
    },
  }), [scale]);
  const baseColumns = useMemo<ColDef<NoticeRow>[]>(() => ([
    selectionColumn,
    { field: 'doc_date', headerName: '单据日期', pinned: 'left', wrapText: false }, { field: 'bill_no', tooltipField: 'bill_no', headerName: '单据编码', pinned: 'left', wrapText: false },
    { field: 'project_display', headerName: '付款项目', ...textWidth(96, 160, scale, 1), cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : p.data!.ownership_id ? <EllipsisText text={p.data!.project_display} fullText={p.data!.project_name||p.data!.project_display}/> : <Button htmlType="submit" className="project-link" disabled={current.current.unavailable} onClick={() => current.current.open('ownership',p.data!)}>待指定归属</Button> },
    { field: 'category_label', headerName: '分类', wrapText: true, cellRenderer: (p: ICellRendererParams<NoticeRow>) => { if (p.node.rowPinned) return ''; const r = p.data!, label = archiveLabel(r); return label ? <span><span className={`notice-tag ${r.is_excluded ? r.exclude_source : 'revoked'}`} title={r.exclude_rule_hint}>{label}</span>{r.is_revoked && (cents(r.amount_paid) > 0n || r.has_link) && <span className="notice-tag rule notice-revoke-hint">请先撤销付款 / 解绑关联</span>}</span> : <Select className="notice-category-select" aria-label={`${r.bill_no}分类`} value={r.category} disabled={current.current.unavailable} onChange={value => void current.current.action('/api/m03/actions/category', { ids: [r.notice_id], category: value })} options={Object.entries(categories).map(([value,label])=>({value,label}))} popupMatchSelectWidth={false} labelRender={option=><EnumTag kind="category" value={String(option.label)}/>}/>; } },
    ...(['bill_name','biz_type','payee','jc_supplier','input_by'] as const).map((key, index): ColDef<NoticeRow> => ({ field: key, headerName: ['单据名称','业务类型','收款单位','集采实际供应商','录入人'][index]!, ...(key==='biz_type'||key==='input_by' ? {} : key==='bill_name' ? textWidth(128,280,scale,2) : key==='payee' ? textWidth(112,240,scale,2) : textWidth(180,280,scale,1)),
      ...(key === 'jc_supplier' ? { cellRenderer: (p: ICellRendererParams<NoticeRow>) => { const r=p.data!; if(p.node.rowPinned || (r.category !== 'jc' || r.is_excluded || r.is_revoked) && !r.has_link) return '—'; return <Button data-contract-notice={r.notice_id} className="notice-association-trigger" htmlType="button" aria-label={`${r.bill_no}供应商与合同关联`} disabled={current.current.unavailable} onClick={() => current.current.open('link',r)}><EllipsisText text={r.jc_supplier || '选择供应商与合同'}/><small>{r.has_link ? '已关联合同' : '未关联合同'}</small></Button>; } } : key==='bill_name'||key==='payee' ? {cellRenderer:(p:ICellRendererParams<NoticeRow>)=><EllipsisText text={String(p.value??'')}/>} : {}) })),
    ...moneyKeys.map((key): ColDef<NoticeRow> => ({ field: key, headerName: amountNames[key], cellClass: 'money', comparator: (a: string, b: string) => cents(a) < cents(b) ? -1 : cents(a) > cents(b) ? 1 : 0,
      cellRenderer: (p: ICellRendererParams<NoticeRow>) => !p.node.rowPinned && key === 'pay_amount' ? <PayAmountCell row={p.data!} override={current.current.payOverrides[p.data!.notice_id]} draft={current.current.payDrafts[p.data!.notice_id]} edit={current.current.editPay} change={current.current.setPay} disabled={current.current.unavailable || p.data!.is_excluded || p.data!.is_revoked} /> : !p.node.rowPinned && (key === 'stat_settle' || key === 'stat_paid' || key === 'amount_approved' && p.data!.is_manual) ? <StatCell row={p.data!} field={key} /> : <span>{money(p.data![key])}{!p.node.rowPinned && key === 'amount_paid' && p.data!.is_overpaid && <span className="notice-tag rule">超付</span>}</span> })),
    { field: 'approve_status', headerName: '审批状态', cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : <Tag className={`status-tag ${p.value === '已批' ? 'status-positive' : 'status-pending'}`}>{p.value || '—'}</Tag> }, { field: 'pay_status', headerName: '付款状态', cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : <Tag className={`status-tag ${p.value === '已付清' ? 'status-positive' : 'status-pending'}`}>{p.value || '—'}</Tag> },
    { colId: 'actions', headerName: '操作', wrapText: true, sortable: false, cellRenderer: (p: ICellRendererParams<NoticeRow>) => p.node.rowPinned ? '' : <div className="notice-row-actions">{p.data!.has_any_flow && <Button htmlType="submit" disabled={current.current.unavailable} onClick={() => current.current.viewFlows(p.data!)}>查看流水</Button>}{cents(p.data!.amount_paid)>0n && <Link className="row-button danger" to={`/ledger?notice=${p.data!.notice_id}`}>撤销付款</Link>}{p.data!.is_manual && <><span className="notice-tag">手动</span><Button htmlType="submit" disabled={current.current.unavailable || Boolean(current.current.draft)} onClick={() => current.current.begin(p.data!)}>编辑</Button><Button htmlType="submit" className="danger" disabled={current.current.unavailable || Boolean(current.current.draft)} onClick={() => current.current.open('delete',p.data!)}>删除</Button></>}</div> },
  ] as ColDef<NoticeRow>[]).map((column: ColDef<NoticeRow>): ColDef<NoticeRow> => {
    if (column.colId === 'pick') return column;
    const original = column.cellRenderer;
    const mapping: Record<string,keyof Draft> = { doc_date:'doc_date',bill_no:'bill_no',project_display:'ownership_id',category_label:'category',bill_name:'bill_name',biz_type:'biz_type',payee:'payee',amount_approved:'amount_approved',stat_settle:'stat_settle',stat_paid:'stat_paid',approve_status:'approve_status' };
    return { ...column, wrapText:false, wrapHeaderText:false, cellRenderer: (p: ICellRendererParams<NoticeRow>) => {
      const d = current.current.draft, editing = d && (p.data?.notice_id === -2 || String(p.data?.notice_id) === d.row_id);
      if (p.data?.notice_id === -2 && !d) return '';
      if (!editing) { const content = original ? original(p) : p.value ?? ''; return column.wrapText ? <div style={{width: '100%', minWidth: 0}}>{content}</div> : content; }
      if (column.colId === 'actions') return <div className="notice-row-actions"><Button htmlType="submit" disabled={current.current.unavailable} onClick={() => void current.current.saveDraft()}>保存</Button><Button htmlType="submit" disabled={current.current.unavailable} onClick={current.current.cancelDraft}>取消</Button></div>;
      const field = mapping[column.field ?? '']; return field ? current.current.draftCell(p.data!,field,column.headerName ?? '') : '—';
    } };
  }), [scale,Boolean(draft),selectionColumn]);
  const columns = useMemo(() => baseColumns.map(column => {
    const width = widths[column.colId ?? String(column.field)];
    return width ? { ...column, ...width } : column;
  }), [baseColumns, widths]);
  const footer = useMemo(() => draft && !draft.row_id ? [{ notice_id: -2 } as NoticeRow,...summary] : summary, [draft,summary]);
  const measurement = useMemo(() => ({signature:(row:NoticeRow,id:string,pinned:boolean) => {
    const fixedInput = ['pay_amount','stat_settle','stat_paid'].includes(id) || id === 'amount_approved' && row.is_manual;
    return JSON.stringify([pinned, row.notice_id === -2, id === 'pick' ? '' : id === 'actions' ? [row.has_any_flow,cents(row.amount_paid ?? '0') > 0n,row.is_manual,Boolean(draft)] : [fixedInput ? '' : row[id as keyof NoticeRow],row.is_excluded,row.is_revoked,row.is_manual,row.has_link,row.is_overpaid,row.category]]);
  },textOnly:draft?[]:['doc_date','bill_no','biz_type','payee','input_by','bill_name','amount_approved','amount_paid']}), [draft]);
  const presentation = useGridPresentation({table: 'notices', root: gridRoot, fontRoot: pageRoot, active: active && !blocked, rows: shown, totals: footer, columns, measurement, rowId: noticeRowId, scale, scope: JSON.stringify([filters,shown === scope ? '' : needle,pasteScope]), identity: `${me?.account ?? ''}:${[...filters.projects].sort().join(',')}`});
  useEffect(() => { if (presentation.state === 'ready' && pendingFocus.current) { const node = api.current?.getRowNode(String(pendingFocus.current)); if (node) { api.current?.ensureNodeVisible(node, 'middle'); pendingFocus.current = 0; } } }, [presentation.state,shown]);
  const postSortRows = useMemo(() => (params: PostSortRowsParams<NoticeRow>) => { const top = params.nodes.filter(node => pasteTop.has(node.data!.notice_id)), rest = params.nodes.filter(node => !pasteTop.has(node.data!.notice_id)); params.nodes.splice(0,params.nodes.length,...top,...rest); }, [pasteTop]);
  const gridOptions = useMemo<AgGridReactProps<NoticeRow>>(() => ({
    theme: gridTheme, defaultColDef: defaultColumn, rowBuffer: 2,
    alwaysShowVerticalScroll: true, suppressColumnVirtualisation: true,
    enableCellTextSelection: true, ensureDomOrder: true, suppressScrollOnNewData: true, animateRows: false,
    getRowId: p => String(p.data.notice_id),
    getRowClass: p => p.data?.notice_id === focusId ? 'notice-focused' : '',
    onRowDataUpdated: e => e.api.refreshCells({ columns: ['jc_supplier'], force: true }),
    onGridReady: e => { api.current = e.api; }, postSortRows,
    overlayNoRowsTemplate: '当前筛选条件下没有付款通知书，请调整条件或按月抓取。',
  }), [focusId, postSortRows]);
  const exportClosing = useDialogClose({ busy, dirty: false, close: () => setExportOpen(false) });
  async function exportExcel() {
    if (actionsUnavailable || !shown.length || lock.current) return;
    const ids: number[] = []; api.current?.forEachNodeAfterFilterAndSort(node => { if (node.data) ids.push(node.data.notice_id); });
    lock.current = true; setBusy(true); setError('');
    try { const value = await requestJson('/api/m03/notices/export', { method: 'POST', ...body({ ids }) }); if (!record(value) || typeof value.filename !== 'string' || typeof value.content_b64 !== 'string') throw new ApiError('导出结果不完整，请重试。'); const blob = new Blob([Uint8Array.from(atob(value.content_b64), c => c.charCodeAt(0))], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }); const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = value.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setExportOpen(false); announce(`已导出 ${value.rows} 条通知书。`); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '导出失败，请重试。'); }
    finally { lock.current = false; setBusy(false); }
  }
  return <NoticeCells.Provider value={cellSaves.cells}><NoticeSelectionContext.Provider value={current.current}><div className="notices-page" ref={pageRoot}>
    <div className="notice-selection" data-page-chrome role="status"><span>已勾选 <b>{picked.size}</b> 行</span><span>审批金额 <b>{selectedAmounts.approved}</b> 元</span><span>本次应付 <b>{selectedAmounts.due}</b> 元</span>{hidden > 0 && <span className="notice-tag rule">当前列表外 {hidden} 条</span>}{picked.size > 0 && <Button htmlType="submit" onClick={() => setPicked(new Set())}>清空勾选</Button>}<span className="notice-selection-actions"><Button htmlType="submit" disabled={actionsUnavailable || Boolean(print) || !picked.size || Boolean(draft)} onClick={()=>startPrint('print')}>批量打印</Button><Button htmlType="submit" disabled={actionsUnavailable || Boolean(print) || !picked.size || Boolean(draft)} onClick={()=>startPrint('pdf')}>导出 PDF</Button><Button htmlType="button" disabled={blocked || !active || Boolean(print) || !printOwner || Boolean(draft)}
      onClick={() => void recoverPrint()}>查看打印批次</Button><Button htmlType="submit" disabled={actionsUnavailable} onClick={()=>setPrinterOpen(true)}>打印机设置</Button><Button htmlType="submit" type="primary" className="notice-pay-action" disabled={batchUnavailable || !selectedPay.length || Boolean(draft)} title={batchReason} onClick={openPayment}>付款{selectedPay.length ? `（${selectedPay.length} 条）` : ''}</Button></span></div>
    {payError && <p className="notice" role="alert">{payError}</p>}
    <section className="notice-card"><div className="notice-tools" data-page-chrome><div className="notice-batch" role="group" aria-label="已勾选通知书的批量处理"><span>批量改分类</span>{Object.entries(categories).map(([key, label]) => <Button htmlType="submit" key={key} disabled={batchUnavailable} title={batchReason} onClick={() => { if (!hidden) void action('/api/m03/actions/category', { ids: [...picked], category: key }); }}>{label}</Button>)}<Button htmlType="submit" className="danger" disabled={batchUnavailable} title={batchReason || undefined} onClick={() => { if (!hidden) void action('/api/m03/actions/exclude', { ids: [...picked] }, true); }}>批量剔除</Button><Button htmlType="submit" disabled={batchUnavailable} title={batchReason || undefined} onClick={() => { if (!hidden) void action('/api/m03/actions/restore', { ids: [...picked] }, true); }}>恢复剔除</Button></div><div className="notice-toolbar"><Button htmlType="submit" disabled={actionsUnavailable} onClick={() => setFetchOpen(true)}>按月抓取 i8</Button><Button htmlType="submit" disabled={actionsUnavailable||!shown.some(r=>live(r)&&r.category==='jc'&&!r.has_link)} onClick={()=>setAutoIds(shown.filter(r=>live(r)&&r.category==='jc'&&!r.has_link).map(r=>r.notice_id))}>批量关联集采合同</Button><Button type="primary" htmlType="submit" disabled={actionsUnavailable || Boolean(draft)} onClick={() => begin()}>手动新增</Button><Button htmlType="submit" disabled={actionsUnavailable || !shown.length} onClick={() => setExportOpen(true)}>导出 Excel</Button></div></div>
      <div className="notice-filters" data-page-chrome><div className="time-picker-field"><span>单据时间</span><TimePicker singleEntry label="单据时间" value={filters.period} modes={['月','跨月','年','全部']} onChange={period => setFilters(f => ({ ...f, period }))} /></div>
      <div className="notice-project"><span>项目</span><ProjectPicker projects={projects.data ?? []} selected={filters.projects} pick={projects => setFilters(f => ({ ...f, projects }))} multiple emptyLabel="全部项目" label="项目筛选" disabled={projects.isPending || projects.isError} /></div>
      <label>分类<Select aria-label="通知书分类" disabled={false} value={filters.category} onChange={value=>setFilters(f=>({...f,category:value, link: ''}))} options={[{value:'',label:'全部'},...Object.entries(categories).map(([value,label])=>({value,label})),{value:'exclude',label:'剔除'}]}/></label><label>合同关联（集采）<Select aria-label="合同关联" disabled={!['','jc'].includes(filters.category)} value={filters.link} onChange={value=>setFilters(f=>({...f,link:value}))} options={[{value:'',label:'全部'},{value:'no',label:'未关联'},{value:'yes',label:'已关联'}]}/></label>
      <label>审批状态<Select aria-label="审批状态" disabled={filters.category === 'exclude'} value={filters.approval} onChange={value=>setFilters(f=>({...f,approval:value}))} options={[{value:'',label:'全部'},...['已批','未批'].map(value=>({value,label:value}))]}/></label><label>付款状态<Select aria-label="付款状态" disabled={filters.category === 'exclude'} value={filters.paid} onChange={value=>setFilters(f=>({...f,paid:value}))} options={[{value:'',label:'全部'},...['已付清','未付清'].map(value=>({value,label:value}))]}/></label>{filters.pending && <span className="notice-pending-chip">只看{filters.pending === 'ownership' ? '待指定归属' : '撤单有牵涉'}<Button htmlType="submit" aria-label="清除待办筛选" onClick={() => setFilters(f => ({ ...f, pending: '' }))}>×</Button></span>}<label className="notice-search-field">搜索<Input aria-label="通知书搜索" type="search" allowClear placeholder="搜索各列内容" value={searchInput} onChange={e => typeSearch(e.target.value)} onCompositionStart={() => { window.clearTimeout(searchTimer.current); composing.current = true; }} onCompositionEnd={e => { composing.current = false; typeSearch(e.currentTarget.value); }} /></label><Button htmlType="submit" onClick={() => { setFilters(defaults()); setSearch(''); setPasteScope(null); }}>重置</Button>
      <Button htmlType="submit" disabled={actionsUnavailable || Boolean(draft)} onClick={() => setPasteOpen(true)}>粘贴单据号勾选</Button></div>
      <NoticePaste open={pasteOpen} blocked={blocked || !active} close={() => setPasteOpen(false)} read={async () => { const latest = await query.refetch({ throwOnError: true }); return latest.data!; }} apply={ids => { setPasteScope(null); setFilters({ ...defaults(), paid: '' }); setSearch(''); setPicked(new Set(ids)); setPasteTop(new Set(ids)); requestAnimationFrame(() => api.current?.ensureIndexVisible(0, 'top')); }} process={ids => { setPicked(new Set()); setPasteScope(ids); setFilters({ ...defaults(), paid: '', category: 'exclude' }); setSearch(''); }} />
      {pasteScope && <p className="notice-feedback">仅显示本次已剔除或撤单单据<Button htmlType="submit" onClick={() => setPasteScope(null)}>清除此筛选</Button></p>}
      {warning && <p className="notice" role="alert">{warning}<Button htmlType="submit" disabled={busy} onClick={() => void refresh().then(() => setWarning('')).catch(e => setError(e.message))}>重读核对</Button></p>}{error && <p className="notice" role="alert">{error}<Button htmlType="submit" disabled={busy} onClick={() => void refresh().then(() => setError('')).catch(e => setError(e.message))}>重读核对</Button></p>}
      {cellSaves.error && <p className="notice" role="alert">{cellSaves.error}<Button disabled={cellSaves.busy} onMouseDown={event=>event.preventDefault()} onClick={()=>{cellSaves.update(()=>({}));if(!cellSaves.uncertain)cellSaves.clearFeedback();}}>取消金额修改</Button></p>}
      {cellSaves.uncertain && <div className="notice-feedback"><Button disabled={blocked || cellSaves.busy} onClick={() => void cellSaves.reread('')}>重读核对金额</Button><Button disabled={blocked || cellSaves.busy || !cellSaves.verified} onClick={() => cellSaves.confirm()}>已核对，继续编辑</Button></div>}
      {cellSaves.uncertain && cellSaves.readback.map(item=><p key={item.key} className="notice" role="status">{item.bill}，{item.field}：当前输入 {item.input}，系统 {item.actual}{item.submitted !== null && `，本次提交 ${item.submitted}`}</p>)}
      <ReadStatusLane phase={readState} announce="正在读取付款通知书…" className="notice-read-status">{(readState === 'error' || readState === 'stale') && <ReadFailure read={query} retained={readState === 'stale' ? '列表更新失败，保留上次结果。' : undefined} />}{projects.isError && <ReadFailure read={projects} label="项目清单" retained="项目清单更新未成功，保留上次结果。" />}</ReadStatusLane>
      {placeheld ? <div className="notice-grid notice-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={8} quiet={readState === 'error'} /></div> : <PreparedGrid inert={searchBusy} presentation={presentation} className="notice-grid grid-single-line" role="region" aria-label="付款通知书列表" grid={gridOptions} />}
      {draftUncertain && <p role="alert" className="notice">新增结果待核实。<Button disabled={blocked || busy} onClick={() => { setBusy(true); void refresh().then(() => setDraftChecked(true)).catch(failure => setError(failure instanceof Error ? failure.message : '重读失败，请重试。')).finally(() => setBusy(false)); }}>重读核对新增结果</Button><Button disabled={blocked || busy || !draftChecked} onClick={cancelDraft}>已核对，关闭草稿</Button></p>}
      {draft && <p role="status" className="notice-feedback">{draft.row_id ? `正在编辑 ${draft.bill_no}` : '新增草稿位于表尾'}，尚未保存，返回本页可继续填写。<Button htmlType="submit" disabled={actionsUnavailable} onClick={() => void saveDraft()}>保存草稿</Button><Button htmlType="submit" disabled={actionsUnavailable} onClick={cancelDraft}>取消草稿</Button></p>}
      <OwnershipPending blocked={blocked || !active} disabled={actionsUnavailable} open={document => { if (!actionsUnavailable) setMaintenance({ kind: 'ownership', document }); }} />
      <DialogPresence>{autoIds&&<AutoLinkDialog ids={autoIds} blocked={blocked||!active} close={()=>setAutoIds(null)} refresh={async()=>{await refresh();}} announce={announce} />}</DialogPresence>
      <DialogPresence>{maintenance?.kind === 'link' ? <ContractDialog row={maintenance.row} blocked={blocked || !active} close={() => { const id=maintenance.row.notice_id; setMaintenance(null); requestAnimationFrame(() => gridRoot.current?.querySelector<HTMLButtonElement>(`[data-contract-notice="${id}"]`)?.focus({preventScroll:true})); }} refresh={()=>refresh()} announce={announce} />
        : maintenance?.kind === 'ownership' ? <OwnershipDialog document={maintenance.document} blocked={blocked || !active} close={() => setMaintenance(null)} refresh={() => refresh('ownership')} announce={announce} />
        : maintenance && <NoticeDeleteDialog row={maintenance.row} blocked={blocked || !active} close={() => setMaintenance(null)} refresh={() => refresh()} announce={announce} />}</DialogPresence>
    </section>
    <DialogPresence>{print && <NoticePrint key={printOwner} rows={print.rows} mode={print.mode} owner={printOwner} resumed={print.resumed} blocked={blocked || !active} close={()=>{printLock.current=false;setPrint(null);}} />}</DialogPresence>
    <DialogPresence>{flowNotice && <NoticeFlows notice={flowNotice} blocked={blocked || !active} close={()=>setFlowNotice(null)} />}</DialogPresence>
    <DialogPresence>{printerOpen && <PrinterSettings blocked={blocked || !active} close={()=>setPrinterOpen(false)} />}</DialogPresence>
    <DialogPresence>{payIds && <NoticePayment projects={projects.data ?? []} ids={payIds} overrides={payOverrides} blocked={blocked || !active} remove={id => { pick(id,false);setPayIds(ids => ids?.filter(x => x !== id) ?? null); }} close={() => setPayIds(null)} paid={paid} refresh={async()=>{await refresh();}} announce={announce} />}</DialogPresence>
    <DialogPresence>{fetchOpen && <NoticeFetch me={me} blocked={blocked || !active} close={() => setFetchOpen(false)} refresh={async()=>{await refresh('fetch');}} />}</DialogPresence>
    <BusinessModal open={exportOpen && active && !blocked} className="project-dialog" titleId="notice-export-title" requestClose={exportClosing.requestClose}><DialogContents titleId="notice-export-title" title="导出付款通知书台账" closing={exportClosing}><p>导出当前筛选的 {shown.length} 条通知书，按表格显示顺序排列。</p>{error && <p className="notice" role="alert">{error}</p>}<div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={exportClosing.requestClose}>取消</Button><Button htmlType="submit" className="primary" disabled={actionsUnavailable || !shown.length} onClick={() => void exportExcel()}>保存到本地</Button></div></DialogContents></BusinessModal>
  </div></NoticeSelectionContext.Provider></NoticeCells.Provider>;
}
