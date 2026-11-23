import assert from 'node:assert/strict';
import test from 'node:test';
import { searchWithinRows } from '../../src/grid-search.ts';

test('substring search narrows only within the current rows and searchable labels', () => {
  const rows = ['N-10', 'N-11', 'N-20'].map((bill, id) => ({id, bill}));
  const visited = [];
  const matcher = labels => searchWithinRows(rows, (row, needle) => {
    visited.push(row.id);
    return row.bill.includes(needle) || labels[row.id].includes(needle);
  });
  const find = matcher(['甲', '乙', '丙']);
  assert.equal(find('N-'), rows);
  assert.deepEqual(find('1'), rows.slice(0, 2));
  visited.length = 0;
  assert.deepEqual(find('N-11'), [rows[1]]);
  assert.deepEqual(visited, [0, 1]);
  assert.deepEqual(find('N-12'), []);
  assert.deepEqual(find('N-20'), [rows[2]]);
  assert.equal(find(''), rows);

  assert.deepEqual(find('新名'), []);
  const renamed = matcher(['甲', '乙', '新名']);
  assert.deepEqual(renamed('新名'), [rows[2]]);
  const replaced = [{id: 2, bill: 'N-30'}];
  assert.equal(searchWithinRows(replaced, (row, needle) => row.bill.includes(needle))('N-30'), replaced);
});
