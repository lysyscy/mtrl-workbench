import test, { beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  clearSubtableSnapshot,
  emptySubtableSnapshot,
  newSubtableRequestId,
  readSubtableSnapshot,
  snapshotIsEmpty,
  subtableStorageAvailable,
  writeSubtableSnapshot,
} from '../../src/contract-subtable-recovery.ts';

// Node has no sessionStorage: inject a real in-memory Storage so the module's
// call-time lookup of globalThis.sessionStorage is exercised end to end.
class MemoryStorage {
  #m = new Map();
  getItem(key) { return this.#m.has(key) ? this.#m.get(key) : null; }
  setItem(key, value) { this.#m.set(String(key), String(value)); }
  removeItem(key) { this.#m.delete(key); }
  clear() { this.#m.clear(); }
  get length() { return this.#m.size; }
  key(index) { return [...this.#m.keys()][index] ?? null; }
}

const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const draft = (date = '2026-01-05', amount = '', initialDate = date) => ({ date, amount, initialDate });
const operation = overrides => ({
  requestId: '11111111-1111-4111-8111-111111111111',
  kind: 'supplier',
  action: 'add',
  date: '2026-01-05',
  amount: '100.00',
  rowId: null,
  at: 1_700_000_000_000,
  ...overrides,
});
const key = (accountId, contractId) => `m11-subtable:${accountId}:${contractId}`;

beforeEach(() => { globalThis.sessionStorage = new MemoryStorage(); });
afterEach(() => { delete globalThis.sessionStorage; });

test('写入后能读回，operations 与 drafts 内容一致', () => {
  const snapshot = emptySubtableSnapshot(7, 42);
  snapshot.operations.supplier = operation();
  snapshot.drafts.trade = draft('2026-02-01', '12.34', '2026-01-01');
  assert.equal(writeSubtableSnapshot(snapshot), true);
  const read = readSubtableSnapshot(7, 42);
  assert.notEqual(read, null);
  assert.equal(read.version, 1);
  assert.equal(read.accountId, 7);
  assert.equal(read.contractId, 42);
  assert.deepEqual(read.operations.supplier, snapshot.operations.supplier);
  assert.deepEqual(read.drafts.trade, snapshot.drafts.trade);
  assert.equal(read.operations.trade, undefined);
  assert.equal(read.drafts.supplier, undefined);
});

test('账号隔离：账号 2 读同一合同返回 null，账号 1 仍可读', () => {
  const snapshot = emptySubtableSnapshot(1, 99);
  snapshot.drafts.supplier = draft();
  assert.equal(writeSubtableSnapshot(snapshot), true);
  assert.equal(readSubtableSnapshot(2, 99), null);
  assert.notEqual(readSubtableSnapshot(1, 99), null);
});

test('合同隔离：同账号不同合同互不可见', () => {
  const snapshot = emptySubtableSnapshot(1, 100);
  snapshot.drafts.payment = draft('2026-03-03', '9.99', '2026-03-01');
  assert.equal(writeSubtableSnapshot(snapshot), true);
  assert.equal(readSubtableSnapshot(1, 101), null);
  assert.deepEqual(readSubtableSnapshot(1, 100).drafts.payment, snapshot.drafts.payment);
});

test('换号后写别人的数据不会污染：两个账号各自快照互不覆盖', () => {
  const mine = emptySubtableSnapshot(1, 5);
  mine.drafts.supplier = draft('2026-04-04', '10.00', '2026-04-01');
  assert.equal(writeSubtableSnapshot(mine), true);
  const theirs = emptySubtableSnapshot(2, 5);
  theirs.operations.payment = operation({ requestId: '22222222-2222-4222-8222-222222222222', kind: 'payment', action: 'del', date: '', amount: '', rowId: 8 });
  assert.equal(writeSubtableSnapshot(theirs), true);
  const readMine = readSubtableSnapshot(1, 5);
  assert.deepEqual(readMine.drafts.supplier, mine.drafts.supplier);
  assert.equal(readMine.operations.payment, undefined);
  assert.deepEqual(readSubtableSnapshot(2, 5).operations.payment, theirs.operations.payment);
});

test('version 不符的手工数据返回 null', () => {
  globalThis.sessionStorage.setItem(key(1, 1), JSON.stringify({ version: 2, accountId: 1, contractId: 1, operations: {}, drafts: {} }));
  assert.equal(readSubtableSnapshot(1, 1), null);
});

test('JSON 损坏返回 null 且不抛，原内容不被删除', () => {
  globalThis.sessionStorage.setItem(key(1, 2), '{');
  assert.doesNotThrow(() => readSubtableSnapshot(1, 2));
  assert.equal(readSubtableSnapshot(1, 2), null);
  assert.equal(globalThis.sessionStorage.getItem(key(1, 2)), '{');
});

test('operation 字段类型错误时只丢弃该条，drafts 仍可读', () => {
  globalThis.sessionStorage.setItem(key(3, 3), JSON.stringify({
    version: 1,
    accountId: 3,
    contractId: 3,
    operations: {
      supplier: operation({ requestId: 123 }),
      trade: operation({ requestId: '33333333-3333-4333-8333-333333333333', kind: 'trade' }),
    },
    drafts: { payment: draft('2026-05-05', '1.00', '2026-05-01') },
  }));
  const read = readSubtableSnapshot(3, 3);
  assert.notEqual(read, null);
  assert.equal(read.operations.supplier, undefined);
  assert.deepEqual(read.operations.trade, operation({ requestId: '33333333-3333-4333-8333-333333333333', kind: 'trade' }));
  assert.deepEqual(read.drafts.payment, draft('2026-05-05', '1.00', '2026-05-01'));
});

test('sessionStorage 完全不可用时三个接口都安全降级且不抛', () => {
  globalThis.sessionStorage = undefined;
  assert.equal(subtableStorageAvailable(), false);
  assert.doesNotThrow(() => readSubtableSnapshot(1, 1));
  assert.equal(readSubtableSnapshot(1, 1), null);
  assert.doesNotThrow(() => writeSubtableSnapshot(emptySubtableSnapshot(1, 1)));
  assert.equal(writeSubtableSnapshot(emptySubtableSnapshot(1, 1)), false);
  assert.doesNotThrow(() => clearSubtableSnapshot(1, 1));
});

test('setItem 抛 QuotaExceededError 时写入返回 false 且不抛', () => {
  const storage = globalThis.sessionStorage;
  storage.setItem = () => { const error = new Error('quota'); error.name = 'QuotaExceededError'; throw error; };
  assert.doesNotThrow(() => writeSubtableSnapshot(emptySubtableSnapshot(1, 1)));
  assert.equal(writeSubtableSnapshot(emptySubtableSnapshot(1, 1)), false);
});

test('snapshotIsEmpty 依 dirty 草稿与进行中操作判定', () => {
  const empty = emptySubtableSnapshot(1, 1);
  assert.equal(snapshotIsEmpty(empty), true);
  const unchanged = emptySubtableSnapshot(1, 1);
  unchanged.drafts.supplier = draft('2026-06-06', '', '2026-06-06');
  assert.equal(snapshotIsEmpty(unchanged), true);
  const withAmount = emptySubtableSnapshot(1, 1);
  withAmount.drafts.supplier = draft('2026-06-06', '1', '2026-06-06');
  assert.equal(snapshotIsEmpty(withAmount), false);
  const withDate = emptySubtableSnapshot(1, 1);
  withDate.drafts.trade = draft('2026-06-07', '', '2026-06-06');
  assert.equal(snapshotIsEmpty(withDate), false);
  const busy = emptySubtableSnapshot(1, 1);
  busy.operations.supplier = operation();
  assert.equal(snapshotIsEmpty(busy), false);
});

test('newSubtableRequestId 生成互不相同的 UUID v4', () => {
  const first = newSubtableRequestId();
  const second = newSubtableRequestId();
  assert.equal(typeof first, 'string');
  assert.notEqual(first, '');
  assert.notEqual(first, second);
  assert.match(first, uuidV4);
  assert.match(second, uuidV4);
});

test('稳定复用：读回的 operations.supplier.requestId 与写入的完全相同', () => {
  const written = newSubtableRequestId();
  const snapshot = emptySubtableSnapshot(4, 4);
  snapshot.operations.supplier = operation({ requestId: written });
  assert.equal(writeSubtableSnapshot(snapshot), true);
  assert.equal(readSubtableSnapshot(4, 4).operations.supplier.requestId, written);
  // 恢复流程再来一次读取，ID 不变（模块只负责原样读回）。
  assert.equal(readSubtableSnapshot(4, 4).operations.supplier.requestId, written);
});

test('storage 可用时探测后不留残值，clearSubtableSnapshot 只清本账号合同', () => {
  assert.equal(subtableStorageAvailable(), true);
  assert.equal(globalThis.sessionStorage.getItem('m11-subtable:probe'), null);
  const mine = emptySubtableSnapshot(1, 1);
  mine.drafts.supplier = draft();
  const theirs = emptySubtableSnapshot(2, 1);
  theirs.drafts.supplier = draft();
  assert.equal(writeSubtableSnapshot(mine), true);
  assert.equal(writeSubtableSnapshot(theirs), true);
  clearSubtableSnapshot(1, 1);
  assert.equal(readSubtableSnapshot(1, 1), null);
  assert.notEqual(readSubtableSnapshot(2, 1), null);
});
