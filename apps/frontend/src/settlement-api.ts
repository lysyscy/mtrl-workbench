import { ApiError, record, requestJson } from './api';

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
export function readSettlement(value: unknown, ym: string): Settlement {
  if (!record(value) || value.ym !== ym || !Array.isArray(value.rows) || !record(value.counts) ||
      ![value.counts.warehouses,value.counts.rows,value.counts.files].every(integer) || typeof value.balance_ok !== 'boolean') throw invalid();
  for (const r of value.rows) if (!record(r) || typeof r.id !== 'string' || !r.id || r.name !== r.id || !integer(r.rows) ||
      !['begin','in','out','end'].every(k => numeric(r[k]))) throw invalid();
  if (new Set(value.rows.map(r => r.id)).size !== value.rows.length) throw invalid();
  return value as unknown as Settlement;
}
export function readExtract(value: unknown, year: string): ExtractData {
  if (!record(value) || !record(value.annual) || !record(value.balances)) throw invalid();
  for (const kind of kinds) {
    const grid = value.annual[kind], balances = value.balances[kind];
    if (!record(grid) || grid.kind !== kind || grid.year !== year || !Array.isArray(grid.months) || grid.months.length !== 12 ||
        grid.months.some((m, i) => m !== `${year}-${String(i + 1).padStart(2,'0')}`) || !Array.isArray(grid.rows) ||
        !Array.isArray(grid.sum_row) || grid.sum_row.length !== 14 || !grid.sum_row.every(amount) ||
        !record(balances) || !Object.values(balances).every(amount)) throw invalid();
    for (const row of grid.rows) if (!record(row) || typeof row.warehouse !== 'string' || !row.warehouse ||
        ![row.prior,row.balance,row.total].every(amount) || !Array.isArray(row.cells) || row.cells.length !== 12 || !row.cells.every(amount)) throw invalid();
    if (new Set(grid.rows.map(r => r.warehouse)).size !== grid.rows.length) throw invalid();
  }
  return value as unknown as ExtractData;
}
export const getSettlement = async (ym: string, signal?: AbortSignal) => readSettlement(await requestJson(`/api/m07/settlement?${new URLSearchParams({ period: ym })}`, signal ? { signal } : {}), ym);
export const getExtract = async (year: string, status: string, signal?: AbortSignal) => readExtract(await requestJson(`/api/m07/extract?${new URLSearchParams({ year, status })}`, signal ? { signal } : {}), year);
export async function saveBalance(kind: ExtractKind, warehouse: string, raw: string, signal: AbortSignal) {
  const value = await requestJson('/api/m07/extract/balance', { method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, warehouse, raw }) });
  // This existing endpoint returns Decimal values as JSON numbers, and null when cleared.
  if (!record(value) || value.ok !== true || !(amount(value.value) || typeof value.value === 'number' && Number.isFinite(value.value))) throw new ApiError('保存回执未确认，请重读核对，勿重复提交。', 0, 'invalid_response');
}
export const uncertainBalance = (e: unknown) => !(e instanceof ApiError) || !e.status || e.status >= 500 || e.code === 'invalid_response';
const cents = (value: string) => { const [whole, fraction = ''] = value.split('.'); return BigInt(`${whole}${fraction.padEnd(2,'0')}`); };
export function settlementTotal(rows: SettlementRow[], field: 'begin' | 'in' | 'out' | 'end') {
  const value = rows.reduce((n,r) => n + cents(r[field]), 0n), digits = String(value < 0n ? -value : value).padStart(3,'0');
  return `${value < 0n ? '-' : ''}${digits.slice(0,-2)}.${digits.slice(-2)}`;
}
export const balanced = (r: SettlementRow) => cents(r.begin) + cents(r.in) - cents(r.out) === cents(r.end);