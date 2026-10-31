import Button from 'antd/es/button';
import Input from 'antd/es/input';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ColGroupDef, ICellRendererParams } from 'ag-grid-community';
import { ApiError, cents, decimal, money, projectLabel, requestJson } from './api';
import type { Identity, Project } from './api';
import { BusinessGrid } from './business-grid';
import { contentWidth, fullTextWidth } from './grid';
import { readHistory } from './history';
import { reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { useCellSaveQueue } from './use-cell-save';
import { enableOilBigLinkage, enableOilFeeLinkage, getOilLinkage, saveOilBigCustom, saveOilFeeCustom } from './oilcard-linkage-api';
import type { OilFeeMonth, OilLinkage } from './oilcard-linkage-api';

type Field = 'custom_amount' | 'remark' | 'big_amount' | 'big_remark';
type Draft = { projectId: number; ym: string; field: Field; original: string; value: string; error: string };
const labels: Record<Field, string> = { custom_amount: '特殊费用自定义额', remark: '特殊费用用油备注', big_amount: '大表额外自定义额', big_remark: '大表用油独立备注' };
const isBig = (field: Field) => field === 'big_amount' || field === 'big_remark';
const valueOf = (row: OilFeeMonth, field: Field) => (field === 'big_amount' ? row.big.extra_amount : field === 'big_remark' ? row.big.remark : row[field]) ?? '';
const keyOf = (row: OilFeeMonth, field: Field) => `${row.project_id}:${row.ym}:${field}`;
interface Cells { rows: OilFeeMonth[]; projects: Project[]; drafts: Record<string, Draft>; disabled: boolean; structuralDisabled: boolean; enable: (row: OilFeeMonth, big: boolean) => void; change: (row: OilFeeMonth, field: Field, value: string) => void; save: (key: string) => void }
const LinkageCells = createContext<Cells | null>(null);
function Editor({ data: rendered, colDef }: ICellRendererParams<OilFeeMonth>) {
  const state = useContext(LinkageCells)!, [focused, setFocused] = useState(false);
  const row = state.rows.find(item => item.project_id === rendered?.project_id);
  if (!row) return null;
  const field = (colDef?.colId ?? colDef?.field) as Field, key = keyOf(row, field), draft = state.drafts[key], original = valueOf(row, field), numeric = field === 'custom_amount' || field === 'big_amount';
  const project = state.projects.find(project => project.id === row.project_id);
  const label = `${row.ym} ${project ? projectLabel(project) : `项目 #${row.project_id}`} ${labels[field]}`;
  if (!(isBig(field) ? row.big.enabled : row.enabled)) return <span className="muted">—</span>;
  return <div className="oilcard-cell"><Input aria-label={label} value={draft?.value ?? (numeric && original && !focused ? money(original) : original)}
    className={numeric ? 'record-value oilcard-amount' : 'record-value'} disabled={state.disabled} status={draft?.error ? 'error' : ''}
    onFocus={() => setFocused(true)} onChange={e => state.change(row, field, e.target.value)} onBlur={() => { setFocused(false); state.save(key); }}
    onKeyDown={e => { if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }} />
    {field === 'big_amount' && <span className="big-origin" title="清空本月额外值恢复更早快照；填0终止旧值沿用">{row.big.source_ym === row.ym ? '本月' : row.big.source_ym ? `沿用 ${row.big.source_ym}` : '未维护'}</span>}
    {draft?.error && <p role="alert" className="oilcard-cell-error">{draft.error}</p>}</div>;
}

function LinkageState({ data: row, colDef }: ICellRendererParams<OilFeeMonth>) {
  const state = useContext(LinkageCells)!;
  if (!row) return null;
  const big = colDef?.colId === 'big_state', value = big ? row.big : row;
  if (value.enabled) return '已启用';
  return value.can_enable ? <Button size="small" disabled={state.structuralDisabled} onClick={() => state.enable(row, big)}>{big ? '启用大表联动' : '启用用油联动'}</Button> : <span className="muted">{big && !row.enabled ? '先核对特殊费用' : '待接续核对'}</span>;
}

export function OilLinkageSheet({ me, projects, active, blocked, scale, otherLocked, onWriteLock, onUncertain }: {
  me: Identity | null; projects: Project[]; active: boolean; blocked: boolean; scale: number; otherLocked: boolean;
  onWriteLock: (value: boolean) => void; onUncertain: (value: boolean) => void;
}) {
  const [ym, setYm] = useState(reportMonth), client = useQueryClient(), queryKey = ['oilcard-linkage', ym];
  const query = useQuery({ queryKey, enabled: active && !blocked, queryFn: ({ signal }) => getOilLinkage(ym, signal) });
  const current = useRef(query.data); current.current = query.data;
  const saves = useCellSaveQueue<Draft, OilLinkage>({ enabled: active && !blocked && Boolean(me), canWrite: Boolean(query.data && !query.isError && !otherLocked),
    read: reload, write: async (draft, signal) => {
      const row = current.current?.rows.find(item => item.project_id === draft.projectId && item.ym === draft.ym);
      if (!row || !(isBig(draft.field) ? row.big.enabled : row.enabled) || valueOf(row, draft.field) !== draft.original) throw new ApiError('这个项目的当月字段已变化，请重读核对后处理保留输入。', 409);
      if (isBig(draft.field)) {
        const amount = draft.field === 'big_amount' ? draft.value.trim() ? decimal(cents(draft.value)) : null : row.big.extra_amount ?? '0';
        await saveOilBigCustom(row, { amount, remark: amount === null ? '' : draft.field === 'big_remark' ? draft.value : row.big.remark }, signal);
      } else await saveOilFeeCustom(row, { amount: draft.field === 'custom_amount' ? draft.value.trim() ? decimal(cents(draft.value)) : null : row.custom_amount,
        remark: draft.field === 'remark' ? draft.value : row.remark }, signal);
    }, acknowledge: (present, submitted) => { if (present.value === submitted.value) return undefined; const row = current.current?.rows.find(row => row.project_id === submitted.projectId); return row ? { ...present, original: valueOf(row, submitted.field) } : present; },
    saved: () => '', validate: draft => { if (!['custom_amount', 'big_amount'].includes(draft.field) || !draft.value.trim()) return ''; try { cents(draft.value); return ''; } catch { return '请填写有效金额，允许正数、负数和零。'; } },
  }, { key: 'oilcard-linkage', label: '用油联动' });
  async function reload() {
    await client.invalidateQueries({ refetchType: 'none' });
    await client.cancelQueries({ queryKey, exact: true });
    const result = await client.fetchQuery({ queryKey, staleTime: 0, queryFn: ({ signal }) => getOilLinkage(ym, signal) });
    current.current = result;
    if (me) await client.fetchQuery({ queryKey: ['history', `${me.id}:${me.account}`], staleTime: 0, queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
    return result;
  }
  const { drafts, busy, uncertain, verified, error } = saves, dirty = Object.keys(drafts).length > 0;
  useEffect(() => { onWriteLock(busy || uncertain); }, [busy, uncertain, onWriteLock]);
  useEffect(() => { onUncertain(uncertain); }, [uncertain, onUncertain]);
  const disabled = blocked || !active || !me || uncertain || otherLocked || !query.data || query.isError;
  const rows = useMemo(() => query.data?.rows ?? [], [query.data]);
  const columns = useMemo<(ColDef<OilFeeMonth> | ColGroupDef<OilFeeMonth>)[]>(() => [
    { colId: 'project', headerName: '项目', pinned: 'left', valueGetter: p => { const project = projects.find(project => project.id === p.data?.project_id); return project ? projectLabel(project) : `项目 #${p.data?.project_id}`; }, ...contentWidth(180, 340, scale, 1) },
    { headerName: '当月特殊费用', marryChildren: true, children: [
    { colId: 'linkage_state', headerName: '联动状态', cellRenderer: LinkageState, ...contentWidth(150, 200, scale) },
    { field: 'recharge_amount', headerName: '当月充值', cellClass: 'money', valueFormatter: p => money(p.value), ...contentWidth(Math.max(130, fullTextWidth(rows.map(row => money(row.recharge_amount)), scale).minWidth / scale), 240, scale, 1) },
    { field: 'custom_amount', headerName: '特殊费用自定义额', cellRenderer: Editor, ...contentWidth(180, 260, scale, 1) },
    { field: 'remark', headerName: '特殊费用用油备注', cellRenderer: Editor, ...contentWidth(220, 460, scale, 2) },
    { field: 'fee_amount', headerName: '特殊费用用油', cellClass: 'money', valueFormatter: p => p.data?.enabled ? money(p.value) : '待接续核对', ...contentWidth(Math.max(150, fullTextWidth(rows.map(row => money(row.fee_amount)), scale).minWidth / scale), 260, scale, 1) },
    ] },
    { headerName: '截至月会议大表', marryChildren: true, children: [
      { colId: 'big_state', headerName: '联动状态', cellRenderer: LinkageState, ...contentWidth(150, 200, scale) },
      { colId: 'big_auto', headerName: '累计自动金额', cellClass: 'money', valueGetter: p => p.data ? decimal(cents(p.data.big.recharge_amount) + cents(p.data.big.fee_custom_amount)) : '',
        tooltipValueGetter: p => p.data ? `累计充值 ${money(p.data.big.recharge_amount)}＋累计特殊费用自定义额 ${money(p.data.big.fee_custom_amount)}` : '', valueFormatter: p => money(p.value), ...contentWidth(160, 240, scale, 1) },
      { colId: 'big_amount', headerName: '额外自定义额', autoHeight: true, cellRenderer: Editor, valueGetter: p => p.data?.big.extra_amount, ...contentWidth(170, 250, scale, 1) },
      { colId: 'big_remark', headerName: '独立备注', cellRenderer: Editor, valueGetter: p => p.data?.big.remark, ...contentWidth(200, 420, scale, 2) },
      { colId: 'big_total', headerName: '大表工程用油', cellClass: 'money', valueGetter: p => p.data?.big.amount, valueFormatter: p => p.data?.big.enabled ? money(p.value) : '待接续核对', ...contentWidth(160, 260, scale, 1) },
    ] },
  ], [projects, rows, scale]);
  return <section aria-label="用油联动"><div data-page-chrome className="oilcard-toolbar"><label>核算月<TimePicker label="用油联动核算月" modes={['月']} value={ym} onChange={setYm} disabled={blocked || busy || dirty || uncertain} /></label>
    <Button disabled={blocked || busy || !dirty} onMouseDown={e => e.preventDefault()} onClick={() => saves.update(() => ({}))}>取消未保存修改</Button></div>
    {rows.some(row => !row.enabled) && <p className="muted">待接续项目仅显示当月充值供核对，原特殊费用和导出仍取旧记录；核对旧用油总额后启用联动。</p>}
    {(error || query.isError) && <p role="alert" className="notice">{error || query.error?.message}<Button disabled={blocked || busy || !active} onClick={() => void saves.reread()}>重读核对</Button></p>}
    {uncertain && <p role="alert" className="notice">核对刚才的用油自定义额后再继续。<Button disabled={blocked || busy || !verified} onClick={() => saves.confirm()}>已核对，保留输入继续</Button></p>}
    {Object.entries(drafts).filter(([, draft]) => draft.error).map(([key, draft]) => <p key={key} className="oilcard-draft-error">{draft.ym} {labels[draft.field]}：{draft.error}<Button size="small" disabled={disabled || busy} onMouseDown={e => e.preventDefault()} onClick={() => saves.save(key, true)}>重试保存</Button></p>)}
    {query.isPending ? <p data-page-loading role="status">正在读取用油联动…</p> : query.data && <LinkageCells.Provider value={{ rows, projects, drafts, disabled, structuralDisabled: disabled || busy || dirty || query.isFetching, save: saves.save,
      enable: (row, big) => { void saves.run(signal => (big ? enableOilBigLinkage : enableOilFeeLinkage)(row.project_id, signal), () => '', big ? '启用大表联动：' : '启用用油联动：'); },
      change: (row, field, value) => { if (disabled) return; const key = keyOf(row, field); saves.update((previous, writing) => { const next = { ...previous }, original = previous[key]?.original ?? valueOf(row, field); if (value === original && !writing) delete next[key]; else next[key] = { projectId: row.project_id, ym: row.ym, field, original, value, error: '' }; return next; }); } }}>
      {!rows.length ? <p className="state">尚无正式项目，请先维护项目档案。</p> : <BusinessGrid table="oilcard-linkage" label="用油联动项目月表" rows={rows} columns={columns} rowId={row => String(row.project_id)} scale={scale} domLayout="autoHeight" />}
    </LinkageCells.Provider>}</section>;
}
