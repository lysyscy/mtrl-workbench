import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { ApiError, projectLabel, readProjects, requestJson } from './api';
import type { Identity, Project } from './api';
import { BusinessGrid, ReadGrid } from './business-grid';
import { contentWidth, fullTextWidth } from './grid';
import { readHistory } from './history';
import { PageActivity } from './page-activity';
import { randomUUID } from './random-id';
import { useCellSaveQueue } from './use-cell-save';
import { getOilArchives, getOilAssignments, replaceOilCard, saveOilAccount, saveOilCard } from './oilcard-api';
import type { AccountFields, CardFields, OilAccount, OilArchives, OilCard } from './oilcard-api';
import { OilLedgerSheet } from './oilcard-ledger';
import { OilReconciliationSheet } from './oilcard-reconciliation';
import { OilReplacementDialog } from './oilcard-association';

type ArchiveKind = 'card' | 'account';
type Field = 'card_no' | 'kind' | 'parent_card_id' | 'remark' | 'name' | 'project_id' | 'card_id' | 'status';
type Draft = { kind: ArchiveKind; id: number; field: Field; original: string; value: string; error: string };
type PendingAccount = OilAccount;
const keyOf = (kind: ArchiveKind, id: number, field: Field) => `${kind}:${id}:${field}`;
const text = (value: unknown) => value === null || value === undefined ? '' : String(value);
const cardLabel = (card: OilCard) => card.card_no || `卡号待补 #${card.id}`;
const fieldLabels: Record<Field, string> = { card_no: '完整卡号更正', kind: '主卡/副卡', parent_card_id: '所属主卡', remark: '备注', name: '账户名称', project_id: '项目', card_id: '关联卡片', status: '账户状态' };
interface Cells {
  drafts: Record<string, Draft>; disabled: boolean; busy: boolean; projects: Project[]; cards: OilCard[]; accounts: OilAccount[]; pending: PendingAccount | null;
  change: (kind: ArchiveKind, row: OilCard | OilAccount, field: Field, value: string) => void;
  save: (kind: ArchiveKind, row: OilCard | OilAccount, field: Field) => void;
}
const ArchiveCells = createContext<Cells | null>(null);
function ArchiveEditor({ kind, row: rendered, field }: { kind: ArchiveKind; row: OilCard | OilAccount; field: Field }) {
  const state = useContext(ArchiveCells)!;
  const row = kind === 'card' ? state.cards.find(item => item.request_id === rendered.request_id) : state.accounts.find(item => item.request_id === rendered.request_id) ?? (state.pending?.request_id === rendered.request_id ? state.pending : null);
  if (!row) return null;
  const key = keyOf(kind, row.id, field), draft = state.drafts[key];
  const original = text((row as unknown as Record<string, unknown>)[field]), value = draft?.value ?? original;
  const label = `${fieldLabels[field]}：${'name' in row ? row.name || '新增账户' : cardLabel(row)}`;
  const disabled = state.disabled || row.id === 0 && state.busy;
  const change = (next: string) => state.change(kind, row, field, next);
  let options: { value: string; label: string }[] | undefined;
  if (field === 'kind') options = [{ value: 'primary', label: '主卡' }, { value: 'secondary', label: '副卡' }];
  if (field === 'status') options = [{ value: 'active', label: '在用' }, { value: 'archived', label: '归档' }];
  if (field === 'project_id') options = [{ value: '', label: '请选择项目' }, ...state.projects.filter(p => p.project_type !== 'shell').map(p => ({ value: String(p.id), label: `${projectLabel(p)}${p.status === 'archived' ? '（项目归档）' : ''}` }))];
  if (field === 'parent_card_id' || field === 'card_id') options = [{ value: '', label: field === 'parent_card_id' ? '无' : '未关联卡片' }, ...state.cards.filter(c => field === 'parent_card_id' ? c.kind === 'primary' && c.id !== row.id : c.kind === 'secondary').map(c => ({ value: String(c.id), label: cardLabel(c) }))];
  if (field === 'parent_card_id' && 'kind' in row && (state.drafts[keyOf(kind, row.id, 'kind')]?.value ?? row.kind) === 'primary') return <span className="muted">—</span>;
  return <div className="oilcard-cell">{options ? <Select aria-label={label} value={field === 'project_id' && value === '0' ? '' : value} disabled={disabled} status={draft?.error ? 'error' : ''}
    showSearch={{ optionFilterProp: 'label' }} options={options} onChange={next => change(next)} /> : <Input aria-label={label} value={value} disabled={disabled} status={draft?.error ? 'error' : ''}
    className="record-value" placeholder={field === 'card_no' ? '未知可留空' : undefined} onChange={e => change(e.target.value)}
    onBlur={() => state.save(kind, row, field)} onKeyDown={e => { if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }} />}
    {draft?.error && <p role="alert" className="oilcard-cell-error">{draft.error}</p>}</div>;
}
const cardFields = (row: OilCard): CardFields => ({ card_no: row.card_no, kind: row.kind, parent_card_id: row.parent_card_id, remark: row.remark });
const accountFields = (row: OilAccount): AccountFields => ({ name: row.name, project_id: row.project_id, card_id: row.card_id, status: row.status, remark: row.remark });

export function OilCardPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const client = useQueryClient();
  const [tab, setTab] = useState<'overview' | 'ledger' | ArchiveKind>('overview'), [status, setStatus] = useState('all');
  const [ledgerVisited, setLedgerVisited] = useState(false), [ledgerLocked, setLedgerLocked] = useState(false);
  const [ledgerUncertain, setLedgerUncertain] = useState(false);
  const [pending, setPending] = useState<PendingAccount | null>(null), pendingRef = useRef(pending); pendingRef.current = pending;
  const [selected, setSelected] = useState(0), [historyAccount, setHistoryAccount] = useState(0);
  const [replacing, setReplacing] = useState<OilAccount | null>(null);
  const query = useQuery({ queryKey: ['oilcard-archives'], enabled: active && !blocked, queryFn: ({ signal }) => getOilArchives(signal) });
  const projects = useQuery({ queryKey: ['projects', 'all'], enabled: active && !blocked, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const assignments = useQuery({ queryKey: ['oilcard-assignments', historyAccount], enabled: active && !blocked && historyAccount > 0, queryFn: ({ signal }) => getOilAssignments(historyAccount, signal) });
  const data = query.data, currentData = useRef(data); currentData.current = data;
  const saves = useCellSaveQueue<Draft, OilArchives>({
    enabled: active && !blocked && Boolean(me), canWrite: Boolean(data && !query.isError && projects.data && !projects.isError && !ledgerLocked),
    read: reload, write: async (draft, signal) => {
      const row = draft.kind === 'card' ? currentData.current?.cards.find(r => r.id === draft.id) : currentData.current?.accounts.find(r => r.id === draft.id);
      if (!row) throw new ApiError('这条档案已不在当前结果内，请重读核对。', 409);
      const original = text((row as unknown as Record<string, unknown>)[draft.field]);
      if (original !== draft.original) throw new ApiError('这个字段已变化，请重读核对后处理保留输入。', 409);
      const value = ['parent_card_id', 'project_id', 'card_id'].includes(draft.field) ? draft.value ? Number(draft.value) : null : draft.field === 'card_no' ? draft.value.trim() || null : draft.field === 'name' ? draft.value.trim() : draft.value;
      if (draft.kind === 'card') {
        const fields = { ...cardFields(row as OilCard), [draft.field]: value };
        if (draft.field === 'kind' && value === 'primary') fields.parent_card_id = null;
        await saveOilCard(fields, row, signal);
      } else await saveOilAccount({ ...accountFields(row as OilAccount), [draft.field]: value }, row, signal);
    },
    acknowledge: (current, submitted) => current.value === submitted.value ? undefined : { ...current, original: submitted.field === 'card_no' || submitted.field === 'name' ? submitted.value.trim() : submitted.value },
    saved: () => '', validate: d => d.field === 'name' && !d.value.trim() ? '请填写账户名称。' : '',
  }, { key: 'oilcard-archives', label: '油卡档案', pending: Boolean(pending) });
  async function reload() {
    await client.invalidateQueries({ refetchType: 'none' });
    await client.cancelQueries({ queryKey: ['oilcard-archives'], exact: true });
    const result = await client.fetchQuery({ queryKey: ['oilcard-archives'], staleTime: 0, queryFn: ({ signal }) => getOilArchives(signal) });
    currentData.current = result;
    if (historyAccount) await client.fetchQuery({ queryKey: ['oilcard-assignments', historyAccount], staleTime: 0, queryFn: ({ signal }) => getOilAssignments(historyAccount, signal) });
    if (me) await client.fetchQuery({ queryKey: ['history', `${me.id}:${me.account}`], staleTime: 0, queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
    return result;
  }
  const { drafts, busy, uncertain, verified, error } = saves, dirty = Object.keys(drafts).length > 0;
  const disabled = blocked || !active || !me || uncertain || ledgerLocked || !data || query.isError || !projects.data || projects.isError;
  const structuralDisabled = disabled || busy || dirty || Boolean(pending) || query.isFetching;
  const scale = Number(me?.ui_scale_css) || 1;
  useEffect(() => { if (pending && data?.accounts.some(row => row.request_id === pending.request_id)) setPending(null); }, [pending, data]);
  async function createAccount(row: PendingAccount) {
    if (disabled || busy || !row.name.trim() || !row.project_id) return;
    const outcome = await saves.run(async signal => { await saveOilAccount({ ...accountFields(row), name: row.name.trim() }, { request_id: row.request_id }, signal); }, () => '', '新增用卡账户：');
    if (outcome === 'saved') setPending(null);
  }
  function change(kind: ArchiveKind, row: OilCard | OilAccount, field: Field, value: string) {
    if (disabled) return;
    const actual = kind === 'card' ? currentData.current?.cards.find(item => item.request_id === row.request_id) : currentData.current?.accounts.find(item => item.request_id === row.request_id);
    if (actual) row = actual;
    if (row.id === 0 && pendingRef.current) {
      const next = { ...pendingRef.current, [field]: ['project_id', 'card_id'].includes(field) ? value ? Number(value) : field === 'project_id' ? 0 : null : value };
      pendingRef.current = next; setPending(next);
      if (['project_id', 'card_id', 'status'].includes(field)) void createAccount(next);
      return;
    }
    const key = keyOf(kind, row.id, field), original = text((row as unknown as Record<string, unknown>)[field]);
    saves.update((ds, writing) => {
      const next = { ...ds }, previous = ds[key];
      if (value === original && !writing) delete next[key];
      else next[key] = { kind, id: row.id, field, value, original: previous?.original ?? original, error: '' };
      return next;
    });
    if (['kind', 'parent_card_id', 'project_id', 'card_id', 'status'].includes(field)) saves.save(key);
  }
  function save(kind: ArchiveKind, row: OilCard | OilAccount, field: Field) {
    const actual = kind === 'card' ? currentData.current?.cards.find(item => item.request_id === row.request_id) : currentData.current?.accounts.find(item => item.request_id === row.request_id);
    if (actual) row = actual;
    if (row.id === 0) { if (pendingRef.current) void createAccount(pendingRef.current); }
    else saves.save(keyOf(kind, row.id, field));
  }
  async function addCard() {
    if (structuralDisabled) return;
    const request_id = randomUUID();
    await saves.run(async signal => { await saveOilCard({ card_no: null, kind: 'secondary', parent_card_id: null, remark: '' }, { request_id }, signal); }, () => '', '新增实体油卡：');
  }
  function addAccount() {
    if (structuralDisabled) return;
    const row: OilAccount = { id: 0, request_id: randomUUID(), version: '', name: '', project_id: 0, card_id: null, status: 'active', remark: '' };
    pendingRef.current = row; setPending(row);
  }
  const accounts = useMemo(() => [...(data?.accounts ?? []).filter(a => status === 'all' || a.status === status), ...(pending && !data?.accounts.some(a => a.request_id === pending.request_id) ? [pending] : [])], [data, status, pending]);
  const cards = useMemo(() => data?.cards ?? [], [data]);
  const cardNumberWidth = fullTextWidth(cards.map(c => c.card_no || '卡号待补 #000'), scale).minWidth;
  const cardColumns = useMemo<ColDef<OilCard>[]>(() => [
    { field: 'card_no', headerName: '完整卡号', ...contentWidth(Math.max(180, cardNumberWidth / scale), 350, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilCard>) => row && <ArchiveEditor kind="card" row={row} field="card_no" /> },
    { field: 'kind', headerName: '主卡/副卡', ...contentWidth(120, 160, scale), cellRenderer: ({ data: row }: ICellRendererParams<OilCard>) => row && <ArchiveEditor kind="card" row={row} field="kind" /> },
    { field: 'parent_card_id', headerName: '所属主卡', ...contentWidth(200, 350, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilCard>) => row && <ArchiveEditor kind="card" row={row} field="parent_card_id" /> },
    { field: 'remark', headerName: '备注', ...contentWidth(200, 500, scale, 2), cellRenderer: ({ data: row }: ICellRendererParams<OilCard>) => row && <ArchiveEditor kind="card" row={row} field="remark" /> },
  ], [scale, cardNumberWidth]);
  const accountColumns = useMemo<ColDef<OilAccount>[]>(() => [
    { field: 'name', headerName: '账户名称', ...contentWidth(170, 300, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="name" /> },
    { field: 'project_id', headerName: '项目', ...contentWidth(200, 360, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="project_id" /> },
    { field: 'card_id', headerName: '关联卡片', ...contentWidth(200, 350, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="card_id" /> },
    { field: 'status', headerName: '状态', ...contentWidth(100, 140, scale), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="status" /> },
    { field: 'remark', headerName: '备注', ...contentWidth(200, 440, scale, 2), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="remark" /> },
  ], [scale]);
  const state: Cells = { drafts, disabled, busy, projects: projects.data ?? [], cards, accounts: data?.accounts ?? [], pending, change, save };
  const renderRemark = useCallback((kind: ArchiveKind, row: OilCard | OilAccount) => <ArchiveEditor kind={kind} row={row} field="remark" />, []);
  function chooseTab(value: typeof tab) { if (value === 'ledger') setLedgerVisited(true); setTab(value); }
  return <section className="oilcard-page" aria-label="油卡管理">
    <div data-page-chrome className="oilcard-tabs" role="tablist" aria-label="油卡工作表">{([{ value: 'overview', label: '账户核对' }, { value: 'ledger', label: '充值与发票' }, { value: 'linkage', label: '用油联动' }, { value: 'account', label: '用卡账户' }, { value: 'card', label: '实体油卡' }] as const).map(item => <Button key={item.value} role="tab" id={`oilcard-tab-${item.value}`} aria-controls={`oilcard-panel-${item.value}`} aria-selected={tab === item.value} disabled={item.value === 'linkage'} title={item.value === 'linkage' ? '用油联动将在后续接入' : undefined} type={tab === item.value ? 'primary' : 'default'} onClick={() => { if (item.value !== 'linkage') chooseTab(item.value); }}>{item.label}</Button>)}</div>
    {(tab === 'account' || tab === 'card') && <div data-page-chrome className="oilcard-toolbar"><div><Button type="primary" disabled={structuralDisabled} onClick={() => tab === 'card' ? void addCard() : addAccount()}>{tab === 'card' ? '新增实体油卡' : '新增用卡账户'}</Button>
      <Button disabled={blocked || busy || !dirty && !pending} onMouseDown={e => e.preventDefault()} onClick={() => { saves.update(() => ({})); setPending(null); pendingRef.current = null; }}>取消未保存修改</Button>
      {tab === 'account' && <><Button disabled={!selected || structuralDisabled} onClick={() => { const account = currentData.current?.accounts.find(item => item.id === selected); if (account) { saves.clearFeedback(); setReplacing(account); } }}>换卡</Button><Button disabled={!selected || blocked || busy} onClick={() => setHistoryAccount(selected)}>关联历史</Button></>}</div>
      {tab === 'account' && <label>账户状态<Select aria-label="账户状态筛选" value={status} onChange={setStatus} options={[{ value: 'all', label: '全部' }, { value: 'active', label: '在用' }, { value: 'archived', label: '归档' }]} /></label>}</div>}
    {!me && <p className="state">登录后可维护油卡档案。</p>}
    {ledgerUncertain && tab !== 'ledger' && <p className="notice" role="alert">充值或收票结果待核实，请先核对后再继续编辑。<Button onClick={() => chooseTab('ledger')}>核对保存结果</Button></p>}
    {(error || query.isError || projects.isError) && <p className="notice" role="alert">{error || query.error?.message || projects.error?.message}<Button disabled={blocked || busy} onClick={() => void saves.reread()}>重读核对</Button></p>}
    {uncertain && <p className="notice" role="alert">核对刚才的档案变更后再继续。<Button disabled={!verified || blocked || busy} onClick={() => saves.confirm()}>已核对，保留输入继续</Button></p>}
    {Object.entries(drafts).filter(([, d]) => d.error).map(([key, d]) => <p className="oilcard-draft-error" key={key}>{fieldLabels[d.field]}：{d.error}<Button size="small" disabled={disabled || busy} onMouseDown={e => e.preventDefault()} onClick={() => saves.save(key, true)}>重试保存</Button></p>)}
    {pending && <p className="muted oilcard-pending-hint">填写账户名称并选择项目后自动建档。</p>}
    {tab === 'card' && <p className="muted oilcard-pending-hint">卡号录错可直接更正；换卡请在用卡账户表选择账户后办理。</p>}
    {query.isPending || projects.isPending ? <p data-page-loading role="status">正在读取油卡档案…</p> : data && <ArchiveCells.Provider value={state}>
      <div role="tabpanel" id="oilcard-panel-overview" aria-labelledby="oilcard-tab-overview" hidden={tab !== 'overview'}><PageActivity.Provider value={active && tab === 'overview'}><OilReconciliationSheet archives={data} projects={projects.data ?? []} active={active && tab === 'overview'} blocked={blocked} scale={scale} remark={renderRemark} openLedger={() => chooseTab('ledger')} /></PageActivity.Provider></div>
      {ledgerVisited && <div role="tabpanel" id="oilcard-panel-ledger" aria-labelledby="oilcard-tab-ledger" hidden={tab !== 'ledger'}><PageActivity.Provider value={active && tab === 'ledger'}><OilLedgerSheet me={me} archives={data} projects={projects.data ?? []} active={active && tab === 'ledger'} blocked={blocked} scale={scale} archiveLocked={busy || uncertain || query.isError || projects.isError} onWriteLock={setLedgerLocked} onUncertain={setLedgerUncertain} /></PageActivity.Provider></div>}
      <div role="tabpanel" id="oilcard-panel-account" aria-labelledby="oilcard-tab-account" hidden={tab !== 'account'}><PageActivity.Provider value={active && tab === 'account'}>
        {!accounts.length ? <p className="state">尚无符合条件的用卡账户。</p> : <BusinessGrid table="oilcard-accounts" label="用卡账户档案" rows={accounts} columns={accountColumns} rowId={row => row.id ? String(row.id) : `draft-${row.request_id}`} scale={scale} domLayout="autoHeight" grid={{ onRowClicked: e => { if (e.data?.id) setSelected(e.data.id); }, rowClassRules: { 'oilcard-selected': p => Boolean(p.data?.id && p.data.id === selected) } }} />}
      </PageActivity.Provider></div>
      <div role="tabpanel" id="oilcard-panel-card" aria-labelledby="oilcard-tab-card" hidden={tab !== 'card'}><PageActivity.Provider value={active && tab === 'card'}>
        {!cards.length ? <p className="state">尚无实体油卡，可先建立卡号待补的档案。</p> : <BusinessGrid table="oilcard-cards" label="实体油卡档案" rows={cards} columns={cardColumns} rowId={row => String(row.id)} scale={scale} domLayout="autoHeight" />}
      </PageActivity.Provider></div>
    </ArchiveCells.Provider>}
    {historyAccount > 0 && tab === 'account' && <section className="oilcard-assignment-history" aria-label="用卡账户关联历史"><div className="oilcard-toolbar"><h2>{data?.accounts.find(a => a.id === historyAccount)?.name} 关联历史</h2><Button onClick={() => setHistoryAccount(0)}>收起关联历史</Button></div>
      {assignments.isPending ? <p role="status">正在读取关联历史…</p> : assignments.isError ? <p role="alert" className="notice">{assignments.error.message}<Button disabled={blocked} onClick={() => void assignments.refetch()}>重读关联历史</Button></p> : <ReadGrid table="oilcard-assignments" label="账户关联历史" rows={assignments.data ?? []} rowId={row => String(row.id)} scale={scale} domLayout="autoHeight" columns={[
        { field: 'changed_at', headerName: '关联时间' },
        { colId: 'change', headerName: '操作', valueGetter: p => p.data?.change_kind === 'replacement' ? '换卡' : '关联维护' },
        { colId: 'project', headerName: '项目', valueGetter: p => projects.data?.find(project => project.id === p.data?.project_id)?.disp || `项目 #${p.data?.project_id}` },
        { colId: 'card', headerName: '卡片', valueGetter: p => { const card = cards.find(c => c.id === p.data?.card_id); return card ? cardLabel(card) : '未关联卡片'; } },
        { colId: 'previous_card', headerName: '换卡前卡片', valueGetter: p => { if (p.data?.change_kind !== 'replacement') return '—'; const card = cards.find(c => c.id === p.data?.previous_card_id); return card ? cardLabel(card) : '未关联卡片'; } },
        { field: 'changed_by', headerName: '操作人' },
      ]} />}</section>}
    {replacing && data && <OilReplacementDialog account={replacing} archives={data} disabled={disabled} busy={busy} error={error} close={() => setReplacing(null)} submit={async fields => {
      const outcome = await saves.run(async signal => { await replaceOilCard(fields, replacing, signal); }, () => '', `${replacing.name} 换卡：`);
      if (outcome === 'saved' || outcome === 'uncertain') setReplacing(null);
    }} />}
  </section>;
}
