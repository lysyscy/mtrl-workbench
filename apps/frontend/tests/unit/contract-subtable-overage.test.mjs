import test from 'node:test';
import assert from 'node:assert/strict';
import { subtableOverage } from '../../src/contract-subtable-overage.ts';

const base = (overrides = {}) => ({
  side: 'supplier',
  savedTotal: '0.00',
  contractAmount: '1000000.00',
  ...overrides,
});

test('恰好 110% 不报超，多 0.01 才报超', () => {
  const exact = subtableOverage(base({ savedTotal: '1100000.00' }));
  assert.equal(exact.over, false);
  assert.equal(exact.saved, '1100000.00');
  assert.equal(exact.contract, '1000000.00');
  assert.equal(exact.ratio, '110.0');

  const more = subtableOverage(base({ savedTotal: '1100000.01' }));
  assert.equal(more.over, true);
  assert.equal(more.ratio, '110.0');
});

test('累计低于合同不报超且比例正确', () => {
  const result = subtableOverage(base({ savedTotal: '500000' }));
  assert.equal(result.over, false);
  assert.equal(result.missingContract, false);
  assert.equal(result.saved, '500000.00');
  assert.equal(result.ratio, '50.0');
});

test('累计超合同但未到 110% 不报超', () => {
  const result = subtableOverage(base({ savedTotal: '1050000.00' }));
  assert.equal(result.over, false);
  assert.equal(result.ratio, '105.0');
});

test('合同额缺失或非正时统一按不可判断处理', () => {
  for (const contractAmount of [null, undefined, '', '0.00']) {
    const result = subtableOverage(base({ contractAmount, savedTotal: '1100000.00' }));
    assert.equal(result.missingContract, true, String(contractAmount));
    assert.equal(result.contract, null, String(contractAmount));
    assert.equal(result.ratio, null, String(contractAmount));
    assert.equal(result.over, false, String(contractAmount));
    assert.equal(result.saved, '1100000.00', String(contractAmount));
  }
});

test('本次输入恰好到 110% 不算将超，多 0.01 才算', () => {
  const exact = subtableOverage(base({ savedTotal: '1000000.00', pendingAmount: '100000.00' }));
  assert.equal(exact.projected, '1100000.00');
  assert.equal(exact.projectedOver, false);
  assert.equal(exact.over, false);

  const more = subtableOverage(base({ savedTotal: '1000000.00', pendingAmount: '100000.01' }));
  assert.equal(more.projected, '1100000.01');
  assert.equal(more.projectedOver, true);
  // 已保存金额本身没有超，超的判定只来自本次输入。
  assert.equal(more.over, false);
});

test('合同额缺失时本次输入也不会判为将超', () => {
  const result = subtableOverage(base({ contractAmount: null, savedTotal: '1000000.00', pendingAmount: '500000.00' }));
  assert.equal(result.missingContract, true);
  assert.equal(result.projected, '1500000.00');
  assert.equal(result.projectedOver, false);
});

test('未完成的输入按无输入处理且不抛错', () => {
  for (const pendingAmount of ['12.', '1.234', 'abc', '', '0', '-5']) {
    let result;
    assert.doesNotThrow(() => { result = subtableOverage(base({ savedTotal: '1200000.00', pendingAmount })); }, pendingAmount);
    assert.equal(result.projected, '1200000.00', pendingAmount);
    assert.equal(result.projectedOver, false, pendingAmount);
    assert.equal(result.over, true, pendingAmount);
  }
});

test('没有本次输入时累计等于已保存金额', () => {
  const absent = subtableOverage(base({ savedTotal: '1200000.00' }));
  assert.equal(absent.projected, absent.saved);
  assert.equal(absent.projectedOver, false);
  assert.equal(absent.over, true);

  const nullish = subtableOverage(base({ savedTotal: '1200000.00', pendingAmount: null }));
  assert.equal(nullish.projected, nullish.saved);
  assert.equal(nullish.projectedOver, false);
});

test('大额金额不因浮点失真：11000000000000000.00 对 9999999999999999.99 真超阈值', () => {
  const result = subtableOverage(base({ savedTotal: '11000000000000000.00', contractAmount: '9999999999999999.99' }));
  assert.equal(result.contract, '9999999999999999.99');
  assert.equal(result.saved, '11000000000000000.00');
  // 真实比例 110.00000000000000011...%，浮点会读成恰好 110.0%，整数分不会。
  assert.equal(result.over, true);
  assert.equal(result.ratio, '110.0');
});

test('trade 侧行为与 supplier 完全一致', () => {
  const input = { savedTotal: '1050000.00', contractAmount: '1000000.00', pendingAmount: '60000.00' };
  const supplier = subtableOverage({ ...input, side: 'supplier' });
  const trade = subtableOverage({ ...input, side: 'trade' });
  assert.deepEqual(trade, supplier);
  assert.equal(trade.over, false);
  assert.equal(trade.ratio, '105.0');
  assert.equal(trade.projected, '1110000.00');
  assert.equal(trade.projectedOver, true);
});

test('超出比例与占合同额比例分开：112万元对100万元超出12%', () => {
  const result = subtableOverage(base({ savedTotal: '1120000.00', pendingAmount: '10000.00' }));
  assert.equal(result.ratio, '112.0');
  assert.equal(result.excessRatio, '12.0');
  assert.equal(result.projectedExcessRatio, '13.0');
});
