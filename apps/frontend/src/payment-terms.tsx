import { useQuery } from '@tanstack/react-query';
import Button from 'antd/es/button';
import { ApiError, record, requestJson } from './api';
import { BoundedTable } from './bounded-table';
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
    <div className="payment-terms-table"><BoundedTable columns={[{ min: 9, max: 22, flex: 1 },{ min: 9, max: 24, flex: 1 },{ min: 10, max: 14 },{ min: 11, max: 14 },{ min: 8, max: 18 },{ min: 11, max: 18 }]}><thead><tr>{['付款项目','合同材料名','本条付款金额','发票日期','账期','提醒截止'].map(t => <th key={t}>{t}</th>)}</tr></thead>
    <tbody>{warnings.flatMap(row => row.term_warning!.invoices.map((invoice,index,all) => <tr key={`${row.notice_id}:${invoice.invoice_id}`} className={index === 0 ? 'payment-terms-start' : undefined}>
      {index === 0 && <><td rowSpan={all.length}>{project(row.notice_id)}</td><td rowSpan={all.length}><ContractMaterial id={row.contract_id!} /></td><td rowSpan={all.length} className="money">{amount(row.notice_id) === null ? '待核对' : money(amount(row.notice_id)!)}</td></>}
      <td><time>{invoice.invoice_date}</time></td>{index === 0 && <td rowSpan={all.length}>{row.term_warning!.payment_term}</td>}<td><time>{invoice.remind_through || '日期范围以外'}</time></td>
    </tr>))}</tbody></BoundedTable></div>
  </section>;
}
