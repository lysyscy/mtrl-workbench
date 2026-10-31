import { ApiError, body, cents, confirmWrite, record, requestJson } from './api';

export interface OilInvoiceOriginal { id: number; sha256: string; invoice_id: number; byte_size: number; outcome: 'received' | 'duplicate' | 'conflict'; reason: string; recognized: { invoice_no: string | null; invoice_date: string | null; amount: string | null; card_no: string | null }; resolution: string | null }
export interface OilInvoiceAllocation { id: number; account_id: number; project_id: number; card_id: number | null; amount: string }
export interface OilInvoice { id: number; invoice_no: string | null; invoice_date: string | null; card_no: string | null; amount: string | null; status: 'pending' | 'registered' | 'voided'; kind: 'normal' | 'credit'; related_invoice_id: number | null; void_date: string | null; change_note: string; reason: string; remark: string; version: string; allocations: OilInvoiceAllocation[]; originals: OilInvoiceOriginal[] }
export interface OilInvoices { invoices: OilInvoice[]; total_amount: string }
const id = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v > 0;
const amount = (v: unknown): v is string => typeof v === 'string' && /^-?\d+\.\d{2}$/.test(v);
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(v);
const nullableText = (v: unknown) => v === null || typeof v === 'string';
export function readOilOriginal(v: unknown): OilInvoiceOriginal {
  if (!record(v) || !id(v.id) || !id(v.invoice_id) || !id(v.byte_size) || typeof v.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(v.sha256) || !['received', 'duplicate', 'conflict'].includes(String(v.outcome)) || typeof v.reason !== 'string' || !nullableText(v.resolution) || !record(v.recognized) || !['invoice_no', 'invoice_date', 'card_no', 'amount'].every(key => nullableText((v.recognized as Record<string, unknown>)[key]))) throw new ApiError('发票原件回执不完整，请重读核对。');
  return v as unknown as OilInvoiceOriginal;
}
export function readOilInvoice(v: unknown): OilInvoice {
  if (!record(v) || !id(v.id) || !uuid(v.version) || !nullableText(v.invoice_no) || !nullableText(v.card_no) || !(v.invoice_date === null || typeof v.invoice_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v.invoice_date)) || !(v.amount === null || amount(v.amount)) || !['pending', 'registered', 'voided'].includes(String(v.status)) || !['normal', 'credit'].includes(String(v.kind)) || !(v.related_invoice_id === null || id(v.related_invoice_id)) || !nullableText(v.void_date) || typeof v.change_note !== 'string' || typeof v.reason !== 'string' || typeof v.remark !== 'string' || !Array.isArray(v.allocations) || !v.allocations.every(a => record(a) && id(a.id) && id(a.project_id) && id(a.account_id) && (a.card_id === null || id(a.card_id)) && amount(a.amount)) || !Array.isArray(v.originals)) throw new ApiError('发票台账读取不完整，请重读核对。');
  const originals = v.originals.map(readOilOriginal), row = v as unknown as OilInvoice;
  if (!originals.length || originals.some(o => o.invoice_id !== row.id) || new Set(originals.map(o => o.id)).size !== originals.length || new Set(row.allocations.map(a => a.account_id)).size !== row.allocations.length || row.status === 'registered' && (!row.invoice_no || !row.invoice_date || row.amount === null || !row.allocations.length || row.allocations.reduce((n, a) => n + cents(a.amount), 0n) !== cents(row.amount) || row.kind === 'normal' && (cents(row.amount) <= 0n || row.related_invoice_id !== null) || row.kind === 'credit' && (cents(row.amount) >= 0n || row.related_invoice_id === null))) throw new ApiError('发票与分配未能完整核对，请重读。');
  return { ...row, originals };
}
export function readOilInvoices(v: unknown): OilInvoices {
  if (!record(v) || !Array.isArray(v.invoices) || !amount(v.total_amount)) throw new ApiError('发票台账读取不完整，请重读核对。');
  const invoices = v.invoices.map(readOilInvoice);
  for (const row of invoices.filter(r => r.status === 'registered' && r.kind === 'credit')) {
    const parent = invoices.find(r => r.id === row.related_invoice_id);
    if (!parent || parent.status !== 'registered' || parent.kind !== 'normal' || cents(row.amount!) >= 0n) throw new ApiError('红票与原票未能核对，请重读。');
  }
  for (const parent of invoices.filter(r => r.status === 'registered' && r.kind === 'normal')) if (invoices.filter(r => r.status === 'registered' && r.related_invoice_id === parent.id).reduce((n, r) => n - cents(r.amount!), 0n) > cents(parent.amount!)) throw new ApiError('累计红冲与原票金额未能核对，请重读。');
  if (new Set(invoices.map(r => r.id)).size !== invoices.length || invoices.filter(r => r.status === 'registered').reduce((n, r) => n + cents(r.amount!), 0n) !== cents(v.total_amount)) throw new ApiError('发票台账合计未能核对，请重读。');
  return { invoices, total_amount: v.total_amount };
}
export async function getOilInvoices(signal?: AbortSignal) { return readOilInvoices(await requestJson('/api/m13/invoices', signal ? { signal } : {})); }
export async function receiveOilInvoice(file: File, digest: string, signal: AbortSignal) {
  const form = new FormData(); form.append('file', file);
  const result = await requestJson('/api/m13/invoices/receive', { method: 'POST', body: form, signal });
  confirmWrite(record(result) && result.ok === true, '收票结果待核实，请重读核对，勿重复登记。');
  const original = readOilOriginal((result as Record<string, unknown>).original), item = readOilInvoice((result as Record<string, unknown>).item);
  confirmWrite(original.sha256 === digest && original.byte_size === file.size && original.invoice_id === item.id && item.originals.some(o => o.id === original.id && o.sha256 === digest), '收票回执与原件不一致，请重读核对。');
  return { original, item };
}
export async function readOilReceipt(digest: string, signal?: AbortSignal) {
  const result = await requestJson(`/api/m13/invoices/receipts/${digest}`, signal ? { signal } : {});
  if (!record(result) || typeof result.received !== 'boolean' || result.received && (!record(result.original) || readOilOriginal(result.original).sha256 !== digest) || !result.received && result.original !== null) throw new ApiError('收票结果未能核对，请重读。');
  return result.received;
}
export async function saveOilInvoiceRemark(row: OilInvoice, remark: string, signal: AbortSignal) {
  const result = await requestJson(`/api/m13/invoices/${row.id}/remark`, { method: 'PUT', signal, ...body({ version: row.version, remark }) });
  confirmWrite(record(result) && result.ok === true, '发票备注保存回执待核实，请重读核对。');
  const saved = readOilInvoice((result as Record<string, unknown>).item);
  confirmWrite(saved.id === row.id && saved.remark === remark, '发票备注回执与输入不一致，请重读核对。');
  return saved;
}

export type OilAllocationFields = Pick<OilInvoiceAllocation, 'project_id' | 'account_id' | 'amount'>;
export interface OilInvoiceCorrection { invoice_no: string; invoice_date: string; amount: string; card_no: string | null; allocations: OilAllocationFields[]; note: string; review_original_id: number | null; related_invoice_id?: number }
function checkParts(saved: OilInvoice, parts: OilAllocationFields[]) {
  return saved.allocations.length === parts.length && parts.every(p => saved.allocations.some(a => a.project_id === p.project_id && a.account_id === p.account_id && cents(a.amount) === cents(p.amount)));
}
export async function changeOilInvoice(row: OilInvoice, action: 'correct' | 'allocations' | 'credit' | 'void' | `originals/${number}/resolve`, fields: Record<string, unknown>, signal: AbortSignal) {
  const result = await requestJson(`/api/m13/invoices/${row.id}/${action}`, { method: action === 'credit' || action === 'void' ? 'POST' : 'PUT', signal, ...body({ ...fields, version: row.version }) });
  confirmWrite(record(result) && result.ok === true, '发票变更回执待核实，请重读，勿重复提交。');
  const saved = readOilInvoice((result as Record<string, unknown>).item);
  confirmWrite(saved.id === row.id, '发票变更对象未能核对，请重读。');
  if (action === 'correct' || action === 'credit') confirmWrite(saved.invoice_no === String(fields.invoice_no).trim() && saved.invoice_date === fields.invoice_date && cents(saved.amount!) === cents(String(fields.amount)) && saved.card_no === (fields.card_no || null) && saved.change_note === String(fields.note).trim() && checkParts(saved, fields.allocations as OilAllocationFields[]) && (action !== 'credit' || saved.kind === 'credit' && saved.related_invoice_id === fields.related_invoice_id), '票面或整体分配回执与输入不一致，请重读核对。');
  if (action === 'allocations') confirmWrite(checkParts(saved, fields.allocations as OilAllocationFields[]), '分配回执与输入不一致，请重读核对。');
  if (action === 'void') confirmWrite(saved.status === 'voided' && saved.void_date === fields.date && saved.change_note === String(fields.note).trim(), '作废回执与输入不一致，请重读核对。');
  if (action.startsWith('originals/')) confirmWrite(saved.originals.some(o => o.id === Number(action.split('/')[1]) && o.resolution === String(fields.note).trim()), '原件处理结论未能核对，请重读。');
  return saved;
}
