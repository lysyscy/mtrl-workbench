import { useEffect, useRef, useState } from 'react';
import { Button, Checkbox, Input, Select } from 'antd';
import { requestJson } from './api';
import { body } from './notices-api';
import { MechanicalDialog } from './mechanical-details';
import { detailSum, mechanicalMoney as money, readI8Preview, readWorkResult } from './mechanical-api';
import type { Workbench, Relation, SourceRow, Discovery, Matter, I8Preview } from './mechanical-api';

const kinds = [['usage','班组使用累计'],['project','项目结算累计'],['team','班组审批累计']] as const;
const metadataLabels: Record<string,string> = {origin:'关联月份',due:'约定月份',amount:'约定金额',mode:'处理方式',evidence:'依据',status:'历史状态',flow:'核查进度',reply:'项目回复'};
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
  return <>{kinds.map(([kind,label])=><details key={kind}><summary>{label}（{sources[kind]?.length??0}条）</summary><div className="mechanical-work-table"><table><thead><tr><th>单号</th><th>来源周期</th><th>本期结算额</th><th>本期审批额</th></tr></thead><tbody>{sources[kind]?.map(row=><tr key={row.id}><td>{row.bill||row.id}</td><td>{row.periodName||row.periodKey||'未可靠映射'}</td><td className="money">{money(row.amount)}</td><td className="money">{money(row.approval)}</td></tr>)}</tbody></table></div></details>)}</>;
}
export function MechanicalWork({ data, warehouses, label, writable, busy, operate, refresh, added }: {
  data: Workbench; warehouses: string[]; label: (warehouse:string)=>string; writable:boolean; busy:boolean;
  operate:(action:()=>Promise<void>)=>Promise<void>; refresh:()=>Promise<boolean>; added:(warehouse:string)=>void;
}) {
  const [filter,setFilter]=useState<'pending'|'findings'|'all'>('pending');
  const [dialog,setDialog]=useState<'fetch'|'basis'|'history'|'matters'|'edit'|'discovery'|null>(null);
  const [warehouse,setWarehouse]=useState('');
  const [preview,setPreview]=useState<I8Preview|null>(null);
  const [selected,setSelected]=useState<string[]>([]);
  const [allowReduction,setAllowReduction]=useState(false),[reason,setReason]=useState('');
  const [matter,setMatter]=useState<Partial<Matter>>({}),[discovery,setDiscovery]=useState<Discovery|null>(null),[note,setNote]=useState('');
  const [feedback,setFeedback]=useState('');
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
      try {await action();if(!mounted.current||currentScope.current!==scope){await refresh();return;}after?.();setFeedback(message);if(!await refresh()&&mounted.current&&currentScope.current===scope)setFeedback(message+' 重新读取失败，请先重新读取。');}
      catch(error){await refresh();if(mounted.current&&currentScope.current===scope)setFeedback(error instanceof Error?error.message:'操作未完成，请重新核对后再试。');}
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
        if(!refreshed){setFeedback('取数预览已取得，重新读取失败；请重新读取后再抓取。');return;}
        setPreview(result);setSelected(result.projects.filter(p=>p.complete&&(!wh||p.warehouse===wh)).map(p=>p.warehouse));
      }catch(error){await refresh();if(mounted.current&&currentScope.current===scope)setFeedback(error instanceof Error?error.message:'取数失败，请重试。');}
    });}finally{lock.current=false;if(mounted.current)setWorking(false);}
  }
  function table(items:string[]) {
    return <div className="mechanical-work-table"><table className="mechanical-check-table"><thead><tr><th rowSpan={2}>项目</th><th colSpan={3}>报表核对</th><th colSpan={3}>i8内部核对</th><th rowSpan={2}>结算／审批不同</th><th rowSpan={2}>跟进事项</th><th rowSpan={2}>操作</th></tr><tr><th>报表费用累计</th><th>班组使用累计<br/>（含i6历史数据）</th><th>待处理差额</th><th>班组使用累计</th><th>项目结算＋班组审批</th><th>待处理差额</th></tr></thead><tbody>{items.map(wh=><tr key={wh}><th>{label(wh)}<small>{snapshotTime(relations(wh)[0]?.fetched_at)||(hasData(wh)?'尚未取数':'尚未录入')}</small>{filter==='findings'&&findings.filter(d=>d.warehouse===wh).map(d=><Button key={d.id} className="mechanical-link" disabled={blocked} onClick={()=>{setDiscovery(d);setNote(d.note||'');open('discovery',wh);}}>{d.kind==='first'?'首次取数，核实':'取数变化，核实'}</Button>)}</th>{(['report','internal'] as const).flatMap(relation=>{
      const row=relations(wh).find(r=>r.relation===relation);return [<td key={relation+'left'} className="money">{money(row?.left)}</td>,<td key={relation+'right'} className="money">{money(row?.right)}</td>,<td key={relation+'pending'} className={`money ${nonzero(row?.pending)?'mechanical-difference':''}`}>{money(row?.pending)}{row?.pending==null?hasData(wh)&&<small>{row?.fetched_at?'待核对':'待取数'}</small>:nonzero(row.pending)?<Button className="mechanical-link" disabled={!writable||blocked} onClick={()=>ignore(row,false)}>忽略新增差额</Button>:nonzero(row.ignored)?<Button className="mechanical-link" disabled={!writable||blocked} onClick={()=>ignore(row,true)}>已忽略，撤销</Button>:null}</td>];
    })}<td>{documents(wh).map(document=><div className={document.ignored?'':'mechanical-difference'} key={document.fact}><div>结 {money(document.settlement)}<br/>审 {money(document.approval)}</div><Button className="mechanical-link" disabled={!writable||blocked} onClick={()=>void commit(()=>post('document-ignore',{warehouse:wh,document_id:document.document_id,fact:document.fact,revision:document.revision,undo:document.ignored}),document.ignored?'已恢复该单差额提醒。':'已忽略该单这次结算／审批差额。')}>{document.ignored?'已忽略，撤销':'忽略此单差额'}</Button><small>{document.bill||document.id}，{document.periodName||document.periodKey||'周期未取得'}</small></div>)}</td><td><Button className="mechanical-link" disabled={blocked} onClick={()=>open('matters',wh)}>{matters(wh).some(m=>!m.completed)?matters(wh).filter(m=>!m.completed).length+'项未完成':'记录跟进'}</Button><small>{matters(wh).find(m=>!m.completed)?.text}</small></td><td><Button disabled={!writable||blocked} onClick={()=>void fetchPreview(wh)}>更新i8</Button><Button disabled={blocked} onClick={()=>open('basis',wh)}>依据</Button>{filter==='findings'&&!warehouses.includes(wh)&&<Button disabled={!writable||blocked} onClick={()=>void commit(()=>post('settings',{revision:data.settings.revision,shown_projects:[...new Set([...data.shown,wh])]}),'已加入显示名单，金额保持原样。',()=>added(wh))}>加入显示</Button>}</td></tr>)}</tbody></table>{!items.length&&<p className="state">当前范围没有此类项目。</p>}</div>;
  }
  const basis=relations(warehouse),snapshot=data.i8.find(s=>s.warehouse===warehouse),history=data.histories.find(h=>h.warehouse===warehouse);
  const reduction=preview?.projects.some(p=>selected.includes(p.warehouse)&&p.reduction)??false;
  const reviewProjects=preview?.projects??[];
  return <div className="mechanical-work">
    <div className="mechanical-work-tools"><div role="group" aria-label="核对筛选">{([['pending','待处理'],['findings',`取数变化（${findings.length}）`],['all','全部显示项目']] as const).map(([id,name])=><Button key={id} disabled={blocked} aria-pressed={filter===id} onClick={()=>setFilter(id)}>{name}</Button>)}</div><div><Button disabled={blocked} onClick={()=>open('history')}>i6历史数据</Button><Button disabled={!writable||blocked} onClick={()=>void fetchPreview()}>抓取i8</Button></div></div>
    <p className="muted">核对当前累计，不随查看月份截断。累计差额与单据差额分别处理；原始差额和忽略留底见“依据”。抓取可能重新登录 i8，并使该账号其他会话下线。</p>
    {filter==='findings'&&findings.some(d=>!d.warehouse)&&<section><h3>归属待确认</h3><div className="mechanical-work-table"><table><thead><tr><th>i8项目</th>{kinds.map(([k,n])=><th key={k}>{n}</th>)}<th>操作</th></tr></thead><tbody>{findings.filter(d=>!d.warehouse).map(d=><tr key={d.id}><th>{d.projectName||d.projectId}</th>{kinds.map(([k])=><td className="money" key={k}>{money(d.totals?.[k])}</td>)}<td><Button disabled={blocked} onClick={()=>{setDiscovery(d);setNote(d.note||'');open('discovery');}}>核实发现</Button></td></tr>)}</tbody></table></div></section>}
    {table(rows)}{normal.length>0&&<details><summary>已对平／已忽略（{normal.length}）</summary>{table(normal)}</details>}
    {feedback&&!dialog&&<p className="notice" role="status">{feedback}</p>}
    {dialog&&<MechanicalDialog className={dialog==='fetch'?'mechanical-i8-dialog':dialog==='edit'||dialog==='discovery'?'mechanical-note-dialog':''} title={dialog==='fetch'?(warehouse?'更新本项目i8累计':'抓取 i8，累计变化核对'):dialog==='basis'?'核对依据，'+label(warehouse):dialog==='history'?'i6历史数据':dialog==='matters'?'跟进事项，'+label(warehouse):dialog==='edit'?(matter.id?'处理跟进事项':'新增跟进事项'):'取数变化，'+(discovery?.warehouse?label(discovery.warehouse):discovery?.projectName||discovery?.projectId||'')} busy={blocked} close={()=>setDialog(null)}>
      {dialog==='fetch'&&(!preview?<><p>{blocked?'正在抓取 i8 当前累计…':'本次未取得可采用的预览。'}</p><footer><Button disabled={blocked} onClick={()=>setDialog(null)}>关闭</Button>{!blocked&&<Button disabled={!writable} onClick={()=>void fetchPreview(warehouse)}>重新抓取</Button>}</footer></>:<>
        <p>已读取班组使用 {preview.counts.usage} 条、项目结算 {preview.counts.project} 条、班组消耗 {preview.counts.team} 条。确认只更新勾选项目。</p>
        <div className="mechanical-work-table"><table className="mechanical-i8-review"><thead><tr><th rowSpan={2}>采用</th><th rowSpan={2}>项目</th>{kinds.map(([key,name])=><th colSpan={3} key={key}>{name}</th>)}<th rowSpan={2}>状态</th></tr><tr>{kinds.flatMap(([key])=>[<th key={key+'old'}>原值</th>,<th key={key+'new'}>本次取得</th>,<th key={key+'delta'}>变化额</th>])}</tr></thead><tbody>{reviewProjects.map(p=><tr key={p.warehouse}><td><Checkbox aria-label={'采用'+label(p.warehouse)} checked={selected.includes(p.warehouse)} disabled={!p.complete||!writable||blocked} onChange={e=>setSelected(previous=>e.target.checked?[...previous,p.warehouse]:previous.filter(wh=>wh!==p.warehouse))}/></td><th>{label(p.warehouse)}</th>{kinds.flatMap(([key])=>[<td key={key+'old'} className="money">{money(p.before?.totals?.[key])}</td>,<td key={key+'new'} className="money">{money(p.totals[key])}</td>,<td key={key+'delta'} className={`money ${p.complete&&p.before?.totals?.[key]!=null&&p.totals[key]!=null&&Number(p.totals[key])<Number(p.before.totals[key])?'mechanical-reduction':''}`}>{change(p.before?.totals?.[key],p.totals[key],p.complete)}</td>])}<td>{!p.complete?'来源未齐，保留旧值':p.reduction?'含减少，需核实':!p.before||!Object.keys(p.before).length?'首次发现':p.changed?'单据或金额有变化':'未变化'}{p.missing.length>0&&<small>单据减少 {p.missing.length} 条</small>}</td></tr>)}</tbody></table></div>
        {!reviewProjects.length&&<p>本次没有可采用的项目。</p>}{preview.unmapped_projects.length>0&&<p>发现 {preview.unmapped_projects.length} 个未对应档案的项目；在“取数变化”核实来源。</p>}
        {reduction&&<div className="mechanical-reduction-fields"><label><Checkbox checked={allowReduction} disabled={blocked} onChange={e=>setAllowReduction(e.target.checked)}/>已核实查询范围及单据减少</label><label>减少采用依据<Input.TextArea value={reason} disabled={blocked} onChange={e=>setReason(e.target.value)}/></label></div>}
        <footer><Button disabled={blocked} onClick={()=>setDialog(null)}>暂不采用</Button><Button type="primary" disabled={!writable||blocked||!selected.length||(reduction&&(!allowReduction||!reason.trim()))} onClick={()=>void commit(()=>post('i8-confirm',{preview_id:preview.preview_id,warehouses:selected,allow_reduction:allowReduction,reduction_reason:reason}),'已更新所选项目的i8累计。',()=>{setPreview(null);setDialog(null);})}>确认所选项目</Button></footer>
      </>)}
      {dialog==='history'&&<><p>i6仅计入报表核对；退出显示名单后历史依据保留。</p><table><thead><tr><th>项目</th><th>固定i6（元）</th></tr></thead><tbody>{data.relations.filter(r=>r.relation==='report').map(r=><tr key={r.warehouse}><td>{label(r.warehouse)}</td><td className="money">{money(r.i6)}</td></tr>)}</tbody></table></>}
      {dialog==='basis'&&<><table><thead><tr><th>核对关系</th><th>左侧金额</th><th>右侧金额</th><th>原始差额</th><th>忽略留底</th></tr></thead><tbody>{basis.map(r=><tr key={r.relation}><th>{r.relation==='report'?'报表核对':'i8内部核对'}</th>{[r.left,r.right,r.raw,r.ignored].map((value,index)=><td className="money" key={index}>{money(value)}</td>)}</tr>)}</tbody></table><p>取数时间：{snapshotTime(basis[0]?.fetched_at)||'未取得'}，范围：{text(snapshot?.scope)}</p>{history&&<details><summary>历史来源说明</summary><pre>{JSON.stringify(history,null,2)}</pre></details>}<Sources sources={snapshot?.sources??{}}/><footer><Button disabled={blocked} onClick={()=>{const summary=`${label(warehouse)}：请核查机械费。\n取数时间：${basis[0]?.fetched_at||'未取得'}\n`+basis.map(r=>`${r.relation==='report'?'报表核对':'i8内部'}原始差额 ${money(r.raw)} 元，待处理 ${money(r.pending)} 元。`).join('\n')+'\n'+documents(warehouse).map(d=>`单据${d.bill||d.id}，结算${money(d.settlement)}，审批${money(d.approval)}。`).join('\n');void navigator.clipboard.writeText(summary).then(()=>setFeedback('核对摘要已复制，请自行发送。'),()=>setFeedback('复制失败，请手动选择核对内容复制。'));}}>复制核对摘要</Button></footer></>}
      {dialog==='matters'&&<><div className="mechanical-work-tools"><span>事项保存／完成不改变费用或忽略记录。</span><Button disabled={!writable||blocked} onClick={()=>{setMatter({warehouse,text:''});setDialog('edit');}}>新增跟进</Button></div><table><thead><tr><th>事项／处理备注</th><th>状态</th><th>操作</th></tr></thead><tbody>{matters(warehouse).map(item=><tr key={item.id}><td>{item.text}{Object.entries(metadataLabels).filter(([k])=>item.metadata?.[k]!=null&&item.metadata[k]!=='').map(([key,name])=><small key={key}>{name}：{text(item.metadata[key])}</small>)}</td><td>{item.completed?'已确认完成':'未完成'}</td><td><Button disabled={!writable||blocked} onClick={()=>{setMatter(item);setDialog('edit');setFeedback('');}}>处理</Button></td></tr>)}</tbody></table>{!matters(warehouse).length&&<p>当前项目没有跟进事项。</p>}</>}
      {dialog==='edit'&&<><label>项目<Select aria-label="跟进事项项目" value={matter.warehouse||undefined} placeholder="请选择项目" disabled={blocked} options={data.warehouses.map(wh=>({value:wh,label:label(wh)}))} onChange={value=>setMatter({...matter,warehouse:value??''})}/></label><label>事项／处理备注<Input.TextArea value={matter.text||''} disabled={blocked} onChange={e=>setMatter({...matter,text:e.target.value})}/></label><footer><Button disabled={blocked} onClick={()=>setDialog('matters')}>返回跟进</Button>{[false,true].map(completed=><Button key={String(completed)} disabled={!writable||blocked||!matter.warehouse||!matter.text?.trim()} onClick={()=>void commit(()=>post('matter-save',{id:matter.id,revision:matter.revision??0,warehouse:matter.warehouse,text:matter.text?.trim(),completed}),completed?'事项已确认完成，金额保持原样。':'事项已保存。',()=>{setWarehouse(matter.warehouse!);setDialog('matters');})}>{completed?'确认完成':'保存'}</Button>)}</footer></>}
      {dialog==='discovery'&&discovery&&<><p>{discovery.kind==='unmapped'?'归属尚未唯一确定，金额未分配；请先核实对应项目。':discovery.kind==='first'?'首次发现，不据历史非零直接认定漏报。':discovery.kind==='missing-project'?'原有项目本轮未返回，旧值保留。':'i8单据或金额有变化，请核实报表是否覆盖。'}</p>{discovery.sources&&<Sources sources={discovery.sources}/>}<label>本轮无需补报的核实说明<Input.TextArea value={note} disabled={blocked} onChange={e=>setNote(e.target.value)}/></label><footer><Button disabled={blocked} onClick={()=>setDialog(null)}>返回</Button><Button disabled={!writable||blocked||!note.trim()} onClick={()=>void commit(()=>post('discovery-resolve',{id:discovery.id,revision:discovery.revision,note:note.trim()}),'本轮取数变化已核实，以后有新变化仍会提示。',()=>setDialog(null))}>已核实，本轮无需补报</Button></footer></>}
      {feedback&&<p className="notice" role="status">{feedback}</p>}
    </MechanicalDialog>}
  </div>;
}
