import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Segmented from 'antd/es/segmented';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { Link } from 'react-router';
import { readProjects, requestJson } from './api';
import type { Identity, Project } from './api';
import { pageGridGeometry, contentWidth, fitGridColumns, gridTheme } from './grid';
import { ProjectPicker } from './ledger-controls';
import { useHistoryGuard } from './history';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { money } from './notices-api';
import { uncertainWrite } from './api';
import { categories, getProcess, manualProcess, mechKeys, mechLabels, saveProcess, tabLabels } from './process-api';
import type { Difference, ProcessRow } from './process-api';
import { ProcessExport } from './process-export';
import './process.css';

interface Draft { warehouse:string; ym:string; column:string; value:string; revision:number; error:string }
const keyOf=(warehouse:string,ym:string,column:string)=>JSON.stringify([warehouse,ym,column]);
const show=(value:unknown)=>value==null?'':money(String(value));
const matrixColumns=[
  ...['in','out'].flatMap((direction,i)=>categories.map((label,j)=>({field:`${direction}_${label}`,label:`${i?'出库':'入库'}${label}`,segment:j===0}))),
  ...mechKeys.map((field,i)=>({field,label:mechLabels[i]!,segment:i===0||i===4})),
];
interface Cells { drafts:Record<string,Draft>; warehouse:string; disabled:boolean; source:(ym:string,column:string)=>boolean; change:(ym:string,column:string,value:string)=>void; save:(key:string,retry?:boolean)=>void; switchSource:(ym:string,column:string)=>void }
const ProcessCells=createContext<Cells|null>(null);
function MechanicalCell({data,column}:{data:ProcessRow;column:string}) {
  const cells=useContext(ProcessCells)!;
  const label=mechLabels[mechKeys.indexOf(column)]!,key=keyOf(cells.warehouse,data.ym,column),draft=cells.drafts[key];
  if(cells.source(data.ym,column)) return <div className="process-cell"><span>{show(data[column])}</span><small>明细确认</small><Button size="small" disabled={cells.disabled} onClick={()=>cells.switchSource(data.ym,column)}>切为手填</Button></div>;
  return <div className={`process-cell${draft?' process-dirty':''}`}><Input aria-label={`${data.ym} ${label}`} value={draft?.value??data[column]??''} disabled={cells.disabled} style={{width:`${Math.max(11,(draft?.value??data[column]??'').length+1)}ch`}}
    status={draft?.error?'error':''} title={draft?.error||(draft?'未保存':'手填；清空按 0 保存')} onChange={e=>cells.change(data.ym,column,e.target.value)} onBlur={()=>cells.save(key)}
    onKeyDown={e=>{e.stopPropagation();if(e.nativeEvent.isComposing)return;if(e.key==='Enter'){e.preventDefault();cells.save(key,true);}}} />{draft&&<small>{draft.error?'未保存':'待保存'}</small>}</div>;
}
export function ProcessPage({me,blocked,active}:{me:Identity|null;blocked:boolean;active:boolean}) {
  const writeAbort = useRef(new AbortController());
  useEffect(() => { writeAbort.current = new AbortController(); return () => writeAbort.current.abort(); }, []);
  const client=useQueryClient(),root=useRef<HTMLDivElement>(null),alive=useRef(true),lock=useRef(false),queue=useRef<string[]>([]),revision=useRef(0);
  const [warehouse,setWarehouse]=useState(''),[tab,setTab]=useState(1);
  const [drafts,setDrafts]=useState<Record<string,Draft>>({}),[busy,setBusy]=useState(false),[uncertain,setUncertain]=useState(false),[verified,setVerified]=useState(false);
  const [error,setError]=useState(''),[feedback,setFeedback]=useState(''),[source,setSource]=useState<{warehouse:string;ym:string;column:string;signature:string;value:string|null}|null>(null);
  const query=useQuery({queryKey:['process'],enabled:active&&!blocked,queryFn:({signal})=>getProcess(signal)});
  const projects=useQuery({queryKey:['projects','all'],enabled:active&&!blocked,queryFn:async({signal})=>readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  const candidates=useMemo(()=>query.data?.projects.map((key,index):Project=>projects.data?.find(p=>p.warehouse_name===key)??{id:-index-1,disp:`未建档项目 ${index+1}`,name_full:'',warehouse_name:key,project_type:'normal',status:'active',ord:index,phid:''})??[],[query.data,projects.data]);
  useEffect(()=>{if(!warehouse&&query.data?.projects[0])setWarehouse(query.data.projects[0]);},[warehouse,query.data]);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;queue.current=[];};},[]);
  useEffect(()=>{if(!active||blocked)queue.current=[];},[active,blocked]);
  const state=useRef({drafts,active,blocked,uncertain,warehouse,data:query.data});state.current={drafts,active,blocked,uncertain,warehouse,data:query.data};
  function update(next:Record<string,Draft>){state.current.drafts=next;setDrafts(next);}
  const name=(key:string)=>candidates.find(p=>p.warehouse_name===key)?.disp??'项目';
  const detailSource=(ym:string,column:string)=>query.data?.sources[warehouse]?.[ym]?.[column]?.mode==='detail';
  useHistoryGuard('process',()=>lock.current?'过程资料正在保存，请稍候。':uncertain?'过程资料结果待核实，请先重读核对。':Object.keys(state.current.drafts).length?'过程资料有未保存输入，请先处理。':'');
  async function reload(){
    await client.cancelQueries({queryKey:['process'],exact:true});
    const data=await client.fetchQuery({queryKey:['process'],staleTime:0,queryFn:({signal})=>getProcess(signal)});
    await client.invalidateQueries({predicate:q=>q.queryKey[0]!=='process'});return data;
  }
  function change(ym:string,column:string,value:string){
    const key=keyOf(warehouse,ym,column);
    update({...state.current.drafts,[key]:{warehouse,ym,column,value,revision:++revision.current,error:''}});
  }
  async function drain(){
    if(lock.current||!state.current.active||state.current.blocked||state.current.uncertain||!me)return;
    const key=queue.current.shift();if(!key)return;
    const draft=state.current.drafts[key];if(!draft){void drain();return;}
    const {warehouse:wh,ym,column,value}=draft;
    if(state.current.data?.sources[wh]?.[ym]?.[column]?.mode==='detail'){
      update({...state.current.drafts,[key]:{...draft,error:'当前为明细确认，请先切为手填。'}});void drain();return;
    }
    lock.current=true;setBusy(true);setError('');setFeedback('');let written=false;
    try{
      await saveProcess(wh,ym,column,value,writeAbort.current.signal);written=true;if(!alive.current)return;
      const next={...state.current.drafts};if(next[key]?.revision===draft.revision)delete next[key];update(next);
      await reload();if(alive.current&&state.current.warehouse===wh)setFeedback(`${name(wh)} · ${ym} ${mechLabels[mechKeys.indexOf(column)]}已保存`);
    }catch(e){if(!alive.current)return;const message=e instanceof Error?e.message:'保存失败，请重试。';
      if(written||uncertainWrite(e)){state.current.uncertain=true;setUncertain(true);setVerified(false);queue.current=[];setError(`${name(wh)} · ${ym} ${written?'已保存，重读失败。':'保存结果待核实。'}${message}请重读核对，勿重复提交。`);}
      else{const next={...state.current.drafts};if(next[key])next[key]={...next[key],error:message};update(next);if(state.current.warehouse===wh)setError(message);}
    }finally{lock.current=false;if(alive.current){setBusy(false);void drain();}}
  }
  function save(key:string,retry=false){
    const draft=state.current.drafts[key];if(!draft||draft.error&&!retry||state.current.uncertain||state.current.blocked||!state.current.active||query.isError)return;
    if(!queue.current.includes(key))queue.current.push(key);void drain();
  }
  async function reread(){
    if(lock.current||blocked||!active)return;
    try{await reload();if(alive.current){setVerified(true);setError('');setFeedback(uncertain?'已重读，请核对刚才的保存结果。':'已重读，未保存输入仍保留。');}}
    catch(e){if(alive.current)setError(e instanceof Error?e.message:'重读失败。');}
  }
  async function switchManual(){
    if(!source||lock.current||disabled)return;
    lock.current=true;setBusy(true);setError('');let written=false;
    try{await manualProcess(source.warehouse,source.ym,source.column,source.signature,writeAbort.current.signal);written=true;if(!alive.current)return;await reload();if(alive.current){setSource(null);setFeedback('已切为手填，金额保留。');}}
    catch(e){if(!alive.current)return;const unknown=written||uncertainWrite(e);state.current.uncertain=unknown;setUncertain(unknown);setVerified(false);setError(`${written?'已切换，重读失败。':''}${e instanceof Error?e.message:'切换失败。'}`);if(unknown)setSource(null);}
    finally{lock.current=false;if(alive.current)setBusy(false);}
  }
  const disabled=blocked||!active||!me||uncertain||query.isError||projects.isError;
  const paused=blocked||!active;
  const closing=useDialogClose({busy,dirty:false,close:()=>setSource(null),active:Boolean(source)&&active});
  const matrix=query.data?.matrices[warehouse],kind=tab===0?'raw':'adjusted',scale=Number(me?.ui_scale_css??1);
  const diffs=useMemo<ColDef<Difference>[]>(()=>[
    ...(['doc_no','seq','material','warehouse','before','after','delta','remark','operator','at'] as const).map((field,i):ColDef<Difference>=>({field,headerName:['单据编号','序号','物料','仓库','原值（i8）','调整后','差额','备注','操作人','时间'][i]!,...(field==='doc_no'?{pinned:'left' as const}:{}),...contentWidth(field==='seq'?52:['before','after','delta'].includes(field)?130:field==='operator'?96:['material','warehouse','at'].includes(field)?128:140,field==='seq'?80:260,scale,field==='remark'?1:0),wrapText:true,autoHeight:true,...(['before','after','delta'].includes(field)?{cellClass:'money',valueFormatter:(p:{value:unknown})=>show(p.value)}:{})})),
    {colId:'locate',headerName:'操作',pinned:'right',...contentWidth(100,130,scale),cellRenderer:(p:ICellRendererParams<Difference>)=>p.data&&!p.node.rowPinned&&<Link className="row-button" to={`/inventory?row=${p.data.id}`}>定位原行</Link>},
  ],[scale]);
  const dirty=Object.keys(drafts).length>0,reason=uncertain?'先重读核对保存结果':busy?'正在保存':dirty?'先处理未保存输入':query.isError||projects.isError?'先重读资料':query.isFetching?'正在重读':'';
  const currentDrafts=Object.entries(drafts).filter(([,d])=>d.warehouse===warehouse);
  return <section className="process-page" aria-label="过程资料">
    <div className="process-toolbar"><h2>过程资料</h2><ProcessExport projects={candidates} current={warehouse} tab={tab} paused={paused} reason={reason} /></div>
    <div className="process-filters"><span>项目</span><ProjectPicker label="过程资料项目" projects={candidates} selected={candidates.filter(p=>p.warehouse_name===warehouse).map(p=>p.id)} pick={ids=>{const p=candidates.find(p=>p.id===ids[0]);if(p?.warehouse_name){setWarehouse(p.warehouse_name);setError('');setFeedback('');}}} disabled={paused||projects.isPending||projects.isError||query.isPending} /></div>
    <div className="process-tabs"><Segmented aria-label="过程资料表" value={tab} options={tabLabels.map((label,value)=>({label:value===2?<span>{label}{matrix&&<span className="process-diff-count">{matrix.diffs.length}</span>}</span>:label,value}))} onChange={value=>setTab(Number(value))} disabled={paused} />{dirty&&<span>{Object.keys(drafts).length} 项未保存</span>}{query.isFetching&&!query.isPending&&<span role="status">正在重读…</span>}</div>
    {(error||query.isError||projects.isError||uncertain)&&<p className="notice" role="alert">{error||query.error?.message||projects.error?.message}{(error||query.isError||uncertain)&&<Button disabled={paused||busy||query.isFetching} onClick={()=>void reread()}>重读资料</Button>}{projects.isError&&<Button disabled={paused||projects.isFetching} onClick={()=>void projects.refetch()}>重读项目</Button>}</p>}
    {feedback&&<p role="status">{feedback}</p>}
    {uncertain&&<p className="notice" role="alert">核对结果后再继续。<Button disabled={paused||busy||!verified||query.isFetching||query.isError} onClick={()=>{state.current.uncertain=false;setUncertain(false);setError('');setFeedback('已确认，请核对保留输入后再保存。');}}>已核对，保留输入继续</Button></p>}
    {currentDrafts.filter(([,d])=>d.error).map(([key,d])=><p key={key} role="alert" className="notice">{d.ym} {mechLabels[mechKeys.indexOf(d.column)]}：{d.error}<Button disabled={disabled||busy} onClick={()=>save(key,true)}>重试保存</Button><Button disabled={paused||busy||uncertain} onMouseDown={e=>e.preventDefault()} onClick={()=>{const next={...state.current.drafts};delete next[key];update(next);}}>取消这项修改</Button></p>)}
    {currentDrafts.length>0&&<Button disabled={paused||busy||uncertain} onMouseDown={e=>e.preventDefault()} onClick={()=>update(Object.fromEntries(Object.entries(state.current.drafts).filter(([,d])=>d.warehouse!==warehouse)))}>取消本项目修改</Button>}
    {query.isPending?<p role="status">正在读取过程资料…</p>:query.isError&&!matrix?null:!matrix?<p>暂无有数据的项目。</p>:<>
      {tab===2?<div className="process-grid" ref={root}><AgGridReact<Difference> key="diff" domLayout="autoHeight" theme={gridTheme} rowData={matrix.diffs} columnDefs={diffs} pinnedBottomRowData={[{...matrix.diff_totals,id:-1,doc_no:'合计'} as unknown as Difference]}
        getRowId={p=>String(p.data.id)} defaultColDef={{resizable:true,sortable:false,suppressMovable:true}} rowHeight={pageGridGeometry(scale).rowHeight} headerHeight={pageGridGeometry(scale).headerHeight} suppressScrollOnNewData suppressColumnVirtualisation overlayNoRowsTemplate="当前项目没有调整差异"
        onGridReady={e=>fitGridColumns(e.api,root.current,true)} onFirstDataRendered={e=>fitGridColumns(e.api,root.current,true)} onGridSizeChanged={e=>fitGridColumns(e.api,root.current)} /></div>:
      <ProcessCells.Provider value={{drafts,warehouse,disabled,source:detailSource,change,save,switchSource:(ym,column)=>{const signature=query.data?.signatures[warehouse]?.[ym];if(!signature)return;setError('');setSource({warehouse,ym,column,signature,value:matrix[kind].find(r=>r.ym===ym)?.[column]??null});}}}>
        <div className="process-matrix-scroll" tabIndex={0} role="region" aria-label="过程资料月度表，可横向滚动"><table className="process-matrix" aria-label={`${tabLabels[tab]}，金额单位：元`}>
          <thead><tr><th scope="col">核算月</th>{matrixColumns.map(column=><th scope="col" key={column.field} className={column.segment?'process-segment':''}>{column.label}</th>)}</tr></thead>
          <tbody>{matrix[kind].length?matrix[kind].map(row=><tr key={row.ym}><th scope="row">{row.ym}</th>{matrixColumns.map(column=><td key={column.field} className={`money${column.segment?' process-segment':''}${tab===1&&!column.field.startsWith('mech_')&&matrix.raw.find(raw=>raw.ym===row.ym)?.[column.field]!==row[column.field]?' process-adjusted':''}`}>{column.field.startsWith('mech_')?<MechanicalCell data={row} column={column.field}/>:show(row[column.field])}</td>)}</tr>):<tr><td colSpan={17} className="process-empty">当前项目没有月度记录</td></tr>}</tbody>
          <tfoot><tr><th scope="row">合计</th>{matrixColumns.map(column=><td key={column.field} className={`money${column.segment?' process-segment':''}`}>{show(matrix.totals[kind][column.field])}</td>)}</tr>
            <tr><th scope="row">总求和（本表）</th>{matrix.segments[kind].map((segment,i)=><td key={segment.name} colSpan={[5,5,4,2][i]} className="money process-segment">{['入库合计','出库合计','机械合计','不含税合计'][i]} {show(segment.total)}</td>)}</tr></tfoot>
        </table></div>
      </ProcessCells.Provider>}
    </>}
    {source&&<BusinessModal open={active&&!blocked} titleId="process-source-title" requestClose={closing.requestClose} className="process-source-dialog"><DialogContents title={`切为手填 · ${mechLabels[mechKeys.indexOf(source.column)]}`} titleId="process-source-title" closing={closing}>
      <p>{name(source.warehouse)} · {source.ym}</p><p>当前金额 {show(source.value)} 元。切换后保留金额，该格可手填；之后确认明细可重新采用明细汇总。</p>{error&&<p role="alert" className="notice">{error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>保留明细来源</Button><Button type="primary" loading={busy} disabled={disabled} onClick={()=>void switchManual()}>确认切为手填</Button></div>
    </DialogContents></BusinessModal>}
  </section>;
}
