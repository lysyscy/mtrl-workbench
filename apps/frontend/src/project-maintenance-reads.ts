import { ApiError, record } from './api';

type Candidate = { id: number; disp: string; warehouse_name: string; status: string; is_placeholder: boolean };
export type Pending = { full_name: string; warehouse_name?: string | null; candidates?: Candidate[]; warehouses?: string[] };
type PendingList = { items: Pending[]; source: { at?: string; target?: string } };
export type Trail = { at: string; project: string; field_label: string; before: string; after: string; by: string };

function validCandidate(value: unknown): boolean {
  return record(value) && Number.isInteger(value.id) && typeof value.disp === 'string' &&
    typeof value.warehouse_name === 'string' && typeof value.status === 'string' && typeof value.is_placeholder === 'boolean';
}

function validPending(value: unknown, kind: 'promote' | 'archive'): boolean {
  if (!record(value) || typeof value.full_name !== 'string') return false;
  if (kind === 'promote') return typeof value.warehouse_name === 'string' &&
    Array.isArray(value.candidates) && value.candidates.every(validCandidate);
  return (value.warehouse_name == null || typeof value.warehouse_name === 'string') &&
    Array.isArray(value.warehouses) && value.warehouses.every(warehouse => typeof warehouse === 'string');
}

export function readProjectPending(value: unknown, kind: 'promote' | 'archive'): PendingList {
  if (!record(value) || !Array.isArray(value.items) || !record(value.source) ||
    !value.items.every(item => validPending(item, kind)) ||
    (value.items.length > 0 && (typeof value.source.target !== 'string' || typeof value.source.at !== 'string'))) {
    throw new ApiError('读取结果不完整，请重试。');
  }
  return value as PendingList;
}

export function readProjectTrails(value: unknown): Trail[] {
  if (!Array.isArray(value) || !value.every(row => record(row) &&
    typeof row.at === 'string' && typeof row.project === 'string' && typeof row.field_label === 'string' &&
    typeof row.before === 'string' && typeof row.after === 'string' && typeof row.by === 'string')) {
    throw new ApiError('修改留痕读取不完整，请重试。');
  }
  return value as Trail[];
}
