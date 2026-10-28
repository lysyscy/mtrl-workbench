import Button from 'antd/es/button';
import Input from 'antd/es/input';
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { DialogContents, useDialogClose } from './dialog-close';
import { BusinessModal } from './business-modal';
import { numberColumnWidth, contentWidth, fixedWidth } from './grid';
import { BusinessGrid } from './business-grid';
import { mechanicalMoney as money, detailNet, detailProblems, detailSum, editDetailRow } from './mechanical-api';
import type { Category, Detail, DetailRow } from './mechanical-api';

export function mechanicalNumberWidth(values: readonly unknown[], scale: number, control = false, stretch = 0) {
  return numberColumnWidth(values, scale, control, stretch);
}
const numericFields = ['amount','rate','net','qty','plan','used'];

export interface Draft { warehouse: string; ym: string; category: Category; revision: number; rows: DetailRow[]; version: number; error:string }
export const detailKey = (warehouse: string, ym: string, category: Category) => JSON.stringify([warehouse,ym,category]);
export const fields: Record<Category, [string,string][]> = {
  zero: [['device','设备名称'],['spec','规格型号'],['unit','单位'],['qty','数量'],['rate','零租单价'],['amount','合价（元）'],['tax','票种／税率'],['net','不含税价'],['date','租赁日期／期间'],['use','用途'],['team','使用班组'],['reviewer','审核人'],['vendor','出租单位'],['plate','车牌号'],['memo','备注']],
  monthly: [['device','设备名称'],['spec','规格型号'],['unit','单位'],['plan','计划月数'],['used','已包月数'],['rate','包月单价'],['amount','合价（元）'],['net','不含税价'],['date','入场日期'],['vendor','出租单位'],['reviewer','审核人'],['tax','票种／税率'],['oil','含油说明'],['plate','车牌号'],['memo','原备注']],
};
const aliases: Record<string,string> = { use:'usage', vendor:'lessor', memo:'note' };
interface DetailGroup { warehouse:string; name:string; saved:Detail|undefined; draft:Draft|undefined }
interface DetailDisplay { id:string; kind:'group'|'detail'; warehouse:string; name:string; rows:DetailRow[]; row?:DetailRow; index:number; shown:number; draft:boolean; gross:unknown; net:unknown; missing:number }
function DetailInput({value,change,...props}:Omit<React.ComponentProps<typeof Input>,'value'|'onChange'>&{value:string;change:(value:string)=>void}) {
  const [text,setText]=useState(value);
  useEffect(()=>setText(value),[value]);
  return <Input {...props} value={text} onChange={e=>{setText(e.target.value);change(e.target.value);}}/>;
}
export function DetailsTable({ scale,groups,category,ym,keywords,problemsOnly,writable,change,save }: {
  scale:number;groups:DetailGroup[];category:Category;ym:string;keywords:string[];problemsOnly:boolean;writable:boolean;change:(warehouse:string,rows:DetailRow[])=>void;save:(warehouse:string)=>void;
}) {
  const labels=fields[category],grossIndex=labels.findIndex(([field])=>field==='amount');
  const focus=useRef('');
  const root=useRef<HTMLDivElement>(null);
  const api=useRef<import('ag-grid-community').GridApi<DetailDisplay>|null>(null);
  useEffect(()=>{if(api.current&&!api.current.isDestroyed())api.current.refreshCells({force:true});},[writable]);
  function fitHeight(grid:import('ag-grid-community').GridApi<DetailDisplay>){
    const element=root.current?.querySelector<HTMLElement>('.business-grid');
    if(!element||grid.isDestroyed())return;
    const last=grid.getDisplayedRowAtIndex(grid.getDisplayedRowCount()-1);
    const horizontal=element.querySelector<HTMLElement>('.ag-body-horizontal-scroll');
    const height=Math.ceil(Math.min(window.innerHeight*.65,
      (element.querySelector('.ag-header')?.getBoundingClientRect().height??48*scale)
      +(last?(last.rowTop??0)+(last.rowHeight??36*scale):36*scale)
      +(horizontal&&getComputedStyle(horizontal).visibility!=='hidden'?horizontal.offsetHeight:0)+2));
    if(Math.abs(element.getBoundingClientRect().height-height)>.5)element.style.height=`${height}px`;
  }
  const current=useRef({groups,change,save,writable,category,ym,keywords,problemsOnly});current.current={groups,change,save,writable,category,ym,keywords,problemsOnly};
  const display:DetailDisplay[]=groups.flatMap(group=>{
    const rows=group.draft?.rows??group.saved?.rows??[],shown=rows.map((row,index)=>({row,index})).filter(({row})=>!problemsOnly||detailProblems(row,category,ym,keywords).length);
    const amounts=rows.filter(row=>String(row.amount??'').trim()!=='');
    const base={warehouse:group.warehouse,name:group.name,rows,shown:shown.length,draft:Boolean(group.draft),gross:group.draft?detailSum(amounts.map(row=>row.amount)):group.saved?.totals.gross,net:group.draft?(amounts.some(row=>detailNet(row)===null)?null:detailSum(amounts.map(detailNet))):group.saved?.totals.net,missing:amounts.filter(row=>detailNet(row)===null).length};
    return [{...base,id:'group:'+group.warehouse,kind:'group',index:-1},...shown.map(({row,index})=>({...base,id:group.warehouse+':'+row.id,kind:'detail' as const,row,index}))] as DetailDisplay[];
  });
  const fullValues=groups.flatMap(group=>group.draft?.rows??group.saved?.rows??[]);
  const signature=JSON.stringify(labels.map(([field])=>numericFields.includes(field)?numberColumnWidth([...fullValues.map(row=>field==='net'?money(detailNet(row)):row[field]??''),...display.filter(row=>row.kind==='group').map(row=>field==='amount'?money(row.gross as string):field==='net'?money(row.net as string):'')],scale,true).minWidth:0));
  const columns=useMemo<ColDef<DetailDisplay>[]>(()=>[
    {colId:'sequence',headerName:'序号',...contentWidth(48,64,scale),colSpan:p=>p.data?.kind==='group'?grossIndex+1:1,
      cellRenderer:({data:d}:ICellRendererParams<DetailDisplay>)=>!d?null:d.kind==='group'?<><strong>{d.name}</strong>，{d.shown}条{d.draft?'，未保存':''}</>:d.index+1},
    ...labels.map(([field,label]):ColDef<DetailDisplay>=>({colId:field,headerName:label,...(numericFields.includes(field)?numberColumnWidth([...fullValues.map(row=>field==='net'?money(detailNet(row)):row[field]??''),...display.filter(row=>row.kind==='group').map(row=>field==='amount'?money(row.gross as string):field==='net'?money(row.net as string):'')],scale,true):contentWidth(field==='unit'?52:field==='tax'?112:field==='spec'?88:field==='memo'?128:field==='device'?104:100,['device','spec'].includes(field)?160:field==='tax'?168:320,scale,['vendor','memo'].includes(field)?1:0)),
      cellClass:numericFields.includes(field)?'money':'',valueGetter:p=>p.data?.kind==='group'?field==='amount'?p.data.gross:field==='net'?p.data.net:'':field==='net'&&p.data?.row?detailNet(p.data.row):p.data?.row?.[field]??p.data?.row?.[aliases[field]??'']??'',
      cellRenderer:({data:d}:ICellRendererParams<DetailDisplay>)=>{
        if(!d)return null;
        if(d.kind==='group')return field==='amount'?money(d.gross as string):field==='net'?<>{money(d.net as string)}{d.missing>0&&<small>（{d.missing}条待补）</small>}</>:null;
        const row=d.row!,state=current.current,exempt=field==='plate'&&((state.category==='monthly'&&state.ym<'2026-06')||state.keywords.some(word=>String(row.device??'').includes(word)))&&!row.plate;
        return field==='net'?(detailNet(row)===null?'待补税率':money(detailNet(row))):exempt?<span className="muted">无需车牌</span>:<DetailInput id={field==='device'?'mechanical-device-'+row.id:undefined} aria-label={`${d.name} 第${d.index+1}行 ${label}`} inputMode={numericFields.includes(field)?'decimal':'text'} className={numericFields.includes(field)?'money':''} value={String(row[field]??row[aliases[field]??'']??'')} disabled={!state.writable} maxLength={4000} onBlur={()=>current.current.save(d.warehouse)} onKeyDown={e=>{e.stopPropagation();if(e.key==='Enter'&&!e.nativeEvent.isComposing){e.preventDefault();e.currentTarget.blur();}}} change={value=>{const latest=current.current,g=latest.groups.find(g=>g.warehouse===d.warehouse),rows=g?.draft?.rows??g?.saved?.rows??[];latest.change(d.warehouse,rows.map(item=>item.id===row.id?editDetailRow(item,field,value,latest.category):item));}}/>;
      }})),
    {colId:'actions',headerName:'操作',pinned:'right',...fixedWidth(80,scale),cellRenderer:({data:d}:ICellRendererParams<DetailDisplay>)=>!d?null:<Button danger={d.kind==='detail'} size="small" disabled={!current.current.writable} onClick={()=>{const state=current.current,g=state.groups.find(g=>g.warehouse===d.warehouse),rows=g?.draft?.rows??g?.saved?.rows??[];if(d.kind==='group'){const row={id:crypto.randomUUID(),device:'',unit:'台班',amount:'',tax:''};focus.current=row.id;state.change(d.warehouse,[...rows,row]);}else{state.change(d.warehouse,rows.filter(row=>row.id!==d.row!.id));state.save(d.warehouse);}}}>{d.kind==='group'?'增行':'移除'}</Button>},
  // Numeric bounds update after editing; handlers read the current draft rather than a retained closure.
  ],[category,scale,signature]);
  const count=display.filter(row=>row.kind==='detail').length;
  return <div ref={root}><BusinessGrid table={'mechanical-details-'+category} className="mechanical-detail-table" label={category==='zero'?'零租明细':'包月明细'} rows={display} columns={columns} rowId={row=>row.id} scale={scale} scope={category+':'+ym} domLayout="normal" style={{height:`min(65dvh, ${(display.length*36+48)*scale}px)`}} grid={{
    onGridReady:e=>{api.current=e.api;const observer=new ResizeObserver(()=>fitHeight(e.api));const element=root.current?.querySelector('.business-grid');for(const node of element?.querySelectorAll('.ag-header,.ag-body-horizontal-scroll')??[])observer.observe(node);const visibility=new MutationObserver(()=>fitHeight(e.api)),scrollbar=element?.querySelector('.ag-body-horizontal-scroll');if(scrollbar)visibility.observe(scrollbar,{attributes:true,attributeFilter:['class','style']});e.api.addEventListener('gridPreDestroyed',()=>{api.current=null;observer.disconnect();visibility.disconnect();});},
    onGridSizeChanged:e=>fitHeight(e.api),onModelUpdated:e=>fitHeight(e.api),
    onRowDataUpdated:e=>{if(!focus.current)return;const id=focus.current;focus.current='';e.api.ensureNodeVisible(node=>node.data?.row?.id===id,'middle');requestAnimationFrame(()=>document.getElementById('mechanical-device-'+id)?.focus());},getRowClass:p=>p.data?.kind==='group'?'mechanical-detail-group-row':'',overlayNoRowsTemplate:'尚未选择显示项目。用“显示项目”选入已有项目后增行。'}}/><p className="mechanical-feedback">当前显示 {count} 条，项目合计见合价、不含税价列</p></div>;
}

export function MechanicalDialog({ title, close, busy, dirty = false, paused = false, className = '', children }: { className?: string; title: string; close: () => void; busy: boolean; dirty?: boolean; paused?: boolean; children: React.ReactNode | ((requestClose: () => boolean) => React.ReactNode) }) {
  const titleId = useId();
  const closing = useDialogClose({ busy, dirty, close, active: !paused });
  return <BusinessModal open={!paused} requestClose={closing.requestClose} className={`mechanical-dialog ${className}`} titleId={titleId}><DialogContents title={title} titleId={titleId} closing={closing}><div className="mechanical-dialog-body">{typeof children === 'function' ? children(closing.requestClose) : children}</div></DialogContents></BusinessModal>;
}
