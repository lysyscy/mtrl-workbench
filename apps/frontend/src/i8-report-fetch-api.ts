import { ApiError, record } from './api';
import { readFetchReceipt } from './i8-api';
import type { FetchReceipt } from './i8-api';

export type ReportSource = 'inventory' | 'settlement';
export const reportFetch = {
  inventory: {title: '库存单据', path: '/api/m08/fetch', preserved: 'kept_with_adjustment',
    scope: '全项目按核算月抓取，不受页面筛选限制；重抓保留调整单。'},
  settlement: {title: '收发结存', path: '/api/m07/fetch', preserved: 'kept_manual',
    scope: '按核算月抓取全部已配置 i8 编号的项目；同键自动明细更新为本次来源，手工行保留。'},
} as const;

export function readReportFetchResult(source: ReportSource, month: string, value: unknown): FetchReceipt {
  const invalid = () => new ApiError('抓取回执不完整，请到执行记录核对，勿重复抓取。', 0, 'invalid_response');
  // requestJson owns explicit ok:false responses (including empty/degraded reports).
  if (!record(value) || value.ym !== month || value.ok !== true) throw invalid();
  const spec = reportFetch[source], stats = value.stats;
  const count = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
  if (!count(value.rows) || !record(stats) || !['inserted', 'updated', 'deleted', spec.preserved].every(key => count(stats[key]))) throw invalid();
  if (value.receipt != null) {
    const receipt = readFetchReceipt(value.receipt, source);
    if (receipt.status === 'success' && (receipt.scope === month || receipt.scope.startsWith(month + '（'))) return receipt;
    throw invalid();
  }
  const recovery = record(value.recovery) ? value.recovery : {};
  const items = Array.isArray(recovery.unresolved_items) ? recovery.unresolved_items.filter(record) : null;
  const message = typeof recovery.message === 'string' ? recovery.message : '';
  return {
    source, scope: month, status: 'success', startedAt: '', duration: null,
    summary: { ...stats, total: value.rows, unsettled: recovery.unresolved ?? items?.length },
    items, warning: recovery.degraded ? message : '', note: recovery.degraded ? '' : message,
  };
}
