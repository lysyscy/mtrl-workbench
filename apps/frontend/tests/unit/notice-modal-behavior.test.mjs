import assert from 'node:assert/strict';
import test from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { registerHooks } from 'node:module';

const button = `import { createElement } from ${JSON.stringify(import.meta.resolve('react'))};
  export default ({ htmlType, ...props }) => createElement('button', { ...props, type: htmlType });`;
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.endsWith('.css')) return { url: 'data:text/javascript,export default {}', shortCircuit: true };
    if (specifier === 'antd/es/button') return { url: 'data:text/javascript,' + encodeURIComponent(button), shortCircuit: true };
    return nextResolve(specifier, context);
  },
});

const { validatePaymentAmount } = await import('../../src/notice-payment.tsx');
const { ReviewMatchItem } = await import('../../src/notice-match-list.tsx');

test('付款校验拒绝空值、过多小数和非正金额，允许修正后提交', () => {
  for (const input of ['', 'abc', '1.001', '0', '-0.01']) {
    assert.equal(validatePaymentAmount(input, '100.00').amount, null, input);
  }
  assert.deepEqual(validatePaymentAmount('￥ 1,000.01', '1000.01'), { amount: '1000.01' });
});

test('付款上限在大额金额上仍精确到分，错误显示完整金额和单位', () => {
  assert.deepEqual(validatePaymentAmount('90071992547409.93', '90071992547409.92'), {
    amount: null, error: '付款金额不能超过 90,071,992,547,409.92 元。',
  });
  assert.deepEqual(validatePaymentAmount('90071992547409.92', '90071992547409.92'), { amount: '90071992547409.92' });
});

test('不可批量确认的候选给出原因和手动入口，抓取回执仍为只读', () => {
  const row = {
    notice_id: 1, code: 'FKTZS2026110001', title: '付款通知书', project_name: '项目',
    expected_amount: '53068.55', reason: '通知书提及的合同与已填供应商不一致',
    candidates: [{ contract_id: 3, selectable: false }],
  };
  const review = props => renderToStaticMarkup(createElement(ReviewMatchItem, { row, ...props }));
  const batch = review({ openManualLink: () => {} });
  assert.match(batch, /通知书提及的合同与已填供应商不一致/);
  assert.match(batch, /53,068\.55 元/);
  assert.match(batch, /候选合同均不可批量确认/);
  assert.match(batch, /<button[^>]*>.*去手动关联.*<\/button>/);
  assert.doesNotMatch(review({}), /去手动关联/);
  assert.doesNotMatch(review({ row: {...row, candidates: [{ contract_id: 3, selectable: true }]}, openManualLink: () => {} }), /去手动关联/);
});
