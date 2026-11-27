import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';

const src = new URL('../../src/', import.meta.url);
const read = file => readFileSync(new URL(file, src), 'utf8');
const css = file => read(file).replace(/\/\*[\s\S]*?\*\//g, '');

test('ui.css leaves page fill layout to shared classes', () => {
  assert.doesNotMatch(css('ui.css'), /\.(?:process-page|inventory-page|notices-page)(?![\w-])/);
});

test('page-layout.css owns BoundedGrid styles and loads immediately after ui.css', () => {
  const boundedGrid = /\.bounded-grid(?![\w-])/;
  assert.doesNotMatch(css('business-modal.css'), boundedGrid);
  assert.match(css('page-layout.css'), boundedGrid);

  const imports = [...css('styles.css').matchAll(/@import\s+['"]([^'"]+)['"]/g)].map(match => match[1]);
  const layout = imports.indexOf('./page-layout.css');
  assert.ok(layout > 0 && imports[layout - 1] === './ui.css');
  assert.ok(imports.indexOf('./business-modal.css') > layout);
});

function assertPageShell(source, label) {
  const root = source.match(/<(?:div|section|main|article)\b[^<>]*\bdata-page-layout=("\w+"|\{\w+\})[^<>]*>/)?.[0];
  assert.ok(root, `${label} must declare data-page-layout`);
  assert.match(root, /\bclassName=(?:"|\{`)[^"`]*\bpage-shell\s/, label);

  const literal = root.match(/\bdata-page-layout="(\w+)"/)?.[1];
  if (literal) {
    assert.match(literal, /^(?:flow|fill|split)$/, label);
    assert.match(root, new RegExp(`\\bpage-shell--${literal}(?![\\w-])`), label);
    return;
  }

  const mode = root.match(/\bdata-page-layout=\{(\w+)\}/)[1];
  assert.ok(root.includes(`page-shell--\${${mode}}`), `${label} must use the same mode in class and attribute`);
  assert.match(source, new RegExp(`\\bconst ${mode} = [^;]+\\? '(?:flow|fill|split)' : '(?:flow|fill|split)';`), label);
}

test('registered pages and the catch-all explicitly declare their page layout', () => {
  const main = read('main.tsx');
  const registry = main.match(/^const pages:.*= \[\r?\n([\s\S]*?)^\];/m)?.[1];
  assert.ok(registry, 'Could not locate the page registry');
  const entries = [...registry.matchAll(/^\s*\{ path: '([^']+)'.*component: (.*) \},$/gm)];
  assert.equal(entries.length, [...registry.matchAll(/\bpath:/g)].length);
  assert.ok(entries.length > 0);

  const entryWrappers = {
    HomeEntry: ['home', 'HomePage'],
    NoticeEntry: ['notices', 'NoticesPage'],
  };
  for (const [, route, component] of entries) {
    const lazy = component.match(/import\('\.\/([^']+)'\).*default: module\.(\w+)/);
    const target = lazy ? lazy.slice(1) : entryWrappers[component];
    assert.ok(target, `Could not resolve the registered component for ${route}`);
    const [module, name] = target;
    const source = read(`${module}.tsx`);
    const start = source.indexOf(`export function ${name}(`);
    assert.notEqual(start, -1, `Could not locate ${name} for ${route}`);
    const definition = source.slice(start).split(/\r?\n(?:export )?function \w+\(/)[0];
    assertPageShell(definition, `${route} (${name})`);
  }

  const fallback = main.match(/<Route path="\*"[\s\S]*?\/\s*>/)?.[0];
  assert.ok(fallback?.includes('className="page-view"'), 'The catch-all must use page-view spacing');
  assertPageShell(fallback, 'catch-all route');
});

test('bounded page tables use BoundedGrid and keep scrolling inside the grid', () => {
  const tables = {
    'rules.tsx': ['exclusion-rules'],
    'jc-rules.tsx': ['jc-ignore-rules'],
    'users.tsx': ['users'],
    'i8.tsx': ['i8-records'],
    'oilcard-openings.tsx': ['oilcard-openings'],
    'oilcard.tsx': ['oilcard-assignments'],
    'mechanical-work.tsx': ['mechanical-reconciliation', 'mechanical-unmapped'],
  };
  for (const [file, keys] of Object.entries(tables)) {
    const grids = [...read(file).matchAll(/<([A-Z]\w*)\b[^<>]*?\btable="([^"]+)"/g)];
    for (const key of keys) {
      const renderers = grids.filter(match => match[2] === key).map(match => match[1]);
      assert.deepEqual(renderers, ['BoundedGrid'], `${file}: ${key} must use BoundedGrid`);
    }
  }

  const wrapper = /(?:\.(?:rules-table|users-table|i8-records|oilcard-openings|oilcard-assignment-history|mechanical-work-table)|#oilcard-opening-details)(?![\w-])/;
  for (const file of readdirSync(src).filter(name => name.endsWith('.css'))) {
    for (const [, selector, declarations] of css(file).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      if (!wrapper.test(selector)) continue;
      assert.doesNotMatch(declarations, /\b(?:max-height|max-block-size)\s*:|\boverflow(?:-y|-block)?\s*:\s*(?:auto|scroll)\b/, `${file}: ${selector.trim()} caps or scrolls the outer table`);
    }
  }
});

test('process matrices use the page height budget without subtracting assumed chrome', () => {
  assert.doesNotMatch(css('process.css'), /100dvh\s*-\s*104px/);
});

test('split panes stack when the content container reaches 780px', () => {
  const layout = css('page-layout.css');
  assert.match(layout, /\.page-shell--split\s*\{[^{}]*container-type:\s*inline-size/);
  assert.match(layout, /@container\s*\(\s*max-width:\s*780px\s*\)\s*\{\s*\.page-split-panels\s+\.wb-split-grid\s*\{[^{}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/);
});

test('native table markup opts into sticky column headers', () => {
  const tableCounts = new Map([
    ['equipment-dialogs.tsx', 1],
    ['history-details.tsx', 1],
    ['oilcard-receive-detail.tsx', 2],
  ]);
  for (const file of readdirSync(src).filter(name => name.endsWith('.tsx'))) {
    const tables = [...read(file).matchAll(/<table\b[^>]*>/g)];
    assert.equal(tables.length, tableCounts.get(file) ?? 0, file);
    for (const [tag] of tables) assert.match(tag, /\bclassName="[^"]*\bwb-native-table\b/, file);
  }
  assert.match(css('style.css'), /\.wb-native-table thead th\s*\{[^{}]*position:\s*sticky/);
});
