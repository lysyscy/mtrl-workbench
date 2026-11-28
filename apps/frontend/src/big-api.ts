import * as v from 'valibot';
import { ApiError, body, confirmWrite, record, requestJson } from './api';

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
  seq: number; warehouse: string; display: string; carry_n: number; oil_linked: boolean;
  manual: Record<ManualKey, { value: Amount; from: string }>;
  auto: Record<AutoKey, Amount>; derived: Record<DerivedKey, Amount>;
}
export interface BigData {
  month: string; selection: {fixed: boolean; source: string}; selected: string[]; candidates: { warehouse: string; display: string }[];
  rows: BigRow[]; totals: Record<TotalKey, Amount>; mat_available: boolean; empty_text: string;
}
const month = (v: unknown): v is string => typeof v === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(v);
const amount = (v: unknown) => v === null || typeof v === 'string' && /^-?\d+(?:\.\d+)?$/.test(v);
const invalid = () => new ApiError('大表读取不完整，请重读。');
const amountSchema = v.custom<Amount>(amount);
const bigSchema = v.looseObject({
  month: v.string(), selected: v.array(v.string()),
  candidates: v.array(v.looseObject({ warehouse: v.pipe(v.string(), v.nonEmpty()), display: v.string() })),
  rows: v.array(v.looseObject({
    seq: v.pipe(v.number(), v.safeInteger()), warehouse: v.string(), display: v.string(),
    carry_n: v.number(), oil_linked: v.boolean(),
    manual: v.objectWithRest(v.entriesFromList(manualKeys, v.looseObject({
      value: v.nullable(v.string()), from: v.string(),
    })), v.unknown()),
    auto: v.objectWithRest(v.entriesFromList(autoKeys, amountSchema), v.unknown()),
    derived: v.objectWithRest(v.entriesFromList(derivedKeys, amountSchema), v.unknown()),
  })),
  totals: v.objectWithRest(v.entriesFromList(totalKeys, amountSchema), v.unknown()),
  selection: v.looseObject({ fixed: v.boolean(), source: v.string() }),
  manual_keys: v.array(v.string()), manual_fmts: v.array(v.string()),
  mat_available: v.boolean(), empty_text: v.string(),
});
export function readBig(value: unknown, ym: string): BigData {
  if (!v.is(bigSchema, value) || value.month !== ym ||
      !(value.selection.source === 'legacy' || value.selection.source === 'default' || month(value.selection.source) && value.selection.source <= ym) ||
      (value.selection.fixed && value.selection.source !== ym) ||
      value.manual_keys.join(',') !== manualKeys.join(',') ||
      value.manual_fmts.join(',') !== 'ym,money,money,money,money,text') throw invalid();
  for (const row of value.rows) {
    for (const k of manualKeys) {
      const cell = row.manual[k];
      if (!(cell.from === '' || month(cell.from) && cell.from < ym) ||
          (k === 'open_ym' && cell.value !== null && !month(cell.value)) ||
          (k !== 'open_ym' && k !== 'note' && !amount(cell.value))) throw invalid();
    }
  }
  const candidates = value.candidates.map(c => c.warehouse);
  if (new Set(candidates).size !== candidates.length || new Set(value.selected).size !== value.selected.length ||
      value.selected.some(k => !candidates.includes(k)) || value.rows.length !== value.selected.length ||
      value.rows.some((r, i) => r.warehouse !== value.selected[i] || r.seq !== i + 1)) throw invalid();
  return value;
}
export const getBig = async (ym: string, signal?: AbortSignal) => readBig(await requestJson(`/api/m07/big?${new URLSearchParams({period:ym})}`, signal ? {signal} : {}),ym);
export async function saveBigCell(ym: string, warehouse: string, key: ManualKey, raw: string, signal: AbortSignal) {
  const result = await requestJson('/api/m07/big/cell', {method:'POST',signal,...body({month:ym,warehouse,key,raw})});
  confirmWrite(record(result) && result.ok === true && 'value' in result, '保存回执未确认，请重读核对，勿重复提交。');
}
export async function saveBigSelection(ym: string, selected: string[], signal: AbortSignal) {
  const result = await requestJson('/api/m07/big/selection', {method:'POST',signal,...body({month:ym,selected})});
  confirmWrite(record(result) && result.ok === true && Array.isArray(result.selected) && result.selected.every(v => typeof v === 'string'), '选题回执未确认，请重读核对，勿重复提交。');
}
