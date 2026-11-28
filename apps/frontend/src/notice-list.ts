import * as v from 'valibot';
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

const safeInteger = v.pipe(v.number(), v.safeInteger());
const notice = v.looseObject({
  notice_id: safeInteger, ownership_id: v.nullable(safeInteger),
  ...v.entriesFromList(['doc_date', 'bill_no', 'project_display', 'project_name', 'category', 'category_label',
    'bill_name', 'biz_type', 'payee', 'jc_supplier', 'input_by', 'approve_status', 'pay_status',
    'exclude_source', 'exclude_rule_hint', 'planned_pay_method', 'pay_block_reason'], v.string()),
  ...v.entriesFromList(['is_excluded', 'is_revoked', 'is_manual', 'is_overpaid', 'has_link', 'has_any_flow'], v.boolean()),
  edited_fields: v.array(v.string()),
});
export function readNotices(value: unknown): NoticeRow[] {
  if (!record(value) || !Array.isArray(value.items)) throw new ApiError('通知书列表读取不完整，请重试。');
  return value.items.map((row: unknown) => {
    if (!v.is(notice, row)) throw new ApiError('通知书列表读取不完整，请重试。');
    const {amount_approved, amount_paid, pay_amount, stat_settle, stat_paid} = row;
    assertAmountText(amount_approved);
    assertAmountText(amount_paid);
    assertAmountText(pay_amount);
    assertAmountText(stat_settle);
    assertAmountText(stat_paid);
    return {...row, amount_approved, amount_paid, pay_amount, stat_settle, stat_paid};
  });
}
export const noticeListQuery = {
  queryKey: ['notices'] as const,
  queryFn: async ({ signal }: { signal: AbortSignal }) => readNotices(await requestJson('/api/m03/notice-list?period=', { signal })),
};

export function live(row: NoticeRow): boolean { return !row.is_excluded && (!row.is_revoked || cents(row.amount_paid) > 0n || row.has_link); }
