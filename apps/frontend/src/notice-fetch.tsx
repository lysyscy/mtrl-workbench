import { useRef, useState } from 'react';
import { ApiError, record } from './api';
import type { Identity } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { I8FetchActions, I8FetchRecovery, I8FetchStatus, useI8FetchAction } from './i8-fetch';
import { I8FetchReceiptContents } from './i8-fetch-receipt';
import { readFetchReceipt } from './i8-api';
import type { FetchReceipt } from './i8-api';
import { currentMonth } from './notices-api';
import { TimePicker } from './time-picker';

function readNoticeFetch(value: unknown, month: string): FetchReceipt {
  if (!record(value) || value.year_month !== month || typeof value.fetched !== 'number' || typeof value.upserted !== 'number' ||
    !Array.isArray(value.ignored) || !value.ignored.every(item => record(item) && ['bill_no', 'project_name', 'doc_name', 'reason'].every(key => typeof item[key] === 'string'))) {
    throw new ApiError('付款通知书抓取回执不完整。');
  }
  if (value.receipt != null) {
    const receipt = readFetchReceipt(value.receipt, 'notices');
    if (receipt.scope === month && ['success', 'partial'].includes(receipt.status)) return receipt;
    throw new ApiError('付款通知书抓取回执的月份不一致。', 0, 'invalid_response');
  }
  return {
    source: 'notices', scope: month, status: value.ignored.length ? 'partial' : 'success', startedAt: '', duration: null,
    summary: { total: value.fetched, written: value.upserted, unsettled: value.ignored.length },
    items: value.ignored,
  };
}

export function NoticeFetch({ me, blocked, close, refresh }: { me: Identity | null; blocked: boolean; close: () => void; refresh: () => Promise<void> }) {
  const [month, setMonth] = useState(currentMonth);
  const [result, setResult] = useState<ReturnType<typeof readNoticeFetch>>();
  const initialMonth = useRef(month);
  const action = useI8FetchAction({ me, paused: blocked, refresh, source: 'notices' });
  const closing = useDialogClose({ busy: action.busy || action.refreshing, dirty: !action.sent && month !== initialMonth.current, close, active: !blocked });
  const validMonth = /^\d{4}-(0[1-9]|1[0-2])$/.test(month);

  async function run() {
    if (!me || !validMonth) return;
    const receipt = await action.run({
      path: '/api/m03/notices/fetch',
      payload: { year_month: month, expected_account: me.account },
      http: { allow_kick: true },
      parse: value => readNoticeFetch(value, month),
    });
    if (receipt) setResult(receipt);
  }

  return <BusinessModal open={!blocked} className="project-dialog notice-result-dialog" titleId="notice-fetch-title" requestClose={closing.requestClose}>
    <DialogContents titleId="notice-fetch-title" title="抓取 i8 付款通知书（按月）" closing={closing}>
      <I8FetchStatus action={action} me={me} />
      {(!action.sent || action.busy) && <>
        <div className="time-picker-field"><span>抓取月份</span><TimePicker label="抓取月份" value={month} modes={['月']} disabled={action.busy || blocked} onChange={value => { setMonth(value); action.reset(); }} /></div>
        <p>按所选月份全量抓取，不受本页项目筛选限制。保留人工分类、已修改统计金额与集采实际供应商。</p>
      </>}
      {result && <I8FetchReceiptContents data={result} />}
      <I8FetchRecovery action={action} source="notices" />
      <I8FetchActions action={action} close={closing.requestClose} canRun={validMonth} onRun={() => void run()} />
    </DialogContents>
  </BusinessModal>;
}
