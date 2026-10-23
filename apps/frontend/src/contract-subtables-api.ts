import { ApiError, record, requestJson } from './api';
import { body, cents } from './notices-api';

export type SubtableKind = 'supplier' | 'trade' | 'payment';
export interface InvoiceRow { id: number; kind: 'supplier' | 'trade'; date: string; amount: string }
export interface PaymentRow { id: number; date: string; amount: string; source: 'manual' | 'notice'; notice_id: number | null }
export interface PaymentDisplayRow extends PaymentRow { display_kind: 'manual' | 'flow' | 'stat'; flow_id?: number; mismatch?: boolean }
export interface SubtableDetail {
  id: number; supplier: string; trade_co: string | null; inv_sum: string; trade_inv_sum: string; settle: string; pay_sum: string; debt: string;
  supplier_invoices: InvoiceRow[]; trade_invoices: InvoiceRow[]; payments: PaymentRow[]; payment_display_rows: PaymentDisplayRow[];
}
const id = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const amount = (value: unknown): value is string => typeof value === 'string' && /^-?\d+(?:\.\d{1,2})?$/.test(value);
function payment(value: unknown): value is PaymentRow {
  return record(value) && id(value.id) && typeof value.date === 'string' && amount(value.amount) &&
    (value.source === 'manual' && value.notice_id === null || value.source === 'notice' && id(value.notice_id));
}
export function readSubtables(value: unknown, contractId: number): SubtableDetail {
  const d = record(value) ? value.data : undefined;
  if (!record(d) || d.id !== contractId || typeof d.supplier !== 'string' || !(d.trade_co === null || typeof d.trade_co === 'string') ||
    !['inv_sum','trade_inv_sum','settle','pay_sum','debt'].every(k => amount(d[k]))) throw new ApiError('合同子表读取不完整，请重读核对。');
  for (const [key,kind] of [['supplier_invoices','supplier'],['trade_invoices','trade']] as const) {
    if (!Array.isArray(d[key]) || !d[key].every(x => record(x) && id(x.id) && x.kind === kind && typeof x.date === 'string' && amount(x.amount))) throw new ApiError('合同发票读取不完整，请重读核对。');
  }
  if (!Array.isArray(d.payments) || !d.payments.every(payment) || !Array.isArray(d.payment_display_rows) || !d.payment_display_rows.every(x => payment(x) && record(x) &&
    (x.source === 'manual' && x.display_kind === 'manual' || x.source === 'notice' && (x.display_kind === 'flow' && id(x.flow_id) || x.display_kind === 'stat' && x.mismatch === true)))) throw new ApiError('合同付款来源读取不完整，请重读核对。');
  return d as unknown as SubtableDetail;
}
export async function loadSubtables(contractId: number, signal?: AbortSignal) {
  return readSubtables(await requestJson(`/api/m11/detail?id=${contractId}`, { signal: signal ?? null }), contractId);
}
export function todayBeijing(): string {
  const parts = new Intl.DateTimeFormat('en', { timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit' }).formatToParts(new Date());
  return ['year','month','day'].map(key => parts.find(p => p.type === key)!.value).join('-');
}
export interface SubtableDraft { date: string; amount: string; initialDate: string }
export function emptySubtableDraft(): SubtableDraft { const date=todayBeijing();return {date,amount:'',initialDate:date}; }
export function draftProblem(draft: SubtableDraft): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.date) || Number.isNaN(Date.parse(`${draft.date}T00:00:00Z`)) || new Date(`${draft.date}T00:00:00Z`).toISOString().slice(0,10) !== draft.date) return '请选择有效日期。';
  if (!/^\d+(?:\.\d{1,2})?$/.test(draft.amount.trim()) || cents(draft.amount.trim()) <= 0n) return '金额须大于0，最多两位小数。';
  return '';
}
export async function writeSubtable(contractId: number, kind: SubtableKind, draft: SubtableDraft | null, rowId?: number): Promise<number | null> {
  const adding = draft !== null;
  const result = await requestJson(`/api/m11/${kind === 'payment' ? 'payment' : 'invoice'}/${adding ? 'add' : 'del'}`, { method:'POST', ...body(adding ? {id:contractId,date:draft.date,amount:draft.amount.trim(),...(kind === 'payment' ? {source:'manual'} : {kind})} : {row_id:rowId}) });
  if (!record(result) || result.ok !== true || adding && !id(result.id)) throw new ApiError('保存回执不完整，请重读核对，勿重复操作。');
  return adding ? result.id as number : null;
}
