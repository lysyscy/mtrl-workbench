import * as v from 'valibot';
import { ApiError, record, requestJson } from './api';
import { cents } from './notices-api';
const nonArrayObject = v.custom<object>(record);
const positiveId = v.pipe(v.number(), v.safeInteger(), v.minValue(1));
const flowSchema = v.intersect([v.object({
  id: positiveId, notice_id: v.nullable(positiveId), project_id: v.nullable(positiveId),
  flow_no: v.string(), doc_no: v.string(), doc_date: v.string(), bill_name: v.string(),
  project_key: v.string(), project_display: v.string(), payee: v.string(), category_label: v.string(),
  amount_approved: v.nullable(v.string()), pay_date: v.string(), amount: v.string(),
  pay_method: v.string(), remark: v.string(), created_by: v.string(),
  status: v.picklist(['effective', 'revoked']), status_label: v.string(), revoke_reason: v.string(),
}), nonArrayObject]);
const flowsSchema = v.intersect([v.object({ rows: v.array(flowSchema) }), nonArrayObject]);
export type Flow = v.InferOutput<typeof flowSchema>;
export async function loadFlows(signal?: AbortSignal): Promise<Flow[]> {
  const data = await requestJson('/api/m05/flows?year_month=', { signal: signal ?? null });
  if (!v.is(flowsSchema, data)) throw new ApiError('付款流水读取不完整，请重试。');
  return data.rows.map(row => {
    cents(row.amount);
    if (row.amount_approved !== null) cents(row.amount_approved);
    return row;
  });
}
export function saveBlob(blob: Blob, filename: string) { const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
