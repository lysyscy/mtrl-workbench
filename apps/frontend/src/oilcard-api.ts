import * as v from 'valibot';
import { ApiError, body, confirmWrite, record, requestJson } from './api';

export interface OilCard { id: number; request_id: string; card_no: string | null; kind: 'primary' | 'secondary'; parent_card_id: number | null; status: 'active' | 'archived'; remark: string; version: string }
export interface OilAccount { id: number; request_id: string; name: string; project_id: number; card_id: number | null; status: 'active' | 'archived'; remark: string; version: string }
export interface OilArchives { cards: OilCard[]; accounts: OilAccount[] }
export type OilOrderKind = 'account' | 'primary' | 'secondary';
export interface OilAssignment { id: number; account_id: number; project_id: number; card_id: number | null; previous_card_id: number | null; change_kind: 'assignment' | 'replacement'; request_id: string | null; changed_by: string; changed_at: string }
export type CardFields = Omit<OilCard, 'id' | 'request_id' | 'version'>;
export type AccountFields = Omit<OilAccount, 'id' | 'request_id' | 'version'>;
const id = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const nullableId = (value: unknown) => value === null || id(value);
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value);
const archiveFields = {
  id: v.custom<number>(id), request_id: v.custom<string>(uuid), version: v.custom<string>(uuid),
  remark: v.string(), status: v.picklist(['active', 'archived']),
};
const card = v.looseObject({
  ...archiveFields, card_no: v.nullable(v.string()), kind: v.picklist(['primary', 'secondary']),
  parent_card_id: v.nullable(archiveFields.id),
});
const account = v.looseObject({
  ...archiveFields, name: v.pipe(v.string(), v.check(name => !!name.trim())),
  project_id: archiveFields.id, card_id: v.nullable(archiveFields.id),
});
export function readOilCard(value: unknown): OilCard {
  if (!v.is(card, value)) throw new ApiError('实体油卡读取不完整，请重读核对。');
  return value;
}
export function readOilAccount(value: unknown): OilAccount {
  if (!v.is(account, value)) throw new ApiError('用卡账户读取不完整，请重读核对。');
  return value;
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
export function oilArchiveOrder(archives: OilArchives, kind: OilOrderKind, parentId: number | null) {
  return kind === 'account' ? archives.accounts.map(row => row.id) : archives.cards.filter(row => row.kind === kind && row.parent_card_id === parentId).map(row => row.id);
}
export async function saveOilArchiveOrder(kind: OilOrderKind, parentId: number | null, previous: number[], order: number[], signal: AbortSignal) {
  const data = await requestJson('/api/m13/archives/order', { method: 'PUT', signal, ...body({ kind, parent_id: parentId, previous, order }) });
  confirmWrite(record(data) && data.ok === true && JSON.stringify(data.order) === JSON.stringify(order), '排序回执不完整，请重读核对。');
}
export async function deleteOilArchive(kind: 'card' | 'account', row: OilCard | OilAccount, signal: AbortSignal) {
  const data = await requestJson(`/api/m13/${kind === 'card' ? 'cards' : 'accounts'}/${row.id}/delete`, { method: 'POST', signal, ...body({ version: row.version }) });
  confirmWrite(record(data) && data.ok === true && data.id === row.id, '删除回执不完整，请重读核对。');
}
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
export async function archiveOilAccount(account: OilAccount, card: OilCard | null, signal: AbortSignal) {
  const result = await requestJson('/api/m13/accounts/' + account.id + '/archive', {
    method: 'POST', signal, ...body({ version: account.version, card_version: card?.version ?? null }),
  });
  confirmWrite(record(result) && result.ok === true, '归档回执待核实，请重读核对。');
  const data = result as Record<string, unknown>, saved = readOilAccount(data.item);
  const savedCard = card ? readOilCard(data.card) : null;
  confirmWrite(saved.id === account.id && saved.card_id === account.card_id && saved.status === 'archived' &&
    (card ? savedCard?.id === card.id && savedCard.status === 'archived' : data.card === null),
  '归档回执与所选范围不一致，请重读核对。');
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
