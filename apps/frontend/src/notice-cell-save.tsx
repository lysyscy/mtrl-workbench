import { createContext, useContext, useRef } from 'react';
import { ApiError, body, requestJson, uncertainWrite } from './api';
import { manualDraft } from './notice-maintenance';
import { confirmNoticeAmount, money, noticeAmountLabels, noticeAmountMatches } from './notices-api';
import type { NoticeRow } from './notices-api';
import type { NoticeAmountField } from './notices-api';
import { useCellSaveQueue } from './use-cell-save';

type Field = NoticeAmountField;
interface Draft { id: number; field: Field; value: string; revision: number; error: string }
interface Cells {
  drafts: Record<string, Draft>; disabled: boolean;
  change: (row: NoticeRow, field: Field, value: string) => void;
  save: (key: string, retry?: boolean) => void;
  cancel: (key: string) => void;
}
export const NoticeCells = createContext<Cells | null>(null);
const keyOf = (id: number, field: Field) => `${id}:${field}`;

export function useNoticeCellSaves({ rows, enabled, canWrite, read }: {
  rows: NoticeRow[] | undefined; enabled: boolean; canWrite: boolean; read: () => Promise<NoticeRow[]>;
}) {
  const latest = useRef(rows), published = useRef(rows), revision = useRef(0), attempt = useRef<Draft | null>(null);
  if (published.current !== rows) { published.current = rows; latest.current = rows; }
  const saves = useCellSaveQueue<Draft, NoticeRow[]>({
    enabled, canWrite,
    read: async () => { const data = await read(); latest.current = data; return data; },
    write: async (draft, signal) => {
      attempt.current = draft;
      const row = latest.current?.find(item => item.notice_id === draft.id);
      if (!row || row.is_excluded || row.is_revoked || draft.field === 'amount_approved' && !row.is_manual) throw new ApiError('本条通知书已不可编辑，请核对后取消修改。', 409);
      const manual = draft.field === 'amount_approved';
      try {
        const result = await requestJson(manual ? '/api/m03/actions/manual-save' : '/api/m03/actions/stat', {
          method: 'POST', signal, ...body(manual ? { ...manualDraft(row), amount_approved: draft.value } : { notice_id: draft.id, field: draft.field, value: draft.value }),
        });
        confirmNoticeAmount(result, draft.id, draft.field);
      } catch (failure) { if (!uncertainWrite(failure)) attempt.current = null; throw failure; }
    },
    acknowledge: (current, submitted) => { attempt.current = null; return current.revision === submitted.revision ? undefined : current; },
    saved: () => '',
  }, { key: 'notice-cells', label: '通知书金额' });
  const cells: Cells = {
    drafts: saves.drafts, disabled: !enabled || !canWrite || saves.uncertain, save: saves.save,
    change: (row, field, value) => saves.update((drafts, writing) => {
      const key = keyOf(row.notice_id, field), next = { ...drafts };
      if (!writing && value === row[field]) delete next[key];
      else next[key] = { id: row.notice_id, field, value, revision: ++revision.current, error: '' };
      return next;
    }),
    cancel: key => saves.update((drafts, writing) => {
      const next = { ...drafts }, submitted = attempt.current;
      if (writing && submitted && key === keyOf(submitted.id, submitted.field)) next[key] = submitted;
      else delete next[key];
      return next;
    }),
  };
  function confirm() {
    if (!saves.verified || saves.busy || !enabled) return;
    saves.confirm('');
    saves.update(drafts => Object.fromEntries(Object.entries(drafts).filter(([, draft]) => {
      const actual = latest.current?.find(row => row.notice_id === draft.id);
      return !actual || !noticeAmountMatches(draft.value, actual[draft.field]);
    })));
    attempt.current = null;
  }
  const checking = { ...saves.drafts };
  if (attempt.current) { const key = keyOf(attempt.current.id, attempt.current.field); checking[key] ??= attempt.current; }
  const readback = saves.verified ? Object.entries(checking).map(([key, draft]) => {
    const row = latest.current?.find(item => item.notice_id === draft.id);
    return { key, bill: row?.bill_no ?? '通知书已不在列表', field: noticeAmountLabels[draft.field], input: draft.value,
      submitted: attempt.current?.id === draft.id && attempt.current.field === draft.field ? attempt.current.value : null,
      actual: row ? money(row[draft.field]) : '未读到' };
  }) : [];
  return { ...saves, cells, confirm, readback };
}

export function StatCell({ row, field }: { row: NoticeRow; field: Field }) {
  const cells = useContext(NoticeCells)!, key = keyOf(row.notice_id, field), draft = cells.drafts[key];
  return <input className={row.edited_fields.includes(field) ? 'notice-edited' : ''}
    aria-label={`${row.bill_no}${field === 'amount_approved' ? '审批金额' : field === 'stat_settle' ? '统计结算金额' : '统计付款金额'}`}
    aria-invalid={Boolean(draft?.error)} title={draft?.error || `${field === 'amount_approved' ? '手动行审批金额；两个统计金额不得超过它' : `上限 = 审批金额 ${money(row.amount_approved)}`}；保存失败保留输入`}
    inputMode="decimal" value={draft?.value ?? row[field]} disabled={cells.disabled || row.is_excluded || row.is_revoked}
    onChange={event => cells.change(row, field, event.target.value)} onBlur={() => cells.save(key)} onKeyDown={event => {
      if (event.nativeEvent.isComposing) return;
      if (event.key === 'Enter') { event.preventDefault(); cells.save(key, true); }
      if (event.key === 'Escape') cells.cancel(key);
    }} />;
}
