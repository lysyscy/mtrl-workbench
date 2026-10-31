import { ApiError, body, cents, confirmWrite, record, requestJson } from './api';

export interface OilEntry {
  id: number; request_id: string; version: string; kind: 'recharge' | 'adjustment' | 'refund' | 'transfer_out' | 'transfer_in';
  project_id: number; account_id: number; card_id: number | null; date_text: string; entry_date: string | null;
  amount: string; remark: string; related_entry_id: number | null; transfer_id: string | null;
}
export const oilEntryKindLabels: Record<OilEntry['kind'], string> = { recharge: '充值', adjustment: '调整', refund: '退款', transfer_out: '转出', transfer_in: '转入' };
export const isOilTransfer = (row: OilEntry) => row.kind === 'transfer_out' || row.kind === 'transfer_in';
export interface OilLedger { entries: OilEntry[]; total_amount: string }
export interface OilReconciliationRow { account_id: number; project_id: number; card_id: number | null; primary_card_id: number | null; current: boolean; recharge_amount: string; opening_amount: string; total_amount: string }
export interface OilReconciliation { rows: OilReconciliationRow[]; total_amount: string }
export type EntryFields = Pick<OilEntry, 'kind' | 'project_id' | 'account_id' | 'date_text' | 'amount' | 'remark'>;
export type OilAttributionFields = Pick<OilEntry, 'project_id' | 'account_id' | 'card_id'>;
const id = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v > 0;
const nullableId = (v: unknown) => v === null || id(v);
const moneyText = (v: unknown): v is string => typeof v === 'string' && /^-?\d+\.\d{2}$/.test(v);
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(v);
export function readOilEntry(v: unknown): OilEntry {
  if (!record(v) || !id(v.id) || !uuid(v.request_id) || !uuid(v.version) || !id(v.project_id) || !id(v.account_id) || !nullableId(v.card_id) || !nullableId(v.related_entry_id) ||
    typeof v.date_text !== 'string' || !(v.entry_date === null || typeof v.entry_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v.entry_date)) || !moneyText(v.amount) || typeof v.remark !== 'string' ||
    !['recharge', 'adjustment', 'refund', 'transfer_out', 'transfer_in'].includes(String(v.kind)) ||
    !(v.transfer_id === null || uuid(v.transfer_id)) ||
    v.kind === 'recharge' && (cents(v.amount) <= 0n || v.related_entry_id !== null || v.transfer_id !== null) ||
    v.kind === 'adjustment' && (v.related_entry_id !== null || v.transfer_id !== null) ||
    v.kind === 'refund' && (cents(v.amount) >= 0n || !id(v.related_entry_id) || v.transfer_id !== null) ||
    (v.kind === 'transfer_out' || v.kind === 'transfer_in') && (v.related_entry_id !== null || !uuid(v.transfer_id) || (v.kind === 'transfer_out' ? cents(v.amount) >= 0n : cents(v.amount) <= 0n))) throw new ApiError('充值记录读取不完整，请重读核对。');
  return v as unknown as OilEntry;
}
export function readOilLedger(v: unknown): OilLedger {
  if (!record(v) || !Array.isArray(v.entries) || !moneyText(v.total_amount)) throw new ApiError('充值台账读取不完整，请重读核对。');
  const entries = v.entries.map(readOilEntry);
  const transfers = new Map<string, OilEntry[]>();
  for (const entry of entries) if (entry.transfer_id) transfers.set(entry.transfer_id, [...(transfers.get(entry.transfer_id) ?? []), entry]);
  for (const pair of transfers.values()) readOilTransferPair(pair);
  if (new Set(entries.map(e => e.id)).size !== entries.length || new Set(entries.map(e => e.request_id)).size !== entries.length || entries.reduce((total, row) => total + cents(row.amount), 0n) !== cents(v.total_amount)) throw new ApiError('充值台账合计未能核对，请重读。');
  return { entries, total_amount: v.total_amount };
}
function readOilTransferPair(rows: OilEntry[]): [OilEntry, OilEntry] {
  const out = rows.find(row => row.kind === 'transfer_out'), incoming = rows.find(row => row.kind === 'transfer_in');
  if (rows.length !== 2 || !out || !incoming || !out.transfer_id || out.transfer_id !== incoming.transfer_id ||
    out.version !== incoming.version || out.date_text !== incoming.date_text || out.entry_date !== incoming.entry_date ||
    out.account_id === incoming.account_id || cents(out.amount) + cents(incoming.amount) !== 0n) throw new ApiError('转账两端未能一致核对，请重读，勿重复转账。');
  return [out, incoming];
}
export function readOilReconciliation(v: unknown): OilReconciliation {
  if (!record(v) || !Array.isArray(v.rows) || !moneyText(v.total_amount) || !v.rows.every(row => record(row) && id(row.account_id) && id(row.project_id) && nullableId(row.card_id) && nullableId(row.primary_card_id) && typeof row.current === 'boolean' && moneyText(row.recharge_amount) && moneyText(row.opening_amount) && moneyText(row.total_amount) && cents(row.recharge_amount) + cents(row.opening_amount) === cents(row.total_amount))) throw new ApiError('账户充值核对读取不完整，请重读。');
  const rows = v.rows as OilReconciliationRow[];
  if (new Set(rows.map(row => `${row.account_id}:${row.project_id}:${row.card_id}`)).size !== rows.length || rows.reduce((total, row) => total + cents(row.total_amount), 0n) !== cents(v.total_amount)) throw new ApiError('账户累计未能核对，请重读。');
  return { rows, total_amount: v.total_amount };
}
export async function getOilLedger(signal?: AbortSignal) { return readOilLedger(await requestJson('/api/m13/ledger', signal ? { signal } : {})); }
export async function getOilReconciliation(signal?: AbortSignal) { return readOilReconciliation(await requestJson('/api/m13/reconciliation', signal ? { signal } : {})); }
export async function saveOilEntry(fields: EntryFields, target: { id: number; version: string } | { request_id: string }, signal: AbortSignal) {
  const result = await requestJson(`/api/m13/ledger/entries${'id' in target ? `/${target.id}` : ''}`, { method: 'id' in target ? 'PUT' : 'POST', signal, ...body({ ...fields, ...('id' in target ? { version: target.version } : target) }) });
  confirmWrite(record(result) && result.ok === true, '充值保存回执待核实，请重读，勿重复提交。');
  const row = readOilEntry((result as Record<string, unknown>).item);
  confirmWrite(('id' in target ? row.id === target.id : row.request_id === target.request_id) && row.kind === fields.kind && row.account_id === fields.account_id && row.project_id === fields.project_id && row.date_text === fields.date_text && row.remark === fields.remark, '充值保存回执与输入不一致，请重读核对。');
  return row;
}
export async function refundOilEntry(fields: { request_id: string; original_id: number; amount: string; date_text: string; remark: string }, signal: AbortSignal) {
  const result = await requestJson('/api/m13/ledger/refunds', { method: 'POST', signal, ...body(fields) });
  confirmWrite(record(result) && result.ok === true, '退款登记回执待核实，请重读，勿重复办理。');
  const row = readOilEntry((result as Record<string, unknown>).item);
  confirmWrite(row.kind === 'refund' && row.request_id === fields.request_id && row.related_entry_id === fields.original_id && row.date_text === fields.date_text && row.remark === fields.remark, '退款登记回执与输入不一致，请重读核对。');
  return row;
}

export async function correctOilAttribution(fields: OilAttributionFields, target: OilEntry, signal: AbortSignal) {
  const result = await requestJson(`/api/m13/ledger/entries/${target.id}/attribution`, { method: 'PUT', signal, ...body({ ...fields, version: target.version }) });
  confirmWrite(record(result) && result.ok === true, '历史关联更正回执待核实，请重读，勿重复提交。');
  const row = readOilEntry((result as Record<string, unknown>).item);
  confirmWrite(Object.entries({ ...target, ...fields }).every(([key, value]) => key === 'version' || row[key as keyof OilEntry] === value), '历史关联更正回执与输入不一致，请重读核对。');
  return row;
}

export interface OilTransferFields { request_id: string; out_project_id: number; out_account_id: number; in_project_id: number; in_account_id: number; amount: string; date_text: string; out_remark: string; in_remark: string }
export async function transferOilEntries(fields: OilTransferFields, signal: AbortSignal) {
  const result = await requestJson('/api/m13/ledger/transfers', { method: 'POST', signal, ...body(fields) });
  confirmWrite(record(result) && result.ok === true && Array.isArray(result.items), '转账保存回执待核实，请重读，勿重复提交。');
  const rows = readOilTransferPair(((result as Record<string, unknown>).items as unknown[]).map(readOilEntry));
  const [out, incoming] = rows;
  confirmWrite(out.transfer_id === fields.request_id && out.project_id === fields.out_project_id && out.account_id === fields.out_account_id &&
    incoming.project_id === fields.in_project_id && incoming.account_id === fields.in_account_id && out.date_text === fields.date_text &&
    out.remark === fields.out_remark && incoming.remark === fields.in_remark, '转账回执与本次输入不一致，请重读核对。');
  return rows;
}
