import test from 'node:test';
import assert from 'node:assert/strict';
import { matchNoticeCodes, noticePrintRows, prioritizeNoticeRows } from '../../src/notices-api.ts';

const row = (id, code, extra = {}) => ({notice_id: id, bill_no: code, is_excluded: false, is_revoked: false, pay_status: '未付清', ...extra});
const idsOf = rows => rows.map(row => row.notice_id);
const gridWithOrder = rows => ({
  forEachNodeAfterFilterAndSort(visit) { rows.forEach((data, index) => visit({data}, index)); },
});

test('notice_code_exception_algorithm_without_browser', async () => {
  const rows=[row(1,'FKTZS2026100001'),row(2,'FKTZS2026100002',{pay_status:'已付清'}),row(3,'FKTZS2026100003'),row(8,'FKTZS2026100003'),row(4,'FKTZS2026100004',{is_excluded:true}),row(5,'FKTZS2026100005',{is_revoked:true})];
  const result=matchNoticeCodes('"fktzs2026100002" FKTZS2026100001 FKTZS2026100001,FKTZS2026100003；FKTZS2026100004\tFKTZS2026100005 QTZC2026100001 FKTZS2026130001 FKTZS2026109999 名称FKTZS2026100006',rows);
  assert.deepEqual([...result.ids],[2,1]);
  assert.deepEqual([...result.paid],['FKTZS2026100002']);
  assert.deepEqual([...result.duplicates],['FKTZS2026100001（2次）']);
  assert.deepEqual([...result.ambiguous],['FKTZS2026100003（系统2条）']);
  assert.deepEqual(result.blocked.map(row=>row.notice_id),[4,5]);
  assert.deepEqual([...result.missing],['FKTZS2026109999']);
  assert.deepEqual([...result.invalid],['QTZC2026100001','FKTZS2026130001','名称FKTZS2026100006']);
  console.log('Pure notice-code exception cases passed; no browser or HTTP listener');
});

test('pasted notice numbers determine the grid prefix and the print scope order', () => {
  const rows = [1, 2, 3, 4, 5].map(id => row(id, `FKTZS202610000${id}`));
  const pasteOrder = new Set(matchNoticeCodes('FKTZS2026100003 FKTZS2026100001 FKTZS2026100003', rows).ids);
  const nodes = [rows[4], rows[0], rows[1], rows[2], rows[3]].map(data => ({data}));

  prioritizeNoticeRows(nodes, pasteOrder, node => node.data?.notice_id);

  const displayed = nodes.map(node => node.data);
  assert.deepEqual(idsOf(displayed), [3, 1, 5, 2, 4]);
  const selected = rows.filter(row => pasteOrder.has(row.notice_id));
  assert.deepEqual(idsOf(noticePrintRows(selected, pasteOrder, gridWithOrder(displayed))), [3, 1]);
});

test('manually selected notices follow the current grid order', () => {
  const rows = [1, 2, 3, 4].map(id => row(id, `FKTZS202610000${id}`));
  const selected = [rows[0], rows[1], rows[3]];
  const grid = gridWithOrder([rows[3], rows[2], rows[1], rows[0]]);

  assert.deepEqual(idsOf(noticePrintRows(selected, new Set(), grid)), [4, 2, 1]);
  assert.deepEqual(idsOf(selected), [1, 2, 4]);
});

test('hidden pasted notices keep their position and other hidden notices follow source order', () => {
  const rows = [1, 2, 3, 4, 5, 6, 7].map(id => row(id, `FKTZS202610000${id}`));
  const selected = rows.filter(row => row.notice_id !== 5);
  const pasteOrder = new Set([5, 6, 2]);
  const grid = gridWithOrder([rows[1], rows[6], rows[3], rows[4]]);

  assert.deepEqual(idsOf(noticePrintRows(selected, pasteOrder, grid)), [6, 2, 7, 4, 1, 3]);
  assert.deepEqual(idsOf(noticePrintRows(selected, pasteOrder, null)), [6, 2, 1, 3, 4, 7]);
});
