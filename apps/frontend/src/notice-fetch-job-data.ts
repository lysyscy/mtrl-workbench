import * as v from 'valibot';
import { ApiError, requestJson } from './api';
import { readyMatch, reviewMatch } from './notice-link-matches';

export const noticeFetchJobsPath = '/api/m03/notices/fetch-jobs';
const count = v.pipe(v.number(), v.safeInteger(), v.minValue(0));
const text = v.string();
const result = v.object({
  year_month: text, notices_saved: v.boolean(), fetched: count, saved: count, upserted: count,
  created: count, updated: count, excluded: count, ignored_count: count, unresolved: count,
  ignored: v.array(v.object({ bill_no: text, project_name: text, doc_name: text, reason: text })),
  auto_linked: count, auto_linked_items: v.array(readyMatch),
  manual_review: count, manual_review_items: v.array(reviewMatch),
  payable_source_failed: v.boolean(), payable_source_error: text, fetch_error: text, matching_error: text,
});
const jobFields = {
  id: v.pipe(count, v.minValue(1)), account: text, year_month: text, stage_label: text, error_message: text,
  created_at: text, updated_at: text,
};
const jobSchema = v.variant('status', [
  v.object({
    ...jobFields, status: v.literal('running'), stage: v.picklist(['fetching_notices', 'saving_notices', 'matching_jc']),
    result: v.nullable(result), completed_at: v.null(), acknowledged_at: v.null(),
  }),
  v.object({
    ...jobFields, status: v.literal('completed'), stage: v.literal('completed'),
    result, completed_at: text, acknowledged_at: v.nullable(text),
  }),
  v.object({
    ...jobFields, status: v.literal('failed'), stage: v.literal('failed'),
    result, completed_at: text, acknowledged_at: v.nullable(text),
  }),
]);

export type NoticeFetchJob = v.InferOutput<typeof jobSchema>;
export type FinishedNoticeFetchJob = Exclude<NoticeFetchJob, { status: 'running' }>;

export function readNoticeFetchJob(value: unknown, expected: { account: string; month?: string; id?: number }) {
  const parsed = v.safeParse(jobSchema, value);
  if (!parsed.success || parsed.output.account !== expected.account
    || expected.month !== undefined && parsed.output.year_month !== expected.month
    || expected.id !== undefined && parsed.output.id !== expected.id
    || parsed.output.result && parsed.output.result.year_month !== parsed.output.year_month) {
    throw new ApiError('抓取任务回执与本次请求不一致，请重读。', 0, 'invalid_response');
  }
  return parsed.output;
}

export function fetchJobViews(jobs: readonly NoticeFetchJob[]) {
  const visible = jobs.filter(job => job.acknowledged_at === null).sort((a, b) => b.id - a.id);
  return {
    running: visible.find(job => job.status === 'running'),
    finished: visible.find(job => job.status !== 'running'),
  };
}

export function fetchJobPollInterval(job: NoticeFetchJob | undefined) {
  return job?.status === 'running' ? 1000 : false;
}

export function latestFetchJob(previous: NoticeFetchJob | undefined, incoming: NoticeFetchJob) {
  // A GET started before an ack or stage write may arrive after the newer snapshot.
  if (previous && (previous.acknowledged_at || previous.status !== 'running' && incoming.status === 'running'
    || previous.updated_at >= incoming.updated_at)) return previous;
  return incoming;
}

export async function recoverNoticeFetchJob(account: string, signal: AbortSignal) {
  const value = await requestJson(`${noticeFetchJobsPath}/active`, { signal });
  return value === null ? null : readNoticeFetchJob(value, { account });
}

export async function pollNoticeFetchJob(account: string, id: number, signal: AbortSignal) {
  const value = await requestJson(`${noticeFetchJobsPath}/${id}`, { signal });
  return readNoticeFetchJob(value, { account, id });
}

export async function acknowledgeNoticeFetchJob(account: string, id: number) {
  const value = await requestJson(`${noticeFetchJobsPath}/${id}/ack`, { method: 'POST' });
  const acknowledged = readNoticeFetchJob(value, { account, id });
  if (!acknowledged.acknowledged_at) throw new ApiError('关闭结果尚待确认，请重试。');
  return acknowledged;
}
