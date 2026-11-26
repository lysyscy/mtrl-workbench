import Button from 'antd/es/button';
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Query } from '@tanstack/react-query';
import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import {
  acknowledgeNoticeFetchJob, fetchJobPollInterval, fetchJobViews, latestFetchJob, pollNoticeFetchJob, recoverNoticeFetchJob,
} from './notice-fetch-job-data';
import type { FinishedNoticeFetchJob, NoticeFetchJob } from './notice-fetch-job-data';

const FetchMatchDetails = lazy(() => import('./notice-match-list').then(module => ({ default: module.FetchMatchDetails })));

function fetchJobKey(account: string, id: number | 'active') {
  return ['notice-fetch-job', account, id];
}

type JobActions = {
  accept: (job: NoticeFetchJob) => void;
  currentId: number | undefined;
  recover: () => Promise<NoticeFetchJob | null | undefined>;
};
const JobContext = createContext<JobActions | null>(null);

export function useNoticeFetchJobs() {
  const jobs = useContext(JobContext);
  if (!jobs) throw new Error('抓取窗口需要账号工作区。');
  return jobs;
}

export function NoticeFetchJobs({ account, paused, children }: { account: string; paused: boolean; children: ReactNode }) {
  const client = useQueryClient();
  const [ids, setIds] = useState<number[]>([]);
  const refreshed = useRef(new Set<number>());
  const enabled = Boolean(account) && !paused;
  const active = useQuery({
    queryKey: fetchJobKey(account, 'active'), enabled, refetchOnMount: 'always', refetchOnWindowFocus: true,
    queryFn: ({ signal }) => recoverNoticeFetchJob(account, signal),
  });
  const accept = useCallback((job: NoticeFetchJob) => {
    client.setQueryData<NoticeFetchJob>(fetchJobKey(account, job.id), previous => latestFetchJob(previous, job));
    setIds(previous => previous.includes(job.id) ? previous : [...previous, job.id]);
  }, [account, client]);
  useEffect(() => {
    if (active.data && active.data.acknowledged_at === null) accept(active.data);
  }, [active.data, accept]);

  const reads = useQueries({ queries: ids.map(id => ({
    queryKey: fetchJobKey(account, id), enabled,
    queryFn: async ({ signal }) => {
      const response = await pollNoticeFetchJob(account, id, signal);
      return latestFetchJob(client.getQueryData<NoticeFetchJob>(fetchJobKey(account, id)), response);
    },
    refetchInterval: (query: Query<NoticeFetchJob>) => fetchJobPollInterval(query.state.data),
  })) });
  const { running, finished } = fetchJobViews(reads.flatMap(read => read.data ?? []));
  const pollingError = reads.find(read => read.data?.id === running?.id)?.error;

  useEffect(() => {
    if (!finished || refreshed.current.has(finished.id)) return;
    refreshed.current.add(finished.id);
    void client.invalidateQueries({ refetchType: 'none', predicate: query => query.queryKey[0] !== 'notice-fetch-job' });
    for (const key of ['notices', 'notice-ownership-pending', 'projects', 'history', 'contracts']) {
      void client.invalidateQueries({ queryKey: [key] });
    }
  }, [client, finished]);

  async function acknowledge(job: FinishedNoticeFetchJob) {
    const id = job.id;
    const acknowledged = await acknowledgeNoticeFetchJob(account, id);
    client.setQueryData(fetchJobKey(account, id), acknowledged);
    client.setQueryData<NoticeFetchJob | null>(fetchJobKey(account, 'active'), previous =>
      previous?.id === id ? null : previous);
    setIds(previous => previous.filter(current => current !== id));
    void client.invalidateQueries({ queryKey: fetchJobKey(account, 'active'), exact: true });
  }

  return <JobContext.Provider value={{
    accept, currentId: Math.max(active.data?.id ?? 0, ...ids) || undefined,
    recover: async () => (await active.refetch({ throwOnError: true })).data,
  }}>
    {children}
    {running && <aside className="notice-fetch-progress" role="status">
      <span>{running.year_month} {pollingError ? '正在重读抓取进度…' : running.stage_label}</span>
      <progress aria-label="付款通知书抓取进度" />
    </aside>}
    {finished && <FetchResult key={finished.id} job={finished} acknowledge={() => acknowledge(finished)} />}
  </JobContext.Provider>;
}

function FetchResult({ job, acknowledge }: { job: FinishedNoticeFetchJob; acknowledge: () => Promise<void> }) {
  const [closingResult, setClosingResult] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const result = job.result;
  const title = job.status === 'completed' ? '付款通知书抓取完成'
    : result.notices_saved ? '通知书已保存，自动关联未完成' : '付款通知书抓取失败';
  async function close() {
    if (lock.current) return;
    lock.current = true;
    setClosingResult(true);
    setError('');
    try { await acknowledge(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '关闭结果失败，请重试。'); }
    finally { lock.current = false; setClosingResult(false); }
  }
  const closing = useDialogClose({ busy: closingResult, dirty: false, close: () => void close() });
  return <BusinessModal open zIndex={1600} layout="scroll-body" className="project-dialog notice-contract-dialog notice-fetch-result"
    titleId="notice-fetch-result-title" requestClose={closing.requestClose}>
    <DialogContents title={title} titleId="notice-fetch-result-title" closing={closing}>
      <div className="dialog-body">
        <p className="notice-fetch-month">抓取月份 {job.year_month}</p>
        {job.status === 'failed' && <p className="notice" role="alert">{job.error_message}</p>}
        {result.payable_source_failed && <p className="notice" role="alert">
          通知书已保存，采购应付读取失败。{result.payable_source_error}
        </p>}
        {(result.notices_saved || result.fetched > 0) && <dl className="notice-fetch-counts">
          {([
            ['i8 返回', result.fetched], ['已保存', result.saved], ['新增', result.created],
            ['更新', result.updated], ['剔除', result.excluded], ['待归属未写入', result.unresolved],
          ] as const).map(([label, count]) => <div key={label}><dt>{label}</dt><dd>{count}</dd></div>)}
        </dl>}
        {result.notices_saved && <Suspense fallback={<p role="status">正在加载关联明细…</p>}>
          <FetchMatchDetails result={result} />
        </Suspense>}
        {error && <p className="notice" role="alert">{error}</p>}
      </div>
      <div className="dialog-actions">
        <Button htmlType="button" type="primary" loading={closingResult} onClick={closing.requestClose}>关闭</Button>
      </div>
    </DialogContents>
  </BusinessModal>;
}
