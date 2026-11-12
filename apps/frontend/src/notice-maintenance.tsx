import { BusinessDate } from './time-picker';
import { ProjectPicker } from './ledger-controls';
import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import type { Project } from './api';
import { body, categories, currentMonth, receipt } from './notices-api';
import type { NoticeRow } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';

export type Draft = { row_id: string; doc_date: string; bill_no: string; bill_name: string; biz_type: string; payee: string; category: string; amount_approved: string; stat_settle: string; stat_paid: string; ownership_id: string; approve_status: string };
export function manualDraft(row?: NoticeRow): Draft {
  return { row_id: row ? String(row.notice_id) : '', doc_date: row?.doc_date ?? `${currentMonth()}-01`, bill_no: row?.bill_no ?? '', bill_name: row?.bill_name ?? '', biz_type: row?.biz_type ?? '', payee: row?.payee ?? '', category: row?.category ?? 'material', amount_approved: row?.amount_approved ?? '0', stat_settle: row?.stat_settle ?? '0', stat_paid: row?.stat_paid ?? '0', ownership_id: row?.ownership_id ? String(row.ownership_id) : '', approve_status: row?.approve_status ?? '已批' };
}
export function DraftField({ draft, field, label, disabled, projects }: { draft: Draft; field: keyof Draft; label: string; disabled: boolean; projects: Project[] }) {
  const [value, setValue] = useState(draft[field]);
  const choose = (next: string) => { draft[field] = next; setValue(next); };
  if (field === 'ownership_id') return <ProjectPicker projects={projects.filter(p => p.project_type !== 'shell')} selected={value ? [Number(value)] : []} pick={ids => choose(String(ids[0] ?? ''))} label={`草稿${label}`} disabled={disabled} />;
  if (field === 'doc_date') return <BusinessDate label={`草稿${label}`} value={value} onChange={choose} disabled={disabled} />;
  const options = field === 'category' ? Object.entries(categories) : field === 'approve_status' ? [['已批','已批'],['未批','未批']] : null;
  return options ? <select aria-label={`草稿${label}`} defaultValue={draft[field]} disabled={disabled} onChange={e => { draft[field] = e.target.value; }}>{options.map(([v,t]) => <option key={v} value={v}>{t}</option>)}</select> : <input autoFocus={!draft.row_id && field === 'bill_no'} aria-label={`草稿${label}`} type="text" inputMode={['amount_approved','stat_settle','stat_paid'].includes(field) ? 'decimal' : undefined} defaultValue={draft[field]} disabled={disabled} onChange={e => { draft[field] = e.target.value; }} />;
}

export function NoticeDeleteDialog({ row, blocked, close, refresh, announce }: {
  row: NoticeRow; blocked: boolean; close: () => void; refresh: () => Promise<unknown>; announce: (message: string) => void;
}) {
  const lock = useRef(false);
  const [busy, setBusy] = useState(false), [done, setDone] = useState(false), [error, setError] = useState('');
  const query = useQuery({
    queryKey: ['notice-maintenance', 'delete', row.notice_id, row.bill_no],
    enabled: !blocked, refetchOnMount: 'always',
    queryFn: async ({ signal }) => {
      const data = await requestJson('/api/m03/actions/manual-delete-impact', {
        method: 'POST', signal, ...body({ notice_id: row.notice_id }),
      });
      if (!record(data) || typeof data.message !== 'string' || !Array.isArray(data.effects)) {
        throw new ApiError('删除影响读取不完整，请重读。');
      }
      return data;
    },
  });
  const data = query.data;
  const unavailable = blocked || busy || done || query.isFetching || !data;
  const closing = useDialogClose({ busy, dirty: false, close, active: !blocked });

  async function remove() {
    if (unavailable || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    let saved = false;
    try {
      const response = await requestJson('/api/m03/actions/manual-delete', {
        method: 'POST', ...body({ notice_id: row.notice_id }),
      });
      saved = true; setDone(true);
      announce(receipt(response)); await refresh(); close();
    } catch (failure) {
      const detail = failure instanceof Error ? failure.message : '操作未完成，请重试。';
      setError(saved ? '操作已保存，但读取尚待核对；请关闭后重读，勿重复保存。' + detail : detail);
    } finally { setBusy(false); lock.current = false; }
  }

  const titleId = 'notice-maintenance-title';
  return <BusinessModal open={!blocked} className="project-dialog notice-dialog" titleId={titleId} requestClose={closing.requestClose}>
    <DialogContents title="删除手动通知书" titleId={titleId} closing={closing}>
      <form onSubmit={event => { event.preventDefault(); void remove(); }}>
        <p>{row.bill_no}，{row.bill_name}，{row.project_display}</p>
        {query.isPending && <p role="status">正在读取…</p>}
        {query.isError && <p className="notice" role="alert">{query.error.message}<Button onClick={() => void query.refetch()}>重读候选</Button></p>}
        {data && <>
          <p className="danger">{receipt(data)}</p>
          <dl>{[['项目', data.project_name], ['单据日期', data.doc_date], ['统计结算金额', data.stat_settle], ['统计付款金额', data.stat_paid], ['已付金额（流水）', data.amount_paid]].map(([label, number]) =>
            <div key={String(label)}><dt>{String(label)}</dt><dd>{String(number)}</dd></div>)}</dl>
          <ul>{(data.effects as string[]).map(effect => <li key={effect}>{effect.replace(/\*\*/g, '')}</li>)}</ul>
        </>}
        {error && <p className="notice" role="alert">{error}</p>}
        <div className="dialog-actions">
          <Button disabled={busy} onClick={closing.requestClose}>{done ? '关闭' : '取消'}</Button>
          {!done && <Button htmlType="submit" className="danger" disabled={unavailable}>确认删除</Button>}
        </div>
      </form>
    </DialogContents>
  </BusinessModal>;
}
