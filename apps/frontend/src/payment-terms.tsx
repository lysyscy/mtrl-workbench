import { useQuery } from '@tanstack/react-query';
import Button from 'antd/es/button';
import { ApiError, record, requestJson } from './api';
import { ReadGrid } from './business-grid';
import { numberColumnWidth } from './grid';
import type { PaymentContextRow } from './payment-context';
import { money } from './notices-api';

function ContractMaterial({ id }: { id: number }) {
  const query = useQuery({ queryKey: ['payment-contract-material',id], retry: false, refetchOnWindowFocus: false, queryFn: async ({ signal }) => {
    const value = await requestJson(`/api/m11/detail?id=${id}`, { signal });
    if (!record(value) || !record(value.data) || typeof value.data.material !== 'string') throw new ApiError('合同材料名读取失败');
    return value.data.material;
  } });
  return query.isPending ? <span>读取中…</span> : query.isError ? <span>材料名未读到<Button size="small" onClick={() => void query.refetch()}>重读</Button></span> : <span>{query.data || '未填写材料名'}</span>;
}
export function PaymentTerms({ rows, project, amount }: { rows: PaymentContextRow[]; project: (id: number) => string; amount: (id: number) => string | null }) {
  const warnings = rows.filter(row => row.term_warning);
  if (!warnings.length) return null;
  return <section className="payment-terms" aria-label="账期提醒"><div className="payment-terms-heading"><strong>未满账期</strong><span>可继续付款</span></div>
    <p>依据录入发票日期计算提醒截止，日期真实性需人工核对；不代表准确应付款日或到期可付金额。</p>
    <ReadGrid table="payment-terms" className="payment-terms-table" label="账期发票依据" domLayout="autoHeight" rows={warnings.flatMap(row=>row.term_warning!.invoices.map((invoice,index)=>({id:row.notice_id+':'+invoice.invoice_id,row,invoice,first:index===0})))} rowId={item=>item.id} grid={{getRowClass:p=>p.data?.first?'payment-terms-start':''}} columns={[
      {colId:'project',headerName:'付款项目',valueGetter:p=>p.data!.first?project(p.data!.row.notice_id):''},
      {colId:'material',headerName:'合同材料名',cellRenderer:({data}:{data:{first:boolean;row:PaymentContextRow}})=>data.first?<ContractMaterial id={data.row.contract_id!}/>:null},
      {colId:'amount',headerName:'本条付款金额',...numberColumnWidth(warnings.map(row=>amount(row.notice_id)===null?'待核对':money(amount(row.notice_id)!))),cellClass:'money',valueGetter:p=>!p.data!.first?'':amount(p.data!.row.notice_id)===null?'待核对':money(amount(p.data!.row.notice_id)!)},
      {colId:'invoice',headerName:'发票日期',valueGetter:p=>p.data!.invoice.invoice_date},
      {colId:'term',headerName:'账期',valueGetter:p=>p.data!.first?p.data!.row.term_warning!.payment_term:''},
      {colId:'deadline',headerName:'提醒截止',valueGetter:p=>p.data!.invoice.remind_through||'日期范围以外'},
    ]}/>
  </section>;
}
