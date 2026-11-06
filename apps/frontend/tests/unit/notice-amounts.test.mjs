import test from 'node:test';
import assert from 'node:assert/strict';
import { confirmNoticeAmount, noticeAmountMatches } from '../../src/notices-api.ts';
import { uncertainWrite } from '../../src/api.ts';

test('amount reconciliation follows accepted separators and HALF_UP without another write',()=>{
  for(const [input,actual] of [['1,234.50','1234.50'],[' 1，234.50 ','1234.50'],['12.345','12.35'],['-0.00','0.00'],['1.2e2','120.00']])assert.equal(noticeAmountMatches(input,actual),true);
  assert.equal(noticeAmountMatches('12.345','12.34'),false);
  assert.equal(noticeAmountMatches('','0.00'),false);
  assert.equal(noticeAmountMatches('NaN','0.00'),false);
});

test('notice cell receipts must identify the operation and its actual result',()=>{
  confirmNoticeAmount({ok:true,changed:false,message:'unchanged'},7,'stat_settle');
  const changed={ok:true,changed:true,notice_id:7,field:'stat_settle',before:'0.00',after:'12.35',label:'统计结算金额',message:'saved'};
  confirmNoticeAmount(changed,7,'stat_settle');
  confirmNoticeAmount({ok:true,row_id:'7',message:'saved'},7,'amount_approved');
  for(const result of [{ok:true},{...changed,notice_id:8},{...changed,after:null},{...changed,field:'stat_paid'}]){
    assert.throws(()=>confirmNoticeAmount(result,7,'stat_settle'),failure=>uncertainWrite(failure));
  }
  assert.throws(()=>confirmNoticeAmount({ok:true,row_id:'8',message:'saved'},7,'amount_approved'),failure=>uncertainWrite(failure));
});
