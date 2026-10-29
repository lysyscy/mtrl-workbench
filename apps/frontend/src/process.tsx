import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Segmented from 'antd/es/segmented';
import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ColGroupDef, ICellRendererParams, IHeaderParams } from 'ag-grid-community';
import { Link } from 'react-router';
import { readProjects, requestJson } from './api';
import type { Identity, Project } from './api';
import { contentWidth, fixedWidth, numberColumnWidth, gridTheme } from './grid';
import { BusinessGrid } from './business-grid';
import { ProjectPicker } from './ledger-controls';
import { useCellSaveQueue } from './use-cell-save';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { cents, money } from './notices-api';
import { categories, dataKeys, getProcess, mechKeys, mechLabels, saveProcess, tabLabels } from './process-api';
import type { Confirmation, Difference, ProcessRow } from './process-api';
import { ProcessExport } from './process-export';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
const differenceRowId = (row: Difference) => String(row.id);

interface Draft { warehouse:string; ym:string; column:string; value:string; expected:string|null; revision:number; error:string }
const acknowledgeDraft=(current:Draft,submitted:Draft)=>current.revision===submitted.revision?undefined:{...current,expected:submitted.value.trim()?submitted.value:null};
const keyOf=(warehouse:string,ym:string,column:string)=>JSON.stringify([warehouse,ym,column]);
const approvalKey=(draft:Draft)=>JSON.stringify([draft.warehouse,draft.ym,draft.column,draft.revision]);
const show=(value:unknown)=>value==null?'':money(String(value));
const displayAmount=(value:unknown)=>{try{return show(value);}catch{return String(value??'');}};
const matrixColumns=[
  ...['in','out'].flatMap((direction,i)=>categories.map((label,j)=>({field:`${direction}_${label}`,label:`${i?'出库':'入库'}${label}`,header:label,segment:j===0}))),
  ...mechKeys.map((field,i)=>({field,label:mechLabels[i]!,header:i<4?mechLabels[i]!:i===4?'零租':'包月',segment:i===0||i===4})),
];
interface Cells { drafts:Record<string,Draft>; warehouse:string; disabled:boolean; source:(ym:string,column:string)=>boolean; change:(ym:string,column:string,value:string)=>void; save:(key:string,retry?:boolean)=>void; cancel:(key:string)=>void }
const ProcessCells=createContext<Cells|null>(null);
function ProcessAmountCell({data,column,label,mechanical=false}:{data:ProcessRow;column:string;label:string;mechanical?:boolean}) {
  const cells=useContext(ProcessCells)!;
  const [focused,setFocused]=useState(false),key=keyOf(cells.warehouse,data.ym,column),draft=cells.drafts[key];
  const raw=draft?.value??data[column]??'';
  let display=raw;
  if(!focused&&String(raw).trim())display=displayAmount(raw);
  // Native input records an explicit 0 even when it replaces the same displayed default.
  return <div className={`process-cell${draft?' process-dirty':''}`}><Input className="record-value" htmlSize={1} aria-label={`${data.ym} ${label}`} value={display} disabled={cells.disabled}
    status={draft?.error?'error':''} title={draft?.error||undefined}
    onFocus={()=>setFocused(true)} onInput={e=>cells.change(data.ym,column,e.currentTarget.value)} onBlur={()=>{setFocused(false);cells.save(key);}}
    onKeyDown={e=>{e.stopPropagation();if(e.nativeEvent.isComposing)return;if(e.key==='Enter'){e.preventDefault();cells.save(key,true);e.currentTarget.blur();}}} />
    {draft?.error?<div className="process-cell-error" role="alert"><span>{draft.error}</span><div><Button size="small" disabled={cells.disabled} onClick={()=>cells.save(key,true)}>重试</Button><Button size="small" disabled={cells.disabled} onClick={()=>cells.cancel(key)}>取消修改</Button></div></div>:mechanical&&cells.source(data.ym,column)&&<small>明细确认</small>}</div>;
}
function MechanicalCell({data,column}:{data:ProcessRow;column:string}) {
  return <ProcessAmountCell data={data} column={column} label={mechLabels[mechKeys.indexOf(column)]!} mechanical/>;
}
function MaterialCell({data,column,label}:{data:ProcessRow;column:string;label:string}) {
  if(data.materialEditable!=='yes') return <>{show(data[column])}</>;
  return <ProcessAmountCell data={data} column={column} label={label}/>;
}
export function ProcessPage({me,blocked,active}:{me:Identity|null;blocked:boolean;active:boolean}) {
  const client=useQueryClient(),revision=useRef(0),attempt=useRef<Draft|null>(null);
  const [warehouse,setWarehouse]=useState(''),[tab,setTab]=useState(1);
  const [newMonth,setNewMonth]=useState(''),[extraMonths,setExtraMonths]=useState<Record<string,string[]>>({});
  const [source,setSource]=useState<{draft:Draft;signature:string;details:string}|null>(null);
  const approvals=useRef(new Map<string,Confirmation>());
  const query=useQuery({queryKey:['process'],enabled:active&&!blocked,queryFn:({signal})=>getProcess(signal)});
  const projects=useQuery({queryKey:['projects','all'],enabled:active&&!blocked,queryFn:async({signal})=>readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  const candidates=useMemo(()=>query.data?.projects.map((key,index):Project=>projects.data?.find(p=>p.warehouse_name===key)??{id:-index-1,disp:`未建档项目 ${index+1}`,name_full:'',warehouse_name:key,project_type:'normal',status:'active',ord:index,phid:''})??[],[query.data,projects.data]);
  useEffect(()=>{if(!warehouse&&query.data?.projects[0])setWarehouse(query.data.projects[0]);},[warehouse,query.data]);
  const saves=useCellSaveQueue<Draft,Awaited<ReturnType<typeof getProcess>>>({
    enabled:active&&!blocked&&Boolean(me),canWrite:!query.isError&&!projects.isError,
    read:reload,write:(draft,signal)=>{
      attempt.current={...draft};
      const approval=approvals.current.get(approvalKey(draft));approvals.current.delete(approvalKey(draft));
      return saveProcess(draft.warehouse,draft.ym,draft.column,draft.value,draft.expected,signal,approval);
    },
    validate:draft=>{
      if(mechKeys.includes(draft.column)) {
        try {if(cents(draft.value.trim()||'0')<0n)return '机械费不能为负数。';} catch {return '请输入有效金额，最多两位小数。';}
        if(requiresConfirmation(draft)&&!approvals.current.has(approvalKey(draft)))return '同项目同月已有机械明细，请确认后保存。';
      }
      return '';
    },
    acknowledge:acknowledgeDraft,
    describe:draft=>`${name(draft.warehouse)}，${draft.ym} ${matrixColumns.find(column=>column.field===draft.column)?.label??draft.column} `,
    saved:()=>'',
  },{key:'process',label:'过程资料'});
  const {drafts,busy,uncertain,verified,error}=saves;
  const name=(key:string)=>candidates.find(p=>p.warehouse_name===key)?.disp??'项目';
  const detailSource=(ym:string,column:string)=>query.data?.sources[warehouse]?.[ym]?.[column]?.mode==='detail';
  async function reload(){
    await client.cancelQueries({queryKey:['process'],exact:true});
    await client.invalidateQueries({refetchType:'none'});
    if(me)void client.invalidateQueries({queryKey:['history',`${me.id}:${me.account}`],exact:true});
    return client.fetchQuery({queryKey:['process'],staleTime:0,queryFn:({signal})=>getProcess(signal)});
  }
  function change(ym:string,column:string,value:string){
    const key=keyOf(warehouse,ym,column);
    const expected=query.data?.matrices[warehouse]?.[kind].find(row=>row.ym===ym)?.[column]??null;
    saves.update(drafts=>({...drafts,[key]:{warehouse,ym,column,value,expected:drafts[key]&&!drafts[key].error?drafts[key].expected:expected,revision:++revision.current,error:''}}));
  }
  function requiresConfirmation(draft:Draft) {
    return Boolean(query.data?.detailSignatures[draft.warehouse]?.[draft.ym]) || query.data?.sources[draft.warehouse]?.[draft.ym]?.[draft.column]?.mode==='detail';
  }
  function save(key:string,retry=false) {
    const draft=drafts[key];if(!draft||disabled||source)return;
    if(mechKeys.includes(draft.column)) {
      try {
        const next=draft.value.trim()?cents(draft.value):null;
        const signed=query.data?.effectiveValues[draft.warehouse]?.[draft.ym];
        const expected=signed?signed[draft.column]??null:query.data?.matrices[draft.warehouse]?.[kind].find(row=>row.ym===draft.ym)?.[draft.column]??null;
        if(signed&&next===(expected===null?null:cents(expected))) {
          saves.update(current=>{const result={...current};if(result[key]?.revision===draft.revision)delete result[key];return result;});return;
        }
        if((next===null||next>=0n)&&requiresConfirmation(draft)) {
          const signature=query.data?.signatures[draft.warehouse]?.[draft.ym];if(!signature)return;
          setSource({draft:{...draft,expected},signature,details:query.data?.detailSignatures[draft.warehouse]?.[draft.ym]??''});return;
        }
      } catch { /* Queue validation reports the invalid amount beside its draft. */ }
    }
    saves.save(key,retry);
  }
  const reread=()=>saves.reread(uncertain?'已重读，请核对刚才的保存结果。':'已重读，未保存输入仍保留。');
  function confirmResult(){
    if(!verified||busy||paused||!me||query.isFetching||query.isError||projects.isError)return;
    const submitted=attempt.current;
    if(submitted)saves.update(current=>{
      const key=keyOf(submitted.warehouse,submitted.ym,submitted.column),draft=current[key];
      if(!draft)return current;
      const expected=query.data?.matrices[submitted.warehouse]?.[kind].find(row=>row.ym===submitted.ym)?.[submitted.column]??null;
      const hasRecord=!mechKeys.includes(submitted.column)||Boolean(query.data?.effectiveValues[submitted.warehouse]?.[submitted.ym]);
      let matches=false;
      try{matches=hasRecord&&(submitted.value.trim()?cents(submitted.value):null)===(expected===null?null:cents(expected));}catch{/* An unverified submission remains a draft. */}
      if(!matches)return current;
      const next={...current},retained=acknowledgeDraft(draft,submitted);
      if(retained)next[key]=retained;else delete next[key];
      return next;
    });
    saves.confirm();
  }
  function confirmSave(){
    if(!source||busy||disabled)return;
    const draft=source.draft,key=keyOf(draft.warehouse,draft.ym,draft.column);
    if(drafts[key]?.revision!==draft.revision){setSource(null);return;}
    approvals.current.set(approvalKey(draft),{confirmed:true,effective_signature:source.signature,detail_signature:source.details});
    setSource(null);saves.save(key,true);
  }
  const disabled=blocked||!active||!me||uncertain||query.isError||projects.isError;
  const paused=blocked||!active;
  const closing=useDialogClose({busy,dirty:false,close:()=>setSource(null),active:Boolean(source)&&active});
  const matrix=query.data?.matrices[warehouse],kind=tab===0?'raw':'adjusted',scale=Number(me?.ui_scale_css??1);
  const displayRows=useMemo(()=>{
    const rows=matrix?.[kind]??[];
    const added=(extraMonths[warehouse]??[]).filter(ym=>!rows.some(row=>row.ym===ym)).map(ym=>({...Object.fromEntries(dataKeys.map(key=>[key,null])),ym,materialEditable:'yes'}) as ProcessRow);
    return [...rows,...added].sort((a,b)=>a.ym.localeCompare(b.ym));
  },[matrix,kind,extraMonths,warehouse]);
  const diffs=useMemo<ColDef<Difference>[]>(()=>[
    ...(['doc_no','seq','material','warehouse','before','after','delta','changes','remark','operator','at'] as const).map((field,i):ColDef<Difference>=>({field,headerName:['单据编号','序号','物料','仓库','原值（i8）','调整后','差额','调整内容','备注','操作人','时间'][i]!,...(field==='doc_no'?{pinned:'left' as const}:{}),...contentWidth(field==='seq'?52:['before','after','delta'].includes(field)?130:field==='operator'?96:['material','warehouse','at'].includes(field)?128:140,field==='seq'?80:260,scale,field==='remark'?1:0),wrapText:true,autoHeight:true,...(['before','after','delta'].includes(field)?{cellClass:'money',valueFormatter:(p:{value:unknown})=>show(p.value)}:{})})),
    {colId:'locate',headerName:'操作',pinned:'right',...contentWidth(100,130,scale),cellRenderer:(p:ICellRendererParams<Difference>)=>p.data&&!p.node.rowPinned&&<Link className="row-button" to={`/inventory?row=${p.data.id}`}>定位原行</Link>},
  ],[scale]);
  const dirty=Object.keys(drafts).length>0,reason=uncertain?'先重读核对保存结果':busy?'正在保存':dirty?'先处理未保存输入':query.isError||projects.isError?'先重读资料':query.isFetching?'正在重读':'';
  const currentDrafts=Object.entries(drafts).filter(([,d])=>d.warehouse===warehouse);
  return <section className="process-page" aria-label="过程资料">
    <div data-page-chrome className="process-toolbar"><h2>过程资料</h2><ProcessExport projects={candidates} current={warehouse} tab={tab} paused={paused} reason={reason} /></div>
    <div data-page-chrome className="process-filters"><span>项目</span><ProjectPicker label="过程资料项目" projects={candidates} selected={candidates.filter(p=>p.warehouse_name===warehouse).map(p=>p.id)} pick={ids=>{const p=candidates.find(p=>p.id===ids[0]);if(p?.warehouse_name){setWarehouse(p.warehouse_name);saves.clearFeedback();}}} disabled={paused||projects.isPending||projects.isError||query.isPending} />{tab!==2&&matrix&&<div className="process-history"><label>增加历史月份 <Input type="month" aria-label="增加历史月份" max="2025-11" value={newMonth} onChange={e=>setNewMonth(e.target.value)} /></label><Button disabled={disabled||!/^\d{4}-(0[1-9]|1[0-2])$/.test(newMonth)||newMonth>'2025-11'||displayRows.some(row=>row.ym===newMonth)} onClick={()=>{setExtraMonths(current=>({...current,[warehouse]:[...(current[warehouse]??[]),newMonth]}));setNewMonth('');}}>增加月份</Button><span>填写金额后保存月份</span></div>}</div>
    <div data-page-chrome className="process-tabs"><Segmented aria-label="过程资料表" value={tab} options={tabLabels.map((label,value)=>({label:value===2?<span>{label}{matrix&&<span className="process-diff-count">{matrix.diffs.length}</span>}</span>:label,value}))} onChange={value=>setTab(Number(value))} disabled={paused} />{Object.values(drafts).some(draft=>draft.error)&&<span>有未保存的修改，请查看对应金额格。</span>}<Button disabled={paused||busy||uncertain||!currentDrafts.length} onMouseDown={e=>e.preventDefault()} onClick={()=>saves.update(drafts=>Object.fromEntries(Object.entries(drafts).filter(([,d])=>d.warehouse!==warehouse)))}>取消本项目修改</Button></div>
    {(query.isError||projects.isError||uncertain)&&<div className="notice" role="alert">{error||query.error?.message||projects.error?.message}{(query.isError||uncertain)&&<Button disabled={paused||busy||query.isFetching} onClick={()=>void reread()}>重新核对</Button>}{projects.isError&&<Button disabled={paused||projects.isFetching} onClick={()=>void projects.refetch()}>重读项目</Button>}</div>}
    {uncertain&&<div className="notice process-uncertain" role="alert">{attempt.current&&<p>{name(attempt.current.warehouse)}，{attempt.current.ym} {matrixColumns.find(column=>column.field===attempt.current!.column)?.label}，本次输入：{attempt.current.value.trim()?displayAmount(attempt.current.value):'留空'}。</p>}<p>{query.isFetching?'正在重新核对…':verified?'已重读，请对照当前金额和本次输入核对结果。':'保存结果待核实，核对前暂停后续保存。'}</p><Button disabled={paused||!me||busy||!verified||query.isFetching||query.isError||projects.isError} onClick={confirmResult}>已核对，保留输入继续</Button></div>}
    {query.isPending?<p role="status" data-page-loading>正在读取过程资料…</p>:query.isError&&!matrix?null:!matrix?<p>暂无有数据的项目。</p>:<>
      {tab===2?<DifferenceGrid matrix={matrix} diffs={diffs} warehouse={warehouse} scale={scale} active={active} />:<>
      <ProcessCells.Provider value={{drafts,warehouse,disabled,source:detailSource,change,save,cancel:key=>saves.update(current=>{const next={...current};delete next[key];return next;})}}>
        <MatrixGrid matrix={matrix} rows={displayRows} kind={kind} warehouse={warehouse} scale={scale}/>
      </ProcessCells.Provider></>}
    </>}
    {source&&<BusinessModal open={active&&!blocked} titleId="process-source-title" requestClose={closing.requestClose} className="process-source-dialog"><DialogContents title="确认保存机械费" titleId="process-source-title" closing={closing}>
      <p>{name(source.draft.warehouse)}，{source.draft.ym} {mechLabels[mechKeys.indexOf(source.draft.column)]}</p><p>该项目本月已有机械明细。此格将采用手填金额，原明细保留。</p>
      <p>原金额 {source.draft.expected===null?'未录入':show(source.draft.expected)+' 元'} → 新金额 {source.draft.value.trim()?show(source.draft.value)+' 元':'留空'}</p>
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" loading={busy} disabled={disabled} onClick={confirmSave}>确认保存</Button></div>
    </DialogContents></BusinessModal>}
  </section>;
}

type MatrixRow=ProcessRow&{rowkind?:'total'|'segments'};
function MatrixHeader(p:IHeaderParams){useLayoutEffect(()=>{const label=p.column.getColDef().headerTooltip;p.eGridHeader.setAttribute('aria-label',typeof label==='string'?label:p.displayName);},[p]);return <span>{p.displayName}</span>;}
function MatrixCell(p:ICellRendererParams<MatrixRow>){
  const row=p.data!,field=p.colDef!.field!;
  if(row.rowkind==='segments'){
    if(!row[field])return '';
    const [label,...amount]=String(row[field]).split(' ');
    return <span className="process-segment-total"><span>{label}</span>{' '}<span>{amount.join(' ')}</span></span>;
  }
  if(p.node.rowPinned)return show(row[field]);
  const column=matrixColumns.find(column=>column.field===field)!;return field.startsWith('mech_')?<MechanicalCell data={row} column={field}/>:<MaterialCell data={row} column={field} label={column.label}/>;
}
function MatrixGrid({matrix,rows,kind,warehouse,scale}:{matrix:Awaited<ReturnType<typeof getProcess>>['matrices'][string];rows:ProcessRow[];kind:'raw'|'adjusted';warehouse:string;scale:number}){
  const cells=useContext(ProcessCells)!;
  const errors=JSON.stringify(Object.entries(cells.drafts).filter(([,draft])=>draft.warehouse===warehouse&&draft.error).map(([key,draft])=>[key,draft.error]));
  const measurement=useMemo(()=>{
    const messages=new Map<string,string>(JSON.parse(errors));
    return {signature:(row:MatrixRow,column:string,pinned:boolean)=>JSON.stringify([row,pinned?'':messages.get(keyOf(warehouse,row.ym,column))??''])};
  },[errors,warehouse]);
  const totals=useMemo<MatrixRow[]>(()=>[
    {...matrix.totals[kind],ym:'合计',rowkind:'total'} as MatrixRow,
    {...Object.fromEntries(dataKeys.map(field=>[field,null])),ym:'总求和（本表）',rowkind:'segments',...Object.fromEntries([0,5,10,14].map((start,index)=>[matrixColumns[start]!.field,['入库合计','出库合计','机械合计','不含税合计'][index]+' '+show(matrix.segments[kind][index]!.total)]))} as MatrixRow,
  ],[matrix,kind]);
  const columns=useMemo<(ColDef<MatrixRow>|ColGroupDef<MatrixRow>)[]>(()=>[
    {field:'ym',headerName:'核算月',pinned:'left',...fixedWidth(112,scale)},
    ...[['入库',0,5],['出库',5,10],['机械',10,14],['机械（不含税）',14,16]].map(([name,start,end])=>({headerName:String(name),children:matrixColumns.slice(Number(start),Number(end)).map((column,index):ColDef<MatrixRow>=>({field:column.field,headerName:column.header,headerTooltip:column.label,headerComponentParams:{innerHeaderComponent:MatrixHeader},...numberColumnWidth([...rows.map(row=>show(row[column.field])),show(matrix.totals[kind][column.field])],scale,true,1),wrapText:false,cellClass:p=>'money'+(column.segment?' process-segment':'')+(kind==='adjusted'&&!column.field.startsWith('mech_')&&matrix.raw.some(raw=>raw.ym===p.data?.ym&&raw[column.field]!==p.data?.[column.field])?' process-adjusted':''),colSpan:p=>p.data?.rowkind==='segments'&&index===0?Number(end)-Number(start):1,cellRenderer:MatrixCell}))})),
  ],[matrix,rows,kind,scale]);
  return <div className="process-matrix-scroll" role="region" aria-label="过程资料月度表，可横向滚动"><BusinessGrid table="process-matrix" className="process-matrix-view" gridClassName="process-matrix" label={tabLabels[kind==='raw'?0:1]+'，金额单位：元'} domLayout="normal" rows={rows} totals={totals} columns={columns} measurement={measurement} rowId={row=>row.ym} scope={warehouse+':'+kind} scale={scale} rowMinimum={56*scale} style={{height:'100%'}} grid={{overlayNoRowsTemplate:'当前项目没有月度记录',groupHeaderHeight:34*scale}}/></div>;
}
function DifferenceGrid({matrix,diffs,warehouse,scale,active}: {
  matrix: Awaited<ReturnType<typeof getProcess>>['matrices'][string]; diffs: ColDef<Difference>[]; warehouse: string; scale: number; active: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  const diffRows = matrix.diffs;
  const diffTotals = useMemo(() => [{...matrix.diff_totals,id:-1,doc_no:'合计'} as unknown as Difference], [matrix]);
  const presentation = useGridPresentation({table:'process-differences',root,active,rows:diffRows,totals:diffTotals,columns:diffs,rowId:differenceRowId,scale,scope:warehouse,identity:warehouse});
  return <PreparedGrid presentation={presentation} className="process-grid" grid={{domLayout:'autoHeight',theme:gridTheme,
    getRowId:p=>String(p.data.id),defaultColDef:{resizable:true,sortable:false,suppressMovable:true,wrapHeaderText:true},suppressScrollOnNewData:true,suppressColumnVirtualisation:true,overlayNoRowsTemplate:'当前项目没有调整差异',animateRows:false}} />;
}
