import type { OilAccount } from './oilcard-api';
import type { EntryFields, OilEntry } from './oilcard-ledger-api';

export type OilEntryDraft = OilEntry & { original: OilEntry | null; error: string };
export const entryFields = (row: OilEntry): EntryFields => ({ date_text: row.date_text, kind: row.kind, project_id: row.project_id, account_id: row.account_id, amount: row.amount, remark: row.remark });
export const sameEntryFields = (a: OilEntry, b: OilEntry) => JSON.stringify(entryFields(a)) === JSON.stringify(entryFields(b));

export function editOilEntry(drafts: Record<string, OilEntryDraft>, entries: readonly OilEntry[], key: string,
  field: keyof EntryFields, value: string, accounts: readonly OilAccount[], writing: boolean): Record<string, OilEntryDraft> {
  const previous = drafts[key], row = previous ?? entries.find(entry => entry.request_id === key);
  if (!row) return drafts;
  const next: OilEntryDraft = { ...row, original: previous ? previous.original : row.id ? row : null, error: '', [field]: field === 'project_id' || field === 'account_id' ? Number(value) : value };
  if (field === 'project_id') {
    const candidates = accounts.filter(account => account.project_id === next.project_id);
    next.account_id = candidates.length === 1 ? candidates[0]!.id : candidates.some(account => account.id === next.account_id) ? next.account_id : 0;
  }
  const result = { ...drafts, [key]: next };
  if (next.original && sameEntryFields(next, next.original) && !writing) delete result[key];
  return result;
}

export function rebaseOilEntryDraft(draft: OilEntryDraft, saved: OilEntry): OilEntryDraft {
  return { ...draft, id: saved.id, version: saved.version, card_id: saved.card_id,
    entry_date: saved.entry_date, related_entry_id: saved.related_entry_id, original: saved };
}
