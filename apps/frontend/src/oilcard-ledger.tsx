import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Dropdown from 'antd/es/dropdown';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { ApiError, cents, decimal, money, projectLabel, requestJson } from './api';
import type { Identity, Project } from './api';
import { BusinessGrid } from './business-grid';
import { contentWidth, fullTextWidth } from './grid';
import { valueFilterColumn } from './grid-value-filter';
import type { ValueFilterOptions } from './grid-value-filter';
import { valueFilterPasses } from './grid-value-filter-model';
import type { ValueFilterModel } from './grid-value-filter-model';
import { readHistory } from './history';
import { randomUUID } from './random-id';
import { OilDateText as DateText } from './oilcard-date';
import { OilTransferDialog } from './oilcard-transfer';
import { OilAttributionDialog } from './oilcard-association';
import { OilInvoiceSheet } from './oilcard-invoices';
import { useCellSaveQueue } from './use-cell-save';
import type { OilArchives } from './oilcard-api';
import { correctOilAttribution, getOilLedger, getOilReconciliation, isOilTransfer, oilEntryKindLabels, saveOilEntry, transferOilEntries } from './oilcard-ledger-api';
import type { EntryFields, OilEntry, OilLedger } from './oilcard-ledger-api';
import { editOilEntry, entryFields as fieldsOf, rebaseOilEntryDraft, sameEntryFields as sameFields } from './oilcard-ledger-edits';
import type { OilEntryDraft as Draft } from './oilcard-ledger-edits';

type Field = keyof EntryFields;
type TableRow = OilEntry & { total?: boolean };
const labels: Record<Field, string> = { date_text: '日期', kind: '类型', project_id: '项目', account_id: '用卡账户', amount: '金额', remark: '备注' };
interface Cells { drafts: Record<string, Draft>; entries: OilEntry[]; archives: OilArchives; projects: Project[]; disabled: boolean; busy: boolean; change: (key: string, field: Field, value: string) => void; save: (key: string) => void }
const LedgerCells = createContext<Cells | null>(null);

function EntryCell({ data: row, colDef, node }: ICellRendererParams<TableRow>) {
  const state = useContext(LedgerCells)!;
  const [focused, setFocused] = useState(false);
  if (!row) return null;
  const field = colDef?.field as Field;
  if (node.rowPinned) return field === 'date_text' ? '合计' : field === 'amount' ? money(row.amount) : '';
  const draft = state.drafts[row.request_id], current = draft ?? state.entries.find(entry => entry.request_id === row.request_id);
  if (!current) return null;
  const label = `${labels[field]}：${current.id ? `充值记录 #${current.id}` : '新增充值'}`;
  const disabled = state.disabled || !current.id && state.busy;
  const change = (value: string) => state.change(row.request_id, field, value);
  const save = () => state.save(row.request_id);
  if (field === 'date_text') return <DateText label={label} value={current.date_text} disabled={disabled} change={(value, commit) => { change(value); if (commit) save(); }} save={save} />;
  let options: { value: string; label: string }[] | undefined;
  if (field === 'kind') {
    if (isOilTransfer(current)) return <span title={`同笔转账：${current.transfer_id}`}>{oilEntryKindLabels[current.kind]}</span>;
    if (current.kind === 'refund') return <span title={`关联原充值 #${current.related_entry_id}`}>退款</span>;
    options = [{ value: 'recharge', label: '充值' }, { value: 'adjustment', label: '调整' }];
  }
  if (field === 'project_id') options = [{ value: '', label: '请选择项目' }, ...state.projects.filter(p => p.project_type !== 'shell').map(p => ({ value: String(p.id), label: `${projectLabel(p)}${p.status === 'archived' ? '（项目归档）' : ''}` }))];
  if (field === 'account_id') {
    const candidates = state.archives.accounts.filter(account => account.project_id === current.project_id);
    const original = state.archives.accounts.find(account => account.id === current.account_id);
    options = [{ value: '', label: '请选择账户' }, ...candidates.map(account => ({ value: String(account.id), label: `${account.name}${account.status === 'archived' ? '（归档）' : ''}` })), ...(original && !candidates.some(account => account.id === original.id) ? [{ value: String(original.id), label: `${original.name}（历史关联）` }] : [])];
  }
  if (current.kind === 'refund' && (field === 'project_id' || field === 'account_id')) return options?.find(option => option.value === String(current[field]))?.label || String(current[field]);
  if (options) return <Select aria-label={label} value={String(current[field] || '')} disabled={disabled} options={options} status={draft?.error ? 'error' : ''} showSearch={{ optionFilterProp: 'label' }} onChange={change} />;
  return <Input aria-label={label} className={field === 'amount' ? 'oilcard-amount record-value' : 'record-value'}
    value={field === 'amount' && !draft && !focused ? money(current.amount) : String(current[field])} disabled={disabled} status={draft?.error ? 'error' : ''}
    onFocus={() => setFocused(true)} onChange={e => change(e.target.value)} onBlur={() => { setFocused(false); save(); }} onKeyDown={e => { if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }} />;
}

export function OilLedgerSheet({ me, archives, projects, active, blocked, scale, archiveLocked, onWriteLock, onUncertain }: {
  me: Identity | null; archives: OilArchives; projects: Project[]; active: boolean; blocked: boolean; scale: number; archiveLocked: boolean;
  onWriteLock: (locked: boolean) => void;
  onUncertain: (uncertain: boolean) => void;
}) {
  const client = useQueryClient(), [selected, setSelected] = useState('');
  const [transferOpen, setTransferOpen] = useState(false);
  const [correcting, setCorrecting] = useState<OilEntry | null>(null);
  const [invoiceLocked, setInvoiceLocked] = useState(false), [invoiceUncertain, setInvoiceUncertain] = useState(false);
  const [filters, setFilters] = useState<Record<string, ValueFilterModel>>({});
  const query = useQuery({ queryKey: ['oilcard-ledger'], enabled: active && !blocked, queryFn: ({ signal }) => getOilLedger(signal) });
  const current = useRef(query.data); current.current = query.data;
  const draftRef = useRef<Record<string, Draft>>({});
  const ownPairWrite = useRef<{ key: string; transferId: string; beforeVersion: string; savedVersion: string } | null>(null);
  const saves = useCellSaveQueue<Draft, OilLedger>({
    enabled: active && !blocked && Boolean(me), canWrite: Boolean(query.data && !query.isError && !archiveLocked), read: reload,
    write: async (draft, signal) => {
      const existing = current.current?.entries.find(row => row.request_id === draft.request_id);
      if (draft.original && (!existing || existing.version !== draft.original.version)) throw new ApiError('这条充值记录已变化，请重读核对后处理保留输入。', 409);
      const saved = await saveOilEntry(fieldsOf(draft), existing ? { id: existing.id, version: draft.original?.version ?? existing.version } : { request_id: draft.request_id }, signal);
      if (saved.transfer_id && existing) ownPairWrite.current = { key: saved.request_id, transferId: saved.transfer_id, beforeVersion: existing.version, savedVersion: saved.version };
    },
    acknowledge: (present, submitted) => {
      if (sameFields(present, submitted)) return undefined;
      const saved = current.current?.entries.find(row => row.request_id === submitted.request_id);
      return saved ? rebaseOilEntryDraft(present, saved) : present;
    },
    saved: () => '', validate: draft => !draft.project_id || !draft.account_id ? '请配套选择项目和用卡账户。' : !draft.amount.trim() ? '请填写金额。' : '',
  }, { key: 'oilcard-ledger', label: '油卡充值' });
  async function reload() {
    await client.invalidateQueries({ refetchType: 'none' });
    await client.cancelQueries({ queryKey: ['oilcard-ledger'], exact: true });
    const result = await client.fetchQuery({ queryKey: ['oilcard-ledger'], staleTime: 0, queryFn: ({ signal }) => getOilLedger(signal) });
    current.current = result;
    await client.fetchQuery({ queryKey: ['oilcard-reconciliation'], staleTime: 0, queryFn: ({ signal }) => getOilReconciliation(signal) });
    if (me) await client.fetchQuery({ queryKey: ['history', `${me.id}:${me.account}`], staleTime: 0, queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
    const written = ownPairWrite.current; ownPairWrite.current = null;
    if (written) {
      const pair = result.entries.filter(row => row.transfer_id === written.transferId);
      if (pair.length !== 2 || pair.some(row => row.version !== written.savedVersion)) throw new ApiError('转账已保存，但记录随后发生变化，请重读核对保留输入。', 409);
      if (pair.length === 2 && pair.every(row => row.version === written.savedVersion)) saves.update(ds => Object.fromEntries(Object.entries(ds).map(([key, draft]) => {
        const saved = pair.find(row => row.request_id === key);
        return [key, saved && key !== written.key && draft.original?.version === written.beforeVersion ? rebaseOilEntryDraft(draft, saved) : draft];
      })));
    }
    return result;
  }
  const { drafts, busy, uncertain, verified, error } = saves;
  draftRef.current = drafts;
  useEffect(() => { onWriteLock(busy || uncertain || invoiceLocked); }, [busy, uncertain, invoiceLocked, onWriteLock]);
  useEffect(() => { onUncertain(uncertain || invoiceUncertain); }, [uncertain, invoiceUncertain, onUncertain]);
  const disabled = !active || blocked || !me || uncertain || invoiceLocked || !query.data || query.isError || archiveLocked;
  const structuralDisabled = disabled || busy || Object.keys(drafts).length > 0;
  const filterOptions = useMemo<Record<Field, ValueFilterOptions<TableRow>>>(() => {
    const saved = (row: TableRow) => current.current?.entries.find(entry => entry.request_id === row.request_id);
    const common = { includeCandidate: (row: TableRow) => Boolean(saved(row)), keepVisible: (row: TableRow) => Boolean(draftRef.current[row.request_id]) };
    return {
      date_text: { ...common, kind: 'date', value: row => saved(row)?.date_text },
      kind: { ...common, kind: 'text', value: row => { const kind = saved(row)?.kind; return kind ? oilEntryKindLabels[kind] : null; } },
      project_id: { ...common, kind: 'text', value: row => { const project = projects.find(project => project.id === saved(row)?.project_id); return project ? projectLabel(project) : null; } },
      account_id: { ...common, kind: 'text', value: row => archives.accounts.find(account => account.id === saved(row)?.account_id)?.name },
      amount: { ...common, kind: 'number', value: row => saved(row)?.amount, format: value => money(String(value)) },
      remark: { ...common, kind: 'text', value: row => saved(row)?.remark },
    };
  }, [archives, projects]);
  const filteredAmount = useMemo(() => decimal((query.data?.entries ?? []).filter(row => Object.entries(filters).every(([field, model]) => {
    const options = filterOptions[field as Field];
    return !options || valueFilterPasses(model, options.value(row), options.kind);
  })).reduce((total, row) => total + cents(row.amount), 0n)), [query.data, filters, filterOptions]);
  function save(key: string) {
    const draft = draftRef.current[key];
    if (draft && draft.project_id && draft.account_id && draft.amount.trim()) saves.save(key);
  }
  function change(key: string, field: Field, value: string) {
    if (disabled) return;
    saves.update((ds, writing) => {
      const result = editOilEntry(ds, current.current?.entries ?? [], key, field, value, archives.accounts, writing);
      draftRef.current = result;
      return result;
    });
    if (field === 'kind' || field === 'project_id' || field === 'account_id') {
      const draft = draftRef.current[key];
      if (draft?.project_id && draft.account_id && draft.amount.trim()) saves.save(key);
    }
  }
  function add() {
    if (structuralDisabled) return;
    const request_id = randomUUID();
    const draft: Draft = { id: 0, request_id, version: '', kind: 'recharge', project_id: 0, account_id: 0, card_id: null, date_text: '', entry_date: null, amount: '', remark: '', related_entry_id: null, transfer_id: null, original: null, error: '' };
    saves.update(ds => { const next = { ...ds, [request_id]: draft }; draftRef.current = next; return next; });
  }
  function confirm() {
    if (!verified) return;
    saves.confirm();
    saves.update(ds => Object.fromEntries(Object.entries(ds).flatMap(([key, draft]) => {
      const actual = current.current?.entries.find(row => row.request_id === key);
      return actual && sameFields(actual, draft) ? [] : [[key, { ...(actual ? rebaseOilEntryDraft(draft, actual) : draft), error: '' }]];
    })));
  }
  const rows = useMemo<TableRow[]>(() => [...(query.data?.entries ?? []).map(row => drafts[row.request_id] ?? row), ...Object.values(drafts).filter(draft => !query.data?.entries.some(row => row.request_id === draft.request_id))], [query.data, drafts]);
  const selectedRow = query.data?.entries.find(row => row.request_id === selected);
  const bounds = (query.data?.entries ?? []).reduce((sum, row) => {
    const value = cents(row.amount); if (value > 0n) sum.positive += value; else sum.negative += value; return sum;
  }, { positive: 0n, negative: 0n });
  const amountWidth = fullTextWidth([money(decimal(bounds.positive)), money(decimal(bounds.negative)), ...(query.data?.entries ?? []).map(row => money(row.amount))], scale).minWidth;
  const columns = useMemo<ColDef<TableRow>[]>(() => ([
    { field: 'date_text', headerName: '日期', ...contentWidth(190, 240, scale), cellRenderer: EntryCell },
    { field: 'kind', headerName: '类型', ...contentWidth(100, 130, scale), cellRenderer: EntryCell },
    { field: 'project_id', headerName: '项目', ...contentWidth(180, 320, scale, 1), cellRenderer: EntryCell },
    { field: 'account_id', headerName: '用卡账户', ...contentWidth(160, 300, scale, 1), cellRenderer: EntryCell },
    { field: 'amount', headerName: '金额', cellClass: 'money', ...contentWidth(Math.max(130, amountWidth / scale), 200, scale), cellRenderer: EntryCell },
    { field: 'remark', headerName: '备注', ...contentWidth(160, 360, scale, 1), cellRenderer: EntryCell },
  ] satisfies ColDef<TableRow>[]).map(column => valueFilterColumn<TableRow>(column, filterOptions[column.field as Field])), [scale, amountWidth, filterOptions]);
  const totals = useMemo<TableRow[]>(() => query.data ? [{ id: -1, request_id: 'total', version: '', kind: 'adjustment', project_id: 0, account_id: 0, card_id: null, date_text: '合计', entry_date: null, amount: filteredAmount, remark: '', related_entry_id: null, transfer_id: null, total: true }] : [], [query.data, filteredAmount]);
  return <section className="oilcard-ledger-sheet" aria-label="充值与发票">
    {(error || query.isError) && <p className="notice" role="alert">{error || query.error?.message}<Button disabled={blocked || busy} onClick={() => void saves.reread()}>重读核对</Button></p>}
    {(uncertain || verified && Object.keys(drafts).length > 0) && <p className="notice" role="alert">{uncertain ? '核对刚才的充值登记后再继续。' : '已读取当前记录，请核对保留的输入。'}<Button disabled={!verified || blocked || busy} onClick={confirm}>已核对，保留输入继续</Button></p>}
    <div className="oilcard-ledger-panes"><section className="oilcard-ledger-pane" aria-label="充值台账"><div data-page-chrome className="oilcard-toolbar"><h2>充值与调整</h2><div><Button type="primary" disabled={structuralDisabled} onClick={add}>新增充值</Button>
      <Button disabled={structuralDisabled} onClick={() => { saves.clearFeedback(); setTransferOpen(true); }}>转账</Button>
      {Object.values(drafts).some(draft => !draft.id) && <Button disabled={blocked || busy || uncertain} onMouseDown={e => e.preventDefault()} onClick={() => saves.update(ds => { const next = Object.fromEntries(Object.entries(ds).filter(([, draft]) => draft.id)); draftRef.current = next; return next; })}>取消新增</Button>}</div></div>
      <div className="oilcard-selection-actions" aria-label="所选充值记录">{selectedRow && <><span>{selectedRow.date_text || '日期未知'}，{projects.find(project => project.id === selectedRow.project_id)?.disp || `项目 #${selectedRow.project_id}`}，{money(selectedRow.amount)} 元</span><Button size="small" disabled={structuralDisabled} onClick={() => { saves.clearFeedback(); setCorrecting(selectedRow); }}>更正本笔归属</Button></>}</div>
      {Object.entries(drafts).filter(([, draft]) => draft.error).map(([key, draft]) => <p className="oilcard-draft-error" key={key}>充值记录 {draft.id || '草稿'}：{draft.error}<Button size="small" disabled={disabled || busy} onMouseDown={e => e.preventDefault()} onClick={() => saves.save(key, true)}>重试保存</Button><Button size="small" disabled={blocked || busy || uncertain} onMouseDown={e => e.preventDefault()} onClick={() => saves.update(ds => { const next = { ...ds }; delete next[key]; draftRef.current = next; return next; })}>放弃本次输入</Button></p>)}
      {query.isPending ? <p role="status" data-page-loading>正在读取充值台账…</p> : query.data && <LedgerCells.Provider value={{ drafts, entries: query.data.entries, archives, projects, disabled, busy, change, save }}><div onContextMenuCapture={e => { if (e.target instanceof Element && e.target.closest('input,.ant-select')) e.stopPropagation(); }}><Dropdown trigger={['contextMenu']} menu={{ items: [{ key: 'attribution', label: '更正本笔归属', disabled: structuralDisabled || !selectedRow }], onClick: () => { if (!structuralDisabled && selectedRow) { saves.clearFeedback(); setCorrecting(selectedRow); } } }}><div><BusinessGrid table="oilcard-ledger" label="油卡充值台账" rows={rows} columns={columns} totals={totals} rowId={row => row.request_id} scale={scale} domLayout="normal" style={{ height: '62dvh', minHeight: '300px' }} grid={{ enableFilterHandlers: true, popupParent: document.body, onFilterChanged: e => setFilters(e.api.getFilterModel() as Record<string, ValueFilterModel>), onRowClicked: e => { if (e.data && !e.node.rowPinned) setSelected(e.data.request_id); }, onCellContextMenu: e => { if (e.data && !e.node.rowPinned) setSelected(e.data.request_id); }, rowClassRules: { 'oilcard-selected': p => p.data?.request_id === selected } }} /></div></Dropdown></div></LedgerCells.Provider>}
    </section><OilInvoiceSheet me={me} archives={archives} projects={projects} active={active} blocked={blocked} scale={scale} locked={busy || uncertain || archiveLocked} onWriteLock={setInvoiceLocked} onUncertain={setInvoiceUncertain} /></div>
    {transferOpen && <OilTransferDialog archives={archives} projects={projects} disabled={disabled} busy={busy} error={error} close={() => setTransferOpen(false)} submit={async values => {
      const from = archives.accounts.find(account => account.id === values.out_account_id)?.name ?? '转出账户';
      const to = archives.accounts.find(account => account.id === values.in_account_id)?.name ?? '转入账户';
      const outcome = await saves.run(async signal => { await transferOilEntries(values, signal); }, () => '', `${from} 转至 ${to}，${values.amount}：`);
      if (outcome === 'saved' || outcome === 'uncertain') setTransferOpen(false);
    }} />}
    {correcting && <OilAttributionDialog row={correcting} archives={archives} projects={projects} disabled={disabled} busy={busy} error={error} close={() => setCorrecting(null)} submit={async fields => {
      const outcome = await saves.run(async signal => { await correctOilAttribution(fields, correcting, signal); }, () => '', `充值记录 #${correcting.id} 归属更正：`);
      if (outcome === 'saved' || outcome === 'uncertain') setCorrecting(null);
    }} />}
  </section>;
}
