import test from 'node:test';
import assert from 'node:assert/strict';
import { readInventory } from '../../src/inventory-api.ts';
import { ApiError } from '../../src/api.ts';

const values = {qty:'1.00',price_excl:'2.00',price_incl:'2.00',amount:'2.00',tax_total:'2.00',material_property:'主材'};
const row = (id, adjusted = false) => ({
  id, ym:'2026-08', direction:'入库', project_full_name:'甲项目', adjusted, edit_token:'tok',
  doc_no:'D', seq:'1', material:'水泥', material_property:'主材', spec:'', unit:'吨', qty:'1.00',
  price_excl:'2.00', price_incl:'2.00', amount:'2.00', adj_amount: null, tax_total:'2.00',
  biz_type:'采购', vendor:'甲', doc_date:'2026-08-01', warehouse:'甲库', wbs_name:'', cbs_name:'',
  original_values: values,
});
const adjustment = (id, rowId) => ({
  id, row_id: rowId, before_amount:'2.00', amount:'3.00', remark:'', operator:'甲',
  changed_at:'2026-08-02', values:{amount:'3.00'}, before_values:null,
});
const payload = rows => ({ rows, adjustments: [], projects:['甲项目'], material_properties:['主材'] });

test('inventory row adjustment correspondence keeps the strict both-ways rule', () => {
  // A row claiming an adjustment that is absent stays rejected.
  assert.throws(() => readInventory(payload([row(1, true)])), error => error instanceof ApiError && /库存读取不完整/.test(error.message));
  // An adjustment whose row claims no adjustment stays rejected.
  assert.throws(() => readInventory({ ...payload([row(1)]), adjustments:[adjustment(1, 1)] }), /库存读取不完整/);
  // The matched pair is accepted and reports both sides.
  const data = readInventory({ ...payload([row(1, true), row(2)]), adjustments:[adjustment(1, 1)] });
  assert.equal(data.rows.length, 2);
  assert.equal(data.adjustments.length, 1);
  assert.equal(data.rows[0].adjusted, true);
});

test('dangling adjustments without a matching row stay accepted, not a new error', () => {
  const data = readInventory({ ...payload([row(1)]), adjustments:[adjustment(7, 999)] });
  assert.equal(data.adjustments.length, 1);
  assert.equal(data.adjustments[0].row_id, 999);
});

test('duplicate row ids and duplicate adjustment row ids stay rejected', () => {
  assert.throws(() => readInventory(payload([row(1), row(1)])), /库存读取不完整/);
  assert.throws(() => readInventory({ ...payload([row(1, true)]), adjustments:[adjustment(1, 1), adjustment(2, 1)] }), /库存读取不完整/);
});

test('amount and id validation still runs before the correspondence check', () => {
  assert.throws(() => readInventory({ ...payload([row(1)]), adjustments:[{ ...adjustment(1, 1), amount:'abc' }] }), /金额读取不完整/);
  assert.throws(() => readInventory({ ...payload([{ ...row(1), id:1.5 }]), adjustments:[] }), /库存读取不完整/);
});
