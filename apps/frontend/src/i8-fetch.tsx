import Button from 'antd/es/button';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, body, record, requestJson } from './api';
import type { Identity } from './api';
import { SESSION_MODE_BROWSER, sessionPayload } from './i8-browser-relay';
import type { SessionChoice } from './i8-browser-relay';
import { I8ConnectionWaitStatus, useI8ActionWait, useI8Session } from './i8-session';
import { readI8KickConfirmation, readRecords, recordSource, revokeI8KickToken } from './i8-api';
import type { sourceNames } from './i8-api';
import { useHistoryGuard } from './history';

interface FetchRequest<T> {
  path: string;
  payload: Record<string, unknown>;
  parse: (value: unknown) => T;
  onSuccess?: (result: T) => void;
  operate?: (issue: () => Promise<void>) => Promise<void>;
}
interface Options {
  source?: keyof typeof sourceNames | 'mechanical';
  me: Identity | null;
  paused: boolean;
  refresh: () => Promise<unknown>;
  enabled?: boolean;
  scopeKey: string;
  pending?: boolean;
  onPending?: (pending: boolean) => void;
}

interface KickConfirmation {
  token: string;
  message: string;
  key: string;
  submit: () => Promise<unknown>;
}

/** Shared execution lifecycle. Domains own scope, response meaning and subsequent adoption. */
export function useI8FetchAction({source, me, paused, refresh, enabled = true, scopeKey, pending: initialPending = false, onPending}: Options) {
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
  const kickRef = useRef<KickConfirmation | null>(null), kickGeneration = useRef(0);
  const [kickConfirmation, setKickConfirmation] = useState<KickConfirmation | null>(null);
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
  const confirmationKey = JSON.stringify([scopeKey, session.mode, me?.id, me?.account, config.data?.i8_user, config.data?.ready, paused, enabled]);
  const {waiting, cancelWaiting, runWhenReady} = useI8ActionWait(confirmationKey);
  const unavailable = paused || !enabled || busy || !me || config.isFetching || config.isError
    || !config.data?.ready || config.data.account !== me.account || waiting;
  function discardKick() {
    kickGeneration.current += 1;
    const confirmation = kickRef.current;
    kickRef.current = null;
    if (confirmation) revokeI8KickToken(confirmation.token);
  }
  useLayoutEffect(() => {
    setKickConfirmation(null);
    return discardKick;
  }, [confirmationKey]);

  function cancelKick() {
    discardKick();
    setKickConfirmation(null);
  }
  async function confirmKick() {
    const confirmation = kickRef.current;
    if (unavailable || lock.current || pendingRef.current || !confirmation || confirmation.key !== confirmationKey) return;
    kickRef.current = null;
    setKickConfirmation(null);
    await confirmation.submit();
  }
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
    cancelWaiting();
    cancelKick();
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
  async function run<T>(request: FetchRequest<T>): Promise<T | undefined> {
    if (unavailable || lock.current || pendingRef.current || kickRef.current) return undefined;
    return runWhenReady(choice => alive.current && !lock.current && !pendingRef.current
      ? issue(request, choice) : undefined);
  }

  async function issue<T>(request: FetchRequest<T>, choice: SessionChoice, retry?: ReturnType<typeof body>, token = '') {
    if (!request.operate) return submit(request, choice, retry);
    let result: T | undefined;
    let issued = false;
    await request.operate(async () => {
      issued = true;
      result = await submit(request, choice, retry);
    });
    if (!issued) revokeI8KickToken(token);
    return result;
  }

  async function submit<T>(request: FetchRequest<T>, choice: SessionChoice, retry?: ReturnType<typeof body>): Promise<T | undefined> {
    const {path, payload, parse, onSuccess} = request;
    lock.current = true; setBusy(true); setError(''); setRefreshError('');
    const generation = kickGeneration.current;
    let confirmed = false, issued = false, awaitingKick = false, parsed: T | undefined;
    let snapshot: ReturnType<typeof body> | undefined;
    try {
      snapshot = retry ?? body(sessionPayload(choice, {}, payload));
      markPending(true); setSent(true); issued = true;
      const value = await requestJson(path, {method: 'POST', ...snapshot});
      parsed = parse(value);
      confirmed = true;
    } catch (failure) {
      confirmed = !issued || failure instanceof ApiError && failure.status > 0 && failure.status < 500 && failure.code !== 'invalid_response';
      const conflict = readI8KickConfirmation(failure);
      if (conflict) {
        awaitingKick = true;
        if (alive.current && !retry) setSent(false);
        if (!retry && snapshot && session.mode !== SESSION_MODE_BROWSER
          && alive.current && generation === kickGeneration.current) {
          const confirmedBody = body({...JSON.parse(snapshot.body), kick_token: conflict.token});
          const confirmation = {
            ...conflict, key: confirmationKey,
            submit: () => issue(request, choice, confirmedBody, conflict.token),
          };
          kickRef.current = confirmation;
          setKickConfirmation(confirmation);
        } else {
          revokeI8KickToken(conflict.token);
          if (retry && alive.current) setError(conflict.message);
        }
      } else if (alive.current) setError(failure instanceof Error ? failure.message : '抓取未完成。');
    } finally {
      if (issued && !awaitingKick) {
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
    if (alive.current && parsed !== undefined) onSuccess?.(parsed);
    return alive.current ? parsed : undefined;
  }
  const kickMessage = kickConfirmation?.key === confirmationKey ? kickConfirmation.message : '';
  return {busy, sent, pending, error, storageError, refreshError, refreshing, unavailable, browserBlocked, config,
    waiting, cancelWaiting, connectionNotice: session.notice,
    mode: session.mode, kickMessage, confirmKick, cancelKick, run, reset, acknowledge, reread};
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
      ? '使用浏览器已有会话。需要登录时，请在 i8 标签页完成。'
      : '使用工作台直连。遇到在线冲突时，需要另行确认是否让现有会话下线。'}</p>}
    {action.waiting ? <I8ConnectionWaitStatus /> : action.browserBlocked &&
      <p role="status">{action.connectionNotice || '确认抓取后将自动连接 i8。'}</p>}
    {action.busy && <p role="status">正在抓取，请稍候…</p>}
    {action.kickMessage && <p className="notice" role="status">{action.kickMessage}</p>}
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
  if (action.kickMessage) return <div className="dialog-actions">
    <Button htmlType="button" onClick={action.cancelKick}>取消</Button>
    <Button htmlType="button" type="primary" danger disabled={action.unavailable || !canRun}
      onClick={() => void action.confirmKick()}>让现有会话下线并继续</Button>
  </div>;
  if (action.waiting) return <div className="dialog-actions">
    <Button htmlType="button" onClick={action.cancelWaiting}>取消等待</Button>
  </div>;
  return <div className="dialog-actions">
    <Button htmlType="button" disabled={action.busy || action.refreshing} onClick={close}>{action.sent ? '关闭' : '取消'}</Button>
    {!action.sent && <Button htmlType="button" type="primary" disabled={action.unavailable || action.pending || !canRun} onClick={onRun}>{label}</Button>}
  </div>;
}
