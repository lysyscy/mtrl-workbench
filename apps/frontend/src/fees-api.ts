import { ApiError, body, confirmWrite, record, requestJson } from './api';

export interface FeeRow { kind: 'auto' | 'manual'; id: number; index: number; item: string; source: string; amount: string; share: string }
export interface FeeData {
  ym: string; project: string; project_display: string; auto: FeeRow; manuals: FeeRow[]; total: string; count: number; can_edit: boolean;
  projects: { key: string; display: string; archived: boolean; placeholder: boolean }[];
}
export type FeeField = 'item' | 'amount';
const moneyText = (value: unknown): value is string => typeof value === 'string' && /^-?\d+(?:\.\d{1,2})?$/.test(value);
function row(value: unknown, manual: boolean): FeeRow {
  if (!record(value) || value.kind !== (manual ? 'manual' : 'auto') ||
    !['item','source','share'].every(key => typeof value[key] === 'string') || !moneyText(value.amount) ||
    manual && !(typeof value.id === 'number' && Number.isSafeInteger(value.id) && value.id > 0 && typeof value.index === 'number' && Number.isInteger(value.index) && value.index >= 0)) throw new ApiError('费用明细读取不完整，请重读。');
  return { ...value, id: manual ? value.id : 0, index: manual ? value.index : -1 } as FeeRow;
}
export function readFees(value: unknown): FeeData {
  if (!record(value) || typeof value.ym !== 'string' || !/^\d{4}-(0[1-9]|1[0-2])$/.test(value.ym) ||
    typeof value.project !== 'string' || typeof value.project_display !== 'string' || typeof value.can_edit !== 'boolean' ||
    !moneyText(value.total) || !Array.isArray(value.manuals) || value.count !== value.manuals.length || !Array.isArray(value.projects) ||
    !value.projects.every(p => record(p) && typeof p.key === 'string' && typeof p.display === 'string' && typeof p.archived === 'boolean' && typeof p.placeholder === 'boolean')) throw new ApiError('费用读取不完整，请重读。');
  const manuals = value.manuals.map(x => row(x, true));
  if (new Set(manuals.map(x => x.id)).size !== manuals.length || manuals.some((x, i) => x.index !== i)) throw new ApiError('费用记录顺序不完整，请重读。');
  return { ...value, auto: row(value.auto, false), manuals } as FeeData;
}
export async function getFees(ym: string, project: string, signal?: AbortSignal) {
  const data = readFees(await requestJson(`/api/m09/fee?${new URLSearchParams({ ym, pj: project })}`, signal ? { signal } : {}));
  if (data.ym !== ym || project && data.project !== project) throw new ApiError('费用范围已变化，请重新选择项目。');
  return data;
}
export async function feeWrite(action: string, payload: unknown, signal: AbortSignal) {
  const data = await requestJson(`/api/m09/fee/${action}`, { method: 'POST', signal, ...body(payload) });
  confirmWrite(record(data) && data.ok === true && data.kind === 'ok', '保存回执未确认，请重读核对，勿重复提交。');
  return record(data) && typeof data.row_id === 'number' && Number.isSafeInteger(data.row_id) && data.row_id > 0 ? data.row_id : null;
}

export interface FeeYearRow { item: string; manual: boolean; prior: string | null; months: (string | null)[]; total: string; periods: string[] }
export interface FeeYearRecord { ym: string; id: number; index: number; item: string; amount: string }
export interface FeeYearData { auto_name: string; records: FeeYearRecord[]; year: string; project: string; project_display: string; can_edit: boolean; rows: FeeYearRow[]; prior: string; months: string[]; total: string }
export async function getFeeYear(year: string, project: string, signal?: AbortSignal): Promise<FeeYearData> {
  const data = await requestJson(`/api/m09/fee/year?${new URLSearchParams({year,pj:project})}`, signal ? {signal} : {});
  const amounts = (r: Record<string,unknown>, nullable: boolean) =>
    (nullable && r.prior === null || moneyText(r.prior)) && moneyText(r.total) && Array.isArray(r.months) && r.months.length === 12 && r.months.every(v => nullable && v === null || moneyText(v));
  if (!record(data) || typeof data.auto_name !== 'string' || data.year !== year || typeof data.project !== 'string' || project && data.project !== project ||
    typeof data.project_display !== 'string' || typeof data.can_edit !== 'boolean' || !amounts(data,false) || !Array.isArray(data.records) || !data.records.every(r => record(r) && typeof r.ym === 'string' && new RegExp(`^${year}-(0[1-9]|1[0-2])$`).test(r.ym) && typeof r.id === 'number' && Number.isSafeInteger(r.id) && r.id > 0 && typeof r.index === 'number' && Number.isSafeInteger(r.index) && r.index >= 0 && typeof r.item === 'string' && moneyText(r.amount)) || new Set(data.records.map(r => r.id)).size !== data.records.length || !Array.isArray(data.rows) ||
    !data.rows.every(r => record(r) && typeof r.item === 'string' && typeof r.manual === 'boolean' && amounts(r,true) && Array.isArray(r.periods) && r.periods.every(ym => typeof ym === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(ym) && ym <= `${year}-12`)) ||
    new Set(data.rows.map(r => r.item)).size !== data.rows.length) throw new ApiError('费用年度数据读取不完整，请重读。');
  return data as unknown as FeeYearData;
}
