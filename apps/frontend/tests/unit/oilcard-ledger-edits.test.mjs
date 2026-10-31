import assert from 'node:assert/strict';
import test from 'node:test';
import { editOilEntry as editByKey, rebaseOilEntryDraft } from '../../src/oilcard-ledger-edits.ts';

// Cell props may keep an older row; the page forwards its stable identity only.
const editOilEntry=(drafts,entries,rendered,...args)=>editByKey(drafts,entries,rendered.request_id,...args);

const blank = { id:0,request_id:'stable-request',version:'',kind:'recharge',project_id:0,account_id:0,card_id:null,date_text:'',entry_date:null,amount:'',remark:'',related_entry_id:null };
const saved = { ...blank,id:1,version:'saved-v1',project_id:11,account_id:31,card_id:51,date_text:'原始数据',amount:'10000.00',remark:'原备注' };
const accounts = [{id:31,project_id:11},{id:32,project_id:12},{id:33,project_id:13},{id:34,project_id:13}];

test('after automatic creation, an unchanged cell keeps the saved identity, amount and ownership',()=>{
  let drafts=editOilEntry({},[saved],blank,'remark','更正后备注',accounts,false);
  assert.equal(drafts[blank.request_id].id,1);
  assert.equal(drafts[blank.request_id].amount,'10000.00');
  assert.equal(drafts[blank.request_id].account_id,31);
  assert.equal(drafts[blank.request_id].project_id,11);
  assert.equal(drafts[blank.request_id].original.version,'saved-v1');
});

test('existing row cross-column edits never restore an earlier saved field',()=>{
  const latest={...saved,version:'saved-v2',amount:'12000.00',date_text:'2026-10-31',remark:'已保存备注'};
  const drafts=editOilEntry({},[latest],saved,'date_text','2026-11-01',accounts,false);
  assert.equal(drafts[saved.request_id].amount,'12000.00');
  assert.equal(drafts[saved.request_id].remark,'已保存备注');
  assert.equal(drafts[saved.request_id].original.version,'saved-v2');
});

test('unsaved input stays ahead of readback; project and account remain one change',()=>{
  const draft={...saved,amount:'12345',original:saved,error:''};
  let drafts=editOilEntry({[saved.request_id]:draft},[saved],blank,'remark','后续输入',accounts,true);
  assert.equal(drafts[saved.request_id].amount,'12345');
  drafts=editOilEntry(drafts,[saved],blank,'project_id','12',accounts,false);
  assert.equal(drafts[saved.request_id].account_id,32);
  assert.equal(drafts[saved.request_id].amount,'12345');
  drafts=editOilEntry(drafts,[saved],blank,'project_id','13',accounts,false);
  assert.equal(drafts[saved.request_id].account_id,0);
  assert.equal(drafts[saved.request_id].original.version,'saved-v1');
});

test('readback advances saved identity and version without replacing later input',()=>{
  const later={...blank,date_text:'原始数据',project_id:11,account_id:31,amount:'10000',remark:'下一格输入',original:null,error:''};
  const rebased=rebaseOilEntryDraft(later,saved);
  assert.equal(rebased.id,1);
  assert.equal(rebased.version,'saved-v1');
  assert.equal(rebased.original,saved);
  assert.equal(rebased.remark,'下一格输入');
  assert.equal(rebased.amount,'10000');
  const drafts=editOilEntry({[saved.request_id]:rebased},[saved],blank,'date_text','2026-11-01',accounts,false);
  assert.equal(drafts[saved.request_id].remark,'下一格输入');
  assert.equal(drafts[saved.request_id].original.version,'saved-v1');
});
