import { uncertainWrite } from './api';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import { useEffect, useRef, useState } from 'react';
import type { Identity } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { money } from './notices-api';
import { adjustInventory, effectiveValues, numericFields } from './inventory-api';
import type { Adjustment, CalculationBasis, Inventory, InventoryRow, InventoryValues } from './inventory-api';
import { calculateInventory, editInventory, valueLabels } from './inventory-calculation';

const unchanged=():CalculationBasis=>({amount:'unchanged',tax_total:'unchanged'});
export function InventoryAdjust({row,adjustment,properties,me,paused,close,reload,unknown,onUnknown,missing}: {
  row:InventoryRow; adjustment:Adjustment|undefined; properties:string[]; me:Identity|null; paused:boolean; close:()=>void; reload:()=>Promise<Inventory>;
  unknown:boolean;onUnknown:(value:boolean)=>void;missing:boolean;
}) {
  const initial=()=>({values:effectiveValues(row,adjustment),remark:adjustment?.remark??'',token:row.edit_token});
  const [baseline,setBaseline]=useState(initial),[values,setValues]=useState<InventoryValues>(()=>initial().values);
  const [basis,setBasis]=useState<CalculationBasis>(unchanged),[remark,setRemark]=useState(adjustment?.remark??'');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[feedback,setFeedback]=useState('');
  const [verified,setVerified]=useState(false),[confirmClear,setConfirmClear]=useState(false);
  const actual=useRef<ReturnType<typeof initial>|null>(null),writeAbort=useRef(new AbortController()),lock=useRef(false);
  useEffect(()=>{writeAbort.current=new AbortController();return()=>writeAbort.current.abort();},[]);
  let calculated:InventoryValues|undefined,problem='';
  try {calculated=calculateInventory(values,basis,baseline.values);} catch(e) {problem=e instanceof Error?e.message:'请输入有效数值。';}
  if(!remark.trim()) problem||='调整备注必填。';
  const dirty=JSON.stringify(calculated??values)!==JSON.stringify(baseline.values)||remark!==baseline.remark;
  const closing=useDialogClose({busy,dirty,close,active:!paused});
  const disabled=busy||unknown||!me||missing;
  function readActual(data:Inventory) {
    const source=data.rows.find(r=>r.id===row.id);
    if(!source) throw new Error('原单已不在当前库存，请关闭后核对。');
    const saved=data.adjustments.find(a=>a.row_id===row.id);
    return {values:effectiveValues(source,saved),remark:saved?.remark??'',token:source.edit_token};
  }
  async function write(clear:boolean) {
    if(lock.current||paused||disabled||(!clear&&(!calculated||problem||!dirty))) return;
    lock.current=true;setBusy(true);setError('');setFeedback('');onUnknown(true);let written=false;
    try {
      await adjustInventory(row.id,calculated??values,basis,remark,baseline.token,clear,writeAbort.current.signal);written=true;
      if(writeAbort.current.signal.aborted)return;
      setConfirmClear(false);
      const saved=readActual(await reload());actual.current=saved;
      setValues(saved.values);setRemark(saved.remark);setBaseline(saved);setBasis(unchanged());onUnknown(false);
      if(clear)close();else setFeedback('调整单已保存；原始数据未改，相关报表已标记重读。');
    } catch(e) {
      if(writeAbort.current.signal.aborted)return;
      if(written||uncertainWrite(e)){onUnknown(true);setVerified(false);}else onUnknown(false);
      setError(`${written?'已保存，重读失败。':uncertainWrite(e)?'结果待核实，勿重复提交。':''}${e instanceof Error?e.message:'操作失败。'}`);
    } finally {lock.current=false;setBusy(false);}
  }
  async function reread() {
    if(lock.current||paused)return;lock.current=true;setBusy(true);
    try {actual.current=readActual(await reload());setVerified(true);setFeedback('已重读，请核对当前调整单；输入仍保留。');}
    catch(e){setError(e instanceof Error?e.message:'重读失败。');}
    finally{lock.current=false;setBusy(false);}
  }
  function acceptRead() {
    if(!actual.current)return;
    setBaseline(actual.current);setBasis(unchanged());onUnknown(false);setError('');setVerified(false);
  }
  return <BusinessModal open={!paused} requestClose={closing.requestClose} className="inventory-dialog" titleId="inventory-adjust-title"><DialogContents title={`调整单，${row.doc_no} #${row.seq}`} titleId="inventory-adjust-title" closing={closing}>
    <dl className="inventory-details"><dt>物料 / 规格</dt><dd>{row.material} / {row.spec||'—'}</dd><dt>核算月 / 仓库</dt><dd>{row.ym} / {row.warehouse}</dd><dt>项目全名</dt><dd>{row.project_full_name||'未记录'}</dd></dl>
    <form onSubmit={e=>{e.preventDefault();void write(false);}}>
      {missing&&<p className="notice" role="alert">这条原单已不在当前库存，不能继续调整。请关闭后核对原单。</p>}
      <div className="inventory-fields">{numericFields.map(key=><label key={key}>调整后{valueLabels[key]}<Input className="record-value" aria-label={`调整后${valueLabels[key]}`} value={values[key]} disabled={disabled} onChange={e=>{const next=editInventory(values,basis,key,e.target.value,baseline.values);setValues(next.values);setBasis(next.basis);setConfirmClear(false);}}/><small>原始 {money(row.original_values[key])}</small></label>)}
      <label>调整后物料性质<Select aria-label="调整后物料性质" value={values.material_property} disabled={disabled} options={[...new Set([...properties,values.material_property])].map(value=>({value,label:value||'未分类'}))} onChange={value=>{setValues(old=>({...old,material_property:value}));setConfirmClear(false);}}/><small>原始 {row.original_values.material_property||'未分类'}</small></label></div>
      <label className="inventory-remark">调整备注<Input.TextArea className="record-value" aria-label="调整备注" value={remark} disabled={disabled} onChange={e=>{setRemark(e.target.value);setConfirmClear(false);}} autoSize={{minRows:2,maxRows:4}}/></label>
      <p>数量与两种单价分别联算金额；手填金额反算对应单价并保留手填金额。物料性质用于调整后归类，重抓保留调整单。</p>
      {adjustment?<div className="inventory-trail"><p>留痕：{Object.entries(adjustment.values).map(([key,value])=>`${valueLabels[key as keyof InventoryValues]} ${adjustment.before_values?.[key as keyof InventoryValues]??row.original_values[key as keyof InventoryValues]} → ${value}`).join('；')}</p><p>{adjustment.operator||'未记录操作人'}，{adjustment.changed_at||'未记录时间'}</p><p>{adjustment.remark}</p></div>:<p>当前没有调整单。</p>}
      {feedback&&<p role="status">{feedback}</p>}{error&&<p className="notice" role="alert">{error}{!unknown&&<Button disabled={busy||paused} onClick={()=>void reread()}>重读核对</Button>}{!unknown&&verified&&<Button disabled={busy||paused} onClick={acceptRead}>已核对，继续编辑</Button>}</p>}
      {unknown&&!busy&&<p className="inventory-warning">核对实际结果后再继续。<Button disabled={busy||paused} onClick={()=>void reread()}>重读核对</Button><Button disabled={!verified||busy||paused} onClick={acceptRead}>已核对，继续编辑</Button></p>}
      {confirmClear&&<div className="inventory-trail" role="alert"><p>撤销本条调整单的全部数值和物料性质修正，恢复采用原单。相关统计将重算。</p><Button danger disabled={disabled||paused} onClick={()=>void write(true)}>确认撤销调整单</Button><Button disabled={busy} onClick={()=>setConfirmClear(false)}>保留调整</Button></div>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button>{adjustment&&<Button danger disabled={disabled} onClick={()=>setConfirmClear(true)}>撤销调整单…</Button>}<Button type="primary" htmlType="submit" loading={busy} disabled={paused||disabled||Boolean(problem)||!dirty} title={problem}>保存调整单</Button></div>
      {problem&&<p className="muted">{problem}</p>}
    </form>
  </DialogContents></BusinessModal>;
}
