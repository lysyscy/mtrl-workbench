import assert from 'node:assert/strict';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { ApiError, beginIdentityVerification } from '../../src/api.ts';
import {
  bindBrowserIdentity,
  connectBrowser,
  deviceId,
  readBrowserIdentity,
  relayConnectionWanted,
  resetBrowserRelay,
  runBrowserRelay,
  setRelayConnectionWanted,
} from '../../src/i8-browser-relay.ts';
import { maintainBrowserRelay } from '../../src/i8-relay-recovery.ts';

const identity = { origin: 'https://i8.example.test' };
const state = {
  connected: true,
  mode: 'browser',
  ...identity,
  i8_user: 'tester',
  expected_org: 'org',
  expected_org_code: '001',
  expected_org_name: '示例组织',
  generation: 1,
  message: '',
};
const ticket = {
  ticket: 't-1',
  generation: 1,
  method: 'POST',
  url: `${identity.origin}/example`,
  headers: {},
  body_b64: '',
  timeout_ms: 200,
};

const browserDeps = {
  read: readBrowserIdentity,
  connect: connectBrowser,
  bind: bindBrowserIdentity,
  run: runBrowserRelay,
};
const never = () => assert.fail('不应执行这一步');

function browser(t, onMessage, onFetch) {
  const entries = new Map();
  const keys = ['sessionStorage', 'chrome', 'fetch'];
  const descriptors = keys.map(key => Object.getOwnPropertyDescriptor(globalThis, key));
  Object.defineProperties(globalThis, {
    sessionStorage: {
      configurable: true,
      value: {
        getItem: key => entries.get(key) ?? null,
        setItem: (key, value) => entries.set(key, String(value)),
        removeItem: key => entries.delete(key),
      },
    },
    chrome: {
      configurable: true,
      value: { runtime: { sendMessage: (_id, message, callback) => callback(onMessage(message)) } },
    },
    fetch: { configurable: true, value: onFetch },
  });
  resetBrowserRelay();
  t.after(() => {
    resetBrowserRelay();
    keys.forEach((key, index) => {
      const descriptor = descriptors[index];
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    });
  });
  return entries;
}

test('连接意图随当前账号跨刷新保留，设备号仅存在于当前页面，手动断开后清除意图', t => {
  const stored = browser(t, never, never);
  const owner = '1:alice';
  const firstDevice = deviceId();
  assert.equal(relayConnectionWanted(owner), false);
  setRelayConnectionWanted(owner, true);
  assert.deepEqual([...stored.values()], ['yes']);
  resetBrowserRelay();
  assert.notEqual(deviceId(), firstDevice);
  assert.equal(relayConnectionWanted(owner), true);
  assert.equal(relayConnectionWanted('2:bob'), false);
  setRelayConnectionWanted(owner, false);
  resetBrowserRelay();
  assert.equal(relayConnectionWanted(owner), false);
  assert.equal(stored.size, 0);
});

for (const failure of ['reconnect', 'network', 'extension-unavailable']) {
  test(`新页面读站点、连接、绑定后取票，${failure} 恢复时旧业务票只执行一次`, async t => {
    const controller = new AbortController();
    const steps = [];
    const updates = [];
    let generation = 0;
    let firstPoll = true;
    browser(t, message => {
      assert.equal(message.device_id, deviceId());
      steps.push(message.type);
      if (message.type === 'i8-relay:identity') return { ok: true, ...identity };
      if (message.type === 'i8-relay:bind') {
        assert.equal(message.generation, generation);
        assert.deepEqual(message.identity, identity);
        return { ok: true };
      }
      assert.equal(message.type, 'i8-relay:execute');
      assert.deepEqual(message.request, ticket);
      if (failure === 'extension-unavailable') {
        globalThis.chrome.runtime.lastError = { message: 'extension unavailable' };
      }
      return { status: 200, headers: {}, body_b64: '', declared_length: 0 };
    }, async (path, init) => {
      const endpoint = path.split('?')[0];
      steps.push(endpoint);
      switch (endpoint) {
        case '/api/m02/browser/connect':
          assert.deepEqual(JSON.parse(init.body), { device_id: deviceId(), i8_origin: identity.origin });
          return Response.json({ ...state, generation: ++generation });
        case '/api/m02/browser/pending':
          assert.equal(new URL(path, 'https://workbench.example.test').searchParams.get('device_id'), deviceId());
          if (generation === 2) {
            controller.abort();
            return Response.json({ request: null });
          }
          if (firstPoll) {
            firstPoll = false;
            return Response.json({ request: ticket });
          }
          return Response.json({ code: 'i8_browser_relay_unavailable' }, { status: 409 });
        case '/api/m02/browser/complete': {
          delete globalThis.chrome.runtime.lastError;
          const reply = JSON.parse(init.body);
          assert.equal(reply.ticket, ticket.ticket);
          assert.equal(reply.status, failure === 'extension-unavailable' ? 599 : 200);
          if (failure === 'network') throw new TypeError('fetch failed');
          return Response.json({ accepted: true });
        }
        default:
          return never();
      }
    });

    await maintainBrowserRelay(controller.signal, update => updates.push(update), {
      ...browserDeps,
      wait: async () => { steps.push('wait'); },
    });
    assert.deepEqual(steps, [
      'i8-relay:identity', '/api/m02/browser/connect', 'i8-relay:bind', '/api/m02/browser/pending',
      'i8-relay:execute', '/api/m02/browser/complete',
      ...(failure === 'reconnect' ? ['/api/m02/browser/pending'] : []),
      'wait', 'i8-relay:identity', '/api/m02/browser/connect', 'i8-relay:bind', '/api/m02/browser/pending',
    ]);
    assert.deepEqual(updates.map(update => update.phase), ['connecting', 'connected', 'retrying', 'connecting', 'connected']);
    assert.deepEqual(updates.flatMap(update => update.state ? [update.state.generation] : []), [1, 2]);
  });
}

test('连接接口返回畸形状态时停止，不绑定、不轮询、不重试', async t => {
  const phases = [];
  browser(t, message => {
    assert.equal(message.type, 'i8-relay:identity');
    return { ok: true, ...identity };
  }, async path => {
    assert.equal(path, '/api/m02/browser/connect');
    return Response.json({ ...state, generation: 'invalid' });
  });

  await maintainBrowserRelay(new AbortController().signal, ({ phase }) => phases.push(phase), {
    ...browserDeps,
    wait: never,
  });
  assert.deepEqual(phases, ['connecting', 'stopped']);
});

test('连接接口报告未配置或未绑定时停止，等待用户处理', async t => {
  const updates = [];
  const message = '请先配置并绑定 i8 站点。';
  browser(t, request => {
    assert.equal(request.type, 'i8-relay:identity');
    return { ok: true, ...identity };
  }, async path => {
    assert.equal(path, '/api/m02/browser/connect');
    return Response.json({ code: 'i8_browser_relay_unavailable', message }, { status: 400 });
  });

  await maintainBrowserRelay(new AbortController().signal, update => updates.push(update), {
    ...browserDeps,
    wait: never,
  });
  assert.deepEqual(updates.map(update => update.phase), ['connecting', 'stopped']);
  assert.equal(updates.at(-1).message, message);
});

for (const [name, response, reason] of [
  ['无法解析的 JSON', () => new Response('<html>unavailable</html>', { status: 502 }), 'malformed'],
  ['真实 403', () => Response.json({}, { status: 403 }), 'failed'],
]) {
  test(`轮询收到${name}时停止`, async t => {
    let polls = 0;
    const stops = [];
    browser(t, never, async path => {
      assert.equal(path.split('?')[0], '/api/m02/browser/pending');
      polls += 1;
      return response();
    });

    await runBrowserRelay({ onStop: reason => stops.push(reason) });
    assert.equal(polls, 1);
    assert.deepEqual(stops, [reason]);
  });
}

for (const blockedPhase of ['connecting', 'connected']) {
  test(`${blockedPhase} 时身份暂未核实，核验恢复后继续建立连接`, async t => {
    const controller = new AbortController();
    const sent = [];
    const phases = [];
    browser(t, message => {
      if (message.type === 'i8-relay:identity') return { ok: true, ...identity };
      assert.equal(message.type, 'i8-relay:bind');
      return { ok: true };
    }, async path => {
      const endpoint = path.split('?')[0];
      sent.push(endpoint);
      if (endpoint === '/api/m02/browser/connect') return Response.json(state);
      assert.equal(endpoint, '/api/m02/browser/pending');
      controller.abort();
      return Response.json({ request: null });
    });
    const refreshVerification = () => beginIdentityVerification()();
    t.after(refreshVerification);

    await maintainBrowserRelay(controller.signal, ({ phase }) => {
      if (phase === blockedPhase && !phases.includes(phase)) {
        beginIdentityVerification()('身份核验暂未完成。');
      }
      phases.push(phase);
    }, {
      ...browserDeps,
      wait: async () => { refreshVerification(); },
    });
    const connectedBeforeRetry = blockedPhase === 'connected';
    assert.deepEqual(phases, [
      'connecting', ...(connectedBeforeRetry ? ['connected'] : []), 'retrying', 'connecting', 'connected',
    ]);
    assert.deepEqual(sent, [
      ...(connectedBeforeRetry ? ['/api/m02/browser/connect'] : []),
      '/api/m02/browser/connect', '/api/m02/browser/pending',
    ]);
  });
}

test('身份核验期间取消后，核验完成也不会发送旧业务票的回帖', async t => {
  const controller = new AbortController();
  const sent = [];
  const phases = [];
  let finishVerification;
  browser(t, message => {
    if (message.type === 'i8-relay:identity') return { ok: true, ...identity };
    if (message.type === 'i8-relay:bind') return { ok: true };
    assert.equal(message.type, 'i8-relay:execute');
    assert.deepEqual(message.request, ticket);
    finishVerification = beginIdentityVerification();
    return { status: 200, headers: {}, body_b64: '', declared_length: 0 };
  }, async path => {
    const endpoint = path.split('?')[0];
    sent.push(endpoint);
    if (endpoint === '/api/m02/browser/connect') return Response.json(state);
    if (endpoint === '/api/m02/browser/pending') return Response.json({ request: ticket });
    return Response.json({ accepted: true });
  });

  const lifecycle = maintainBrowserRelay(controller.signal, ({ phase }) => phases.push(phase), {
    ...browserDeps,
    wait: never,
  });
  try {
    // 让扩展回执后的异步续体先进入身份核验门，再取消本轮。
    await setImmediate();
    assert.equal(typeof finishVerification, 'function');
    assert.deepEqual(sent, ['/api/m02/browser/connect', '/api/m02/browser/pending']);
  } finally {
    controller.abort();
    finishVerification?.();
    await lifecycle;
  }
  assert.deepEqual(sent, ['/api/m02/browser/connect', '/api/m02/browser/pending']);
  assert.deepEqual(phases, ['connecting', 'connected']);
});

test('握手响应迟到时，已取消的页面不绑定也不轮询', async () => {
  const controller = new AbortController();
  const phases = [];
  const connecting = Promise.withResolvers();
  const response = Promise.withResolvers();
  const lifecycle = maintainBrowserRelay(controller.signal, ({ phase }) => phases.push(phase), {
    read: async () => identity,
    connect: async (_identity, signal) => {
      assert.equal(signal, controller.signal);
      connecting.resolve();
      return response.promise;
    },
    bind: never,
    run: never,
    wait: never,
  });
  await connecting.promise;
  controller.abort();
  response.resolve(state);
  await lifecycle;
  assert.deepEqual(phases, ['connecting']);
});

test('网络故障的退避上限为 30 秒，退避中取消后不再发起连接', async () => {
  const controller = new AbortController();
  const delays = [];
  const phases = [];
  await maintainBrowserRelay(controller.signal, ({ phase }) => phases.push(phase), {
    read: async () => identity,
    connect: async () => { throw new ApiError('网络暂时中断'); },
    bind: never,
    run: never,
    wait: async (ms, signal) => {
      assert.equal(signal, controller.signal);
      delays.push(ms);
      if (delays.length === 7) controller.abort();
    },
  });
  assert.deepEqual(delays, [1000, 2000, 4000, 8000, 16000, 30000, 30000]);
  assert.deepEqual(phases, delays.flatMap(() => ['connecting', 'retrying']));
});
