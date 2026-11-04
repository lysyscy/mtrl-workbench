/**
 * 浏览器会话通道的**账号工作区级**状态（`TAIL-476`）。
 *
 * 为什么放在 `AccountWorkspace` 里而不是某个页面里：
 * - 连接属于**当前登录账号 + 当前这个浏览器页面**，不属于某个业务页；
 * - 页面切来切去不该把连接弄断（否则抓取中途点开别的页就全废了）；
 * - 但**账号暂停/身份待核/退出登录**必须立刻停 —— 那是两回事，这里分开处理。
 *
 * ⛔ 这里不放任何会话材料：只有站点原点、可见账号、组织名称/短码、连接代号。
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { ApiError } from './api';
import {
  SESSION_MODE_HTTP,
  bindBrowserIdentity,
  connectBrowser,
  disconnectBrowser,
  readBrowserIdentity,
  readBrowserState,
  relayAvailable,
  relayMode,
  resetBrowserRelay,
  runBrowserRelay,
  setRelayMode,
  unbindBrowserIdentity,
} from './i8-browser-relay';
import type { BrowserRelayState, SessionMode } from './i8-browser-relay';

/** 通道为什么停了 —— 只用于给用户看一句话，不含技术细节。 */
type StopReason = '' | 'idle' | 'failed' | 'network' | 'malformed';

const STOP_TEXT: Record<Exclude<StopReason, ''>, string> = {
  idle: '浏览器连接已停止：本次没有继续等待取数请求。要接着用，请重新连接。',
  failed: '浏览器连接已停止：取数过程中出错（不会自动改用登录方式）。请检查 i8 标签是否还开着，再重新连接。',
  network: '浏览器连接已停止：和工作台的连接断了。请检查网络后重新连接。',
  malformed: '浏览器连接已停止：和工作台的取数协议对不上（可能是扩展或工作台版本不一致）。请更新后重新连接；不会自动改用登录方式。',
};

export interface I8SessionValue {
  /** 当前账号/本页显式选择的取数方式；没选过就是 `http`（＝产品原行为）。 */
  mode: SessionMode;
  /** 连上后才有的状态（站点/账号/组织/代号）。 */
  state: BrowserRelayState | null;
  connected: boolean;
  /**
   * 通道**在本页已经停了**（出错/断开/协议不符/后台已停）。
   *
   * ⚠️ 这一位必须盖过服务端的 `connected`：服务端那条连接可能还在（还没到空闲超时），
   *    但本页已经没人接活了 —— 这时再显示"已连接"，下一次抓取就会挂在那儿等到超时。
   *    恢复只有一条路：用户自己点「连接」。
   */
  halted: boolean;
  busy: boolean;
  /** 给用户看的一句话（错误或停止原因）；空串表示没有要说的事。 */
  notice: string;
  /** 扩展是否可用（装没装 + ID 填没填）。 */
  extensionReady: boolean;
  selectMode: (mode: SessionMode) => void;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  refresh: () => Promise<void>;
  /** 读一次 i8 页面可见身份（用于「连接」按钮前的预检与提示）。 */
  readIdentity: () => Promise<void>;
}

const EMPTY: I8SessionValue = {
  mode: SESSION_MODE_HTTP,
  state: null,
  connected: false,
  halted: false,
  busy: false,
  notice: '',
  extensionReady: false,
  selectMode: () => {},
  connect: async () => {},
  disconnect: async () => {},
  refresh: async () => {},
  readIdentity: async () => {},
};

const I8SessionContext = createContext<I8SessionValue>(EMPTY);

export function useI8Session(): I8SessionValue {
  return useContext(I8SessionContext);
}

function messageOf(failure: unknown, fallback: string): string {
  if (failure instanceof ApiError) return failure.message;
  return fallback;
}

/**
 * 提供者必须挂在 `AccountWorkspace` 内（`key` 已含账号 ⇒ 换号天然重建）。
 *
 * @param blocked 账号暂停/身份待核（含"正在重新核身份"）。为真时**不跑通道**、且立刻中止在途轮询。
 * @param owner 当前登录身份（`id:account`）。只用于把「取数方式」按账号分开存：
 *              同一账号重新登录后仍停在用户显式选过的浏览器方式，换号则各用各的。
 */
export function I8SessionProvider({ blocked, owner, children }: { blocked: boolean; owner: string; children: ReactNode }) {
  const [mode, setMode] = useState<SessionMode>(() => relayMode(owner));
  const [state, setState] = useState<BrowserRelayState | null>(null);
  const [halted, setHalted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const blockedRef = useRef(blocked);
  blockedRef.current = blocked;
  /** 已停：通道不在跑，`connected` 必须为假；恢复只能由用户重新连接。 */
  const haltedRef = useRef(false);
  const alive = useRef(true);
  const controller = useRef<AbortController | null>(null);

  const markHalted = useCallback((next: boolean) => {
    haltedRef.current = next;
    setHalted(next);
  }, []);

  const applyMode = useCallback((next: SessionMode) => {
    setRelayMode(next, owner);
    setMode(next);
  }, [owner]);

  const refresh = useCallback(async () => {
    if (!alive.current) return;
    try {
      const next = await readBrowserState();
      if (!alive.current) return;
      // 状态照实记下；**是否显示成"已连接"由 `halted` 决定**（见 connected 那一行）。
      setState(next);
      // ⛔ 服务端说"没连了"不代表用户改主意：**模式只有用户能改**。
      //   悄悄改回直连会让下一次抓取直接走登录（可能顶号），正是本票禁止的"默默回退"。
    } catch (failure) {
      if (!alive.current) return;
      setNotice(messageOf(failure, '浏览器连接状态没读出来，请重试。'));
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    void refresh();
    return () => {
      alive.current = false;
      controller.current?.abort();
    };
  }, [refresh]);

  const readIdentity = useCallback(async () => {
    setBusy(true);
    setNotice('');
    try {
      await readBrowserIdentity();
    } catch (failure) {
      if (alive.current) setNotice(messageOf(failure, '没能从浏览器读到 i8 身份，请展开账号面板后再试。'));
    } finally {
      if (alive.current) setBusy(false);
    }
  }, []);

  const connect = useCallback(async () => {
    setBusy(true);
    setNotice('');
    // 用户显式重连：清掉本地停止态，让新一轮通道跑起来（这是**唯一**的恢复入口）。
    markHalted(false);
    try {
      const identity = await readBrowserIdentity();
      const next = await connectBrowser(identity);
      // 扩展把"刚才读到的那一份"记为基准；`generation` 是服务端这次连接给的代号。
      // ⛔ 页面不自己猜账号/组织，也不复用上一次的代号。
      await bindBrowserIdentity(identity, next.generation);
      if (!alive.current) return;
      setState(next);
      applyMode(next.mode);
    } catch (failure) {
      if (!alive.current) return;
      // 连不上就不要再显示"已连接"：留下的半截状态会让抓取空等。
      markHalted(true);
      setNotice(messageOf(failure, '没能连上浏览器会话，请重试。'));
      // 模式不变：用户在「取数方式」里选的是浏览器，就得由用户自己改回去。
    } finally {
      if (alive.current) setBusy(false);
    }
  }, [applyMode, markHalted]);

  const disconnect = useCallback(async () => {
    setBusy(true);
    setNotice('');
    try {
      const next = await disconnectBrowser();
      await unbindBrowserIdentity();
      if (!alive.current) return;
      setState(next);
      markHalted(false);
      // 断开也不改模式：已选的浏览器方式要显式改回直连，⛔ 不许默默换成登录。
      setNotice('已断开浏览器连接。取数方式仍是「浏览器已有会话」，要改回直连请在上面切换。');
    } catch (failure) {
      if (alive.current) setNotice(messageOf(failure, '断开时出错，请刷新页面后重试。'));
    } finally {
      if (alive.current) setBusy(false);
    }
  }, [markHalted]);

  /**
   * 对外一律以**本页实况**为准：
   * 服务端连接还在（`state.connected`）但本页通道已停（`halted`）时，必须显示未连接。
   * 否则抓取控件会判定"可以走浏览器"，然后一等等到后端超时。
   */
  const connected = state?.connected === true && !halted;

  // 通道随「已连接 + 账号未被暂停」起停；路由切换**不影响**它。
  useEffect(() => {
    if (!connected || blocked) return undefined;
    const local = new AbortController();
    controller.current = local;
    const stop = (text: string) => {
      if (!alive.current || blockedRef.current) return;
      // 通道自己停了 ⇒ 立刻落到本地停止态（⛔ 不许继续显示"已连接"）。
      // 只读一次服务端状态用于展示，**不再用它把 connected 顶回来**。
      markHalted(true);
      setNotice(text);
      void refresh();
    };
    void runBrowserRelay({
      keep: () => alive.current && !blockedRef.current && !local.signal.aborted,
      signal: local.signal,
      onStop: reason => {
        const key = (reason as Exclude<StopReason, ''>);
        stop(key in STOP_TEXT ? STOP_TEXT[key] : STOP_TEXT.failed);
      },
    }).catch(() => {
      stop(STOP_TEXT.failed);
    });
    return () => {
      local.abort();
      if (controller.current === local) controller.current = null;
    };
  }, [connected, blocked, refresh, markHalted]);

  // 账号暂停/身份待核 ⇒ 立刻中止在途轮询（并且不再执行已取回的请求）。
  useEffect(() => {
    if (!blocked) return;
    controller.current?.abort();
  }, [blocked]);

  // 账号恢复（blocked 解除）时重新读一次状态。⚠️ 这里**不清停止态**：
  // 通道是本页停的，得用户重新连接；只有用户点「连接」才算恢复。
  useEffect(() => {
    if (blocked) return;
    void refresh();
  }, [blocked, refresh]);

  const value = useMemo<I8SessionValue>(() => ({
    mode,
    state,
    connected,
    halted,
    busy,
    notice,
    extensionReady: relayAvailable(),
    selectMode: applyMode,
    connect,
    disconnect,
    refresh,
    readIdentity,
  }), [mode, state, connected, halted, busy, notice, applyMode, connect, disconnect, refresh, readIdentity]);

  return <I8SessionContext.Provider value={value}>{children}</I8SessionContext.Provider>;
}

/** 账号事件（退出登录/身份失效）时换掉本页的连接标识；⛔ 不动用户选过的模式。 */
export { resetBrowserRelay };
