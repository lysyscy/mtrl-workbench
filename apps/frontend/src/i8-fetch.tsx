import Button from 'antd/es/button';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, body, record, requestJson } from './api';
import type { Identity } from './api';
import { SESSION_MODE_BROWSER, sessionPayload } from './i8-browser-relay';
import { useI8Session } from './i8-session';
import { readRecords, recordSource } from './i8-api';
import type { sourceNames } from './i8-api';
import { useHistoryGuard } from './history';

interface FetchRequest<T> {
  path: string;
  payload: Record<string, unknown>;
  http?: Record<string, unknown>;
  parse: (value: unknown) => T;
}
interface Options {
  source?: keyof typeof sourceNames | 'mechanical';
  me: Identity | null;
  paused: boolean;
  refresh: () => Promise<unknown>;
  enabled?: boolean;
  pending?: boolean;
  onPending?: (pending: boolean) => void;
}

/** Shared execution lifecycle. Domains own scope, response meaning and subsequent adoption. */
export function useI8FetchAction({source, me, paused, refresh, enabled = true, pending: initialPending = false, onPending}: Options) {
  const session = useI8Session();
  // Monthly pages already retain the exact pending month; use that owner when supplied.
  const storageKey = source && !onPending ? `i8-fetch-pending:${source}:${me?.account ?? ''}` : '';
  const [restored] = useState(() => {
    try {return initialPending || Boolean(storageKey && sessionStorage.getItem(storageKey));}
    catch {return initialPending;}
  });
  const [busy, setBusy] = useState(false), [sent, setSent] = useState(restored);
  const [pending, setPending] = useState(restored), [error, setError] = useState(''), [storageError, setStorageError] = useState('');
  const [refreshError, setRefreshError] = useState(''), [refreshing, setRefreshing] = useState(false);
  const lock = useRef(false), pendingRef = useRef(restored), alive = useRef(true);
  useHistoryGuard(`i8-fetch-${source ?? 'monthly'}`, () => busy || refreshing ? 'i8 抓取正在处理，请稍候。' : pending ? 'i8 抓取结果待核实，请先核对。' : '');
  useEffect(() => {alive.current = true; return () => {alive.current = false;};}, []);
  const config = useQuery({
    queryKey: ['i8-fetch-config', me?.account], enabled: enabled && !paused && Boolean(me),
    staleTime: 0, refetchOnMount: 'always', retry: false,
    queryFn: async ({signal}) => {
      const value = await requestJson('/api/m02/config', {signal});
      if (!record(value) || typeof value.ready !== 'boolean' || typeof value.account !== 'string'
        || typeof value.i8_user !== 'string' || typeof value.message !== 'string') throw new ApiError('i8 绑定读取不完整，请重读。');
      return {ready: value.ready, account: value.account, i8_user: value.i8_user, message: value.message};
    },
  });
  const browserBlocked = session.mode === SESSION_MODE_BROWSER && !session.connected;
  const unavailable = paused || !enabled || busy || !me || config.isFetching || config.isError
    || !config.data?.ready || config.data.account !== me.account || browserBlocked;
  function markPending(value: boolean) {
    pendingRef.current = value;
    if (alive.current) setPending(value);
    if (storageKey) try {
      if (value) sessionStorage.setItem(storageKey, 'pending'); else sessionStorage.removeItem(storageKey);
      if (alive.current) setStorageError('');
    } catch {if (alive.current) setStorageError('本机未能记住抓取状态；刷新后请先核对执行结果，勿重复抓取。');}
    onPending?.(value);
  }
  function acknowledge() {
    if (lock.current) return;
    markPending(false);
    setError('');
  }
  function reset() {
    if (lock.current || pendingRef.current) return;
    setSent(false); setError(''); setRefreshError('');
  }
  async function reread() {
    if (lock.current || paused || !me) return;
    lock.current = true; setRefreshing(true);
    try {
      await refresh();
      if (alive.current) setRefreshError('');
    } catch (failure) {
      if (alive.current) setRefreshError(failure instanceof Error ? failure.message : '请重读台账。');
    } finally {
      lock.current = false;
      if (alive.current) setRefreshing(false);
    }
  }
  async function run<T>({path, payload, http = {}, parse}: FetchRequest<T>): Promise<T | undefined> {
    if (unavailable || lock.current || pendingRef.current) return undefined;
    lock.current = true; setBusy(true); setError(''); setRefreshError('');
    let confirmed = false, issued = false, parsed: T | undefined;
    try {
      const request = sessionPayload(session, http, payload);
      markPending(true); setSent(true); issued = true;
      const value = await requestJson(path, {method: 'POST', ...body(request)});
      parsed = parse(value);
      confirmed = true;
    } catch (failure) {
      confirmed = !issued || failure instanceof ApiError && failure.status > 0 && failure.status < 500 && failure.code !== 'invalid_response';
      if (alive.current) setError(failure instanceof Error ? failure.message : '抓取未完成。');
    } finally {
      if (issued) {
        try {await refresh();}
        catch (failure) {
          const reason = failure instanceof Error ? failure.message : '请重读核对。';
          // Mechanical fetch produces a preview for adoption and keeps its own recovery policy.
          if (source === 'mechanical') confirmed = false;
          if (alive.current) {
            if (parsed !== undefined && confirmed) setRefreshError(reason);
            else setError(previous => `${previous} 抓取后的数据重读失败：${reason}`);
          }
        }
      }
      if (confirmed) markPending(false);
      lock.current = false;
      if (alive.current) setBusy(false);
    }
    return alive.current ? parsed : undefined;
  }
  const browserRecovery = browserBlocked && session.maintaining ? session.notice || '正在自动连接浏览器会话，请稍候。' : '';
  return {busy, sent, pending, error, storageError, refreshError, refreshing, unavailable, browserBlocked, browserRecovery, config, mode: session.mode, run, reset, acknowledge, reread};
}

export type I8FetchAction = ReturnType<typeof useI8FetchAction>;

/** Binding, session and execution feedback are identical across all fetch entry points. */
export function I8FetchStatus({action, me, showBinding = true, alwaysShowMode = false}: {
  action: I8FetchAction; me: Identity | null; showBinding?: boolean; alwaysShowMode?: boolean;
}) {
  const {config} = action;
  return <>
    {showBinding && (config.isPending ? <p role="status">正在核对 i8 绑定…</p>
      : config.isError ? <p className="notice" role="alert">{config.error.message}<Button disabled={action.busy} onClick={() => void config.refetch()}>重读绑定</Button></p>
      : <p>当前账号：{me?.name || me?.account}，i8 绑定：{config.data.i8_user || '未绑定'}</p>)}
    {config.data && (!config.data.ready || config.data.account !== me?.account) && <p className="notice" role="alert">{config.data.message || '账号已变化，请关闭后重新打开。'}</p>}
    {(!action.sent || alwaysShowMode) && <p className="i8-fetch-mode">{action.mode === SESSION_MODE_BROWSER
      ? '使用浏览器已有会话，不登录、不顶号；会话失效时停止。'
      : '使用工作台直连，可能使该 i8 账号的其他会话下线；失败不会自动重试。'}</p>}
    {action.browserBlocked && (action.browserRecovery
      ? <p className="notice" role="status">{action.browserRecovery}</p>
      : <p className="notice" role="alert">浏览器会话未连接，请到「i8 接入」页连接后再抓取。本次不会改用工作台直连。</p>)}
    {action.busy && <p role="status">正在抓取，请稍候…</p>}
    {action.error && <p className="notice" role="alert">{action.error}</p>}
    {action.refreshError && <div className="notice" role="alert">
      抓取已完成，台账暂未刷新。{action.refreshError}
      <Button disabled={action.refreshing} onClick={() => void action.reread()}>{action.refreshing ? '正在重读…' : '重读台账'}</Button>
    </div>}
    {action.storageError && <p className="notice" role="alert">{action.storageError}</p>}
  </>;
}

/** Existing execution records help resolve an unknown response; this never retries a fetch. */
export function I8FetchRecovery({action, source, scope = '', onAcknowledged}: {
  action: I8FetchAction; source: keyof typeof sourceNames; scope?: string; onAcknowledged?: () => void;
}) {
  const records = useQuery({queryKey: ['i8-fetch-records', source], enabled: false,
    queryFn: async ({signal}) => readRecords(await requestJson('/api/m02/fetch/records?limit=50', {signal}))});
  const [verified, setVerified] = useState(false);
  const relevant = records.data?.filter(row => recordSource(row) === source) ?? [];
  if (!action.pending || action.busy) return null;
  return <div className="notice">
    <p>{scope ? `${scope} 的` : ''}抓取结果待核实。请核对执行记录，确认没有在途任务后再安排下一次。</p>
    <Button disabled={records.isFetching} onClick={async () => {setVerified(false); const read = await records.refetch(); setVerified(!read.isError);}}>读取执行记录</Button>
    {records.isError && <p role="alert">{records.error.message}</p>}
    {records.data && <>{!relevant.length && <p>最近记录中未找到此类抓取，请先核实原任务是否仍在处理。</p>}<ul>{relevant.map(row => <li key={row.id}>{row.started_at}，{row.target}，{row.status}，{row.error_message}</li>)}</ul>
      <Button disabled={!verified || records.isFetching || records.isError || relevant.some(row => row.status === 'running')}
        onClick={() => {action.acknowledge(); onAcknowledged?.();}}>已核对，无在途任务</Button></>}
  </div>;
}

export function I8FetchActions({action, close, canRun = true, onRun, label = '确认抓取'}: {
  action: I8FetchAction; close: () => void; canRun?: boolean; onRun: () => void; label?: string;
}) {
  return <div className="dialog-actions">
    <Button htmlType="button" disabled={action.busy || action.refreshing} onClick={close}>{action.sent ? '关闭' : '取消'}</Button>
    {!action.sent && <Button htmlType="button" type="primary" disabled={action.unavailable || action.pending || !canRun} onClick={onRun}>{label}</Button>}
  </div>;
}
