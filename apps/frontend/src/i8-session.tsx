/** Browser relay belongs to the account workspace, independently of the visible business page. */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { ApiError } from './api';
import {
  SESSION_MODE_BROWSER, SESSION_MODE_HTTP, disconnectBrowser, readBrowserIdentity, readBrowserState,
  relayAvailable, relayConnectionWanted, relayMode, resetBrowserRelay, setRelayConnectionWanted,
  setRelayMode, unbindBrowserIdentity,
} from './i8-browser-relay';
import type { BrowserRelayState, SessionMode } from './i8-browser-relay';
import { maintainBrowserRelay } from './i8-relay-recovery';

export interface I8SessionValue {
  mode: SessionMode;
  state: BrowserRelayState | null;
  connected: boolean;
  maintaining: boolean;
  halted: boolean;
  busy: boolean;
  notice: string;
  extensionReady: boolean;
  selectMode: (mode: SessionMode) => void;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  refresh: () => Promise<void>;
  readIdentity: () => Promise<void>;
}

const EMPTY: I8SessionValue = {
  mode: SESSION_MODE_HTTP, state: null, connected: false, maintaining: false, halted: false, busy: false, notice: '', extensionReady: false,
  selectMode: () => {}, connect: async () => {}, disconnect: async () => {}, refresh: async () => {}, readIdentity: async () => {},
};
const I8SessionContext = createContext<I8SessionValue>(EMPTY);
export function useI8Session(): I8SessionValue {return useContext(I8SessionContext);}
function messageOf(failure: unknown, fallback: string): string {return failure instanceof ApiError ? failure.message : fallback;}

export function I8SessionProvider({blocked, owner, children}: {blocked: boolean; owner: string; children: ReactNode}) {
  const [mode, setMode] = useState<SessionMode>(() => relayMode(owner));
  const [wanted, setWanted] = useState(() => relayMode(owner) === SESSION_MODE_BROWSER && relayConnectionWanted(owner));
  const [state, setState] = useState<BrowserRelayState | null>(null);
  const [halted, setHalted] = useState(true), [busy, setBusy] = useState(false), [notice, setNotice] = useState('');
  const [attempt, setAttempt] = useState(0);
  const alive = useRef(true), wantedRef = useRef(wanted), controller = useRef<AbortController | null>(null);
  const operation = useRef(0);
  wantedRef.current = wanted;
  const remember = useCallback((next: boolean) => {
    wantedRef.current = next; setWanted(next); setRelayConnectionWanted(owner, next);
  }, [owner]);

  const refresh = useCallback(async () => {
    try {
      const next = await readBrowserState();
      // The active supervisor owns readiness; a stale GET cannot overwrite its result.
      if (alive.current && !wantedRef.current) setState(next);
    } catch (failure) {
      if (alive.current && !wantedRef.current) setNotice(messageOf(failure, '浏览器连接状态没读出来，请重试。'));
    }
  }, []);
  useEffect(() => {
    alive.current = true;
    if (!wantedRef.current) void refresh();
    return () => {alive.current = false; operation.current += 1; controller.current?.abort();};
  }, [refresh]);

  const selectMode = useCallback((next: SessionMode) => {
    setRelayMode(next, owner); setMode(next);
    if (next === SESSION_MODE_HTTP) {
      operation.current += 1; controller.current?.abort(); remember(false);
      setHalted(true); setBusy(false); setNotice('');
    }
  }, [owner, remember]);

  const connect = useCallback(async () => {
    operation.current += 1; controller.current?.abort();
    setRelayMode(SESSION_MODE_BROWSER, owner); setMode(SESSION_MODE_BROWSER);
    remember(true); setHalted(true); setNotice('正在连接浏览器会话…');
    setAttempt(value => value + 1);
  }, [owner, remember]);

  const disconnect = useCallback(async () => {
    const current = ++operation.current;
    controller.current?.abort(); remember(false); setHalted(true); setBusy(true);
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
  }, [remember]);

  const readIdentity = useCallback(async () => {
    try {await readBrowserIdentity();}
    catch (failure) {if (alive.current) setNotice(messageOf(failure, '没能读取 i8 标签，请点击扩展图标后再试。'));}
  }, []);

  useEffect(() => {
    if (!wanted || mode !== SESSION_MODE_BROWSER || blocked) {setHalted(true); return;}
    const local = new AbortController(); controller.current = local;
    void maintainBrowserRelay(local.signal, update => {
      if (local.signal.aborted || !alive.current) return;
      setNotice(update.message);
      setBusy(update.phase === 'connecting');
      setHalted(update.phase !== 'connected');
      if (update.phase === 'connected') setState(update.state);
      if (update.phase === 'stopped') remember(false);
    });
    return () => {local.abort(); if (controller.current === local) controller.current = null;};
  }, [wanted, mode, blocked, attempt, remember]);

  // Temporary account verification pauses work; the same account can resume afterward.
  const connected = wanted && mode === SESSION_MODE_BROWSER && !blocked && !halted && state?.connected === true;
  const value = useMemo<I8SessionValue>(() => ({
    mode, state, connected, maintaining: wanted && mode === SESSION_MODE_BROWSER, halted, busy, notice, extensionReady: relayAvailable(),
    selectMode, connect, disconnect, refresh, readIdentity,
  }), [mode, state, connected, wanted, halted, busy, notice, selectMode, connect, disconnect, refresh, readIdentity]);
  return <I8SessionContext.Provider value={value}>{children}</I8SessionContext.Provider>;
}

export {resetBrowserRelay};
