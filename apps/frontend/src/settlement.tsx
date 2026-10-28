import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Segmented from 'antd/es/segmented';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import { createContext, useContext, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { Identity } from './api';
import { contentWidth, fixedWidth, gridTheme } from './grid';
import { reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { money } from './notices-api';
import { useCellSaveQueue } from './use-cell-save';
import { balanced, getExtract, getSettlement, kinds, saveBalance, settlementTotal } from './settlement-api';
import type { AnnualRow, ExtractKind, SettlementRow } from './settlement-api';
import { SettlementExport } from './settlement-export';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
const settlementRowId = (row: SettlementRow) => row.id;
const annualRowId = (row: AnnualRow) => row.warehouse;
const emptySettlement: SettlementRow[] = [];

type Props = { me: Identity | null; blocked: boolean; active: boolean };
export function SettlementPage(props: Props) {
  const [tab,setTab] = useState('month');
  return <section className={`settlement-page${tab === 'month' ? ' settlement-month-page' : ''}`} aria-label="收发结存与提取">
    <Segmented data-page-chrome className="settlement-tabs" aria-label="收发结存页面" value={tab} options={[{value:'month',label:'收发结存月报'},{value:'extract',label:'焊材 / 气体提取'}]} onChange={setTab} disabled={props.blocked} />
    <div hidden={tab !== 'month'} inert={tab !== 'month'}><Monthly {...props} active={props.active && tab === 'month'} /></div>
    <div hidden={tab !== 'extract'} inert={tab !== 'extract'}><Extract {...props} active={props.active && tab === 'extract'} /></div>
  </section>;
}
function Monthly({ me, blocked, active }: Props) {
  const [ym,setYm] = useState(reportMonth), root = useRef<HTMLDivElement>(null);
  const query = useQuery({ queryKey:['settlement',ym], enabled: active && !blocked, queryFn:({signal}) => getSettlement(ym,signal) });
  const scale = Number(me?.ui_scale_css ?? 1);
  const columns = useMemo<ColDef<SettlementRow>[]>(() => [
    {field:'name',headerName:'仓库名',pinned:'left',wrapText:true,autoHeight:true,...contentWidth(200,500,scale,1)},
    {field:'rows',headerName:'行数',cellClass:'money',...fixedWidth(85,scale)},
    ...(['begin','in','out','end'] as const).map((field,i) => ({field,headerName:['期初金额','收金额','发金额','结存金额'][i]!,cellClass:'money',wrapText:true,autoHeight:true,valueFormatter:(p: {value: unknown}) => money(String(p.value)),...contentWidth(160,260,scale)})),
    {colId:'check',headerName:'校验',...fixedWidth(100,scale),cellRenderer:(p: ICellRendererParams<SettlementRow>) => p.data && <Tag className={`status-tag ${balanced(p.data) ? 'status-positive' : 'status-negative'}`}>{balanced(p.data) ? '已对平' : '未对平'}</Tag>},
  ],[scale]);
  const total = useMemo(() => query.data?.rows.length ? [{ id:'__total',name:'合计',rows:query.data.counts.rows,
    begin:settlementTotal(query.data.rows,'begin'),in:settlementTotal(query.data.rows,'in'),out:settlementTotal(query.data.rows,'out'),end:settlementTotal(query.data.rows,'end') }] : [],[query.data]);
  const presentation = useGridPresentation({table: 'settlement-month', root, active, rows: query.data?.rows ?? emptySettlement, totals: total, columns, rowId: settlementRowId, scale, scope: ym, identity: ym});
  return <>
    <div data-page-chrome className="settlement-toolbar"><label>核算月<TimePicker value={ym} onChange={setYm} modes={['月']} label="收发结存核算月" disabled={blocked} /></label>
      <SettlementExport scope={`${ym} 收发结存`} url={`/api/m07/settlement/export?${new URLSearchParams({period:ym})}`} paused={!active || blocked} disabled={!query.data?.rows.length || query.isFetching || query.isError}>
        <p>{query.data?.counts.warehouses} 个分仓库工作簿 ＋ 1 个总表，打包 ZIP。</p>
        <ul className="settlement-export-list">{query.data?.rows.map(row => <li key={row.id}>{row.name}，{row.rows} 行</li>)}</ul>
      </SettlementExport>
    </div>
    {query.isError && <p className="notice" role="alert">{query.error.message}<Button onClick={() => void query.refetch()} disabled={blocked}>重读</Button></p>}
    {query.isPending ? <p role="status">正在读取收发结存…</p> : query.data && <>
      <p className="settlement-summary">{ym}，{query.data.counts.warehouses} 仓，{query.data.counts.rows} 行，{query.data.counts.files} 个文件{query.data.rows.length > 0 && <Tag className={`status-tag ${query.data.balance_ok ? 'status-positive' : 'status-negative'}`}>{query.data.balance_ok ? '全部对平' : '存在未对平'}</Tag>}</p>
      <PreparedGrid presentation={presentation} className={`settlement-grid${query.data.rows.length ? '' : ' is-empty'}`} grid={{theme:gridTheme,domLayout:'autoHeight',
        getRowId:p=>p.data.id,defaultColDef:{resizable: true,sortable:false,suppressMovable:true},
        overlayNoRowsTemplate:'该核算月没有收发结存数据',suppressColumnVirtualisation:true,suppressScrollOnNewData:true}} />
    </>}
  </>;
}

interface Draft { kind: ExtractKind; warehouse: string; value: string; original: string; error: string }
const keyOf = (kind: ExtractKind, warehouse: string) => JSON.stringify([kind,warehouse]);
interface BalanceCells { drafts: Record<string,Draft>; disabled: boolean; change: (kind: ExtractKind, warehouse: string, original: string, value: string) => void; save: (key: string) => void; cancel: (key: string) => void }
const Cells = createContext<BalanceCells | null>(null);
function BalanceInput({data,node,colDef}: ICellRendererParams<AnnualRow>) {
  const cells = useContext(Cells)!, kind = colDef?.context.kind as ExtractKind;
  if (!data || node.rowPinned) return null;
  const key = keyOf(kind,data.warehouse), draft = cells.drafts[key];
  return <Input className="record-value" aria-label={`${kind}，${data.warehouse}，2025-11及之前`} value={draft?.value ?? data.balance ?? ''} placeholder="未录入" disabled={cells.disabled}
    status={draft?.error ? 'error' : ''} onChange={e => cells.change(kind,data.warehouse,data.balance ?? '',e.target.value)} onBlur={() => cells.save(key)}
    onKeyDown={e => { if(e.nativeEvent.isComposing) return; if(e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } if(e.key === 'Escape') {e.stopPropagation(); cells.cancel(key);} }} />;
}
function Extract({ me, blocked, active }: Props) {
  const [year,setYear] = useState(() => reportMonth().slice(0,4)), [status,setStatus] = useState('在建');
  const client=useQueryClient();
  const queryKey=['extract',year,status];
  const query=useQuery({queryKey,enabled:active&&!blocked,queryFn:({signal})=>getExtract(year,status,signal)});
  const saves=useCellSaveQueue<Draft,Awaited<ReturnType<typeof getExtract>>>({
    enabled:active&&!blocked&&Boolean(me),canWrite:!query.isError&&!query.isPending,
    read:reload,write:(draft,signal)=>saveBalance(draft.kind,draft.warehouse,draft.value,signal),
    acknowledge:(current,submitted)=>current.value===submitted.value?undefined:current,
    saved:draft=>`${draft.kind}，${draft.warehouse}，已${draft.value.trim()?'保存':'清空'}`,
  },{key:'extract-balances',label:'历史结余'});
  const {drafts,busy,uncertain,verified,error,feedback}=saves;
  async function reload() {
    await client.cancelQueries({queryKey:['extract']});
    const data = await client.fetchQuery({queryKey,staleTime:0,queryFn:({signal}) => getExtract(year,status,signal)});
    await client.invalidateQueries({predicate:q => q.queryKey[0] !== 'extract'});
    await client.invalidateQueries({queryKey:['extract']}, {throwOnError:true});
    return data;
  }
  const save=saves.save;
  const dirty = Object.keys(drafts).length > 0;
  const disabled = blocked || !active || !me || uncertain || query.isError || query.isPending;
  return <>
    <div data-page-chrome className="settlement-toolbar"><div><label>年份<TimePicker value={year} onChange={setYear} modes={['年']} label="提取年份" disabled={blocked} /></label>
      <label>项目状态<Select aria-label="提取项目状态" value={status} onChange={setStatus} options={['在建','归档','全部'].map(value => ({value,label:value}))} disabled={blocked} /></label></div>
      <SettlementExport scope={`${year} 焊材 / 气体`} url={`/api/m07/extract/export?${new URLSearchParams({period:year,status})}`} paused={!active || blocked} disabled={!query.data || query.isFetching || query.isError || busy || dirty || uncertain}>
        <p>{year}，{status}，焊材 {query.data?.annual.焊材.rows.length} 仓 / 气体 {query.data?.annual.气体.rows.length} 仓</p>
        <p>保留原模板，并附年度汇总；合计包含历史值与所选年 12 个月，2025 年 1–11 月留空。</p>
      </SettlementExport>
    </div>
    {(busy || feedback) && <p role="status">{busy ? '正在保存历史结余…' : feedback}</p>}
    {(error || query.isError) && <p className="notice" role="alert">{error || query.error?.message}<Button disabled={busy || blocked} onClick={() => {
      void saves.reread();
    }}>重读核对</Button></p>}
    {uncertain && <p className="notice" role="alert">核对刚才的操作结果后再继续。<Button disabled={!verified || busy || query.isFetching || query.isError} onClick={() => {saves.confirm();}}>已核对，保留输入继续</Button></p>}
    {Object.entries(drafts).map(([key,d]) => <div className="settlement-draft" key={key}><span>{d.kind}，{d.warehouse}，2025-11及之前：{d.value || '清空'}{d.error && <span role="alert">，{d.error}</span>}</span>
      <Button disabled={disabled || busy} onMouseDown={e => e.preventDefault()} onClick={() => {save(key,true);}}>保存这项</Button>
      <Button disabled={busy} onMouseDown={e => e.preventDefault()} onClick={() => {saves.update(drafts=>{const next={...drafts};delete next[key];return next;});}}>取消修改</Button></div>)}
    {query.isPending ? <p role="status">正在读取库存年度汇总…</p> : query.data && <Cells.Provider value={{drafts,disabled,save,
      change:(kind,warehouse,original,value)=>{const key=keyOf(kind,warehouse);saves.update((drafts,writing)=>{const old=drafts[key],next={...drafts,[key]:{kind,warehouse,original:old?.original??original,value,error:''}};if(value===(old?.original??original)&&!writing)delete next[key];return next;});},
      cancel:key=>saves.update((drafts,writing)=>{if(writing)return drafts;const next={...drafts};delete next[key];return next;})}}>
      {kinds.map(kind => <AnnualTable key={kind} grid={query.data!.annual[kind]} active={active} scale={Number(me?.ui_scale_css ?? 1)} />)}
    </Cells.Provider>}
  </>;
}
function AnnualTable({grid,scale,active}:{grid: import('./settlement-api').AnnualGrid;scale:number;active:boolean}) {
  const root = useRef<HTMLDivElement>(null), history = grid.year <= '2025';
  const columns = useMemo<ColDef<AnnualRow>[]>(() => {
    // Use the complete result and its supplied totals, including rows below the viewport.
    const amountWidth = (values: (string | null | undefined)[], minimum = 72) => {
      const width = Math.max(minimum, ...values.map(value => value == null ? 0 : money(value).length * 8.2 + 20));
      return contentWidth(width,width + 64,scale,1);
    };
    return [
      {field:'warehouse',headerName:'仓库名',pinned:'left',wrapText:true,autoHeight:true,...contentWidth(160,320,scale,1)},
      {field:'prior',headerName:'往年金额',cellClass:'money',valueFormatter:p => p.value == null ? '' : money(p.value),...amountWidth([...grid.rows.map(row => row.prior),grid.sum_row[0]])},
      ...grid.months.map((_month,i):ColDef<AnnualRow> => ({colId:`month-${i+1}`,headerName:`${i+1}月`,valueGetter:p => p.data?.cells[i],valueFormatter:p => p.value == null ? '' : money(p.value),cellClass:'money',...amountWidth([...grid.rows.map(row => row.cells[i]),grid.sum_row[i+1]])})),
      {field:'total',headerName:'合计',cellClass:'money',valueFormatter:p => p.value == null ? '' : money(p.value),...amountWidth([...grid.rows.map(row => row.total),grid.sum_row[13]])},
      ...(history ? [{field:'balance' as const,headerName:'2025-11及之前',cellRenderer:BalanceInput,...amountWidth(grid.rows.map(row => row.balance),148),context:{kind:grid.kind}}] : []),
    ];
  },[grid,history,scale]);
  const total = useMemo<AnnualRow[]>(() => [{warehouse:`${grid.kind}合计`,prior:grid.sum_row[0]!,cells:grid.sum_row.slice(1,13),total:grid.sum_row[13]!,balance:null}], [grid]);
  const presentation = useGridPresentation({table: `extract-${grid.kind}`, root, active, rows: grid.rows, totals: total, columns, rowId: annualRowId, scale, scope: grid.year, identity: grid.year});
  return <section className="settlement-annual" aria-label={`${grid.kind}年度汇总`}><h2>{grid.kind}</h2><PreparedGrid presentation={presentation} className={`settlement-grid annual-grid${grid.rows.length ? '' : ' is-empty'}`} grid={{theme:gridTheme,domLayout:'autoHeight',
    getRowId:p=>p.data.warehouse,defaultColDef:{resizable:true,sortable:false,suppressMovable:true,suppressKeyboardEvent:e=>e.event.target instanceof HTMLInputElement},
    overlayNoRowsTemplate:`当前筛选条件下没有${grid.kind}数据`,suppressScrollOnNewData:true,suppressColumnVirtualisation:true}} /></section>;
}
