/**
 * 工作台 i8 会话桥 —— MV3 service worker。
 *
 * 定位：**无状态搬运工**。它只做三件事：
 *   1. 报告用户选中的 i8 标签站点，不读取账号菜单；
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
 * 权限：`activeTab`（用户点扩展图标才临时授予当前标签）+ `scripting` + `storage`。
 *   ⇒ 页面地址与标签都由**用户点击**决定，不靠通配 host 权限。
 *
 * 注入函数必须自包含：executeScript 不携带模块作用域。
 */

'use strict';

// 允许唤起本扩展的工作台页面：生产（8000）与隔离预览（8065）。
// 与 manifest 的 `externally_connectable.matches` 必须一致；扩展这侧再核一遍 sender。
const WORKBENCH_ORIGINS = [
  'http://127.0.0.1:8000',
  'http://localhost:8000',
  'http://127.0.0.1:8065',
  'http://localhost:8065',
];

/** 后端白名单的同名集合（`browser_relay._ALLOWED_HEADERS`）；扩展这侧再收一遍。 */
const ALLOWED_HEADERS = ['accept', 'content-type', 'x-requested-with', 'accept-language'];

/**
 * **只读端点白名单**（与后端 `browser_relay._READONLY_ENDPOINTS` 逐条对应，
 * 两侧必须逐条一致；改动一处就要同步改另一处，否则一侧放行、另一侧拒）。
 *
 * ⚠️ 不看方法就当只读：登录、踢人（KillOnlineUser）、任何保存/提交端点**永远不在这里**。
 * ⚠️ `GetCntMList` 是采购合同**列表**口：正式部署的 `I8_CONTRACT_LIST_URL` 实测就是
 *    这一条（POST、无查询参数），所以这里按**字面路径**收进来。扩展读不到部署配置，
 *    若某个部署把它换成了别的地址，浏览器方式只会在本扩展这里当场停下（可诊断），
 *    ⛔ 不会静默改用登录方式。
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

/**
 * 绑定基准**按连接分键**：`i8RelayBound:<device_id>`。
 *
 * ⛔ 不能用一份全局绑定：工作台可能开着两个页面（两个 `device_id`），后一个的连接
 * 会悄悄替换前一个的基准，前一个页面还以为自己连着 —— 那样"绑定"就形同虚设。
 * 选中另一个 i8 标签仍然会让**所有**旧绑定失效（标签是用户对扩展的单次动作）。
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

/** 清掉**所有**连接的绑定与待核身份（换标签时用）。 */
async function clearAllBindings() {
  pendingIdentities.clear();
  let stored;
  try {
    stored = await chrome.storage.session.get(null);
  } catch {
    return;
  }
  const keys = Object.keys(stored || {}).filter(key => key === BOUND_PREFIX || key.startsWith(`${BOUND_PREFIX}:`));
  if (keys.length) await chrome.storage.session.remove(keys);
}

function originOf(value) {
  try {
    const url = new URL(value);
    return `${url.protocol}//${url.host}`;
  } catch {
    return '';
  }
}

function isWorkbenchSender(sender) {
  const origin = sender && (sender.origin || originOf(sender.url || ''));
  return WORKBENCH_ORIGINS.includes(originOf(origin) || origin);
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
  if (!allowed.includes(path)) {
    return '这条请求不在只读取数白名单里，已拒绝执行（未触碰标签、未改任何数据）。';
  }
  return '';
}

async function selectedTab() {
  const stored = await chrome.storage.session.get(TAB_KEY);
  const entry = stored && stored[TAB_KEY];
  if (!entry || typeof entry.tabId !== 'number' || typeof entry.origin !== 'string') return null;
  return entry;
}

/** 用户点扩展图标 ⇒ 记下**当前标签**（activeTab 由此授予），并回报读到的站点。 */
chrome.action.onClicked.addListener(async tab => {
  if (!tab || typeof tab.id !== 'number') return;
  const origin = originOf(tab.url || '');
  if (!origin) return;
  // ⚠️ `chrome.storage.session.set` 只有 `set(items)` / `set(items, callback)` 两种签名；
  //    写成 `set(key, value)` 在真浏览器里会抛 "No matching signature" 而**静默失败**
  //    （样机的 vm 替身原先按 (key, value) 实现，把这处错盖住了 —— 真浏览器样机抓到）。
  await chrome.storage.session.set({ [TAB_KEY]: { tabId: tab.id, origin, selectedAt: Date.now() } });
  // 换了标签 ⇒ 之前绑定的那些身份不再代表"当前",必须重新连接（所有连接一起失效）。
  await clearAllBindings();
});

/** 在选中标签里读取实际站点；不访问 DOM、Cookie 或存储。 */
function readIdentityInPage() {
  return { ok: true, origin: `${location.protocol}//${location.host}` };
}

async function readIdentity() {
  const entry = await selectedTab();
  if (!entry) {
    return {
      ok: false,
      code: 'need-tab',
      message: '还没有选中 i8 标签：请开到已登录的 i8 业务页，点一下扩展图标选中它，再回工作台点连接。',
    };
  }
  let results;
  try {
    results = await chrome.scripting.executeScript({
      target: { tabId: entry.tabId },
      world: 'ISOLATED',
      func: readIdentityInPage,
    });
  } catch {
    return {
      ok: false,
      code: 'need-tab',
      message: '读不到那个 i8 标签（可能已关闭、已跳到别的站点或权限已失效）。请重新点扩展图标选中标签。',
    };
  }
  const first = Array.isArray(results) ? results[0] : null;
  const value = first && first.result ? first.result : null;
  if (!value || value.ok !== true || !nonEmptyString(value.origin)) {
    return { ok: false, code: 'need-tab', message: '读不到那个 i8 标签的站点，请重新选中标签后再试。' };
  }
  if (originOf(value.origin) !== entry.origin) {
    return { ok: false, code: 'need-tab', message: '那个标签已经跳到别的站点，请重新选中当前 i8 业务页。' };
  }
  return {
    ok: true,
    origin: value.origin,
  };
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
async function executeInPage(payload, allowedHeaders, allowedMethods, allowedEndpoints) {
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
    return { failed: '请求目标不是当前标签的站点' };
  }
  // 端点白名单二次核对（service worker 侧已经拒过一次；这里是"到了页面再拒一次"）。
  const endpoints = (allowedEndpoints && allowedEndpoints[method]) || [];
  if (!endpoints.includes(target.pathname)) {
    return { failed: '这条请求不在只读取数白名单里' };
  }
  let body;
  if (payload.body_b64) {
    const binary = atob(payload.body_b64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    body = bytes;
  }
  let response;
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
  } catch (error) {
    // 超时是**超时**：⛔ 不许说成会话/身份失效（那会把用户推向重登，反而顶号）。
    if (error && error.name === 'AbortError') {
      return { failed: '这条请求超过它自己的时间预算还没回来，本次已停止（超时）。没有重试，也没有当成登录状态问题。' };
    }
    return { failed: '请求没有发出去（网络或站点不可达）' };
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (response.type === 'opaqueredirect' || response.type === 'opaque') {
    // 不透明响应拿不到状态与正文 ⇒ 不许当成结果继续解析（后端也会判停，这里先拦）。
    return { failed: '浏览器返回了不透明响应（无法核对结果）' };
  }
  const buffer = await response.arrayBuffer();
  const bytes = new Uint8Array(buffer);
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
    return { ok: false, message: '这条连接没有登记过身份（可能已断开），本次已停止。请回「i8 接入」页重新连接。' };
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
  return { ok: true };
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
  const entry = await selectedTab();
  if (!entry) {
    return { ok: false, message: '还没有选中 i8 标签：请点一下扩展图标选中那个已登录的 i8 业务页。' };
  }
  if (originOf(request.url) !== entry.origin) {
    return { ok: false, message: '请求目标与选中的 i8 标签不是同一个站点，已拒绝执行。' };
  }
  // 方法与端点都在**注入脚本之前**拒掉：不该为一条越界的请求去碰用户标签。
  if (!ALLOWED_METHODS.includes(String(request.method || '').toUpperCase())) {
    return { ok: false, message: '这个方法不在只读白名单里，已拒绝执行（未触碰标签）。' };
  }
  const endpointProblem = checkEndpoint(request.method, request.url);
  if (endpointProblem) return { ok: false, message: endpointProblem };

  // 先核连接归属与代号；页面中的执行函数再核实际站点。
  const identity = await identityStillBound(deviceId, generation, senderKey);
  if (!identity.ok) return { ok: false, message: identity.message, code: identity.code };

  let results;
  try {
    results = await chrome.scripting.executeScript({
      target: { tabId: entry.tabId },
      world: 'ISOLATED',
      func: executeInPage,
      args: [{
        url: request.url,
        method: request.method,
        headers: request.headers || {},
        body_b64: request.body_b64 || '',
        timeout_ms: request.timeout_ms,
      }, ALLOWED_HEADERS, ALLOWED_METHODS, READONLY_ENDPOINTS],
    });
  } catch {
    return { ok: false, message: '那个 i8 标签已经不可用（关闭、跳站或权限失效），请重新选中标签。' };
  }
  const first = Array.isArray(results) ? results[0] : null;
  const value = first && first.result ? first.result : null;
  if (!value) return { ok: false, message: '标签里没有返回结果，本次已停止。' };
  if (value.failed) return { ok: false, message: String(value.failed) };
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
    readIdentity().then(
      result => {
        // 只记住**这个连接的这个页面**刚读到的这一份；工作台确认连接成功后才会经 `bind` 提升为基准。
        // ⛔ 键里带发送页面：另一个本地页面用同一个 `device_id` 读身份，只会写到它自己那格，
        // 顶不掉这里待核对的那一份。
        const key = pendingKeyOf(deviceId, senderKey);
        if (result.ok) pendingIdentities.set(key, result);
        else pendingIdentities.delete(key);
        sendResponse(result);
      },
      () => sendResponse({ ok: false, message: '读取身份时出错，本次已停止。' }),
    );
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
      sendResponse({ ok: false, message: '还没有读到 i8 的身份，请先点「连接浏览器会话」。' });
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
