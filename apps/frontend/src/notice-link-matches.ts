import * as v from 'valibot';
import { ApiError } from './api';

const id = v.pipe(v.number(), v.safeInteger(), v.minValue(1));
const amount = v.pipe(v.string(), v.regex(/^-?\d+(?:\.\d{1,2})?$/));
const text = v.string();
const candidate = v.object({
  contract_id: id, contract_no: text, supplier_name: text, material: text,
  selectable: v.boolean(), evidence: v.array(text), payable_codes: v.array(text),
  invoice_side: v.picklist(['supplier', 'trade']), invoice_match: v.boolean(), invoice_ids: v.array(id),
});
const matchFields = {
  notice_id: id, code: text, title: text, project_name: text,
  expected_jc_supplier: text, expected_warehouse_key: text,
  rule_code: text, reason: text, payable_codes: v.array(text), candidates: v.array(candidate),
};
export const readyMatch = v.object({ ...matchFields, expected_amount: amount, bucket: v.literal('auto_ready'), target: candidate });
export const reviewMatch = v.object({ ...matchFields, expected_amount: amount, bucket: v.literal('needs_review'), target: v.null() });
const skippedMatch = v.object({
  ...matchFields, expected_amount: v.nullable(amount), bucket: v.literal('skipped'), target: v.null(),
});
const matchRow = v.variant('bucket', [readyMatch, reviewMatch, skippedMatch]);
const previewSchema = v.object({ ok: v.literal(true), rows: v.array(matchRow) });
const needsPayables = v.object({ ok: v.literal(true), needs_payables: v.literal(true) });

export type MatchCandidate = v.InferOutput<typeof candidate>;
export type ReadyMatch = v.InferOutput<typeof readyMatch>;
export type ReviewMatch = v.InferOutput<typeof reviewMatch>;
type SkippedMatch = v.InferOutput<typeof skippedMatch>;
type MatchRow = v.InferOutput<typeof matchRow>;
type MatchGroups = { auto_ready: ReadyMatch[]; needs_review: ReviewMatch[]; skipped: SkippedMatch[] };
type MatchPreview = { kind: 'needs_payables' } | { kind: 'preview'; groups: MatchGroups };

function groupNoticeMatches(rows: readonly MatchRow[]): MatchGroups {
  const groups: MatchGroups = { auto_ready: [], needs_review: [], skipped: [] };
  for (const row of rows) {
    switch (row.bucket) {
      case 'auto_ready': groups.auto_ready.push(row); break;
      case 'needs_review': groups.needs_review.push(row); break;
      case 'skipped': groups.skipped.push(row); break;
    }
  }
  return groups;
}

export function readMatchPreview(value: unknown, expectedIds: number[]): MatchPreview {
  if (v.is(needsPayables, value)) return { kind: 'needs_payables' };
  const result = v.safeParse(previewSchema, value);
  const ids = new Set(expectedIds);
  if (!result.success || !result.output.rows.every(row => ids.delete(row.notice_id)) || ids.size) {
    throw new ApiError('关联预览与本次通知书不一致，请重读。', 0, 'invalid_response');
  }
  return { kind: 'preview', groups: groupNoticeMatches(result.output.rows) };
}

function selection(row: ReadyMatch | ReviewMatch, choice: MatchCandidate) {
  return {
    notice_id: row.notice_id, contract_id: choice.contract_id, expected_amount: row.expected_amount,
    expected_jc_supplier: row.expected_jc_supplier, expected_warehouse_key: row.expected_warehouse_key,
    expected_contract_supplier: choice.supplier_name,
  };
}

export function readyLinkSelections(rows: readonly ReadyMatch[]) {
  return rows.map(row => selection(row, row.target));
}

export function reviewLinkSelections(rows: readonly ReviewMatch[], choices: ReadonlyMap<number, number>) {
  return rows.flatMap(row => {
    const picked = row.candidates.find(c => c.selectable && c.contract_id === choices.get(row.notice_id));
    return picked ? [selection(row, picked)] : [];
  });
}

const confirmationRow = v.object({ notice_id: id, code: text, contract_id: v.nullable(id), contract_no: text, reason: text });
const confirmationSchema = v.object({
  ok: v.literal(true), linked: v.pipe(v.number(), v.safeInteger(), v.minValue(0)), rows: v.array(confirmationRow),
});
export type LinkConfirmationRow = v.InferOutput<typeof confirmationRow>;

export function readLinkConfirmation(value: unknown, selections: ReturnType<typeof readyLinkSelections>) {
  const result = v.safeParse(confirmationSchema, value);
  if (result.success) {
    const { rows, linked } = result.output;
    const expected = new Map(selections.map(row => [row.notice_id, row.contract_id]));
    const matches = rows.every(row => (row.contract_id === null || row.contract_id === expected.get(row.notice_id))
      && expected.delete(row.notice_id));
    if (matches && !expected.size && linked === rows.filter(row => row.contract_id !== null).length) return result.output;
  }
  throw new ApiError('关联回执与本次确认不一致，请重读核对。', 0, 'invalid_response');
}
