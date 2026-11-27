import assert from 'node:assert/strict';
import test from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AppearanceChoices } from '../../src/appearance-preferences.tsx';

const scales = [
  { key: 'standard', label: '标准', css: '1' },
  { key: 'large', label: '大一点', css: '1.12' },
  { key: 'larger', label: '更大', css: '1.25' },
  { key: 'largest', label: '最大', css: '1.4' },
];
const pine = { name: '松绿', label: '松绿', description: '松绿界面', scene: '', vars: {} };
const mist = { name: '浅雾', label: '浅雾', description: '浅雾界面', scene: '', vars: {} };

function render(palette, theme, { unavailable = false } = {}) {
  return renderToStaticMarkup(createElement(AppearanceChoices, {
    options: { themes: palette.map(item => item.name), palette, theme, scales, ui_scale: 'larger' },
    unavailable,
    onChange: () => assert.fail('Rendering must not change preferences'),
  }));
}

test('single theme offers four size choices first and a read-only current theme', () => {
  const html = render([pine], '松绿');
  assert.ok(html.indexOf('界面大小') < html.indexOf('当前主题：精工深墨松绿'));
  assert.doesNotMatch(html, /aria-label="配色主题"/);
  assert.equal([...html.matchAll(/role="radio"/g)].length, 4);
  for (const {key, label, css} of scales) {
    assert.ok(html.includes(`aria-label="${label}字号" aria-checked="${key === 'larger'}"`));
    assert.ok(html.includes(`>${css === '1' ? '1.0' : css}×</small>`));
  }
  assert.match(html, /<span class="appearance-control-sample" aria-hidden="true">查看明细<\/span>/);
});

test('multiple themes retain the choice group and mark the current theme', () => {
  const html = render([pine, mist], '浅雾', { unavailable: true });
  assert.match(html, /role="radiogroup" aria-label="配色主题"/);
  assert.doesNotMatch(html, /当前主题：/);
  assert.match(html, /aria-label="松绿主题" aria-checked="false" aria-disabled="true"/);
  assert.match(html, /aria-label="浅雾主题" aria-checked="true" aria-disabled="true"/);
  assert.match(html, /aria-label="更大字号" aria-checked="true" aria-disabled="true"/);
});
