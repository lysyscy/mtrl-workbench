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
  return target.startsWith('jc_contract ') || target.includes('采购合同') ? 'contracts' : null;
}
export function recordScope(row: RunRecord): string {
  if (row.run_type === 'sync') return '—';
  if (row.target.startsWith('jc_contract ')) {
    const scope = row.target.slice('jc_contract '.length);
    return /^全量(?:（\d+ 条）)?$/.test(scope) ? '范围未记录' : scope;
  }
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

const optionalText = (value: unknown) => typeof value === 'string' ? value : '';

export type ReceiptSource = 'notices' | 'settlement' | 'inventory';

export interface FetchReceipt {
  source: ReceiptSource;
  status: string;
  scope: string;
  startedAt: string;
  duration: number | null;
  summary: Record<string, unknown>;
  items: Record<string, unknown>[] | null;
  warning?: string;
  note?: string;
  error?: string;
}

export function readFetchReceipt(value: unknown, source: ReceiptSource): FetchReceipt {
  if (!record(value) || value.source !== source || typeof value.status !== 'string' || !record(value.summary)) {
    throw new ApiError('抓取回执不完整，请到执行记录核对。', 0, 'invalid_response');
  }
  return {
    source, status: value.status, scope: optionalText(value.scope), startedAt: optionalText(value.started_at),
    duration: typeof value.duration_seconds === 'number' && Number.isFinite(value.duration_seconds) && value.duration_seconds >= 0
      ? value.duration_seconds : null,
    summary: value.summary, items: Array.isArray(value.items) ? value.items.filter(record) : null,
    warning: optionalText(value.warning), note: optionalText(value.note), error: optionalText(value.error_message),
  };
}
