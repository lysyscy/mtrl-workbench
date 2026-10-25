import { ApiError, body, confirmWrite, record, requestJson } from './api';

export type Category = 'material' | 'mechanical';
export type Field = 'month' | 'other_expense' | 'payment' | 'remark';
export interface LedgerRow {
  key: string; category: Category; seq: number; month: string; month_label: string;
  row_kind: 'manual' | 'month' | 'undated'; record_id: number | null;
  other_expense: string; payment: string; debt: string; remark: string;
  token: string; editable: boolean; counts_in_total: boolean;
}
export interface LedgerSide { category: Category; label: string; rows: LedgerRow[] }
export interface Ledger { project_id: number; sides: LedgerSide[] }
const money = /^-?\d+\.\d{2}$/;
const invalid = () => new ApiError('台账结果不完整，请刷新重试；仍失败请联系维护人员。');
export function readLedger(value: unknown, project: number): Ledger {
  if (!record(value) || value.project_id !== project || !Array.isArray(value.sides) || value.sides.length !== 2) throw invalid();
  const sides = value.sides.map((side: unknown): LedgerSide => {
    if (!record(side) || (side.category !== 'material' && side.category !== 'mechanical') || typeof side.label !== 'string' || !Array.isArray(side.rows)) throw invalid();
    const category = side.category;
    const rows = side.rows.map((row: unknown): LedgerRow => {
      if (!record(row) || typeof row.seq !== 'number' || !Number.isInteger(row.seq) || typeof row.month !== 'string' || (row.month !== '' && !/^\d{4}-(0[1-9]|1[0-2])$/.test(row.month)) || typeof row.month_label !== 'string' || !['manual', 'month', 'undated'].includes(String(row.row_kind)) || (row.record_id !== null && (typeof row.record_id !== 'number' || !Number.isInteger(row.record_id))) || typeof row.token !== 'string' || !row.token || typeof row.editable !== 'boolean' || typeof row.counts_in_total !== 'boolean' || typeof row.remark !== 'string') throw invalid();
      for (const field of ['other_expense', 'payment', 'debt']) if (typeof row[field] !== 'string' || !money.test(row[field])) throw invalid();
      if (row.row_kind === 'manual' && row.record_id === null) throw invalid();
      return {
        key: `${category}:${row.row_kind}:${row.row_kind === 'manual' ? row.record_id : row.month}`,
        category, seq: row.seq, month: row.month, month_label: row.month_label,
        row_kind: row.row_kind as LedgerRow['row_kind'], record_id: row.record_id as number | null,
        other_expense: row.other_expense as string, payment: row.payment as string, debt: row.debt as string,
        remark: row.remark, token: row.token, editable: row.editable, counts_in_total: row.counts_in_total,
      };
    });
    if (new Set(rows.map(row => row.key)).size !== rows.length) throw invalid();
    return { category, label: side.label, rows };
  });
  if (new Set(sides.map(side => side.category)).size !== 2) throw invalid();
  return { project_id: project, sides };
}
export async function loadLedger(project: number, end: string, signal: AbortSignal): Promise<Ledger> {
  const result = readLedger(await requestJson(`/api/m05/ledger?${new URLSearchParams({ project_id: String(project), end_ym: end })}`, { signal }), project);
  if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
  return result;
}
export function payload(project: number, row: LedgerRow) {
  return { id: row.record_id, project_id: project, category: row.category,
    entry_kind: row.row_kind === 'manual' ? 'manual' : 'month', cutoff_ym: row.month,
    settle_amount: row.other_expense, paid_amount: row.payment, remark: row.remark, token: row.token };
}
export function editable(row: LedgerRow, field: Field): boolean {
  return Boolean(row.token) && (field === 'remark' || row.editable) && (field !== 'month' || row.row_kind === 'manual') && (field !== 'other_expense' || row.category === 'material');
}
export function amount(value: string): string { return value.replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
export function sum(rows: LedgerRow[], field: 'other_expense' | 'payment' | 'debt'): string {
  const cents = rows.filter(row => row.counts_in_total).reduce((n, row) => n + BigInt(row[field].replace('.', '')), 0n);
  const sign = cents < 0n ? '-' : ''; const digits = String(cents < 0n ? -cents : cents).padStart(3, '0');
  return sign + digits.slice(0, -2) + '.' + digits.slice(-2);
}
export function same(field: Field, a: string, b: string): boolean {
  if (field === 'month') return a === b;
  if (field === 'remark') return a.trim() === b.trim();
  const normalize = (value: string) => {
    const match = /^(-?)(\d+)(?:\.(\d{0,2}))?$/.exec(value.trim().replaceAll(',', ''));
    return match ? BigInt(`${match[1]}${match[2]}${(match[3] ?? '').padEnd(2, '0')}`).toString() : value;
  };
  return normalize(a) === normalize(b);
}

export async function saveLedgerCell(project: number, row: LedgerRow, field: Field, text: string, signal: AbortSignal) {
  const remarkOnly = !row.editable && field === 'remark';
  const result = await requestJson(remarkOnly ? '/m05/ledger/remark' : '/api/m05/history/save', { method: 'POST', signal,
    headers: { 'Content-Type': remarkOnly ? 'application/x-www-form-urlencoded' : 'application/json' },
    body: remarkOnly ? new URLSearchParams({ project_id: String(project), category: row.category, ym: row.month, remark: text.trim(), token: row.token }) : JSON.stringify(payload(project, { ...row, [field]: text })) });
  confirmWrite(record(result) && result.ok === true && (remarkOnly || typeof result.id === 'number' && Number.isSafeInteger(result.id) && result.id > 0), '保存结果未确认，请刷新核对后再试。');
}
export async function deleteLedgerRow(row: LedgerRow, signal: AbortSignal) {
  const result = await requestJson('/api/m05/history/delete', { method: 'POST', signal, ...body({ id: row.record_id, token: row.token }) });
  confirmWrite(record(result) && result.ok === true, '删除结果未确认，请刷新核对，勿重复删除。');
}
export async function addLedgerRow(project: number, signal: AbortSignal): Promise<number> {
  const result = await requestJson('/api/m05/history/save', { method: 'POST', signal, ...body({ project_id: project, category: 'material', entry_kind: 'manual', cutoff_ym: '2025-11', settle_amount: '0', paid_amount: '0', remark: '' }) });
  if (!record(result) || result.ok !== true || typeof result.id !== 'number' || !Number.isSafeInteger(result.id) || result.id <= 0) throw new ApiError('新增结果未确认，请刷新核对后再试。', 0, 'invalid_response');
  return result.id;
}
