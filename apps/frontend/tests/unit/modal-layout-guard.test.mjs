import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  allocateBoundedHeights,
  boundedGridMinHeight,
  estimateBoundedGridHeight,
} from '../../src/bounded-grid-layout.ts';

const srcDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../src');

function readSrcFiles(ext) {
  return fs.readdirSync(srcDir)
    .filter(name => name.endsWith(ext))
    .sort()
    .map(name => ({ name, text: fs.readFileSync(path.join(srcDir, name), 'utf8') }));
}

function stripCssComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

test('bounded-grid-layout: estimates and minimum floors scale cleanly', () => {
  const short = estimateBoundedGridHeight({ rowCount: 2, pinnedBottomCount: 1, scale: 1 });
  const taller = estimateBoundedGridHeight({ rowCount: 2, pinnedBottomCount: 1, scale: 1.12 });
  const withScroll = estimateBoundedGridHeight({ rowCount: 2, pinnedBottomCount: 1, scale: 1, hasHorizontalScroll: true });
  assert.ok(taller > short);
  assert.ok(withScroll > short);

  const floorShort = boundedGridMinHeight({ minRows: 4, rowCount: 2, pinnedBottomCount: 1, scale: 1 });
  const floorLong = boundedGridMinHeight({ minRows: 4, rowCount: 20, pinnedBottomCount: 1, scale: 1 });
  assert.equal(floorShort, short);
  assert.ok(floorLong > floorShort);
  assert.equal(floorLong, estimateBoundedGridHeight({ rowCount: 4, pinnedBottomCount: 1, scale: 1 }));
});

test('allocateBoundedHeights: hugs short tables, yields surplus, splits 65:35, and preserves floors on tight viewports', () => {
  // Both short -> exact natural heights without empty stretch.
  assert.deepEqual(
    allocateBoundedHeights(600, [
      { id: 'payment', naturalHeight: 200, minHeight: 240, weight: 65 },
      { id: 'terms', naturalHeight: 150, minHeight: 140, weight: 35 },
    ]),
    { payment: 200, terms: 150 },
  );

  // Short payment + long terms -> payment hugs natural height and gives surplus to terms.
  assert.deepEqual(
    allocateBoundedHeights(600, [
      { id: 'payment', naturalHeight: 180, minHeight: 240, weight: 65 },
      { id: 'terms', naturalHeight: 800, minHeight: 140, weight: 35 },
    ]),
    { payment: 180, terms: 420 },
  );

  // Long payment + short terms -> terms hugs natural height and gives surplus to payment.
  assert.deepEqual(
    allocateBoundedHeights(600, [
      { id: 'payment', naturalHeight: 900, minHeight: 240, weight: 65 },
      { id: 'terms', naturalHeight: 120, minHeight: 140, weight: 35 },
    ]),
    { payment: 480, terms: 120 },
  );

  // Both long -> 65:35 split and sum never exceeds budget.
  const split = allocateBoundedHeights(600, [
    { id: 'payment', naturalHeight: 900, minHeight: 240, weight: 65 },
    { id: 'terms', naturalHeight: 800, minHeight: 140, weight: 35 },
  ]);
  assert.equal(split.payment, 390);
  assert.equal(split.terms, 210);
  assert.ok(split.payment + split.terms <= 600);

  // Tight viewport where 35% would dip below terms floor -> terms holds floor, payment takes remainder.
  const floorBound = allocateBoundedHeights(400, [
    { id: 'payment', naturalHeight: 900, minHeight: 240, weight: 65 },
    { id: 'terms', naturalHeight: 800, minHeight: 160, weight: 35 },
  ]);
  assert.equal(floorBound.terms, 160);
  assert.equal(floorBound.payment, 240);

  // Ultra-short viewport -> both keep readable floors so outer modal fallback scroll engages.
  assert.deepEqual(
    allocateBoundedHeights(300, [
      { id: 'payment', naturalHeight: 900, minHeight: 240, weight: 65 },
      { id: 'terms', naturalHeight: 800, minHeight: 160, weight: 35 },
    ]),
    { payment: 240, terms: 160 },
  );
});

test('static guard: modal TSX files never use ReadGrid(domLayout="autoHeight") inside modals', () => {
  const modalSubcomponentFiles = new Set([
    'notice-payment-grid.tsx',
    'payment-terms.tsx',
    'contract-subtables.tsx',
    'notice-contract.tsx',
    'notice-flows.tsx',
    'notice-auto-link.tsx',
    'notice-print.tsx',
    'contract-tools.tsx',
    'notice-payment.tsx',
  ]);
  const violations = [];

  for (const { name, text } of readSrcFiles('.tsx')) {
    if (modalSubcomponentFiles.has(name)) {
      for (const match of text.matchAll(/<ReadGrid\b[^>]*domLayout\s*=\s*["'{]\s*autoHeight/g)) {
        const line = text.slice(0, match.index).split('\n').length;
        violations.push(`${name}:${line} uses ReadGrid domLayout="autoHeight" inside modal component`);
      }
      continue;
    }

    // For mixed files containing both page views and modals (e.g. ledger-controls, mechanical-work),
    // inspect every <BusinessModal> and <MechanicalDialog> block as well as helper components used only inside modals.
    for (const block of text.matchAll(/<(BusinessModal|MechanicalDialog)\b[\s\S]*?<\/\1>/g)) {
      const inner = block[0];
      for (const match of inner.matchAll(/<ReadGrid\b[^>]*domLayout\s*=\s*["'{]\s*autoHeight/g)) {
        const line = text.slice(0, block.index + match.index).split('\n').length;
        violations.push(`${name}:${line} uses ReadGrid domLayout="autoHeight" inside <${block[1]}>`);
      }
    }
  }

  // Also check mechanical-work Sources helper which renders inside the discovery modal.
  const mechWork = fs.readFileSync(path.join(srcDir, 'mechanical-work.tsx'), 'utf8');
  const sourcesFn = mechWork.match(/function Sources\b[\s\S]*?\n\}/);
  if (sourcesFn && /<ReadGrid\b[^>]*domLayout\s*=\s*["'{]\s*autoHeight/.test(sourcesFn[0])) {
    violations.push('mechanical-work.tsx:Sources uses ReadGrid domLayout="autoHeight" inside discovery modal');
  }

  assert.deepEqual(violations, [], `Found forbidden autoHeight ReadGrid inside modals:\n${violations.join('\n')}`);
});

test('static guard: no business CSS bypasses business-modal.css to alter .ant-modal-body or sticky modal chrome', () => {
  const violations = [];
  const forbiddenModalTableOuterScroll = [
    '.notice-pay-table',
    '.payment-terms-table',
    '.notice-flows-table',
    '.notice-result-grid',
    '.notice-print-list',
    '.contract-settings-table',
    '.export-table',
  ];

  for (const { name, text } of readSrcFiles('.css')) {
    if (name === 'business-modal.css') continue;
    const clean = stripCssComments(text);

    for (const match of clean.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const selector = match[1].trim();
      const body = match[2];

      if (/\.ant-modal-body\b/.test(selector)) {
        violations.push(`${name}: selector "${selector}" bypasses business-modal.css by targeting .ant-modal-body`);
      }

      if (/(?:\.dialog-close-heading|\.dialog-actions|\.(?:mechanical-dialog|contract-footer|inventory-actions)\b)/.test(selector)
        && /position\s*:\s*sticky\b/.test(body)) {
        violations.push(`${name}: selector "${selector}" uses position:sticky instead of shared modal layout`);
      }

      for (const cls of forbiddenModalTableOuterScroll) {
        if (selector.includes(cls) && /overflow(?:-y)?\s*:\s*auto\b/.test(body) && /max-height\s*:/.test(body)) {
          violations.push(`${name}: selector "${selector}" applies outer max-height + overflow:auto to modal grid ${cls}`);
        }
      }
    }
  }

  assert.deepEqual(violations, [], `Found forbidden modal CSS overrides:\n${violations.join('\n')}`);
});

test('static guard: all BusinessModal layout props use one of compact | scroll-body | pane', () => {
  const allowed = new Set(['compact', 'scroll-body', 'pane']);
  const violations = [];
  for (const { name, text } of readSrcFiles('.tsx')) {
    for (const match of text.matchAll(/<BusinessModal\b[^>]*\blayout\s*=\s*"([^"]+)"/g)) {
      if (!allowed.has(match[1])) {
        violations.push(`${name}: invalid BusinessModal layout="${match[1]}"`);
      }
    }
  }
  assert.deepEqual(violations, [], violations.join('\n'));
});

test('surfaces leave edge focus rings visible and modal sections need no reset', () => {
  const surface = /\.wb-surface(?![\w-])/;
  const sheets = readSrcFiles('.css');
  assert.match(sheets.find(file => file.name === 'ui.css').text, surface);
  for (const { name, text } of sheets) {
    const css = stripCssComments(text);
    if (name === 'business-modal.css') assert.doesNotMatch(css, /(?:^|[\s>+~])section\s*\{/m);
    for (const [, selector, declarations] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      if (!surface.test(selector)) continue;
      assert.doesNotMatch(declarations, /\boverflow(?:-[\w-]+)?\s*:\s*(?:hidden|clip)\b/, name);
    }
  }
});
