import test from 'node:test';
import assert from 'node:assert/strict';
import { currentMonth, timeRange, timeMatches } from '../../src/business-time.ts';
import { coarseRows } from '../../src/inventory-api.ts';

test('periods retain UTC closed boundaries', () => {
  for (const [period, from, to] of [
    ['2024-02', '2024-02-01', '2024-02-29'],
    ['2025-02~2025-03', '2025-02-01', '2025-03-31'],
    ['2025', '2025-01-01', '2025-12-31'],
    ['2024Q1', '2024-01-01', '2024-03-31'],
    ['2024-12-30', '2024-12-30', '2025-01-05'],
  ]) {
    assert.deepEqual(timeRange(period), { dateFrom: from, dateTo: to });
    assert.equal(timeMatches(period, from), true);
    assert.equal(timeMatches(period, `${to}T23:59:59`), true);
  }
  assert.equal(timeMatches('2024-02', '2024-03-01'), false);
  assert.deepEqual(timeRange('全部'), { dateFrom: '', dateTo: '' });
  assert.equal(timeMatches('', ''), true);
  for (const value of ['2025-12~2026-01', '2025-03~2025-02', '2025Q5', '2025-02-30', '2025-01-07']) {
    assert.throws(() => timeRange(value), RangeError);
  }
});

test('current month uses Beijing time', () => {
  assert.equal(currentMonth(new Date('2025-01-31T16:00:00Z')), '2025-02');
  assert.equal(currentMonth(new Date('2025-01-31T15:59:59Z')), '2025-01');
});

test('inventory periods match the first day of the inventory month', () => {
  const rows = [{ ym: '2024-12', warehouse: '甲', direction: '入库', adjusted: false }, { ym: '2025-01', warehouse: '甲', direction: '入库', adjusted: false }];
  assert.deepEqual(coarseRows(rows, '2024-12-30', [], '全部', false), [rows[1]]);
});
