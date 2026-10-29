import { createContext, useContext, useMemo } from 'react';
import Button from 'antd/es/button';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { NoticeRow } from './notices-api';
import { cents, decimal, money } from './notices-api';
import { numberColumnWidth, fullTextWidth, textWidth } from './grid';
import { completeColumnWidth, EllipsisText } from './grid-text';
import { ReadGrid } from './business-grid';

interface PayView { id:string; notice:NoticeRow|null; bill:string; project:string; approval:string; approved:string; paid:string; due:string; pay:string; reason:string }
interface Editing { disabled:boolean; waiting:boolean; methods:string[]; draft:(row:NoticeRow)=>{amount:string;pay_method:string}; update:(row:NoticeRow,field:'amount'|'pay_method',value:string)=>void; remove:(id:number)=>void }
const PaymentEditing=createContext<Editing>(null!);
function Method({data}:ICellRendererParams<PayView>){const edit=useContext(PaymentEditing),row=data!.notice;return row?<Select aria-label={row.bill_no+'实际付款方式'} disabled={edit.disabled||Boolean(data!.reason)||edit.waiting} value={edit.draft(row).pay_method} onChange={value=>edit.update(row,'pay_method',value)} options={edit.methods.map(value=>({value,label:value}))}/>:null;}
function Amount({data}:ICellRendererParams<PayView>){const edit=useContext(PaymentEditing),row=data!.notice;return row?<input aria-label={row.bill_no+'本次付款金额'} inputMode="decimal" disabled={edit.disabled||Boolean(data!.reason)||edit.waiting} value={edit.draft(row).amount} onChange={e=>edit.update(row,'amount',e.target.value)}/>:data!.pay;}
function Actions({data}:ICellRendererParams<PayView>){const edit=useContext(PaymentEditing);return data!.notice?<Button disabled={edit.disabled} onClick={()=>edit.remove(data!.notice!.notice_id)}>移出</Button>:null;}
export function PaymentGrid({rows,due,normalize,warningIds,...editing}:Editing&{rows:NoticeRow[];due:(row:NoticeRow)=>string;normalize:(value:string)=>string|null;warningIds:number[]}){
  const scale=Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))||1;
  const views:PayView[]=rows.map(row=>({id:String(row.notice_id),notice:row,bill:row.bill_no,project:row.project_display,approval:row.approve_status||'未批',approved:money(row.amount_approved),paid:money(row.amount_paid),due:money(due(row)),pay:editing.draft(row).amount,reason:row.pay_block_reason|| (cents(due(row))<=0n?'本次应付不大于0，请调整付款金额':'')}));
  const total:PayView={id:'total',notice:null,bill:'合计（元）',project:'',approval:'',approved:'',paid:'',due:money(decimal(rows.reduce((sum,row)=>sum+cents(due(row)),0n))),pay:rows.every(row=>normalize(editing.draft(row).amount)!==null)?money(decimal(rows.reduce((sum,row)=>sum+cents(normalize(editing.draft(row).amount)!),0n))):'待核对',reason:''};
  const floors=['approved','paid','due','pay'].map((field,index)=>Math.max(numberColumnWidth([...views,total].map(row=>row[field as keyof PayView]),scale,field==='pay').minWidth,
    completeColumnWidth([],['审批金额','已付金额','本次应付','本次付款金额'][index]!,scale).minWidth));
  const signature=floors.join(':')+':'+fullTextWidth(views.map(row=>row.bill),scale).minWidth;
  const columns=useMemo<ColDef<PayView>[]>(()=>[
    {field:'bill',headerName:'单据编码',...fullTextWidth(views.map(row=>row.bill),scale),wrapText:false},
    {field:'project',headerName:'付款项目',...textWidth(96,160,scale,1),cellRenderer:({value}:ICellRendererParams<PayView>)=><EllipsisText text={String(value??'')}/>},
    {field:'approval',headerName:'审批状态',...completeColumnWidth(views.map(row=>row.approval),'审批状态',scale,12),cellRenderer:({value,data}:ICellRendererParams<PayView>)=>data!.notice?<Tag className={'status-tag '+(value==='已批'?'status-positive':'status-pending')}>{value}</Tag>:null},
    ...(['approved','paid','due'] as const).map((field,index):ColDef<PayView>=>({field,headerName:['审批金额','已付金额','本次应付'][index]!,minWidth:floors[index]!,cellClass:'money',wrapText:false})),
    {colId:'method',headerName:'实际付款方式',minWidth:110*scale,cellRenderer:Method},
    {field:'pay',headerName:'本次付款金额',minWidth:floors[3]!,cellClass:'money',cellRenderer:Amount},
    {field:'reason',headerName:'不可付原因',minWidth:160*scale,wrapText:true,autoHeight:true,valueFormatter:p=>p.data?.notice?p.value||'—':''},
    {colId:'actions',headerName:'操作',...completeColumnWidth(['移出'],'操作',scale,16),cellRenderer:Actions},
  ],[signature,scale]);
  return <PaymentEditing.Provider value={editing}><ReadGrid singleLine table="notice-payment" label="本次付款清单" className="notice-pay-table" domLayout="autoHeight" rows={views} totals={[total]} rowId={row=>row.id} columns={columns} scale={scale} grid={{getRowClass:p=>p.data?.notice&&warningIds.includes(p.data.notice.notice_id)?'payment-term-warning':''}}/></PaymentEditing.Provider>;
}
