import { ApiError, record, requestJson } from './api';
import { cents } from './notices-api';
export interface Flow { id: number; notice_id: number | null; flow_no: string; doc_no: string; doc_date: string; bill_name: string; project_id: number | null; project_key: string; project_display: string; payee: string; category_label: string; amount_approved: string | null; pay_date: string; amount: string; pay_method: string; remark: string; created_by: string; status: string; status_label: string; revoke_reason: string }
export async function loadFlows(signal?: AbortSignal): Promise<Flow[]> {
  const data = await requestJson('/api/m05/flows?year_month=', { signal: signal ?? null });
  if (!record(data) || !Array.isArray(data.rows)) throw new ApiError('付款流水读取不完整，请重试。');
  return data.rows.map(row => { if (!record(row) || typeof row.id !== 'number' || typeof row.amount !== 'string') throw new ApiError('付款流水读取不完整，请重试。'); cents(row.amount); return row as unknown as Flow; });
}
export function saveBlob(blob: Blob, filename: string) { const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
