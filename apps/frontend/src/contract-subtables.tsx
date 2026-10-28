import { BusinessDate } from './time-picker';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Pagination from 'antd/es/pagination';
import { useEffect, useId, useRef, useState } from 'react';
import type { Dispatch, ReactNode, SetStateAction } from 'react';
import { useHref, useLinkClickHandler } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, requestJson } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { contractHistoryDate, contractWrite } from './contracts-api';
import type { ContractRow } from './contracts-api';
import { useHistoryGuard } from './history';
import { live, money, readNotices } from './notices-api';
import { draftProblem, emptySubtableDraft, loadSubtables, writeSubtable } from './contract-subtables-api';
import type { SubtableDraft, SubtableKind } from './contract-subtables-api';
import type { InvoiceRow,PaymentDisplayRow } from './contract-subtables-api';
import { ReadGrid } from './business-grid';
import { numberColumnWidth,contentWidth } from './grid';

export interface SubtableState {
  drafts: Record<SubtableKind, SubtableDraft>; busy: boolean; uncertain: boolean; reconciled: boolean; error: string; feedback: string;
  deleting: {kind:SubtableKind;id:number;date:string;amount:string} | null;
  focus: {kind:SubtableKind;id:number} | null;
}
export type SubtableWorkspace = Record<number, SubtableState>;
export type ChangeSubtables = Dispatch<SetStateAction<SubtableWorkspace>>;
export function newSubtableState(historyDate=''): SubtableState { const supplier=emptySubtableDraft();if(historyDate){supplier.date=historyDate;supplier.initialDate=historyDate;}return {drafts:{supplier,trade:emptySubtableDraft(),payment:emptySubtableDraft()},busy:false,uncertain:false,reconciled:false,error:'',feedback:'',deleting:null,focus:null}; }
function NoticeButton({id,children}:{id:number;children:ReactNode}) {
  const to=`/notices?notice=${id}`, href=useHref(to), onClick=useLinkClickHandler<HTMLAnchorElement>(to);
  return <Button size="small" href={href} onClick={onClick}>{children}</Button>;
}
const draftDirty = (d: SubtableDraft) => d.amount !== '' || d.date !== d.initialDate;
export function hasSubtableDrafts(state: SubtableState | undefined): boolean { return Boolean(state && Object.values(state.drafts).some(draftDirty)); }
export function ContractSubtables({ contractId, historyDate, workspace, change, writable, paused, onlyKind, summaryRow, contracts = [], pageSize = 2 }: {
  contractId:number;historyDate:string;workspace:SubtableWorkspace;change:ChangeSubtables;writable:boolean;paused:boolean;onlyKind?:SubtableKind;summaryRow?:ContractRow;contracts?:ContractRow[];pageSize?:number;
}) {
  const client=useQueryClient(), root=useRef<HTMLDivElement>(null), lock=useRef(false), guard=useId();
  const [referencing,setReferencing]=useState(false);
  const focused=useRef<SubtableState['focus']>(null);
  const [pages,setPages]=useState<Record<SubtableKind,number>>({supplier:1,trade:1,payment:1}),[linkPage,setLinkPage]=useState(1);
  const linkPageSize=8;
  const pageFor=(kind:SubtableKind,total:number)=>Math.max(1,Math.min(pages[kind],Math.ceil(total/pageSize)));
  const pageRows=<T,>(kind:SubtableKind,rows:T[])=>rows.slice((pageFor(kind,rows.length)-1)*pageSize,pageFor(kind,rows.length)*pageSize);
  const pagination=(kind:SubtableKind,total:number)=><div className="subtable-pagination"><span>共 {total} 条</span>{total>pageSize&&<Pagination aria-label={`${labels[kind]}明细分页`} size="small" current={pageFor(kind,total)} pageSize={pageSize} total={total} showSizeChanger={false} onChange={page=>setPages(old=>({...old,[kind]:page}))}/>}</div>;
  const labels:Record<SubtableKind,string>={supplier:historyDate?'历史未结金额':'供应商发票',trade:'贸易公司发票',payment:'手工付款'};
  const state=workspace[contractId], live=useRef({writable,paused});live.current={writable,paused};
  const query=useQuery({queryKey:['contract-subtables',contractId],enabled:!paused,staleTime:0,refetchOnMount:'always',refetchOnWindowFocus:false,retry:false,queryFn:({signal})=>loadSubtables(contractId,signal)});
  function update(fn:(current:SubtableState)=>SubtableState) { change(old=>({...old,[contractId]:fn(old[contractId]??newSubtableState(historyDate))})); }
  useEffect(()=>{change(old=>old[contractId]?old:{...old,[contractId]:newSubtableState(historyDate)});},[contractId,historyDate,change]);
  useHistoryGuard(guard,()=>paused?'':state?.busy?'合同子表正在保存，请稍候。':state?.uncertain?'合同子表结果待核实，请先重读。':hasSubtableDrafts(state)?'合同子表有未保存输入，请先处理。':'');
  useEffect(()=>{
    if(!state?.focus||state.focus===focused.current||query.isFetching||paused)return;
    const rows=state.focus.kind==='payment'?query.data?.payment_display_rows:query.data?.[state.focus.kind==='supplier'?'supplier_invoices':'trade_invoices'];
    const index=rows?.findIndex(row=>row.id===state.focus!.id)??-1;
    if(index>=0) {const page=Math.floor(index/pageSize)+1;if(pages[state.focus.kind]!==page){setPages(old=>({...old,[state.focus!.kind]:page}));return;}}
    const target=root.current?.querySelector<HTMLElement>(`[data-subtable="${state.focus.kind}"][data-row="${state.focus.id}"]`);
    if(target && (!root.current?.contains(document.activeElement)||document.activeElement?.tagName==='BUTTON')) {target.focus({preventScroll:true});target.scrollIntoView({block:'nearest'});}
    if(target) focused.current=state.focus;
  },[state?.focus,query.data,query.isFetching,paused,pages,pageSize]);
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
  function draftRow(kind:SubtableKind) {return state&&<div className="subtable-draft subtable-entry"><label>{kind==='supplier'&&historyDate?'核对截至日':'日期'}<BusinessDate label={kind==='supplier'&&historyDate?'核对截至日':labels[kind]+'日期'} value={state.drafts[kind].date} disabled={!writable||paused||state.busy||state.uncertain} onChange={value=>input(kind,'date',value)}/></label><label>金额（元）<Input aria-label={kind==='supplier'&&historyDate?'历史未结金额（元）':labels[kind]+'金额（元）'} inputMode="decimal" value={state.drafts[kind].amount} disabled={!writable||paused||state.busy||state.uncertain} onChange={e=>input(kind,'amount',e.target.value)}/></label>{kind==='payment'&&<span>手工录入</span>}<div className="subtable-draft-actions"><Button htmlType="button" className="primary" disabled={unavailable} onClick={()=>void save(kind)}>新增{labels[kind]}</Button><Button htmlType="button" disabled={!writable||paused||state.busy||state.uncertain||!draftDirty(state.drafts[kind])} onClick={()=>update(s=>({...s,drafts:{...s.drafts,[kind]:newSubtableState(historyDate).drafts[kind]}}))}>取消</Button></div></div>;}
  function remove(kind:SubtableKind,row:{id:number;date:string;amount:string}) {update(s=>({...s,deleting:{kind,...row}}));}
  const data=query.data;
  const linkedNotices=[...new Set((data?.payments??[]).filter(p=>p.source==='notice').map(p=>p.notice_id!))];
  const currentLinkPage=Math.max(1,Math.min(linkPage,Math.ceil(linkedNotices.length/linkPageSize)));
  const invoiceRows=(kind:'supplier'|'trade')=>data?.[kind==='supplier'?'supplier_invoices':'trade_invoices']??[];
  return <div ref={root} className="contract-subtables" onKeyDown={e=>{if(e.key==='Enter'&&e.target instanceof HTMLInputElement&&!e.nativeEvent.isComposing)e.preventDefault();}} aria-label="合同发票与付款明细">
    <div className="subtable-heading">{!onlyKind&&<h3>发票与付款</h3>}<div className="subtable-tools"><Button htmlType="button" disabled={paused||Boolean(state?.busy)} onClick={()=>void reread()}>重读明细</Button>{onlyKind==='payment'&&<Button htmlType="button" disabled={unavailable} onClick={()=>setReferencing(true)}>从付款域引用</Button>}</div></div>
    {onlyKind&&summaryRow&&<dl className="subtable-summary"><div><dt>供应商</dt><dd>{onlyKind==='trade'?summaryRow.trade_co||'未填':summaryRow.supplier||'未填'}</dd></div><div><dt>材料名</dt><dd>{summaryRow.material||'未填'}</dd></div><div><dt>{onlyKind==='payment'?'结算金额':'合同金额'}</dt><dd className="money">{onlyKind==='payment'?`${money(data?.settle??summaryRow.settle)} 元`:onlyKind==='trade'?(summaryRow.trade_contract_amt===null?'—':`${money(summaryRow.trade_contract_amt)} 元`):`${money(summaryRow.contract_amt)} 元`}</dd></div></dl>}
    {query.isPending?<p role="status">正在读取合同子表…</p>:query.isError?<p className="notice" role="alert">{query.error.message}</p>:null}
    {data&&<>{historyDate&&<p>历史未结金额，核对截至日 {historyDate}；已扣除此前付款，请勿重复录入。</p>}{!onlyKind&&<div className="subtable-totals">{[['结算金额',data.settle],['付款金额',data.pay_sum],['欠款金额',data.debt]].map(([label,value])=><span key={label}>{label}<strong>{money(value!)} 元</strong></span>)}</div>}
      <div className="subtable-invoices">{(['supplier','trade'] as const).filter(kind=>(!onlyKind||kind===onlyKind)&&(kind==='supplier'||data.trade_co||data.trade_invoices.length||state&&draftDirty(state.drafts.trade))).map(kind=><section key={kind} aria-label={labels[kind]}>{!onlyKind&&<h4>{labels[kind]}{kind==='trade'&&data.trade_co?`，${data.trade_co}`:kind==='supplier'&&data.supplier?`，${data.supplier}`:''}</h4>}<ReadGrid table={'contract-invoices-'+kind} className="subtable-invoice-table" label={labels[kind]+'明细'} domLayout="autoHeight" rows={pageRows(kind,invoiceRows(kind))} rowId={row=>String(row.id)} totals={[{id:-1,kind,date:kind==='supplier'&&historyDate?'历史未结合计':'发票合计',amount:kind==='supplier'?data.inv_sum:data.trade_inv_sum}]} columns={[
        {field:'date',headerName:kind==='supplier'&&historyDate?'核对截至日':'发票日期',...contentWidth(110,180),cellRenderer:({data:row,node}:{data:InvoiceRow;node:{rowPinned:unknown}})=>node.rowPinned?row.date:<div tabIndex={-1} data-subtable={kind} data-row={row.id}>{row.date||'日期未填'}</div>},
        {field:'amount',headerName:'金额（元）',...numberColumnWidth([...invoiceRows(kind).map(row=>money(row.amount)),money(kind==='supplier'?data.inv_sum:data.trade_inv_sum)]),cellClass:'money',valueFormatter:p=>money(p.value)},
        {colId:'actions',headerName:'操作',cellRenderer:({data:row,node}:{data:InvoiceRow;node:{rowPinned:unknown}})=>node.rowPinned?null:<Button htmlType="button" danger size="small" disabled={unavailable} onClick={()=>remove(kind,row)}>删除发票</Button>},
      ]}/>{draftRow(kind)}{pagination(kind,invoiceRows(kind).length)}</section>)}</div>
      {(!onlyKind||onlyKind==='payment')&&<section aria-label="合同付款明细">{!onlyKind&&<div className="subtable-heading"><h4>付款明细</h4><Button htmlType="button" disabled={unavailable} onClick={()=>setReferencing(true)}>从付款域引用</Button></div>}<ReadGrid table="contract-payments" className="subtable-payment-table" label="合同付款记录" domLayout="autoHeight" rows={pageRows('payment',data.payment_display_rows)} rowId={row=>row.id+':'+(row.flow_id??row.display_kind)} totals={[{id:-1,date:'合同付款合计',amount:data.pay_sum,source:'manual',notice_id:null,display_kind:'manual'}]} columns={[
        {field:'date',headerName:'付款日期',...contentWidth(110,180),cellRenderer:({data:row,node}:{data:PaymentDisplayRow;node:{rowPinned:unknown}})=>node.rowPinned?row.date:<div tabIndex={-1} data-subtable="payment" data-row={row.id}>{row.date||'日期未填'}{row.display_kind==='stat'&&row.date&&<small>最近实际付款日</small>}</div>},
        {field:'amount',headerName:'金额（元）',...numberColumnWidth([...data.payment_display_rows.map(row=>money(row.amount)),money(data.pay_sum)]),cellClass:'money',valueFormatter:p=>money(p.value)},
        {colId:'source',headerName:'来源与口径',cellRenderer:({data:row,node}:{data:PaymentDisplayRow;node:{rowPinned:unknown}})=>node.rowPinned?null:row.display_kind==='manual'?'手工录入':<span className="subtable-payment-source"><NoticeButton id={row.notice_id!}>查看通知书</NoticeButton><small>{row.display_kind==='flow'?'实际付款（统计一致）':'统计累计，与实际付款有差异'}</small></span>},
        {colId:'actions',headerName:'操作',cellRenderer:({data:row,node}:{data:PaymentDisplayRow;node:{rowPinned:unknown}})=>node.rowPinned?null:row.source==='manual'?<Button htmlType="button" danger size="small" disabled={unavailable} onClick={()=>remove('payment',row)}>删除手工付款</Button>:<span className="muted">回通知书改关联</span>},
      ]}/>{draftRow('payment')}{pagination('payment',data.payment_display_rows.length)}</section>}
      {(!onlyKind||onlyKind==='payment')&&linkedNotices.length>0&&<div className="subtable-linked-group"><div className="subtable-links"><span>已关联通知书</span>{linkedNotices.slice((currentLinkPage-1)*linkPageSize,currentLinkPage*linkPageSize).map((id,index)=><NoticeButton key={id} id={id}>通知书 {(currentLinkPage-1)*linkPageSize+index+1}</NoticeButton>)}</div>{linkedNotices.length>linkPageSize&&<Pagination aria-label="已关联通知书分页" size="small" current={currentLinkPage} pageSize={linkPageSize} total={linkedNotices.length} showSizeChanger={false} onChange={setLinkPage}/>}</div>}
    </>}
    {referencing&&<ContractPaymentReference contractId={contractId} contracts={contracts} paused={paused} writable={writable} state={state} update={update} refresh={refresh} close={()=>setReferencing(false)}/>}
    {state?.deleting&&(!onlyKind||state.deleting.kind===onlyKind)&&<div className="subtable-delete" role="group" aria-label="确认删除子行"><p>删除{labels[state.deleting.kind]}：{state.deleting.date||'日期未填'}，{money(state.deleting.amount)} 元？</p><Button htmlType="button" disabled={state.busy} onClick={()=>update(s=>({...s,deleting:null}))}>取消删除</Button><Button htmlType="button" danger disabled={unavailable} onClick={()=>void save(state.deleting!.kind,true)}>确认删除</Button></div>}
    {state?.busy&&<p role="status">正在处理合同子表…</p>}{state?.feedback&&<p role="status">{state.feedback}</p>}{state?.error&&<p className="notice" role="alert">{state.error}</p>}
    {state?.uncertain&&<div className="subtable-reconcile"><span>先核对已保存行；本次输入保留。</span><Button htmlType="button" disabled={paused||!writable||!state.reconciled||state.busy||query.isFetching||query.isError||!data} onClick={()=>update(s=>({...s,uncertain:false,error:'',deleting:null,feedback:'已确认核对结果，请按需处理保留的输入。'}))}>已核对结果，继续处理</Button></div>}
  </div>;
}

export function ContractSubtableDialog({ scale, row, kind, contracts, workspace, change, paused, writable, close }: {
  scale:number;row:ContractRow;kind:SubtableKind;contracts:ContractRow[];workspace:SubtableWorkspace;change:ChangeSubtables;paused:boolean;writable:boolean;close:()=>void;
}) {
  const state=workspace[row.id], historyDate=contractHistoryDate(row.remark), titleId=useId();
  const [shortViewport,setShortViewport]=useState(()=>window.matchMedia('(max-height:760px)').matches);
  useEffect(()=>{
    const media=window.matchMedia('(max-height:760px)'), changed=()=>setShortViewport(media.matches);
    media.addEventListener('change',changed);changed();
    return ()=>media.removeEventListener('change',changed);
  },[]);
  const compact=shortViewport&&scale>1;
  const closing=useDialogClose({busy:Boolean(state?.busy),dirty:Boolean(state&&draftDirty(state.drafts[kind])),active:!paused,close:()=>{
    change(old=>old[row.id]?{...old,[row.id]:{...old[row.id]!,drafts:{...old[row.id]!.drafts,[kind]:newSubtableState(historyDate).drafts[kind]},deleting:old[row.id]!.deleting?.kind===kind?null:old[row.id]!.deleting}}:old);
    close();
  }});
  const title=kind==='payment'?'付款子表':kind==='trade'?'贸易公司发票子表':historyDate?'历史未结金额':'供应商发票子表';
  return <BusinessModal open={!paused} className={`project-dialog contract-subtable-dialog${compact?' contract-subtable-dialog-compact':''}`} titleId={titleId} requestClose={closing.requestClose}><DialogContents title={title} titleId={titleId} closing={closing}>
    <ContractSubtables contractId={row.id} historyDate={historyDate} contracts={contracts} workspace={workspace} change={change} writable={writable} paused={paused} onlyKind={kind} summaryRow={row} pageSize={compact?1:2}/>
    <div className="dialog-actions"><Button htmlType="button" disabled={Boolean(state?.busy)} onClick={closing.requestClose}>关闭</Button></div>
  </DialogContents></BusinessModal>;
}

function ContractPaymentReference({contractId,contracts,paused,writable,state,update,refresh,close}:{
  contractId:number;contracts:ContractRow[];paused:boolean;writable:boolean;state:SubtableState|undefined;update:(fn:(s:SubtableState)=>SubtableState)=>void;refresh:()=>Promise<void>;close:()=>void;
}) {
  const [selected,setSelected]=useState<number|undefined>(),[saved,setSaved]=useState(false),[error,setError]=useState('');
  const lock=useRef(false),titleId=useId();
  const closing=useDialogClose({busy:Boolean(state?.busy),dirty:!saved&&selected!==undefined,close,active:!paused});
  const query=useQuery({queryKey:['contract-payment-candidates',contractId],enabled:!paused,staleTime:0,refetchOnMount:'always',retry:false,queryFn:async({signal})=>readNotices(await requestJson('/api/m03/notice-list?period=',{signal}))});
  const used=new Set(contracts.flatMap(row=>row.notice_ids));
  const candidates=(query.data??[]).filter(row=>live(row)&&row.category==='jc'&&!used.has(row.notice_id));
  const chosen=candidates.find(row=>row.notice_id===selected);
  const unavailable=paused||!writable||Boolean(state?.busy||state?.uncertain)||saved||query.isFetching||query.isError||!chosen;
  async function reference() {
    if(unavailable||lock.current||!chosen)return;
    lock.current=true;update(s=>({...s,busy:true,error:'',feedback:''}));setError('');let written=false;
    try {
      await contractWrite('/api/m11/link',{notice_id:chosen.notice_id,contract_id:contractId});written=true;setSaved(true);
      update(s=>({...s,feedback:'已从付款域引用，两侧关联已同步。'}));
      await refresh();close();
    } catch(failure) {
      const rejected=failure instanceof ApiError&&failure.code!=='invalid_response'&&(failure.status===200||failure.status>=400&&failure.status<500);
      const message=`${written?'已关联，重读失败，请核对，勿重复引用。':rejected?'未关联。':'关联结果待核实，请重读核对，勿重复引用。'}${failure instanceof Error?failure.message:''}`;
      update(s=>({...s,uncertain:!written&&!rejected,reconciled:false,error:message}));setError(message);
    } finally {lock.current=false;update(s=>({...s,busy:false}));}
  }
  return <BusinessModal open={!paused} className="project-dialog contract-payment-reference" titleId={titleId} requestClose={closing.requestClose}><DialogContents title="从付款域引用付款记录" titleId={titleId} closing={closing}>
    <p>按集采实际供应商核对；同一通知书只能引用一次。</p>
    {query.isPending?<p role="status">正在读取可引用通知书…</p>:query.isError?<p role="alert" className="notice">{query.error.message}<Button htmlType="button" onClick={()=>void query.refetch()}>重读候选</Button></p>:<label className="contract-field">集采通知书<Select aria-label="引用集采通知书" placeholder="请选择通知书" value={selected} disabled={Boolean(state?.busy)||saved||Boolean(state?.uncertain)} onChange={setSelected} getPopupContainer={trigger => (trigger as HTMLElement).closest<HTMLElement>('.ant-modal-container') ?? document.body} options={candidates.map(row=>({value:row.notice_id,label:`${row.bill_no}，${row.jc_supplier||'未录入供应商'}，${money(row.stat_paid)} 元`}))}/></label>}
    {!query.isPending&&!query.isError&&!candidates.length&&<p>没有可引用的通知书。</p>}
    {error&&<p className="notice" role="alert">{error}</p>}
    <div className="dialog-actions"><Button htmlType="button" disabled={Boolean(state?.busy)} onClick={closing.requestClose}>{saved?'关闭':'取消'}</Button>{!saved&&<Button htmlType="button" type="primary" disabled={unavailable} onClick={()=>void reference()}>引用</Button>}</div>
  </DialogContents></BusinessModal>;
}
