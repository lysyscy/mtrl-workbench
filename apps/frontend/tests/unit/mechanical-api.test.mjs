import test from 'node:test';
import assert from 'node:assert/strict';
import {companySummaryRows,historyInitialization,internalAmount,readInternalSave,readI8Preview,readMechanicalReport,readWorkbench,readWorkbenchPage,readWorkResult} from '../../src/mechanical-api.ts';

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

const base={warehouse:'甲',revision:0,signature:'captured-month-values',can_initialize:true,base_month:'',category_totals:{zero:null,monthly:null,internal:null},i6:null,note:''};
const draft={base_month:'2026-09',zero:'0',monthly:'0',internal:'0',i6:'0',note:'已核原汇总，前期费用及i6明确为0'};
test('history initialization requires explicit amounts and preserves unknown optional categories',()=>{
  const payload=historyInitialization(base,draft);
  assert.deepEqual(payload,{warehouse:'甲',revision:0,effective_signature:'captured-month-values',base_month:'2026-09',category_totals:{zero:'0.00',monthly:'0.00',internal:'0.00',weekly:null,company:null},i6:'0.00',note:draft.note});
  for(const field of ['zero','monthly','internal','i6','note','base_month'])assert.equal(historyInitialization(base,{...draft,[field]:''}),null);
  assert.equal(historyInitialization(base,{...draft,base_month:'2026-13'}),null);
  assert.equal(historyInitialization(base,{...draft,zero:'-1'}),null);
  assert.equal(historyInitialization({...base,can_initialize:false},draft),null);
  assert.equal(historyInitialization({...base,revision:1},draft),null);
});

test('history initialization acknowledges only the submitted project and first revision',()=>{
  const payload=historyInitialization(base,draft);
  assert.doesNotThrow(()=>readWorkResult({ok:true,warehouse:'甲',revision:1},'history-initialize',payload));
  for(const receipt of [{ok:true,warehouse:'乙',revision:1},{ok:true,warehouse:'甲',revision:0},{ok:true,warehouse:'甲',revision:2},{ok:false,warehouse:'甲',revision:1}])assert.throws(()=>readWorkResult(receipt,'history-initialize',payload),error=>error.code==='invalid_receipt');
});

function workbench(){return {ok:true,months:['2026-10'],settings:{shown_projects:['甲'],plate_keywords:[],revision:0},projects:[{warehouse:'甲'}],details:[],effective:[],reconciliations:[{warehouse:'甲',relation:'report',left:null,right:null,pending:null,raw:null,ignored:'0.00',revision:0,i8_revision:0,i6:null,recorded_total:'9600.00',recorded_months:['2026-10'],i8_usage:'9599.00',missing_reasons:['累计起点待补','固定i6待补'],i8_checked_at:'2026-11-02T00:00:00Z',i8_source_status:'no-records'}],billDifferences:[],discoveries:[],matters:[],i8:[],histories:[],summary:[],history_bases:[base]};}
function page(){return {...workbench(),company_rows:[{warehouse:'甲',values:['1','甲项目','2025','06',...Array(10).fill(null),'原备注']}]};}
test('page reads require one complete company row per project and only the requested financial month',()=>{
  const data=page();data.months.unshift('2026-09');
  assert.deepEqual(readWorkbenchPage(data,'2026-10').months,['2026-09','2026-10']);
  for(const corrupt of [
    value=>delete value.company_rows,
    value=>value.company_rows[0].values.pop(),
    value=>value.company_rows[0].values[4]='NaN',
    value=>value.company_rows[0].values[2]=2025,
    value=>value.company_rows[0].warehouse='乙',
    value=>{value.projects.push({warehouse:'乙'});value.company_rows.push(structuredClone(value.company_rows[0]));},
    value=>value.summary.push({warehouse:'甲',ym:'2026-09',cumulative:{weekly:null}}),
  ]){const data=page();corrupt(data);assert.throws(()=>readWorkbenchPage(data,'2026-10'));}
});

test('company rows follow display selection and real project ids while preserving weekly and note overrides',()=>{
  const source=page();source.projects.push({warehouse:'乙'});
  source.company_rows[0].values[4]='125.125';
  source.company_rows.push({warehouse:'乙',values:['2','乙项目',null,null,'20.125',null,'999',null,null,null,null,'888',null,null,'旧备注']});
  source.histories=[{warehouse:'乙',original_months:{'2026-10':{weekly:'12.50'}}}];
  source.summary=[{warehouse:'乙',ym:'2026-10',cumulative:{weekly:'33.00'},note:'当前备注'}];
  source.effective=[{warehouse:'乙',ym:'2026-10',signature:'current',values:{weekly:'10.00'},sources:{}}];
  const data=readWorkbenchPage(source,'2026-10');
  const rows=companySummaryRows(data,'2026-10',[{warehouse:'乙',id:42},{warehouse:'甲',id:7}]);
  assert.deepEqual(rows.map(row=>[row.id,row.c0,row.c1]),[['42','1','乙项目'],['7','2','甲项目'],['total','合计',null]]);
  assert.equal(rows[0].c6,'33.00');assert.equal(rows[0].c11,'12.50');assert.equal(rows[0].c14,'当前备注');
  assert.equal(rows[2].c4,'145.25');assert.equal(rows[2].c5,null);assert.equal(rows[2].c6,'33.00');assert.equal(rows[2].c11,'10.00');
  assert.equal(source.company_rows[1].values[6],'999');
  assert.throws(()=>companySummaryRows(data,'2026-10',[{warehouse:'不存在',id:99}]));
});

test('company totals preserve explicit zero and empty display selection',()=>{
  const source=page();source.company_rows[0].values[4]='0.00';
  const data=readWorkbenchPage(source,'2026-10');
  assert.equal(companySummaryRows(data,'2026-10',[{warehouse:'甲',id:7}])[1].c4,'0.00');
  const empty=companySummaryRows(data,'2026-10',[]);
  assert.equal(empty.length,1);assert.equal(empty[0].c4,null);assert.equal(empty[0].c11,null);
});
test('workbench keeps recorded totals and checked source states separate from unknown cumulative amounts',()=>{
  const data=readWorkbench(workbench());
  assert.equal(data.relations[0].left,null);
  assert.equal(data.relations[0].recorded_total,'9600.00');
  assert.equal(data.relations[0].i8_usage,'9599.00');
  assert.deepEqual(data.relations[0].missing_reasons,['累计起点待补','固定i6待补']);
  assert.equal(data.relations[0].i8_source_status,'no-records');
  assert.equal(data.history_bases[0].signature,'captured-month-values');
  const legacy=workbench();delete legacy.history_bases;assert.deepEqual(readWorkbench(legacy).history_bases,[]);
  for(const corrupt of [value=>value.reconciliations[0].recorded_total='NaN',value=>value.reconciliations[0].missing_reasons=null,value=>value.history_bases[0]={...base,signature:''}]){
    const value=workbench();corrupt(value);assert.throws(()=>readWorkbench(value));
  }
});

test('first empty i8 reads cannot masquerade as adoptable zero snapshots',()=>{
  const project={warehouse:'甲',sources:{usage:[],project:[],team:[]},totals:{usage:null,project:null,team:null},before:{},complete:false,reduction:false,changed:false,missing:[],source_status:'no-records'};
  const preview={ok:true,preview_id:'read-empty',projects:[project],unmapped_projects:[],counts:{usage:0,project:0,team:0}};
  assert.equal(readI8Preview(preview).projects[0].source_status,'no-records');
  for(const corrupt of [{...project,complete:true},{...project,totals:{usage:'0.00',project:null,team:null}},{...project,source_status:'unknown'}])assert.throws(()=>readI8Preview({...preview,projects:[corrupt]}));
  assert.doesNotThrow(()=>readI8Preview({...preview,projects:[{...project,source_status:'available',complete:true,reduction:true,totals:{usage:'0.00',project:'0.00',team:'0.00'}}]}));
});
