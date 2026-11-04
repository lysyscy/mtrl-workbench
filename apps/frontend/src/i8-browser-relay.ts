/**
 * 「用浏览器已有会话」这条通道的**页面侧**（`TAIL-476`）。
 *
 * 页面只做三件事：①把后端排队的**那一条**请求转交给扩展；②把扩展带回来的响应原样回帖；
 * ③如实显示状态。⛔ 页面不构造 i8 请求、不碰 Cookie、不自己做 fetch。
 *
 * 身份门：所有请求都走 `requestJson()`（与其它页面同一条路）——
 * `401` 仍按既有语义派发 `session-lost` 并抛错；本地身份未核时照旧等待。
 * ⛔ 这里**不**绕过 `api.ts` 的身份门，也**不**自己吞 401。
 *
 * ⚠️ 本文件里**没有任何会话材料**：只有一次性票、请求/响应正文、站点原点与代号。
 */

import { ApiError, record, requestJson } from './api';

/** 服务端长轮询上限（`browser_broker.PENDING_WAIT_SECONDS`）；页面只能要更短的。 */
export const RELAY_POLL_SECONDS = 10;

/**
 * 服务端"这一轮没活"提前返回时的让出间隔。
 *
 * ⚠️ 不设这个间隔会变成**忙等**：每轮只 await 已 resolve 的 promise，宏任务轮不到，
 *    页面定时器（包括停止开关）永远不触发 —— 这条被页面侧单测当场抓到。
 */
const EMPTY_ROUND_MS = 250;

/**
 * 扩展 ID。
 *
 * 扩展的 `manifest.json` 带了固定公钥（`"key"`）⇒ 打包 ID 是**确定的**，装一次就一直是它，
 * 用户不需要每次重填。下面的常量是那个确定值；`sessionStorage` 里存的是**覆盖值**
 * （只有换了构建/换了打包方式才需要），构建期也可注入 `VITE_I8_RELAY_EXTENSION_ID`。
 */
const DEFAULT_EXTENSION_ID = 'jfkgliolimmpceandogfimjkadplidem';
const EXTENSION_ID_KEY = 'mtrl.i8.relay.extension';
/**
 * 「取数方式」的存储键前缀。实际键是 `前缀` 或 `前缀.<登录账号>`：
 * 同一账号重新登录后仍停在用户显式选过的浏览器方式，换了账号则各用各的、互不串。
 */
const MODE_KEY = 'mtrl.i8.relay.mode';

export const SESSION_MODE_HTTP = 'http';
export const SESSION_MODE_BROWSER = 'browser';
export type SessionMode = typeof SESSION_MODE_HTTP | typeof SESSION_MODE_BROWSER;

/** 各取数入口共用的最小会话选择（`I8SessionValue` 结构上就满足它）。 */
export interface SessionChoice {
  mode: SessionMode;
  connected: boolean;
}

export interface BrowserRelayState {
  connected: boolean;
  mode: SessionMode;
  origin: string;
  i8_user: string;
  expected_org: string;
  expected_org_code: string;
  expected_org_name: string;
  /** 本次连接的代号：每次连上都会变；回帖必须带同一个。 */
  generation: number;
  message: string;
}

export interface RelayRequest {
  ticket: string;
  generation: number;
  method: string;
  url: string;
  headers: Record<string, string>;
  body_b64: string;
  /**
   * 后端这条请求**原本的 HTTP 读取预算**（毫秒，正整数）。
   * 扩展必须按它设超时：合同列表 200s、明细 60s 这类预算不能压成统一的短超时。
   */
  timeout_ms: number;
}

export interface RelayReply {
  status: number;
  headers: Record<string, string>;
  body_b64: string;
  /** 扩展自己数出来的字节数；后端会拿它和实际解码长度核对（截断即停）。 */
  declared_length: number;
}

/** 从 i8 页面读到的**可见身份**（不是凭据；账号/组织名/短码都不是令牌）。 */
export interface VisibleIdentity {
  origin: string;
  account: string;
  orgCode: string;
  orgName: string;
}

/** 扩展侧最小 API 面（只用 `runtime.sendMessage`；⛔ 不需要 cookies/tabs/debugger）。 */
interface RuntimeMessenger {
  sendMessage(extensionId: string, message: unknown, callback: (response: unknown) => void): void;
  lastError?: { message?: string } | undefined;
}
interface RuntimeApi { runtime?: RuntimeMessenger | undefined }

/** 扩展注入的全局只在装了扩展的浏览器里存在；不装也必须能正常打开页面。 */
function extensionRuntime(): RuntimeMessenger | null {
  return (globalThis as unknown as { chrome?: RuntimeApi }).chrome?.runtime ?? null;
}

/**
 * 本页面的连接标识：**每个文档一份、只放内存**。
 *
 * ⚠️ 以前的实现写在 `sessionStorage` 里。复制标签页会把存储一起复制，
 *    于是两个页面共用同一个设备标识、抢同一条服务端连接队列（一个断开另一个也废）。
 *    放进模块级变量后，复制出来的文档必然是**新**标识；它也不是凭据、不落盘。
 */
let documentDeviceId = '';

export function deviceId(): string {
  if (!documentDeviceId) documentDeviceId = `dev-${crypto.randomUUID()}`;
  return documentDeviceId;
}

export function relayExtensionId(): string {
  const injected = (import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_I8_RELAY_EXTENSION_ID;
  const stored = sessionStorage.getItem(EXTENSION_ID_KEY) || '';
  return (stored || injected || DEFAULT_EXTENSION_ID).trim();
}

export function setRelayExtensionId(value: string): void {
  const trimmed = value.trim();
  if (trimmed) sessionStorage.setItem(EXTENSION_ID_KEY, trimmed);
  else sessionStorage.removeItem(EXTENSION_ID_KEY);
}

function modeStorageKey(owner: string | null | undefined): string {
  return owner ? `${MODE_KEY}.${owner}` : MODE_KEY;
}

/**
 * 本账号选择的取数方式。**只有用户显式选过「浏览器」才返回 browser**；
 * 没选过（老页面/老请求）一律 `http` ＝ 与改动前逐字节一致的产品直连行为。
 *
 * @param owner 登录账号（`id:account`）；不给就退回到不带账号的旧键。
 */
export function relayMode(owner?: string | null): SessionMode {
  return sessionStorage.getItem(modeStorageKey(owner)) === SESSION_MODE_BROWSER ? SESSION_MODE_BROWSER : SESSION_MODE_HTTP;
}

/** 记录本账号的选择。选了浏览器就**一直停在浏览器**，⛔ 不会因为失败悄悄改回直连。 */
export function setRelayMode(mode: SessionMode, owner?: string | null): void {
  const key = modeStorageKey(owner);
  if (mode === SESSION_MODE_BROWSER) sessionStorage.setItem(key, SESSION_MODE_BROWSER);
  else sessionStorage.removeItem(key);
}

/**
 * 身份事件（登录失效/退出登录/换号/卸载）时换掉**本页的连接标识**。
 *
 * ⛔ 不动「取数方式」：同一账号重新登录后仍应停在用户显式选过的浏览器方式，
 *    否则下一次抓取会悄悄走登录（可能顶号）—— 正是本票禁止的"默默回退"。
 *    不同账号用不同存储键，换号自然各用各的，不会串。
 *
 * 只动内存与 `sessionStorage`：⛔ 不在这里发请求（此刻 `401` 会再次派发 `session-lost`，会自激）；
 * 服务端那条旧连接另有归属键 `(认证身份, 设备)`、代号与空闲超时，换标识后不会被别人用到。
 */
export function resetBrowserRelay(): void {
  documentDeviceId = '';
}

/** 扩展是否可达（只是**本机装没装、填没填 ID**的判断，⛔ 不代表已登录、更不代表验收通过）。 */
export function relayAvailable(): boolean {
  return extensionRuntime() !== null && relayExtensionId() !== '';
}

function readString(source: Record<string, unknown>, key: string): string {
  const value = source[key];
  return typeof value === 'string' ? value : '';
}

function flatHeaders(value: unknown): Record<string, string> {
  if (!record(value)) return {};
  const flat: Record<string, string> = {};
  for (const [key, header] of Object.entries(value)) {
    if (typeof header === 'string') flat[key] = header;
  }
  return flat;
}

export function readBrowserRelayState(value: unknown): BrowserRelayState {
  if (!record(value) || typeof value.connected !== 'boolean' || typeof value.mode !== 'string'
    || typeof value.origin !== 'string' || typeof value.i8_user !== 'string'
    || typeof value.expected_org !== 'string' || typeof value.message !== 'string'
    || typeof value.expected_org_code !== 'string' || typeof value.expected_org_name !== 'string'
    || typeof value.generation !== 'number' || !Number.isInteger(value.generation)) {
    throw new ApiError('浏览器连接状态读取不完整，请重试；仍失败请联系维护人员。');
  }
  if (value.mode !== SESSION_MODE_HTTP && value.mode !== SESSION_MODE_BROWSER) {
    throw new ApiError('浏览器连接状态读取不完整，请重试；仍失败请联系维护人员。');
  }
  return {
    connected: value.connected,
    mode: value.mode,
    origin: value.origin,
    i8_user: value.i8_user,
    expected_org: value.expected_org,
    expected_org_code: value.expected_org_code,
    expected_org_name: value.expected_org_name,
    generation: value.generation,
    message: value.message,
  };
}

export async function readBrowserState(signal?: AbortSignal): Promise<BrowserRelayState> {
  const path = `/api/m02/browser/state?device_id=${encodeURIComponent(deviceId())}`;
  return readBrowserRelayState(await requestJson(path, signal ? { signal } : {}));
}

/** 连上浏览器：`identity` 里的账号/组织是**扩展从 i8 页面读到的可见值**，不是用户手填。 */
export async function connectBrowser(identity: VisibleIdentity, signal?: AbortSignal): Promise<BrowserRelayState> {
  const body = {
    device_id: deviceId(),
    i8_origin: identity.origin,
    i8_account: identity.account,
    i8_org_code: identity.orgCode,
    i8_org_name: identity.orgName,
  };
  const init: RequestInit = { method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } };
  return readBrowserRelayState(await requestJson('/api/m02/browser/connect', signal ? { ...init, signal } : init));
}

export async function disconnectBrowser(signal?: AbortSignal): Promise<BrowserRelayState> {
  const path = `/api/m02/browser/disconnect?device_id=${encodeURIComponent(deviceId())}`;
  const init: RequestInit = { method: 'POST' };
  return readBrowserRelayState(await requestJson(path, signal ? { ...init, signal } : init));
}

/**
 * 解析后端排队的请求。
 *
 * 形状不对就返回 `null`（调用方据此**停止**），⛔ 不能当成"这一轮没活"继续轮询：
 * 那样协议对不上时会永远安静地空转，看起来像"已连接、只是没任务"。
 */
export function readRelayRequest(value: unknown): RelayRequest | null {
  if (!record(value) || typeof value.ticket !== 'string' || !value.ticket) return null;
  if (typeof value.method !== 'string' || typeof value.url !== 'string') return null;
  if (typeof value.generation !== 'number' || !Number.isInteger(value.generation)) return null;
  if (typeof value.timeout_ms !== 'number' || !Number.isInteger(value.timeout_ms) || value.timeout_ms <= 0) return null;
  return {
    ticket: value.ticket,
    generation: value.generation,
    method: value.method.toUpperCase(),
    url: value.url,
    headers: flatHeaders(value.headers),
    body_b64: readString(value, 'body_b64'),
    timeout_ms: value.timeout_ms,
  };
}

export function readRelayReply(value: unknown): RelayReply {
  if (!record(value) || typeof value.status !== 'number' || !Number.isInteger(value.status)
    || typeof value.body_b64 !== 'string' || typeof value.declared_length !== 'number'
    || !Number.isInteger(value.declared_length) || value.declared_length < 0) {
    throw new ApiError('浏览器回帖不完整，本次已停止，请重试。');
  }
  return {
    status: value.status,
    headers: flatHeaders(value.headers),
    body_b64: value.body_b64,
    declared_length: value.declared_length,
  };
}

const BROWSER_MISSING = '当前选的是「浏览器已有会话」，但浏览器连接不在：本次没有发出任何请求，也不会改用登录方式。请先到「i8 接入」页重新连接。';

/**
 * 七个取数入口共用的**窄助手**：只决定「会话来源」那几个字段，业务字段仍由调用方给。
 *
 * - `browser`：**连接不在就当场失败**（⛔ 不退回登录、也绝不带强踢授权）；
 * - `http`：原样保留调用方给的那几个授权字段（例如 `allow_kick`）。
 */
export function sessionPayload(choice: SessionChoice, http: Record<string, unknown> = {}, base: Record<string, unknown> = {}): Record<string, unknown> {
  if (choice.mode === SESSION_MODE_BROWSER) {
    if (!choice.connected) throw new ApiError(BROWSER_MISSING);
    return { ...base, session_mode: SESSION_MODE_BROWSER, device_id: deviceId() };
  }
  return { ...base, ...http, session_mode: SESSION_MODE_HTTP };
}

/** 同上，给「用查询串说明会话来源」的入口（例如项目同步）用。 */
export function sessionParams(choice: SessionChoice, http: Record<string, unknown> = {}, base: Record<string, unknown> = {}): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(sessionPayload(choice, http, base))) {
    if (value !== undefined && value !== null) params.set(key, String(value));
  }
  return params;
}

type Send = (message: unknown) => Promise<unknown>;

function sendToExtension(message: unknown): Promise<unknown> {
  const runtime = extensionRuntime();
  const extensionId = relayExtensionId();
  return new Promise((resolve, reject) => {
    if (!runtime || !extensionId) {
      reject(new ApiError('没有检测到浏览器扩展，请按说明安装后再连接；本次未发出任何 i8 请求。'));
      return;
    }
    runtime.sendMessage(extensionId, message, (response: unknown) => {
      if (runtime.lastError) {
        reject(new ApiError('浏览器扩展没有应答（可能已停用或未授权）。本次未发出任何 i8 请求。'));
        return;
      }
      resolve(response);
    });
  });
}

const IDENTITY_HINT = '没能从浏览器读取 i8 的登录身份：请先在 i8 页面展开右上角的账号面板（显示账号与组织），再回来点连接。';

/**
 * 让扩展报告「用户选中的那个 i8 标签」的站点与账号/组织（可见身份，不是凭据）。
 *
 * 带 `device_id`：扩展按连接缓存这份待核身份，另一个工作台页面的预检不会把它换掉。
 */
export async function readBrowserIdentity(send: Send = sendToExtension): Promise<VisibleIdentity> {
  const value = await send({ type: 'i8-relay:identity', device_id: deviceId() });
  if (!record(value) || value.ok !== true) {
    const message = record(value) ? readString(value, 'message') : '';
    throw new ApiError(message || IDENTITY_HINT);
  }
  const origin = readString(value, 'origin');
  const account = readString(value, 'account');
  const orgCode = readString(value, 'orgCode');
  const orgName = readString(value, 'orgName');
  if (!origin || !account || !orgCode || !orgName) throw new ApiError(IDENTITY_HINT);
  return { origin, account, orgCode, orgName };
}

/**
 * 告诉扩展「这条连接已经建立，可以拿这份身份作基准」。
 *
 * `identity` 必须是**服务端刚刚校验过的那一份**（就是 `connect` 前读到的可见身份），
 * `generation` 是服务端这次连接给的代号 —— ⛔ 页面不自己猜账号/组织，也不复用旧代号。
 * 扩展对不上刚才缓存的待核值或当前页面实读值时必须拒绝。
 */
export async function bindBrowserIdentity(identity: VisibleIdentity, generation: number, send: Send = sendToExtension): Promise<void> {
  if (!Number.isInteger(generation) || generation <= 0) {
    throw new ApiError('这次连接没有拿到有效代号，请重新连接。');
  }
  const value = await send({
    type: 'i8-relay:bind',
    device_id: deviceId(),
    generation,
    identity: { origin: identity.origin, account: identity.account, orgCode: identity.orgCode, orgName: identity.orgName },
  });
  if (!record(value) || value.ok !== true) {
    const message = record(value) ? readString(value, 'message') : '';
    throw new ApiError(message || '浏览器扩展没能记下这次连接，请重试。');
  }
}

/** 断开时同时让扩展忘掉基准身份（下次连必须重新读一遍）；只撤本页这条连接。 */
export async function unbindBrowserIdentity(send: Send = sendToExtension): Promise<void> {
  try {
    await send({ type: 'i8-relay:unbind', device_id: deviceId() });
  } catch {
    // 扩展不在/没应答时本来就无从泄漏；这里不阻塞断开。
  }
}

export interface RelayRunHooks {
  /** 是否还该继续轮询（`false` ⇒ 本页已断开、路由已不活跃或账号已暂停）。 */
  keep?: () => boolean;
  send?: Send;
  /** 停止信号（路由切走/账号暂停/组件卸载）。 */
  signal?: AbortSignal;
  /** 通道自身停止时回调（用于把状态如实回显到界面）。 */
  onStop?: (reason: string) => void;
}

/**
 * 通道主循环：**只有页面打开且已连接时**才跑；关页面即停（没有后台常驻）。
 *
 * 停止语义（与后端一一对应，⛔ 一律不回落登录）：
 * - `401`/`403`：身份失效/无权 ⇒ 立刻停（`api.ts` 已按既有语义处理 `401`）。
 * - `abort`/`keep()===false`：路由切走/账号暂停 ⇒ 立刻停，**并且不再执行已取回的请求**。
 * - 网络中断：**不当身份失效**，退避后重试；连续失败超限才停。
 * - 扩展无应答/回帖失败：停（用户可在「i8 接入」页重连）。
 * - 协议形状不对：停（`malformed`），⛔ 不当成"没任务"继续空转。
 *
 * ⭐ 每一次 `await` 之后都**重新核一遍** `aborted()`：中途可能已经断开、切页或换号；
 *    尤其扩展失败后回 599 的那条路径，已经停了就**不能再发回帖**（那会替用户把
 *    一次自己不认的结果报成"已发生"）。
 */
export async function runBrowserRelay(hooks: RelayRunHooks = {}): Promise<void> {
  const keep = hooks.keep ?? (() => true);
  const send = hooks.send ?? sendToExtension;
  const signal = hooks.signal;
  const stopped = (reason: string): void => {
    if (hooks.onStop) hooks.onStop(reason);
  };
  const aborted = (): boolean => Boolean(signal?.aborted) || !keep();
  let networkFaults = 0;
  while (!aborted()) {
    let payload: unknown;
    try {
      const path = `/api/m02/browser/pending?device_id=${encodeURIComponent(deviceId())}&timeout=${RELAY_POLL_SECONDS}`;
      payload = await requestJson(path, signal ? { signal } : {});
      networkFaults = 0;
    } catch (failure) {
      if (failure instanceof DOMException || aborted()) {
        stopped('idle');
        return;
      }
      // 后端受控停止（400/409/502）或身份失效（401/403）⇒ 立刻停，不回退登录。
      if (failure instanceof ApiError && failure.status > 0) {
        stopped('failed');
        return;
      }
      networkFaults += 1;
      if (networkFaults > 3) {
        stopped('network');
        return;
      }
      await new Promise<void>(resolve => setTimeout(resolve, 500 * networkFaults));
      continue;
    }
    // await 之后：这一轮结果已经无意义了就别接着做。
    if (aborted()) {
      stopped('idle');
      return;
    }
    if (!record(payload)) {
      stopped('failed');
      return;
    }
    // 真正的"这一轮没活"：服务端明确给出空请求。只有这一种才继续轮询。
    if (payload.request === undefined || payload.request === null) {
      await new Promise<void>(resolve => setTimeout(resolve, EMPTY_ROUND_MS));
      continue;
    }
    const request = readRelayRequest(payload.request);
    if (!request) {
      // 有任务但形状对不上（例如扩展/后端版本不一致）⇒ 明说停止，⛔ 不当空队列空转。
      stopped('malformed');
      return;
    }
    // ⭐ 取到活之后**再核一次**：这期间用户可能已经断开、切页或换号。
    if (aborted()) {
      stopped('idle');
      return;
    }
    let reply: RelayReply;
    try {
      reply = readRelayReply(await send({ type: 'i8-relay:execute', device_id: deviceId(), request }));
    } catch (failure) {
      if (aborted()) {
        // 已经停了：⛔ 不回帖（后端会按自己的等待上限判停），也不把这次当成"已发生"。
        stopped('idle');
        return;
      }
      // 扩展侧失败也必须回一个「终止」信号，否则后端会一直挂到自己的等待上限。
      // 回帖本身失败 ⇒ 通道已不可用：停止并把失败交出去（⛔ 不吞、不假装已回帖）。
      try {
        await postReply({ status: 599, headers: {}, body_b64: '', declared_length: 0 }, request);
      } catch (postFailure) {
        stopped('failed');
        throw postFailure instanceof ApiError
          ? postFailure
          : new ApiError('浏览器回帖失败：和工作台的连接断了，本次已停止，请重新连接。');
      }
      stopped('failed');
      if (failure instanceof ApiError) return;
      throw failure;
    }
    if (aborted()) {
      // 已经停了：不回帖（后端会按自己的等待上限判停），⛔ 也不把结果当成"本次成功"。
      stopped('idle');
      return;
    }
    await postReply(reply, request);
  }
  stopped('idle');
}

/**
 * 回帖。失败**不吞**：交给调用方按"通道已不可用"处理（停止并回显），
 * 否则界面会一直显示"已连接、在等活"，而后端早已判停 —— 那是在骗用户。
 */
async function postReply(reply: RelayReply, request: RelayRequest): Promise<void> {
  const body = {
    device_id: deviceId(),
    ticket: request.ticket,
    generation: request.generation,
    status: reply.status,
    headers: reply.headers,
    body_b64: reply.body_b64,
    declared_length: reply.declared_length,
  };
  await requestJson('/api/m02/browser/complete', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
  });
}
