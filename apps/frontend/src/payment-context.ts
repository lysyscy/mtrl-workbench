import { ApiError, record, requestJson } from './api';
import { body } from './notices-api';

interface InvoiceReminder { invoice_id: number; invoice_date: string; remind_through: string | null }
interface TermWarning { message: string; payment_term: string; max_days: number; pay_date: string; invoice_side: 'supplier' | 'trade'; invoices: InvoiceReminder[] }
export interface PaymentContextRow {
  notice_id: number; default_pay_method: string; default_pay_method_source: 'plan' | 'contract' | 'fallback';
  contract_id?: number; contract_no?: string; payment_term?: string; contract_payment_method?: string; term_warning: TermWarning | null;
}
export interface PaymentContext { available: boolean; rows: PaymentContextRow[] }
export async function readPaymentContext(ids: number[], date: string, methods: string[], signal?: AbortSignal): Promise<PaymentContext> {
  let value: unknown;
  try { value = await requestJson('/api/m03/payment-context', { method: 'POST', ...body({ ids, pay_date: date }), ...(signal ? { signal } : {}) }); }
  catch (error) { if (error instanceof ApiError && error.status === 404) return { available: false, rows: [] }; throw error; }
  const incomplete = () => new ApiError('合同账期读取不完整，请重试。');
  if (!record(value) || value.ok !== true || value.pay_date !== date || !Array.isArray(value.rows)) throw incomplete();
  const seen = new Set<number>();
  for (const row of value.rows) {
    if (!record(row) || typeof row.notice_id !== 'number' || !Number.isSafeInteger(row.notice_id) || !ids.includes(row.notice_id) || seen.has(row.notice_id) || typeof row.default_pay_method !== 'string' || !methods.includes(row.default_pay_method) || !['plan','contract','fallback'].includes(String(row.default_pay_method_source))) throw incomplete();
    seen.add(row.notice_id);
    if (row.contract_id !== undefined && (!Number.isSafeInteger(row.contract_id) || !['contract_no','payment_term','contract_payment_method'].every(k => typeof row[k] === 'string'))) throw incomplete();
    const warning = row.term_warning;
    if (warning !== null && (!record(warning) || typeof warning.message !== 'string' || typeof warning.payment_term !== 'string' || !Number.isInteger(warning.max_days) || Number(warning.max_days) < 0 || warning.pay_date !== date || !['supplier','trade'].includes(String(warning.invoice_side)) || !Number.isSafeInteger(row.contract_id) || !Array.isArray(warning.invoices) || !warning.invoices.length || !warning.invoices.every(i => record(i) && Number.isSafeInteger(i.invoice_id) && typeof i.invoice_date === 'string' && (i.remind_through === null || typeof i.remind_through === 'string')))) throw incomplete();
  }
  if (ids.some(id => !seen.has(id))) throw new ApiError('部分通知书已不在付款记录中，请关闭并重新勾选核对。');
  return { available: true, rows: value.rows as PaymentContextRow[] };
}
