import { replaceEqualDeep } from '@tanstack/react-query';
import { cents, decimal, money } from './api';
import { contractApprovalStatuses, contractMoneyKeys } from './contracts-api';
import type { ContractList, ContractRow } from './contracts-api';
import { cacheFontMeasurement, numberColumnWidth } from './grid';
import { completeColumnWidth } from './grid-text';

export const amountColumnIds = new Set<string>(contractMoneyKeys);
const textKeys = ['project_seq','date','contract_no','approve_status','payment_term','payment_method','tag','arch','arch_no','ret_date'] as const;
const textColumnIds = new Set<string>(textKeys);
// The suggested archive number depends on which project each number belongs to.
const textInputs = [...textKeys, 'project_key'] as const;

function contractAmountWidths(columns: ContractList['columns'], rows: ContractRow[], scale: number) {
  return Object.fromEntries(columns.filter(column => amountColumnIds.has(column.key)).map(column => {
    const key = column.key as typeof contractMoneyKeys[number];
    const header = column.label.replace('（自动）', '');
    // A filtered total lies between the sum of the negatives and the sum of
    // the positives, even when opposite entries cancel on the opening view.
    let positive = 0n, negative = 0n;
    const values = rows.map(row => {
      const value = row[key];
      if (value === null) return '未确定';
      const amount = cents(value ?? '0');
      if (amount > 0n) positive += amount;
      else negative += amount;
      return money(value ?? '0');
    });
    values.push(money(decimal(positive)), money(decimal(negative)));
    const extra = ['inv_sum', 'trade_inv_sum', 'pay_sum'].includes(key) ? 56 : 0;
    const width = completeColumnWidth(values, header, scale, extra);
    width.initialWidth = width.minWidth = Math.max(width.minWidth, numberColumnWidth(values, scale).minWidth + extra * scale);
    return [key, width];
  }));
}

export function contractWidthMeasurements(columns: ContractList['columns'], methods: readonly string[], scale: number) {
  let previous: ContractRow[] = [];
  let archives: ReadonlyMap<string, string> = new Map();
  const amounts = () => contractAmountWidths(columns, previous, scale);
  const text = () => Object.fromEntries(columns.filter(column => textColumnIds.has(column.key)).map(column => {
    const key = column.key as typeof textKeys[number];
    const values = previous.map(row => String(row[key] ?? ''));
    if (key === 'approve_status') values.push(...contractApprovalStatuses);
    if (key === 'payment_method') values.push('未约定', ...methods);
    if (key === 'arch_no') values.push(...archives.values());
    if (key === 'ret_date') values.push('2000-12-31');
    const extra = key === 'payment_method' || key === 'ret_date' ? 44 : key === 'payment_term' || key === 'arch_no' ? 20
      : key === 'tag' || key === 'arch' || key === 'approve_status' ? 12 : 0;
    return [key, completeColumnWidth(values, key === 'tag' ? '纳入状态' : column.label.replace('（自动）',''), scale, extra)];
  }));
  let measureText = cacheFontMeasurement(text), measureAmounts = cacheFontMeasurement(amounts);
  let last: {completeWidths: ReturnType<typeof text>; moneyWidths: ReturnType<typeof amounts>} | undefined;
  return (rows: ContractRow[], archiveNumbers: ReadonlyMap<string, string>) => {
    // Query rereads share unchanged rows. Inspect changed rows before invalidating
    // all identifier or amount measurements; font readiness is checked separately.
    const changed = (keys: readonly (keyof ContractRow)[]) => rows !== previous &&
      (rows.length !== previous.length || rows.some((row, index) => {
        const prior = previous[index]!;
        return row !== prior && keys.some(key => row[key] !== prior[key]);
      }));
    if (changed(textInputs)) measureText = cacheFontMeasurement(text);
    if (changed(contractMoneyKeys)) measureAmounts = cacheFontMeasurement(amounts);
    previous = rows;
    archives = archiveNumbers;
    // An edited value can fit the same measured bounds. Keep its existing renderers.
    last = replaceEqualDeep(last, {completeWidths:measureText(), moneyWidths:measureAmounts()});
    return last;
  };
}
