import { BusinessDate } from './time-picker';
import { ProjectPicker } from './ledger-controls';
import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { createContext, useContext, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, assertAmountText, confirmWrite, record, requestJson, uncertainWrite } from './api';
import type { Project } from './api';
import { body, categories, currentMonth, money, receipt } from './notices-api';
import type { NoticeRow } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';

export type Draft = { row_id: string; doc_date: string; bill_no: string; bill_name: string; biz_type: string; payee: string; category: string; amount_approved: string; stat_settle: string; stat_paid: string; ownership_id: string; approve_status: string };
export function manualDraft(row?: NoticeRow): Draft {
  return { row_id: row ? String(row.notice_id) : '', doc_date: row?.doc_date ?? `${currentMonth()}-01`, bill_no: row?.bill_no ?? '', bill_name: row?.bill_name ?? '', biz_type: row?.biz_type ?? '', payee: row?.payee ?? '', category: row?.category ?? 'material', amount_approved: row?.amount_approved ?? '0', stat_settle: row?.stat_settle ?? '0', stat_paid: row?.stat_paid ?? '0', ownership_id: row?.ownership_id ? String(row.ownership_id) : '', approve_status: row?.approve_status ?? '已批' };
}
export const NoticeDraftDisabled = createContext(false);
export function DraftField({ draft, field, label, projects }: { draft: Draft; field: keyof Draft; label: string; projects: Project[] }) {
  const disabled = useContext(NoticeDraftDisabled);
  const [value, setValue] = useState(draft[field]);
  const choose = (next: string) => { draft[field] = next; setValue(next); };
  if (field === 'ownership_id') return <ProjectPicker projects={projects.filter(p => p.project_type !== 'shell')} selected={value ? [Number(value)] : []} pick={ids => choose(String(ids[0] ?? ''))} label={`草稿${label}`} disabled={disabled} />;
  if (field === 'doc_date') return <BusinessDate label={`草稿${label}`} value={value} onChange={choose} disabled={disabled} />;
  const options = field === 'category' ? Object.entries(categories) : field === 'approve_status' ? [['已批','已批'],['未批','未批']] : null;
  return options ? <select aria-label={`草稿${label}`} defaultValue={draft[field]} disabled={disabled} onChange={e => { draft[field] = e.target.value; }}>{options.map(([v,t]) => <option key={v} value={v} data-notice-approval={field === 'approve_status' ? v : undefined}>{t}</option>)}</select> : <input autoFocus={!draft.row_id && field === 'bill_no'} aria-label={`草稿${label}`} type="text" inputMode={['amount_approved','stat_settle','stat_paid'].includes(field) ? 'decimal' : undefined} defaultValue={draft[field]} disabled={disabled} onChange={e => { draft[field] = e.target.value; }} />;
}

export function NoticeDeleteDialog({ row, blocked, close, refresh, announce }: {
  row: NoticeRow; blocked: boolean; close: () => void; refresh: () => Promise<NoticeRow[]>; announce: (message: string) => void;
}) {
  const lock = useRef(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [readback, setReadback] = useState<'saved' | 'unknown' | null>(null);
  const query = useQuery({
    queryKey: ['notice-maintenance', 'delete', row.notice_id, row.bill_no],
    enabled: !blocked && readback === null, refetchOnMount: 'always',
    queryFn: async ({ signal }) => {
      const data = await requestJson('/api/m03/actions/manual-delete-impact', {
        method: 'POST', signal, ...body({ notice_id: row.notice_id }),
      });
      if (!record(data) || data.notice_id !== row.notice_id || typeof data.project_name !== 'string'
        || typeof data.doc_date !== 'string' || !Array.isArray(data.effects)
        || !data.effects.every(effect => typeof effect === 'string')) {
        throw new ApiError('删除影响读取不完整，请重读。');
      }
      const { project_name, doc_date, stat_settle, stat_paid, amount_paid, effects } = data;
      assertAmountText(stat_settle);
      assertAmountText(stat_paid);
      assertAmountText(amount_paid);
      return { project_name, doc_date, stat_settle, stat_paid, amount_paid, effects };
    },
  });
  const data = query.data;
  const unavailable = blocked || busy || readback !== null || query.isFetching || query.isError || !data;
  const closing = useDialogClose({ busy: busy || readback !== null, dirty: false, close, active: !blocked });

  async function isStillListed() {
    const latest = await refresh();
    return latest.some(item => item.notice_id === row.notice_id);
  }

  async function remove() {
    if (unavailable || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    let saved = false;
    try {
      const response = await requestJson('/api/m03/actions/manual-delete', {
        method: 'POST', ...body({ notice_id: row.notice_id }),
      });
      confirmWrite(record(response) && response.ok === true && response.notice_id === row.notice_id
        && typeof response.message === 'string', '删除回执与本条通知书不一致。');
      saved = true;
      if (await isStillListed()) throw new Error('列表仍可见这条通知书。');
      announce(receipt(response)); close();
    } catch (failure) {
      const detail = failure instanceof Error ? failure.message : '操作未完成，请重试。';
      if (saved || uncertainWrite(failure)) {
        setReadback(saved ? 'saved' : 'unknown');
        setError(`${saved ? '已收到删除回执，列表仍待核对。' : '删除结果待核实。'}请重读核对，勿重复提交。${detail}`);
      } else setError(detail);
    } finally { setBusy(false); lock.current = false; }
  }

  async function reread() {
    if (blocked || lock.current || readback === null) return;
    lock.current = true; setBusy(true);
    try {
      const listed = await isStillListed();
      if (listed && readback === 'saved') throw new Error('列表仍可见这条通知书。');
      announce(listed ? '已重读列表，这条通知书仍在。' : `已重读列表，${row.bill_no} 已移出。`);
      close();
    } catch (failure) {
      setError(`删除结果仍待核实，请重读核对。${failure instanceof Error ? failure.message : ''}`);
    } finally { setBusy(false); lock.current = false; }
  }

  const titleId = 'notice-maintenance-title';
  return <BusinessModal open={!blocked} className="project-dialog notice-dialog" titleId={titleId} requestClose={closing.requestClose}>
    <DialogContents title="删除手动通知书" titleId={titleId} closing={closing}>
      <form onSubmit={event => { event.preventDefault(); void remove(); }}>
        <p>{row.bill_no}，{row.bill_name}，{row.project_display}</p>
        {query.isPending && <p role="status">正在读取…</p>}
        {query.isError && <p className="notice" role="alert">{query.error.message}<Button htmlType="button" onClick={() => void query.refetch()}>重试读取</Button></p>}
        {data && <>
          <h3>删除影响</h3>
          <dl className="notice-delete-impact">
            <div><dt>项目</dt><dd>{data.project_name || '—'}</dd></div>
            <div><dt>单据日期</dt><dd>{data.doc_date || '—'}</dd></div>
            {([['统计结算金额', data.stat_settle], ['统计付款金额', data.stat_paid], ['已付金额（流水）', data.amount_paid]] as const).map(([label, amount]) =>
              <div key={label}><dt>{label}</dt><dd className="money">{money(amount)} 元</dd></div>)}
          </dl>
          <ul>{data.effects.map(effect => <li key={effect}>{effect.replace(/\*\*/g, '')
            .replace(/-?\d+\.\d{2}(?![\d.])/g, amount => `${money(amount)} 元`)}</li>)}</ul>
        </>}
        {error && <p className="notice" role="alert">{error}</p>}
        <div className="dialog-actions">
          {readback ? <Button htmlType="button" type="primary" loading={busy} disabled={blocked} onClick={() => void reread()}>重读核对</Button>
            : <>
              <Button htmlType="button" disabled={busy} onClick={closing.requestClose}>取消</Button>
              <Button htmlType="submit" danger loading={busy} disabled={unavailable}>确认删除</Button>
            </>}
        </div>
      </form>
    </DialogContents>
  </BusinessModal>;
}
