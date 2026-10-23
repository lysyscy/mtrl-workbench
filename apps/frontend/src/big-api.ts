import { ApiError, record, requestJson } from './api';

export const manualKeys = ['open_ym','mech_est','contract','output_cum','oil','note'] as const;
export type ManualKey = typeof manualKeys[number];
export const autoKeys = ['hw_cum','hw_mon','qt_cum','qt_mon','rent_cum','rent_mon','lease_cum','lease_mon'] as const;
export type AutoKey = typeof autoKeys[number];
export const derivedKeys = ['total_cum','use_rate','output_rate','mat_cum'] as const;
export type DerivedKey = typeof derivedKeys[number];
export const totalKeys = [...autoKeys,'total_cum','mech_est','contract','output_cum','mat_cum','oil'] as const;
export type TotalKey = typeof totalKeys[number];
export type Amount = string | null;
export interface BigRow {
  seq: number; warehouse: string; display: string; carry_n: number;
  manual: Record<ManualKey, { value: Amount; from: string }>;
  auto: Record<AutoKey, Amount>; derived: Record<DerivedKey, Amount>;
}
export interface BigData {
  month: string; selected: string[]; candidates: { warehouse: string; display: string }[];
  rows: BigRow[]; totals: Record<TotalKey, Amount>; mat_available: boolean; empty_text: string;
}
const month = (v: unknown): v is string => typeof v === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(v);
const amount = (v: unknown) => v === null || typeof v === 'string' && /^-?\d+(?:\.\d+)?$/.test(v);
const invalid = () => new ApiError('大表读取不完整，请重读。');
export function readBig(value: unknown, ym: string): BigData {
  if (!record(value) || value.month !== ym || !Array.isArray(value.selected) || !value.selected.every(v => typeof v === 'string') ||
      !Array.isArray(value.candidates) || !Array.isArray(value.rows) || !record(value.totals) || !totalKeys.every(k => amount((value.totals as Record<string,unknown>)[k])) ||
      typeof value.mat_available !== 'boolean' || typeof value.empty_text !== 'string' ||
      !Array.isArray(value.manual_keys) || value.manual_keys.join(',') !== manualKeys.join(',') ||
      !Array.isArray(value.manual_fmts) || value.manual_fmts.join(',') !== 'ym,money,money,money,money,text') throw invalid();
  for (const c of value.candidates) if (!record(c) || typeof c.warehouse !== 'string' || !c.warehouse || typeof c.display !== 'string') throw invalid();
  for (const row of value.rows) {
    if (!record(row) || typeof row.seq !== 'number' || !Number.isSafeInteger(row.seq) || typeof row.warehouse !== 'string' || typeof row.display !== 'string' ||
        typeof row.carry_n !== 'number' || !record(row.manual) || !record(row.auto) || !record(row.derived) ||
        !autoKeys.every(k => amount((row.auto as Record<string,unknown>)[k])) || !derivedKeys.every(k => amount((row.derived as Record<string,unknown>)[k]))) throw invalid();
    for (const k of manualKeys) {
      const cell = row.manual[k];
      if (!record(cell) || !(cell.value === null || typeof cell.value === 'string') || !(cell.from === '' || month(cell.from) && cell.from < ym) ||
          (k === 'open_ym' && cell.value !== null && !month(cell.value)) || (k !== 'open_ym' && k !== 'note' && !amount(cell.value))) throw invalid();
    }
  }
  const candidates = value.candidates.map(c => c.warehouse);
  if (new Set(candidates).size !== candidates.length || new Set(value.selected).size !== value.selected.length ||
      value.selected.some(k => !candidates.includes(k)) || value.rows.length !== value.selected.length ||
      value.rows.some((r,i) => r.warehouse !== (value.selected as string[])[i] || r.seq !== i+1)) throw invalid();
  return value as unknown as BigData;
}
export const getBig = async (ym: string, signal?: AbortSignal) => readBig(await requestJson(`/api/m07/big?${new URLSearchParams({period:ym})}`, signal ? {signal} : {}),ym);
export async function saveBigCell(ym: string, warehouse: string, key: ManualKey, raw: string, signal: AbortSignal) {
  const result = await requestJson('/api/m07/big/cell', {method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({month:ym,warehouse,key,raw})});
  if (!record(result) || result.ok !== true || !('value' in result)) throw new ApiError('保存回执未确认，请重读核对，勿重复提交。',0,'invalid_response');
}
export async function saveBigSelection(selected: string[], signal: AbortSignal) {
  const result = await requestJson('/api/m07/big/selection', {method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({selected})});
  if (!record(result) || result.ok !== true || !Array.isArray(result.selected) || !result.selected.every(v => typeof v === 'string')) throw new ApiError('选题回执未确认，请重读核对，勿重复提交。',0,'invalid_response');
}
export const uncertainBig = (e: unknown) => !(e instanceof ApiError) || !e.status || e.status >= 500 || e.code === 'invalid_response';
