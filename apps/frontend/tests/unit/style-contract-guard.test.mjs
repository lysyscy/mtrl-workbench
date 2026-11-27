import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';

const src = new URL('../../src/', import.meta.url);
const files = readdirSync(src, { recursive: true }).map(file => file.replaceAll('\\', '/')).sort();
const read = file => readFileSync(new URL(file, src), 'utf8');
const css = file => read(file).replace(/\/\*[\s\S]*?\*\//g, '');
const sheets = files.filter(file => file.endsWith('.css'));
const rules = file => [...css(file).matchAll(/([^{}]+)\{([^{}]*)\}/g)];

test('style contract: colors are supplied by theme variables', () => {
  const literals = /#[\da-f]{3,8}(?![\w-])|(?<![\w-])(?:rgba?\s*\(|white(?![\w-]))/gi;
  const hits = [];
  for (const file of sheets) {
    for (const [rule, , declarations] of rules(file)) {
      for (const _ of declarations.matchAll(literals)) hits.push([file, rule.trim()]);
    }
  }

  // PR-W4: remove both exceptions when these oilcard declarations use theme roles.
  assert.deepEqual(hits, [
    ['oilcard.css', '.oilcard-preview-stage { flex: 1 1 auto; min-height: calc(240px * var(--fscale)); height: min(72dvh, 850px); overflow: auto; overscroll-behavior: contain; padding: 12px; background: var(--surface-soft, #eef2f1); }'],
    ['oilcard.css', '.oilcard-preview-page canvas { display: block; width: 100%; height: auto; background: white; }'],
  ]);
});

test('style contract: sections and sticky table headers require explicit classes', () => {
  for (const file of ['style.css', 'ui-theme.css']) {
    for (const [, selectors, declarations] of rules(file)) {
      for (const selector of selectors.split(',').map(value => value.trim())) {
        assert.doesNotMatch(selector, /(?:^|[\s>+~])section$/, file + ' styles an unclassed section');
        if (/(?:^|\s)th$/.test(selector) && /\bposition\s*:\s*sticky\b/.test(declarations)) {
          assert.equal(selector, '.wb-native-table thead th');
        }
      }
    }
  }
});

test('style contract: domain classes have one owner', () => {
  const owners = {
    'contract-selection': [],
    'contract-inline-editor': ['contract-subtables.css'],
    'flow-revoke': ['business-modal.css'],
    'jc-bulk-selection': ['contracts.css'],
    'notice-contract-summary': ['notice-contract.css'],
  };
  for (const [className, expected] of Object.entries(owners)) {
    const selector = new RegExp('\\.' + className + '(?![\\w-])');
    assert.deepEqual(sheets.filter(file => rules(file).some(([, names]) => selector.test(names))), expected, className);
  }
});

test('style contract: styles.css loads every component sheet and only main imports CSS', () => {
  const imports = [...css('styles.css').matchAll(/@import\s+['"]([^'"]+)['"]/g)].map(match => match[1]);
  assert.deepEqual(imports.sort(), sheets.filter(file => file !== 'styles.css').map(file => './' + file));

  const componentImports = [];
  for (const file of files.filter(name => /\.tsx?$/.test(name))) {
    for (const [, path] of read(file).matchAll(/\b(?:from\s+|import\s*(?:\(\s*)?)['"]([^'"]+\.css(?:\?[^'"]*)?)['"]/g)) {
      componentImports.push([file, path]);
    }
  }
  assert.deepEqual(componentImports, [['main.tsx', './styles.css']]);
});
