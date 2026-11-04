import test from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';

import { ReadPlaceholder, readPhase } from '../../src/read-region.tsx';

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
