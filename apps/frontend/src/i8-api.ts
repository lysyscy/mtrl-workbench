import { ApiError, record } from './api';

export const sourceNames = { notices: '付款通知书', settlement: '收发结存表', inventory: '库存单据明细表', contracts: '采购合同信息', warehouses: '仓库列表', 'common-projects': '常用项目列表' };
export interface RunRecord { id: number; run_type: string; target: string; status: string; success_count: number; fail_count: number; error_message: string; started_at: string; finished_at: string | null; triggered_by: string; duration_seconds: number | null }
export function readRecords(value: unknown): RunRecord[] {
  if (!Array.isArray(value)) throw new ApiError('执行记录读取不完整，请重试。');
  return value.map((row: unknown) => {
    if (!record(row) || typeof row.id !== 'number' || !Number.isSafeInteger(row.id) || !['run_type', 'target', 'status', 'error_message', 'started_at', 'triggered_by'].every(key => typeof row[key] === 'string') || ![row.success_count, row.fail_count].every(n => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0) || (row.finished_at !== null && typeof row.finished_at !== 'string') || (row.duration_seconds !== null && (typeof row.duration_seconds !== 'number' || !Number.isFinite(row.duration_seconds) || row.duration_seconds < 0))) throw new ApiError('执行记录读取不完整，请重试。');
    return row as unknown as RunRecord;
  });
}
export function recordSource(row: RunRecord): keyof typeof sourceNames | null {
  const target = row.target.trim();
  if (row.run_type === 'sync') return target === '仓库列表' ? 'warehouses' : target === '常用项目列表' ? 'common-projects' : null;
  if (row.run_type !== 'fetch') return null;
  if (/^\d{4}-\d{2}$/.test(target) || target.startsWith('付款通知书 ')) return 'notices';
  if (/^(setl |收发结存表)/.test(target)) return 'settlement';
  if (/^(inv |库存单据明细表)/.test(target)) return 'inventory';
  return target.includes('采购合同') ? 'contracts' : null;
}
export function recordScope(row: RunRecord): string {
  if (row.run_type === 'sync') return '—';
  return row.target.replace(/^(inv|setl|付款通知书) /, '');
}
export function recordLabel(row: RunRecord): string {
  const source = recordSource(row);
  if (source) return `${row.run_type === 'sync' ? '同步' : '抓取'}${sourceNames[source]}`;
  return ({ print: '批量打印', export_pdf: '只导出 PDF', fetch: '抓取', sync: '同步 i8 名单' } as Record<string, string>)[row.run_type] ?? row.run_type;
}
export function duration(row: RunRecord): string {
  if (row.duration_seconds === null) return '—';
  return `${row.duration_seconds < 10 ? row.duration_seconds.toFixed(2) : row.duration_seconds.toFixed(1)} 秒`;
}
