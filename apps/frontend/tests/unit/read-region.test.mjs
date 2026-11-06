import test from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { registerHooks } from 'node:module';

// read-region.tsx owns its presentation file and imports it, so every page that renders a region
// loads the same styles. tsx does not transform CSS, so this test stubs the import to an empty
// module; the assertions below stay about behaviour, never about stylesheet contents.
// The same run has no bundler for the AntD entry point, so its button is stubbed to the text it
// was given: the assertions below are about which words each region says, not about AntD.
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.endsWith('.css')) return { url: 'data:text/javascript,export default {}', shortCircuit: true };
    if (specifier === 'antd/es/button') {
      return { url: 'data:text/javascript,export%20default%20function%20Button(p)%7Breturn%20p.children%7D', shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
});

const { ReadFailure, ReadPlaceholder, ReadStatusLane, readPhase } = await import('../../src/read-region.tsx');

const read = (value) => ({
  isPending: false,
  isFetching: false,
  isError: false,
  error: null,
  data: undefined,
  refetch: () => {},
  ...value,
});

test('a read that is not permitted yet announces nothing', () => {
  assert.equal(readPhase(read({ isPending: true })), 'idle');
});

test('a first read in flight is loading, not an empty result', () => {
  assert.equal(readPhase(read({ isPending: true, isFetching: true })), 'reading');
  assert.equal(readPhase(read({ isPending: true, isFetching: true }), true), 'reading');
});

test('a result on screen separates rows from no rows', () => {
  assert.equal(readPhase(read({ data: [{}, {}] })), 'ready');
  assert.equal(readPhase(read({ data: [] }), true), 'empty');
  assert.equal(readPhase(read({ data: [] })), 'ready');
});

test('a failure with nothing on screen is an error, not an empty table', () => {
  const failed = read({ isError: true, error: new Error('欠款读取不完整，请重试。') });
  assert.equal(readPhase(failed), 'error');
  assert.equal(readPhase(failed, true), 'error');
});

test('a failure after a result keeps the result and reports it as stale', () => {
  assert.equal(readPhase(read({ isError: true, error: new Error('连接失败'), data: [{}] })), 'stale');
  assert.equal(readPhase(read({ isError: true, error: new Error('连接失败'), data: [] }), true), 'stale');
});

test('a waiting region announces itself to screen readers as decorative space only', () => {
  const markup = renderToStaticMarkup(ReadPlaceholder({ rows: 6 }));
  assert.match(markup, /aria-hidden="true"/u);
});

test('a waiting region carries no amount, count or percentage', () => {
  // The region must not invent business values while it waits. How many neutral rows it uses is
  // an implementation detail, so this checks content rather than a row count.
  const markup = renderToStaticMarkup(ReadPlaceholder({ rows: 6 }));
  assert.doesNotMatch(markup, /[0-9,.%¥]/u, markup);
});

test('a region that failed before showing anything keeps its space without looking busy', () => {
  const waiting = renderToStaticMarkup(ReadPlaceholder({ rows: 6 }));
  const quiet = renderToStaticMarkup(ReadPlaceholder({ rows: 6, quiet: true }));
  assert.match(quiet, /read-placeholder-quiet/u);
  assert.doesNotMatch(waiting, /read-placeholder-quiet/u);
  assert.match(quiet, /aria-hidden="true"/u);
});

test('a lane is present in every state and only speaks while it is reading', () => {
  const idle = renderToStaticMarkup(ReadStatusLane({ phase: 'idle' }));
  const reading = renderToStaticMarkup(ReadStatusLane({ phase: 'reading', announce: '正在读取付款流水…' }));
  const ready = renderToStaticMarkup(ReadStatusLane({ phase: 'ready' }));
  // Keep the status wrapper in the markup even when it takes no space.
  for (const markup of [idle, reading, ready]) assert.match(markup, /class="read-status"/u);
  assert.match(idle, /data-read-phase="idle"/u);
  assert.match(reading, /data-read-phase="reading"/u);
  // Only a running read announces; a settled or idle lane says nothing at all.
  assert.match(reading, /role="status"/u);
  assert.doesNotMatch(idle, /role="status"/u);
  assert.doesNotMatch(ready, /role="status"/u);
});

test('two failed reads in one lane stay apart, each naming itself and retrying itself', () => {
  const own = renderToStaticMarkup(ReadFailure({
    read: read({ isError: true, error: new Error('库存读取不完整。'), data: [] }),
    retained: '读取更新失败，保留上次读取的内容。',
  }));
  const secondary = renderToStaticMarkup(ReadFailure({
    read: read({ isError: true, error: new Error('项目读取不完整。') }),
    retained: '项目清单更新未成功，保留上次结果。',
    label: '项目清单',
  }));
  // Each failure carries its own error text and its own retry, so a reader can tell them apart.
  assert.match(own, /库存读取不完整。/u);
  assert.match(secondary, /项目清单：/u);
  assert.match(secondary, /项目读取不完整。/u);
  assert.match(own, /重试读取/u);
  assert.match(secondary, /重试读取/u);
});
