import { ApiError, body, cents, confirmWrite, decimal, record, requestJson } from './api';

export interface OilFeeMonth { project_id: number; ym: string; enabled: boolean; can_enable: boolean; recharge_amount: string; custom_amount: string | null; remark: string; fee_amount: string; version: string | null }
export interface OilLinkage { ym: string; rows: OilFeeMonth[] }
const amount = (value: unknown): value is string => typeof value === 'string' && /^-?\d+(?:\.\d{1,2})?$/.test(value);
function readMonth(value: unknown, ym: string): OilFeeMonth {
  if (!record(value) || value.ym !== ym || typeof value.project_id !== 'number' || !Number.isSafeInteger(value.project_id) || value.project_id <= 0 ||
    typeof value.enabled !== 'boolean' || typeof value.can_enable !== 'boolean' || value.enabled && value.can_enable || !amount(value.recharge_amount) || !(value.custom_amount === null || amount(value.custom_amount)) || !amount(value.fee_amount) || typeof value.remark !== 'string' ||
    !(value.version === null || typeof value.version === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value.version))) throw new ApiError('用油联动读取不完整，请重读核对。');
  if (cents(value.fee_amount) !== cents(value.recharge_amount) + cents(value.custom_amount ?? '0')) throw new ApiError('用油联动金额读取不一致，请重读核对。');
  return value as unknown as OilFeeMonth;
}
export async function getOilLinkage(ym: string, signal: AbortSignal): Promise<OilLinkage> {
  const value = await requestJson(`/api/m13/linkage?${new URLSearchParams({ ym })}`, { signal });
  if (!record(value) || value.ym !== ym || !Array.isArray(value.rows)) throw new ApiError('用油联动范围读取不完整，请重读核对。');
  const rows = value.rows.map(row => readMonth(row, ym));
  if (new Set(rows.map(row => row.project_id)).size !== rows.length) throw new ApiError('用油联动项目重复，请重读核对。');
  return { ym, rows };
}
export async function saveOilFeeCustom(row: OilFeeMonth, fields: { amount: string | null; remark: string }, signal: AbortSignal) {
  const value = await requestJson(`/api/m13/linkage/${row.project_id}/${row.ym}/fee`, { method: 'PUT', signal,
    ...body({ ...fields, version: row.version }) });
  confirmWrite(record(value) && value.ok === true, '用油自定义额保存回执待核实，请重读核对。');
  const saved = readMonth((value as Record<string, unknown>).item, row.ym);
  confirmWrite(saved.enabled && saved.version !== null && saved.project_id === row.project_id && saved.remark === fields.remark && saved.custom_amount === (fields.amount === null ? null : decimal(cents(fields.amount))), '用油自定义额回执与输入不一致，请重读核对。');
  return saved;
}

export async function enableOilFeeLinkage(projectId: number, signal: AbortSignal) {
  const value = await requestJson(`/api/m13/linkage/${projectId}/enable`, { method: 'POST', signal });
  confirmWrite(record(value) && value.ok === true && value.enabled === true && value.can_enable === false && value.fee_item_id === null, '启用联动回执待核实，请重读核对。');
}
