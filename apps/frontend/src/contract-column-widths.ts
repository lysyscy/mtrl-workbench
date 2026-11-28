import { cents, decimal, money } from './api';
import { contractApprovalStatuses, contractMoneyKeys, contractRemarkText } from './contracts-api';
import type { ContractRow } from './contracts-api';
import { contentColumn } from './grid-content-widths';

type AmountKey = typeof contractMoneyKeys[number];
export function isContractAmount(key: string): key is AmountKey {
  return contractMoneyKeys.some(amount => amount === key);
}

export function contractTotalSamples(rows: ContractRow[]) {
  const first = rows[0];
  if (!first) return [];
  const lower = {...first}, upper = {...first};
  for (const key of contractMoneyKeys) {
    let negative = 0n, positive = 0n;
    for (const row of rows) {
      const value = cents(row[key] ?? '0');
      if (value < 0n) negative += value;
      else positive += value;
    }
    lower[key] = decimal(negative);
    upper[key] = decimal(positive);
  }
  return [lower, upper];
}

export function contractColumnWidth(key: string, options: {
  subtable: boolean;
  projectName: (row: ContractRow) => string;
  archiveHint: (row: ContractRow) => string;
  methods: readonly string[];
}) {
  if (isContractAmount(key)) {
    return contentColumn<ContractRow>('bounded', (row, measure, pinned) => {
      const value = row[key];
      const label = value === null && !options.subtable ? '未确定' : money(value ?? '0');
      return measure.text(label, { tabular: true, weight: pinned ? 600 : 400 }) + (options.subtable ? measure.px(40) + 6 : 0);
    });
  }
  if (key === 'material') {
    return contentColumn<ContractRow>('demand', (row, measure, pinned) => pinned ? measure.text('合计', { weight: 600 })
      : measure.buttons([row.material || '材料名未填']) + measure.px(8) + measure.text(options.projectName(row), { size: 11.25 }));
  }
  if (key === 'remark') {
    return contentColumn<ContractRow>('demand', (row, measure, pinned) => pinned ? 0
      : measure.text(contractRemarkText(row.remark ?? '')) + 10);
  }
  if (key === 'payment_method') {
    return contentColumn<ContractRow>('bounded', (row, measure, pinned) => pinned ? 0
      : measure.text(row.payment_method || '未约定', { size: 12 }) + measure.px(28) + 2,
      measure => Math.max(...['未约定', ...options.methods].map(label => measure.text(label, { size: 12 }))) + measure.px(28) + 2);
  }
  if (key === 'payment_term' || key === 'arch_no') {
    return contentColumn<ContractRow>('bounded', (row, measure, pinned) => pinned ? 0
      : measure.text(row[key] || (key === 'arch_no' ? options.archiveHint(row) : '可填')) + 10);
  }
  if (key === 'ret_date') {
    return contentColumn<ContractRow>('bounded', undefined,
      measure => measure.text('00/00/0000', { tabular: true }) + measure.px(20) + 10);
  }
  if (key === 'tag' || key === 'arch' || key === 'approve_status') {
    return contentColumn<ContractRow>('bounded', (row, measure, pinned) => pinned ? 0
      : measure.text(row[key] || (key === 'approve_status' ? '—' : '未存档'), { size: 12 }) + measure.px(15) + 2,
      key === 'approve_status' ? measure => Math.max(...contractApprovalStatuses.map(label => measure.text(label, { size: 12 }))) + measure.px(15) + 2 : undefined);
  }
  if (key === 'supplier' || key === 'trade_co' || key === 'project') {
    return contentColumn<ContractRow>('demand', (row, measure, pinned) => pinned ? 0 : measure.text(key === 'project' ? options.projectName(row) : row[key]));
  }
  return contentColumn<ContractRow>('bounded', (row, measure, pinned) => pinned ? 0 : measure.text(Object.getOwnPropertyDescriptor(row, key)?.value));
}
