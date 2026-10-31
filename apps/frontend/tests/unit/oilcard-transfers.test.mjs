import assert from 'node:assert/strict';
import test from 'node:test';
import { readOilLedger, transferOilEntries } from '../../src/oilcard-ledger-api.ts';
import { CellSaveQueue } from '../../src/cell-save.ts';

const transfer='10000000-0000-4000-8000-000000000000';
const version='20000000-0000-4000-8000-000000000000';
const out={id:1,request_id:'30000000-0000-4000-8000-000000000000',version,kind:'transfer_out',project_id:11,account_id:31,card_id:51,date_text:'原始数据',entry_date:null,amount:'-1000.00',remark:'转出',related_entry_id:null,transfer_id:transfer};
const incoming={...out,id:2,request_id:'40000000-0000-4000-8000-000000000000',kind:'transfer_in',account_id:32,amount:'1000.00',remark:'转入'};

test('full ledger accepts balanced same-card transfer and refuses missing, mismatched or duplicate sides',()=>{
  assert.equal(readOilLedger({entries:[out,incoming],total_amount:'0.00'}).entries.length,2);
  for(const entries of [[out],[out,{...incoming,amount:'999.00'}],[out,{...incoming,date_text:'日期不同'}],[out,{...incoming,version:incoming.request_id}],[out,incoming,{...incoming,id:3,request_id:'50000000-0000-4000-8000-000000000000'}]]){
    assert.throws(()=>readOilLedger({entries,total_amount:'0.00'}));
  }
  assert.throws(()=>readOilLedger({entries:[{...out,kind:'adjustment'},incoming],total_amount:'0.00'}));
});

test('an incomplete transfer reply locks later writes until reliable paired readback and explicit confirmation',async()=>{
  const originalFetch=globalThis.fetch;
  let writes=0;
  globalThis.fetch=async()=>{writes++;return new Response(JSON.stringify({ok:true,items:[out]}),{status:200,headers:{'Content-Type':'application/json'}});};
  try{
    const options={enabled:true,read:async()=>readOilLedger({entries:[out,incoming],total_amount:'0.00'}),write:async()=>{},acknowledge:()=>undefined,saved:()=>''};
    const queue=new CellSaveQueue(()=>options);
    const result=await queue.run(signal=>transferOilEntries({request_id:transfer,out_project_id:11,out_account_id:31,in_project_id:11,in_account_id:32,amount:'1000',date_text:'原始数据',out_remark:'转出',in_remark:'转入'},signal),()=>'');
    assert.equal(result,'uncertain');
    assert.equal(await queue.run(async()=>{writes++;},()=>''),'blocked');
    assert.equal(await queue.reread(),true);
    assert.equal(queue.getSnapshot().uncertain,true);
    queue.confirm();
    assert.equal(queue.getSnapshot().uncertain,false);
    assert.equal(writes,1);
    queue.dispose();
  }finally{globalThis.fetch=originalFetch;}
});
