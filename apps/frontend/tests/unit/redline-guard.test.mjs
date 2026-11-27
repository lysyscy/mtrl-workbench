import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';

const src = new URL('../../src/', import.meta.url);
const files = readdirSync(src, { recursive: true }).map(file => file.replaceAll('\\', '/'));
const read = file => readFileSync(new URL(file, src), 'utf8');
const modules = files.filter(file => /\.tsx?$/.test(file));
const uiSources = modules.filter(file => file.endsWith('.tsx'));

function forbidCopy(candidates, phrases) {
  assert.ok(candidates.length);
  for (const file of candidates) {
    const source = read(file);
    for (const phrase of phrases) assert.ok(!source.includes(phrase), file + ' contains ' + phrase);
  }
}

test('R05: single-line mode stays on the approved pages and their shared grids', () => {
  const allowed = new Set([
    'notices.tsx', 'notices.css', 'notice-payment-grid.tsx',
    'contracts.tsx', 'contract-subtables.tsx', 'contract-subtables.css',
    'grid-single-line.css', 'business-grid.tsx', 'bounded-grid.tsx',
  ]);
  const usage = /(?<![\w-])(?:grid-single-line|singleLine)(?![\w-])/g;
  for (const file of files.filter(name => /\.(tsx|css)$/.test(name))) {
    if (allowed.has(file) || /^mechanical(?:-[\w-]+)?\.tsx$/.test(file)) continue;
    let source = read(file);
    if (file.endsWith('.css')) source = source.replace(/\/\*[\s\S]*?\*\//g, '');
    if (file === 'styles.css') source = source.replace(/^@import '\.\/grid-single-line\.css';\s*$/m, '');

    // PR-W4: review the existing equipment distribution grid from d454dc90.
    if (file === 'equipment-distribution.tsx') {
      assert.match(source, /<BusinessGrid\s+key=\{category\}\s+table=\{'equipment-' \+ category\}[^<]*\s+singleLine\s+className="equipment-grid-slot"/);
      assert.deepEqual([...source.matchAll(usage)].map(match => match[0]), ['singleLine'], file);
      continue;
    }
    assert.deepEqual([...source.matchAll(usage)].map(match => match[0]), [], file);
  }
});

test('R06: autosave toolbars never offer to discard a whole page or scope', () => {
  forbidCopy(modules, ['取消未保存修改', '撤销未保存修改', '取消本项目修改', '放弃未保存输入']);
});

test('R07: global undo shortcuts stay out of key handlers and the grid leaves text editing native', () => {
  const keydown = /\b(?:on)?keydown(?:capture)?\b/i;
  const modifiers = /\b(?:ctrlKey|metaKey)\b/;
  const undoKeys = /['"](?:[zy]|Key[ZY])['"]/i;
  const owners = [];
  for (const file of modules) {
    const source = read(file);
    assert.ok(!(keydown.test(source) && modifiers.test(source) && undoKeys.test(source)), file + ' handles Ctrl/Cmd undo');
    if (/\bsuppressKeyboardEvent\b/.test(source)) owners.push(file);
  }
  assert.deepEqual(owners, ['grid.ts']);

  const grid = read('grid.ts');
  assert.equal([...grid.matchAll(/\bsuppressKeyboardEvent\b/g)].length, 1);
  assert.match(grid, /suppressKeyboardEvent:\s*suppressEditorKeyboardEvent\b/);
  const nativeEditor = grid.match(/function suppressEditorKeyboardEvent\b[\s\S]*?^\}/m)?.[0];
  assert.ok(nativeEditor);
  assert.match(nativeEditor, /target\.isContentEditable/);
  assert.match(nativeEditor, /target\.closest\('input, textarea, select,/);
  assert.doesNotMatch(nativeEditor, /\b(?:preventDefault|stopPropagation|stopImmediatePropagation)\b/);
});

test('R08: discard confirmation puts the initial focus on continuing to edit', () => {
  const close = read('dialog-close.tsx');
  const discard = close.split('export function DiscardConfirmation(')[1]?.split('export function DialogContents(')[0];
  assert.ok(discard);
  assert.match(discard, />放弃未保存的修改？<\/DialogHeading>/);
  assert.match(discard, /<p>本次输入和选择尚未保存。<\/p>/);
  const buttons = [...discard.matchAll(/<Button\b([^>]+)>([^<]+)<\/Button>/g)];
  assert.deepEqual(buttons.map(button => button[2]), ['继续编辑', '放弃并关闭']);
  assert.match(buttons[0][1], /\bautoFocus\b/);
  assert.match(buttons[0][1], /onClick=\{closing\.resume\}/);
  assert.doesNotMatch(buttons[1][1], /\bautoFocus\b/);
  assert.match(buttons[1][1], /onClick=\{closing\.discard\}/);

  const modal = read('business-modal.tsx');
  assert.match(modal, /onCancel=\{[^}]*\brequestClose\(\)/);
  assert.doesNotMatch(modal, /放弃未保存的修改|放弃并关闭/);
});

test('R13: contracts do not show 最近抓取结果', () => {
  forbidCopy(uiSources.filter(file => /^(?:contracts|contract-).*\.tsx$/.test(file)), ['最近抓取结果']);
});

test('R16 and R17: retired report summaries and mechanical submit buttons stay retired', () => {
  forbidCopy(['settlement.tsx', 'big.tsx', 'fees.tsx'], ['报表待核对汇总']);
  forbidCopy(uiSources.filter(file => /^mechanical.*\.tsx$/.test(file)), ['确认汇总', '确认内租']);
});
