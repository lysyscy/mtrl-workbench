import assert from 'node:assert/strict';
import test from 'node:test';
import { readReceipt, readReceiptRows } from '../../src/jc-fetch-receipt-data.ts';

const base = { id: 12, started_at: '2026-11-12T10:06:00', status: 'success', matched: 3 };

test('legacy receipts preserve the matched count and leave contract details unknown', () => {
  const receipt = readReceipt({ receipt: base });
  assert.equal(receipt.matched, 3);
  assert.equal(receipt.matchedItems, null);
  assert.equal(receipt.matchedItemsTotal, null);
});

test('matched details preserve change status, exact source money and explicit zero totals', () => {
  const receipt = readReceipt({ receipt: {
    ...base, matched_items_total: 3,
    matched_items: [
      { contract_no: 'A', material_name: '钢材', status: 'inserted', i8_amount: '9999999999999999.99' },
      { contract_no: 'B', status: 'updated', i8_amount: null },
      { contract_no: 'C', status: 'unchanged', i8_amount: '0.00' },
    ],
  } });
  assert.deepEqual(receipt.matchedItems.map(({ contract, status, amount }) => [contract, status, amount]), [
    ['A', 'inserted', '9,999,999,999,999,999.99'], ['B', 'updated', ''], ['C', 'unchanged', '0.00'],
  ]);
  assert.equal(receipt.matchedItems[0].material, '钢材');
  assert.equal(receipt.matchedItemsTotal, 3);
  const empty = readReceipt({ receipt: { ...base, matched: 0, matched_items: [], matched_items_total: 0 } });
  assert.deepEqual(empty.matchedItems, []);
  assert.equal(empty.matchedItemsTotal, 0);
});

test('pending contracts keep their identity when another contract disappears or ownership is re-evaluated', () => {
  const a = { contract_no: 'A', project_name: '甲项目', doc_name: '采购合同', kind: 'not_archived' };
  const b = { contract_no: 'B', project_name: '乙项目', doc_name: '材料合同', kind: 'not_archived' };
  const legacy = { bill_no: 'C', project_name: '丙项目', doc_name: '材料合同' };
  const unnumbered = { project_name: '丁项目', doc_name: '旧合同' };
  const before = readReceiptRows([a, b, legacy, unnumbered], false);
  const after = readReceiptRows([unnumbered, { ...b, kind: 'needs_keyword' }, legacy], false);
  assert.deepEqual(after.map(row => row.id), [before[3].id, before[1].id, before[2].id]);
  assert.equal(after.some(row => row.id === before[0].id), false);
  assert.equal(after[2].contract, 'C');
});

test('matched receipt row keys preserve repeated evidence and survive removal of an unrelated contract', () => {
  const a = { contract_no: 'A', status: 'inserted' };
  const b = { contract_no: 'B', bill_name: `钢材 & 五金 <"样品">'旧'`, status: 'updated' };
  const readIds = matched_items => readReceipt({ receipt: { ...base, matched_items } }).matchedItems.map(row => row.id);
  const ids = readIds([a, b, { ...b, status: 'unchanged' }, b]);
  assert.equal(new Set(ids).size, 4);
  assert.ok(ids.every(id => !/[&<>"']/.test(id)));
  assert.deepEqual(readIds([b, { ...b, status: 'unchanged' }, b]), ids.slice(1));
});
