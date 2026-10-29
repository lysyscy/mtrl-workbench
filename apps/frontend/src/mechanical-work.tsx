import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { Button, Checkbox, Input, Select } from 'antd';
import { requestJson } from './api';
import { body } from './notices-api';
import { MechanicalDialog } from './mechanical-details';
import { detailSum, mechanicalMoney as money, readI8Preview, readWorkResult } from './mechanical-api';
import type { Workbench, Relation, SourceRow, Discovery, Matter, I8Preview } from './mechanical-api';
import { ReadGrid } from './business-grid';
import { numberColumnWidth, textWidth } from './grid';
import { EllipsisText } from './grid-text';
import type { ColDef,ColGroupDef } from 'ag-grid-community';

const kinds = [['usage','班组使用累计'],['project','项目结算累计'],['team','班组审批累计']] as const;
const metadataLabels: Record<string,string> = {origin:'关联月份',due:'约定月份',amount:'约定金额',mode:'处理方式',evidence:'依据',status:'历史状态',flow:'核查进度',reply:'项目回复'};
const AdoptionSelection=createContext<{selected:string[];disabled:boolean;label:(warehouse:string)=>string;toggle:(warehouse:string,checked:boolean)=>void}>(null!);
function AdoptionCheckbox({data:project}:{data:I8Preview['projects'][number]}) {
  const controls=useContext(AdoptionSelection);
  return <Checkbox aria-label={'采用'+controls.label(project.warehouse)} checked={controls.selected.includes(project.warehouse)} disabled={!project.complete||controls.disabled} onChange={e=>controls.toggle(project.warehouse,e.target.checked)}/>;
}
const text = (value: unknown) => typeof value === 'string' ? value : value == null ? '未取得' : JSON.stringify(value);
const nonzero = (value: string | null | undefined) => value != null && Number(value) !== 0;
function snapshotTime(value: string | undefined) {
  if (!value) return;
  const date = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? new Date(value) : null;
  if (!date || !Number.isFinite(date.getTime())) return value;
  const stamp = date.toISOString();
  return <time dateTime={value} title={value}><span style={{whiteSpace:'nowrap'}}>{stamp.slice(0, 10)}</span>{' '}<span style={{whiteSpace:'nowrap'}}>{stamp.slice(11, 19)} UTC</span></time>;
}
function change(before: string | null | undefined, after: string | null | undefined, complete: boolean) {
  if (!complete || after == null) return '待核实';
  if (before == null) return '首次取得';
  const difference = detailSum([after, before.startsWith('-') ? before.slice(1) : '-'+before]);
  return difference === '0.00' ? '未变化' : `${difference?.startsWith('-') ? '' : '+'}${money(difference)}`;
}
function Sources({ sources = {} }: { sources?: Record<string,SourceRow[]> }) {
  return <>{kinds.map(([kind,label])=><details key={kind}><summary>{label}（{sources[kind]?.length??0}条）</summary><ReadGrid table={'mechanical-sources-'+kind} className="mechanical-work-table" label={label+'单据'} domLayout="autoHeight" rows={sources[kind]??[]} rowId={row=>String(row.id)} columns={[
    {colId:'bill',headerName:'单号',valueGetter:p=>p.data!.bill||p.data!.id},
    {colId:'period',headerName:'来源周期',valueGetter:p=>p.data!.periodName||p.data!.periodKey||'未可靠映射'},
    {colId:'amount',headerName:'本期结算额',...numberColumnWidth((sources[kind]??[]).map(row=>money(row.amount))),cellClass:'money',valueGetter:p=>money(p.data!.amount)},
    {colId:'approval',headerName:'本期审批额',...numberColumnWidth((sources[kind]??[]).map(row=>money(row.approval))),cellClass:'money',valueGetter:p=>money(p.data!.approval)},
  ]}/></details>)}</>;
}
export function MechanicalWork({ data, warehouses, label, writable, busy, paused, operate, refresh, added }: {
  data: Workbench; warehouses: string[]; label: (warehouse:string)=>string; writable:boolean; busy:boolean; paused:boolean;
  operate:(action:()=>Promise<void>)=>Promise<void>; refresh:()=>Promise<boolean>; added:(warehouse:string)=>void;
}) {
  const scale=Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))||1;
  const [filter,setFilter]=useState<'pending'|'findings'|'all'>('pending');
  const [dialog,setDialog]=useState<'fetch'|'history'|'matters'|'edit'|'discovery'|null>(null);
  const [warehouse,setWarehouse]=useState('');
  const [preview,setPreview]=useState<I8Preview|null>(null);
  const [selected,setSelected]=useState<string[]>([]);
  const [allowReduction,setAllowReduction]=useState(false),[reason,setReason]=useState('');
  const [matter,setMatter]=useState<Partial<Matter>>({}),[discovery,setDiscovery]=useState<Discovery|null>(null),[note,setNote]=useState('');
  const [feedback,setFeedback]=useState('');
  const [feedbackKind,setFeedbackKind]=useState<'success'|'error'>('success');
  function failed(message:string){setFeedbackKind('error');setFeedback(message);}
  const [working,setWorking]=useState(false);
  const lock=useRef(false),mounted=useRef(true);
  const scopeKey=JSON.stringify(warehouses),currentScope=useRef(scopeKey);currentScope.current=scopeKey;
  const blocked=busy||working;
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{setDialog(null);setPreview(null);setSelected([]);setFeedback('');},[scopeKey]);
  const findings=data.discoveries.filter(d=>d.status==='pending');
  const relations=(wh:string)=>data.relations.filter(r=>r.warehouse===wh);
  const documents=(wh:string)=>data.billDifferences.filter(d=>d.warehouse===wh);
  const matters=(wh:string)=>data.matters.filter(m=>m.warehouse===wh);
  function hasData(wh:string) {
    return relations(wh).some(r=>r.left!=null||r.right!=null)||documents(wh).length>0||data.effective.some(e=>e.warehouse===wh&&Object.values(e.values).some(v=>v!=null))||data.details.some(d=>d.warehouse===wh&&d.rows.length>0)||data.i8.some(s=>s.warehouse===wh&&Object.values(s.sources).some(rows=>rows.length>0));
  }
  const pending=(wh:string)=>(hasData(wh)&&relations(wh).some(r=>r.pending==null||nonzero(r.pending)))||documents(wh).some(d=>!d.ignored)||matters(wh).some(m=>!m.completed);
  const scope=filter==='findings'?data.warehouses.filter(wh=>findings.some(d=>d.warehouse===wh)):warehouses;
  const rows=filter==='pending'?scope.filter(pending):scope;
  const normal=filter==='pending'?scope.filter(wh=>hasData(wh)&&!pending(wh)):[];
  function open(next:typeof dialog,wh='') {if(blocked)return;setFeedback('');setWarehouse(wh);setDialog(next);}
  async function post(action:string,payload:Record<string,unknown>) {
    readWorkResult(await requestJson('/api/m06/workbench/'+action,{method:'POST',...body(payload)}),action,payload);
  }
  async function commit(action:()=>Promise<unknown>, message:string, after?:()=>void) {
    if(!writable||blocked||lock.current)return;
    lock.current=true;setWorking(true);const scope=scopeKey;
    try {await operate(async()=>{
      setFeedback('');
      try {await action();if(!mounted.current||currentScope.current!==scope){await refresh();return;}after?.();setFeedbackKind('success');setFeedback(message);if(!await refresh()&&mounted.current&&currentScope.current===scope)failed(message+' 重新读取失败，请先重新读取。');}
      catch(error){await refresh();if(mounted.current&&currentScope.current===scope)failed(error instanceof Error?error.message:'操作未完成，请重新核对后再试。');}
    });}finally{lock.current=false;if(mounted.current)setWorking(false);}
  }
  function ignore(row:Relation,undo:boolean) {
    void commit(()=>post('ignore',{warehouse:row.warehouse,relation:row.relation,revision:row.revision,raw:row.raw,i8_revision:row.i8_revision,undo}),undo?'已恢复差额提醒。':'已留底忽略金额，以后只提示新增差额。');
  }
  async function fetchPreview(wh='') {
    if(!writable||blocked||lock.current)return;
    lock.current=true;setWorking(true);const scope=scopeKey;
    setWarehouse(wh);setDialog('fetch');setPreview(null);setSelected([]);setAllowReduction(false);setReason('');
    try {await operate(async()=>{
      setFeedback('');
      try {
        const result=readI8Preview(await requestJson('/api/m06/workbench/i8-fetch',{method:'POST',...body({request_id:crypto.randomUUID(),allow_kick:true})}));
        const refreshed=await refresh();
        if(!mounted.current||currentScope.current!==scope)return;
        if(!refreshed){failed('取数预览已取得，重新读取失败；请重新读取后再抓取。');return;}
        setPreview(result);setSelected(result.projects.filter(p=>p.complete&&(!wh||p.warehouse===wh)).map(p=>p.warehouse));
      }catch(error){await refresh();if(mounted.current&&currentScope.current===scope)failed(error instanceof Error?error.message:'取数失败，请重试。');}
    });}finally{lock.current=false;if(mounted.current)setWorking(false);}
  }
  function table(items:string[]) {
    type WorkRow={warehouse:string};
    const columns:(ColDef<WorkRow>|ColGroupDef<WorkRow>)[]=[
      {colId:'project',headerName:'项目',pinned:'left',...textWidth(180,260,scale),valueGetter:p=>label(p.data!.warehouse),cellRenderer:({data}:{data:WorkRow})=>{const wh=data.warehouse;return <><EllipsisText text={label(wh)}/><small>{snapshotTime(relations(wh)[0]?.fetched_at)||(hasData(wh)?'尚未取数':'尚未录入')}</small>{filter==='findings'&&findings.filter(d=>d.warehouse===wh).map(d=><Button key={d.id} className="mechanical-link" disabled={blocked} onClick={()=>{setDiscovery(d);setNote(d.note||'');open('discovery',wh);}}>{d.kind==='first'?'首次取数，核实':'取数变化，核实'}</Button>)}</>;}},
      ...(['report','internal'] as const).map(relation=>({headerName:relation==='report'?'报表核对':'i8内部核对',children:(['left','right','pending'] as const).map((field,index):ColDef<WorkRow>=>({colId:relation+'-'+field,headerName:relation==='report'?['报表费用累计','班组使用累计（含i6历史数据）','待处理差额'][index]!:['班组使用累计','项目结算＋班组审批','待处理差额'][index]!,...numberColumnWidth(items.map(wh=>money(relations(wh).find(r=>r.relation===relation)?.[field]))),minWidth:Math.max(108*scale,numberColumnWidth(items.map(wh=>money(relations(wh).find(r=>r.relation===relation)?.[field]))).minWidth),cellClass:'money',valueGetter:p=>money(relations(p.data!.warehouse).find(r=>r.relation===relation)?.[field]),...(field==='pending'?{cellRenderer:({data}:{data:WorkRow})=>{const wh=data.warehouse,row=relations(wh).find(r=>r.relation===relation);return <div className={nonzero(row?.pending)?'mechanical-difference':''}>{money(row?.pending)}{row?.pending==null?hasData(wh)&&<small>{row?.fetched_at?'待核对':'待取数'}</small>:nonzero(row.pending)?<Button className="mechanical-link" disabled={!writable||blocked} onClick={()=>ignore(row,false)}>忽略新增差额</Button>:nonzero(row.ignored)?<Button className="mechanical-link" disabled={!writable||blocked} onClick={()=>ignore(row,true)}>已忽略，撤销</Button>:null}</div>;}}:{})}))})),
      {colId:'documents',headerName:'结算／审批不同',minWidth:180,initialFlex:1,cellRenderer:({data}:{data:WorkRow})=>{const wh=data.warehouse;return <>{documents(wh).map(document=><div className={document.ignored?'':'mechanical-difference'} key={document.fact}><div>结 {money(document.settlement)}<br/>审 {money(document.approval)}</div><Button className="mechanical-link" disabled={!writable||blocked} onClick={()=>void commit(()=>post('document-ignore',{warehouse:wh,document_id:document.document_id,fact:document.fact,revision:document.revision,undo:document.ignored}),document.ignored?'已恢复该单差额提醒。':'已忽略该单这次结算／审批差额。')}>{document.ignored?'已忽略，撤销':'忽略此单差额'}</Button><small>{document.bill||document.id}，{document.periodName||document.periodKey||'周期未取得'}</small></div>)}</>;}},
      {colId:'matters',headerName:'跟进事项',cellRenderer:({data}:{data:WorkRow})=><><Button className="mechanical-link" disabled={blocked} onClick={()=>open('matters',data.warehouse)}>{matters(data.warehouse).some(m=>!m.completed)?matters(data.warehouse).filter(m=>!m.completed).length+'项未完成':'记录跟进'}</Button><small><EllipsisText text={matters(data.warehouse).find(m=>!m.completed)?.text??''}/></small></>},
      {colId:'actions',headerName:'操作',minWidth:160,cellRenderer:({data:entry}:{data:WorkRow})=>{const wh=entry.warehouse;return <><Button disabled={!writable||blocked} onClick={()=>void fetchPreview(wh)}>更新i8</Button>{filter==='findings'&&!warehouses.includes(wh)&&<Button disabled={!writable||blocked} onClick={()=>void commit(()=>post('settings',{revision:data.settings.revision,shown_projects:[...new Set([...data.shown,wh])]}),'已加入显示名单，金额保持原样。',()=>added(wh))}>加入显示</Button>}</>;}},
    ];
    return <ReadGrid table="mechanical-reconciliation" className="mechanical-work-table" label={items===normal?'已对平／已忽略':'当前累计核对'} domLayout="autoHeight" rows={items.map(warehouse=>({warehouse}))} rowId={row=>row.warehouse} columns={columns} grid={{overlayNoRowsTemplate:'当前范围没有此类项目。'}}/>;
  }
  const reduction=preview?.projects.some(p=>selected.includes(p.warehouse)&&p.reduction)??false;
  const reviewProjects=preview?.projects??[];
  return <div className="mechanical-work">
    <div className="mechanical-work-tools"><div role="group" aria-label="核对筛选">{([['pending','待处理'],['findings',`取数变化（${findings.length}）`],['all','全部显示项目']] as const).map(([id,name])=><Button key={id} disabled={blocked} aria-pressed={filter===id} onClick={()=>setFilter(id)}>{name}</Button>)}</div><div><Button disabled={blocked} onClick={()=>open('history')}>i6历史数据</Button><Button disabled={!writable||blocked} onClick={()=>void fetchPreview()}>抓取i8</Button></div></div>
    <p className="muted">核对当前累计，不随查看月份截断。累计差额与单据差额分别处理。抓取可能重新登录 i8，并使该账号其他会话下线。</p>
    {filter==='findings'&&findings.some(d=>!d.warehouse)&&<section><h3>归属待确认</h3><ReadGrid table="mechanical-unmapped" className="mechanical-work-table" label="归属待确认" domLayout="autoHeight" rows={findings.filter(d=>!d.warehouse)} rowId={d=>String(d.id)} columns={[
      {colId:'project',headerName:'i8项目',valueGetter:p=>p.data!.projectName||p.data!.projectId},
      ...kinds.map(([kind,name])=>({colId:kind,headerName:name,...numberColumnWidth(findings.filter(d=>!d.warehouse).map(d=>money(d.totals?.[kind]))),cellClass:'money',valueGetter:(p:{data:Discovery|undefined})=>money(p.data!.totals?.[kind])})),
      {colId:'actions',headerName:'操作',cellRenderer:({data:d}:{data:Discovery})=><Button disabled={blocked} onClick={()=>{setDiscovery(d);setNote(d.note||'');open('discovery');}}>核实发现</Button>},
    ]}/></section>}
    {table(rows)}{normal.length>0&&<details><summary>已对平／已忽略（{normal.length}）</summary>{table(normal)}</details>}
    {feedback&&!dialog&&<p className={'notice'+(feedbackKind==='success'?' mechanical-success':'')} role={feedbackKind==='success'?'status':'alert'}>{feedback}</p>}
    {dialog&&<MechanicalDialog className={dialog==='fetch'?'mechanical-i8-dialog':dialog==='edit'||dialog==='discovery'?'mechanical-note-dialog':''} title={dialog==='fetch'?(warehouse?'更新本项目i8累计':'抓取 i8，累计变化核对'):dialog==='history'?'i6历史数据':dialog==='matters'?'跟进事项，'+label(warehouse):dialog==='edit'?(matter.id?'处理跟进事项':'新增跟进事项'):'取数变化，'+(discovery?.warehouse?label(discovery.warehouse):discovery?.projectName||discovery?.projectId||'')} busy={blocked} paused={paused} close={()=>setDialog(null)}>
      {dialog==='fetch'&&(!preview?<><p>{blocked?'正在抓取 i8 当前累计…':'本次未取得可采用的预览。'}</p><footer><Button disabled={blocked} onClick={()=>setDialog(null)}>关闭</Button>{!blocked&&<Button disabled={!writable} onClick={()=>void fetchPreview(warehouse)}>重新抓取</Button>}</footer></>:<>
        <p>已读取班组使用 {preview.counts.usage} 条、项目结算 {preview.counts.project} 条、班组消耗 {preview.counts.team} 条。确认只更新勾选项目。</p>
        <AdoptionSelection.Provider value={{selected,disabled:!writable||blocked,label,toggle:(warehouse,checked)=>setSelected(previous=>checked?[...new Set([...previous,warehouse])]:previous.filter(wh=>wh!==warehouse))}}><ReadGrid table="mechanical-i8-review" className="mechanical-work-table mechanical-i8-review" label="i8累计采用预览" domLayout="autoHeight" rows={reviewProjects} rowId={p=>p.warehouse} columns={[
      {colId:'pick',headerName:'采用',minWidth:60,maxWidth:80,cellRenderer:AdoptionCheckbox},
      {colId:'project',headerName:'项目',valueGetter:p=>label(p.data!.warehouse)},
      ...kinds.map(([kind,name])=>({headerName:name,children:(['old','new','delta'] as const).map((field,index)=>({colId:kind+'-'+field,headerName:['原值','本次取得','变化额'][index]!,...numberColumnWidth(reviewProjects.map(p=>field==='old'?money(p.before?.totals?.[kind]):field==='new'?money(p.totals[kind]):change(p.before?.totals?.[kind],p.totals[kind],p.complete))),cellClass:'money',valueGetter:(p:{data:I8Preview['projects'][number]|undefined})=>field==='old'?money(p.data!.before?.totals?.[kind]):field==='new'?money(p.data!.totals[kind]):change(p.data!.before?.totals?.[kind],p.data!.totals[kind],p.data!.complete)}))})),
      {colId:'status',headerName:'状态',valueGetter:p=>{const row=p.data!;return (!row.complete?'来源未齐，保留旧值':row.reduction?'含减少，需核实':!row.before||!Object.keys(row.before).length?'首次发现':row.changed?'单据或金额有变化':'未变化')+(row.missing.length?'，单据减少 '+row.missing.length+' 条':'');}},
    ]}/></AdoptionSelection.Provider>
        {!reviewProjects.length&&<p>本次没有可采用的项目。</p>}{preview.unmapped_projects.length>0&&<p>发现 {preview.unmapped_projects.length} 个未对应档案的项目；在“取数变化”核实来源。</p>}
        {reduction&&<div className="mechanical-reduction-fields"><label><Checkbox checked={allowReduction} disabled={blocked} onChange={e=>setAllowReduction(e.target.checked)}/>已核实查询范围及单据减少</label><label>减少采用依据<Input.TextArea value={reason} disabled={blocked} onChange={e=>setReason(e.target.value)}/></label></div>}
        <footer><Button disabled={blocked} onClick={()=>setDialog(null)}>暂不采用</Button><Button type="primary" disabled={!writable||blocked||!selected.length||(reduction&&(!allowReduction||!reason.trim()))} onClick={()=>void commit(()=>post('i8-confirm',{preview_id:preview.preview_id,warehouses:selected,allow_reduction:allowReduction,reduction_reason:reason}),'已更新所选项目的i8累计。',()=>{setPreview(null);setDialog(null);})}>确认所选项目</Button></footer>
      </>)}
      {dialog==='history'&&<><p>i6仅计入报表核对；退出显示名单后历史依据保留。</p><ReadGrid table="mechanical-i6" label="i6历史数据" domLayout="autoHeight" rows={data.relations.filter(r=>r.relation==='report')} rowId={row=>row.warehouse} columns={[
      {colId:'project',headerName:'项目',valueGetter:p=>label(p.data!.warehouse)},
      {field:'i6',headerName:'固定i6（元）',...numberColumnWidth(data.relations.filter(r=>r.relation==='report').map(r=>money(r.i6))),cellClass:'money',valueFormatter:p=>money(p.value)},
    ]}/></>}
      {dialog==='matters'&&<><div className="mechanical-work-tools"><span>事项保存／完成不改变费用或忽略记录。</span><Button disabled={!writable||blocked} onClick={()=>{setMatter({warehouse,text:''});setDialog('edit');}}>新增跟进</Button></div><ReadGrid table="mechanical-matters" label="跟进事项" domLayout="autoHeight" rows={matters(warehouse)} rowId={item=>String(item.id)} columns={[
      {field:'text',headerName:'事项／处理备注',cellRenderer:({data:item}:{data:Matter})=><>{item.text}{Object.entries(metadataLabels).filter(([key])=>item.metadata?.[key]!=null&&item.metadata[key]!=='').map(([key,name])=><small key={key}>{name}：{text(item.metadata[key])}</small>)}</>},
      {colId:'status',headerName:'状态',valueGetter:p=>p.data!.completed?'已确认完成':'未完成'},
      {colId:'actions',headerName:'操作',cellRenderer:({data:item}:{data:Matter})=><Button disabled={!writable||blocked} onClick={()=>{setMatter(item);setDialog('edit');setFeedback('');}}>处理</Button>},
    ]}/>{!matters(warehouse).length&&<p>当前项目没有跟进事项。</p>}</>}
      {dialog==='edit'&&<><label>项目<Select aria-label="跟进事项项目" value={matter.warehouse||undefined} placeholder="请选择项目" disabled={blocked} options={data.warehouses.map(wh=>({value:wh,label:label(wh)}))} onChange={value=>setMatter({...matter,warehouse:value??''})}/></label><label>事项／处理备注<Input.TextArea value={matter.text||''} disabled={blocked} onChange={e=>setMatter({...matter,text:e.target.value})}/></label><footer><Button disabled={blocked} onClick={()=>setDialog('matters')}>返回跟进</Button>{[false,true].map(completed=><Button key={String(completed)} disabled={!writable||blocked||!matter.warehouse||!matter.text?.trim()} onClick={()=>void commit(()=>post('matter-save',{id:matter.id,revision:matter.revision??0,warehouse:matter.warehouse,text:matter.text?.trim(),completed}),completed?'事项已确认完成，金额保持原样。':'事项已保存。',()=>{setWarehouse(matter.warehouse!);setDialog('matters');})}>{completed?'确认完成':'保存'}</Button>)}</footer></>}
      {dialog==='discovery'&&discovery&&<><p>{discovery.kind==='unmapped'?'归属尚未唯一确定，金额未分配；请先核实对应项目。':discovery.kind==='first'?'首次发现，不据历史非零直接认定漏报。':discovery.kind==='missing-project'?'原有项目本轮未返回，旧值保留。':'i8单据或金额有变化，请核实报表是否覆盖。'}</p>{discovery.sources&&<Sources sources={discovery.sources}/>}<label>本轮无需补报的核实说明<Input.TextArea value={note} disabled={blocked} onChange={e=>setNote(e.target.value)}/></label><footer><Button disabled={blocked} onClick={()=>setDialog(null)}>返回</Button><Button disabled={!writable||blocked||!note.trim()} onClick={()=>void commit(()=>post('discovery-resolve',{id:discovery.id,revision:discovery.revision,note:note.trim()}),'本轮取数变化已核实，以后有新变化仍会提示。',()=>setDialog(null))}>已核实，本轮无需补报</Button></footer></>}
      {feedback&&<p className={'notice'+(feedbackKind==='success'?' mechanical-success':'')} role={feedbackKind==='success'?'status':'alert'}>{feedback}</p>}
    </MechanicalDialog>}
  </div>;
}
