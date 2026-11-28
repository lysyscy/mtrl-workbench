import * as v from 'valibot';
import { ApiError, body, cents, confirmWrite, decimal, record, requestJson } from './api';

export const kinds = ['焊材', '气体'] as const;
export type ExtractKind = typeof kinds[number];
export type Amount = string | null;
export interface SettlementRow { id: string; name: string; rows: number; begin: string; in: string; out: string; end: string }
export interface Settlement { ym: string; rows: SettlementRow[]; counts: { warehouses: number; rows: number; files: number }; balance_ok: boolean }
export interface AnnualRow { warehouse: string; prior: Amount; balance: Amount; total: Amount; cells: Amount[] }
export interface AnnualGrid { kind: ExtractKind; year: string; months: string[]; rows: AnnualRow[]; sum_row: Amount[] }
export interface ExtractData { annual: Record<ExtractKind, AnnualGrid>; balances: Record<ExtractKind, Record<string, Amount>> }
const numeric = (v: unknown): v is string => typeof v === 'string' && /^-?\d+(?:\.\d{1,2})?$/.test(v);
const amount = (v: unknown): v is Amount => v === null || numeric(v);
const invalid = () => new ApiError('报表读取不完整，请重读。');
const integer = (v: unknown) => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0;
const numberText = v.custom<string>(numeric);
const amountSchema = v.nullable(numberText);
const settlement = v.looseObject({
  ym: v.string(), balance_ok: v.boolean(),
  counts: v.objectWithRest(v.entriesFromList(['warehouses', 'rows', 'files'], v.custom<number>(integer)), v.unknown()),
  rows: v.array(v.looseObject({
    id: v.pipe(v.string(), v.nonEmpty()), name: v.string(), rows: v.custom<number>(integer),
    begin: numberText, in: numberText, out: numberText, end: numberText,
  })),
});
const annualGrid = v.looseObject({
  kind: v.picklist(kinds), year: v.string(), months: v.pipe(v.array(v.string()), v.length(12)),
  sum_row: v.pipe(v.array(amountSchema), v.length(14)),
  rows: v.array(v.looseObject({
    warehouse: v.pipe(v.string(), v.nonEmpty()), prior: amountSchema, balance: amountSchema, total: amountSchema,
    cells: v.pipe(v.array(amountSchema), v.length(12)),
  })),
});
const extract = v.looseObject({
  annual: v.objectWithRest(v.entriesFromList(kinds, annualGrid), v.unknown()),
  balances: v.objectWithRest(v.entriesFromList(kinds, v.record(v.string(), amountSchema)), v.unknown()),
});
export function readSettlement(value: unknown, ym: string): Settlement {
  if (!v.is(settlement, value) || value.ym !== ym || value.rows.some(row => row.name !== row.id) ||
      new Set(value.rows.map(row => row.id)).size !== value.rows.length) throw invalid();
  return value;
}
export function readExtract(value: unknown, year: string): ExtractData {
  if (!v.is(extract, value)) throw invalid();
  for (const kind of kinds) {
    const grid = value.annual[kind];
    if (grid.kind !== kind || grid.year !== year ||
        grid.months.some((m, i) => m !== `${year}-${String(i + 1).padStart(2,'0')}`) ||
        new Set(grid.rows.map(row => row.warehouse)).size !== grid.rows.length) throw invalid();
  }
  return value;
}
export const getSettlement = async (ym: string, signal?: AbortSignal) => readSettlement(await requestJson(`/api/m07/settlement?${new URLSearchParams({ period: ym })}`, signal ? { signal } : {}), ym);
export const getExtract = async (year: string, status: string, signal?: AbortSignal) => readExtract(await requestJson(`/api/m07/extract-screen?${new URLSearchParams({ year, status })}`, signal ? { signal } : {}), year);
export async function saveBalance(kind: ExtractKind, warehouse: string, raw: string, signal: AbortSignal) {
  const value = await requestJson('/api/m07/extract/balance', { method: 'POST', signal, ...body({ kind, warehouse, raw }) });
  // constraint: The balance write endpoint serializes Decimal as a JSON number and clear as null.
  confirmWrite(record(value) && value.ok === true && (amount(value.value) || typeof value.value === 'number' && Number.isFinite(value.value)), '保存回执未确认，请重读核对，勿重复提交。');
}
export function settlementTotal(rows: SettlementRow[], field: 'begin' | 'in' | 'out' | 'end') {
  return decimal(rows.reduce((n,r) => n + cents(r[field]), 0n));
}
export const balanced = (r: SettlementRow) => cents(r.begin) + cents(r.in) - cents(r.out) === cents(r.end);