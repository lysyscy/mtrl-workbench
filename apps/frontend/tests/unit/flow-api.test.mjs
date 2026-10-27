import test from 'node:test';
import assert from 'node:assert/strict';
import { loadFlows } from '../../src/flow-api.ts';
import { ApiError, cents, money } from '../../src/api.ts';

const base = {
  id: 1, notice_id: 2, project_id: 3, flow_no: '', doc_no: '', doc_date: '', bill_name: '',
  project_key: '', project_display: '', payee: '', category_label: '', amount_approved: '100.00',
  pay_date: '2026-10-28', amount: '12.34', pay_method: '现汇', remark: '', created_by: '',
  status: 'effective', status_label: '生效', revoke_reason: '',
};
async function load(payload) {
  const previous = globalThis.fetch;
  globalThis.fetch = async (path, init) => {
    assert.equal(path, '/api/m05/flows?year_month=');
    assert.ok(init.signal instanceof AbortSignal);
    return { status: 200, ok: true, json: async () => payload };
  };
  try { return await loadFlows(); }
  finally { globalThis.fetch = previous; }
}

test('known bad flow facts fail in reader before date/amount/status consumers', async () => {
  for (const patch of [{ pay_date: undefined }, { amount_approved: 'bad' }, { status: undefined }]) {
    await assert.rejects(load({ rows: [{ ...base, ...patch }] }), error => error instanceof ApiError && /读取不完整/.test(error.message));
  }
});

test('schema validates every claimed field, IDs, row objects and envelope', async () => {
  for (const field of Object.keys(base)) {
    const row = { ...base }; delete row[field];
    await assert.rejects(load({ rows: [row] }), ApiError, field);
  }
  for (const id of [0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, NaN, '1']) {
    await assert.rejects(load({ rows: [{ ...base, id }] }), ApiError);
  }
  for (const patch of [{ notice_id: '2' }, { project_id: 0 }, { status: 'unknown' }, { amount: 12.34 }]) {
    await assert.rejects(load({ rows: [{ ...base, ...patch }] }), ApiError);
  }
  for (const payload of [null, {}, { rows: null }, { rows: [null] }, { rows: [Object.assign([], base)] }, Object.assign([], { rows: [base] })]) {
    await assert.rejects(load(payload), ApiError);
  }
});

test('existing money rules stay exact and reject malformed approval amount at read boundary', async () => {
  for (const value of ['', '1,234.00', '1.234', '+1', '.1']) {
    await assert.rejects(load({ rows: [{ ...base, amount: value }] }), /金额读取不完整/);
    await assert.rejects(load({ rows: [{ ...base, amount_approved: value }] }), /金额读取不完整/);
  }
  const [row] = await load({ rows: [{ ...base, amount: '-0.01', amount_approved: '0.00' }] });
  assert.equal(money(row.amount), '-0.01'); assert.equal(row.amount_approved, '0.00');
});

test('normal effective/revoked/orphan history keeps values, identity, extras and effective totals', async () => {
  const first = { ...base, extra: { retained: true } };
  const second = { ...base, id: 2, notice_id: null, project_id: null, amount_approved: null,
    amount: '0.00', pay_date: '', pay_method: '', created_by: '', status: 'revoked', status_label: '已撤销', revoke_reason: '合成原因' };
  const payload = { rows: [first, second], extra: 'envelope metadata' };
  const rows = await load(payload);
  assert.notEqual(rows, payload.rows);
  assert.equal(rows[0], first); assert.equal(rows[1], second); assert.equal(rows[0].extra, first.extra);
  assert.equal(rows.filter(row => row.status === 'effective').reduce((total, row) => total + cents(row.amount), 0n), 1234n);
  assert.equal(rows[1].amount_approved, null); assert.equal(rows[1].pay_date, '');
  assert.deepEqual(await load({ rows: [] }), []);
});
