import assert from 'node:assert/strict';
import test from 'node:test';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { HomePage } from '../../src/home.tsx';
import { noticeTodosKey } from '../../src/notice-todos';

function render(counts) {
  const client = new QueryClient();
  if (counts != null) client.setQueryData(noticeTodosKey, { notice_count: 9, ...counts });
  return renderToStaticMarkup(createElement(QueryClientProvider, { client },
    createElement(MemoryRouter, null, createElement(HomePage, { active: true, blocked: false }))));
}

test('unknown counts render three neutral cards and leave the number slots empty', () => {
  const html = render(null);
  assert.equal([...html.matchAll(/data-tone="neutral"/g)].length, 3);
  assert.equal([...html.matchAll(/home-tile-count-reading/g)].length, 3);
  assert.equal([...html.matchAll(/待读取/g)].length, 3);
  assert.doesNotMatch(html, /无待办|data-tone="(?:pending|negative)"/);
});

test('zero renders a neutral complete count beside outstanding and risk counts', () => {
  const html = render({ ownership: 0, jc: 2, void: 1 });
  const tones = [...html.matchAll(/<div class="home-tile(?: home-clear)?" data-tone="([^"]+)">/g)];
  assert.deepEqual(tones.map(([, tone]) => tone), ['neutral', 'pending', 'negative']);
  assert.match(html, /home-tile-count">0<\/p>.*无待办/);
  assert.match(html, /home-tile-count">2<\/p>.*待处理/);
  assert.match(html, /home-tile-count">1<\/p>.*需核对/);
});
