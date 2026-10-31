import assert from 'node:assert/strict';
import test from 'node:test';
import { replaceOilCard } from '../../src/oilcard-api.ts';
import { correctOilAttribution } from '../../src/oilcard-ledger-api.ts';
import { CellSaveQueue } from '../../src/cell-save.ts';

const uuid = n => `${n}0000000-0000-4000-8000-000000000000`;
const account = { id: 1, request_id: uuid(1), version: uuid(2), name: '账户', project_id: 11, card_id: 21, status: 'archived', remark: '账户备注' };
const changed = { ...account, version: uuid(3), card_id: 22 };
const fields = { request_id: uuid(4), card_id: 22, new_card: null };
const assignment = { id: 51, request_id: fields.request_id, account_id: 1, project_id: 11, card_id: 22, previous_card_id: 21, change_kind: 'replacement', changed_by: '测试', changed_at: '2026-10-31T12:00:00' };
const entry = { id: 31, request_id: uuid(5), version: uuid(6), kind: 'recharge', project_id: 11, account_id: 1, card_id: 21, date_text: '原始数据', entry_date: null, amount: '1000.00', remark: '账务备注', related_entry_id: null, transfer_id: null };

test('replacement receipt checks old and new identities and preserves independent account fields', async () => {
  const originalFetch = globalThis.fetch;
  let reply = { ok: true, item: changed, assignment };
  globalThis.fetch = async () => new Response(JSON.stringify(reply), { status: 200 });
  try {
    assert.deepEqual(await replaceOilCard(fields, account, new AbortController().signal), changed);
    for (const invalid of [{ ...assignment, previous_card_id: 99 }, { ...assignment, request_id: uuid(9) }, { ...assignment, change_kind: 'assignment' }]) {
      reply = { ok: true, item: changed, assignment: invalid };
      await assert.rejects(replaceOilCard(fields, account, new AbortController().signal));
    }
    reply = { ok: true, item: { ...changed, remark: '串了新卡备注' }, assignment };
    await assert.rejects(replaceOilCard(fields, account, new AbortController().signal));
  } finally { globalThis.fetch = originalFetch; }
});

test('a historical correction cannot silently change money or notes; uncertain receipt keeps the save lock', async () => {
  const originalFetch = globalThis.fetch, fields = { project_id: 12, account_id: 2, card_id: null };
  let actual = { ...entry, ...fields, version: uuid(7) }, writes = 0;
  globalThis.fetch = async () => { writes++; return new Response(JSON.stringify({ ok: true, item: actual }), { status: 200 }); };
  const options = { enabled: true, read: async () => actual, write: async () => {}, acknowledge: () => undefined, saved: () => '' };
  const queue = new CellSaveQueue(() => options);
  try {
    assert.deepEqual(await correctOilAttribution(fields, entry, new AbortController().signal), actual);
    actual = { ...actual, amount: '2000.00' };
    assert.equal(await queue.run(signal => correctOilAttribution(fields, entry, signal), () => ''), 'uncertain');
    assert.equal(await queue.run(async () => { writes++; }, () => ''), 'blocked');
    await queue.reread();
    assert.equal(queue.getSnapshot().uncertain, true);
    queue.confirm();
    assert.equal(queue.getSnapshot().uncertain, false);
    assert.equal(writes, 2);
  } finally { queue.dispose(); globalThis.fetch = originalFetch; }
});
