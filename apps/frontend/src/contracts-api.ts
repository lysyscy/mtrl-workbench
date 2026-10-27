import * as v from 'valibot';
import { ApiError, record, requestJson } from './api';
import { body } from './notices-api';

export const contractMoneyKeys = ['contract_amt','inv_sum','trade_contract_amt','trade_inv_sum','settle','pay_sum','debt'] as const;
export const editableContractKeys = ['material_name','payment_term','payment_method','remark','arch','arch_no','ret_date'] as const;
export type ContractFields = Record<typeof editableContractKeys[number], string>;
const nonArrayObject = v.custom<object>(record);
const positiveId = v.pipe(v.number(), v.safeInteger(), v.minValue(1));
const moneyText = v.pipe(v.string(), v.regex(/^-?\d+(?:\.\d{1,2})?$/));
const contractEntries = {
  id: positiveId, project_seq: v.nullable(positiveId), contract_no: v.string(), date: v.string(),
  material: v.string(), supplier: v.string(), contract_amt: moneyText, inv_sum: moneyText,
  trade_co: v.nullable(v.string()), trade_contract_amt: v.nullable(moneyText), trade_inv_sum: moneyText,
  settle: moneyText, pay_sum: moneyText, debt: moneyText, payment_term: v.string(), payment_method: v.string(),
  remark: v.string(), tag: v.string(), arch: v.string(), arch_no: v.string(), ret_date: v.string(),
};
const contractSchema = v.intersect([v.object(contractEntries), nonArrayObject]);
const rowSchema = v.intersect([v.object({ ...contractEntries, project_key: v.string(), notice_ids: v.array(positiveId) }), nonArrayObject]);
const invoiceSchema = v.intersect([v.object({ id: positiveId, kind: v.string(), date: v.string(), amount: moneyText }), nonArrayObject]);
const detailSchema = v.intersect([v.object({ ...contractEntries, supplier_invoices: v.array(invoiceSchema), trade_invoices: v.array(invoiceSchema) }), nonArrayObject]);
const listSchema = v.intersect([v.object({
  rows: v.array(v.unknown()),
  columns: v.array(v.intersect([v.object({ key: v.string(), label: v.string(), type: v.string() }), nonArrayObject])),
  tags: v.array(v.string()), payment_methods: v.array(v.string()),
}), nonArrayObject]);
export type ContractBase = v.InferOutput<typeof contractSchema>;
export type ContractRow = v.InferOutput<typeof rowSchema>;
export type ContractInvoice = v.InferOutput<typeof invoiceSchema>;
export type ContractDetail = v.InferOutput<typeof detailSchema>;
export type ContractList = Omit<v.InferOutput<typeof listSchema>, 'rows'> & { rows: ContractRow[] };
function contractRow(value: unknown): ContractBase {
  if (record(value) && value.ret_date === null) value = { ...value, ret_date: '' };
  if (!v.is(contractSchema, value)) throw new ApiError('合同读取不完整，请重读。');
  return value;
}
export function readContracts(value: unknown): ContractList {
  if (!v.is(listSchema, value)) throw new ApiError('合同列表读取不完整，请重读。');
  const rows = value.rows.map((x: unknown) => {
    const row = contractRow(x);
    if (!v.is(rowSchema, row)) throw new ApiError('合同归属或关联读取不完整，请重读。');
    return row;
  });
  return { rows, columns: value.columns, tags: value.tags, payment_methods: value.payment_methods };
}
export function readContractDetail(value: unknown): ContractDetail {
  if (!record(value) || !record(value.data)) throw new ApiError('合同详情读取不完整，请重读。');
  const row = contractRow(value.data);
  if (!v.is(detailSchema, row)) throw new ApiError('合同发票依据读取不完整，请重读。');
  return { ...value.data, ...row };
}
export function contractFields(row: ContractBase): ContractFields {
  return { material_name: row.material, payment_term: row.payment_term, payment_method: row.payment_method,
    remark: row.remark, arch: row.arch, arch_no: row.arch_no, ret_date: row.ret_date };
}
export async function contractWrite(path: string, payload: unknown, method = 'POST') {
  const value=await requestJson(path, { method, ...body(payload) });
  if(!record(value)||value.ok!==true)throw new ApiError('操作回执未确认，请重读核对，勿重复提交。',0,'invalid_response');
  return value;
}

const historyPrefix='历史未结金额；核对截至日：';
export function contractHistoryDate(remark:string):string{return remark.startsWith(historyPrefix)?remark.slice(historyPrefix.length,historyPrefix.length+10):'';}
export function historyContractRemark(date:string,remark:string):string{return `${historyPrefix}${date}；${remark.trim()}`;}

export function contractRemarkText(remark:string):string{const date=contractHistoryDate(remark);return date?remark.slice(historyContractRemark(date,'').length):remark;}
