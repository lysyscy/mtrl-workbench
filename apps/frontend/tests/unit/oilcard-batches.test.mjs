import test from 'node:test';
import assert from 'node:assert/strict';
import { createDeliveryBatch, findDeliveryBatch, readDeliveryBatch, runDeliveryItem } from '../../src/oilcard-batch-api.ts';
import { uncertainWrite } from '../../src/api.ts';

const requestId = '00000000-0000-4000-8000-000000000001';
const item = { id: 1, position: 1, status: 'pending', message: '请确认归属', invoice_id: 1, original_id: 2, can_run: false };
const batch = { id: 1, request_id: requestId, created_at: '2026-10-31T12:00:00', items: [item] };

test('批次各项保持身份和处理状态，不能把不完整结果当作成功', () => {
  assert.equal(readDeliveryBatch(batch).items[0].status, 'pending');
  for (const invalid of [{ ...batch, items: [] }, { ...batch, items: [{ ...item, invoice_id: null }] }, { ...batch, items: [{ ...item, can_run: true }] }, { ...batch, items: [item, item] }]) assert.throws(() => readDeliveryBatch(invalid));
});

test('未知建立结果凭request_id读回，明确未建立和无效回执分开', async () => {
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ found: false, batch: null }));
    assert.equal(await findDeliveryBatch(requestId), null);
    globalThis.fetch = async () => new Response(JSON.stringify({ found: false }));
    await assert.rejects(findDeliveryBatch(requestId));
    globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, batch: { ...batch, request_id: '00000000-0000-4000-8000-000000000002' } }));
    await assert.rejects(createDeliveryBatch(requestId, 'synthetic', new AbortController().signal), error => uncertainWrite(error));
  } finally { globalThis.fetch = previous; }
});

test('续办回执必须包含同一批次和当前条目，否则保持待核实', async () => {
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, batch }));
    await runDeliveryItem(1, 1, new AbortController().signal);
    await assert.rejects(runDeliveryItem(2, 1, new AbortController().signal), error => uncertainWrite(error));
    await assert.rejects(runDeliveryItem(1, 9, new AbortController().signal), error => uncertainWrite(error));
  } finally { globalThis.fetch = previous; }
});
