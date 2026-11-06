import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiError } from '../../src/api.ts';
import { readProjectPending, readProjectTrails } from '../../src/project-maintenance-reads.ts';
import { countNewRuleMatches } from '../../src/rule-add-recovery.ts';

const candidate = { id: 1, disp: '', warehouse_name: '未建仓-1', status: 'archived', is_placeholder: true };
const promote = { full_name: '待指认', warehouse_name: '材料仓', candidates: [candidate] };
const archive = { full_name: '待建档', warehouses: ['一仓', '二仓'] };
const source = { at: '', target: '记录范围', run_record_id: null };

test('project pending readers keep actual empty and populated lists and reject broken consumed values', () => {
  for (const [kind, row] of [['promote', promote], ['archive', archive]]) {
    const populated = { items: [row], source, dropped_items: [{ why_text: '未消费' }] };
    assert.equal(readProjectPending(populated, kind), populated);
    assert.deepEqual(readProjectPending({ items: [], source: {} }, kind).items, []);
    assert.throws(() => readProjectPending({ items: [null], source: {} }, kind), ApiError);
    assert.throws(() => readProjectPending({ ...populated, source: { ...source, target: {} } }, kind), ApiError);
  }
  for (const broken of [null, { ...candidate, is_placeholder: 'true' }, { ...candidate, id: '1' }]) {
    assert.throws(() => readProjectPending({ items: [{ ...promote, candidates: [broken] }], source }, 'promote'), ApiError);
  }
  assert.throws(() => readProjectPending({ items: [{ ...archive, warehouses: ['一仓', null] }], source }, 'archive'), ApiError);
});

test('project trail rows retain blank historical values and reject missing or malformed visible facts', () => {
  const trail = { at: '2026-11-06 12:10:00', project: '示例项目', field_label: '项目全名', before: '', after: '新全名', by: '' };
  assert.deepEqual(readProjectTrails([trail]), [trail]);
  assert.deepEqual(readProjectTrails([]), []);
  for (const row of [null, { ...trail, field_label: undefined }, { ...trail, before: {} }]) {
    assert.throws(() => readProjectTrails([row]), ApiError);
  }
});

test('rule review reports all newly seen normalized matches and ignores earlier IDs or changed content', () => {
  const draft = { kind: ' 类别 ', values: ' 甲｜|乙，甲,, 丙 ', meaning: ' 含义 ' };
  const same = { kind: '类别', values: '甲｜乙｜丙', meaning: '含义' };
  const earlier = { ...same, id: 1 };
  const matching = [{ ...same, id: 2 }, { ...same, id: 3 }];
  const changed = [{ ...same, id: 4, values: '乙｜甲｜丙' }, { ...same, id: 5, meaning: '不同' }, { ...same, id: 6, kind: '不同' }];
  assert.equal(countNewRuleMatches(draft, new Set([1]), [earlier, ...matching, ...changed]), 2);
  assert.equal(countNewRuleMatches(draft, new Set([1]), [earlier, ...changed]), 0);
});
