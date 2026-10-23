import { ApiError, record, requestJson } from './api';
import { body } from './notices-api';

export const contractMoneyKeys = ['contract_amt','inv_sum','trade_contract_amt','trade_inv_sum','settle','pay_sum','debt'] as const;
export const editableContractKeys = ['material_name','payment_term','payment_method','remark','arch','arch_no','ret_date'] as const;
export type ContractFields = Record<typeof editableContractKeys[number], string>;
export interface ContractRow {
  id: number; project_seq: number | null; project_key: string; contract_no: string; date: string;
  material: string; supplier: string; contract_amt: string; inv_sum: string; trade_co: string | null;
  trade_contract_amt: string | null; trade_inv_sum: string; settle: string; pay_sum: string; debt: string;
  payment_term: string; payment_method: string; remark: string; tag: string; arch: string; arch_no: string;
  ret_date: string; notice_ids: number[];
}
export interface ContractList { rows: ContractRow[]; columns: { key: string; label: string; type: string }[]; tags: string[]; payment_methods: string[] }
export interface ContractInvoice { id: number; kind: string; date: string; amount: string }
export interface ContractDetail extends ContractRow { supplier_invoices: ContractInvoice[]; trade_invoices: ContractInvoice[] }
const moneyText = (x: unknown) => typeof x === 'string' && /^-?\d+(?:\.\d{1,2})?$/.test(x);
const id = (x: unknown): x is number => typeof x === 'number' && Number.isSafeInteger(x) && x > 0;
function contractRow(value: unknown): ContractRow {
  if (!record(value) || !id(value.id) || !(value.project_seq === null || id(value.project_seq)) ||
    !['contract_no','date','material','supplier','payment_term','payment_method','remark','tag','arch','arch_no','ret_date'].every(k => typeof value[k] === 'string') ||
    !(value.trade_co === null || typeof value.trade_co === 'string') ||
    !contractMoneyKeys.every(k => k === 'trade_contract_amt' && value[k] === null || moneyText(value[k]))) throw new ApiError('合同读取不完整，请重读。');
  return value as unknown as ContractRow;
}
export function readContracts(value: unknown): ContractList {
  if (!record(value) || !Array.isArray(value.rows) || !Array.isArray(value.columns) || !value.columns.every(c => record(c) && ['key','label','type'].every(k => typeof c[k] === 'string')) ||
    !Array.isArray(value.tags) || !value.tags.every(x => typeof x === 'string') || !Array.isArray(value.payment_methods) || !value.payment_methods.every(x => typeof x === 'string')) throw new ApiError('合同列表读取不完整，请重读。');
  const rows = value.rows.map((x: unknown) => {
    const row = contractRow(x);
    if (typeof row.project_key !== 'string' || !Array.isArray(row.notice_ids) || !row.notice_ids.every(id)) throw new ApiError('合同归属或关联读取不完整，请重读。');
    return row;
  });
  return { rows, columns: value.columns as ContractList['columns'], tags: value.tags as string[], payment_methods: value.payment_methods as string[] };
}
export function readContractDetail(value: unknown): ContractDetail {
  if (!record(value) || !record(value.data)) throw new ApiError('合同详情读取不完整，请重读。');
  contractRow(value.data);
  for (const key of ['supplier_invoices','trade_invoices']) {
    const invoices = value.data[key];
    if (!Array.isArray(invoices) || !invoices.every(x => record(x) && id(x.id) && typeof x.kind === 'string' && typeof x.date === 'string' && moneyText(x.amount))) throw new ApiError('合同发票依据读取不完整，请重读。');
  }
  return value.data as unknown as ContractDetail;
}
export function contractFields(row: ContractRow): ContractFields {
  return { material_name: row.material, payment_term: row.payment_term, payment_method: row.payment_method,
    remark: row.remark, arch: row.arch, arch_no: row.arch_no, ret_date: row.ret_date };
}
export async function contractWrite(path: string, payload: unknown, method = 'POST') {
  const value=await requestJson(path, { method, ...body(payload) });
  if(!record(value)||value.ok!==true)throw new ApiError('操作回执未确认，请重读核对，勿重复提交。',0,'invalid_response');
  return value;
}
