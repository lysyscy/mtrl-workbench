import test from 'node:test';
import assert from 'node:assert/strict';
import { readOilInvoices, receiveOilInvoice, readOilReceipt } from '../../src/oilcard-invoice-api.ts';
import { uncertainWrite } from '../../src/api.ts';

const digest = 'a'.repeat(64);
const original = { id: 1, invoice_id: 1, sha256: digest, byte_size: 10, outcome: 'received', reason: '' };
const invoice = { id: 1, invoice_no: '20261031000000000001', invoice_date: '2026-10-31', card_no: '1000111400012345678', amount: '3000.00', status: 'registered', reason: '', remark: '', version: '00000000-0000-4000-8000-000000000001', allocations: [{ id: 1, project_id: 1, account_id: 2, card_id: 3, amount: '3000.00' }], originals: [original] };

test('已登记票据与待确认票据分开核对，合计只取已确认金额', () => {
  const pending = { ...invoice, id: 2, status: 'pending', allocations: [], originals: [{ ...original, id: 2, invoice_id: 2, sha256: 'b'.repeat(64) }] };
  assert.equal(readOilInvoices({ invoices: [invoice, pending], total_amount: '3000.00' }).invoices.length, 2);
  assert.throws(() => readOilInvoices({ invoices: [invoice, pending], total_amount: '6000.00' }));
  assert.throws(() => readOilInvoices({ invoices: [{ ...invoice, allocations: [{ ...invoice.allocations[0], amount: '2999.00' }] }], total_amount: '3000.00' }));
});

test('票据原件及分配身份必须完整，缺失不当成已登记', () => {
  for (const invalid of [{ ...invoice, originals: [] }, { ...invoice, originals: [{ ...original, invoice_id: 9 }] }, { ...invoice, amount: null }, { ...invoice, allocations: [] }]) {
    assert.throws(() => readOilInvoices({ invoices: [invalid], total_amount: '3000.00' }));
  }
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
      assert.equal(await readOilReceipt(digest), expected);
    }
    globalThis.fetch = async () => new Response(JSON.stringify({ received: false }));
    await assert.rejects(readOilReceipt(digest));
  } finally { globalThis.fetch = previous; }
});
