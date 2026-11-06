import test, { beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { ContractSubtableWorkspace } from '../../src/contract-subtable-workspace.ts';
import { readSubtableSnapshot, writeSubtableSnapshot } from '../../src/contract-subtable-recovery.ts';

class MemoryStorage {
  data = new Map();
  getItem(key) { return this.data.get(key) ?? null; }
  setItem(key, value) { this.data.set(key, value); }
  removeItem(key) { this.data.delete(key); }
}
beforeEach(() => { globalThis.sessionStorage = new MemoryStorage(); });
afterEach(() => { delete globalThis.sessionStorage; });
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const setup = (overrides = {}, account = 7) => new ContractSubtableWorkspace(account, {
  allowed: () => true, write: async () => 12, lookup: async () => ({ status: 'not_found' }),
  refresh: async () => {}, reference: async () => {}, announce: () => {}, ...overrides,
});
const operation = (kind, requestId) => ({ kind, requestId, action: 'add', date: '2026-10-01', amount: '1.25', rowId: null, at: 1 });
function seed(operations) { writeSubtableSnapshot({ version: 1, accountId: 7, contractId: 42, operations, drafts: {} }); }

test('explicit discard persists before a view closes and cannot resurrect on reload', async () => {
  const workspace = setup(); await workspace.activate(42, '');
  workspace.edit(42, 'payment', 'amount', '1.25');
  assert.equal(readSubtableSnapshot(7, 42).drafts.payment.amount, '1.25');
  workspace.discard(42, 'payment'); workspace.dispose();
  const reopened = setup(); await reopened.activate(42, '');
  assert.equal(reopened.view(42).drafts.payment.amount, '');
  assert.equal(reopened.summary.dirty, false);
});

test('unknown write, edited next draft, reload and retry retain the original operation identity', async () => {
  const writes = [];
  const first = setup({ write: async (id, submitted) => {
    assert.deepEqual(readSubtableSnapshot(7, id).operations.payment, submitted);
    writes.push(submitted); throw new TypeError('reply lost');
  } });
  await first.activate(42, ''); first.edit(42, 'payment', 'amount', '1.25');
  await first.submit(42, 'payment');
  assert.deepEqual(first.view(42).retry, ['payment']);
  first.edit(42, 'payment', 'amount', '9.50'); first.dispose();
  const lookups = [];
  const reopened = setup({ lookup: async id => { lookups.push(id); return { status: 'not_found' }; },
    write: async (_, submitted) => { writes.push(submitted); return 12; } });
  await reopened.activate(42, '');
  assert.deepEqual(lookups, [writes[0].requestId]); assert.equal(writes.length, 1);
  await reopened.submit(42, 'payment');
  assert.deepEqual(writes[1], writes[0]);
  assert.equal(reopened.view(42).drafts.payment.amount, '9.50');
  assert.equal(readSubtableSnapshot(7, 42).operations.payment, undefined);
});

test('one recovered side cannot unlock another unresolved side; duplicate activation shares lookups', async () => {
  seed({ supplier: operation('supplier', 'first'), trade: operation('trade', 'second') });
  const first = deferred(), second = deferred(), queried = [];
  const workspace = setup({ lookup: id => { queried.push(id); return id === 'first' ? first.promise : second.promise; } });
  const a = workspace.activate(42, ''), b = workspace.activate(42, '');
  assert.equal(a, b);
  assert.match(workspace.view(42).feedback, /正在核对/);
  await Promise.resolve(); first.resolve({ status: 'completed', result: { id: 12 } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(workspace.summary.uncertain, true);
  assert.deepEqual(queried, ['first', 'second']);
  second.resolve({ status: 'not_found' }); await a;
  assert.equal(workspace.summary.uncertain, false);
  assert.deepEqual(workspace.view(42).retry, ['trade']);
});

test('the synchronous owner lock prevents double submission and old account results cannot retire persistence', async () => {
  const response = deferred(); let writes = 0;
  const workspace = setup({ write: () => { writes++; return response.promise; } });
  await workspace.activate(42, ''); workspace.edit(42, 'supplier', 'amount', '3.00');
  const pending = workspace.submit(42, 'supplier');
  await workspace.submit(42, 'supplier'); assert.equal(writes, 1);
  workspace.dispose();
  const other = setup({}, 8); await other.activate(42, '');
  response.resolve(12); await pending;
  assert.equal(other.view(42).dirty, false);
  assert.ok(readSubtableSnapshot(7, 42).operations.supplier);
});

test('confirmation of a subtable operation does not clear an unrelated payment-reference unknown result', async () => {
  seed({ payment: operation('payment', 'pending') });
  let completed = false;
  const workspace = setup({ lookup: async () => completed ? { status: 'completed', result: {} } : { status: 'not_found' },
    reference: async () => { throw new TypeError('unknown link'); } });
  await workspace.activate(42, '');
  assert.equal(await workspace.reference(42, 5), 'unknown');
  completed = true; await workspace.activate(42, '');
  assert.equal(workspace.summary.uncertain, true);
  assert.equal(readSubtableSnapshot(7, 42), null);
  assert.match(workspace.view(42).error, /关联结果待确认/);
});

for (const next of ['completed', 'not_found']) test(`a failed side keeps its recovery guidance after another side is ${next}`, async () => {
  seed({ supplier: operation('supplier', 'first'), trade: operation('trade', 'second') });
  const workspace = setup({ lookup: async id => {
    if (id === 'first') throw new TypeError('lookup failed');
    return next === 'completed' ? { status: 'completed', result: {} } : { status: 'not_found' };
  } });
  await workspace.activate(42, '');
  assert.equal(workspace.summary.uncertain, true);
  assert.match(workspace.view(42).error, /供应商发票.*请刷新页面后重试核对/);
  assert.equal(workspace.view(42).feedback, '');
});
