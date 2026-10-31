import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import DatePicker from 'antd/es/date-picker';
import Dropdown from 'antd/es/dropdown';
import dayjs from 'dayjs';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { ApiError, money, projectLabel, requestJson } from './api';
import type { Identity, Project } from './api';
import { BusinessGrid } from './business-grid';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { contentWidth, fullTextWidth } from './grid';
import { readHistory } from './history';
import { randomUUID } from './random-id';
import { useCellSaveQueue } from './use-cell-save';
import type { OilArchives } from './oilcard-api';
import { getOilLedger, getOilReconciliation, refundOilEntry, saveOilEntry } from './oilcard-ledger-api';
import type { EntryFields, OilEntry, OilLedger } from './oilcard-ledger-api';
import { editOilEntry, entryFields as fieldsOf, rebaseOilEntryDraft, sameEntryFields as sameFields } from './oilcard-ledger-edits';
import type { OilEntryDraft as Draft } from './oilcard-ledger-edits';

type Field = keyof EntryFields;
type TableRow = OilEntry & { total?: boolean };
const labels: Record<Field, string> = { date_text: '日期', kind: '类型', project_id: '项目', account_id: '用卡账户', amount: '金额', remark: '备注' };
interface Cells { drafts: Record<string, Draft>; entries: OilEntry[]; archives: OilArchives; projects: Project[]; disabled: boolean; busy: boolean; change: (key: string, field: Field, value: string) => void; save: (key: string) => void }
const LedgerCells = createContext<Cells | null>(null);

function DateText({ label, value, disabled, change, save }: { label: string; value: string; disabled: boolean; change: (value: string, commit: boolean) => void; save: () => void }) {
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) && dayjs(value).isValid() && dayjs(value).format('YYYY-MM-DD') === value ? dayjs(value) : null;
  return <div className="oilcard-date-text"><Input aria-label={label} value={value} disabled={disabled} placeholder="日期、文字或留空" onChange={e => change(e.target.value, false)} onBlur={save} onKeyDown={e => { if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }} />
    <DatePicker aria-label={`选择${label}`} value={date} inputReadOnly allowClear={false} disabled={disabled} format="YYYY-MM-DD" className="oilcard-calendar" classNames={{ popup: { root: 'ag-custom-component-popup' } }} onChange={next => { if (next) change(next.format('YYYY-MM-DD'), true); }} /></div>;
}
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
  const client = useQueryClient(), [selected, setSelected] = useState(''), [refund, setRefund] = useState<OilEntry | null>(null);
  const query = useQuery({ queryKey: ['oilcard-ledger'], enabled: active && !blocked, queryFn: ({ signal }) => getOilLedger(signal) });
  const current = useRef(query.data); current.current = query.data;
  const draftRef = useRef<Record<string, Draft>>({});
  const saves = useCellSaveQueue<Draft, OilLedger>({
    enabled: active && !blocked && Boolean(me), canWrite: Boolean(query.data && !query.isError && !archiveLocked), read: reload,
    write: async (draft, signal) => {
      const existing = current.current?.entries.find(row => row.request_id === draft.request_id);
      if (draft.original && (!existing || existing.version !== draft.original.version)) throw new ApiError('这条充值记录已变化，请重读核对后处理保留输入。', 409);
      await saveOilEntry(fieldsOf(draft), existing ? { id: existing.id, version: draft.original?.version ?? existing.version } : { request_id: draft.request_id }, signal);
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
    return result;
  }
  const { drafts, busy, uncertain, verified, error } = saves;
  draftRef.current = drafts;
  useEffect(() => { onWriteLock(busy || uncertain); }, [busy, uncertain, onWriteLock]);
  useEffect(() => { onUncertain(uncertain); }, [uncertain, onUncertain]);
  const disabled = !active || blocked || !me || uncertain || !query.data || query.isError || archiveLocked;
  const structuralDisabled = disabled || busy || Object.keys(drafts).length > 0;
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
    const draft: Draft = { id: 0, request_id, version: '', kind: 'recharge', project_id: 0, account_id: 0, card_id: null, date_text: '', entry_date: null, amount: '', remark: '', related_entry_id: null, original: null, error: '' };
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
  const amountWidth = fullTextWidth([money(query.data?.total_amount ?? '0.00'), ...(query.data?.entries ?? []).map(row => money(row.amount))], scale).minWidth;
  const columns = useMemo<ColDef<TableRow>[]>(() => [
    { field: 'date_text', headerName: '日期', ...contentWidth(190, 240, scale), cellRenderer: EntryCell },
    { field: 'kind', headerName: '类型', ...contentWidth(100, 130, scale), cellRenderer: EntryCell },
    { field: 'project_id', headerName: '项目', ...contentWidth(180, 320, scale, 1), cellRenderer: EntryCell },
    { field: 'account_id', headerName: '用卡账户', ...contentWidth(160, 300, scale, 1), cellRenderer: EntryCell },
    { field: 'amount', headerName: '金额', cellClass: 'money', ...contentWidth(Math.max(130, amountWidth / scale), 200, scale), cellRenderer: EntryCell },
    { field: 'remark', headerName: '备注', ...contentWidth(160, 360, scale, 1), cellRenderer: EntryCell },
  ], [scale, amountWidth]);
  const totals = useMemo<TableRow[]>(() => query.data ? [{ id: -1, request_id: 'total', version: '', kind: 'adjustment', project_id: 0, account_id: 0, card_id: null, date_text: '合计', entry_date: null, amount: query.data.total_amount, remark: '', related_entry_id: null, total: true }] : [], [query.data]);
  return <section className="oilcard-ledger-sheet" aria-label="充值与发票">
    {(error || query.isError) && <p className="notice" role="alert">{error || query.error?.message}<Button disabled={blocked || busy} onClick={() => void saves.reread()}>重读核对</Button></p>}
    {(uncertain || verified && Object.keys(drafts).length > 0) && <p className="notice" role="alert">{uncertain ? '核对刚才的充值或退款登记后再继续。' : '已读取当前记录，请核对保留的输入。'}<Button disabled={!verified || blocked || busy} onClick={confirm}>已核对，保留输入继续</Button></p>}
    <div className="oilcard-ledger-panes"><section className="oilcard-ledger-pane" aria-label="充值台账"><div data-page-chrome className="oilcard-toolbar"><h2>充值与调整</h2><div><Button type="primary" disabled={structuralDisabled} onClick={add}>新增充值</Button>
      {selectedRow?.kind === 'recharge' && <Button disabled={structuralDisabled} onClick={() => setRefund(selectedRow)}>登记退款</Button>}
      <Button disabled={blocked || busy || !Object.keys(drafts).length} onMouseDown={e => e.preventDefault()} onClick={() => saves.update(() => ({}))}>取消未保存修改</Button></div></div>
      {Object.entries(drafts).filter(([, draft]) => draft.error).map(([key, draft]) => <p className="oilcard-draft-error" key={key}>充值记录 {draft.id || '草稿'}：{draft.error}<Button size="small" disabled={disabled || busy} onMouseDown={e => e.preventDefault()} onClick={() => saves.save(key, true)}>重试保存</Button></p>)}
      {query.isPending ? <p role="status" data-page-loading>正在读取充值台账…</p> : query.data && <LedgerCells.Provider value={{ drafts, entries: query.data.entries, archives, projects, disabled, busy, change, save }}><div onContextMenuCapture={e => { if (e.target instanceof Element && e.target.closest('input,.ant-select')) e.stopPropagation(); }}><Dropdown trigger={['contextMenu']} menu={{ items: [{ key: 'refund', label: '登记退款', disabled: structuralDisabled || selectedRow?.kind !== 'recharge' }], onClick: () => { if (selectedRow?.kind === 'recharge' && !structuralDisabled) setRefund(selectedRow); } }}><div><BusinessGrid table="oilcard-ledger" label="油卡充值台账" rows={rows} columns={columns} totals={totals} rowId={row => row.request_id} scale={scale} domLayout="normal" style={{ height: '62dvh', minHeight: '300px' }} grid={{ onRowClicked: e => { if (e.data && !e.node.rowPinned) setSelected(e.data.request_id); }, onCellContextMenu: e => { if (e.data && !e.node.rowPinned) setSelected(e.data.request_id); }, rowClassRules: { 'oilcard-selected': p => p.data?.request_id === selected } }} /></div></Dropdown></div></LedgerCells.Provider>}
    </section><section className="oilcard-ledger-pane oilcard-invoice-pending" aria-label="发票"><div data-page-chrome className="oilcard-toolbar"><h2>发票</h2></div><p className="state">发票接收与核对将在后续接入。</p></section></div>
    {refund && <RefundDialog row={refund} disabled={disabled} busy={busy} error={error} close={() => setRefund(null)} submit={async values => {
      const outcome = await saves.run(async signal => { await refundOilEntry({ ...values, original_id: refund.id }, signal); }, () => '', `原充值 #${refund.id} 退款 ${values.amount}：`);
      if (outcome === 'saved' || outcome === 'uncertain') setRefund(null);
    }} />}
  </section>;
}
function RefundDialog({ row, disabled, busy, error, close, submit }: { row: OilEntry; disabled: boolean; busy: boolean; error: string; close: () => void; submit: (fields: { request_id: string; amount: string; date_text: string; remark: string }) => Promise<void> }) {
  const [amount, setAmount] = useState(''), [date, setDate] = useState(''), [remark, setRemark] = useState('');
  const requestId = useRef(randomUUID());
  const closing = useDialogClose({ busy, dirty: Boolean(amount || date || remark), close });
  return <BusinessModal open className="oilcard-refund-dialog" titleId="oilcard-refund-title" requestClose={closing.requestClose}><DialogContents title="登记实际退款" titleId="oilcard-refund-title" closing={closing}>
    <p>原充值 #{row.id}，{money(row.amount)} 元</p><form onSubmit={e => { e.preventDefault(); if (!disabled && !busy && amount.trim()) void submit({ request_id: requestId.current, amount, date_text: date, remark }); }}>
      <label>退款金额<Input aria-label="退款金额" autoFocus value={amount} disabled={disabled || busy} onChange={e => setAmount(e.target.value)} placeholder="填写正数" /></label>
      <label>日期<DateText label="退款日期" value={date} disabled={disabled || busy} change={setDate} save={() => {}} /></label>
      <label>备注<Input aria-label="退款备注" value={remark} disabled={disabled || busy} onChange={e => setRemark(e.target.value)} /></label>
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" htmlType="submit" disabled={disabled || busy || !amount.trim()}>登记退款</Button></div>
    </form></DialogContents></BusinessModal>;
}
