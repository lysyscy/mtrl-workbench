import test from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

// Exercise the browser export used by Vite, rather than uuid's node:crypto export.
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    return nextResolve(specifier, specifier === 'uuid'
      ? { ...context, conditions: context.conditions.filter(condition => condition !== 'node') }
      : context);
  },
});
let randomUUID, deviceId, resetBrowserRelay;
try {
  ({ randomUUID } = await import('../../src/random-id.ts'));
  ({ deviceId, resetBrowserRelay } = await import('../../src/i8-browser-relay.ts'));
}
finally { hook.deregister(); }
const nativeCrypto = globalThis.crypto;
const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

test('browser relay device ID works on LAN HTTP without native randomUUID', t => {
  t.mock.getter(globalThis, 'crypto', () => ({getRandomValues: array => nativeCrypto.getRandomValues(array)}));
  resetBrowserRelay();
  const id = deviceId();
  assert.match(id.slice(4), uuidV4);
  assert.equal(deviceId(), id);
  resetBrowserRelay();
  assert.notEqual(deviceId(), id);
});

test('LAN HTTP capability set retains cryptographically random v4 IDs without randomUUID', t => {
  let calls = 0;
  t.mock.getter(globalThis, 'crypto', () => ({
    getRandomValues(array) { calls++; return nativeCrypto.getRandomValues(array); },
  }));
  t.mock.method(Math, 'random', () => { throw new Error('Weak randomness must not be used'); });
  const ids = Array.from({ length: 100 }, () => randomUUID());
  for (const id of ids) assert.match(id, uuidV4);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(calls, ids.length);
});

test('native randomUUID remains available when the browser exposes it', t => {
  const expected = 'e7f97665-e61b-4329-a51e-c3abb048b904';
  let calls = 0;
  t.mock.getter(globalThis, 'crypto', () => ({ randomUUID() { calls++; return expected; } }));
  assert.equal(randomUUID(), expected);
  assert.equal(calls, 1);
});

test('missing secure randomness fails without generating a weak request ID', t => {
  t.mock.getter(globalThis, 'crypto', () => ({}));
  t.mock.method(Math, 'random', () => { throw new Error('Weak randomness must not be used'); });
  assert.throws(() => randomUUID(), /getRandomValues/);
});
