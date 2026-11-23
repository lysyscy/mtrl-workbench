/**
 * 工作台 i8 会话桥 —— MV3 service worker。
 *
 * 定位：**无状态搬运工**。它只做三件事：
 *   1. 在工作台配置的站点查找可用标签并探测会话；
 *   2. 在**那个标签**里执行后端**已经构造好**的那一条请求，把响应原样带回去；
 *   3. 核对连接代号、发送页面与目标站点。
 *
 * ⛔ 不做的事（都是硬约束，改动前先读 `apps/browser-extension/README.md`）：
 *   - 不读、不存、不导出 Cookie / localStorage / 任何令牌（不申请 `cookies` 权限）；
 *   - 不开启远程调试端口、不用 `debugger`、不申请 `webRequest` / `tabs` / `<all_urls>`；
 *   - 不接受页面传来的任意地址：只执行后端票里的那一条，且必须命中**只读端点白名单**；
 *   - 不自己做重试、不跟随跳转（`redirect: 'manual'`；真机上跳转拿到的是不透明响应
 *     ——`opaqueredirect`、status 0、读不到 Location——所以一律**停下**，不假装能判出跳转目标）；
 *   - 不登录、不顶号、不改页面 DOM、不猜 DOM 结构。
 *
 * 持久访问需要用户授权配置站点；点扩展图标可临时授权当前标签。
 *
 * 注入函数必须自包含：executeScript 不携带模块作用域。
 */

'use strict';

// 允许唤起本扩展的工作台页面：本机生产/预览与用户指定的局域网正式入口。
// 与 manifest 的 `externally_connectable.matches` 必须一致；扩展这侧再核一遍 sender。
const WORKBENCH_ORIGINS = [
  'http://192.168.5.3:8000',
  'http://127.0.0.1:8000',
  'http://localhost:8000',
  'http://127.0.0.1:8065',
  'http://localhost:8065',
];

// Paired with browser_relay.is_signature_image_target; the worker and tab use the same pattern.
const SIGNATURE_IMAGE_PATH = /^\/(?:[A-Za-z0-9_.~-]+\/)*[A-Za-z0-9_.~-]+\.(?:png|jpe?g|gif|bmp|webp)$/i.source;

/** 后端白名单的同名集合（`browser_relay._ALLOWED_HEADERS`）；扩展这侧再收一遍。 */
const ALLOWED_HEADERS = ['accept', 'content-type', 'x-requested-with', 'accept-language'];

/**
 * **只读端点白名单**（与后端 `browser_relay._READONLY_ENDPOINTS` 逐条对应，
 * 两侧必须逐条一致；改动一处就要同步改另一处，否则一侧放行、另一侧拒）。
 *
 * ⚠️ 不看方法就当只读：登录、踢人（KillOnlineUser）、任何保存/提交端点**永远不在这里**。
 * `GetCntMList` 是采购合同列表。工作台从当前 i8 服务地址派生列表及详情地址。
 * ⚠️ `reportExport/export` 是库存/结存的**二进制报表响应**读取（xlsx 字节原样带回，
 *    由后端核长度与文件头）；它**不是**实际打印动作，打印链路不在本通道里。
 */
const READONLY_ENDPOINTS = {
  GET: [
    '/api/WorkFlow3/WorkFlowApi/getFlowHisForPrint',
    '/SUP/RichHelp/GetCommonUseList',
    '/reportcenter/printManage/getPrintDesign',
  ],
  POST: [
    '/FC/FM/PaymentBill/getList',
    '/FC/FM/PaymentBill/getInfo',
    '/FC/FM/PaymentBill/getDetInfo',
    '/PMS/PMM/KcBaseSetting/GetWareHouseList',
    '/reportcenter/reportExport/export',
    '/PMS/PCM/Contract/GetCntMList',
    '/PMS/PCM/Contract/ProjBal/GetCntProjBalList',
    '/PMS/PCM/Contract/GetCntMInfoFirst',
    '/sup/customServer/getList',
  ],
};

/** 允许的方法（i8 取数只用到 GET / POST）。 */
const ALLOWED_METHODS = ['GET', 'POST'];

const TAB_KEY = 'i8RelayTab';
const TAB_PROBE_TIMEOUT_MS = 2500;
const TAB_PAUSED = {
  ok: false,
  code: 'tab-paused',
  message: 'i8 标签暂时没有响应，工作台会自动重试。标签休眠时可以切到 i8 标签页唤醒。',
};

/**
 * 绑定基准**按连接分键**：`i8RelayBound:<device_id>`。
 *
 * ⛔ 不能用一份全局绑定：工作台可能开着两个页面（两个 `device_id`），后一个的连接
 * 会悄悄替换前一个的基准，前一个页面还以为自己连着 —— 那样"绑定"就形同虚设。
 * 每条连接固定到完成握手的标签，发现或选择其他标签不会转移旧业务票。
 */
const BOUND_PREFIX = 'i8RelayBound';

/**
 * 刚读到、还没被工作台确认的身份，**按连接（`device_id`）分开**存。
 * 同样是隔离需要：另一个页面读一次身份不能覆盖本连接待核对的那一份。
 *
 * ⚠️ 光有 `device_id` 还不够：`device_id` 是页面自己生成的串，同一浏览器里另一个
 * 本地工作台页面完全可以拿它来冒充。所以每一份待核身份都**记下发送页面**，
 * 后续 `bind`/`execute`/`unbind` 必须来自同一个页面（见 `senderKeyOf`）。
 */
const pendingIdentities = new Map();

function boundKeyOf(deviceId) {
  return `${BOUND_PREFIX}:${deviceId}`;
}

function deviceOf(message) {
  const value = message && message.device_id;
  return typeof value === 'string' ? value.trim() : '';
}

/**
 * 发送页面的归属标识：工作台标签页 + 文档。
 *
 * ⛔ 不要只看 `origin`：所有本地工作台页面同源，`origin` 分辨不出"另一个页面"。
 * 页面刷新会换 `documentId`，于是旧连接自然失效并要求重新连接 —— 这是有意的：
 * 认不出来的归属宁可让它重连，也不要让另一份文档借同一个 `device_id` 顶掉别人。
 */
function senderKeyOf(sender) {
  if (!sender) return '';
  const tabId = sender.tab && typeof sender.tab.id === 'number' ? sender.tab.id : null;
  const documentId = typeof sender.documentId === 'string' ? sender.documentId : '';
  if (tabId === null && !documentId) return '';
  return `${tabId === null ? '-' : tabId}#${documentId || '-'}`;
}

function nonEmptyString(value) {
  return typeof value === 'string' && value.trim() !== '';
}

/** 连接只核站点；账号、组织不再从菜单读取。 */
function identityComplete(value) {
  return Boolean(value)
    && nonEmptyString(value.origin);
}

/** 取服务端给的正整数代号；缺失/0/负数/小数/字符串一律返回 0（= 无效）。 */
function positiveGeneration(value) {
  if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) return 0;
  return value;
}

function sameIdentity(left, right) {
  return Boolean(left) && Boolean(right)
    && originOf(left.origin) === originOf(right.origin);
}

function originOf(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.origin : '';
  } catch {
    return '';
  }
}

function isWorkbenchSender(sender) {
  const origin = sender && originOf(sender.origin ?? sender.url);
  return WORKBENCH_ORIGINS.includes(origin) && (sender.frameId ?? 0) === 0;
}

/**
 * 只读端点核对：**精确路径**匹配（带 query 的常量已在表里去掉了 query）。
 * 与后端 `assert_readonly` 同一套判据：`..`、`//`、尾斜杠、userinfo、非 http(s) 一律拒。
 */
function checkEndpoint(method, rawUrl) {
  let target;
  try {
    target = new URL(rawUrl);
  } catch {
    return '请求地址不成形，已拒绝执行（未触碰标签）。';
  }
  if (target.protocol !== 'http:' && target.protocol !== 'https:') {
    return '请求地址的协议不在允许范围，已拒绝执行。';
  }
  if (target.username || target.password) return '请求地址里带了账号信息，已拒绝执行。';
  const path = target.pathname;
  if (!path.startsWith('/') || path.includes('..') || path.includes('//')) {
    return '请求路径不成形，已拒绝执行。';
  }
  if (path.length > 1 && path.endsWith('/')) return '请求路径带了尾斜杠，已拒绝执行。';
  const verb = String(method || '').toUpperCase();
  const allowed = READONLY_ENDPOINTS[verb] || [];
  const rawPath = rawUrl.match(/^https?:\/\/[^/?#]+(\/[^?#]*)/i)?.[1] || '';
  const tokens = target.searchParams.getAll('s');
  const signatureImage = verb === 'GET' && !target.username && !target.password && !target.hash
    && rawPath === target.pathname && !rawPath.includes('..')
    && new RegExp(SIGNATURE_IMAGE_PATH, 'i').test(rawPath) && tokens.length === 1 && !!tokens[0].trim();
  if (!allowed.includes(path) && !signatureImage) {
    return '这条请求不在只读取数白名单里，已拒绝执行（未触碰标签、未改任何数据）。';
  }
  return '';
}

let tabSelectionUpdate = Promise.resolve();
const discoveries = new Map();
const LOGIN_REQUIRED = {ok: false, code: 'login-required', message: '请在 i8 标签页登录。登录后，工作台会自动继续连接。'};
const TAB_OPENING = {ok: false, code: 'tab-opening', message: 'i8 标签页正在加载，工作台会自动继续连接。'};
const SITE_CHANGED = {ok: false, code: 'site-changed', message: 'i8 标签的站点已变化，工作台会按当前配置重新核对。'};
const PERMISSION_REQUIRED = {
  ok: false,
  code: 'permission-required',
  message: '请授权工作台扩展访问当前 i8 站点，或在 i8 标签页点一下扩展图标。',
};
const NEED_ACTION_CLICK = {
  ok: false,
  code: 'need-action-click',
  message: '请在已登录的 i8 标签页点一下扩展图标，工作台会自动继续连接。',
};

async function readSelectedTab() {
  const stored = await chrome.storage.session.get(TAB_KEY);
  const entry = stored && stored[TAB_KEY];
  if (!entry || typeof entry.tabId !== 'number' || typeof entry.origin !== 'string') return null;
  return entry;
}

async function selectedTab() {
  await tabSelectionUpdate;
  return readSelectedTab();
}

function updateTabSelection(change) {
  tabSelectionUpdate = tabSelectionUpdate.then(change).catch(() => {});
  return tabSelectionUpdate;
}

/** 用户点扩展图标 ⇒ 记下**当前标签**（activeTab 由此授予），并回报读到的站点。 */
chrome.action.onClicked.addListener(tab => {
  if (!tab || typeof tab.id !== 'number') return;
  const origin = originOf(tab.url || '');
  if (!origin) return;
  // ⚠️ `chrome.storage.session.set` 只有 `set(items)` / `set(items, callback)` 两种签名；
  //    写成 `set(key, value)` 在真浏览器里会抛 "No matching signature" 而**静默失败**
  //    （样机的 vm 替身原先按 (key, value) 实现，把这处错盖住了 —— 真浏览器样机抓到）。
  return updateTabSelection(async () => {
    await chrome.storage.session.set({ [TAB_KEY]: { tabId: tab.id, origin, selectedAt: Date.now() } });
  });
});

// Chromium may replace the selected tab's ID when discarding it. Follow only the browser's
// replacement event. The next handshake still requires injection permission and the same origin.
chrome.tabs.onReplaced.addListener((addedTabId, removedTabId) => {
  return updateTabSelection(async () => {
    const entry = await readSelectedTab();
    if (entry?.tabId !== removedTabId) return;
    await chrome.storage.session.set({ [TAB_KEY]: { ...entry, tabId: addedTabId } });
  });
});

/** 等一个页面任务，避免把只能执行注入代码的冻结标签误判为可取数。 */
async function readIdentityInPage(origin, probePath) {
  await new Promise(resolve => setTimeout(resolve, 0));
  if (location.origin !== origin) return {code: 'site-changed'};
  if (!probePath) return {ok: true, origin};
  if (/(?:^|\/)login(?:[./]|$)/i.test(location.pathname)) return {code: 'login-required'};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2000);
  try {
    const response = await fetch(origin + probePath, {
      credentials: 'same-origin',
      redirect: 'manual',
      cache: 'no-store',
      headers: {accept: 'application/json', 'x-requested-with': 'XMLHttpRequest'},
      signal: controller.signal,
    });
    if (response.type === 'opaqueredirect' || response.status === 401) return {code: 'login-required'};
    if (!response.ok) return {code: 'tab-paused'};
    const result = await response.json();
    if (String(result?.Code) === '401' || /no sessioninfo/i.test(String(result?.Msg || result?.msg || ''))) {
      return {code: 'login-required'};
    }
    return Array.isArray(result?.Record ?? result?.record) ? {ok: true, origin} : {code: 'tab-paused'};
  } catch {
    return {code: 'tab-paused'};
  } finally {
    clearTimeout(timer);
  }
}

function tabStatus(tab) {
  if (tab.frozen || tab.discarded) return TAB_PAUSED;
  if (tab.status === 'loading') return TAB_OPENING;
  return null;
}

async function tabPaused(tabId) {
  return Boolean(tabStatus(await chrome.tabs.get(tabId)));
}

async function probeTab(entry, checkSession) {
  let results, timer;
  const probePath = '/SUP/RichHelp/GetCommonUseList?helpid=project_table_pchelp&ORMMode=true&skipInfoAuth=1';
  if (checkSession && checkEndpoint('GET', entry.origin + probePath)) return SITE_CHANGED;
  try {
    const tab = await chrome.tabs.get(entry.tabId);
    const status = tabStatus(tab);
    if (status) return status;
    if (tab.url && originOf(tab.url) !== entry.origin) return SITE_CHANGED;
    results = await Promise.race([
      chrome.scripting.executeScript({
        target: { tabId: entry.tabId },
        world: 'ISOLATED',
        func: readIdentityInPage,
        injectImmediately: true,
        args: [entry.origin, checkSession ? probePath : ''],
      }),
      new Promise(resolve => { timer = setTimeout(() => resolve(null), TAB_PROBE_TIMEOUT_MS); }),
    ]);
  } catch {
    return entry.selectedAt ? NEED_ACTION_CLICK : TAB_PAUSED;
  } finally { clearTimeout(timer); }
  if (results === null) return TAB_PAUSED;
  const first = Array.isArray(results) ? results[0] : null;
  const value = first && first.result ? first.result : null;
  if (value?.code === 'login-required') return LOGIN_REQUIRED;
  if (value?.code === 'site-changed') return SITE_CHANGED;
  if (value?.ok !== true || value.origin !== entry.origin) return TAB_PAUSED;
  return {ok: true, ...entry};
}

async function discoverTab(origin, openIfMissing) {
  const hasHost = await chrome.permissions.contains({origins: [origin + '/*']});
  const selected = await selectedTab();
  if (!hasHost) {
    if (selected?.origin !== origin) return PERMISSION_REQUIRED;
    return probeTab(selected, true);
  }
  const tabs = (await chrome.tabs.query({url: origin + '/*'}))
    .filter(tab => typeof tab.id === 'number' && originOf(tab.pendingUrl || tab.url) === origin);
  const ready = tabs.filter(tab => !tabStatus(tab));
  if (ready.length) {
    // Probe in parallel so a frozen renderer or login tab cannot hold up a healthy alternative.
    const probes = await Promise.all(ready.map(tab => probeTab({tabId: tab.id, origin}, true)));
    return probes.find(result => result.ok) || probes.find(result => result.code === 'login-required') || probes[0];
  }
  if (tabs.length) return tabs.some(tab => tabStatus(tab) === TAB_OPENING) ? TAB_OPENING : TAB_PAUSED;
  const key = `i8RelayOpened:${origin}`;
  const stored = await chrome.storage.session.get(key);
  if (typeof stored[key] === 'number') {
    const opened = await chrome.tabs.get(stored[key]).catch(() => null);
    if (opened) {
      if (opened.status !== 'complete') return TAB_OPENING;
      if (originOf(opened.url || '') === origin) return tabStatus(opened) || probeTab({tabId: stored[key], origin}, true);
      // A completed tab outside granted host permissions may no longer expose its URL.
    }
    await chrome.storage.session.remove(key);
  }
  if (!openIfMissing()) return {ok: false, code: 'need-tab', message: '请打开配置的 i8 站点，工作台会自动继续连接。'};
  const opened = await chrome.tabs.create({url: origin, active: false});
  await chrome.storage.session.set({[key]: opened.id});
  return TAB_OPENING;
}

async function readIdentity(message) {
  // Older workbenches can still use a tab explicitly selected by the user.
  if (message.origin === undefined) {
    const selected = await selectedTab();
    return selected ? probeTab(selected, false) : NEED_ACTION_CLICK;
  }
  const origin = originOf(message.origin);
  if (!origin || message.origin !== origin) return SITE_CHANGED;
  // Only one tab search/open can be in flight per configured site, even across workbench documents.
  const current = discoveries.get(origin);
  if (current) {
    current.openIfMissing ||= message.openIfMissing === true;
    return current.result;
  }
  const attempt = {openIfMissing: message.openIfMissing === true};
  attempt.result = discoverTab(origin, () => attempt.openIfMissing).finally(() => discoveries.delete(origin));
  discoveries.set(origin, attempt);
  return attempt.result;
}

/**
 * 在选中标签里执行**后端票里那一条**请求（ISOLATED 世界 ⇒ 请求沿页面 origin 发出）。
 *
 * ⚠️ `chrome.scripting.executeScript` 只把**函数源码**注入页面，**不带模块作用域** ——
 *    所以白名单必须经 `args` 传进来，⛔ 别在这里引用 `ALLOWED_HEADERS` / `ALLOWED_METHODS`，
 *    否则一执行就是 `ReferenceError`（这条曾有 4 个协议测试当场抓到）。
 *
 * 返回的 `declared_length` 是扩展自己数出来的字节数；后端会拿它核对解码长度，
 * 对不上即判「传输可能被截断」并停止。
 */
async function executeInPage(payload, allowedHeaders, allowedMethods, allowedEndpoints, signaturePath) {
  const allowed = new Set(allowedHeaders);
  const headers = {};
  for (const [key, value] of Object.entries(payload.headers || {})) {
    if (typeof value !== 'string') continue;
    if (!allowed.has(key.toLowerCase())) continue;
    headers[key] = value;
  }
  const method = String(payload.method || '').toUpperCase();
  if (!allowedMethods.includes(method)) {
    return { failed: '方法不在只读白名单里' };
  }
  let target;
  try {
    target = new URL(payload.url);
  } catch {
    return { failed: '请求地址不成形' };
  }
  if (`${target.protocol}//${target.host}` !== `${location.protocol}//${location.host}`) {
    return { failed: '请求目标不是当前标签的站点', code: 'target-mismatch' };
  }
  // 端点白名单二次核对（service worker 侧已经拒过一次；这里是"到了页面再拒一次"）。
  const endpoints = (allowedEndpoints && allowedEndpoints[method]) || [];
  const rawPath = payload.url.match(/^https?:\/\/[^/?#]+(\/[^?#]*)/i)?.[1] || '';
  const tokens = target.searchParams.getAll('s');
  const signatureImage = method === 'GET' && !target.username && !target.password && !target.hash
    && rawPath === target.pathname && !rawPath.includes('..')
    && new RegExp(signaturePath, 'i').test(rawPath) && tokens.length === 1 && !!tokens[0].trim();
  if (!endpoints.includes(target.pathname) && !signatureImage) {
    return { failed: '这条请求不在只读取数白名单里' };
  }
  let body;
  if (payload.body_b64) {
    const binary = atob(payload.body_b64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    body = bytes;
  }
  let response, signatureBytes;
  // 预算由后端按**这条请求自己的** read 超时给（合同列表 200s / 详情 60s / 默认 30s），
  // ⛔ 不要在这里另设固定值：拿 30s 去截 200s 的列表就是凭空判死一条正常请求。
  const budget = Number(payload.timeout_ms) > 0 ? Number(payload.timeout_ms) : 0;
  const controller = budget > 0 && typeof AbortController === 'function' ? new AbortController() : null;
  let timer = null;
  if (controller) {
    timer = setTimeout(() => controller.abort(), budget);
  }
  try {
    response = await fetch(target.href, {
      method,
      headers,
      ...(body ? { body } : {}),
      credentials: 'same-origin',
      redirect: 'manual',
      cache: 'no-store',
      ...(controller ? { signal: controller.signal } : {}),
    });
    if (response.type === 'opaqueredirect' || response.type === 'opaque') {
      return { failed: '浏览器返回了不透明响应（无法核对结果）', code: 'opaque-response' };
    }
    if (signatureImage) {
      const mediaType = (response.headers.get('content-type') || '').split(';', 1)[0].trim().toLowerCase();
      // Relay status and media type for a precise stop reason, without returning a login page.
      const noImage = { status: response.status, headers: { 'content-type': mediaType }, body_b64: '', declared_length: 0 };
      if (response.status < 200 || response.status >= 300 || mediaType === 'text/html') return noImage;

      const bytes = new Uint8Array(await response.arrayBuffer());
      const header = String.fromCharCode(...bytes.subarray(0, 12));
      const raster = ['\x89PNG\r\n\x1a\n', '\xff\xd8\xff', 'GIF87a', 'GIF89a', 'BM'].some(magic => header.startsWith(magic))
        || (header.startsWith('RIFF') && header.slice(8, 12) === 'WEBP');
      if (!raster) {
        const text = new TextDecoder().decode(bytes);
        let envelope;
        try { envelope = JSON.parse(text); } catch { /* The server may also return plain text. */ }
        if ([envelope?.Code, envelope?.code].some(code => String(code).trim() === '401') || /no sessioninfo/i.test(text)) {
          return { failed: 'i8 会话已失效，本批已停止。', code: 'session-ended' };
        }
      }
      const imageType = /^image\/.+/.test(mediaType);
      const genericBinary = ['', 'application/octet-stream', 'binary/octet-stream'].includes(mediaType);
      if (!raster || (!imageType && !genericBinary)) return noImage;
      signatureBytes = bytes;
    }
  } catch (error) {
    // 超时是**超时**：⛔ 不许说成会话/身份失效（那会把用户推向重登，反而顶号）。
    if (error && error.name === 'AbortError') {
      return { failed: '这条请求超过它自己的时间预算还没回来，本次已停止（超时）。没有重试，也没有当成登录状态问题。', code: 'request-timeout' };
    }
    return { failed: '请求未能完成（网络或站点不可达）', code: 'request-network' };
  } finally {
    if (timer) clearTimeout(timer);
  }
  const bytes = signatureBytes ?? new Uint8Array(await response.arrayBuffer());
  let binary = '';
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(index, index + chunk));
  }
  const replyHeaders = {};
  response.headers.forEach((value, key) => {
    // 只回必要的响应头；Set-Cookie 浏览器本来就不暴露，这里也不额外读取。
    if (['content-type', 'content-length', 'location'].includes(key.toLowerCase())) replyHeaders[key] = value;
  });
  return {
    status: response.status,
    headers: replyHeaders,
    body_b64: btoa(binary),
    declared_length: bytes.length,
  };
}

/**
 * 每次执行前确认发送页面与连接代号。实际目标站点由 executeInPage 检查。
 *
 * 基准是**按连接（`device_id`）分开存**的：另一个页面的连接不能替换这一份。
 *
 * 先核代号（本地读，不碰标签），再执行请求。
 * 代号不对时**一个字节都不该发出去**，也不该去读用户的 i8 页面。
 */
async function identityStillBound(deviceId, generation, senderKey) {
  if (!deviceId) {
    return { ok: false, message: '这条请求没有连接标识，本次已停止。请回「i8 接入」页重新连接。' };
  }
  if (!senderKey) {
    return { ok: false, message: '认不出这条请求来自哪个工作台页面，本次已停止。请刷新页面后重新连接。' };
  }
  if (!generation) {
    return { ok: false, message: '这条请求没有带连接代号，已忽略。请回「i8 接入」页重新连接后再抓取。' };
  }
  const stored = await chrome.storage.session.get(boundKeyOf(deviceId));
  const bound = stored && stored[boundKeyOf(deviceId)];
  if (!bound) {
    return { ok: false, code: 'binding-lost', message: '这条连接没有登记过身份，工作台会自动重新连接。' };
  }
  if (bound.sender !== senderKey) {
    return {
      ok: false,
      code: 'sender-mismatch',
      message: '这条连接是另一个工作台页面建立的，本页面不能借用它取数。请在本页面重新连接。',
    };
  }
  if (positiveGeneration(bound.generation) !== generation) {
    return {
      ok: false,
      code: 'stale-generation',
      message: '这条请求属于上一次连接（代号已过期），本次已停止，没有发出任何请求。请回「i8 接入」页重新连接后再抓取。',
    };
  }
  const selected = bound.selectedAt ? await selectedTab() : null;
  if (typeof bound.tabId !== 'number' || bound.selectedAt &&
      (selected?.tabId !== bound.tabId || selected.selectedAt !== bound.selectedAt)) {
    return {ok: false, code: 'binding-lost', message: '临时选中的 i8 标签已变化，工作台会重新连接。'};
  }
  return bound;
}

async function execute(message, senderKey) {
  const request = message && message.request;
  const deviceId = deviceOf(message);
  const generation = positiveGeneration(request && request.generation);
  // ⛔ 代号是**第一道闸**，排在选中标签、读 DOM、注入脚本之前：
  // 过期的请求不该去碰用户的 i8 页面，更不该发出去。
  if (!deviceId) {
    return { ok: false, message: '这条请求没有连接标识，已忽略。请回「i8 接入」页重新连接。' };
  }
  if (!generation) {
    return { ok: false, message: '这条请求没有带有效的连接代号，已忽略。请回「i8 接入」页重新连接后再抓取。' };
  }
  if (!request || typeof request.url !== 'string' || typeof request.ticket !== 'string') {
    return { ok: false, message: '请求不完整，已忽略。' };
  }
  // 方法与端点都在**注入脚本之前**拒掉：不该为一条越界的请求去碰用户标签。
  if (!ALLOWED_METHODS.includes(String(request.method || '').toUpperCase())) {
    return { ok: false, message: '这个方法不在只读白名单里，已拒绝执行（未触碰标签）。' };
  }
  const endpointProblem = checkEndpoint(request.method, request.url);
  if (endpointProblem) return { ok: false, message: endpointProblem };

  // 先核连接归属与代号；页面中的执行函数再核实际站点。
  const entry = await identityStillBound(deviceId, generation, senderKey);
  if (!entry.ok) return entry;
  if (originOf(request.url) !== entry.origin) {
    return { ok: false, code: 'target-mismatch', message: '请求目标与绑定的 i8 标签不是同一个站点，已拒绝执行。' };
  }

  let results;
  try {
    if (await tabPaused(entry.tabId)) return TAB_PAUSED;
    results = await chrome.scripting.executeScript({
      target: { tabId: entry.tabId },
      world: 'ISOLATED',
      func: executeInPage,
      injectImmediately: true,
      args: [{
        url: request.url,
        method: request.method,
        headers: request.headers || {},
        body_b64: request.body_b64 || '',
        timeout_ms: request.timeout_ms,
      }, ALLOWED_HEADERS, ALLOWED_METHODS, READONLY_ENDPOINTS, SIGNATURE_IMAGE_PATH],
    });
  } catch {
    return { ok: false, code: 'binding-lost', message: '绑定的 i8 标签已不可用，工作台会自动重新连接。' };
  }
  const first = Array.isArray(results) ? results[0] : null;
  const value = first && first.result ? first.result : null;
  if (!value) return { ok: false, message: '标签里没有返回结果，本次已停止。' };
  if (value.failed) return { ok: false, message: String(value.failed), code: value.code || 'malformed' };
  if (typeof value.status !== 'number' || typeof value.body_b64 !== 'string') {
    return { ok: false, message: '标签返回的结果不成形，本次已停止。' };
  }
  return {
    ok: true,
    status: value.status,
    headers: value.headers || {},
    body_b64: value.body_b64,
    declared_length: value.declared_length,
  };
}

/** 待核身份的键：连接 + **发送页面**，两者都参与。 */
function pendingKeyOf(deviceId, senderKey) {
  return `${deviceId}\u0000${senderKey}`;
}

chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  if (!isWorkbenchSender(sender)) {
    sendResponse({ ok: false, message: '这个页面没有连接权限。' });
    return false;
  }
  const type = message && message.type;
  const deviceId = deviceOf(message);
  const senderKey = senderKeyOf(sender);
  if (type === 'i8-relay:identity') {
    if (!deviceId) {
      sendResponse({ ok: false, message: '读取身份时缺少连接标识，本次已停止。' });
      return false;
    }
    if (!senderKey) {
      sendResponse({ ok: false, message: '认不出这个工作台页面，本次已停止。请刷新页面后重新连接。' });
      return false;
    }
    readIdentity(message).then(
      result => {
        // 只记住**这个连接的这个页面**刚读到的这一份；工作台确认连接成功后才会经 `bind` 提升为基准。
        // ⛔ 键里带发送页面：另一个本地页面用同一个 `device_id` 读身份，只会写到它自己那格，
        // 顶不掉这里待核对的那一份。
        const key = pendingKeyOf(deviceId, senderKey);
        if (result.ok) pendingIdentities.set(key, result);
        else pendingIdentities.delete(key);
        sendResponse(result.ok ? {ok: true, origin: result.origin, ...(message.origin ? {sessionReady: true} : {})} : result);
      },
      () => sendResponse({ ok: false, message: '读取身份时出错，本次已停止。' }),
    );
    return true;
  }
  if (type === 'i8-relay:health') {
    identityStillBound(deviceId, positiveGeneration(message.generation), senderKey).then(
      async bound => {
        const status = bound.ok ? (bound.origin === message.origin ? await probeTab(bound, true) : SITE_CHANGED) : bound;
        sendResponse(status.ok ? {ok: true} : status);
      },
    ).catch(() => sendResponse(TAB_PAUSED));
    return true;
  }
  if (type === 'i8-relay:permission') {
    const origin = originOf(message.origin);
    if (!senderKey || !deviceId || !origin || origin !== message.origin) {
      sendResponse(SITE_CHANGED);
      return false;
    }
    const key = `i8RelayPermission:${senderKey}`;
    chrome.storage.session.set({[key]: origin}).then(() =>
      chrome.tabs.create({url: chrome.runtime.getURL('permission.html') + '#' + encodeURIComponent(key)}),
    ).then(() => sendResponse({ok: true}), () => sendResponse(NEED_ACTION_CLICK));
    return true;
  }
  if (type === 'i8-relay:bind') {
    const generation = positiveGeneration(message && message.generation);
    if (!deviceId) {
      sendResponse({ ok: false, message: '绑定时缺少连接标识，本次已停止。请回「i8 接入」页重新连接。' });
      return false;
    }
    if (!senderKey) {
      sendResponse({ ok: false, message: '认不出这个工作台页面，本次已停止。请刷新页面后重新连接。' });
      return false;
    }
    if (!generation) {
      sendResponse({ ok: false, message: '绑定时缺少有效的连接代号，本次已停止。请回「i8 接入」页重新连接。' });
      return false;
    }
    const key = pendingKeyOf(deviceId, senderKey);
    const pending = pendingIdentities.get(key);
    if (!pending) {
      sendResponse({ ok: false, code: 'binding-lost', message: '扩展暂存的站点已丢失，工作台会重新核对并连接。' });
      return false;
    }
    // 绑定站点必须与扩展刚才实读的站点一致。
    if (!identityComplete(message.identity)) {
      sendResponse({ ok: false, message: '绑定时没有带上站点，本次已停止。请回「i8 接入」页重新连接。' });
      return false;
    }
    if (!sameIdentity(message.identity, pending)) {
      sendResponse({ ok: false, code: 'site-changed', message: '服务端核对的站点与本扩展刚读到的不一致，请重新连接。' });
      return false;
    }
    // 绑定按 device_id 保存，另一个页面不能替换已有连接。
    chrome.storage.session.get(boundKeyOf(deviceId)).then(stored => {
      const existing = stored && stored[boundKeyOf(deviceId)];
      if (existing && existing.sender && existing.sender !== senderKey) {
        sendResponse({ ok: false, code: 'sender-mismatch', message: '这条连接已被另一个工作台页面占用，本页面不能顶掉它。请刷新本页面后重新连接，或先在那边断开。' });
        return;
      }
      const record = { ...pending, generation, sender: senderKey };
      chrome.storage.session.set({ [boundKeyOf(deviceId)]: record }).then(
        () => sendResponse({ ok: true, generation }),
        () => sendResponse({ ok: false, message: '保存连接时出错，本次已停止。' }),
      );
    }, () => sendResponse({ ok: false, message: '绑定时读取已有连接出错，本次已停止。' }));
    return true;
  }
  if (type === 'i8-relay:unbind') {
    if (!deviceId) {
      sendResponse({ ok: false, message: '撤绑时缺少连接标识，已忽略。' });
      return false;
    }
    if (!senderKey) {
      sendResponse({ ok: false, message: '认不出这个工作台页面，已忽略。' });
      return false;
    }
    // 只撤**这条连接的这个页面**的，别动另一个页面已经绑好的连接。
    pendingIdentities.delete(pendingKeyOf(deviceId, senderKey));
    chrome.storage.session.get(boundKeyOf(deviceId)).then(stored => {
      const bound = stored && stored[boundKeyOf(deviceId)];
      // 别的页面建的连接，这个页面撤不掉（否则一个页面能把另一个页面的连接清掉）。
      if (bound && bound.sender && bound.sender !== senderKey) {
        sendResponse({ ok: false, message: '这条连接是另一个工作台页面建立的，本页面不能撤绑。' });
        return;
      }
      chrome.storage.session.remove(boundKeyOf(deviceId)).then(
        () => sendResponse({ ok: true }),
        () => sendResponse({ ok: false }),
      );
    }, () => sendResponse({ ok: false }));
    return true;
  }
  if (type === 'i8-relay:execute') {
    execute(message, senderKey).then(sendResponse, () => sendResponse({ ok: false, message: '执行请求时出错，本次已停止。' }));
    return true;
  }
  sendResponse({ ok: false, message: '不认识的消息类型，已忽略。' });
  return false;
});
