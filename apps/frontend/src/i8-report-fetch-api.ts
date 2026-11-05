import { ApiError, record } from './api';

export type ReportSource = 'inventory' | 'settlement';
export const reportFetch = {
  inventory: {title: '库存单据', path: '/api/m08/fetch', preserved: 'kept_with_adjustment', preservedLabel: '保留有调整的源行',
    scope: '全项目按核算月抓取，不受页面筛选限制；重抓保留调整单。'},
  settlement: {title: '收发结存', path: '/api/m07/fetch', preserved: 'kept_manual', preservedLabel: '保留手工行',
    scope: '按核算月抓取全部已配置 i8 编号的项目；同键明细更新为本次来源，未匹配的手工行保留。'},
} as const;

export interface ReportFetchResult { ok: boolean; message: string }
export function readReportFetchResult(source: ReportSource, month: string, value: unknown): ReportFetchResult {
  const invalid = () => new ApiError('抓取回执不完整，请到执行记录核对，勿重复抓取。', 0, 'invalid_response');
  // requestJson owns explicit ok:false responses (including empty/degraded reports).
  if (!record(value) || value.ym !== month || value.ok !== true) throw invalid();
  const spec = reportFetch[source], stats = value.stats;
  const count = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
  if (!count(value.rows) || !record(stats) || !['inserted', 'updated', 'deleted', spec.preserved].every(key => count(stats[key]))) throw invalid();
  const recovery = record(value.recovery) && typeof value.recovery.message === 'string' ? ` ${value.recovery.message}` : '';
  return {ok: true, message: `${month} 抓取 ${value.rows} 行；插入 ${stats.inserted}、更新 ${stats.updated}、删除旧源行 ${stats.deleted}、${spec.preservedLabel} ${stats[spec.preserved]}。${recovery}`};
}
