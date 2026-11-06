import { ApiError, cents, confirmWrite, decimal, record } from './api';
import Decimal from 'decimal.js';
export { body, cents, decimal, money } from './api';
export interface NoticeRow {
  notice_id: number; doc_date: string; bill_no: string; project_display: string; project_name: string; ownership_id: number | null;
  category: string; category_label: string; bill_name: string; biz_type: string; payee: string; jc_supplier: string; input_by: string;
  approve_status: string; pay_status: string; amount_approved: string; amount_paid: string; pay_amount: string; stat_settle: string; stat_paid: string;
  planned_pay_method: string; pay_block_reason: string;
  is_excluded: boolean; exclude_source: string; exclude_rule_hint: string; is_revoked: boolean; is_manual: boolean; is_overpaid: boolean; has_link: boolean; has_any_flow: boolean; edited_fields: string[];
}
export const categories: Record<string, string> = { material: '辅材', mechanical: '机械', jc: '集采' };
export const moneyKeys = ['amount_approved', 'pay_amount', 'amount_paid', 'stat_settle', 'stat_paid'] as const;
export type MoneyKey = typeof moneyKeys[number];
export type NoticeAmountField = 'amount_approved' | 'stat_settle' | 'stat_paid';
export const noticeAmountLabels: Record<NoticeAmountField, string> = { amount_approved: '审批金额', stat_settle: '统计结算金额', stat_paid: '统计付款金额' };
export function noticeAmountMatches(input: string, actual: string) {
  try {
    const value = new Decimal(input.trim().replace(/[,，]/g, ''));
    return value.isFinite() && value.toDecimalPlaces(2, Decimal.ROUND_HALF_UP).equals(actual);
  } catch { return false; }
}
export function confirmNoticeAmount(value: unknown, id: number, field: NoticeAmountField) {
  const common = record(value) && value.ok === true && typeof value.message === 'string';
  if (field === 'amount_approved') {
    confirmWrite(common && value.row_id === String(id), '审批金额保存回执未能核对，请重读，勿重复保存。');
    return;
  }
  const changed = common && typeof value.changed === 'boolean' && (!value.changed || value.notice_id === id && value.field === field && typeof value.before === 'string' && typeof value.after === 'string' && typeof value.label === 'string');
  confirmWrite(changed, '统计金额保存回执未能核对，请重读，勿重复保存。');
  if (record(value) && value.changed) {
    try { cents(String(value.before)); cents(String(value.after)); }
    catch { confirmWrite(false, '统计金额回执中的金额未能核对，请重读，勿重复保存。'); }
  }
}
export function readNotices(value: unknown): NoticeRow[] {
  if (!record(value) || !Array.isArray(value.items)) throw new ApiError('通知书列表读取不完整，请重试。');
  return value.items.map((row: unknown) => {
    if (!record(row) || !Number.isSafeInteger(row.notice_id) || !['doc_date','bill_no','project_display','project_name','category','category_label','bill_name','biz_type','payee','jc_supplier','input_by','approve_status','pay_status','exclude_source','exclude_rule_hint','planned_pay_method','pay_block_reason'].every(key => typeof row[key] === 'string') || !['is_excluded','is_revoked','is_manual','is_overpaid','has_link','has_any_flow'].every(key => typeof row[key] === 'boolean') || !Array.isArray(row.edited_fields) || !(row.ownership_id === null || Number.isSafeInteger(row.ownership_id))) throw new ApiError('通知书列表读取不完整，请重试。');
    for (const key of moneyKeys) { if (typeof row[key] !== 'string') throw new ApiError('金额读取不完整，请重试。'); cents(row[key]); }
    return row as unknown as NoticeRow;
  });
}
export function live(row: NoticeRow): boolean { return !row.is_excluded && (!row.is_revoked || cents(row.amount_paid) > 0n || row.has_link); }
export function selectable(row: NoticeRow): boolean { return !row.is_revoked || row.is_excluded; }
export function archiveLabel(row: NoticeRow): string { return row.is_excluded ? row.exclude_source === 'manual' ? '手动剔除' : row.exclude_source === 'rule' ? '自动剔除' : '已剔除（来源未知）' : row.is_revoked ? 'i8 已撤单' : ''; }
export function total(rows: NoticeRow[], key: MoneyKey): string { return decimal(rows.reduce((sum, row) => sum + cents(row[key]), 0n)); }
export function searchKey(value: string): string { return value.toLocaleLowerCase().replace(/[,，\s]/g, ''); }
export { currentMonth } from './business-time';
export function receipt(value: unknown): string { if (!record(value) || typeof value.message !== 'string') throw new ApiError('操作回执不完整，请重新读取列表核对。'); return value.message.replace(/<[^>]*>/g, '').replace(/\*\*/g, ''); }

export function matchNoticeCodes(raw: string, rows: NoticeRow[]) {
  const tokens = raw.split(/[\s,，;；、]+/).filter(Boolean), counts = new Map<string,number>(), byCode = new Map<string,NoticeRow[]>();
  const result = { total: tokens.length, ids: [] as number[], invalid: [] as string[], missing: [] as string[], ambiguous: [] as string[], duplicates: [] as string[], paid: [] as string[], blocked: [] as NoticeRow[] };
  for (const token of tokens) {
    const code = token.replace(/^["“](.+)["”]$/, '$1').toUpperCase();
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
