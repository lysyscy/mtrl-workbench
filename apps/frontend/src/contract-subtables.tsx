import Button from 'antd/es/button';
import Input from 'antd/es/input';
import { useEffect, useId, useRef } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { Link } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from './api';
import { BoundedTable } from './bounded-table';
import { useHistoryGuard } from './history';
import { money } from './notices-api';
import { draftProblem, emptySubtableDraft, loadSubtables, writeSubtable } from './contract-subtables-api';
import type { SubtableDraft, SubtableKind } from './contract-subtables-api';
import './contract-subtables.css';

export interface SubtableState {
  drafts: Record<SubtableKind, SubtableDraft>; busy: boolean; uncertain: boolean; reconciled: boolean; error: string; feedback: string;
  deleting: {kind:SubtableKind;id:number;date:string;amount:string} | null;
  focus: {kind:SubtableKind;id:number} | null;
}
export type SubtableWorkspace = Record<number, SubtableState>;
export type ChangeSubtables = Dispatch<SetStateAction<SubtableWorkspace>>;
export function newSubtableState(historyDate=''): SubtableState { const supplier=emptySubtableDraft();if(historyDate){supplier.date=historyDate;supplier.initialDate=historyDate;}return {drafts:{supplier,trade:emptySubtableDraft(),payment:emptySubtableDraft()},busy:false,uncertain:false,reconciled:false,error:'',feedback:'',deleting:null,focus:null}; }
const draftDirty = (d: SubtableDraft) => d.amount !== '' || d.date !== d.initialDate;
export function hasSubtableDrafts(state: SubtableState | undefined): boolean { return Boolean(state && Object.values(state.drafts).some(draftDirty)); }
export function ContractSubtables({ contractId, historyDate, workspace, change, writable, paused }: {
  contractId:number;historyDate:string;workspace:SubtableWorkspace;change:ChangeSubtables;writable:boolean;paused:boolean;
}) {
  const client=useQueryClient(), root=useRef<HTMLDivElement>(null), lock=useRef(false), guard=useId();
  const labels:Record<SubtableKind,string>={supplier:historyDate?'历史未结金额':'供应商发票',trade:'贸易公司发票',payment:'手工付款'};
  const state=workspace[contractId], live=useRef({writable,paused});live.current={writable,paused};
  const query=useQuery({queryKey:['contract-subtables',contractId],enabled:!paused,staleTime:0,refetchOnMount:'always',refetchOnWindowFocus:false,retry:false,queryFn:({signal})=>loadSubtables(contractId,signal)});
  function update(fn:(current:SubtableState)=>SubtableState) { change(old=>({...old,[contractId]:fn(old[contractId]??newSubtableState(historyDate))})); }
  useEffect(()=>{change(old=>old[contractId]?old:{...old,[contractId]:newSubtableState(historyDate)});},[contractId,historyDate,change]);
  useHistoryGuard(guard,()=>paused?'':state?.busy?'合同子表正在保存，请稍候。':state?.uncertain?'合同子表结果待核实，请先重读。':hasSubtableDrafts(state)?'合同子表有未保存输入，请先处理。':'');
  useEffect(()=>{
    if(!state?.focus||query.isFetching||paused)return;
    const target=root.current?.querySelector<HTMLElement>(`[data-subtable="${state.focus.kind}"][data-row="${state.focus.id}"]`);
    if(target && (!root.current?.contains(document.activeElement)||document.activeElement?.tagName==='BUTTON')) {target.focus({preventScroll:true});target.scrollIntoView({block:'nearest'});}
  },[state?.focus,query.data,query.isFetching,paused]);
  const unavailable=!writable||paused||!state||state.busy||state.uncertain||query.isFetching||query.isError||!query.data;
  async function refresh() { await client.invalidateQueries({}, {throwOnError:true}); }
  async function save(kind:SubtableKind, deleting=false) {
    if(unavailable||lock.current||!state)return;
    const draft=state.drafts[kind], target=state.deleting;
    if(deleting && (!target||target.kind!==kind))return;
    const problem=deleting?'':draftProblem(draft);
    if(problem){update(s=>({...s,error:`${labels[kind]}：${problem}`}));return;}
    lock.current=true;update(s=>({...s,busy:true,error:'',feedback:''}));let written=false;
    try {
      const id=await writeSubtable(contractId,kind,deleting?null:{...draft},target?.id);
      written=true;
      update(s=>({...s,deleting:null,feedback:deleting?'已删除。':`${labels[kind]}已新增。`,focus:id===null?null:{kind,id},drafts:deleting?s.drafts:{...s.drafts,[kind]:s.drafts[kind].date===draft.date&&s.drafts[kind].amount===draft.amount?newSubtableState(historyDate).drafts[kind]:s.drafts[kind]}}));
      await refresh();
    } catch(failure) {
      const rejected=failure instanceof ApiError&&failure.code!=='invalid_response'&&(failure.status===200||failure.status>=400&&failure.status<500);
      update(s=>({...s,uncertain:!written&&!rejected,reconciled:false,error:`${written?'已保存，重读失败，请重读核对，勿重复保存。':rejected?'未保存。':'未取得保存确认，请重读核对，勿重复操作。'}${failure instanceof Error?failure.message:'请联系维护人员。'}`}));
    } finally {lock.current=false;update(s=>({...s,busy:false}));}
  }
  async function reread() {
    if(lock.current||live.current.paused)return;
    lock.current=true;update(s=>({...s,busy:true}));
    try {await refresh();update(s=>({...s,error:'',reconciled:true,feedback:s.uncertain?'已重读，请对照已保存行与本次输入核对结果。':'已重读，未保存输入保留。'}));}
    catch(failure){update(s=>({...s,error:failure instanceof Error?failure.message:'重读失败。'}));}
    finally{lock.current=false;update(s=>({...s,busy:false}));}
  }
  function input(kind:SubtableKind,key:'date'|'amount',value:string) {update(s=>({...s,drafts:{...s.drafts,[kind]:{...s.drafts[kind],[key]:value}}}));}
  function draftRow(kind:SubtableKind) {return state&&<tr className="subtable-draft"><td><Input type="date" aria-label={kind==='supplier'&&historyDate?'核对截至日':`${labels[kind]}日期`} value={state.drafts[kind].date} disabled={!writable||paused||state.busy||state.uncertain} onChange={e=>input(kind,'date',e.target.value)}/></td><td><Input aria-label={kind==='supplier'&&historyDate?'历史未结金额（元）':`${labels[kind]}金额（元）`} inputMode="decimal" value={state.drafts[kind].amount} disabled={!writable||paused||state.busy||state.uncertain} onChange={e=>input(kind,'amount',e.target.value)}/></td>{kind==='payment'&&<td>手工录入</td>}<td><Button htmlType="button" className="primary" disabled={unavailable} onClick={()=>void save(kind)}>新增{labels[kind]}</Button></td></tr>;}
  function remove(kind:SubtableKind,row:{id:number;date:string;amount:string}) {update(s=>({...s,deleting:{kind,...row}}));}
  const data=query.data;
  return <div ref={root} className="contract-subtables" onKeyDown={e=>{if(e.key==='Enter'&&e.target instanceof HTMLInputElement&&!e.nativeEvent.isComposing)e.preventDefault();}} aria-label="合同发票与付款明细">
    <div className="subtable-heading"><h3>发票与付款</h3><Button htmlType="button" disabled={paused||Boolean(state?.busy)} onClick={()=>void reread()}>重读明细</Button></div>
    {query.isPending?<p role="status">正在读取合同子表…</p>:query.isError?<p className="notice" role="alert">{query.error.message}</p>:null}
    {data&&<>{historyDate&&<p>历史未结金额，核对截至日 {historyDate}；已扣除此前付款，请勿重复录入。</p>}<div className="subtable-totals">{[['结算金额',data.settle],['付款金额',data.pay_sum],['欠款金额',data.debt]].map(([label,value])=><span key={label}>{label}<strong>{money(value!)} 元</strong></span>)}</div>
      <div className="subtable-invoices">{(['supplier','trade'] as const).filter(kind=>kind==='supplier'||data.trade_co||data.trade_invoices.length||state&&draftDirty(state.drafts.trade)).map(kind=><section key={kind} aria-label={labels[kind]}><h4>{labels[kind]}{kind==='trade'&&data.trade_co?` · ${data.trade_co}`:kind==='supplier'&&data.supplier?` · ${data.supplier}`:''}</h4><div className="subtable-scroll"><BoundedTable columns={[{min:10,max:13},{min:10,max:18,flex:1},{min:9,max:12}]}><thead><tr><th scope="col">{kind==='supplier'&&historyDate?'核对截至日':'发票日期'}</th><th scope="col" className="money">金额（元）</th><th scope="col">操作</th></tr></thead><tbody>{data[kind==='supplier'?'supplier_invoices':'trade_invoices'].map(row=><tr key={row.id} tabIndex={-1} data-subtable={kind} data-row={row.id}><td>{row.date||'日期未填'}</td><td className="money">{money(row.amount)}</td><td><Button htmlType="button" danger size="small" disabled={unavailable} onClick={()=>remove(kind,row)}>删除发票</Button></td></tr>)}{draftRow(kind)}</tbody><tfoot><tr><th scope="row">{kind==='supplier'&&historyDate?'历史未结合计':'发票合计'}</th><td className="money">{money(kind==='supplier'?data.inv_sum:data.trade_inv_sum)}</td><td/></tr></tfoot></BoundedTable></div></section>)}</div>
      <section aria-label="合同付款明细"><h4>付款明细</h4><div className="subtable-scroll"><BoundedTable columns={[{min:10,max:13},{min:10,max:18},{min:14,max:32,flex:1},{min:9,max:13}]}><thead><tr><th scope="col">付款日期</th><th scope="col" className="money">金额（元）</th><th scope="col">来源与口径</th><th scope="col">操作</th></tr></thead><tbody>{data.payment_display_rows.map(row=><tr key={`${row.id}:${row.flow_id??row.display_kind}`} tabIndex={-1} data-subtable="payment" data-row={row.id}><td>{row.date||'日期未填'}{row.display_kind==='stat'&&row.date&&<small>最近实际付款日</small>}</td><td className="money">{money(row.amount)}</td><td>{row.display_kind==='manual'?'手工录入':<><Link to={`/notices?notice=${row.notice_id}`}>查看通知书</Link><small>{row.display_kind==='flow'?'实际付款（统计一致）':'统计累计 · 与实际付款有差异'}</small></>}</td><td>{row.source==='manual'?<Button htmlType="button" danger size="small" disabled={unavailable} onClick={()=>remove('payment',row)}>删除手工付款</Button>:<span className="muted">回通知书改关联</span>}</td></tr>)}{draftRow('payment')}</tbody><tfoot><tr><th scope="row">合同付款合计</th><td className="money">{money(data.pay_sum)}</td><td colSpan={2}/></tr></tfoot></BoundedTable></div></section>
      {data.payments.some(p=>p.source==='notice')&&<div className="subtable-links"><span>已关联通知书</span>{[...new Set(data.payments.filter(p=>p.source==='notice').map(p=>p.notice_id!))].map((id,index)=><Link key={id} to={`/notices?notice=${id}`}>通知书 {index+1}</Link>)}</div>}
    </>}
    {state?.deleting&&<div className="subtable-delete" role="group" aria-label="确认删除子行"><p>删除{labels[state.deleting.kind]}：{state.deleting.date||'日期未填'}，{money(state.deleting.amount)} 元？</p><Button htmlType="button" disabled={state.busy} onClick={()=>update(s=>({...s,deleting:null}))}>取消删除</Button><Button htmlType="button" danger disabled={unavailable} onClick={()=>void save(state.deleting!.kind,true)}>确认删除</Button></div>}
    {state?.busy&&<p role="status">正在处理合同子表…</p>}{state?.feedback&&<p role="status">{state.feedback}</p>}{state?.error&&<p className="notice" role="alert">{state.error}</p>}
    {state?.uncertain&&<div className="subtable-reconcile"><span>先核对已保存行；本次输入保留。</span><Button htmlType="button" disabled={paused||!writable||!state.reconciled||state.busy||query.isFetching||query.isError||!data} onClick={()=>update(s=>({...s,uncertain:false,error:'',deleting:null,feedback:'已确认核对结果，请按需处理保留的输入。'}))}>已核对结果，继续处理</Button></div>}
  </div>;
}
