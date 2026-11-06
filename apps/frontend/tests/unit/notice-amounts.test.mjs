import test from 'node:test';
import assert from 'node:assert/strict';
import { confirmNoticeAmount, noticeAmountMatches, saveNoticeAmount } from '../../src/notices-api.ts';
import { uncertainWrite } from '../../src/api.ts';

test('amount reconciliation follows accepted separators and HALF_UP without another write',()=>{
  for(const [input,actual] of [['1,234.50','1234.50'],[' 1，234.50 ','1234.50'],['12.345','12.35'],['-0.00','0.00'],['1.2e2','120.00']])assert.equal(noticeAmountMatches(input,actual),true);
  assert.equal(noticeAmountMatches('12.345','12.34'),false);
  assert.equal(noticeAmountMatches('','0.00'),false);
  assert.equal(noticeAmountMatches('NaN','0.00'),false);
});

test('notice cell receipts must identify the operation and its actual result',()=>{
  confirmNoticeAmount({ok:true,changed:false,notice_id:7,field:'stat_settle',message:'unchanged'},7,'stat_settle');
  const changed={ok:true,changed:true,notice_id:7,field:'stat_settle',before:'0.00',after:'12.35',label:'统计结算金额',message:'saved'};
  confirmNoticeAmount(changed,7,'stat_settle');
  confirmNoticeAmount({...changed,field:'amount_approved'},7,'amount_approved');
  for(const result of [{ok:true},{...changed,notice_id:8},{...changed,after:null},{...changed,field:'stat_paid'}]){
    assert.throws(()=>confirmNoticeAmount(result,7,'stat_settle'),failure=>uncertainWrite(failure));
  }
  for(const result of [{ok:true,row_id:'7',message:'saved'},{...changed,field:'amount_approved',notice_id:8},{ok:true,changed:false,message:'unchanged'}]) {
    assert.throws(()=>confirmNoticeAmount(result,7,'amount_approved'),failure=>uncertainWrite(failure));
  }
});

test('all notice cells submit only the amount intent and reject uncertain receipts',async t=>{
  const originalFetch=globalThis.fetch;
  t.after(()=>{globalThis.fetch=originalFetch;});
  let calls=0, invalid=false;
  globalThis.fetch=async(path,init)=>{
    calls++;
    assert.equal(path,'/api/m03/actions/amount');
    assert.equal(init.method,'POST');
    const payload=JSON.parse(init.body);
    assert.deepEqual(Object.keys(payload).sort(),['field','notice_id','value']);
    assert.equal(payload.notice_id,7);assert.equal(payload.value,'12.35');
    return Response.json(invalid?{ok:true}:{ok:true,changed:true,notice_id:7,field:payload.field,before:'20.00',after:'12.35',label:'金额',message:'saved'});
  };
  for(const field of ['amount_approved','stat_settle','stat_paid'])await saveNoticeAmount(7,field,'12.35');
  invalid=true;
  await assert.rejects(saveNoticeAmount(7,'amount_approved','12.35'),failure=>uncertainWrite(failure));
  assert.equal(calls,4,'An uncertain receipt must never trigger an automatic retry');
});
