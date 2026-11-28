import { layoutCallback } from './grid-layout-callback';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { ApiError, projectLabel, readProjects, requestJson } from './api';
import type { Identity, Project } from './api';
import { BusinessGrid } from './business-grid';
import { BoundedGrid } from './bounded-grid';
import { contentWidth, fullTextWidth } from './grid';
import { readHistory } from './history';
import { PageActivity } from './page-activity';
import { randomUUID } from './random-id';
import { useCellSaveQueue } from './use-cell-save';
import { rowsInOrder, useGridRowDrag } from './use-grid-row-drag';
import { deleteOilArchive, getOilArchives, getOilAssignments, oilArchiveOrder, saveOilAccount, saveOilArchiveOrder, saveOilCard } from './oilcard-api';
import type { AccountFields, CardFields, OilAccount, OilArchives, OilCard, OilOrderKind } from './oilcard-api';
import { OilDeleteDialog } from './oilcard-delete-dialog';
import { OilArchiveAccountDialog, OilCardRelationsTable } from './oilcard-receive-detail';
import { archiveOilAccount } from './oilcard-api';
import { OilLedgerSheet } from './oilcard-ledger';
import { OilReconciliationSheet } from './oilcard-reconciliation';
import { OilLinkageSheet } from './oilcard-linkage';
import { OilTotalExport } from './oilcard-export';
import { FirstReadRegion, ReadPlaceholder, ReadStatusLane, readPhase } from './read-region';
import { DialogPresence, WorkspaceMarker, WorkspacePanel } from './workspace-motion';

type ArchiveKind = 'card' | 'account';
type Field = 'card_no' | 'kind' | 'remark' | 'name' | 'project_id' | 'card_id' | 'status';
type Draft = { kind: ArchiveKind; id: number; field: Field; original: string; value: string; error: string };
type PendingAccount = OilAccount;
const keyOf = (kind: ArchiveKind, id: number, field: Field) => `${kind}:${id}:${field}`;
const text = (value: unknown) => value === null || value === undefined ? '' : String(value);
const fieldValues: Record<Field, (row: OilCard | OilAccount) => string | number | null | undefined> = {
  card_no: row => 'card_no' in row ? row.card_no : undefined,
  kind: row => 'kind' in row ? row.kind : undefined,
  remark: row => row.remark,
  name: row => 'name' in row ? row.name : undefined,
  project_id: row => 'project_id' in row ? row.project_id : undefined,
  card_id: row => 'card_id' in row ? row.card_id : undefined,
  status: row => row.status,
};
const cardLabel = (card: OilCard) => `${card.card_no || `卡号待补 #${card.id}`}${card.status === 'archived' ? '（归档）' : ''}`;
const fieldLabels: Record<Field, string> = { card_no: '完整卡号更正', kind: '主卡/副卡', remark: '备注', name: '账户名称', project_id: '项目', card_id: '关联卡片', status: '账户状态' };
interface Cells {
  drafts: Record<string, Draft>; disabled: boolean; busy: boolean; projects: Project[]; cards: OilCard[]; accounts: OilAccount[]; pending: PendingAccount | null;
  change: (kind: ArchiveKind, row: OilCard | OilAccount, field: Field, value: string) => void;
  save: (kind: ArchiveKind, row: OilCard | OilAccount, field: Field) => void;
  showHistory: (row: OilAccount) => void;
  structuralDisabled: boolean;
  remove: (kind: ArchiveKind, row: OilCard | OilAccount) => void;
  addSecondary: (row: OilCard) => void;
  collapsed: Set<number>;
  toggleGroup: (id: number) => void;
  visibleParents: Set<number>;
}
const ArchiveCells = createContext<Cells | null>(null);
function ArchiveEditor({ kind, row: rendered, field }: { kind: ArchiveKind; row: OilCard | OilAccount; field: Field }) {
  const state = useContext(ArchiveCells)!;
  const row = kind === 'card' ? state.cards.find(item => item.request_id === rendered.request_id) : state.accounts.find(item => item.request_id === rendered.request_id) ?? (state.pending?.request_id === rendered.request_id ? state.pending : null);
  if (!row) return null;
  const key = keyOf(kind, row.id, field), draft = state.drafts[key];
  const original = text(fieldValues[field](row)), value = draft?.value ?? original;
  const label = `${field === 'status' && kind === 'card' ? '油卡状态' : fieldLabels[field]}：${'name' in row ? row.name || '新增账户' : cardLabel(row)}`;
  const disabled = state.disabled || row.id === 0 && state.busy;
  const change = (next: string) => state.change(kind, row, field, next);
  let options: { value: string; label: string }[] | undefined;
  if (field === 'kind') options = [{ value: 'primary', label: '主卡' }, { value: 'secondary', label: '副卡' }];
  if (field === 'status') options = [{ value: 'active', label: '在用' }, { value: 'archived', label: '归档' }];
  if (field === 'project_id') options = [{ value: '', label: '请选择项目' }, ...state.projects.filter(p => p.project_type !== 'shell').map(p => ({ value: String(p.id), label: `${projectLabel(p)}${p.status === 'archived' ? '（项目归档）' : ''}` }))];
  if (field === 'card_id') options = [{ value: '', label: '未关联卡片' }, ...state.cards.filter(c => c.kind === 'secondary' && (c.status === 'active' || String(c.id) === value)).map(c => ({ value: String(c.id), label: cardLabel(c) }))];
  return <div className="oilcard-cell">{options ? <Select aria-label={label} value={field === 'project_id' && value === '0' ? '' : value} disabled={disabled} status={draft?.error ? 'error' : ''}
    showSearch={{ optionFilterProp: 'label' }} options={options} onChange={next => change(next)} /> : <Input aria-label={label} value={value} disabled={disabled} status={draft?.error ? 'error' : ''}
    className="record-value" placeholder={field === 'card_no' ? '未知可留空' : undefined} onChange={e => change(e.target.value)}
    onBlur={() => state.save(kind, row, field)} onKeyDown={e => { if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }} />}
    {draft?.error && <p role="alert" className="oilcard-cell-error">{draft.error}</p>}</div>;
}
const cardFields = (row: OilCard): CardFields => ({ card_no: row.card_no, kind: row.kind, parent_card_id: row.parent_card_id, status: row.status, remark: row.remark });
const accountFields = (row: OilAccount): AccountFields => ({ name: row.name, project_id: row.project_id, card_id: row.card_id, status: row.status, remark: row.remark });

function AccountActions({ row }: { row: OilAccount }) {
  const state = useContext(ArchiveCells)!, current = state.accounts.find(item => item.id === row.id);
  return <div className="oilcard-row-actions">
    {current && <Button size="small" disabled={state.busy} aria-label={`查看${current.name}的用卡记录`} onClick={() => state.showHistory(current)}>用卡记录</Button>}
    <Button size="small" danger disabled={row.id ? state.structuralDisabled : state.disabled || state.busy}
      onMouseDown={event => { if (!row.id) event.preventDefault(); }} onClick={() => state.remove('account', row)}>删除</Button>
  </div>;
}

function CardNumber({ row }: { row: OilCard }) {
  const { collapsed, toggleGroup, visibleParents } = useContext(ArchiveCells)!;
  const closed = collapsed.has(row.id);
  return <div className={row.kind === 'primary' ? 'oilcard-primary' : 'oilcard-child-card'}>
    {row.kind === 'primary' && visibleParents.has(row.id) && <Button size="small" aria-label={`${closed ? '展开' : '收起'} ${cardLabel(row)}`} aria-expanded={!closed} onClick={() => toggleGroup(row.id)}>{closed ? '展开' : '收起'}</Button>}
    <ArchiveEditor kind="card" row={row} field="card_no" />
  </div>;
}

function CardActions({ row }: { row: OilCard }) {
  const state = useContext(ArchiveCells)!;
  return <div className="oilcard-row-actions">
    {row.kind === 'primary' && row.status === 'active' && <Button size="small" disabled={state.structuralDisabled} onClick={() => state.addSecondary(row)}>新增副卡</Button>}
    <Button size="small" danger disabled={state.structuralDisabled} onClick={() => state.remove('card', row)}>删除</Button>
  </div>;
}

export function OilCardPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const client = useQueryClient();
  const [tab, setTab] = useState<'overview' | 'ledger' | 'linkage' | 'archives'>('overview'), [status, setStatus] = useState('active');
  const [cardStatus, setCardStatus] = useState('active');
  const [focusPrimaryId, setFocusPrimaryId] = useState<number | null>(null);
  const [archiving, setArchiving] = useState<{ account: OilAccount; card: OilCard } | null>(null);
  const [visited, setVisited] = useState(() => new Set<typeof tab>(['overview']));
  const [ledgerLocked, setLedgerLocked] = useState(false);
  const [ledgerUncertain, setLedgerUncertain] = useState(false);
  const [linkageLocked, setLinkageLocked] = useState(false), [linkageUncertain, setLinkageUncertain] = useState(false);
  const [pending, setPending] = useState<PendingAccount | null>(null), pendingRef = useRef(pending); pendingRef.current = pending;
  const [historyAccount, setHistoryAccount] = useState(0);
  const [collapsed, setCollapsed] = useState<Set<number>>(() => new Set());
  const [deletion, setDeletion] = useState<{ kind: ArchiveKind; row: OilCard | OilAccount } | null>(null);
  const query = useQuery({ queryKey: ['oilcard-archives'], enabled: active && !blocked, queryFn: ({ signal }) => getOilArchives(signal) });
  const projects = useQuery({ queryKey: ['projects', 'all'], enabled: active && !blocked, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const assignments = useQuery({ queryKey: ['oilcard-assignments', historyAccount], enabled: active && !blocked && historyAccount > 0, queryFn: ({ signal }) => getOilAssignments(historyAccount, signal) });
  const data = query.data;
  const currentData = useRef(data); currentData.current = data;
  const focusPrimary = data?.cards.find(card => card.id === focusPrimaryId && card.kind === 'primary');
  const focusCards = useMemo(() => focusPrimary && data ? data.cards.filter(card => card.parent_card_id === focusPrimary.id) : [], [data, focusPrimary]);
  const focusCardIds = useMemo(() => focusPrimary ? new Set([focusPrimary.id, ...focusCards.map(card => card.id)]) : null, [focusPrimary, focusCards]);
  const saves = useCellSaveQueue<Draft, OilArchives>({
    enabled: active && !blocked && Boolean(me), canWrite: Boolean(data && !query.isError && projects.data && !projects.isError && !ledgerLocked && !linkageLocked),
    read: reload, write: async (draft, signal) => {
      const row = draft.kind === 'card' ? currentData.current?.cards.find(r => r.id === draft.id) : currentData.current?.accounts.find(r => r.id === draft.id);
      if (!row) throw new ApiError('这条档案已不在当前结果内，请重读核对。', 409);
      const original = text(fieldValues[draft.field](row));
      if (original !== draft.original) throw new ApiError('这个字段已变化，请重读核对后处理保留输入。', 409);
      const value = ['project_id', 'card_id'].includes(draft.field) ? draft.value ? Number(draft.value) : null : draft.field === 'card_no' ? draft.value.trim() || null : draft.field === 'name' ? draft.value.trim() : draft.value;
      if (draft.kind === 'card') {
        const fields = { ...cardFields(row as OilCard), [draft.field]: value };
        if (draft.field === 'kind' && value === 'primary') fields.parent_card_id = null;
        await saveOilCard(fields, row, signal);
      } else await saveOilAccount({ ...accountFields(row as OilAccount), [draft.field]: value }, row, signal);
    },
    acknowledge: (current, submitted) => current.value === submitted.value ? undefined : { ...current, original: submitted.field === 'card_no' || submitted.field === 'name' ? submitted.value.trim() : submitted.value },
    saved: () => '', validate: d => d.field === 'name' && !d.value.trim() ? '请填写账户名称。' : '',
  }, { key: 'oilcard-archives', label: '油卡档案', pending: Boolean(pending || archiving) });
  async function reload() {
    await client.invalidateQueries({ refetchType: 'none' });
    await client.cancelQueries({ queryKey: ['oilcard-archives'], exact: true });
    const result = await client.fetchQuery({ queryKey: ['oilcard-archives'], staleTime: 0, queryFn: ({ signal }) => getOilArchives(signal) });
    currentData.current = result;
    await projects.refetch({ throwOnError: true });
    if (historyAccount) await client.fetchQuery({ queryKey: ['oilcard-assignments', historyAccount], staleTime: 0, queryFn: ({ signal }) => getOilAssignments(historyAccount, signal) });
    if (me) await client.fetchQuery({ queryKey: ['history', `${me.id}:${me.account}`], staleTime: 0, queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
    return result;
  }
  const { drafts, busy, uncertain, verified, error } = saves, dirty = Object.keys(drafts).length > 0;
  const disabled = blocked || !active || !me || uncertain || ledgerLocked || linkageLocked || !data || query.isError || !projects.data || projects.isError;
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
    if (kind === 'account' && 'name' in row && row.id && field === 'status' && row.status === 'active' && value === 'archived') {
      const card = data?.cards.find(item => item.id === row.card_id && item.kind === 'secondary' && item.status === 'active');
      if (card && !data?.accounts.some(account => account.id !== row.id && account.card_id === card.id && account.status === 'active')) {
        if (!structuralDisabled) { saves.clearFeedback(); setArchiving({ account: row, card }); }
        return;
      }
    }
    if (row.id === 0 && pendingRef.current) {
      const next = { ...pendingRef.current, [field]: ['project_id', 'card_id'].includes(field) ? value ? Number(value) : field === 'project_id' ? 0 : null : value };
      pendingRef.current = next; setPending(next);
      if (['project_id', 'card_id', 'status'].includes(field)) void createAccount(next);
      return;
    }
    const key = keyOf(kind, row.id, field), original = text(fieldValues[field](row));
    saves.update((ds, writing) => {
      const next = { ...ds }, previous = ds[key];
      if (value === original && !writing) delete next[key];
      else next[key] = { kind, id: row.id, field, value, original: previous?.original ?? original, error: '' };
      return next;
    });
    if (['kind', 'project_id', 'card_id', 'status'].includes(field)) saves.save(key);
  }
  function save(kind: ArchiveKind, row: OilCard | OilAccount, field: Field) {
    const actual = kind === 'card' ? currentData.current?.cards.find(item => item.request_id === row.request_id) : currentData.current?.accounts.find(item => item.request_id === row.request_id);
    if (actual) row = actual;
    if (row.id === 0) { if (pendingRef.current) void createAccount(pendingRef.current); }
    else saves.save(keyOf(kind, row.id, field));
  }
  async function submitArchive(together: boolean) {
    if (!archiving || structuralDisabled) return;
    const { account, card } = archiving;
    const outcome = await saves.run(signal => archiveOilAccount(account, together ? card : null, signal), () => '', '归档用卡账户：');
    if (outcome === 'saved' || outcome === 'uncertain') setArchiving(null);
  }
  async function addCard(parent?: OilCard) {
    if (structuralDisabled) return;
    const request_id = randomUUID();
    const result = await saves.run(async signal => { await saveOilCard({ card_no: null, kind: parent ? 'secondary' : 'primary', parent_card_id: parent?.id ?? null, status: 'active', remark: '' }, { request_id }, signal); }, () => '', parent ? '新增副卡：' : '新增主卡：');
    if (result === 'saved') {
      if (cardStatus === 'archived') setCardStatus('active');
      if (parent) setCollapsed(old => { const next = new Set(old); next.delete(parent.id); return next; });
    }
  }
  function remove(kind: ArchiveKind, row: OilCard | OilAccount) {
    if (!row.id) { setPending(null); pendingRef.current = null; }
    else if (!structuralDisabled) { saves.clearFeedback(); setDeletion({ kind, row }); }
  }
  async function submitDelete() {
    if (!deletion || structuralDisabled) return;
    const { kind, row } = deletion;
    const result = await saves.run(signal => deleteOilArchive(kind, row, signal),
      refreshed => (kind === 'card' ? refreshed.cards : refreshed.accounts).some(item => item.id === row.id) ? '档案仍在，请重读核对。' : '', '删除油卡档案：');
    if (result === 'saved' || result === 'uncertain') setDeletion(null);
  }
  async function reorder(kind: OilOrderKind, parentId: number | null, previous: number[], order: number[]) {
    if (structuralDisabled) return;
    await saves.run(signal => saveOilArchiveOrder(kind, parentId, previous, order, signal),
      refreshed => JSON.stringify(oilArchiveOrder(refreshed, kind, parentId)) === JSON.stringify(order) ? '' : '显示顺序已变化，请重读核对。', '保存显示顺序：');
  }
  function addAccount() {
    if (structuralDisabled) return;
    const row: OilAccount = { id: 0, request_id: randomUUID(), version: '', name: '', project_id: 0, card_id: null, status: 'active', remark: '' };
    pendingRef.current = row; setPending(row);
  }
  const accountDrag = useGridRowDrag<OilAccount>({
    disabled: structuralDisabled || tab !== 'archives',
    sourceId: row => row.id || null, targetId: (_, row) => row.id || null,
    orderFor: () => currentData.current ? oilArchiveOrder(currentData.current, 'account', null) : [],
    save: (_, previous, order) => reorder('account', null, previous, order),
  });
  const cardDrag = useGridRowDrag<OilCard>({
    disabled: structuralDisabled || tab !== 'archives',
    sourceId: row => row.id,
    targetId: (from, to) => from.kind === 'primary' ? to.kind === 'primary' ? to.id : to.parent_card_id
      : to.kind === 'secondary' && to.parent_card_id === from.parent_card_id ? to.id : null,
    orderFor: row => currentData.current ? oilArchiveOrder(currentData.current, row.kind, row.parent_card_id) : [],
    save: (row, previous, order) => reorder(row.kind, row.parent_card_id, previous, order),
  });
  const accountPreview = accountDrag.preview?.order, cardPreview = cardDrag.preview;
  const accounts = useMemo(() => {
    const saved = data?.accounts ?? [];
    return [...rowsInOrder(saved, accountPreview, row => row.id).filter(a => (!focusCardIds || a.card_id !== null && focusCardIds.has(a.card_id)) && (status === 'all' || a.status === status)),
      ...(pending && !saved.some(a => a.request_id === pending.request_id) ? [pending] : [])];
  }, [data, status, pending, accountPreview, focusCardIds]);
  const cards = useMemo(() => data?.cards ?? [], [data]);
  const { visibleCards, visibleParents } = useMemo(() => {
    const included = cards.filter(card => (!focusCardIds || focusCardIds.has(card.id)) && (cardStatus === 'all' || card.status === cardStatus));
    const children = new Map<number | null, OilCard[]>();
    for (const card of included) if (card.kind === 'secondary') {
      const group = children.get(card.parent_card_id) ?? [];
      group.push(card);
      children.set(card.parent_card_id, group);
    }
    if (cardPreview?.source.kind === 'secondary') {
      const parent = cardPreview.source.parent_card_id;
      children.set(parent, rowsInOrder(children.get(parent) ?? [], cardPreview.order, row => row.id));
    }
    const parents = cards.filter(card => card.kind === 'primary' && (included.includes(card) || children.has(card.id)));
    return {
      visibleCards: [...rowsInOrder(parents, cardPreview?.source.kind === 'primary' ? cardPreview.order : undefined, row => row.id)
        .flatMap(card => [card, ...(collapsed.has(card.id) ? [] : children.get(card.id) ?? [])]), ...children.get(null) ?? []],
      visibleParents: new Set([...children.keys()].filter((id): id is number => id !== null)),
    };
  }, [cards, cardStatus, collapsed, cardPreview, focusCardIds]);
  const cardNumberWidth = fullTextWidth(cards.map(c => c.card_no || '卡号待补 #000'), scale).minWidth;
  const cardColumns = useMemo<ColDef<OilCard>[]>(() => [
    { field: 'card_no', headerName: '完整卡号', rowDrag: true, ...contentWidth(Math.max(240, cardNumberWidth / scale + 100), 380, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilCard>) => row && <CardNumber row={row} /> },
    { field: 'kind', headerName: '主卡/副卡', ...contentWidth(100, 130, scale), cellRenderer: ({ data: row }: ICellRendererParams<OilCard>) => row && <ArchiveEditor kind="card" row={row} field="kind" /> },
    { field: 'status', headerName: '状态', ...contentWidth(90, 120, scale), cellRenderer: ({ data: row }: ICellRendererParams<OilCard>) => row && <ArchiveEditor kind="card" row={row} field="status" /> },
    { field: 'remark', headerName: '备注', ...contentWidth(130, 350, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilCard>) => row && <ArchiveEditor kind="card" row={row} field="remark" /> },
    { colId: 'actions', headerName: '操作', pinned: 'right', ...contentWidth(150, 180, scale), cellRenderer: ({ data: row }: ICellRendererParams<OilCard>) => row && <CardActions row={row} /> },
  ], [scale, cardNumberWidth]);
  const accountColumns = useMemo<ColDef<OilAccount>[]>(() => [
    { field: 'name', headerName: '账户名称', pinned: 'left', rowDrag: p => Boolean(p.data?.id), ...contentWidth(150, 240, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="name" /> },
    { field: 'project_id', headerName: '项目', ...contentWidth(130, 240, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="project_id" /> },
    { field: 'card_id', headerName: '关联卡片', ...contentWidth(190, 260, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="card_id" /> },
    { field: 'status', headerName: '状态', ...contentWidth(90, 120, scale), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="status" /> },
    { field: 'remark', headerName: '备注', ...contentWidth(130, 280, scale, 1), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <ArchiveEditor kind="account" row={row} field="remark" /> },
    { colId: 'actions', headerName: '操作', pinned: 'right', ...contentWidth(150, 180, scale), cellRenderer: ({ data: row }: ICellRendererParams<OilAccount>) => row && <AccountActions row={row} /> },
  ], [scale]);
  const state: Cells = { drafts, disabled, busy, projects: projects.data ?? [], cards, accounts: data?.accounts ?? [], pending, change, save, showHistory: row => setHistoryAccount(row.id),
    structuralDisabled, remove, addSecondary: row => void addCard(row), collapsed, visibleParents,
    toggleGroup: id => setCollapsed(old => { const next = new Set(old); if (next.has(id)) next.delete(id); else next.add(id); return next; }) };
  const readState = readPhase(query);
  const projectsWait = projects.isPending && !projects.data;
  const dependencyPhase = data && (projects.data || projects.isError) ? 'content' : !data && query.isError ? 'error' : 'pending';
  const renderRemark = useCallback((kind: ArchiveKind, row: OilCard | OilAccount) => <ArchiveEditor kind={kind} row={row} field="remark" />, []);
  function chooseTab(value: typeof tab) {
    setVisited(previous => previous.has(value) ? previous : new Set(previous).add(value));
    setTab(value);
  }
  const pageLayout = tab === 'ledger' || tab === 'archives' ? 'split' : 'flow';
  return <section className={`wb-surface oilcard-page page-shell page-shell--${pageLayout}${pageLayout === 'split' ? ' oilcard-page-bounded' : ''}`} data-page-layout={pageLayout} aria-label="油卡管理">
    <div data-page-chrome className="oilcard-workspace-bar"><div className="oilcard-tabs" role="tablist" aria-label="油卡工作表">{([{ value: 'overview', label: '账户核对' }, { value: 'ledger', label: '充值与发票' }, { value: 'linkage', label: '用油联动' }, { value: 'archives', label: '账户与油卡' }] as const).map(item => <button type="button" className="oilcard-tab" key={item.value} role="tab" id={`oilcard-tab-${item.value}`} aria-controls={`oilcard-panel-${item.value}`} aria-selected={tab === item.value} onClick={() => chooseTab(item.value)}>{item.label}{tab === item.value && <WorkspaceMarker className="oilcard-tab-marker" layoutId="oilcard-workspace-tab" />}</button>)}</div><OilTotalExport disabled={disabled || busy || ledgerLocked || linkageLocked} active={active && !blocked} /></div>
    {!me && <p className="state">登录后可维护油卡档案。</p>}
    {ledgerUncertain && tab !== 'ledger' && <p className="notice" role="alert">充值或收票结果待核实，请先核对后再继续编辑。<Button onClick={() => chooseTab('ledger')}>核对保存结果</Button></p>}
    {linkageUncertain && tab !== 'linkage' && <p className="notice" role="alert">用油自定义额保存结果待核实，请先核对后再继续编辑。<Button onClick={() => chooseTab('linkage')}>核对保存结果</Button></p>}
    {error && <p className="notice" role="alert">{error}<Button disabled={blocked || busy} onClick={() => void saves.reread()}>重读核对</Button></p>}
    {uncertain && <p className="notice" role="alert">核对刚才的档案变更后再继续。<Button disabled={!verified || blocked || busy} onClick={() => saves.confirm()}>已核对，保留输入继续</Button></p>}
    {Object.entries(drafts).filter(([, d]) => d.error).map(([key, d]) => <p className="oilcard-draft-error" key={key}>{fieldLabels[d.field]}：{d.error}<Button size="small" disabled={disabled || busy} onMouseDown={e => e.preventDefault()} onClick={() => saves.save(key, true)}>重试保存</Button><Button size="small" disabled={blocked || busy || uncertain} onMouseDown={e => e.preventDefault()} onClick={() => saves.update(ds => { const next = { ...ds }; delete next[key]; return next; })}>还原该字段</Button></p>)}
    <ReadStatusLane phase={projectsWait ? 'reading' : readState} announce="正在读取油卡档案及项目…">
      {(query.isError || projects.isError) && <p className="notice" role="alert"><span className="read-failure-text">{data && '更新未成功，保留上次结果。'}{query.error?.message || projects.error?.message}</span><Button disabled={blocked || busy} onClick={() => void saves.reread()}>重读核对</Button></p>}
    </ReadStatusLane>
    <ArchiveCells.Provider value={state}>
      <div className="workspace-panels page-split-panels">
      {(tab === 'ledger' || tab === 'linkage') && (!data || projectsWait) && <div className="oilcard-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={6} quiet={dependencyPhase === 'error'} /></div>}
      <WorkspacePanel id="oilcard-panel-overview" labelledBy="oilcard-tab-overview" active={tab === 'overview'}><PageActivity.Provider value={active && tab === 'overview'}><OilReconciliationSheet archives={data} dependencyPhase={dependencyPhase} projects={projects.data ?? []} active={active && tab === 'overview'} blocked={blocked} scale={scale} remark={renderRemark} sortDisabled={structuralDisabled} movePrimary={(previous, order) => reorder('primary', null, previous, order)} /></PageActivity.Provider></WorkspacePanel>
      <WorkspacePanel id="oilcard-panel-ledger" labelledBy="oilcard-tab-ledger" active={tab === 'ledger'}>{visited.has('ledger') && data && !projectsWait && <PageActivity.Provider value={active && tab === 'ledger'}><OilLedgerSheet me={me} archives={data} projects={projects.data ?? []} active={active && tab === 'ledger'} blocked={blocked} scale={scale} archiveLocked={busy || uncertain || linkageLocked || query.isError || projects.isError} onWriteLock={setLedgerLocked} onUncertain={setLedgerUncertain} /></PageActivity.Provider>}</WorkspacePanel>
      <WorkspacePanel id="oilcard-panel-linkage" labelledBy="oilcard-tab-linkage" active={tab === 'linkage'}>{visited.has('linkage') && data && !projectsWait && <PageActivity.Provider value={active && tab === 'linkage'}><OilLinkageSheet me={me} projects={projects.data ?? []} accounts={data.accounts} active={active && tab === 'linkage'} blocked={blocked} scale={scale} otherLocked={busy || uncertain || ledgerLocked || query.isError || projects.isError} onWriteLock={setLinkageLocked} onUncertain={setLinkageUncertain} /></PageActivity.Provider>}</WorkspacePanel>
      <WorkspacePanel id="oilcard-panel-archives" labelledBy="oilcard-tab-archives" active={tab === 'archives'}>{visited.has('archives') && <PageActivity.Provider value={active && tab === 'archives'}>
        {data && <div className="oilcard-archive-relations">
          <div data-page-chrome className="oilcard-receive-actions">
            <label>按主卡核对<Select aria-label="按主卡核对" allowClear showSearch={{ optionFilterProp: 'label' }} placeholder="输入卡号或尾号"
              value={focusPrimaryId} options={cards.filter(card => card.kind === 'primary').map(card => ({ value: card.id, label: cardLabel(card) }))}
              onChange={id => {
                setFocusPrimaryId(id ?? null);
                if (id) {
                  setStatus('all'); setCardStatus('all');
                  setCollapsed(previous => { const next = new Set(previous); next.delete(id); return next; });
                }
              }} /></label>
            {focusPrimary && <span>主卡 {focusPrimary.status === 'active' ? '在用' : '已归档'}</span>}
          </div>
          {focusPrimary && <OilCardRelationsTable archives={data} projects={projects.data ?? []} cards={focusCards} />}
        </div>}
        <div className="oilcard-archive-panes wb-split-grid"><section className="wb-surface oilcard-archive-section" aria-label="用卡账户"><div data-page-chrome className="oilcard-toolbar"><h2>用卡账户</h2><div><label>状态<Select aria-label="账户状态筛选" value={status} onChange={setStatus} options={[{ value: 'all', label: '全部' }, { value: 'active', label: '在用' }, { value: 'archived', label: '归档' }]} /></label><Button type="primary" disabled={structuralDisabled} onClick={addAccount}>新增账户</Button></div></div>
        <FirstReadRegion className="oilcard-grid-slot" phase={dependencyPhase} placeholder={<div className="oilcard-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={6} quiet={dependencyPhase === 'error'} /></div>}>
        {!accounts.length ? <p className="state">尚无符合条件的用卡账户。</p> : <BusinessGrid table="oilcard-accounts" label="用卡账户档案" rows={accounts} columns={accountColumns} rowId={row => row.id ? String(row.id) : `draft-${row.request_id}`} scale={scale} domLayout="normal" grid={{ ...accountDrag.grid,
          rowClassRules: { 'oilcard-selected': p => Boolean(p.data?.id && p.data.id === historyAccount), 'grid-row-dragging': p => p.node.id === accountDrag.rowId },
        }} />}</FirstReadRegion></section>
        <section className="wb-surface oilcard-archive-section" aria-label="实体油卡"><div data-page-chrome className="oilcard-toolbar"><h2>实体油卡</h2><div><label>状态<Select aria-label="油卡状态筛选" value={cardStatus} onChange={setCardStatus} options={[{ value: 'all', label: '全部' }, { value: 'active', label: '在用' }, { value: 'archived', label: '归档' }]} /></label><Button type="primary" disabled={structuralDisabled} onClick={() => void addCard()}>新增主卡</Button></div></div>
        <FirstReadRegion className="oilcard-grid-slot" phase={dependencyPhase} placeholder={<div className="oilcard-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={6} quiet={dependencyPhase === 'error'} /></div>}>
        {!visibleCards.length ? <p className="state">尚无符合条件的实体油卡。</p> : <BusinessGrid table="oilcard-cards" label="实体油卡档案" rows={visibleCards} columns={cardColumns} rowId={row => String(row.id)} scale={scale} domLayout="normal" grid={{ ...cardDrag.grid,
          rowClassRules: { 'oilcard-primary-row': p => p.data?.kind === 'primary', 'grid-row-dragging': p => p.node.id === cardDrag.rowId },
        }} />}</FirstReadRegion></section></div>
      </PageActivity.Provider>}</WorkspacePanel>
      </div>
    </ArchiveCells.Provider>
    <DialogPresence>{archiving && <OilArchiveAccountDialog account={archiving.account} card={archiving.card} busy={busy} error={error}
      close={() => setArchiving(null)} confirm={together => void submitArchive(together)} />}</DialogPresence>
    <DialogPresence>{deletion && <OilDeleteDialog title={deletion.kind === 'card' ? '删除实体油卡' : '删除用卡账户'} busy={busy} disabled={structuralDisabled} error={error} close={() => setDeletion(null)} submit={() => void submitDelete()}>
      <p>{'name' in deletion.row ? deletion.row.name : cardLabel(deletion.row)}</p>
      <p>仅可删除未被业务使用的档案。主卡须先处理所属副卡。</p>
    </OilDeleteDialog>}</DialogPresence>
    {historyAccount > 0 && tab === 'archives' && <section className="wb-surface oilcard-assignment-history" aria-label="用卡账户关联历史"><div className="oilcard-toolbar"><h2>{data?.accounts.find(a => a.id === historyAccount)?.name}的用卡记录</h2><Button onClick={() => setHistoryAccount(0)}>收起用卡记录</Button></div>
      {assignments.isPending ? <p role="status">正在读取关联历史…</p> : assignments.isError ? <p role="alert" className="notice">{assignments.error.message}<Button disabled={blocked} onClick={() => void assignments.refetch()}>重读关联历史</Button></p> : <BoundedGrid maxHeight="24dvh" minRows={2} table="oilcard-assignments" label="账户关联历史" rows={assignments.data ?? []} rowId={row => String(row.id)} scale={scale} columns={[
        { field: 'changed_at', headerName: '关联时间' },
        { colId: 'change', headerName: '操作', valueGetter: layoutCallback(p => p.data?.change_kind === 'replacement' ? '换卡' : '关联维护') },
        { colId: 'project', headerName: '项目', valueGetter: layoutCallback(p => projects.data?.find(project => project.id === p.data?.project_id)?.disp || `项目 #${p.data?.project_id}`) },
        { colId: 'card', headerName: '卡片', valueGetter: layoutCallback(p => { const card = cards.find(c => c.id === p.data?.card_id); return card ? cardLabel(card) : '未关联卡片'; }) },
        { colId: 'previous_card', headerName: '换卡前卡片', valueGetter: layoutCallback(p => { if (p.data?.change_kind !== 'replacement') return '—'; const card = cards.find(c => c.id === p.data?.previous_card_id); return card ? cardLabel(card) : '未关联卡片'; }) },
        { field: 'changed_by', headerName: '操作人' },
      ]} />}</section>}
  </section>;
}
