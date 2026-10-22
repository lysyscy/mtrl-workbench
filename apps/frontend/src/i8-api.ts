import { ApiError, record, requestJson } from './api';

export type I8Action = { kind: 'notices'; month: string } | { kind: 'warehouses' | 'common-projects' };
export const sourceNames = { notices: '付款通知书', settlement: '收发结存表', inventory: '库存单据明细表', contracts: '采购合同信息', warehouses: '仓库列表', 'common-projects': '常用项目列表' };
export function actionLabel(action: I8Action): string {
  return action.kind === 'notices' ? `抓取付款通知书 · ${action.month}` : `同步${sourceNames[action.kind]}`;
}
export function readAction(value: unknown): I8Action | null {
  if (!record(value)) return null;
  if (value.kind === 'notices' && typeof value.month === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(value.month)) return { kind: 'notices', month: value.month };
  return value.kind === 'warehouses' || value.kind === 'common-projects' ? { kind: value.kind } : null;
}
export interface I8Config { base_url: string; source: 'page' | 'environment'; i8_user: string; ready: boolean; message: string }
export function readConfig(value: unknown, account: string): I8Config {
  if (!record(value) || value.account !== account || typeof value.base_url !== 'string' || !['page', 'environment'].includes(String(value.source)) || typeof value.i8_user !== 'string' || typeof value.ready !== 'boolean' || typeof value.message !== 'string') throw new ApiError('i8 配置读取不完整或账号已变化，请重新核实账号后重试。');
  return value as unknown as I8Config;
}
export interface FetchPlan { year_month: string; start_date: string; end_date: string }
export function readPlan(value: unknown, month: string): FetchPlan {
  if (!record(value) || value.year_month !== month || typeof value.start_date !== 'string' || typeof value.end_date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value.start_date) || !/^\d{4}-\d{2}-\d{2}$/.test(value.end_date) || value.manual_only !== true) throw new ApiError('抓取月份换算不完整，请核对月份后重试。');
  return { year_month: month, start_date: value.start_date, end_date: value.end_date };
}
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
export async function executeI8(action: I8Action, account: string, allowKick: boolean): Promise<{ message: string; partial: boolean }> {
  const init = { method: 'POST', headers: { 'Content-Type': 'application/json' } };
  if (action.kind === 'notices') {
    const value = await requestJson('/api/m03/notices/fetch', { ...init, body: JSON.stringify({ year_month: action.month, allow_kick: allowKick, expected_account: account }) });
    if (!record(value) || value.year_month !== action.month || ![value.fetched, value.upserted].every(n => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0) || !Array.isArray(value.ignored)) throw new ApiError('抓取回执不完整，请先核对执行记录。');
    const ignored = value.ignored.length;
    return { message: `抓到 ${value.fetched} 条，新增或更新 ${value.upserted} 条${ignored ? `，${ignored} 条归属未确定，请在项目档案中处理后重新抓取` : '。'}`, partial: ignored > 0 };
  }
  const query = new URLSearchParams({ allow_kick: String(allowKick), expected_account: account });
  const value = await requestJson(`/api/m02/sync/${action.kind}?${query}`, { ...init, body: '{}' });
  if (!record(value) || typeof value.degraded !== 'boolean' || typeof value.count !== 'number' || !Number.isSafeInteger(value.count) || value.count < 0) throw new ApiError('同步回执不完整，请先核对执行记录。');
  if (value.degraded) throw new ApiError('本次同步未完成，请查看执行记录，核对 i8 配置及网络后重新准备。', 400, 'external_service');
  return { message: `${sourceNames[action.kind]}同步完成，共 ${value.count} 条。`, partial: false };
}
