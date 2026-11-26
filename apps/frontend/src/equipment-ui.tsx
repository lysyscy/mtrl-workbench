import { createContext, useContext, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Button from 'antd/es/button';
import DatePicker from 'antd/es/date-picker';
import dayjs from 'dayjs';
import type { ColDef } from 'ag-grid-community';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import type { SyncStatus } from './equipment-api';
import { uncertainWrite } from './api';
import { valueFilterColumn } from './grid-value-filter';
import type { FilterValue, ValueFilterKind } from './grid-value-filter-model';

export const EquipmentAccess = createContext({ enabled: false, writable: false });
export const useAccess = () => useContext(EquipmentAccess);
export const scopeLabels = { current_asset: '流动资产', fixed_asset: '固定资产', off_book: '不在账' };
export const flagLabels = { yes: '是', no: '否', pending: '待核' };
export const statusLabels = { in_use: '在用', damaged: '损坏', pending_scrap: '待报废', scrapped: '已报废' };
export const syncLabels = {
  pending: '待同步',
  synced: '已同步',
  failed: '同步失败',
  conflict: '同步冲突',
  not_applicable: '无需同步',
};
export const options = (labels: Record<string, string>) =>
  Object.entries(labels).map(([value, label]) => ({ value, label }));
export const rowId = (row: { id: number }) => String(row.id);
export const issue = (status: SyncStatus) => ['pending', 'conflict', 'failed'].includes(status);
export function SyncTag({ status, showNormal = false }: { status: SyncStatus; showNormal?: boolean }) {
  if (!showNormal && !issue(status)) return null;
  const tone = status === 'pending' ? 'status-pending' : issue(status) ? 'status-negative' : 'status-neutral';
  return <span className={'status-tag ' + tone}>{syncLabels[status]}</span>;
}

export function decimalInput(value: string) {
  return value.includes('.') ? value.replace(/0+$/, '').replace(/\.$/, '') : value;
}

export function formatNum(value: FilterValue) {
  if (value == null || value === '') return '—';
  const [whole, fraction] = decimalInput(String(value)).split('.');
  const grouped = whole!.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return fraction ? grouped + '.' + fraction : grouped;
}

export const decimalField = {
  formatter: (value: string | undefined, info: { userTyping: boolean; input: string }) =>
    info.userTyping ? info.input : value == null || value === '' ? '' : formatNum(value),
  parser: (value?: string) => value?.replaceAll(',', '') ?? '',
};

export function ledgerColumn<T>(
  column: ColDef<T>,
  value: (row: T) => FilterValue,
  kind: ValueFilterKind = 'text'
) {
  return valueFilterColumn<T>({
    ...column,
    sortable: true,
    valueGetter: ({ data }) => data ? value(data) : null,
    ...(kind === 'number' ? { valueFormatter: ({ value }) => formatNum(value) } : {}),
  }, { kind, value, ...(kind === 'number' ? { format: formatNum } : {}) });
}

export function projectTitle(disp: string | null, custom: string | null, display: string) {
  return disp && custom && disp !== custom ? '归属系统项目：' + disp : display;
}
export function syncReceipt(results: { status: SyncStatus }[]) {
  return options(syncLabels)
    .map(({ value, label }) => ({ label, n: results.filter((r) => r.status === value).length }))
    .filter((x) => x.n)
    .map((x) => x.label + ' ' + x.n + ' 项')
    .join('、');
}
export function useLedgerQuery<T>(key: readonly unknown[], load: () => Promise<T>, active = true) {
  const { enabled } = useAccess();
  return useQuery({ queryKey: ['equipment-ledger', ...key], queryFn: load, enabled: enabled && active });
}
export function useLedgerAction() {
  const client = useQueryClient(),
    lock = useRef(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function run(fn: () => Promise<void>, refresh = true) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      await fn();
      if (refresh) await client.invalidateQueries({ queryKey: ['equipment-ledger'] });
    } catch (e) {
      setError(
        (e instanceof Error ? e.message : '操作失败。') +
          (refresh && uncertainWrite(e) ? ' 请重读台账核对结果后再操作。' : '')
      );
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return { run, busy, error };
}
export function LoadState({
  query,
}: {
  query: { isPending: boolean; error: Error | null; refetch: () => unknown };
}) {
  if (query.error)
    return (
      <p role="alert">
        {query.error.message} <Button onClick={() => void query.refetch()}>重新读取</Button>
      </p>
    );
  return query.isPending ? <p role="status">正在读取…</p> : null;
}
export function DateField({
  value,
  onChange,
  month = false,
  label,
}: {
  value?: string | null;
  onChange?: (v: string | null) => void;
  month?: boolean;
  label: string;
}) {
  const format = month ? 'YYYY-MM' : 'YYYY-MM-DD';
  return (
    <DatePicker
      aria-label={label}
      picker={month ? 'month' : 'date'}
      format={format}
      value={value ? dayjs(value) : null}
      onChange={(v) => onChange?.(v ? v.format(format) : null)}
    />
  );
}
export function LedgerModal({
  title,
  busy = false,
  dirty = false,
  compact = false,
  className = '',
  close,
  children,
}: {
  title: string;
  busy?: boolean;
  dirty?: boolean;
  compact?: boolean;
  className?: string;
  close: () => void;
  children: ReactNode;
}) {
  const closing = useDialogClose({ busy, dirty, close });
  return (
    <BusinessModal
      open
      titleId="equipment-dialog"
      className={['equipment-dialog', compact ? 'equipment-dialog-compact' : '', className].filter(Boolean).join(' ')}
      requestClose={closing.requestClose}
    >
      <DialogContents titleId="equipment-dialog" title={title} closing={closing}>
        {children}
      </DialogContents>
    </BusinessModal>
  );
}
