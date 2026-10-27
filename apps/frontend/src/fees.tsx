import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Popconfirm from 'antd/es/popconfirm';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { Identity } from './api';
import { readProjects, requestJson } from './api';
import { contentWidth, gridTheme } from './grid';
import { ProjectPicker, reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { money } from './notices-api';
import { feeWrite, getFeeYear } from './fees-api';
import type { FeeYearData, FeeYearRow } from './fees-api';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
import { useCellSaveQueue } from './use-cell-save';

const rowId=(row:FeeYearRow)=>row.item_id ? `item-${row.item_id}` : `auto-${encodeURIComponent(row.item)}`;
type Draft={itemId:number; item:string; ym:string; field:'name'|'amount'; value:string; original:string; error:string};
const keyOf=(itemId:number, field:string, ym='')=>`${itemId}:${field}:${ym}`;
interface Cells { drafts:Record<string,Draft>; disabled:boolean; structuralDisabled:boolean;
  change:(draft:Draft)=>void; save:(key:string,retry?:boolean)=>void; remove:(row:FeeYearRow)=>void }
const FeeCells=createContext<Cells | null>(null);
function Editor({data,field,ym='',original}:{data:FeeYearRow;field:'name'|'amount';ym?:string;original:string}) {
  const cells=useContext(FeeCells)!; const itemId=data.item_id!;const key=keyOf(itemId,field,ym),draft=cells.drafts[key];
  return <Input data-fee-key={key} aria-label={field==='name'?`${data.item}费用项名称`:`${ym} ${data.item}金额`}
    value={draft?.value ?? original} disabled={cells.disabled} status={draft?.error?'error':''} className={`record-value${field==='amount'?' fee-money-input':''}`}
    onChange={e=>cells.change({itemId,item:data.item,field,ym,value:e.target.value,original,error:''})}
    onBlur={()=>cells.save(key)} onKeyDown={e=>{e.stopPropagation();if(!e.nativeEvent.isComposing && e.key==='Enter'){e.preventDefault();e.currentTarget.blur();}}} />;
}
function NameCell({data,node}:ICellRendererParams<FeeYearRow>) {
  const cells=useContext(FeeCells)!;if(!data)return null;
  if(node.rowPinned || !data.manual || !data.item_id)return data.item;
  return <div className="fee-record-names"><Editor data={data} field="name" original={data.item} />
    <Popconfirm title={`删除「${data.item}」及全部月份金额？`} description="往年及其他年份的记录也会一并移除。" okText="删除" cancelText="取消" disabled={cells.structuralDisabled} onConfirm={()=>cells.remove(data)}>
      <Button size="small" danger disabled={cells.structuralDisabled} aria-label={`删除费用项 ${data.item}`}>删除</Button>
    </Popconfirm></div>;
}
function AmountCell({data,node,colDef}:ICellRendererParams<FeeYearRow>) {
  if(!data)return null;const index=Number(colDef?.colId?.slice(6))-1,value=data.months[index];
  if(node.rowPinned || !data.manual || !data.item_id)return value==null?'':money(value);
  return <Editor data={data} field="amount" ym={`${colDef?.headerTooltip}-${String(index+1).padStart(2,'0')}`} original={value??''} />;
}
export function FeesPage({me,blocked,active}:{me:Identity|null;blocked:boolean;active:boolean}) {
  const [year,setYear]=useState(()=>reportMonth().slice(0,4)),[project,setProject]=useState('');
  const client=useQueryClient(),root=useRef<HTMLDivElement>(null);
  const queryKey=['fees-year-inline',year,project];
  const projects=useQuery({queryKey:['projects','all'],enabled:active&&!blocked,queryFn:async({signal})=>readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  const query=useQuery({queryKey,enabled:active&&!blocked,queryFn:({signal})=>getFeeYear(year,project,signal)});
  const ready=query.data?.year===year && query.data.project===project;
  const saves=useCellSaveQueue<Draft,FeeYearData>({
    enabled:active&&!blocked&&Boolean(me),canWrite:Boolean(ready&&query.data?.can_edit&&!query.isError),
    read:reload,write:async(d,signal)=>{await feeWrite(`item/${d.field==='name'?'rename':'amount'}`,{project,item_id:d.itemId,ym:d.ym,value:d.value},signal);},
    acknowledge:(current,submitted)=>current.value===submitted.value?undefined:current,
    saved:d=>`${d.ym ? `${d.ym}，` : ''}${d.item}，已保存`,
  },{key:`fees:${year}:${project}`,label:'特殊费用'});
  async function reload() {
    await client.cancelQueries({queryKey,exact:true});
    const data=await client.fetchQuery({queryKey,staleTime:0,queryFn:({signal})=>getFeeYear(year,project,signal)});
    await client.invalidateQueries({predicate:q=>JSON.stringify(q.queryKey)!==JSON.stringify(queryKey)});return data;
  }
  const {drafts,busy,uncertain,verified,error,feedback}=saves,dirty=Object.keys(drafts).length>0;
  const disabled=blocked||!active||!me||uncertain||!ready||!query.data?.can_edit||query.isError;
  const paused=blocked||busy||dirty||uncertain;
  async function add() {
    if(disabled||busy||dirty||query.isFetching)return;
    const names=new Set(query.data?.rows.map(row=>row.item));let name='新项';for(let n=2;names.has(name);n++)name=`新项${n}`;
    await saves.run(async signal=>{const id=await feeWrite('item/create',{project,name},signal);if(!id)throw new Error('新增回执不完整，请重读核对。');},()=>`已增加「${name}」`,'新增费用项：');
  }
  async function remove(row:FeeYearRow) {
    if(disabled||busy||dirty||!row.item_id)return;
    await saves.run(async signal=>{await feeWrite('item/delete',{project,item_id:row.item_id},signal);},()=>`已删除「${row.item}」及其月度记录`,'删除费用项：');
  }
  const rows=useMemo(()=>query.data?.rows??[],[query.data]);const scale=Number(me?.ui_scale_css??1);
  const columns=useMemo<ColDef<FeeYearRow>[]>(()=>{
    const width=(values:(string|null|undefined)[])=>{const n=Math.max(72,...values.map(v=>v==null?0:money(v).length*8.2+20));return contentWidth(n,n+64,scale,1);};
    return [
      {field:'item',headerName:'费用项名称',pinned:'left',autoHeight:true,wrapText:true,...contentWidth(160,300,scale,1),cellRenderer:NameCell},
      {field:'prior',headerName:'往年',cellClass:'money',valueFormatter:p=>p.value==null?'':money(p.value),...width([query.data?.prior,...rows.map(r=>r.prior)])},
      ...Array.from({length:12},(_,i):ColDef<FeeYearRow>=>({colId:`month-${i+1}`,headerName:`${i+1}月`,headerTooltip:year,cellClass:'money',autoHeight:true,valueGetter:p=>p.data?.months[i],cellRenderer:AmountCell,...width([query.data?.months[i],...rows.map(r=>r.months[i])])})),
      {field:'total',headerName:'累计',cellClass:'money',valueFormatter:p=>money(p.value),...width([query.data?.total,...rows.map(r=>r.total)])},
    ];
  },[year,scale,rows,query.data]);
  const totals=useMemo<FeeYearRow[]>(()=>query.data?[{item:'合计',manual:false,prior:query.data.prior,months:query.data.months,total:query.data.total,periods:[]}]:[],[query.data]);
  const presentation=useGridPresentation({root,active:active&&Boolean(ready),rows,totals,columns,rowId,scale,scope:year+':'+project,identity:year+':'+project});
  useEffect(()=>{if(!project&&query.data?.project)setProject(query.data.project);},[project,query.data]);
  return <section className="fees-page" aria-label="特殊费用">
    <div data-page-chrome className="fee-filters"><label>年份<TimePicker label="费用年份" modes={['年']} value={year} onChange={setYear} disabled={paused} /></label>
      <label>项目<ProjectPicker projects={(projects.data??[]).filter(p=>p.warehouse_name&&p.project_type!=='shell')} selected={(projects.data??[]).filter(p=>p.warehouse_name===project).map(p=>p.id)} pick={ids=>{const next=projects.data?.find(p=>p.id===ids[0])?.warehouse_name;if(next)setProject(next);}} label="费用项目" disabled={paused||projects.isPending} /></label></div>
    <div data-page-chrome className="fee-toolbar"><div><Button disabled={disabled||busy||dirty||query.isFetching} onClick={()=>void add()}>增加手填项</Button></div><span className="muted">随逐月欠款台账导出，特殊费用月报表</span></div>
    {(busy||feedback)&&<p role="status" className="fee-feedback">{busy?'正在保存费用…':feedback}</p>}
    {(error||projects.isError||query.isError)&&<p role="alert" className="notice">{error||projects.error?.message||query.error?.message}<Button disabled={busy||blocked} onClick={()=>void saves.reread()}>重读核对</Button></p>}
    {uncertain&&<p className="notice" role="alert">核对刚才的操作结果后再继续。<Button disabled={!verified||busy} onClick={()=>saves.confirm()}>已核对，保留输入继续</Button></p>}
    {Object.entries(drafts).map(([key,d])=><p key={key} className="fee-draft-feedback">{d.ym}，{d.item}，{d.field==='name'?'项名':'金额'}：{d.error||'未保存'} <Button size="small" disabled={disabled||busy} onMouseDown={e=>e.preventDefault()} onClick={()=>saves.save(key,true)}>保存</Button><Button size="small" disabled={busy||blocked} onMouseDown={e=>e.preventDefault()} onClick={()=>saves.update(ds=>{const next={...ds};delete next[key];return next;})}>取消这项修改</Button></p>)}
    {query.isPending?<p role="status">正在读取费用…</p>:ready&&<FeeCells.Provider value={{drafts,disabled,structuralDisabled:disabled||busy||dirty||query.isFetching,remove,save:saves.save,
      change:d=>saves.update((ds,writing)=>{const key=keyOf(d.itemId,d.field,d.ym),old=ds[key],next={...ds,[key]:{...d,original:old?.original??d.original}};if(d.value===(old?.original??d.original)&&!writing)delete next[key];return next;})}}><PreparedGrid presentation={presentation} className="fees-grid fees-annual-grid" aria-label="特殊费用年度表" grid={{theme:gridTheme,domLayout:'autoHeight',getRowId:p=>rowId(p.data),defaultColDef:{resizable:true,sortable:false,suppressMovable:true,wrapHeaderText:true,suppressKeyboardEvent:e=>e.event.target instanceof HTMLInputElement},suppressScrollOnNewData:true,suppressColumnVirtualisation:true,animateRows:false}} /></FeeCells.Provider>}
  </section>;
}
