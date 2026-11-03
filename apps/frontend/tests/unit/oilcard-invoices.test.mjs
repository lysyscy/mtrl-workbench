import test from 'node:test';
import assert from 'node:assert/strict';
import { changeOilInvoice, readOilInvoices, receiveOilInvoice, readOilReceipt } from '../../src/oilcard-invoice-api.ts';
import { uncertainWrite } from '../../src/api.ts';

const digest = 'a'.repeat(64);
const original = { id: 1, invoice_id: 1, sha256: digest, byte_size: 10, outcome: 'received', reason: '', resolution: null, recognized: { invoice_no: null, invoice_date: null, amount: null, card_no: null } };
const invoice = { id: 1, invoice_no: '20261031000000000001', invoice_date: '2026-10-31', card_no: '1000111400012345678', amount: '3000.00', status: 'registered', deleted: false, kind: 'normal', related_invoice_id: null, change_note: '', void_date: null, reason: '', remark: '', version: '00000000-0000-4000-8000-000000000001', allocations: [{ id: 1, project_id: 1, account_id: 2, card_id: 3, amount: '3000.00' }], originals: [original] };

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
