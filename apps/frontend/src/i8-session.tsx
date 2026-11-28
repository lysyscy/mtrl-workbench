/** Browser relay belongs to the account workspace, independently of the visible business page. */
import Button from 'antd/es/button';
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { ApiError } from './api';
import {
  SESSION_MODE_BROWSER, SESSION_MODE_HTTP, checkBrowserReadiness, deviceId, disconnectBrowser, readBrowserIdentity, readBrowserState,
  relayAvailable, relayConnectionWanted, relayMode, requestBrowserPermission, resetBrowserRelay, setRelayConnectionWanted,
  setRelayMode, unbindBrowserIdentity,
} from './i8-browser-relay';
import type { BrowserRelayState, SessionChoice, SessionMode } from './i8-browser-relay';
import { maintainBrowserRelay, recoverable } from './i8-relay-recovery';
import { createI8ActionGate } from './i8-action-gate';

interface BrowserWaiter {
  open: boolean;
  finish: (ready: boolean) => void;
}

export interface I8SessionValue {
  mode: SessionMode;
  state: BrowserRelayState | null;
  connected: boolean;
  maintaining: boolean;
  halted: boolean;
  busy: boolean;
  notice: string;
  connectionCode: string;
  actionKey: string;
  extensionReady: boolean;
  selectMode: (mode: SessionMode) => void;
  connect: (openIfMissing?: boolean) => Promise<void>;
  disconnect: () => Promise<void>;
  refresh: () => Promise<void>;
  readIdentity: () => Promise<void>;
  requestPermission: () => Promise<void>;
  waitForBrowser: (signal: AbortSignal) => Promise<boolean>;
}

const EMPTY: I8SessionValue = {
  mode: SESSION_MODE_BROWSER, state: null, connected: false, maintaining: false, halted: false, busy: false, notice: '', connectionCode: '', actionKey: '', extensionReady: false,
  selectMode: () => {}, connect: async () => {}, disconnect: async () => {}, refresh: async () => {}, readIdentity: async () => {},
  requestPermission: async () => {}, waitForBrowser: async () => false,
};
const I8SessionContext = createContext<I8SessionValue>(EMPTY);
export function useI8Session(): I8SessionValue {return useContext(I8SessionContext);}
function messageOf(failure: unknown, fallback: string): string {return failure instanceof ApiError ? failure.message : fallback;}

/** Call only from a confirmation. Change the scope key or cancel on close to discard the intent. */
export function useI8ActionWait(scopeKey: string) {
  const {mode, actionKey, waitForBrowser} = useI8Session();
  const [gate] = useState(createI8ActionGate);
  const [waiting, setWaiting] = useState(false);
  useLayoutEffect(() => {
    setWaiting(false);
    return gate.cancel;
  }, [gate, scopeKey, actionKey]);
  const cancelWaiting = () => {gate.cancel(); setWaiting(false);};
  function runWhenReady<T>(issue: (choice: SessionChoice) => T) {
    return mode === SESSION_MODE_BROWSER
      ? gate.run(waitForBrowser, () => issue({mode, connected: true}), setWaiting)
      : Promise.resolve(issue({mode, connected: false}));
  }
  return {waiting, cancelWaiting, runWhenReady};
}

export function I8ConnectionWaitStatus() {
  const {notice, connectionCode, requestPermission} = useI8Session();
  return <div className="notice">
    <p role="status">{notice || '正在连接 i8…'}</p>
    {connectionCode === 'permission-required' &&
      <Button htmlType="button" onClick={() => void requestPermission()}>授权 i8 站点</Button>}
  </div>;
}

export function I8SessionProvider({blocked, owner, children}: {blocked: boolean; owner: string; children: ReactNode}) {
  const [mode, setMode] = useState<SessionMode>(() => relayMode(owner));
  const [wanted, setWanted] = useState(() => relayMode(owner) === SESSION_MODE_BROWSER && relayConnectionWanted(owner));
  const [state, setState] = useState<BrowserRelayState | null>(null);
  const [halted, setHalted] = useState(true), [busy, setBusy] = useState(false), [notice, setNotice] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [connectionCode, setConnectionCode] = useState('');
  const alive = useRef(true), wantedRef = useRef(wanted), controller = useRef<AbortController | null>(null);
  const operation = useRef(0);
  const modeRef = useRef(mode);
  const ready = useRef<BrowserRelayState | null>(null);
  const permissionOrigin = useRef('');
  const manualOpen = useRef(false);
  const waiters = useRef(new Set<BrowserWaiter>());
  const finishWaiters = useCallback((connected: boolean) => {
    for (const waiter of waiters.current) waiter.finish(connected);
  }, []);
  wantedRef.current = wanted;
  const remember = useCallback((next: boolean) => {
    wantedRef.current = next; setWanted(next); setRelayConnectionWanted(owner, next);
  }, [owner]);

  const refresh = useCallback(async () => {
    try {
      const next = await readBrowserState();
      if (alive.current && !wantedRef.current) setState(next);
    } catch (failure) {
      if (alive.current && !wantedRef.current) setNotice(messageOf(failure, '浏览器连接状态没读出来，请重试。'));
    }
  }, []);
  useEffect(() => {
    alive.current = true;
    if (!wantedRef.current) void refresh();
    return () => {alive.current = false; operation.current += 1; controller.current?.abort(); finishWaiters(false);};
  }, [refresh, finishWaiters]);

  const selectMode = useCallback((next: SessionMode) => {
    modeRef.current = next; setRelayMode(next, owner); setMode(next);
    if (next === SESSION_MODE_HTTP) {
      operation.current += 1; controller.current?.abort(); remember(false);
      ready.current = null; manualOpen.current = false;
      finishWaiters(false); setHalted(true); setBusy(false); setNotice(''); setConnectionCode('');
    }
  }, [owner, remember, finishWaiters]);

  const connect = useCallback(async (openIfMissing = true) => {
    operation.current += 1; controller.current?.abort();
    ready.current = null; manualOpen.current = openIfMissing;
    modeRef.current = SESSION_MODE_BROWSER; setRelayMode(SESSION_MODE_BROWSER, owner); setMode(SESSION_MODE_BROWSER);
    remember(true); setHalted(true); setNotice('正在连接 i8…'); setConnectionCode('');
    setAttempt(value => value + 1);
  }, [owner, remember]);

  const disconnect = useCallback(async () => {
    const current = ++operation.current;
    controller.current?.abort(); remember(false); setHalted(true); setBusy(true);
    ready.current = null; manualOpen.current = false; finishWaiters(false); setConnectionCode('');
    setNotice('已停止自动连接。');
    try {
      const next = await disconnectBrowser();
      if (current !== operation.current || !alive.current) return;
      await unbindBrowserIdentity();
      if (current !== operation.current || !alive.current) return;
      setState(next); setNotice('已断开浏览器连接，刷新页面也不会自动重连。取数方式仍是「浏览器已有会话」。');
    } catch (failure) {
      if (current === operation.current && alive.current) setNotice(messageOf(failure, '自动连接已停止，服务端断开未确认，请稍后重试。'));
    } finally {if (current === operation.current && alive.current) setBusy(false);}
  }, [remember, finishWaiters]);

  const readIdentity = useCallback(async () => {
    try {await readBrowserIdentity((await readBrowserState()).origin);}
    catch (failure) {if (alive.current) setNotice(messageOf(failure, '没能读取 i8 标签，请点击扩展图标后再试。'));}
  }, []);

  const requestPermission = useCallback(async () => {
    const origin = permissionOrigin.current;
    if (!origin || modeRef.current !== SESSION_MODE_BROWSER) return;
    try {
      const current = await readBrowserState();
      if (origin === permissionOrigin.current && current.origin === origin && alive.current
          && modeRef.current === SESSION_MODE_BROWSER) await requestBrowserPermission(origin);
    } catch (failure) {
      if (alive.current) setNotice(messageOf(failure, '请在 i8 标签页点一下扩展图标。'));
    }
  }, []);

  /** A caller owns cancellation. Only a current, usable browser generation can resolve true. */
  const waitForBrowser = useCallback(async (signal: AbortSignal) => {
    const device = deviceId();
    const previous = operation.current;
    const valid = () => !signal.aborted && alive.current && deviceId() === device
      && operation.current === previous && modeRef.current === SESSION_MODE_BROWSER;
    if (!valid() || blocked) return false;
    const bound = ready.current;
    if (bound) {
      try {
        await checkBrowserReadiness(bound, signal);
        if (valid() && bound === ready.current) return true;
      } catch (failure) {
        if (!valid()) return false;
        if (!recoverable(failure)) {
          setNotice(messageOf(failure, '无法核对浏览器连接。'));
          return false;
        }
        if (bound === ready.current) {
          ready.current = null; controller.current?.abort();
          setHalted(true); setNotice(messageOf(failure, '正在恢复 i8 连接…'));
          setAttempt(value => value + 1);
        }
      }
    }
    if (!valid()) return false;
    if (ready.current && bound !== ready.current) return true;
    return new Promise<boolean>(resolve => {
      const cancel = () => waiter.finish(false);
      const waiter: BrowserWaiter = {open: true, finish: connected => {
        signal.removeEventListener('abort', cancel);
        waiters.current.delete(waiter);
        resolve(connected && valid());
      }};
      waiters.current.add(waiter);
      signal.addEventListener('abort', cancel, {once: true});
      if (!wantedRef.current) {
        setNotice('正在连接 i8…'); setConnectionCode('');
        remember(true);
      }
    });
  }, [blocked, remember]);

  useEffect(() => {
    if (!wanted || mode !== SESSION_MODE_BROWSER || blocked) {setHalted(true); return;}
    const local = new AbortController(); controller.current = local;
    let openedFor: BrowserWaiter[] = [];
    void maintainBrowserRelay(local.signal, update => {
      if (local.signal.aborted || !alive.current) return;
      ready.current = update.phase === 'connected' ? update.state : null;
      setNotice(update.message);
      const code = update.phase === 'connected' ? '' : update.code || '';
      permissionOrigin.current = update.phase === 'retrying' && code === 'permission-required' ? update.origin || '' : '';
      setConnectionCode(code);
      setHalted(update.phase !== 'connected');
      if (update.phase === 'connected') {
        setState(update.state);
        finishWaiters(true);
      }
      if (update.phase === 'stopped') {
        manualOpen.current = false; finishWaiters(false); remember(false);
      }
    }, {
      requested: () => {
        openedFor = [...waiters.current].filter(waiter => waiter.open);
        return manualOpen.current || openedFor.length > 0;
      },
      checked: () => {
        if (local.signal.aborted) return;
        manualOpen.current = false;
        for (const waiter of openedFor) waiter.open = false;
      },
    });
    return () => {
      local.abort();
      if (controller.current === local) {controller.current = null; ready.current = null;}
    };
  }, [wanted, mode, blocked, attempt, remember, finishWaiters]);

  const connected = wanted && mode === SESSION_MODE_BROWSER && !blocked && !halted && state?.connected === true;
  const value = useMemo<I8SessionValue>(() => ({
    mode, state, connected, maintaining: wanted && mode === SESSION_MODE_BROWSER, halted, busy, notice, connectionCode,
    actionKey: JSON.stringify([owner, mode, blocked]), extensionReady: relayAvailable(),
    selectMode, connect, disconnect, refresh, readIdentity, requestPermission, waitForBrowser,
  }), [mode, state, connected, wanted, halted, busy, notice, connectionCode, owner, blocked, selectMode, connect, disconnect, refresh, readIdentity,
    requestPermission, waitForBrowser]);
  return <I8SessionContext.Provider value={value}>{children}</I8SessionContext.Provider>;
}

export {resetBrowserRelay};
