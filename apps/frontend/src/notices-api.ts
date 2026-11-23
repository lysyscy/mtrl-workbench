import { ApiError, body, cents, confirmWrite, decimal, record, requestJson } from './api';
import Decimal from 'decimal.js';
import type { GridApi } from 'ag-grid-community';
import type { MoneyKey, NoticeRow } from './notice-list';
export type { MoneyKey, NoticeRow } from './notice-list';
export { live, moneyKeys, readNotices } from './notice-list';
export { body, cents, decimal, money } from './api';
export const categories: Record<string, string> = { material: '辅材', mechanical: '机械', jc: '集采' };
export type NoticeAmountField = 'amount_approved' | 'stat_settle' | 'stat_paid';
export const noticeAmountLabels: Record<NoticeAmountField, string> = { amount_approved: '审批金额', stat_settle: '统计结算金额', stat_paid: '统计付款金额' };
export function noticeAmountMatches(input: string, actual: string) {
  try {
    const value = new Decimal(input.trim().replace(/[,，]/g, ''));
    return value.isFinite() && value.toDecimalPlaces(2, Decimal.ROUND_HALF_UP).equals(actual);
  } catch { return false; }
}
export function confirmNoticeAmount(value: unknown, id: number, field: NoticeAmountField) {
  const common = record(value) && value.ok === true && value.notice_id === id && value.field === field && typeof value.message === 'string';
  const valid = common && typeof value.changed === 'boolean' && (!value.changed || typeof value.before === 'string' && typeof value.after === 'string' && typeof value.label === 'string');
  confirmWrite(valid, '金额保存回执未能核对，请重读，勿重复保存。');
  if (record(value) && value.changed) {
    try { cents(String(value.before)); cents(String(value.after)); }
    catch { confirmWrite(false, '金额回执中的金额未能核对，请重读，勿重复保存。'); }
  }
}
export async function saveNoticeAmount(id: number, field: NoticeAmountField, value: string, signal?: AbortSignal) {
  const result = await requestJson('/api/m03/actions/amount', {method: 'POST', ...(signal ? {signal} : {}), ...body({notice_id: id, field, value})});
  confirmNoticeAmount(result, id, field);
}
export function selectable(row: NoticeRow): boolean { return !row.is_revoked || row.is_excluded; }
export function archiveLabel(row: NoticeRow): string { return row.is_excluded ? row.exclude_source === 'manual' ? '手动剔除' : row.exclude_source === 'rule' ? '自动剔除' : '已剔除（来源未知）' : row.is_revoked ? 'i8 已撤单' : ''; }
export function total(rows: NoticeRow[], key: MoneyKey): string { return decimal(rows.reduce((sum, row) => sum + cents(row[key]), 0n)); }
export function searchKey(value: string): string { return value.toLocaleLowerCase().replace(/[,，\s]/g, ''); }
export { currentMonth } from './business-time';
export function receipt(value: unknown): string { if (!record(value) || typeof value.message !== 'string') throw new ApiError('操作回执不完整，请重新读取列表核对。'); return value.message.replace(/<[^>]*>/g, '').replace(/\*\*/g, ''); }

export function matchNoticeCodes(raw: string, rows: NoticeRow[]) {
  const tokens = raw.split(/[\s,，;；、/／\\|]+/).filter(Boolean), counts = new Map<string,number>(), byCode = new Map<string,NoticeRow[]>();
  const result = { total: tokens.length, ids: [] as number[], invalid: [] as string[], missing: [] as string[], ambiguous: [] as string[], duplicates: [] as string[], paid: [] as string[], blocked: [] as NoticeRow[] };
  for (const token of tokens) {
    const code = token
      .replace(/^["“'‘(（\[【]+/, '')
      .replace(/["”'’)）\]】]+$/, '')
      .toUpperCase();
    if (!/^FKTZS\d{4}(?:0[1-9]|1[0-2])\d{4}$/.test(code)) result.invalid.push(token);
    else counts.set(code, (counts.get(code) ?? 0) + 1);
  }
  for (const row of rows) { const code = row.bill_no.trim().toUpperCase(); byCode.set(code, [...(byCode.get(code) ?? []), row]); }
  for (const [code,count] of counts) {
    if (count > 1) result.duplicates.push(`${code}（${count}次）`);
    const hits = byCode.get(code) ?? [];
    if (!hits.length) result.missing.push(code);
    else if (hits.length > 1) { result.ambiguous.push(`${code}（系统${hits.length}条）`); result.blocked.push(...hits.filter(row => row.is_excluded || row.is_revoked)); }
    else { const row = hits[0]!; if (row.is_excluded || row.is_revoked) result.blocked.push(row); else { result.ids.push(row.notice_id); if (row.pay_status === '已付清') result.paid.push(code); } }
  }
  return result;
}

export function prioritizeNoticeRows<Row>(rows: Row[], ids: ReadonlySet<number>, idOf: (row: Row) => number | undefined): void {
  if (!ids.size) return;
  const positions = new Map<number | undefined, number>();
  for (const id of ids) positions.set(id, positions.size);
  const position = (row: Row) => positions.get(idOf(row)) ?? positions.size;
  rows.sort((a, b) => position(a) - position(b));
}

export function noticePrintRows(
  selected: readonly NoticeRow[],
  pasteOrder: ReadonlySet<number>,
  grid: Pick<GridApi<NoticeRow>, 'forEachNodeAfterFilterAndSort'> | null,
): NoticeRow[] {
  const order = new Set(pasteOrder);
  grid?.forEachNodeAfterFilterAndSort(({data}) => {
    if (data) order.add(data.notice_id);
  });
  const rows = [...selected];
  prioritizeNoticeRows(rows, order, row => row.notice_id);
  return rows;
}
