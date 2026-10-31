import { ApiError, body, confirmWrite, record, requestJson } from './api';

export interface OilCard { id: number; request_id: string; card_no: string | null; kind: 'primary' | 'secondary'; parent_card_id: number | null; remark: string; version: string }
export interface OilAccount { id: number; request_id: string; name: string; project_id: number; card_id: number | null; status: 'active' | 'archived'; remark: string; version: string }
export interface OilArchives { cards: OilCard[]; accounts: OilAccount[] }
export interface OilAssignment { id: number; account_id: number; project_id: number; card_id: number | null; previous_card_id: number | null; change_kind: 'assignment' | 'replacement'; request_id: string | null; changed_by: string; changed_at: string }
export type CardFields = Omit<OilCard, 'id' | 'request_id' | 'version'>;
export type AccountFields = Omit<OilAccount, 'id' | 'request_id' | 'version'>;
const id = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const nullableId = (value: unknown) => value === null || id(value);
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value);
function base(value: unknown): value is Record<string, unknown> { return record(value) && id(value.id) && uuid(value.request_id) && uuid(value.version) && typeof value.remark === 'string'; }
export function readOilCard(value: unknown): OilCard {
  if (!base(value) || !(value.card_no === null || typeof value.card_no === 'string') || !['primary', 'secondary'].includes(String(value.kind)) || !nullableId(value.parent_card_id)) throw new ApiError('实体油卡读取不完整，请重读核对。');
  return value as unknown as OilCard;
}
export function readOilAccount(value: unknown): OilAccount {
  if (!base(value) || typeof value.name !== 'string' || !value.name.trim() || !id(value.project_id) || !nullableId(value.card_id) || !['active', 'archived'].includes(String(value.status))) throw new ApiError('用卡账户读取不完整，请重读核对。');
  return value as unknown as OilAccount;
}
export function readOilArchives(value: unknown): OilArchives {
  if (!record(value) || !Array.isArray(value.cards) || !Array.isArray(value.accounts)) throw new ApiError('油卡档案读取不完整，请重读核对。');
  const cards = value.cards.map(readOilCard), accounts = value.accounts.map(readOilAccount);
  if (new Set(cards.map(c => c.id)).size !== cards.length || new Set(accounts.map(a => a.id)).size !== accounts.length ||
    new Set(cards.map(c => c.request_id)).size !== cards.length || new Set(accounts.map(a => a.request_id)).size !== accounts.length ||
    cards.some(c => c.parent_card_id !== null && (c.kind !== 'secondary' || !cards.some(p => p.id === c.parent_card_id && p.kind === 'primary'))) ||
    accounts.some(a => a.card_id !== null && !cards.some(c => c.id === a.card_id && c.kind === 'secondary'))) throw new ApiError('油卡关联读取不完整，请重读核对。');
  return { cards, accounts };
}
export async function getOilArchives(signal?: AbortSignal) { return readOilArchives(await requestJson('/api/m13/archives', signal ? { signal } : {})); }
export async function saveOilCard(fields: CardFields, target: { id: number; version: string } | { request_id: string }, signal: AbortSignal) {
  const data = await requestJson(`/api/m13/cards${'id' in target ? `/${target.id}` : ''}`, { method: 'id' in target ? 'PUT' : 'POST', signal, ...body({ ...fields, ...('id' in target ? { version: target.version } : target) }) });
  confirmWrite(record(data) && data.ok === true, '保存回执不完整，请重读核对，勿重复提交。');
  const item = readOilCard((data as Record<string, unknown>).item);
  confirmWrite(('id' in target ? item.id === target.id : item.request_id === target.request_id) && Object.entries(fields).every(([k, v]) => item[k as keyof OilCard] === v), '保存回执与本次输入不一致，请重读核对。');
  return item;
}
export async function saveOilAccount(fields: AccountFields, target: { id: number; version: string } | { request_id: string }, signal: AbortSignal) {
  const data = await requestJson(`/api/m13/accounts${'id' in target ? `/${target.id}` : ''}`, { method: 'id' in target ? 'PUT' : 'POST', signal, ...body({ ...fields, ...('id' in target ? { version: target.version } : target) }) });
  confirmWrite(record(data) && data.ok === true, '保存回执不完整，请重读核对，勿重复提交。');
  const item = readOilAccount((data as Record<string, unknown>).item);
  confirmWrite(('id' in target ? item.id === target.id : item.request_id === target.request_id) && Object.entries(fields).every(([k, v]) => item[k as keyof OilAccount] === v), '保存回执与本次输入不一致，请重读核对。');
  return item;
}
export async function getOilAssignments(accountId: number, signal: AbortSignal): Promise<OilAssignment[]> {
  const data = await requestJson(`/api/m13/accounts/${accountId}/assignments`, { signal });
  if (!Array.isArray(data) || !data.every(r => validAssignment(r, accountId))) throw new ApiError('关联历史读取不完整，请重读核对。');
  return data as OilAssignment[];
}

function validAssignment(r: unknown, accountId: number): r is OilAssignment {
  return record(r) && id(r.id) && r.account_id === accountId && id(r.project_id) && nullableId(r.card_id) && nullableId(r.previous_card_id) &&
    ['assignment', 'replacement'].includes(String(r.change_kind)) && (r.request_id === null || uuid(r.request_id)) && typeof r.changed_by === 'string' && typeof r.changed_at === 'string';
}
export interface OilReplacementFields { request_id: string; card_id: number | null; new_card: Omit<CardFields, 'kind'> | null }
export async function replaceOilCard(fields: OilReplacementFields, target: OilAccount, signal: AbortSignal) {
  const result = await requestJson(`/api/m13/accounts/${target.id}/replace-card`, { method: 'POST', signal, ...body({ ...fields, version: target.version }) });
  confirmWrite(record(result) && result.ok === true, '换卡保存回执待核实，请重读，勿重复换卡。');
  const data = result as Record<string, unknown>, item = readOilAccount(data.item), event = data.assignment;
  confirmWrite(validAssignment(event, target.id) && event.change_kind === 'replacement' && event.request_id === fields.request_id &&
    event.previous_card_id === target.card_id && event.card_id === item.card_id && item.card_id !== target.card_id &&
    (fields.card_id === null || item.card_id === fields.card_id) && item.id === target.id && item.request_id === target.request_id &&
    item.name === target.name && item.project_id === target.project_id && item.status === target.status && item.remark === target.remark,
  '换卡回执与本次选择不一致，请重读核对。');
  return item;
}
