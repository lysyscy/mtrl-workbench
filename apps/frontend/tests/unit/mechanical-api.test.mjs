import test from 'node:test';
import assert from 'node:assert/strict';
import {internalAmount,readInternalSave,readMechanicalReport} from '../../src/mechanical-api.ts';

const cell=(value,column=1,colspan=1)=>({value,column,colspan,rowspan:1});
function report(){return {ok:true,ym:'2026-10',projects:[{warehouse:'甲'}],sheets:[
  {name:'工程公司汇总表',rows:[[],[],[],[],[],[cell('甲项目')],[cell('合计',1,2)]],project_rows:[{warehouse:'甲',row:6}]},
  ...['零租设备月报表','包月外租设备月报','年度汇总'].map(name=>({name,rows:[[cell('甲项目')]],project_rows:[{warehouse:'甲',row:1}]})),
]};}

test('complete template notes stay separate from company project and total rows',()=>{
  const data=report();assert.equal(readMechanicalReport(data,'2026-10',['甲']).sheets[0].rows.length,7);
  data.sheets[0].rows.push([cell('原表说明',1,15)]);
  const result=readMechanicalReport(data,'2026-10',['甲']);
  assert.equal(result.sheets[0].rows.length,8);
  assert.equal(result.sheets[0].rows[6][0].value,'合计');
  assert.equal(result.sheets[0].rows[7][0].value,'原表说明');
});

test('missing total, misplaced project and unexplained extra financial row remain rejected',()=>{
  for(const corrupt of [data=>data.sheets[0].rows.pop(),data=>data.sheets[0].project_rows[0].row=5,data=>data.sheets[0].rows.push([cell('20.00',5)])]){
    const data=report();corrupt(data);assert.throws(()=>readMechanicalReport(data,'2026-10',['甲']));
  }
});

test('internal rent accepts explicit zero and preserves the nonnegative two-decimal boundary',()=>{
  assert.equal(internalAmount('0'),'0.00');
  assert.equal(internalAmount(' 125.5 '),'125.50');
  for(const value of ['', '-1', '12.345', 'NaN'])assert.equal(internalAmount(value),null);
});

test('internal rent acknowledges only the submitted project month field and amount',()=>{
  const receipt={ok:true,warehouse:'甲',ym:'2026-10',signature:'new-effective',values:{mech_0:'125.50',mech_1:'88.00'},sources:{}};
  assert.equal(readInternalSave(receipt,'甲','2026-10','mech_0','125.50'),receipt);
  for(const corrupt of [{...receipt,ok:false},{...receipt,warehouse:'乙'},{...receipt,ym:'2026-09'},{...receipt,signature:''},{...receipt,values:{mech_0:'125.00'}}]){
    assert.throws(()=>readInternalSave(corrupt,'甲','2026-10','mech_0','125.50'),error=>error.code==='invalid_receipt');
  }
});
