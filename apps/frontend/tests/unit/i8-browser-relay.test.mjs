/**
 * 「用浏览器已有会话」页面侧单测（`TAIL-476`）。
 *
 * 钉的是**页面这一层**的责任边界（不装扩展、不连后端、不连真实 i8）：
 *   - 连接标识每文档一份、只放本页内存，身份事件时换掉；⛔ 它**不是**取数方式；
 *   - 「取数方式」按账号隔离记住：同账号失效重登仍是浏览器，换号各用各的；
 *   - 通道主循环遇到 `401` 立刻停，⛔ 不重试、不回落直连；
 *   - 网络中断与身份失效分开处理（前者有限退避，后者立即停）；
 *   - 停止/断开之后**不再执行**已取回的请求，也**不再回帖**；
 *   - 回帖失败不吞（否则界面会一直显示"已连接"，而后端早已判停）；
 *   - 请求/回帖的字段成形性在页面侧就校验，畸形一律停（⛔ 不当空队列空转）；
 *   - 连接代号（`generation`）与设备标识进出都带，页面不自己编账号/组织；
 *   - 浏览器方式缺连接时七个入口一律**当场失败**，⛔ 不退回登录、不带强踢授权。
 *
 * 运行：`node --import=tsx --test tests/unit/i8-browser-relay.test.mjs`
 */

import test, { beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  bindBrowserIdentity,
  connectBrowser,
  deviceId,
  readBrowserIdentity,
  readBrowserRelayState,
  readRelayReply,
  readRelayRequest,
  relayAvailable,
  relayExtensionId,
  relayMode,
  resetBrowserRelay,
  runBrowserRelay,
  SESSION_MODE_BROWSER,
  SESSION_MODE_HTTP,
  sessionParams,
  sessionPayload,
  setRelayExtensionId,
  setRelayMode,
  unbindBrowserIdentity,
} from '../../src/i8-browser-relay.ts';
import { ApiError } from '../../src/api.ts';

class MemoryStorage {
  #m = new Map();
  getItem(key) { return this.#m.has(key) ? this.#m.get(key) : null; }
  setItem(key, value) { this.#m.set(String(key), String(value)); }
  removeItem(key) { this.#m.delete(key); }
  clear() { this.#m.clear(); }
  get length() { return this.#m.size; }
  key(index) { return [...this.#m.keys()][index] ?? null; }
}

const base = {
  connected: true,
  mode: SESSION_MODE_BROWSER,
  origin: 'https://i8.example.test',
  i8_user: 'tester001',
  expected_org: '3700000000000014',
  expected_org_code: '109',
  expected_org_name: '第四工程公司',
  generation: 3,
  message: '已连接',
};

const identity = { origin: 'https://i8.example.test' };

let restored;

beforeEach(() => {
  restored = { fetch: globalThis.fetch, window: globalThis.window, chrome: globalThis.chrome };
  globalThis.sessionStorage = new MemoryStorage();
  globalThis.window = { dispatchEvent() {} };
});

afterEach(() => {
  globalThis.fetch = restored.fetch;
  globalThis.window = restored.window;
  globalThis.chrome = restored.chrome;
  delete globalThis.sessionStorage;
});

const jsonResponse = (payload, status = 200) => ({
  status,
  ok: status >= 200 && status < 300,
  json: async () => payload,
  headers: { get: () => null },
});

test('连接标识每文档一份且可被身份事件换掉（不是凭据、不落盘、不串标签页）', () => {
  const first = deviceId();
  assert.match(first, /^dev-[0-9a-f-]{36}$/);
  assert.equal(deviceId(), first, '同一页面重复取必须稳定');
  assert.equal(globalThis.sessionStorage.getItem('mtrl.i8.relay.device'), null, '⛔ 不落 sessionStorage：复制标签页会把它一起复制走');
  resetBrowserRelay();
  const second = deviceId();
  assert.notEqual(second, first, '清掉后必须换一个新的，绝不复用别人的连接');
  assert.equal(deviceId(), second, '换过之后仍然稳定');
});

test('取数方式按账号记住：同账号失效后仍是浏览器，换号不串，只有用户能改', () => {
  const alice = '1:alice';
  const bob = '2:bob';
  assert.equal(relayMode(alice), SESSION_MODE_HTTP, '没选过＝产品原有的直连行为');
  setRelayMode(SESSION_MODE_BROWSER, alice);
  assert.equal(relayMode(alice), SESSION_MODE_BROWSER);
  assert.equal(globalThis.sessionStorage.getItem(`mtrl.i8.relay.mode.${alice}`), SESSION_MODE_BROWSER);
  assert.equal(relayMode(bob), SESSION_MODE_HTTP, '另一个账号不受影响');
  // 身份事件（退出登录/401 重登）只换设备标识：⛔ 不许把用户选过的浏览器方式清掉。
  resetBrowserRelay();
  assert.equal(relayMode(alice), SESSION_MODE_BROWSER, '⛔ 同账号重新登录后不许悄悄回落到直连');
  assert.equal(relayMode(bob), SESSION_MODE_HTTP, '⛔ 换号不许继承别人的选择');
  setRelayMode(SESSION_MODE_HTTP, alice);
  assert.equal(relayMode(alice), SESSION_MODE_HTTP);
  assert.equal(globalThis.sessionStorage.getItem(`mtrl.i8.relay.mode.${alice}`), null, '切回直连不留下痕迹');
});

test('扩展 ID 是固定的：装好扩展即可用，不需要用户填；没装扩展一律不可用', () => {
  globalThis.chrome = undefined;
  assert.equal(relayAvailable(), false, '没装扩展就是不可用');
  globalThis.chrome = { runtime: { sendMessage() {} } };
  assert.equal(relayAvailable(), true, '装了扩展即可用，不需要先填 ID');
  assert.match(relayExtensionId(), /^[a-p]{32}$/, '默认扩展 ID 必须成形');
  setRelayExtensionId('ponmlkjihgfedcba');
  assert.equal(relayExtensionId(), 'ponmlkjihgfedcba', '覆盖值优先（只有换了打包方式才需要）');
  setRelayExtensionId('');
  assert.match(relayExtensionId(), /^[a-p]{32}$/, '清掉覆盖值就回到固定 ID，不会变成空');
  assert.equal(relayAvailable(), true);
});

test('连接状态字段必须齐；缺项/未知模式一律抛错不猜', () => {
  assert.deepEqual(readBrowserRelayState(base), base);
  for (const broken of [
    { ...base, connected: 'yes' },
    { ...base, mode: 'auto' },
    { ...base, origin: undefined },
    { ...base, i8_user: 42 },
    { ...base, expected_org: null },
    { ...base, expected_org_code: undefined },
    { ...base, expected_org_name: 7 },
    { ...base, generation: 1.5 },
    { ...base, generation: undefined },
    { ...base, message: undefined },
    null,
  ]) {
    assert.throws(() => readBrowserRelayState(broken), error => error instanceof ApiError);
  }
});

test('连接只提交扩展读取的站点，不依赖菜单账号与组织', async () => {
  const sent = [];
  globalThis.fetch = async (path, init) => {
    sent.push({ path, method: init.method, body: init.body ? JSON.parse(init.body) : null });
    return jsonResponse(base);
  };
  const state = await connectBrowser(identity);
  assert.equal(state.connected, true);
  assert.equal(state.generation, 3);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].path, '/api/m02/browser/connect');
  assert.equal(sent[0].method, 'POST');
  assert.deepEqual(sent[0].body, {
    device_id: deviceId(),
    i8_origin: 'https://i8.example.test',
  });
});

test('只需扩展的站点结果即可连接；读取失败如实抛出', async () => {
  const seen = [];
  const good = await readBrowserIdentity(async message => { seen.push(message); return { ok: true, ...identity }; });
  assert.deepEqual(good, identity);
  assert.equal(seen[0].type, 'i8-relay:identity');
  assert.equal(seen[0].device_id, deviceId(), '待核身份必须按本条连接缓存，别的页面不能替换它');
  assert.deepEqual(await readBrowserIdentity(async () => ({ ok: true, origin: identity.origin })), identity);
  await assert.rejects(readBrowserIdentity(async () => ({ ok: false, message: '请先选中 i8 标签' })), error => /选中 i8 标签/.test(error.message));
  await assert.rejects(readBrowserIdentity(async () => ({ ok: true, origin: 1 })), error => /i8 标签/.test(error.message));
});

test('连接建立后把服务端刚校验过的身份与代号交给扩展；断开时让它忘掉（扩展没应答不阻塞断开）', async () => {
  const seen = [];
  await bindBrowserIdentity(identity, 3, async message => { seen.push(message); return { ok: true }; });
  assert.equal(seen.length, 1);
  assert.equal(seen[0].type, 'i8-relay:bind');
  assert.equal(seen[0].device_id, deviceId(), '绑定只对本条连接生效');
  assert.equal(seen[0].generation, 3, '代号必须是服务端这次给的，页面不自己编');
  assert.deepEqual(seen[0].identity, identity, '绑定的是服务端校验过的那份身份，不是页面猜的账号/组织');
  await assert.rejects(bindBrowserIdentity(identity, 0, async () => ({ ok: true })), error => /有效代号/.test(error.message));
  await assert.rejects(bindBrowserIdentity(identity, 1.5, async () => ({ ok: true })), error => /有效代号/.test(error.message));
  await assert.rejects(bindBrowserIdentity(identity, 3, async () => ({ ok: false, message: '还没读到 i8 身份' })), error => error instanceof ApiError);
  await assert.rejects(bindBrowserIdentity(identity, 3, async () => ({ ok: false })), error => /没能记下/.test(error.message));
  const forget = [];
  await unbindBrowserIdentity(async message => { forget.push(message); return { ok: true }; });
  assert.equal(forget.length, 1);
  assert.equal(forget[0].type, 'i8-relay:unbind');
  assert.equal(forget[0].device_id, deviceId(), '只撤本页这条连接');
  await unbindBrowserIdentity(async () => { throw new ApiError('扩展不在'); });
});

test('请求票成形性：缺票/缺地址/缺代号/缺超时预算一律当作没有活，不执行任何东西', () => {
  const valid = { ticket: 't-1', generation: 2, method: 'post', url: 'https://i8.example.test/x', headers: { a: 'b' }, body_b64: '', timeout_ms: 200 };
  assert.deepEqual(readRelayRequest(valid), { ...valid, method: 'POST' });
  for (const broken of [
    {},
    { ticket: '' },
    { ticket: 't', method: 'GET', url: 'https://i8.example.test/x' },
    { ticket: 't', url: 'x', method: 1, generation: 1 },
    { ticket: 't', url: 'https://i8.example.test/x', method: 'POST', generation: '2' },
    { ticket: 't', url: 'https://i8.example.test/x', method: 'POST', generation: 1.5 },
    { ...valid, timeout_ms: undefined },
    { ...valid, timeout_ms: 0 },
    { ...valid, timeout_ms: -1 },
    { ...valid, timeout_ms: 1.5 },
    { ...valid, timeout_ms: '200' },
    null,
  ]) {
    assert.equal(readRelayRequest(broken), null);
  }
});

test('回帖字段不完整就抛错（后端会按等待上限判停，页面不许瞎编）', () => {
  const ok = { status: 200, headers: {}, body_b64: 'e30=', declared_length: 2 };
  assert.deepEqual(readRelayReply(ok), ok);
  for (const broken of [
    { ...ok, status: 200.5 },
    { ...ok, status: '200' },
    { ...ok, declared_length: -1 },
    { ...ok, declared_length: 1.5 },
    { ...ok, body_b64: undefined },
    null,
  ]) {
    assert.throws(() => readRelayReply(broken), error => error instanceof ApiError);
  }
});

test('窄助手：浏览器方式缺连接当场失败（零请求、不退回登录），直连方式原样保留授权字段', () => {
  const browserChoice = { mode: SESSION_MODE_BROWSER, connected: false };
  assert.throws(() => sessionPayload(browserChoice, { allow_kick: true }, { year_month: '2026-11' }), error => error instanceof ApiError && /不会改用登录方式/.test(error.message));
  assert.throws(() => sessionParams(browserChoice), error => error instanceof ApiError);
  const browser = sessionPayload({ mode: SESSION_MODE_BROWSER, connected: true }, { allow_kick: true }, { year_month: '2026-11' });
  assert.equal(browser.session_mode, SESSION_MODE_BROWSER);
  assert.equal(browser.device_id, deviceId());
  assert.equal(browser.year_month, '2026-11');
  assert.equal('allow_kick' in browser, false, '⛔ 浏览器方式不带强踢授权');
  const http = sessionPayload({ mode: SESSION_MODE_HTTP, connected: false }, { allow_kick: true }, { year_month: '2026-11' });
  assert.deepEqual(http, { year_month: '2026-11', allow_kick: true, session_mode: SESSION_MODE_HTTP }, '直连时授权参数与改动前逐字节一致');
  assert.equal('device_id' in http, false);
  const params = sessionParams({ mode: SESSION_MODE_HTTP, connected: false }, { allow_kick: 'true' }, { expected_account: 'tester001' });
  assert.equal(params.get('session_mode'), SESSION_MODE_HTTP);
  assert.equal(params.get('allow_kick'), 'true');
  assert.equal(params.get('expected_account'), 'tester001');
  const browserParams = sessionParams({ mode: SESSION_MODE_BROWSER, connected: true }, { allow_kick: 'true' }, { expected_account: 'tester001' });
  assert.equal(browserParams.get('session_mode'), SESSION_MODE_BROWSER);
  assert.equal(browserParams.get('device_id'), deviceId());
  assert.equal(browserParams.get('allow_kick'), null);
});

test('通道主循环：401 立刻停，不重试、不回落直连', async () => {
  const sent = [];
  globalThis.fetch = async path => {
    sent.push(path);
    return jsonResponse({ ok: false, message: '登录已失效，请重新登录后重试。' }, 401);
  };
  setRelayMode(SESSION_MODE_BROWSER);
  const stops = [];
  await runBrowserRelay({ send: async () => { throw new Error('不该调用扩展'); }, onStop: reason => stops.push(reason) });
  assert.equal(sent.length, 1, '401 之后不许再轮询第二次');
  assert.deepEqual(stops, ['failed']);
  assert.equal(relayMode(), SESSION_MODE_BROWSER, '⛔ 失败后绝不能悄悄改回直连');
});

test('通道主循环：后端受控停止（409）也立刻停，且不执行任何请求', async () => {
  const sent = [];
  globalThis.fetch = async path => {
    sent.push(path);
    return jsonResponse({ ok: false, message: '浏览器连接不在', code: 'i8_browser_relay_unavailable' }, 409);
  };
  let executed = 0;
  await runBrowserRelay({ send: async () => { executed += 1; return { ok: true }; } });
  assert.equal(sent.length, 1);
  assert.equal(executed, 0);
});

test('通道主循环：网络中断属于另一类，有限退避后停（不当身份失效）', async () => {
  let attempts = 0;
  globalThis.fetch = async () => {
    attempts += 1;
    throw new TypeError('fetch failed');
  };
  await runBrowserRelay({ send: async () => ({ ok: true, status: 200, headers: {}, body_b64: '', declared_length: 0 }) });
  assert.ok(attempts >= 2 && attempts <= 4, `退避后应停止，实际尝试 ${attempts} 次`);
});

test('通道主循环：有任务但协议形状对不上，如实停止（⛔ 不当空队列空转）', async () => {
  let polls = 0;
  let executed = 0;
  const stops = [];
  globalThis.fetch = async path => {
    if (path.startsWith('/api/m02/browser/pending')) {
      polls += 1;
      // 版本不一致：后端给了任务，但缺这次的超时预算。
      return jsonResponse({ request: { ticket: 't-1', generation: 1, method: 'POST', url: 'https://i8.example.test/x', headers: {}, body_b64: '' } });
    }
    throw new Error('畸形任务不许被执行');
  };
  await runBrowserRelay({
    send: async () => { executed += 1; return { ok: true }; },
    onStop: reason => stops.push(reason),
  });
  assert.equal(polls, 1, '不许把畸形任务当成"没活"继续轮询');
  assert.equal(executed, 0);
  assert.deepEqual(stops, ['malformed']);
});

test('通道主循环：已停止（路由切走/账号暂停）时不再执行已取回的请求', async () => {
  let executed = 0;
  globalThis.fetch = async () => jsonResponse({ request: { ticket: 't-1', generation: 1, method: 'POST', url: 'https://i8.example.test/x', headers: {}, body_b64: '', timeout_ms: 200 } });
  const controller = new AbortController();
  const run = runBrowserRelay({
    signal: controller.signal,
    send: async () => { executed += 1; return { ok: true, status: 200, headers: {}, body_b64: '', declared_length: 0 }; },
    onStop: () => {},
  });
  // 第一轮里立刻停：取到活之后再核一次，若已停止就既不执行也不回帖。
  controller.abort();
  await run;
  assert.equal(executed, 0, '停止后不许再把请求交给扩展执行');
});

test('通道主循环：执行期间被中止，扩展的失败不回帖（不替用户报"已发生"）', async () => {
  const posted = [];
  const stops = [];
  const controller = new AbortController();
  globalThis.fetch = async (path, init) => {
    if (path.startsWith('/api/m02/browser/pending')) {
      return jsonResponse({ request: { ticket: 't-7', generation: 2, method: 'GET', url: 'https://i8.example.test/x', headers: {}, body_b64: '', timeout_ms: 200 } });
    }
    posted.push(JSON.parse(init.body));
    return jsonResponse({ accepted: true });
  };
  await runBrowserRelay({
    signal: controller.signal,
    send: async () => { controller.abort(); throw new ApiError('浏览器扩展没有应答。'); },
    onStop: reason => stops.push(reason),
  });
  assert.equal(posted.length, 0, '已经中止时不许再回帖（599 也不行）');
  assert.deepEqual(stops, ['idle']);
});

test('通道主循环：拿到活就交给扩展、并把回帖（含代号）原样送回后端', async () => {
  const ticket = 't-42';
  const posted = [];
  let polls = 0;
  globalThis.fetch = async (path, init) => {
    if (path.startsWith('/api/m02/browser/pending')) {
      polls += 1;
      return jsonResponse({ request: polls === 1 ? { ticket, generation: 5, method: 'POST', url: 'https://i8.example.test/x', headers: {}, body_b64: '', timeout_ms: 200 } : null });
    }
    posted.push(JSON.parse(init.body));
    return jsonResponse({ accepted: true });
  };
  let keep = true;
  const run = runBrowserRelay({
    keep: () => keep,
    send: async message => {
      assert.equal(message.type, 'i8-relay:execute');
      assert.equal(message.device_id, deviceId(), '执行只走本页这条连接');
      assert.equal(message.request.ticket, ticket);
      assert.equal(message.request.generation, 5);
      return { ok: true, status: 200, headers: { 'content-type': 'application/json' }, body_b64: 'e30=', declared_length: 2 };
    },
  });
  while (posted.length === 0) await new Promise(resolve => setTimeout(resolve, 5));
  keep = false;
  await run;
  assert.equal(posted.length, 1);
  assert.equal(posted[0].ticket, ticket);
  assert.equal(posted[0].generation, 5, '回帖必须带回同一个代号，否则迟到旧回帖会落到新连接上');
  assert.equal(posted[0].status, 200);
  assert.equal(posted[0].declared_length, 2);
});

test('扩展没有应答时回终止信号（599），不让后端干等到超时', async () => {
  const posted = [];
  let polls = 0;
  globalThis.fetch = async (path, init) => {
    if (path.startsWith('/api/m02/browser/pending')) {
      polls += 1;
      return jsonResponse({ request: polls === 1 ? { ticket: 't-9', generation: 4, method: 'GET', url: 'https://i8.example.test/x', headers: {}, body_b64: '', timeout_ms: 200 } : null });
    }
    posted.push(JSON.parse(init.body));
    return jsonResponse({ accepted: true });
  };
  await runBrowserRelay({ send: async () => { throw new ApiError('浏览器扩展没有应答。'); } });
  assert.equal(posted.length, 1);
  assert.equal(posted[0].status, 599);
  assert.equal(posted[0].declared_length, 0);
  assert.equal(posted[0].ticket, 't-9');
  assert.equal(posted[0].generation, 4);
});

test('回帖失败不吞：通道当场停（不再假装"已连接在等活"）', async () => {
  let polls = 0;
  globalThis.fetch = async path => {
    if (path.startsWith('/api/m02/browser/pending')) {
      polls += 1;
      return jsonResponse({ request: { ticket: 't-3', generation: 1, method: 'GET', url: 'https://i8.example.test/x', headers: {}, body_b64: '', timeout_ms: 200 } });
    }
    throw new TypeError('fetch failed');
  };
  await assert.rejects(
    runBrowserRelay({ send: async () => ({ ok: true, status: 200, headers: {}, body_b64: '', declared_length: 0 }) }),
    error => error instanceof ApiError && /连接失败/.test(error.message),
  );
  assert.equal(polls, 1, '回帖失败后不许继续轮询');
});

test('模式常量是产品原有 http 与新增 browser，没有第三态', () => {
  assert.equal(SESSION_MODE_HTTP, 'http');
  assert.equal(SESSION_MODE_BROWSER, 'browser');
});
