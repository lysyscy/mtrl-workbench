import * as v from 'valibot';
import { ApiError, record, requestJson } from './api';
import { cents } from './notices-api';
import { timeRange } from './business-time';
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
const count = v.pipe(v.number(), v.safeInteger(), v.minValue(0));
const barSchema = v.intersect([v.object({ key: v.string(), label: v.string(), amount: v.string() }), nonArrayObject]);
const statsSchema = v.intersect([v.object({
  granularity: v.picklist(['week', 'month']), buckets: v.array(v.string()), right: v.array(v.string()), counts: v.array(count),
  selected: v.intersect([v.object({ bucket: v.string(), projects: v.array(barSchema), total: v.string(), count }), nonArrayObject]),
}), nonArrayObject]);
const debtSchema = v.intersect([v.object({ by_project_category: v.array(v.intersect([
  v.object({ project: v.string(), jc: v.string(), material: v.string(), mech: v.string() }), nonArrayObject,
])) }), nonArrayObject]);
export type PaymentBar = v.InferOutput<typeof barSchema>;
export type PaymentStats = v.InferOutput<typeof statsSchema>;
export function readPaymentStats(value: unknown): PaymentStats {
  const invalid = () => new ApiError('付款统计读取不完整，请重试。');
  if (!v.is(statsSchema, value) || value.buckets.length !== value.right.length || value.buckets.length !== value.counts.length) throw invalid();
  for (const bucket of [...value.buckets, value.selected.bucket]) {
    if (!(value.granularity === 'month' ? /^\d{4}-\d{2}$/ : /^\d{4}-\d{2}-\d{2}$/).test(bucket)) throw invalid();
    try { timeRange(bucket); } catch { throw invalid(); }
  }
  for (const amount of [...value.right, value.selected.total, ...value.selected.projects.map(row => row.amount)]) cents(amount);
  return value;
}
export function readDebt(value: unknown) {
  if (!v.is(debtSchema, value)) throw new ApiError('欠款读取不完整，请重试。');
  for (const row of value.by_project_category) for (const amount of [row.jc, row.material, row.mech]) cents(amount);
  return value.by_project_category;
}
export async function loadFlows(signal?: AbortSignal, noticeId?: number): Promise<Flow[]> {
  const path = noticeId === undefined ? '/api/m05/flows?year_month=' : `/api/m05/flows?notice_id=${encodeURIComponent(String(noticeId))}`;
  const data = await requestJson(path, { signal: signal ?? null });
  if (!v.is(flowsSchema, data)) throw new ApiError('付款流水读取不完整，请重试。');
  return data.rows.map(row => {
    cents(row.amount);
    if (row.amount_approved !== null) cents(row.amount_approved);
    return row;
  });
}
export function saveBlob(blob: Blob, filename: string) { const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
