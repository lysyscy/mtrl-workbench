import { ApiError, money, record } from './api';
import { isJcRule } from './jc-rule-data';
import type { JcRule } from './jc-rule-data';
import { receiptCount as count } from './i8-receipt-summary';

export interface ReceiptRow {
  id: string;
  contract: string;
  project: string;
  document: string;
  kind: string;
  reason: string;
  matches: JcRule[];
}

const ownershipReason: Record<string, string> = {
  needs_keyword: '缺少小微识别词',
  needs_choice: '命中多个项目',
  not_archived: '项目未建档',
};

function receiptRowKey(fields: string[], occurrences: Map<string, number>): string {
  // constraint: AG Grid escapes HTML characters in rendered row IDs.
  const key = encodeURIComponent(JSON.stringify(fields)).replaceAll("'", '%27');
  const occurrence = (occurrences.get(key) ?? 0) + 1;
  occurrences.set(key, occurrence);
  return occurrence === 1 ? key : `${key}:${occurrence}`;
}

function readMatchedItems(value: unknown) {
  if (!Array.isArray(value)) return null;
  const occurrences = new Map<string, number>();
  return value.flatMap(row => {
    if (!record(row) || typeof row.contract_no !== 'string' || !row.contract_no.trim()
      || (row.status !== 'inserted' && row.status !== 'updated' && row.status !== 'unchanged')) return [];
    const field = (key: string) => typeof row[key] === 'string' ? row[key] : '';
    const project = field('project_name'), document = field('bill_name'), material = field('material_name');
    const supplier = field('supplier_name'), date = field('contract_date'), amount = field('i8_amount');
    return [{
      id: receiptRowKey([row.contract_no.trim(), row.status, project, document, material, supplier, date, amount], occurrences),
      contract: row.contract_no, status: row.status, project, document, material, supplier, date,
      amount: /^-?\d+\.\d{2}$/.test(amount) ? money(amount) : '',
    } as const];
  });
}

export function readReceiptRows(value: unknown, ignored: boolean): ReceiptRow[] {
  if (!Array.isArray(value)) return [];
  const occurrences = new Map<string, number>();
  return value.filter(record).map(row => {
    const matches = Array.isArray(row.matches) ? row.matches.filter(isJcRule) : [];
    const field = (key: string) => typeof row[key] === 'string' ? row[key] : '';
    const contract = field('contract_no').trim() || field('bill_no').trim();
    const project = field('project_name'), document = field('doc_name') || field('bill_name'), kind = field('kind');
    return {
      id: receiptRowKey([contract, project, document], occurrences),
      contract, project, document, kind,
      reason: ignored ? matches.length ? '规则剔除' : '规则剔除 · 旧记录未保存命中条件'
        : ownershipReason[kind] ?? '归属待指定',
      matches,
    };
  });
}

export function readReceipt(value: unknown) {
  if (record(value) && value.receipt === null) return null;
  if (!record(value) || !record(value.receipt)) throw new ApiError('抓取结果读取不完整，请重试。');
  const item = value.receipt;
  if (typeof item.started_at !== 'string' || typeof item.status !== 'string' || typeof item.matched !== 'number') {
    throw new ApiError('抓取结果读取不完整，请重试。');
  }
  const ignored = readReceiptRows(item.ignored, true);
  const unsettled = readReceiptRows(item.unsettled, false);
  const summary = record(item.summary) ? item.summary : {};
  const groups = Array.isArray(item.ignored_projects) ? item.ignored_projects.flatMap(group =>
    record(group) && typeof group.name === 'string' && count(group.count) !== null
      ? [{ name: group.name, count: Number(group.count) }] : []) : [];
  return {
    id: count(item.id),
    startedAt: item.started_at.replace('T', ' '), status: item.status, matched: item.matched,
    duration: typeof item.duration_seconds === 'number' && item.duration_seconds >= 0 ? item.duration_seconds : null,
    scope: typeof item.scope === 'string' ? item.scope : '',
    sourceCount: count(summary.source_count), identifiedCount: count(summary.identified_count),
    inserted: count(summary.inserted), changed: count(summary.changed), unchanged: count(summary.unchanged),
    materialBlank: count(summary.material_blank),
    syncWarning: typeof item.sync_warning === 'string' ? item.sync_warning.replaceAll('**', '') : '',
    matchedItems: readMatchedItems(item.matched_items), matchedItemsTotal: count(item.matched_items_total),
    ignoredCount: count(item.ignored_count), unsettledCount: count(item.unsettled_count),
    ignored, unsettled, groups,
  };
}

export type Receipt = NonNullable<ReturnType<typeof readReceipt>>;
