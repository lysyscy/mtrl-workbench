import { ApiError } from './api';
import { bindBrowserIdentity, connectBrowser, isTransientRelayError, readBrowserIdentity, readBrowserState, runBrowserRelay } from './i8-browser-relay';
import type { BrowserRelayState } from './i8-browser-relay';

export type RelayConnectionUpdate =
  | {phase: 'connecting' | 'retrying' | 'stopped'; message: string; code?: string; origin?: string}
  | {phase: 'connected'; state: BrowserRelayState; message: string};

const defaults = {state: readBrowserState, read: readBrowserIdentity, connect: connectBrowser, bind: bindBrowserIdentity, run: runBrowserRelay, wait: waitForRecovery};
type Dependencies = typeof defaults;
interface OpenIntent {
  requested: () => boolean;
  checked: () => void;
}

export function recoverable(error: unknown): boolean {
  return isTransientRelayError(error) || error instanceof ApiError && error.code !== 'invalid_response' && error.code !== 'malformed' && (
    error.code === 'identity_unverified'
    || error.status >= 500 || !error.code && error.status === 0);
}

/** Back off while unavailable; returning to the page or coming online wakes the attempt sooner. */
function waitForRecovery(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.resolve();
  return new Promise(resolve => {
    const finish = () => {
      clearTimeout(timer);
      signal.removeEventListener('abort', finish);
      window.removeEventListener('online', finish);
      window.removeEventListener('focus', finish);
      document.removeEventListener('visibilitychange', visible);
      resolve();
    };
    const visible = () => {if (document.visibilityState === 'visible') finish();};
    const timer = setTimeout(finish, ms);
    signal.addEventListener('abort', finish, {once: true});
    window.addEventListener('online', finish, {once: true});
    window.addEventListener('focus', finish, {once: true});
    document.addEventListener('visibilitychange', visible);
  });
}

/** Own a single connect → poll → recover lifecycle. This has no business-fetch retry path. */
export async function maintainBrowserRelay(signal: AbortSignal, update: (value: RelayConnectionUpdate) => void,
  open?: OpenIntent, deps: Dependencies = defaults): Promise<void> {
  let faults = 0;
  while (!signal.aborted) {
    if (!faults) update({phase: 'connecting', message: '正在连接 i8…'});
    let state: BrowserRelayState;
    let origin = '';
    try {
      origin = (await deps.state(signal)).origin;
      if (signal.aborted) return;
      if (!origin) throw new ApiError('请先在工作台设置 i8 服务器地址。', 0, 'i8-unconfigured');
      const shouldOpen = open?.requested() === true;
      const identity = await deps.read(origin, shouldOpen).then(result => {
        if (shouldOpen) open?.checked();
        return result;
      }, failure => {
        if (shouldOpen && failure instanceof ApiError && ['tab-opening', 'tab-paused', 'login-required'].includes(failure.code ?? '')) open?.checked();
        throw failure;
      });
      if (signal.aborted) return;
      state = await deps.connect(identity, signal);
      if (signal.aborted) return;
      if (state.origin !== identity.origin) throw new ApiError('i8 站点已变化，正在重新核对。', 0, 'site-changed');
      if (!state.connected) throw new ApiError('工作台未确认浏览器连接。', 0, 'invalid_response');
      await deps.bind(identity, state.generation);
      if (signal.aborted) return;
    } catch (failure) {
      if (signal.aborted) return;
      if (!recoverable(failure)) {
        update({phase: 'stopped', message: failure instanceof Error ? failure.message : '无法连接浏览器，请重新连接。'});
        return;
      }
      const code = failure instanceof ApiError ? failure.code : undefined;
      update({phase: 'retrying', origin, ...(code ? {code} : {}), message: failure instanceof ApiError && isTransientRelayError(failure)
        ? failure.message : '连接暂时中断，正在自动恢复；不会重新登录或重做抓取。'});
      const limit = isTransientRelayError(failure) ? 2000 : 30_000;
      await deps.wait(Math.min(limit, 1000 * 2 ** Math.min(faults++, 5)), signal);
      continue;
    }
    update({phase: 'connected', state, message: ''});
    const started = Date.now();
    let reason = 'idle';
    let failureMessage = '';
    try {
      await deps.run({signal, onStop: value => {reason = value;}});
    } catch (failure) {
      if (signal.aborted) return;
      reason = recoverable(failure) ? 'network' : 'failed';
      if (failure instanceof ApiError) failureMessage = failure.message;
    }
    if (signal.aborted) return;
    if (reason !== 'network' && reason !== 'reconnect') {
      update({phase: 'stopped', message: failureMessage || (reason === 'malformed'
        ? '浏览器取数协议不一致，请更新扩展后重新连接。'
        : '浏览器取数已停止，请检查 i8 标签或登录状态后重新连接；本次抓取不会自动重做。')});
      return;
    }
    if (Date.now() - started > 30_000) faults = 0;
    update({phase: 'retrying', message: failureMessage || '连接暂时中断，正在自动恢复；不会重新登录或重做抓取。'});
    await deps.wait(Math.min(30_000, 1000 * 2 ** Math.min(faults++, 5)), signal);
  }
}
