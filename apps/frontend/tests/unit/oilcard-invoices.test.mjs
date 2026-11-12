import test from 'node:test';
import assert from 'node:assert/strict';
import { changeOilInvoice, readOilInvoices, receiveOilInvoice, readOilReceipt } from '../../src/oilcard-invoice-api.ts';
import { uncertainWrite } from '../../src/api.ts';
import { CellSaveQueue } from '../../src/cell-save.ts';
import { OilManualRegistration } from '../../src/oilcard-manual-registration.ts';

const digest = 'a'.repeat(64);
const original = { id: 1, invoice_id: 1, sha256: digest, byte_size: 10, outcome: 'received', reason: '', resolution: null, recognized: { invoice_no: null, invoice_date: null, amount: null, card_no: null } };
const invoice = { id: 1, invoice_no: '20261031000000000001', invoice_date: '2026-10-31', card_no: '1000111400012345678', amount: '3000.00', status: 'registered', deleted: false, kind: 'normal', related_invoice_id: null, change_note: '', void_date: null, reason: '', remark: '', version: '00000000-0000-4000-8000-000000000001', allocations: [{ id: 1, project_id: 1, account_id: 2, card_id: 3, amount: '3000.00' }], originals: [original] };
Object.assign(invoice, { manual_request_id: null, manual_date_text: null, manual_cutoff_ym: null });

test('无票号手工行必须保留独立身份，按已登记金额读取', () => {
  const manual = { ...invoice, invoice_no: null, invoice_date: null, originals: [],
    manual_request_id: '00000000-0000-4000-8000-000000000002', manual_date_text: '原始数据', manual_cutoff_ym: '2025-12' };
  assert.equal(readOilInvoices({ invoices: [manual], total_amount: '3000.00' }).total_amount, '3000.00');
  for (const invalid of [{ ...manual, manual_request_id: null }, { ...manual, invoice_date: '2025-12-01' }, { ...manual, originals: [original] }]) {
    assert.throws(() => readOilInvoices({ invoices: [invalid], total_amount: '3000.00' }));
  }
});

test('已登记票据与待确认票据分开核对，合计只取已确认金额', () => {
  const pending = { ...invoice, id: 2, status: 'pending', allocations: [], originals: [{ ...original, id: 2, invoice_id: 2, sha256: 'b'.repeat(64) }] };
  assert.equal(readOilInvoices({ invoices: [invoice, pending], total_amount: '3000.00' }).invoices.length, 2);
  assert.throws(() => readOilInvoices({ invoices: [invoice, pending], total_amount: '6000.00' }));
  assert.throws(() => readOilInvoices({ invoices: [{ ...invoice, allocations: [{ ...invoice.allocations[0], amount: '2999.00' }] }], total_amount: '3000.00' }));
});

test('票据原件及分配身份必须完整，缺失不当成已登记', () => {
  for (const invalid of [{ ...invoice, originals: [{ ...original, invoice_id: 9 }] }, { ...invoice, amount: null }, { ...invoice, allocations: [] }, { ...invoice, deleted: true }]) {
    assert.throws(() => readOilInvoices({ invoices: [invalid], total_amount: '3000.00' }));
  }
});

test('历史已记开票可先无PDF读取，补原件不改变金额，收票仍必须核到本次原件', async () => {
  const before = readOilInvoices({ invoices: [{ ...invoice, originals: [] }], total_amount: '3000.00' });
  const after = readOilInvoices({ invoices: [invoice], total_amount: '3000.00' });
  assert.equal(before.invoices[0].originals.length, 0);
  assert.equal(after.total_amount, before.total_amount);
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, original, item: { ...invoice, originals: [] } }));
    await assert.rejects(receiveOilInvoice(new File(['1234567890'], 'synthetic.pdf'), digest, new AbortController().signal), error => uncertainWrite(error));
  } finally { globalThis.fetch = previous; }
});

test('实际红冲只计算关联负数，作废票保留但退出合计', () => {
  const red = { ...invoice, id: 2, kind: 'credit', related_invoice_id: 1, amount: '-1000.00', allocations: [{ ...invoice.allocations[0], id: 2, amount: '-1000.00' }], originals: [{ ...original, id: 2, invoice_id: 2 }] };
  assert.equal(readOilInvoices({ invoices: [invoice, red], total_amount: '2000.00' }).total_amount, '2000.00');
  assert.equal(readOilInvoices({ invoices: [{ ...invoice, status: 'voided' }], total_amount: '0.00' }).invoices.length, 1);
  assert.throws(() => readOilInvoices({ invoices: [{ ...invoice, status: 'voided' }, red], total_amount: '-1000.00' }));
  const excessive = { ...red, amount: '-3001.00', allocations: [{ ...red.allocations[0], amount: '-3001.00' }] };
  assert.throws(() => readOilInvoices({ invoices: [invoice, excessive], total_amount: '-1.00' }));
});

test('收票回执须对应本次字节身份，不完整回执保持结果未知', async () => {
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, original: { ...original, sha256: 'b'.repeat(64) }, item: invoice }), { headers: { 'Content-Type': 'application/json' } });
    const file = new File(['1234567890'], 'synthetic.pdf', { type: 'application/pdf' });
    await assert.rejects(receiveOilInvoice(file, digest, new AbortController().signal), error => uncertainWrite(error));
  } finally { globalThis.fetch = previous; }
});

test('重读凭原件hash核对存在和未写入，不能把不完整结果当未写入', async () => {
  const previous = globalThis.fetch;
  try {
    for (const [value, expected] of [[{ received: true, original }, true], [{ received: false, original: null }, false]]) {
      globalThis.fetch = async () => new Response(JSON.stringify(value));
      assert.deepEqual(await readOilReceipt(digest), { received: expected, deleted: false, message: '' });
    }
    globalThis.fetch = async () => new Response(JSON.stringify({ received: false }));
    await assert.rejects(readOilReceipt(digest));
    globalThis.fetch = async () => new Response(JSON.stringify({ received: true, original, receipt_status: 'deleted', receipt_message: '该票已删除' }));
    assert.deepEqual(await readOilReceipt(digest), { received: true, deleted: true, message: '该票已删除' });
    globalThis.fetch = async () => new Response(JSON.stringify({ received: true, original, receipt_status: 'deleted' }));
    await assert.rejects(readOilReceipt(digest));
  } finally { globalThis.fetch = previous; }
});

test('删除回执必须明确对应已删除的同一发票，保留原件身份', async () => {
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, item: { ...invoice, deleted: true } }));
    assert.equal((await changeOilInvoice(invoice, 'delete', {}, new AbortController().signal)).deleted, true);
    for (const invalid of [invoice, { ...invoice, deleted: true, originals: [] }, { ...invoice, id: 2, deleted: true, originals: [{ ...original, invoice_id: 2 }] }]) {
      globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, item: invalid }));
      await assert.rejects(changeOilInvoice(invoice, 'delete', {}, new AbortController().signal), error => uncertainWrite(error));
    }
  } finally { globalThis.fetch = previous; }
});

test('整体分配回执必须对应每项归属，合计相同也不能吞掉某一项', async () => {
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, item: invoice }));
    await assert.rejects(changeOilInvoice(invoice, 'allocations', { allocations: [{ project_id: 1, account_id: 2, amount: '2000' }, { project_id: 1, account_id: 4, amount: '1000' }] }, new AbortController().signal), error => uncertainWrite(error));
    await changeOilInvoice(invoice, 'allocations', { allocations: [{ project_id: 1, account_id: 2, amount: '3000' }] }, new AbortController().signal);
  } finally { globalThis.fetch = previous; }
});

const manualFields = () => ({ invoice_no: '', date_text: '原始数据', cutoff_ym: '2025-12', amount: '3000.00', remark: '历史开票',
  allocations: [{ project_id: 1, account_id: 2, amount: '3000.00' }] });

function manualRow(requestId, fields = manualFields()) {
  return { ...invoice, invoice_no: fields.invoice_no || null, invoice_date: fields.invoice_no ? fields.date_text : null,
    manual_request_id: requestId, manual_date_text: fields.date_text, manual_cutoff_ym: fields.cutoff_ym, remark: fields.remark, originals: [] };
}

function connectManualLedger(t, write) {
  const registration = new OilManualRegistration();
  const ledger = { rows: [], total: '0.00', failRead: false, readback: undefined, writes: [] };
  const previous = globalThis.fetch;
  t.after(() => { globalThis.fetch = previous; });
  globalThis.fetch = async (path, init) => {
    const request = { path, method: init.method, fields: JSON.parse(init.body) };
    ledger.writes.push(request);
    const item = await write(request, ledger);
    return item instanceof Response ? item : new Response(JSON.stringify({ ok: true, item }));
  };
  const queue = new CellSaveQueue(() => ({
    enabled: true,
    write: async () => assert.fail('manual registration uses the shared action entry'),
    acknowledge: () => undefined, saved: () => '',
    read: async () => {
      if (ledger.failRead) throw new Error('确认读取失败');
      const data = readOilInvoices({ invoices: ledger.rows, total_amount: ledger.total });
      ledger.readback = registration.readBack(data.invoices);
      return data;
    },
  }));
  t.after(queue.dispose);
  return { registration, queue, ledger };
}

test('新增手工登记已落账但回执丢失，可靠读回并确认后结束原登记', async t => {
  const { registration, queue, ledger } = connectManualLedger(t, ({ fields }, ledger) => {
    ledger.rows = [manualRow(fields.request_id)];
    ledger.total = '3000.00';
    throw new TypeError('连接中断');
  });
  const form = registration.open();
  assert.equal(await form.submit(manualFields(), queue.run), true);
  assert.equal(queue.getSnapshot().uncertain, true);

  ledger.failRead = true;
  assert.equal(await queue.reread(), false);
  queue.confirm(); registration.confirmRead();
  assert.equal(queue.getSnapshot().uncertain, true);
  assert.equal(registration.getPhase(), 'checking');
  assert.equal(registration.open(), undefined);

  ledger.failRead = false;
  assert.equal(await queue.reread(), true);
  assert.equal(ledger.readback.status, 'matched');
  assert.equal(ledger.readback.id, invoice.id);
  assert.equal(registration.getPhase(), 'checking');
  queue.confirm(); registration.confirmRead();
  assert.equal(registration.getPhase(), 'idle');
  await registration.retry(queue.run);
  assert.equal(await form.submit(manualFields(), queue.run), false);
  assert.equal(ledger.writes.length, 1);
  assert.equal(ledger.total, '3000.00');
});

test('可靠读回无原登记时只续用同一请求和快照，连续点击不会重复提交', async t => {
  const { registration, queue, ledger } = connectManualLedger(t, ({ fields }, ledger) => {
    if (ledger.writes.length === 1) throw new TypeError('连接中断');
    ledger.rows = [manualRow(fields.request_id)];
    ledger.total = '3000.00';
    return ledger.rows[0];
  });
  const form = registration.open();
  const fields = manualFields();
  const submission = form.submit(fields, queue.run);
  assert.equal(await form.submit(fields, queue.run), false);
  fields.remark = '后续输入';
  fields.allocations[0].account_id = 99;
  assert.equal(await submission, true);
  assert.equal(await queue.reread(), true);
  assert.equal(ledger.readback.status, 'missing');
  await registration.retry(queue.run);
  assert.equal(ledger.writes.length, 1);

  queue.confirm(); registration.confirmRead();
  assert.equal(registration.getPhase(), 'retry');
  assert.equal(registration.open(), undefined);
  await Promise.all([registration.retry(queue.run), registration.retry(queue.run)]);
  assert.equal(registration.getPhase(), 'idle');
  assert.equal(ledger.writes.length, 2);
  assert.deepEqual(ledger.writes[1], ledger.writes[0]);
  assert.equal(ledger.writes[0].method, 'POST');
  assert.equal(ledger.total, '3000.00');
});

test('已收到成功回执但读回内容有变化，继续核对且不重放已有登记', async t => {
  const { registration, queue, ledger } = connectManualLedger(t, ({ fields }, ledger) => {
    const saved = manualRow(fields.request_id);
    ledger.rows = [{ ...saved, remark: '其他账号已更新备注' }];
    ledger.total = '3000.00';
    return saved;
  });
  assert.equal(await registration.open().submit(manualFields(), queue.run), true);
  assert.equal(queue.getSnapshot().uncertain, true);
  assert.match(queue.getSnapshot().error, /已保存，重读失败/);
  assert.equal(registration.getPhase(), 'checking');
  assert.equal(await queue.reread(), true);
  assert.equal(ledger.readback.status, 'changed');
  assert.equal(ledger.readback.id, invoice.id);
  queue.confirm(); registration.confirmRead();
  assert.equal(registration.getPhase(), 'idle');
  await registration.retry(queue.run);
  assert.equal(ledger.writes.length, 1);
  assert.equal(ledger.rows[0].remark, '其他账号已更新备注');
});

test('原登记重试收到冲突，重新读回和确认前保持锁定，缺行也不第三次提交', async t => {
  const { registration, queue, ledger } = connectManualLedger(t, (_, ledger) => {
    if (ledger.writes.length === 1) throw new TypeError('连接中断');
    return Response.json({ ok: false, message: '这次手工登记已有记录或已经更正，请重读核对，勿重复登记。' }, { status: 409 });
  });
  assert.equal(await registration.open().submit(manualFields(), queue.run), true);
  assert.equal(await queue.reread(), true);
  assert.equal(ledger.readback.status, 'missing');
  queue.confirm(); registration.confirmRead();
  await registration.retry(queue.run);
  assert.equal(queue.getSnapshot().uncertain, true);
  assert.equal(registration.getPhase(), 'checking');
  assert.deepEqual(ledger.writes[1], ledger.writes[0]);

  ledger.failRead = true;
  assert.equal(await queue.reread(), false);
  queue.confirm(); registration.confirmRead();
  assert.equal(queue.getSnapshot().uncertain, true);
  assert.equal(registration.open(), undefined);
  ledger.failRead = false;
  assert.equal(await queue.reread(), true);
  assert.equal(ledger.readback.status, 'missing');
  assert.match(ledger.readback.message, /冲突.*核对操作历史/);
  assert.equal(registration.open(), undefined);
  queue.confirm(); registration.confirmRead();
  assert.equal(queue.getSnapshot().uncertain, false);
  assert.equal(registration.getPhase(), 'idle');
  await registration.retry(queue.run);
  assert.equal(ledger.writes.length, 2);
});

test('补票号使用原行版本，丢回执时读到旧行不能当成修改成功或续办新增', async t => {
  const requestId = '00000000-0000-4000-8000-000000000002';
  const existing = manualRow(requestId);
  const fields = { ...manualFields(), invoice_no: invoice.invoice_no, date_text: invoice.invoice_date, cutoff_ym: null };
  const { registration, queue, ledger } = connectManualLedger(t, ({ fields }, ledger) => {
    if (ledger.writes.length > 1) ledger.rows = [{ ...manualRow(requestId, fields), version: '00000000-0000-4000-8000-000000000003' }];
    throw new TypeError('连接中断');
  });
  ledger.rows = [existing];
  ledger.total = '3000.00';
  assert.equal(await registration.open(existing).submit(fields, queue.run), true);
  assert.equal(await queue.reread(), true);
  assert.equal(ledger.readback.status, 'changed');
  assert.equal(ledger.readback.id, existing.id);
  queue.confirm(); registration.confirmRead();
  assert.equal(registration.getPhase(), 'idle');
  await registration.retry(queue.run);
  assert.equal(ledger.writes.length, 1);

  assert.equal(await registration.open(ledger.rows[0]).submit(fields, queue.run), true);
  assert.equal(await queue.reread(), true);
  assert.equal(ledger.readback.status, 'matched');
  queue.confirm(); registration.confirmRead();
  assert.equal(registration.getPhase(), 'idle');
  assert.deepEqual(ledger.writes, Array(2).fill({ path: `/api/m13/invoices/${existing.id}/manual`, method: 'PUT', fields: { ...fields, version: existing.version } }));
  assert.equal(ledger.rows[0].invoice_no, invoice.invoice_no);
  assert.equal(ledger.rows[0].manual_request_id, requestId);
  assert.equal(ledger.rows[0].id, existing.id);
  assert.equal(ledger.total, '3000.00');
});
