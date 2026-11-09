import { ApiError } from './api';
import { bindBrowserIdentity, connectBrowser, isTransientRelayError, readBrowserIdentity, runBrowserRelay } from './i8-browser-relay';
import type { BrowserRelayState } from './i8-browser-relay';

export type RelayConnectionUpdate =
  | {phase: 'connecting' | 'retrying' | 'stopped'; message: string}
  | {phase: 'connected'; state: BrowserRelayState; message: string};

const defaults = {read: readBrowserIdentity, connect: connectBrowser, bind: bindBrowserIdentity, run: runBrowserRelay, wait: waitForRecovery};
type Dependencies = typeof defaults;

/** Network recovery only: actual site, authentication and protocol errors remain visible stops. */
function recoverable(error: unknown): boolean {
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
export async function maintainBrowserRelay(signal: AbortSignal, update: (value: RelayConnectionUpdate) => void, deps: Dependencies = defaults): Promise<void> {
  let faults = 0;
  while (!signal.aborted) {
    update({phase: 'connecting', message: faults ? '正在恢复浏览器连接…' : '正在连接浏览器会话…'});
    let state: BrowserRelayState;
    try {
      const identity = await deps.read();
      if (signal.aborted) return;
      state = await deps.connect(identity, signal);
      if (signal.aborted) return;
      await deps.bind(identity, state.generation);
      if (signal.aborted) return;
    } catch (failure) {
      if (signal.aborted) return;
      if (!recoverable(failure)) {
        update({phase: 'stopped', message: failure instanceof Error ? failure.message : '无法连接浏览器，请重新选择 i8 标签后连接。'});
        return;
      }
      update({phase: 'retrying', message: failure instanceof ApiError && isTransientRelayError(failure)
        ? failure.message : '连接暂时中断，正在自动恢复；不会重新登录或重做抓取。'});
      await deps.wait(Math.min(30_000, 1000 * 2 ** Math.min(faults++, 5)), signal);
      continue;
    }
    update({phase: 'connected', state, message: ''});
    const started = Date.now();
    let reason = 'idle';
    let failureMessage = '';
    try {
      await deps.run({
        signal,
        onStop: value => {reason = value;},
        checkTab: async () => {
          const identity = await deps.read(undefined, state.generation);
          if (identity.origin !== state.origin) throw new ApiError('i8 标签站点已变化，请核对后重新连接。', 0, 'site-changed');
        },
      });
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
