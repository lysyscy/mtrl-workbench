import { ApiError, record } from './api';
export interface NoticeRow {
  notice_id: number; doc_date: string; bill_no: string; project_display: string; project_name: string; ownership_id: number | null;
  category: string; category_label: string; bill_name: string; biz_type: string; payee: string; jc_supplier: string; input_by: string;
  approve_status: string; pay_status: string; amount_approved: string; amount_paid: string; pay_amount: string; stat_settle: string; stat_paid: string;
  planned_pay_method: string; pay_block_reason: string;
  is_excluded: boolean; exclude_source: string; exclude_rule_hint: string; is_revoked: boolean; is_manual: boolean; is_overpaid: boolean; has_link: boolean; edited_fields: string[];
}
export const categories: Record<string, string> = { material: '辅材', mechanical: '机械', jc: '集采' };
export const moneyKeys = ['amount_approved', 'pay_amount', 'amount_paid', 'stat_settle', 'stat_paid'] as const;
export type MoneyKey = typeof moneyKeys[number];
export function cents(value: string): bigint {
  const match = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(value);
  if (!match) throw new ApiError('金额读取不完整，请重试。');
  return (match[1] ? -1n : 1n) * (BigInt(match[2]!) * 100n + BigInt((match[3] ?? '').padEnd(2, '0')));
}
export function decimal(value: bigint): string { const n = value < 0n ? -value : value; return `${value < 0n ? '-' : ''}${n / 100n}.${String(n % 100n).padStart(2, '0')}`; }
export function money(value: string): string { const [whole, part] = decimal(cents(value)).split('.'); return `${whole!.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${part}`; }
export function readNotices(value: unknown): NoticeRow[] {
  if (!record(value) || !Array.isArray(value.items)) throw new ApiError('通知书列表读取不完整，请重试。');
  return value.items.map((row: unknown) => {
    if (!record(row) || !Number.isSafeInteger(row.notice_id) || !['doc_date','bill_no','project_display','project_name','category','category_label','bill_name','biz_type','payee','jc_supplier','input_by','approve_status','pay_status','exclude_source','exclude_rule_hint','planned_pay_method','pay_block_reason'].every(key => typeof row[key] === 'string') || !['is_excluded','is_revoked','is_manual','is_overpaid','has_link'].every(key => typeof row[key] === 'boolean') || !Array.isArray(row.edited_fields) || !(row.ownership_id === null || Number.isSafeInteger(row.ownership_id))) throw new ApiError('通知书列表读取不完整，请重试。');
    for (const key of moneyKeys) { if (typeof row[key] !== 'string') throw new ApiError('金额读取不完整，请重试。'); cents(row[key]); }
    return row as unknown as NoticeRow;
  });
}
export function live(row: NoticeRow): boolean { return !row.is_excluded && (!row.is_revoked || cents(row.amount_paid) > 0n || row.has_link); }
export function selectable(row: NoticeRow): boolean { return !row.is_revoked || row.is_excluded; }
export function archiveLabel(row: NoticeRow): string { return row.is_excluded ? row.exclude_source === 'manual' ? '手动剔除' : row.exclude_source === 'rule' ? '自动剔除' : '已剔除（来源未知）' : row.is_revoked ? 'i8 已撤单' : ''; }
export function total(rows: NoticeRow[], key: MoneyKey): string { return decimal(rows.reduce((sum, row) => sum + cents(row[key]), 0n)); }
export function searchKey(value: string): string { return value.toLocaleLowerCase().replace(/[,，\s]/g, ''); }
export function currentMonth(): string { const p = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' }).formatToParts(new Date()); return `${p.find(x => x.type === 'year')!.value}-${p.find(x => x.type === 'month')!.value}`; }
export const body = (value: unknown) => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });
export function receipt(value: unknown): string { if (!record(value) || typeof value.message !== 'string') throw new ApiError('操作回执不完整，请重新读取列表核对。'); return value.message.replace(/<[^>]*>/g, '').replace(/\*\*/g, ''); }
