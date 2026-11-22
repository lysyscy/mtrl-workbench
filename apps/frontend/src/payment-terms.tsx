import { memo, useMemo } from 'react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { NoticeRow } from './notices-api';
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
interface InvoiceView {
  id: string; first: boolean; project: string; amount: string; contractId: number | undefined;
  invoice: string; term: string; deadline: string;
}
const invoiceId = (item: InvoiceView) => item.id;
function MaterialCell({data}: ICellRendererParams<InvoiceView>) {
  return data?.contractId === undefined ? null : <ContractMaterial id={data.contractId}/>;
}

export const PaymentTerms = memo(function PaymentTerms({rows,notices,amount,scale}: {
  rows: PaymentContextRow[]; notices: NoticeRow[]; amount: (row: NoticeRow) => string | null; scale: number;
}) {
  const byId = useMemo(() => new Map(notices.map(row => [row.notice_id, row])), [notices]);
  const invoices = useMemo(() => rows.flatMap(row => {
    const warning = row.term_warning;
    if (!warning) return [];
    const notice = byId.get(row.notice_id);
    return warning.invoices.map((invoice, index) => ({
      id: row.notice_id+':'+invoice.invoice_id, first: index === 0,
      project: index === 0 ? notice?.project_display || '—' : '',
      contractId: index === 0 ? row.contract_id : undefined,
      invoice: invoice.invoice_date, term: index === 0 ? warning.payment_term : '',
      deadline: invoice.remind_through || '日期范围以外', amount: '',
      notice: index === 0 ? notice : undefined,
    }));
  }), [rows, byId]);
  const display = useMemo(() => invoices.map(item => {
    if (!item.first) return item;
    const value = item.notice ? amount(item.notice) : null;
    return {...item, amount: value === null ? '待核对' : money(value)};
  }), [invoices, amount]);
  const bounds = useMemo(() => numberColumnWidth(display.map(item => item.amount), scale), [display, scale]);
  const {initialWidth, minWidth} = bounds, maxWidth = 'maxWidth' in bounds ? bounds.maxWidth : undefined;
  const columns = useMemo<ColDef<InvoiceView>[]>(() => [
    {field:'project',headerName:'付款项目'},
    {field:'contractId',colId:'material',headerName:'合同材料名',cellRenderer:MaterialCell},
    {field:'amount',headerName:'本条付款金额',initialWidth,minWidth,...(maxWidth === undefined ? {} : {maxWidth}),cellClass:'money'},
    {field:'invoice',headerName:'发票日期',cellDataType:'text'}, {field:'term',headerName:'账期'}, {field:'deadline',headerName:'提醒截止',cellDataType:'text'},
  ], [initialWidth, minWidth, maxWidth]);
  if (!display.length) return null;
  return <section className="payment-terms" aria-label="账期提醒"><div className="payment-terms-heading"><strong>未满账期</strong><span>可继续付款</span></div>
    <p>依据录入发票日期计算提醒截止，日期真实性需人工核对；不代表准确应付款日或到期可付金额。</p>
    <ReadGrid table="payment-terms" className="payment-terms-table" label="账期发票依据" domLayout="autoHeight" rows={display} rowId={invoiceId} scale={scale}
      grid={{getRowClass:p=>p.data?.first?'payment-terms-start':''}} columns={columns}/>
  </section>;
});
