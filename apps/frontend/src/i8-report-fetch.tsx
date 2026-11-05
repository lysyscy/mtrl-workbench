import { useState } from 'react';
import type { Identity } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { TimePicker } from './time-picker';
import { I8FetchActions, I8FetchRecovery, I8FetchStatus, useI8FetchAction } from './i8-fetch';
import { readReportFetchResult, reportFetch } from './i8-report-fetch-api';
import type { ReportFetchResult, ReportSource } from './i8-report-fetch-api';

/** Keep the exact month through closing/reopening and retain the existing inventory storage key. */
export function useReportFetchPending(source: ReportSource, account: string) {
  const key = `${source}-fetch-pending:${account}`;
  const [month, setMonth] = useState<string | null>(() => {try {return sessionStorage.getItem(key);} catch {return null;}});
  const [error, setError] = useState('');
  function update(value: string | null) {
    setMonth(value);
    try {if (value) sessionStorage.setItem(key, value); else sessionStorage.removeItem(key); setError('');}
    catch {setError('本机未能记住抓取状态；刷新后请先核对 i8 执行记录，勿重复抓取。');}
  }
  return {month, update, error};
}

export interface ReportFetchProps {
  month: string; me: Identity | null; paused: boolean; close: () => void; refresh: () => Promise<void>;
  pending: boolean; onPending: (month: string | null) => void;
}

export function I8ReportFetch({source, month: initial, me, paused, close, refresh, pending, onPending}: ReportFetchProps & {source: ReportSource}) {
  const [month, setMonth] = useState(initial), [result, setResult] = useState<ReportFetchResult | null>(null);
  const action = useI8FetchAction({source, me, paused, refresh, pending, onPending: value => onPending(value ? month : null)});
  const closing = useDialogClose({busy: action.busy, dirty: !action.sent && month !== initial, close, active: !paused});
  const spec = reportFetch[source], titleId = `${source}-fetch-title`;
  async function run() {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) return;
    const value = await action.run({path: spec.path, payload: {month, confirm: true}, parse: value => readReportFetchResult(source, month, value)});
    if (value) setResult(value);
  }
  return <BusinessModal open={!paused} requestClose={closing.requestClose} className="inventory-dialog" titleId={titleId}>
    <DialogContents title={`按月抓取${spec.title}`} titleId={titleId} closing={closing}>
      {!action.sent && <><label className="inventory-fields">抓取月份<TimePicker label={`${spec.title}抓取月份`} value={month} modes={['月']} onChange={setMonth} disabled={action.busy || paused} /></label><p>{spec.scope}</p></>}
      <I8FetchStatus action={action} me={me}/>
      {result && <p className={result.ok ? '' : 'notice'} role={result.ok ? 'status' : 'alert'}>{result.message}</p>}
      <I8FetchRecovery action={action} source={source} scope={month} onAcknowledged={close}/>
      <I8FetchActions action={action} close={closing.requestClose} canRun={/^\d{4}-(0[1-9]|1[0-2])$/.test(month)} onRun={() => void run()} label={`确认按 ${month} 抓取`}/>
    </DialogContents>
  </BusinessModal>;
}
