import { createContext, memo, useContext, useMemo } from 'react';
import Button from 'antd/es/button';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { NoticeRow } from './notices-api';
import { cents, decimal, money } from './notices-api';
import { cacheFontMeasurement, cachedNumberColumnWidths, numberColumnWidth, fullTextWidth, textWidth } from './grid';
import { completeColumnWidth, EllipsisText } from './grid-text';
import { BoundedGrid } from './bounded-grid';
import type { BoundedGridMetrics } from './bounded-grid';

interface PayView { id:string; notice:NoticeRow|null; bill:string; project:string; approval:string; approved:string; paid:string; due:string; pay:string; reason:string }
interface Editing { disabled:boolean; waiting:boolean; methods:string[]; draft:(row:NoticeRow)=>{amount:string;pay_method:string}; update:(row:NoticeRow,field:'amount'|'pay_method',value:string)=>void; remove:(id:number)=>void }
const PaymentEditing=createContext<Editing>(null!);
const MethodSelect = memo(function MethodSelect({row, value, disabled, methods, update}: Pick<Editing,'disabled'|'methods'|'update'> & {row: NoticeRow; value: string}) {
  const options = useMemo(() => methods.map(value => ({value, label:value})), [methods]);
  return <Select aria-label={row.bill_no+'实际付款方式'} disabled={disabled} value={value}
    onChange={method => update(row, 'pay_method', method)} options={options}/>;
});
function Method({data}:ICellRendererParams<PayView>) {
  const edit = useContext(PaymentEditing), row = data!.notice;
  return row ? <MethodSelect row={row} value={edit.draft(row).pay_method} disabled={edit.disabled || Boolean(data!.reason) || edit.waiting} methods={edit.methods} update={edit.update}/> : null;
}
function Amount({data}:ICellRendererParams<PayView>){const edit=useContext(PaymentEditing),row=data!.notice;return row?<input aria-label={row.bill_no+'本次付款金额'} inputMode="decimal" disabled={edit.disabled||Boolean(data!.reason)||edit.waiting} value={edit.draft(row).amount} onChange={e=>edit.update(row,'amount',e.target.value)}/>:data!.pay;}
function Actions({data}:ICellRendererParams<PayView>){const edit=useContext(PaymentEditing);return data!.notice?<Button disabled={edit.disabled} onClick={()=>edit.remove(data!.notice!.notice_id)}>移出</Button>:null;}
export const PaymentGrid = memo(function PaymentGrid({rows,due,normalize,warningIds,scale,height,onMetrics,...editing}:Editing&{scale:number;rows:NoticeRow[];due:(row:NoticeRow)=>string;normalize:(value:string)=>string|null;warningIds:number[];height?:number|undefined;onMetrics?:(metrics:BoundedGridMetrics)=>void}){
  const initialViews = useMemo(() => rows.map(row => {
    const available = due(row);
    return {id:String(row.notice_id), notice:row, bill:row.bill_no, project:row.project_display, approval:row.approve_status||'未批',
      approved:money(row.amount_approved), paid:money(row.amount_paid), due:money(available), pay:available,
      reason:row.pay_block_reason || (cents(available)<=0n?'本次应付不大于0，请调整付款金额':'')};
  }), [rows, due]);
  const views = initialViews.map(view => {
    const pay = editing.draft(view.notice).amount;
    return pay === view.pay ? view : {...view, pay};
  });
  const totalDue = useMemo(() => money(decimal(initialViews.reduce((sum, view) => sum + cents(view.pay), 0n))), [initialViews]);
  let payCents: bigint | null = 0n;
  for (const view of views) {
    const normalized = normalize(view.pay);
    if (normalized === null) { payCents = null; break; }
    payCents += cents(normalized);
  }
  const total: PayView = {id:'total', notice:null, bill:'合计（元）', project:'', approval:'',
    approved:'', paid:'', due:totalDue, pay:payCents === null ? '待核对' : money(decimal(payCents)), reason:''};
  const measureFixed = useMemo(() => cacheFontMeasurement(() => {
    const floors = (['approved', 'paid', 'due'] as const).map((field, index) => Math.max(
      numberColumnWidth([...initialViews.map(row => row[field]), field === 'due' ? totalDue : ''], scale).minWidth,
      completeColumnWidth([], ['审批金额', '已付金额', '本次应付'][index]!, scale).minWidth,
    ));
    return {
      bill: fullTextWidth(initialViews.map(row => row.bill), scale),
      approval: completeColumnWidth(initialViews.map(row => row.approval), '审批状态', scale, 12),
      actions: completeColumnWidth(['移出'], '操作', scale, 16),
      payHeader: completeColumnWidth([], '本次付款金额', scale).minWidth,
      floors,
    };
  }), [initialViews, scale, totalDue]);
  const { bill, approval, actions, payHeader, floors } = measureFixed();
  const measurePay = useMemo(cachedNumberColumnWidths, [initialViews, scale]);
  const payFloor = Math.max(payHeader, measurePay('pay', [...views.map(row => row.pay), total.pay], scale, true).minWidth);
  const signature = [bill.minWidth, approval.minWidth, actions.minWidth, ...floors, payFloor].join(':');
  const columns=useMemo<ColDef<PayView>[]>(()=>[
    {field:'bill',headerName:'单据编码',...bill,wrapText:false},
    {field:'project',headerName:'付款项目',...textWidth(96,160,scale,1),cellRenderer:({value}:ICellRendererParams<PayView>)=><EllipsisText text={String(value??'')}/>},
    {field:'approval',headerName:'审批状态',...approval,cellRenderer:({value,data}:ICellRendererParams<PayView>)=>data!.notice?<Tag className={'status-tag '+(value==='已批'?'status-positive':'status-pending')}>{value}</Tag>:null},
    ...(['approved','paid','due'] as const).map((field,index):ColDef<PayView>=>({field,headerName:['审批金额','已付金额','本次应付'][index]!,minWidth:floors[index]!,cellClass:'money',wrapText:false})),
    {colId:'method',headerName:'实际付款方式',minWidth:110*scale,cellRenderer:Method},
    {field:'pay',headerName:'本次付款金额',minWidth:payFloor,cellClass:'money',cellRenderer:Amount},
    {field:'reason',headerName:'不可付原因',minWidth:160*scale,wrapText:true,autoHeight:true,valueFormatter:p=>p.data?.notice?p.value||'—':''},
    {colId:'actions',headerName:'操作',...actions,cellRenderer:Actions},
  ],[signature,scale]);
  return <PaymentEditing.Provider value={editing}><BoundedGrid singleLine fitAfterFonts minRows={4} height={height} onMetrics={onMetrics} table="notice-payment" label="本次付款清单" className="notice-pay-table" rows={views} totals={[total]} rowId={row=>row.id} columns={columns} scale={scale} grid={{getRowClass:p=>p.data?.notice&&warningIds.includes(p.data.notice.notice_id)?'payment-term-warning':''}}/></PaymentEditing.Provider>;
});
