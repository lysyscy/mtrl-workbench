import assert from 'node:assert/strict';
import test from 'node:test';
import {
  acknowledgeNoticeFetchJob, fetchJobPollInterval, fetchJobViews, latestFetchJob, noticeFetchResultView, pollNoticeFetchJob,
  readNoticeFetchJob, recoverNoticeFetchJob,
} from '../../src/notice-fetch-job-data.ts';
import { readMatchPreview, readyLinkSelections, reviewLinkSelections } from '../../src/notice-link-matches.ts';

const account = 'test-account';
const month = '2026-11';
const job = {
  id: 12, account, year_month: month, status: 'running', stage: 'fetching_notices',
  stage_label: '正在抓取付款通知书…', error_message: '', result: null,
  created_at: '2026-11-26T10:00:00', updated_at: '2026-11-26T10:00:00',
  completed_at: null, acknowledged_at: null,
};
const saved = {
  year_month: month, notices_saved: true, fetched: 2, saved: 2, upserted: 2,
  created: 2, updated: 0, excluded: 0, ignored_count: 0, unresolved: 0, ignored: [],
  auto_linked: 0, auto_linked_items: [], manual_review: 0, manual_review_items: [],
  payable_source_failed: true, payable_source_error: '应付来源不可用', fetch_error: '', matching_error: '',
};
const completed = {
  ...job, status: 'completed', stage: 'completed', stage_label: '抓取完成', result: saved,
  completed_at: '2026-11-26T10:00:20', updated_at: '2026-11-26T10:00:20',
};

test('后台抓取在其他页面显示提醒，点击仅打开对应任务', () => {
  assert.equal(noticeFetchResultView({ pathname: '/projects', jobId: 12, openedId: null }), 'reminder');
  assert.equal(noticeFetchResultView({ pathname: '/projects', jobId: 12, openedId: 12 }), 'dialog');
  assert.equal(noticeFetchResultView({ pathname: '/projects', jobId: 13, openedId: 12 }), 'reminder');
  assert.equal(noticeFetchResultView({ pathname: '/notices', jobId: 13, openedId: null }), 'dialog');
});

test('重新进入工作区恢复后台任务，轮询到终态，关闭后按原任务确认', async t => {
  const calls = [];
  const acknowledged = { ...completed, acknowledged_at: '2026-11-26T10:01:00', updated_at: '2026-11-26T10:01:00' };
  const matching = { ...job, stage: 'matching_jc', stage_label: '正在自动关联集采合同…', result: saved };
  const replies = [job, { ...job, stage: 'saving_notices', stage_label: '正在保存通知书…' },
    matching, completed, acknowledged, null];
  t.mock.method(globalThis, 'fetch', async (path, init) => {
    calls.push([init.method ?? 'GET', path]);
    return Response.json(replies.shift());
  });

  const signal = new AbortController().signal;
  const recovered = await recoverNoticeFetchJob(account, signal);
  assert.equal(fetchJobViews([recovered]).running.stage_label, '正在抓取付款通知书…');
  assert.equal(fetchJobPollInterval(recovered), 1000);
  assert.equal((await pollNoticeFetchJob(account, job.id, signal)).stage, 'saving_notices');
  assert.equal((await pollNoticeFetchJob(account, job.id, signal)).stage_label, matching.stage_label);
  const finished = await pollNoticeFetchJob(account, job.id, signal);
  assert.equal(fetchJobPollInterval(finished), false);
  assert.equal(fetchJobViews([finished]).finished.result.payable_source_error, '应付来源不可用');
  const ack = await acknowledgeNoticeFetchJob(account, job.id);
  assert.equal(fetchJobViews([ack]).finished, undefined);
  assert.equal(latestFetchJob(ack, completed), ack);
  assert.equal(latestFetchJob(finished, job), finished);
  assert.equal(await recoverNoticeFetchJob(account, signal), null);
  assert.deepEqual(calls, [
    ['GET', '/api/m03/notices/fetch-jobs/active'],
    ['GET', '/api/m03/notices/fetch-jobs/12'],
    ['GET', '/api/m03/notices/fetch-jobs/12'],
    ['GET', '/api/m03/notices/fetch-jobs/12'],
    ['POST', '/api/m03/notices/fetch-jobs/12/ack'],
    ['GET', '/api/m03/notices/fetch-jobs/active'],
  ]);
});

test('重开可展示中断任务，未确认关闭时保留回执', async t => {
  const failed = { ...completed, status: 'failed', stage: 'failed', error_message: '服务已重启',
    result: { ...saved, matching_error: '服务已重启' } };
  t.mock.method(globalThis, 'fetch', async () => Response.json(failed));
  const result = await recoverNoticeFetchJob(account, new AbortController().signal);
  assert.equal(fetchJobViews([result, { ...job, id: 13 }]).finished.result.notices_saved, true);
  assert.equal(fetchJobViews([result]).finished.error_message, '服务已重启');
  await assert.rejects(() => acknowledgeNoticeFetchJob(account, job.id), /尚待确认/);
  assert.equal(fetchJobViews([result]).finished.id, job.id);
  assert.throws(() => readNoticeFetchJob(failed, { account: 'other-account' }), /不一致/);
  assert.throws(() => readNoticeFetchJob(completed, { account, id: 13 }), /不一致/);
});

test('分组保留候选依据，只提交高置信结果或明确选中的有效候选', () => {
  const target = { contract_id: 45, contract_no: 'CGHT45', supplier_name: '供应商甲',
    material: '钢材', selectable: true, evidence: ['发票同额'], payable_codes: ['YF1'],
    invoice_side: 'trade', invoice_match: true, invoice_ids: [8] };
  const row = { notice_id: 1, code: 'FK1', title: '钢材付款', project_name: '甲项目',
    bucket: 'auto_ready', rule_code: 'unique_payment_invoice', reason: '同额发票唯一',
    expected_amount: '15.00', expected_jc_supplier: '供应商甲', expected_warehouse_key: '甲仓库',
    target, payable_codes: ['YF1'], candidates: [] };
  const review = { ...row, notice_id: 2, bucket: 'needs_review', target: null,
    candidates: [target, { ...target, contract_id: 46, selectable: false }] };
  const skipped = { ...row, notice_id: 3, bucket: 'skipped', target: null, reason: '已有合同关联' };
  const preview = readMatchPreview({ ok: true, rows: [review, skipped, row] }, [1, 2, 3]);
  assert.deepEqual(preview.groups.auto_ready, [row]);
  assert.equal(preview.groups.needs_review[0].candidates[0].invoice_side, 'trade');
  assert.equal(preview.groups.skipped[0].reason, '已有合同关联');
  assert.deepEqual(readyLinkSelections(preview.groups.auto_ready), [{
    notice_id: 1, contract_id: 45, expected_amount: '15.00', expected_jc_supplier: '供应商甲',
    expected_warehouse_key: '甲仓库', expected_contract_supplier: '供应商甲',
  }]);
  assert.deepEqual(reviewLinkSelections(preview.groups.needs_review, new Map([[2, 46]])), []);
  assert.equal(reviewLinkSelections(preview.groups.needs_review, new Map([[2, 45]]))[0].notice_id, 2);
  assert.throws(() => readMatchPreview({ ok: true, rows: [row, row, skipped] }, [1, 2, 3]), /不一致/);
});
