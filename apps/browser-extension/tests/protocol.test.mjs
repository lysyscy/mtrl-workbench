/**
 * 扩展侧协议测试（`TAIL-476`）。
 *
 * 目的：在**不装到用户 Edge、不连真实 i8** 的前提下，把 `service_worker.js` 的协议边界钉死：
 *   - 只接受工作台 origin 的调用（`sender` 校验，不靠 manifest 单点）；
 *   - 连接只读站点，菜单隐藏或不存在都不阻塞；
 *   - 连接按 `device_id` 隔离：待核身份与绑定基准分开存，另一个页面不能替换；
 *   - `bind` 带服务端给的正整数 `generation`，与刚读到的站点一致；
 *   - 请求使用选中标签的会话，不再读取或核验菜单中的账号、组织；
 *   - 只执行**只读端点白名单**里的 GET/POST，登录/踢人/保存与各种伪装路径一律不碰标签；
 *   - 只转发白名单请求头（Cookie / Authorization 永不外流）；
 *   - 不跟随跳转（真机上是不透明响应 ⇒ 直接停；不假装能判出跳转目标）；
 *   - 请求自带的 `timeout_ms` 是**超时**预算，超了按超时停，⛔ 不谎称"会话失效"；
 *   - `declared_length` 自己数，供后端核完整性。
 *
 * ⚠️ 这是**协议测试**，不是真实业务验收：真实 Edge 安装/授权/取数另由主控执行。
 *    这里的 `chrome`、DOM 与 `fetch` 都是最小替身，只能证明"代码路径与判据"，不能代替浏览器。
 *
 * 运行：`node --test apps/browser-extension/tests/protocol.test.mjs`
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const HERE = dirname(fileURLToPath(import.meta.url));
const SOURCE = readFileSync(join(HERE, '..', 'service_worker.js'), 'utf8');

const WORKBENCH = 'http://127.0.0.1:8000';
const I8 = 'https://i8.example.test';
/** 连接标识（页面每次加载一个）：绑定与待核身份都按它分开存。 */
const DEVICE = 'dev-test-1';
/** 服务端在 connect 时给的代号（正整数），绑定时带回来。 */
const GENERATION = 3;

test('指定局域网工作台可以连接和取数，其他主机与端口不放行', async () => {
  const manifest = JSON.parse(readFileSync(join(HERE, '..', 'manifest.json'), 'utf8'));
  assert.ok(manifest.externally_connectable.matches.includes('http://192.168.5.3:8000/*'));
  const sender = {...workbenchSender, origin: 'http://192.168.5.3:8000', url: 'http://192.168.5.3:8000/app/i8'};
  const page = boot({fetchImpl: async () => reply()});
  await page.bind({sender});
  assert.equal((await page.call(exec(), sender)).ok, true);
  for (const origin of ['http://192.168.5.4:8000', 'http://192.168.5.3:8080']) {
    assert.equal((await page.call(exec(), {...sender, origin, url: origin + '/app/i8'})).ok, false);
  }
});

/* ------------------------------------------------------------------ *
 * 最小 chrome 替身：只实现扩展真正用到的那几个口，别的一个不给。
 * ------------------------------------------------------------------ */

function boot({ tab = { tabId: 7, origin: I8 }, page: initial = {}, fetchImpl = null } = {}) {
  const listeners = { action: null, external: null };
  const session = new Map();
  if (tab) session.set('i8RelayTab', { ...tab, selectedAt: 1 });
  const scriptCalls = [];
  const page = {
    displayName: '测试员',
    account: 'tester001',
    orgName: '第四工程公司',
    orgCode: '109',
    ...initial,
  };

  const chrome = {
    action: { onClicked: { addListener: fn => { listeners.action = fn; } } },
    tabs: {
      get: async () => ({ status: 'complete', frozen: page.frozen }),
      onReplaced: { addListener() {} },
    },
    runtime: { onMessageExternal: { addListener: fn => { listeners.external = fn; } } },
    storage: {
      session: {
        // ⚠️ 真实 `chrome.storage.session` 的签名只有：
        //      get(keys) / get(keys, callback) / set(items) / set(items, callback) / remove(keys)
        //    替身必须同样严格：写成 `set(key, value)` 要**抛错**。原先替身按 (key, value)
        //    实现，把真机上 "No matching signature" 的静默失败整整盖住了 —— 是
        //    `tests/browser_smoke.py`（真浏览器）抓出来的。别把替身放宽回去。
        get: async (keys, callback) => {
          // `get(null)` 在真实 API 里返回**全部**项（换标签时要按前缀清绑定，靠它枚举）。
          if (keys !== null && typeof keys !== 'string' && !Array.isArray(keys) && (typeof keys !== 'object' || keys === undefined)) {
            throw new Error('No matching signature.');
          }
          let result;
          if (keys === null) {
            result = {};
            for (const [key, value] of session.entries()) result[key] = value;
          } else if (typeof keys === 'string') result = session.has(keys) ? { [keys]: session.get(keys) } : {};
          else if (Array.isArray(keys)) {
            result = {};
            for (const key of keys) if (session.has(key)) result[key] = session.get(key);
          } else result = { ...keys };
          if (callback !== undefined) {
            if (typeof callback !== 'function') throw new Error('No matching signature.');
            callback(result);
          }
          return result;
        },
        set: async (items, callback) => {
          if (typeof items !== 'object' || items === null || Array.isArray(items)) {
            throw new Error('No matching signature.');
          }
          if (callback !== undefined && typeof callback !== 'function') {
            throw new Error('No matching signature.');
          }
          for (const [key, value] of Object.entries(items)) session.set(key, value);
          if (callback) callback();
        },
        remove: async (keys, callback) => {
          if (typeof keys !== 'string' && !Array.isArray(keys)) throw new Error('No matching signature.');
          for (const key of Array.isArray(keys) ? keys : [keys]) session.delete(key);
          if (callback !== undefined) {
            if (typeof callback !== 'function') throw new Error('No matching signature.');
            callback();
          }
        },
      },
    },
    scripting: {
      executeScript: async details => {
        scriptCalls.push({
          name: details.func && details.func.name,
          tabId: details.target && details.target.tabId,
          world: details.world,
        });
        // 复刻「页面里那段函数」的真实执行环境：只有 location/document/fetch，没有 chrome。
        // `AbortController`/`setTimeout` 也是页面里本来就有的（超时预算靠它们）。
        const sandbox = {
          location: new URL(page.origin || I8),
          document: { querySelectorAll: () => { throw new Error('连接和取数不得读取账号菜单'); } },
          fetch: fetchImpl,
          URL,
          Uint8Array,
          atob,
          btoa,
          console,
          AbortController,
          setTimeout,
          clearTimeout,
        };
        const result = await vm.runInNewContext(`(${details.func.toString()})`, sandbox)(...(details.args || []));
        return [{ result }];
      },
    },
  };

  const context = vm.createContext({ chrome, URL, Uint8Array, atob, btoa, console, setTimeout, clearTimeout });
  vm.runInContext(SOURCE, context, { filename: 'service_worker.js' });

  const call = (message, sender = workbenchSender) => new Promise(resolve => {
    let settled = false;
    const done = value => { if (!settled) { settled = true; resolve(value); } };
    const returned = listeners.external(message, sender, done);
    if (returned !== true) setTimeout(() => done(undefined), 0);
  });

  /**
   * 走完整的「读身份 → bind」两步，等价于工作台点「连接浏览器会话」。
   * 协议要求两步都带**同一个** `device_id`，bind 还带服务端给的 `generation`
   * 与被服务端核对过的那一份 `identity`。
   */
  const bind = async ({ device = DEVICE, generation = GENERATION, sender = workbenchSender } = {}) => {
    const identity = await call({ type: 'i8-relay:identity', device_id: device }, sender);
    assert.equal(identity.ok, true, `读身份应当成功，实际：${JSON.stringify(identity)}`);
    const bound = await call({
      type: 'i8-relay:bind',
      device_id: device,
      generation,
      identity: {
        origin: identity.origin,
        account: identity.account,
        orgCode: identity.orgCode,
        orgName: identity.orgName,
      },
    }, sender);
    assert.equal(bound.ok, true, `绑定应当成功，实际：${JSON.stringify(bound)}`);
    return identity;
  };

  const boundKeys = () => [...session.keys()].filter(key => key === 'i8RelayBound' || key.startsWith('i8RelayBound:'));
  const executed = () => scriptCalls.filter(entry => entry.name === 'executeInPage');

  return { call, bind, listeners, scriptCalls, executed, session, boundKeys, page };
}

/**
 * 工作台页面的 `sender` 替身。
 *
 * `tab.id` + `documentId` 是**归属**的依据：同一浏览器里所有本地工作台页面同源，
 * 只看 origin 分不出"另一个页面"。真实 `sender` 上这两项都有（`sender.tab` 只在
 * 来自标签页时存在，外部网页消息正是这种）。
 */
const workbenchSender = {
  origin: WORKBENCH,
  url: `${WORKBENCH}/app/`,
  tab: { id: 11 },
  documentId: 'doc-workbench-1',
};

/** 另一个工作台页面（同源、不同标签/文档）—— 用来证明它顶不掉上面的连接。 */
const otherSender = {
  origin: WORKBENCH,
  url: `${WORKBENCH}/app/`,
  tab: { id: 12 },
  documentId: 'doc-workbench-2',
};

const request = overrides => ({
  ticket: 't-1',
  generation: GENERATION,
  method: 'POST',
  url: `${I8}/FC/FM/PaymentBill/getList`,
  headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
  body_b64: '',
  // 后端按**这条请求自己的** read 超时给预算（合同列表 200s / 详情 60s / 默认 30s）。
  timeout_ms: 30_000,
  ...overrides,
});

/** 一条 `i8-relay:execute` 消息：协议要求带 `device_id`。 */
const exec = (overrides = {}, device = DEVICE) => ({
  type: 'i8-relay:execute',
  device_id: device,
  request: request(overrides),
});

/** 造一个和浏览器真实响应同形的替身（`fetch` 只用到这几个字段）。 */
function reply({ status = 200, headers = {}, bytes = new Uint8Array([0x7b, 0x7d]), type = 'basic' } = {}) {
  const entries = Object.entries(headers);
  return {
    type,
    status,
    headers: { forEach: visit => { for (const [key, value] of entries) visit(value, key); } },
    arrayBuffer: async () => bytes,
  };
}

/* ------------------------------------------------------------------ *
 * 1. 来源与标签
 * ------------------------------------------------------------------ */

test('非工作台 origin 的调用一律拒绝，且一根手指都不碰标签', async () => {
  const page = boot();
  for (const sender of [
    { origin: 'https://evil.test', url: 'https://evil.test/app/' },
    { origin: '', url: '' },
    null,
  ]) {
    const answer = await page.call(exec(), sender);
    assert.equal(answer.ok, false);
    assert.match(answer.message, /没有连接权限/);
  }
  assert.deepEqual(page.scriptCalls, [], '被拒的调用不许注入任何脚本');
});

test('没有选中 i8 标签时明确拒绝，不猜也不执行', async () => {
  const page = boot({ tab: null });
  const answer = await page.call(exec());
  assert.equal(answer.ok, false);
  assert.match(answer.message, /还没有选中 i8 标签/);
  assert.deepEqual(page.scriptCalls, []);
});

test('点扩展图标会记下当前标签，并把所有连接的身份基准作废', async () => {
  const page = boot();
  await page.bind();
  assert.deepEqual(page.boundKeys(), [`i8RelayBound:${DEVICE}`], 'bind 之后应当有身份基准');

  await page.listeners.action({ id: 9, url: `${I8}/FC/FM/PaymentBill/list` });
  const tab = page.session.get('i8RelayTab');
  assert.equal(tab.tabId, 9);
  assert.equal(tab.origin, I8);
  assert.deepEqual(page.boundKeys(), [], '换了标签就不再有"已核身份"（所有连接一起失效）');

  const stale = await page.call({ type: 'i8-relay:bind', device_id: DEVICE, generation: GENERATION });
  assert.equal(stale.ok, false);
  assert.equal(stale.code, 'binding-lost');
});

/* ------------------------------------------------------------------ *
 * 2. 身份读取：按已核 DOM，不猜
 * ------------------------------------------------------------------ */

test('连接仅报告实际站点，不报告未核验的账号与组织', async () => {
  const page = boot();
  const identity = await page.call({ type: 'i8-relay:identity', device_id: DEVICE });
  assert.equal(identity.ok, true);
  assert.equal(identity.origin, I8);
  assert.equal(identity.account, undefined);
  assert.equal(identity.orgName, undefined);
  assert.equal(identity.orgCode, undefined);
});

test('菜单隐藏或不存在也能连接并取数', async () => {
  for (const state of [{ hidden: true }, { panels: 0 }]) {
    const page = boot({ page: state, fetchImpl: async () => reply() });
    await page.bind();
    const answer = await page.call(exec());
    assert.equal(answer.ok, true, JSON.stringify(answer));
    assert.equal(page.executed().length, 1);
  }
});

test('标签冻结时暂停探测和取数，恢复后可重新握手', async () => {
  const page = boot({ fetchImpl: async () => reply() });
  await page.bind();
  page.page.frozen = true;
  const identity = {type: 'i8-relay:identity', device_id: DEVICE, probe_only: true};
  assert.equal((await page.call(identity)).code, 'tab-paused');
  assert.equal((await page.call(exec())).code, 'tab-paused');
  assert.deepEqual(page.executed(), []);
  page.page.frozen = false;
  await page.bind({generation: GENERATION + 1});
  assert.equal((await page.call(exec({generation: GENERATION + 1}))).ok, true);
});

test('没读到身份就不许 bind，也不许执行（连接必须有可信基准）', async () => {
  const page = boot({ page: { hidden: true } });
  const bound = await page.call({ type: 'i8-relay:bind', device_id: DEVICE, generation: GENERATION });
  assert.equal(bound.ok, false);
  assert.equal(bound.code, 'binding-lost');

  const executed = await page.call(exec());
  assert.equal(executed.ok, false);
  assert.match(executed.message, /没有登记过身份/);
  assert.deepEqual(page.executed(), []);
});

/* ------------------------------------------------------------------ *
 * 3. 只读端点白名单
 * ------------------------------------------------------------------ */

test('登录/踢人/保存、方法错配与各种伪装路径一律不执行', async () => {
  const cases = [
    ['POST', `${I8}/SUP/Login/SupLogin`, /只读/],
    ['POST', `${I8}/SUP/Login/KillOnlineUser`, /只读/],
    ['POST', `${I8}/FC/FM/PaymentBill/save`, /只读/],
    ['GET', `${I8}/FC/FM/PaymentBill/getList`, /只读/],
    ['DELETE', `${I8}/FC/FM/PaymentBill/getList`, /方法/],
    ['POST', `${I8}/FC/FM/PaymentBill/getList/`, /尾斜杠/],
    ['POST', `${I8}/FC/FM/PaymentBill/%2e%2e/getList`, /只读|不成形/],
    ['POST', `${I8}//FC/FM/PaymentBill/getList`, /只读|不成形/],
    ['POST', `${I8}/FC/FM/PaymentBill/GetList`, /只读/],
    ['POST', `https://user:pw@i8.example.test/FC/FM/PaymentBill/getList`, /账号信息/],
  ];
  for (const [method, url, expected] of cases) {
    const page = boot({ fetchImpl: async () => reply() });
    const answer = await page.call(exec({ method, url }));
    assert.equal(answer.ok, false, `${method} ${url} 不该被放行`);
    assert.match(answer.message, expected, `${method} ${url} 的拒绝理由不对：${answer.message}`);
    assert.deepEqual(page.executed(), [], `${method} ${url} 不许真正执行`);
  }
});

test('白名单内的只读接口正常执行（对照组，别把门关死）', async () => {
  const page = boot({ fetchImpl: async () => reply() });
  await page.bind();
  const answer = await page.call(exec());
  assert.equal(answer.ok, true, JSON.stringify(answer));
  assert.equal(page.executed().length, 1);
});

test('请求目标与选中的标签不同源即拒', async () => {
  const page = boot({ fetchImpl: async () => reply() });
  await page.bind();
  const answer = await page.call(exec({ url: 'https://evil.test/FC/FM/PaymentBill/getList' }));
  assert.equal(answer.ok, false);
  assert.match(answer.message, /不是同一个站点/);
  assert.deepEqual(page.executed(), []);
});

/* ------------------------------------------------------------------ *
 * 4. 会话使用选中标签，实际跳站仍停止
 * ------------------------------------------------------------------ */

test('取数不再以菜单账号组织作为拦截条件', async () => {
  const page = boot({ fetchImpl: async () => reply() });
  await page.bind();
  page.page.account = 'someone-else';
  page.page.orgCode = '208';

  const answer = await page.call(exec());
  assert.equal(answer.ok, true);
  assert.equal(page.executed().length, 1);
});

test('连接后标签跳到别的站点，请求仍不发出', async () => {
  let requests = 0;
  const page = boot({ fetchImpl: async () => { requests += 1; return reply(); } });
  await page.bind();
  page.page.origin = 'https://other.example.test';
  const otherOrg = await page.call(exec());
  assert.equal(otherOrg.ok, false);
  assert.match(otherOrg.message, /不是当前标签的站点/);
  assert.equal(requests, 0);
});

/* ------------------------------------------------------------------ *
 * 5. 头、跳转、二进制
 * ------------------------------------------------------------------ */

test('只转发白名单请求头：Cookie / Authorization 一个字节都不外流', async () => {
  const seen = [];
  const page = boot({
    fetchImpl: async (href, init) => {
      seen.push({ href, init });
      return reply();
    },
  });
  await page.bind();
  const answer = await page.call(exec({
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Requested-With': 'XMLHttpRequest',
      Cookie: 'ASP.NET_SessionId=sentinel-cookie-value',
      Authorization: 'Bearer sentinel-token-value',
      Host: 'i8.example.test',
      Referer: `${I8}/FC/FM/PaymentBill/list`,
    },
  }));
  assert.equal(answer.ok, true, JSON.stringify(answer));
  assert.equal(seen.length, 1);
  const forwarded = Object.keys(seen[0].init.headers).map(key => key.toLowerCase()).sort();
  assert.deepEqual(forwarded, ['content-type', 'x-requested-with']);
  const flat = JSON.stringify(seen[0].init.headers);
  assert.ok(!flat.includes('sentinel-cookie-value'), '会话 Cookie 不许出现在实际发出的请求里');
  assert.ok(!flat.includes('sentinel-token-value'), 'Authorization 不许出现在实际发出的请求里');
});

test('跳转请求仍然不跟随，且真机结果按不透明响应停下', async () => {
  // ⛔ 别把这条用例写成"3xx 原样带回 status/location" —— 那是错的。
  //    真浏览器样机（`tests/browser_smoke.py`）实测：`redirect:'manual'` 拿到的是
  //    `type: 'opaqueredirect'`、`status: 0`、headers 为空，读不出 302 也读不出 Location。
  //    所以这里的替身必须复刻真机：宁可判停，也不能假装能判出"跳到哪了"。
  const seen = [];
  const page = boot({
    fetchImpl: async (href, init) => {
      seen.push(init);
      return reply({ type: 'opaqueredirect', status: 0, headers: {} });
    },
  });
  await page.bind();
  const answer = await page.call(exec());
  assert.equal(answer.ok, false);
  assert.match(answer.message, /不透明响应/);
  assert.equal(seen[0].redirect, 'manual', '⛔ 不许让浏览器自己跟到登录页');
  assert.equal(seen[0].credentials, 'same-origin');
  assert.equal(seen[0].cache, 'no-store');
});

test('不透明响应直接拒（拿不到状态与正文就不能当结果）', async () => {
  const page = boot({ fetchImpl: async () => reply({ status: 0, type: 'opaqueredirect' }) });
  await page.bind();
  const answer = await page.call(exec());
  assert.equal(answer.ok, false);
  assert.match(answer.message, /不透明响应/);
});

test('二进制响应按字节完整带回，长度由扩展自己数', async () => {
  const payload = new Uint8Array(303);
  payload.set([0x50, 0x4b, 0x03, 0x04]);
  for (let index = 4; index < payload.length; index += 1) payload[index] = index % 251;

  const page = boot({ fetchImpl: async () => reply({ bytes: payload, headers: { 'content-type': 'application/vnd.ms-excel' } }) });
  await page.bind();
  const answer = await page.call(exec({ url: `${I8}/reportcenter/reportExport/export` }));
  assert.equal(answer.ok, true, JSON.stringify(answer));
  assert.equal(answer.declared_length, 303, '长度必须是扩展自己数的字节数，供后端核截断');
  const decoded = Buffer.from(answer.body_b64, 'base64');
  assert.equal(decoded.length, 303);
  assert.deepEqual(new Uint8Array(decoded), payload);
});

test('响应头只回必要几项，Set-Cookie 之类不外带', async () => {
  const page = boot({
    fetchImpl: async () => reply({
      headers: {
        'content-type': 'application/json',
        'set-cookie': 'ASP.NET_SessionId=leak; path=/',
        'x-powered-by': 'ASP.NET',
      },
    }),
  });
  await page.bind();
  const answer = await page.call(exec());
  assert.equal(answer.ok, true);
  assert.deepEqual(Object.keys(answer.headers).map(key => key.toLowerCase()), ['content-type']);
});

test('不认识的消息类型明确忽略，不当成执行', async () => {
  const page = boot();
  const answer = await page.call({ type: 'i8-relay:whatever' });
  assert.equal(answer.ok, false);
  assert.match(answer.message, /不认识的消息类型/);
  assert.deepEqual(page.scriptCalls, []);
});

/* ------------------------------------------------------------------ *
 * 6. 采购合同列表口、按连接隔离、代号与超时预算
 * ------------------------------------------------------------------ */

test('采购合同列表口（正式部署实测地址）在浏览器方式下可以走', async () => {
  // 采购合同列表使用已验证的固定 POST 路径。
  // 过去扩展白名单比后端少这一项，用户只能被劝回直连；现在两侧一致。
  const page = boot({ fetchImpl: async () => reply() });
  await page.bind();
  const answer = await page.call(exec({ url: `${I8}/PMS/PCM/Contract/GetCntMList` }));
  assert.equal(answer.ok, true, JSON.stringify(answer));
  assert.equal(page.executed().length, 1);
});

test('身份与绑定按连接隔离：另一个页面的连接不能替换这一份', async () => {
  const page = boot({ fetchImpl: async () => reply() });
  await page.bind({ device: 'dev-a' });
  // 第二个页面（另一个 device_id）自己读身份、自己绑定。
  await page.bind({ device: 'dev-b' });
  assert.deepEqual(
    page.boundKeys().sort(),
    ['i8RelayBound:dev-a', 'i8RelayBound:dev-b'],
    '两个连接的绑定各存一份，互不覆盖',
  );

  // 撤掉 dev-b 之后，dev-a 仍然可用（⛔ 不能把别人的连接一起撤掉）。
  const unbound = await page.call({ type: 'i8-relay:unbind', device_id: 'dev-b' });
  assert.equal(unbound.ok, true);
  assert.deepEqual(page.boundKeys(), ['i8RelayBound:dev-a']);

  const still = await page.call(exec({}, 'dev-a'));
  assert.equal(still.ok, true, JSON.stringify(still));

  const gone = await page.call(exec({}, 'dev-b'));
  assert.equal(gone.ok, false);
  assert.match(gone.message, /没有登记过身份/);
});

test('没有 device_id 的请求一律不动手（不猜是谁的连接）', async () => {
  const page = boot({ fetchImpl: async () => reply() });
  await page.bind();
  const noDevice = await page.call({ type: 'i8-relay:execute', request: request() });
  assert.equal(noDevice.ok, false);
  assert.match(noDevice.message, /没有连接标识/);

  const noDeviceBind = await page.call({ type: 'i8-relay:bind', generation: GENERATION });
  assert.equal(noDeviceBind.ok, false);
  assert.match(noDeviceBind.message, /缺少连接标识/);

  const noDeviceIdentity = await page.call({ type: 'i8-relay:identity' });
  assert.equal(noDeviceIdentity.ok, false);
  assert.match(noDeviceIdentity.message, /缺少连接标识/);

  assert.deepEqual(page.executed(), []);
});

test('bind 必须带服务端给的正整数代号', async () => {
  for (const generation of [undefined, 0, -1, 1.5, 'x']) {
    const page = boot();
    await page.call({ type: 'i8-relay:identity', device_id: DEVICE });
    const bound = await page.call({ type: 'i8-relay:bind', device_id: DEVICE, generation });
    assert.equal(bound.ok, false, `代号 ${String(generation)} 不该被接受`);
    assert.match(bound.message, /连接代号/);
    assert.deepEqual(page.boundKeys(), [], '没绑成就不许留基准');
  }
});

test('bind 时报来的站点与刚读到的不一致时停止', async () => {
  const page = boot();
  const identity = await page.call({ type: 'i8-relay:identity', device_id: DEVICE });
  assert.equal(identity.ok, true);
  const bound = await page.call({
    type: 'i8-relay:bind',
    device_id: DEVICE,
    generation: GENERATION,
    identity: { origin: 'https://other.example.test' },
  });
  assert.equal(bound.ok, false);
  assert.equal(bound.code, 'site-changed');
  assert.deepEqual(page.boundKeys(), []);
});

test('读站点后菜单消失，仍可完成绑定', async () => {
  const page = boot();
  const identity = await page.call({ type: 'i8-relay:identity', device_id: DEVICE });
  page.page.panels = 0;
  const bound = await page.call({
    type: 'i8-relay:bind',
    device_id: DEVICE,
    generation: GENERATION,
    identity: {
      origin: identity.origin,
      account: identity.account,
      orgCode: identity.orgCode,
      orgName: identity.orgName,
    },
  });
  assert.equal(bound.ok, true);
  assert.deepEqual(page.boundKeys(), [`i8RelayBound:${DEVICE}`]);
});

test('请求自带的 timeout_ms 真的当预算用，超时按超时停（不说成会话失效）', async () => {
  let seenSignal = null;
  const page = boot({
    fetchImpl: async (href, init) => {
      seenSignal = init.signal;
      // 模仿一个永远不回的慢请求：只等 abort。
      return new Promise((resolve, reject) => {
        init.signal.addEventListener('abort', () => {
          const error = new Error('aborted');
          error.name = 'AbortError';
          reject(error);
        });
      });
    },
  });
  await page.bind();
  const answer = await page.call(exec({ timeout_ms: 20, url: `${I8}/PMS/PCM/Contract/GetCntMList` }));
  assert.equal(answer.ok, false);
  assert.match(answer.message, /超过它自己的时间预算/);
  assert.ok(!/会话|登录不|重新登录/.test(answer.message), `⛔ 超时不许说成身份/会话问题：${answer.message}`);
  assert.ok(seenSignal, '页面里必须真的把 signal 交给 fetch');
});

test('没有 timeout_ms 时不设预算，照常执行（不凭空造一个 30 秒）', async () => {
  const seen = [];
  const page = boot({ fetchImpl: async (href, init) => { seen.push(init); return reply(); } });
  await page.bind();
  const answer = await page.call(exec({ timeout_ms: undefined }));
  assert.equal(answer.ok, true, JSON.stringify(answer));
  assert.equal(seen[0].signal, undefined, '没有预算就不该挂 AbortController 的 signal');
});

/* ------------------------------------------------------------------ *
 * 7. 代号必须是这条连接当前的、bind 必须带完整身份、发送页面必须归属
 *    —— 这三条都是"别让一条本来就该停的请求碰到用户标签"。
 * ------------------------------------------------------------------ */

test('请求代号不是这条连接当前的 ⇒ 零注入零请求（连 DOM 都不读）', async () => {
  for (const generation of [undefined, 0, -1, 1.5, 'x', GENERATION - 1, GENERATION + 1]) {
    const page = boot({ fetchImpl: async () => reply() });
    await page.bind();                       // 绑定时用的是 GENERATION
    const before = page.scriptCalls.length;  // bind 自己读过身份，基准要按"之后新增"算
    const answer = await page.call(exec({ generation }));
    assert.equal(answer.ok, false, `代号 ${String(generation)} 不该被执行`);
    assert.match(answer.message, /代号/);
    assert.deepEqual(
      page.scriptCalls.slice(before), [],
      `代号 ${String(generation)} 被拒时必须一个脚本都没注入（既不读 i8 DOM，也没发请求）`,
    );
  }
});

test('代号变了（断线重连后的旧请求）⇒ 停，不把旧结果打到新连接上', async () => {
  const page = boot({ fetchImpl: async () => reply() });
  await page.bind({ generation: 3 });
  const before = page.scriptCalls.length;
  const stale = await page.call(exec({ generation: 3 - 1 }));
  assert.equal(stale.ok, false);
  assert.equal(stale.code, 'stale-generation');
  assert.deepEqual(page.scriptCalls.slice(before), [], '旧代号的请求连标签都不许碰');

  // 同一个 device 重新绑定到新代号后，新代号的请求才通过。
  await page.bind({ generation: 4 });
  const fresh = await page.call(exec({ generation: 4 }));
  assert.equal(fresh.ok, true, JSON.stringify(fresh));
  assert.equal(page.executed().length, 1);
});

test('bind 不带站点时停止', async () => {
  const page = boot();
  const identity = await page.call({ type: 'i8-relay:identity', device_id: DEVICE });
  assert.equal(identity.ok, true);

  const missing = await page.call({ type: 'i8-relay:bind', device_id: DEVICE, generation: GENERATION });
  assert.equal(missing.ok, false, '缺 identity 必须被拒');
  assert.match(missing.message, /站点/);

  for (const broken of [
    { origin: '' },
    { origin: '  ' },
    { account: 'tester001', orgCode: '109', orgName: '第四工程公司' },
  ]) {
    const answer = await page.call({
      type: 'i8-relay:bind', device_id: DEVICE, generation: GENERATION, identity: broken,
    });
    assert.equal(answer.ok, false, `残缺身份 ${JSON.stringify(broken)} 必须被拒`);
  }
  assert.deepEqual(page.boundKeys(), [], '没绑成就不许留基准');
});

test('另一个工作台页面借同一个 device_id 不能执行、不能顶掉、不能撤绑', async () => {
  const page = boot({ fetchImpl: async () => reply() });
  await page.bind();                         // 由 workbenchSender 建立连接

  // 1) 执行：认得出是别的页面 ⇒ 零注入。
  const before = page.scriptCalls.length;
  const stolen = await page.call(exec(), otherSender);
  assert.equal(stolen.ok, false);
  assert.equal(stolen.code, 'sender-mismatch');
  assert.deepEqual(page.scriptCalls.slice(before), [], '别的页面不许让扩展去碰用户的 i8 标签');

  // 2) 顶绑：即使它自己读到了身份、也带了正确代号，也不许覆盖已有基准。
  const identity = await page.call({ type: 'i8-relay:identity', device_id: DEVICE }, otherSender);
  assert.equal(identity.ok, true, '读身份本身可以，但结果只记在它自己那一格');
  const overwrite = await page.call({
    type: 'i8-relay:bind',
    device_id: DEVICE,
    generation: GENERATION,
    identity: {
      origin: identity.origin,
      account: identity.account,
      orgCode: identity.orgCode,
      orgName: identity.orgName,
    },
  }, otherSender);
  assert.equal(overwrite.ok, false, '别的页面不能顶掉这条连接');
  assert.equal(overwrite.code, 'sender-mismatch');

  // 3) 原页面仍可正常取数（基准没被动过）。
  const still = await page.call(exec());
  assert.equal(still.ok, true, JSON.stringify(still));

  // 4) 撤绑也只能由建立连接的那个页面做。
  const stolenUnbind = await page.call({ type: 'i8-relay:unbind', device_id: DEVICE }, otherSender);
  assert.equal(stolenUnbind.ok, false);
  assert.match(stolenUnbind.message, /不能撤绑/);
  assert.deepEqual(page.boundKeys(), [`i8RelayBound:${DEVICE}`], '基准还在');

  const ownUnbind = await page.call({ type: 'i8-relay:unbind', device_id: DEVICE });
  assert.equal(ownUnbind.ok, true);
  assert.deepEqual(page.boundKeys(), []);
});

test('认不出来自哪个页面 ⇒ 不建立待核身份、不执行', async () => {
  const page = boot({ fetchImpl: async () => reply() });
  const anonymous = { origin: WORKBENCH, url: `${WORKBENCH}/app/` };   // 没有 tab/documentId
  const identity = await page.call({ type: 'i8-relay:identity', device_id: DEVICE }, anonymous);
  assert.equal(identity.ok, false);
  assert.match(identity.message, /认不出这个工作台页面/);
  const answer = await page.call(exec(), anonymous);
  assert.equal(answer.ok, false);
  assert.match(answer.message, /认不出/);
  assert.deepEqual(page.scriptCalls, []);   // 这一页从没成功 bind 过，所以是空的
});
