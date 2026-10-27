import test from 'node:test';
import assert from 'node:assert/strict';
import { readContracts, readContractDetail, contractFields } from '../../src/contracts-api.ts';

const base = {
  id: 1, project_seq: null, contract_no: '', date: '', material: '物料', supplier: '供应商',
  contract_amt: '12.34', inv_sum: '0', trade_co: null, trade_contract_amt: null, trade_inv_sum: '0.00',
  settle: '12.34', pay_sum: '0.00', debt: '12.34', payment_term: '', payment_method: '', remark: '',
  tag: '', arch: '', arch_no: '', ret_date: '',
};
const list = row => ({ rows: [row], columns: [{ key: 'material', label: '物料', type: 'text' }], tags: [], payment_methods: [] });
const row = () => ({ ...base, project_key: '项目', notice_ids: [1] });
const detail = () => ({ data: { ...base, supplier_invoices: [{ id: 2, kind: 'supplier', date: '', amount: '12.34' }], trade_invoices: [] } });

test('list and detail keep their actual distinct contracts and extra input fields', () => {
  const input = row(); const extra = {}; input.extra = extra;
  const envelope = list(input); envelope.columns[0].extra = extra;
  const result = readContracts(envelope);
  assert.equal(result.rows[0], input);
  assert.equal(result.rows[0].extra, extra);
  assert.equal(result.columns, envelope.columns);
  assert.equal(result.columns[0].extra, extra);
  const data = detail(); data.data.payments = [extra];
  const parsed = readContractDetail(data);
  assert.equal(parsed.payments, data.data.payments);
  assert.equal(parsed.supplier_invoices, data.data.supplier_invoices);
  assert.equal('project_key' in parsed, false);
  assert.equal('notice_ids' in parsed, false);
  assert.equal(contractFields(parsed).material_name, '物料');
  const missing = row(); delete missing.project_key;
  assert.throws(() => readContracts(list(missing)), /合同归属或关联读取不完整/);
  const missingIds = row(); delete missingIds.notice_ids;
  assert.throws(() => readContracts(list(missingIds)), /合同归属或关联读取不完整/);
});

test('ret_date null normalization clones only the row and leaves raw input unchanged', () => {
  const input = row(); input.ret_date = null;
  const parsed = readContracts(list(input)).rows[0];
  assert.notEqual(parsed, input); assert.equal(parsed.ret_date, ''); assert.equal(input.ret_date, null);
  const data = detail(); data.data.ret_date = null;
  assert.equal(readContractDetail(data).ret_date, ''); assert.equal(data.data.ret_date, null);
});

test('missing fields, invalid IDs and money remain rejected with existing error categories', () => {
  for (const field of Object.keys(base)) {
    const input = row(); delete input[field];
    assert.throws(() => readContracts(list(input)), /合同读取不完整/, field);
  }
  for (const id of [0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, NaN, '1']) {
    assert.throws(() => readContracts(list({ ...row(), id })), /合同读取不完整/);
    assert.throws(() => readContracts(list({ ...row(), notice_ids: [id] })), /合同归属或关联读取不完整/);
  }
  for (const value of [12.34, '', '1,234.00', '1.234', null]) {
    assert.throws(() => readContracts(list({ ...row(), contract_amt: value })), /合同读取不完整/);
  }
  assert.equal(readContracts(list({ ...row(), contract_amt: '-0.01', trade_contract_amt: null })).rows[0].contract_amt, '-0.01');
  assert.throws(() => readContracts({ rows: [], columns: [], tags: null, payment_methods: [] }), /合同列表读取不完整/);
});

test('array objects and malformed invoice arrays cannot pass object/shape guards', () => {
  assert.throws(() => readContracts(list(Object.assign([], row()))), /合同读取不完整/);
  assert.throws(() => readContracts(Object.assign([], list(row()))), /合同列表读取不完整/);
  for (const value of [null, {}, [null], [{ id: 1, kind: 'supplier', date: '', amount: 1 }], [Object.assign([], { id: 1, kind: '', date: '', amount: '0' })]]) {
    const data = detail(); data.data.supplier_invoices = value;
    assert.throws(() => readContractDetail(data), /合同发票依据读取不完整/);
  }
  const data = detail(); delete data.data.trade_invoices;
  assert.throws(() => readContractDetail(data), /合同发票依据读取不完整/);
  assert.throws(() => readContractDetail({ data: [] }), /合同详情读取不完整/);
});
