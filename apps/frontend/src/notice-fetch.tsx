import Button from 'antd/es/button';
import { useRef, useState } from 'react';
import type { Identity } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { I8FetchActions, I8FetchStatus, useI8FetchAction } from './i8-fetch';
import { noticeFetchJobsPath, readNoticeFetchJob } from './notice-fetch-job-data';
import { useNoticeFetchJobs } from './notice-fetch-jobs';
import { currentMonth } from './notices-api';
import { TimePicker } from './time-picker';

export function NoticeFetch({ me, blocked, close }: { me: Identity | null; blocked: boolean; close: () => void }) {
  const jobs = useNoticeFetchJobs();
  const [month, setMonth] = useState(currentMonth);
  const [checking, setChecking] = useState(false);
  const [recovery, setRecovery] = useState<{ message: string; checked: boolean }>();
  const previousJob = useRef<number | undefined>(undefined);
  const action = useI8FetchAction({ me, paused: blocked, source: 'notices', scopeKey: month });
  const closing = useDialogClose({
    busy: action.busy || checking, dirty: false,
    beforeRequestClose: action.cancelWaiting, close: () => { void action.cancelKick(); close(); }, active: !blocked,
  });
  const validMonth = /^\d{4}-(0[1-9]|1[0-2])$/.test(month);

  function run() {
    if (!me || !validMonth) return;
    previousJob.current = jobs.currentId;
    void action.run({
      path: noticeFetchJobsPath,
      payload: { year_month: month, expected_account: me.account },
      parse: value => readNoticeFetchJob(value, { account: me.account, month }),
      onSuccess: job => { jobs.accept(job); close(); },
    });
  }

  async function recover() {
    setChecking(true);
    setRecovery(undefined);
    try {
      const job = await jobs.recover();
      if (job?.year_month === month && (job.status === 'running' || job.id !== previousJob.current)) {
        jobs.accept(job);
        action.acknowledge();
        close();
        return;
      }
      setRecovery({ message: '尚未读到本月新任务。请核对执行记录后再重新发起。', checked: true });
    } catch (failure) {
      setRecovery({ message: failure instanceof Error ? failure.message : '读取抓取任务失败，请重试。', checked: false });
    } finally { setChecking(false); }
  }

  return <BusinessModal open={!blocked} layout="compact" className="project-dialog notice-dialog" titleId="notice-fetch-title" requestClose={closing.requestClose}>
    <DialogContents titleId="notice-fetch-title" title="抓取 i8 付款通知书" closing={closing}>
      <div className="dialog-body">
        <div className="notice-fetch-connection" role="group" aria-label="账号与 i8 会话">
          <I8FetchStatus action={action} me={me} busyLabel="正在确认抓取任务…" />
        </div>
        {(!action.sent || action.busy) && <div className="notice-fetch-range" role="group" aria-label="抓取范围">
          <div className="time-picker-field"><span>抓取月份</span><TimePicker label="抓取月份" value={month} modes={['月']}
            disabled={action.busy || blocked} onChange={value => { setMonth(value); setRecovery(undefined); action.reset(); }} /></div>
          <p>按所选月份全量抓取。保存后自动关联本次新增或刚转为已批、且依据明确的集采通知书。</p>
        </div>}
        {action.pending && !action.busy && <div className="notice">
          <p>抓取任务是否已受理尚待核对。</p>
          <Button loading={checking} onClick={() => void recover()}>读取抓取任务</Button>
          {recovery && <p role="status">{recovery.message}</p>}
          {recovery?.checked && <Button disabled={checking} onClick={() => { action.acknowledge(); action.reset(); setRecovery(undefined); }}>
            已核对，返回抓取
          </Button>}
        </div>}
      </div>
      <I8FetchActions action={action} close={closing.requestClose} canRun={validMonth} onRun={run} />
    </DialogContents>
  </BusinessModal>;
}
