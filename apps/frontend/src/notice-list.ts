import { ApiError, assertAmountText, cents, record, requestJson } from './api';

export interface NoticeRow {
  notice_id: number; doc_date: string; bill_no: string; project_display: string; project_name: string; ownership_id: number | null;
  category: string; category_label: string; bill_name: string; biz_type: string; payee: string; jc_supplier: string; input_by: string;
  approve_status: string; pay_status: string; amount_approved: string; amount_paid: string; pay_amount: string; stat_settle: string; stat_paid: string;
  planned_pay_method: string; pay_block_reason: string;
  is_excluded: boolean; exclude_source: string; exclude_rule_hint: string; is_revoked: boolean; is_manual: boolean; is_overpaid: boolean; has_link: boolean; has_any_flow: boolean; edited_fields: string[];
}

export const moneyKeys = ['amount_approved', 'pay_amount', 'amount_paid', 'stat_settle', 'stat_paid'] as const;
export type MoneyKey = typeof moneyKeys[number];

export function readNotices(value: unknown): NoticeRow[] {
  if (!record(value) || !Array.isArray(value.items)) throw new ApiError('通知书列表读取不完整，请重试。');
  return value.items.map((row: unknown) => {
    if (!record(row) || !Number.isSafeInteger(row.notice_id) || !['doc_date','bill_no','project_display','project_name','category','category_label','bill_name','biz_type','payee','jc_supplier','input_by','approve_status','pay_status','exclude_source','exclude_rule_hint','planned_pay_method','pay_block_reason'].every(key => typeof row[key] === 'string') || !['is_excluded','is_revoked','is_manual','is_overpaid','has_link','has_any_flow'].every(key => typeof row[key] === 'boolean') || !Array.isArray(row.edited_fields) || !(row.ownership_id === null || Number.isSafeInteger(row.ownership_id))) throw new ApiError('通知书列表读取不完整，请重试。');
    for (const key of moneyKeys) assertAmountText(row[key]);
    return row as unknown as NoticeRow;
  });
}
export const noticeListQuery = {
  queryKey: ['notices'] as const,
  queryFn: async ({ signal }: { signal: AbortSignal }) => readNotices(await requestJson('/api/m03/notice-list?period=', { signal })),
};

export function live(row: NoticeRow): boolean { return !row.is_excluded && (!row.is_revoked || cents(row.amount_paid) > 0n || row.has_link); }
