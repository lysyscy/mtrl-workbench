import test from 'node:test';
import assert from 'node:assert/strict';
import { loadFlows, readDebt, readPaymentStats } from '../../src/flow-api.ts';
import { ApiError, cents, money } from '../../src/api.ts';

const base = {
  id: 1, notice_id: 2, project_id: 3, flow_no: '', doc_no: '', doc_date: '', bill_name: '',
  project_key: '', project_display: '', payee: '', category_label: '', amount_approved: '100.00',
  pay_date: '2026-10-28', amount: '12.34', pay_method: '现汇', remark: '', created_by: '',
  status: 'effective', status_label: '生效', revoke_reason: '',
};
const stats = () => ({granularity:'month',buckets:['2026-10'],right:['-0.01'],counts:[1],
  selected:{bucket:'2026-10',projects:[{key:'',label:'未判定',amount:'-0.01'}],total:'-0.01',count:1}});

test('statistics reject incomplete 200 facts instead of rendering missing money as zero', () => {
  for (const patch of [{right:[]},{right:[null]},{right:['bad']},{counts:[]},{selected:{}},
    {selected:{...stats().selected,projects:null}},{selected:{...stats().selected,total:null}},
    {buckets:['2026-13']},{selected:{...stats().selected,bucket:'bad'}}]) {
    assert.throws(()=>readPaymentStats({...stats(),...patch}),ApiError);
  }
  const weekly={...stats(),granularity:'week',buckets:['2026-12-28'],selected:{...stats().selected,bucket:'2026-12-28'}};
  assert.equal(readPaymentStats(weekly),weekly);
  assert.throws(()=>readPaymentStats({...weekly,buckets:['2026-12-29']}),ApiError);
});

test('statistics retain zero, negative, unassigned, extra fields and empty chart facts', () => {
  const value={...stats(),quarter:null,extra:{keep:true}};
  assert.equal(readPaymentStats(value),value);
  assert.equal(readPaymentStats(value).selected.projects[0].key,'');
  const empty={...stats(),buckets:[],right:[],counts:[],selected:{bucket:'2026-10',projects:[],total:'0.00',count:0}};
  assert.equal(readPaymentStats(empty),empty);
});

test('debt requires real amount strings before rendering and preserves actual values', () => {
  const row={project:'待指定归属',jc:'0.00',material:'-0.01',mech:'1234.00',extra:'keep'};
  assert.equal(readDebt({by_project_category:[row]})[0],row);
  assert.deepEqual(readDebt({by_project_category:[]}),[]);
  for(const amount of [undefined,null,0,['0.00'],'bad']) {
    assert.throws(()=>readDebt({by_project_category:[{...row,mech:amount}]}),ApiError);
  }
});
async function load(payload, noticeId) {
  const previous = globalThis.fetch;
  const expected = noticeId === undefined ? '/api/m05/flows?year_month=' : `/api/m05/flows?notice_id=${noticeId}`;
  globalThis.fetch = async (path, init) => {
    assert.equal(path, expected);
    assert.ok(init.signal instanceof AbortSignal);
    return { status: 200, ok: true, json: async () => payload };
  };
  try { return await loadFlows(undefined, noticeId); }
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

test('single-notice scope only changes the request path, keeping rows, order and revoked/orphan facts', async () => {
  const newer = { ...base, id: 9, notice_id: 7, pay_date: '2026-10-30' };
  const older = { ...base, id: 4, notice_id: 7, amount_approved: null, status: 'revoked', status_label: '已撤销', revoke_reason: '合成原因' };
  const rows = await load({ rows: [newer, older] }, 7);
  assert.equal(rows[0], newer); assert.equal(rows[1], older);
  assert.equal(rows[1].amount_approved, null); assert.equal(rows[1].status, 'revoked');
  assert.deepEqual(await load({ rows: [] }, 7), []);
  await assert.rejects(load({ rows: [{ ...base, notice_id: '7' }] }, 7), ApiError);
});
