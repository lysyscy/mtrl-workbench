import assert from 'node:assert/strict';
import test from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { ContractMaterialContext } from '../../src/contract-dialog.tsx';

const contract = { contract_no: 'CGHT202611280001-补充协议-002', supplier: '材料供应商', date: '2026-11-28' };
const render = (details, project = '项目展示名') =>
  renderToStaticMarkup(createElement(ContractMaterialContext, { project, contract: details }));

test('the material editor context identifies the project and full contract number', () => {
  assert.match(render(contract), /项目展示名.*CGHT202611280001-补充协议-002/);
});

test('a manual contract uses the available supplier and date', () => {
  const manual = { ...contract, contract_no: '' };
  assert.match(render(manual), /项目展示名.*材料供应商 · 2026-11-28/);
  assert.match(render({ ...manual, supplier: '' }), /项目展示名.*2026-11-28/);
  assert.equal(render({ contract_no: '', supplier: '', date: '' }, ''), '');
});
