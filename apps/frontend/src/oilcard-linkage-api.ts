import { ApiError, body, cents, confirmWrite, decimal, record, requestJson } from './api';

export interface OilBigMonth { enabled: boolean; can_enable: boolean; recharge_amount: string; fee_custom_amount: string; own_amount: string | null; extra_amount: string | null; remark: string; version: string | null; source_ym: string | null; source_version: string | null; amount: string }
export interface OilFeeMonth { project_id: number; ym: string; enabled: boolean; can_enable: boolean; recharge_amount: string; custom_amount: string | null; remark: string; fee_amount: string; version: string | null; big: OilBigMonth }
export interface OilLinkage { ym: string; rows: OilFeeMonth[] }
const amount = (value: unknown): value is string => typeof value === 'string' && /^-?\d+(?:\.\d{1,2})?$/.test(value);
const uuid = (value: unknown) => typeof value === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value);
function readBig(value: unknown, ym: string): OilBigMonth {
  if (!record(value) || typeof value.enabled !== 'boolean' || typeof value.can_enable !== 'boolean' || value.enabled && value.can_enable ||
    !amount(value.recharge_amount) || !amount(value.fee_custom_amount) || !amount(value.amount) ||
    !(value.own_amount === null || amount(value.own_amount)) || !(value.extra_amount === null || amount(value.extra_amount)) || typeof value.remark !== 'string' ||
    !(value.version === null || uuid(value.version)) || !(value.source_version === null || uuid(value.source_version)) ||
    !(value.source_ym === null || typeof value.source_ym === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(value.source_ym) && value.source_ym <= ym)) throw new ApiError('大表用油读取不完整，请重读核对。');
  if ((value.extra_amount === null) !== (value.source_ym === null) || (value.source_ym === null) !== (value.source_version === null) ||
    (value.own_amount !== null) !== (value.source_ym === ym) || (value.own_amount === null) !== (value.version === null) ||
    value.own_amount !== null && (value.own_amount !== value.extra_amount || value.version !== value.source_version) ||
    value.extra_amount === null && value.remark !== '' || cents(value.amount) !== cents(value.recharge_amount) + cents(value.fee_custom_amount) + cents(value.extra_amount ?? '0')) throw new ApiError('大表用油金额或沿用来源不一致，请重读核对。');
  return value as unknown as OilBigMonth;
}
function readMonth(value: unknown, ym: string): OilFeeMonth {
  if (!record(value) || value.ym !== ym || typeof value.project_id !== 'number' || !Number.isSafeInteger(value.project_id) || value.project_id <= 0 ||
    typeof value.enabled !== 'boolean' || typeof value.can_enable !== 'boolean' || value.enabled && value.can_enable || !amount(value.recharge_amount) || !(value.custom_amount === null || amount(value.custom_amount)) || !amount(value.fee_amount) || typeof value.remark !== 'string' ||
    !(value.version === null || typeof value.version === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value.version))) throw new ApiError('用油联动读取不完整，请重读核对。');
  if (cents(value.fee_amount) !== cents(value.recharge_amount) + cents(value.custom_amount ?? '0')) throw new ApiError('用油联动金额读取不一致，请重读核对。');
  return { ...value, big: readBig(value.big, ym) } as unknown as OilFeeMonth;
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

export async function enableOilBigLinkage(projectId: number, signal: AbortSignal) {
  const value = await requestJson(`/api/m13/linkage/${projectId}/big/enable`, { method: 'POST', signal });
  confirmWrite(record(value) && value.ok === true && value.enabled === true && value.can_enable === false, '启用大表联动回执待核实，请重读核对。');
}

export async function saveOilBigCustom(row: OilFeeMonth, fields: { amount: string | null; remark: string }, signal: AbortSignal) {
  const value = await requestJson(`/api/m13/linkage/${row.project_id}/${row.ym}/big`, { method: 'PUT', signal,
    ...body({ ...fields, version: row.big.version, source_ym: row.big.source_ym, source_version: row.big.source_version }) });
  confirmWrite(record(value) && value.ok === true, '大表额外值保存回执待核实，请重读核对。');
  const saved = readMonth((value as Record<string, unknown>).item, row.ym);
  confirmWrite(saved.project_id === row.project_id && saved.big.enabled && (fields.amount === null ? saved.big.own_amount === null && saved.big.version === null :
    saved.big.version !== null && saved.big.source_ym === row.ym && saved.big.own_amount === decimal(cents(fields.amount)) && saved.big.remark === fields.remark), '大表额外值回执与输入不一致，请重读核对。');
  return saved;
}
