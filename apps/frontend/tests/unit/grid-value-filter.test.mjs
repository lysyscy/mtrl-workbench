import assert from 'node:assert/strict';
import test from 'node:test';
import { checkedValueFilterNodes, compareFilterValues, searchValueFilterTree, toggleValueFilter, valueFilterCandidates, valueFilterKey, valueFilterPasses, valueFilterTree } from '../../src/grid-value-filter-model.ts';

test('inactive and last-unchecked selections show all; changing one column preserves the others',()=>{
  const first=valueFilterKey('甲','text'), second=valueFilterKey('乙','text');
  assert.equal(valueFilterPasses(null,'甲','text'),true);
  const columnB={values:[valueFilterKey('调整','text')]};
  const state={a:null,b:columnB};
  state.a=toggleValueFilter(state.a,[first],true);
  assert.equal(valueFilterPasses(state.a,'甲','text'),true);
  assert.equal(valueFilterPasses(state.a,'乙','text'),false);
  state.a=toggleValueFilter(state.a,[second],true);
  state.a=toggleValueFilter(state.a,[first],false);
  assert.deepEqual(state.a,{values:[second]});
  state.a=toggleValueFilter(state.a,[second],false);
  assert.equal(state.a,null);
  assert.equal(valueFilterPasses(state.a,'甲','text'),true);
  assert.equal(state.b,columnB);
});

test('date year/month/day selections keep independent source text and blank candidates',()=>{
  const values=['2025-12-31','2026-10-30','2026-10-31','2026-10-31','2026-11-01','原始数据','',null,'2026-02-30'];
  const candidates=valueFilterCandidates(values,'date');
  assert.equal(candidates.find(c=>c.key==='blank:').count,2);
  assert.equal(candidates.find(c=>c.key==='d:2026-10-31').count,2);
  assert.equal(candidates.find(c=>c.key==='t:2026-02-30').label,'2026-02-30');
  const tree=valueFilterTree(candidates,'date');
  const year=tree.find(n=>n.key==='year:2026');
  const october=year.children.find(n=>n.key==='month:2026-10');
  let model=toggleValueFilter(null,year.values,true);
  assert.equal(valueFilterPasses(model,'2026-11-01','date'),true);
  assert.equal(valueFilterPasses(model,'原始数据','date'),false);
  model=toggleValueFilter(model,october.values,false);
  assert.equal(valueFilterPasses(model,'2026-10-31','date'),false);
  assert.equal(valueFilterPasses(model,'2026-11-01','date'),true);
  assert.ok(checkedValueFilterNodes(tree,model).halfChecked.includes('year:2026'));
  model=toggleValueFilter(model,['t:原始数据','blank:'],true);
  assert.equal(valueFilterPasses(model,'原始数据','date'),true);
  assert.equal(valueFilterPasses(model,null,'date'),true);
  assert.deepEqual(checkedValueFilterNodes(tree,null),{checked:[],halfChecked:[]});
});

test('search only narrows displayed candidates and keeps selection/counts and full date membership',()=>{
  const tree=valueFilterTree(valueFilterCandidates(['2026-10-30','2026-10-31','2026-10-31','原始数据'],'date'),'date');
  const model={values:['t:原始数据']};
  const searched=searchValueFilterTree(tree,'2026-10-31');
  assert.equal(searched.length,1);
  assert.equal(searched[0].children[0].children[0].count,2);
  assert.deepEqual(searched[0].values,['d:2026-10-30','d:2026-10-31']);
  assert.equal(valueFilterPasses(model,'原始数据','date'),true);
  assert.deepEqual(model,{values:['t:原始数据']});
});

test('numeric candidates and sort compare decimal values, including negatives, zero and large cents',()=>{
  const candidates=valueFilterCandidates(['10.00','2.00','-1.25','0.00','2.0','9999999999999999.98','9999999999999999.99'],'number');
  assert.deepEqual(candidates.slice(0,4).map(c=>c.label),['-1.25','0','2','10']);
  assert.equal(candidates.find(c=>c.key==='n:2').count,2);
  assert.equal(compareFilterValues('10.00','2.00','number'),1);
  assert.equal(compareFilterValues('9999999999999999.98','9999999999999999.99','number'),-1);
  assert.equal(valueFilterPasses({values:['n:0']},'0.00','number'),true);
  assert.equal(valueFilterPasses({values:['n:2']},'2.00','number'),true);
  assert.equal(valueFilterPasses({values:['n:2']},'20.00','number'),false);
});
