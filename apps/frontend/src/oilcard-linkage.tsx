import Button from 'antd/es/button';
import Input from 'antd/es/input';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { ApiError, cents, decimal, money, projectLabel, requestJson } from './api';
import type { Identity, Project } from './api';
import { BusinessGrid } from './business-grid';
import { contentWidth, fullTextWidth } from './grid';
import { readHistory } from './history';
import { reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { useCellSaveQueue } from './use-cell-save';
import { enableOilFeeLinkage, getOilLinkage, saveOilFeeCustom } from './oilcard-linkage-api';
import type { OilFeeMonth, OilLinkage } from './oilcard-linkage-api';

type Field = 'custom_amount' | 'remark';
type Draft = { projectId: number; ym: string; field: Field; original: string; value: string; error: string };
const labels: Record<Field, string> = { custom_amount: '特殊费用自定义额', remark: '特殊费用用油备注' };
const keyOf = (row: OilFeeMonth, field: Field) => `${row.project_id}:${row.ym}:${field}`;
interface Cells { rows: OilFeeMonth[]; projects: Project[]; drafts: Record<string, Draft>; disabled: boolean; structuralDisabled: boolean; enable: (row: OilFeeMonth) => void; change: (row: OilFeeMonth, field: Field, value: string) => void; save: (key: string) => void }
const LinkageCells = createContext<Cells | null>(null);
function Editor({ data: rendered, colDef }: ICellRendererParams<OilFeeMonth>) {
  const state = useContext(LinkageCells)!, [focused, setFocused] = useState(false);
  const row = state.rows.find(item => item.project_id === rendered?.project_id);
  if (!row) return null;
  const field = colDef?.field as Field, key = keyOf(row, field), draft = state.drafts[key], original = row[field] ?? '';
  const project = state.projects.find(project => project.id === row.project_id);
  const label = `${row.ym} ${project ? projectLabel(project) : `项目 #${row.project_id}`} ${labels[field]}`;
  if (!row.enabled) return <span className="muted">—</span>;
  return <div className="oilcard-cell"><Input aria-label={label} value={draft?.value ?? (field === 'custom_amount' && original && !focused ? money(original) : original)}
    className={field === 'custom_amount' ? 'record-value oilcard-amount' : 'record-value'} disabled={state.disabled} status={draft?.error ? 'error' : ''}
    onFocus={() => setFocused(true)} onChange={e => state.change(row, field, e.target.value)} onBlur={() => { setFocused(false); state.save(key); }}
    onKeyDown={e => { if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }} />
    {draft?.error && <p role="alert" className="oilcard-cell-error">{draft.error}</p>}</div>;
}

function LinkageState({ data: row }: ICellRendererParams<OilFeeMonth>) {
  const state = useContext(LinkageCells)!;
  if (!row || row.enabled) return '已启用';
  return row.can_enable ? <Button size="small" disabled={state.structuralDisabled} onClick={() => state.enable(row)}>启用用油联动</Button> : <span className="muted">待接续核对</span>;
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
      if (!row?.enabled || (row[draft.field] ?? '') !== draft.original) throw new ApiError('这个项目的当月字段已变化，请重读核对后处理保留输入。', 409);
      await saveOilFeeCustom(row, { amount: draft.field === 'custom_amount' ? draft.value.trim() ? decimal(cents(draft.value)) : null : row.custom_amount,
        remark: draft.field === 'remark' ? draft.value : row.remark }, signal);
    }, acknowledge: (present, submitted) => present.value === submitted.value ? undefined : { ...present, original: submitted.field === 'custom_amount' ? submitted.value.trim() ? decimal(cents(submitted.value)) : '' : submitted.value },
    saved: () => '', validate: draft => { if (draft.field !== 'custom_amount' || !draft.value.trim()) return ''; try { cents(draft.value); return ''; } catch { return '请填写有效金额，允许正数、负数和零。'; } },
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
  const columns = useMemo<ColDef<OilFeeMonth>[]>(() => [
    { colId: 'project', headerName: '项目', pinned: 'left', valueGetter: p => { const project = projects.find(project => project.id === p.data?.project_id); return project ? projectLabel(project) : `项目 #${p.data?.project_id}`; }, ...contentWidth(180, 340, scale, 1) },
    { colId: 'linkage_state', headerName: '联动状态', cellRenderer: LinkageState, ...contentWidth(150, 200, scale) },
    { field: 'recharge_amount', headerName: '当月充值', cellClass: 'money', valueFormatter: p => money(p.value), ...contentWidth(Math.max(130, fullTextWidth(rows.map(row => money(row.recharge_amount)), scale).minWidth / scale), 240, scale, 1) },
    { field: 'custom_amount', headerName: '特殊费用自定义额', cellRenderer: Editor, ...contentWidth(180, 260, scale, 1) },
    { field: 'remark', headerName: '特殊费用用油备注', cellRenderer: Editor, ...contentWidth(220, 460, scale, 2) },
    { field: 'fee_amount', headerName: '特殊费用用油', cellClass: 'money', valueFormatter: p => p.data?.enabled ? money(p.value) : '待接续核对', ...contentWidth(Math.max(150, fullTextWidth(rows.map(row => money(row.fee_amount)), scale).minWidth / scale), 260, scale, 1) },
  ], [projects, rows, scale]);
  return <section aria-label="用油联动"><div data-page-chrome className="oilcard-toolbar"><label>核算月<TimePicker label="用油联动核算月" modes={['月']} value={ym} onChange={setYm} disabled={blocked || busy || dirty || uncertain} /></label>
    <Button disabled={blocked || busy || !dirty} onMouseDown={e => e.preventDefault()} onClick={() => saves.update(() => ({}))}>取消未保存修改</Button></div>
    {rows.some(row => !row.enabled) && <p className="muted">待接续项目仅显示当月充值供核对，原特殊费用和导出仍取旧记录；核对旧用油总额后启用联动。</p>}
    {(error || query.isError) && <p role="alert" className="notice">{error || query.error?.message}<Button disabled={blocked || busy || !active} onClick={() => void saves.reread()}>重读核对</Button></p>}
    {uncertain && <p role="alert" className="notice">核对刚才的用油自定义额后再继续。<Button disabled={blocked || busy || !verified} onClick={() => saves.confirm()}>已核对，保留输入继续</Button></p>}
    {Object.entries(drafts).filter(([, draft]) => draft.error).map(([key, draft]) => <p key={key} className="oilcard-draft-error">{draft.ym} {labels[draft.field]}：{draft.error}<Button size="small" disabled={disabled || busy} onMouseDown={e => e.preventDefault()} onClick={() => saves.save(key, true)}>重试保存</Button></p>)}
    {query.isPending ? <p data-page-loading role="status">正在读取用油联动…</p> : query.data && <LinkageCells.Provider value={{ rows, projects, drafts, disabled, structuralDisabled: disabled || busy || dirty || query.isFetching, save: saves.save,
      enable: row => { void saves.run(signal => enableOilFeeLinkage(row.project_id, signal), () => '', '启用用油联动：'); },
      change: (row, field, value) => { if (disabled) return; const key = keyOf(row, field); saves.update((previous, writing) => { const next = { ...previous }, original = previous[key]?.original ?? row[field] ?? ''; if (value === original && !writing) delete next[key]; else next[key] = { projectId: row.project_id, ym: row.ym, field, original, value, error: '' }; return next; }); } }}>
      {!rows.length ? <p className="state">尚无正式项目，请先维护项目档案。</p> : <BusinessGrid table="oilcard-linkage" label="用油联动项目月表" rows={rows} columns={columns} rowId={row => String(row.project_id)} scale={scale} domLayout="autoHeight" />}
    </LinkageCells.Provider>}</section>;
}
