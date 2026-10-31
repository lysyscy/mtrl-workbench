import { ApiError, body, confirmWrite, record, requestJson } from './api';

export type DeliveryStatus = 'queued' | 'working' | 'uncertain' | 'success' | 'duplicate' | 'pending' | 'deleted' | 'failed';
export interface DeliveryItem { id: number; position: number; invoice_id: number | null; original_id: number | null; status: DeliveryStatus; message: string; can_run: boolean }
export interface DeliveryBatch { id: number; request_id: string; created_at: string; items: DeliveryItem[] }
export interface DeliveryBatchSummary { id: number; request_id: string; created_at: string }
const id = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v > 0;
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(v);
export const deliveryLabels: Record<DeliveryStatus, string> = { queued: '等待下载', working: '处理中', uncertain: '待核实', success: '已接收', duplicate: '重复已处理', pending: '待确认', deleted: '已删除', failed: '失败' };
export function readDeliveryBatch(v: unknown): DeliveryBatch {
  if (!record(v) || !id(v.id) || !uuid(v.request_id) || typeof v.created_at !== 'string' || !Array.isArray(v.items) || !v.items.length || !v.items.every(i => record(i) && id(i.id) && id(i.position) && (i.invoice_id === null || id(i.invoice_id)) && (i.original_id === null || id(i.original_id)) && typeof i.status === 'string' && Object.hasOwn(deliveryLabels, i.status) && typeof i.message === 'string' && typeof i.can_run === 'boolean' && ((i.invoice_id === null) === (i.original_id === null)) && (!['success', 'duplicate', 'pending', 'deleted'].includes(i.status) || id(i.invoice_id) && !i.can_run))) throw new ApiError('收票批次读取不完整，请重新读取核对。');
  const batch = v as unknown as DeliveryBatch;
  if (new Set(batch.items.map(i => i.id)).size !== batch.items.length || batch.items.some((item, index) => item.position !== index + 1)) throw new ApiError('收票批次条目未能完整核对，请重新读取。');
  return batch;
}
export async function getDeliveryBatch(id: number, signal?: AbortSignal) { return readDeliveryBatch(await requestJson(`/api/m13/invoice-batches/${id}`, signal ? { signal } : {})); }
export async function findDeliveryBatch(requestId: string, signal?: AbortSignal) {
  const result = await requestJson(`/api/m13/invoice-batches/request/${requestId}`, signal ? { signal } : {});
  if (!record(result) || typeof result.found !== 'boolean' || !result.found && result.batch !== null) throw new ApiError('收票批次建立结果未能核对，请重新读取。');
  const batch = result.found ? readDeliveryBatch(result.batch) : null;
  if (batch && batch.request_id !== requestId) throw new ApiError('收票批次身份未能核对，请重新读取。');
  return batch;
}
export async function getDeliveryBatches(signal?: AbortSignal): Promise<DeliveryBatchSummary[]> {
  const result = await requestJson('/api/m13/invoice-batches', signal ? { signal } : {});
  if (!record(result) || !Array.isArray(result.batches) || !result.batches.every(b => record(b) && id(b.id) && uuid(b.request_id) && typeof b.created_at === 'string')) throw new ApiError('收票批次列表读取不完整，请重新读取。');
  return result.batches as DeliveryBatchSummary[];
}
export async function createDeliveryBatch(requestId: string, links: string, signal: AbortSignal) {
  const result = await requestJson('/api/m13/invoice-batches', { method: 'POST', signal, ...body({ request_id: requestId, links }) });
  confirmWrite(record(result) && result.ok === true, '建立收票批次的回执待核实，请重新读取。');
  const batch = readDeliveryBatch((result as Record<string, unknown>).batch);
  confirmWrite(batch.request_id === requestId, '收票批次回执身份不一致，请重新读取核对。');
  return batch;
}
export async function runDeliveryItem(batchId: number, itemId: number, signal: AbortSignal) {
  const result = await requestJson(`/api/m13/invoice-batches/${batchId}/items/${itemId}/run`, { method: 'POST', signal });
  confirmWrite(record(result) && result.ok === true, '本项收票结果待核实，请重新读取后续办。');
  const batch = readDeliveryBatch((result as Record<string, unknown>).batch);
  confirmWrite(batch.id === batchId && batch.items.some(i => i.id === itemId), '本项收票回执对象不一致，请重新读取。');
  return batch;
}
