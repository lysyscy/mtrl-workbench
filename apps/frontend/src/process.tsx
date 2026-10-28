import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Segmented from 'antd/es/segmented';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { Link } from 'react-router';
import { readProjects, requestJson } from './api';
import type { Identity, Project } from './api';
import { contentWidth, gridTheme } from './grid';
import { BoundedTable } from './bounded-table';
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
const keyOf=(warehouse:string,ym:string,column:string)=>JSON.stringify([warehouse,ym,column]);
const approvalKey=(draft:Draft)=>JSON.stringify([draft.warehouse,draft.ym,draft.column,draft.revision]);
const show=(value:unknown)=>value==null?'':money(String(value));
const matrixColumns=[
  ...['in','out'].flatMap((direction,i)=>categories.map((label,j)=>({field:`${direction}_${label}`,label:`${i?'出库':'入库'}${label}`,header:label,segment:j===0}))),
  ...mechKeys.map((field,i)=>({field,label:mechLabels[i]!,header:i<4?mechLabels[i]!:i===4?'零租':'包月',segment:i===0||i===4})),
];
interface Cells { drafts:Record<string,Draft>; warehouse:string; disabled:boolean; source:(ym:string,column:string)=>boolean; change:(ym:string,column:string,value:string)=>void; save:(key:string,retry?:boolean)=>void }
const ProcessCells=createContext<Cells|null>(null);
function MechanicalCell({data,column}:{data:ProcessRow;column:string}) {
  const cells=useContext(ProcessCells)!;
  const label=mechLabels[mechKeys.indexOf(column)]!,key=keyOf(cells.warehouse,data.ym,column),draft=cells.drafts[key];
  return <div className={`process-cell${draft?' process-dirty':''}`}><Input className="record-value" htmlSize={1} aria-label={`${data.ym} ${label}`} value={draft?.value??data[column]??''} disabled={cells.disabled}
    status={draft?.error?'error':''} title={draft?.error||(draft?'未保存':cells.source(data.ym,column)?'明细确认金额；修改后须确认，原明细保留':'手填；清空按 0 保存')} onChange={e=>cells.change(data.ym,column,e.target.value)} onBlur={()=>cells.save(key)}
    onKeyDown={e=>{e.stopPropagation();if(e.nativeEvent.isComposing)return;if(e.key==='Enter'){e.preventDefault();cells.save(key,true);}}} />{draft?<small>{draft.error?'未保存':'待保存'}</small>:cells.source(data.ym,column)&&<small>明细确认</small>}</div>;
}
function MaterialCell({data,column,label}:{data:ProcessRow;column:string;label:string}) {
  const cells=useContext(ProcessCells)!;
  const key=keyOf(cells.warehouse,data.ym,column),draft=cells.drafts[key];
  if(data.materialEditable!=='yes') return <>{show(data[column])}</>;
  return <div className={`process-cell${draft?' process-dirty':''}`}><Input className="record-value" htmlSize={1} aria-label={`${data.ym} ${label}`} value={draft?.value??data[column]??''} disabled={cells.disabled}
    status={draft?.error?'error':''} title={draft?.error||(draft?'未保存':'历史材料手填；清空后留空')} onChange={e=>cells.change(data.ym,column,e.target.value)} onBlur={()=>cells.save(key)}
    onKeyDown={e=>{e.stopPropagation();if(e.nativeEvent.isComposing)return;if(e.key==='Enter'){e.preventDefault();cells.save(key,true);}}} />{draft&&<small>{draft.error?'未保存':'待保存'}</small>}</div>;
}
export function ProcessPage({me,blocked,active}:{me:Identity|null;blocked:boolean;active:boolean}) {
  const client=useQueryClient(),revision=useRef(0);
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
    acknowledge:(current,submitted)=>current.revision===submitted.revision?undefined:{...current,expected:submitted.value.trim()?submitted.value:null},
    describe:draft=>`${name(draft.warehouse)}，${draft.ym} `,
    saved:()=>'',
  },{key:'process',label:'过程资料'});
  const {drafts,busy,uncertain,verified,error}=saves;
  const name=(key:string)=>candidates.find(p=>p.warehouse_name===key)?.disp??'项目';
  const detailSource=(ym:string,column:string)=>query.data?.sources[warehouse]?.[ym]?.[column]?.mode==='detail';
  async function reload(){
    await client.cancelQueries({queryKey:['process'],exact:true});
    const data=await client.fetchQuery({queryKey:['process'],staleTime:0,queryFn:({signal})=>getProcess(signal)});
    await client.invalidateQueries({predicate:q=>q.queryKey[0]!=='process'});return data;
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
        const next=cents(draft.value.trim()||'0');
        const signed=query.data?.effectiveValues[draft.warehouse]?.[draft.ym];
        const expected=signed?signed[draft.column]??null:query.data?.matrices[draft.warehouse]?.[kind].find(row=>row.ym===draft.ym)?.[draft.column]??null;
        if(expected!==null&&next===cents(expected)) {
          saves.update(current=>{const result={...current};if(result[key]?.revision===draft.revision)delete result[key];return result;});return;
        }
        if(next>=0n&&requiresConfirmation(draft)) {
          const signature=query.data?.signatures[draft.warehouse]?.[draft.ym];if(!signature)return;
          setSource({draft:{...draft,expected},signature,details:query.data?.detailSignatures[draft.warehouse]?.[draft.ym]??''});return;
        }
      } catch { /* Queue validation reports the invalid amount beside its draft. */ }
    }
    saves.save(key,retry);
  }
  const reread=()=>saves.reread(uncertain?'已重读，请核对刚才的保存结果。':'已重读，未保存输入仍保留。');
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
    <div data-page-chrome className="process-tabs"><Segmented aria-label="过程资料表" value={tab} options={tabLabels.map((label,value)=>({label:value===2?<span>{label}{matrix&&<span className="process-diff-count">{matrix.diffs.length}</span>}</span>:label,value}))} onChange={value=>setTab(Number(value))} disabled={paused} />{dirty&&<span>{Object.keys(drafts).length} 项未保存</span>}{query.isFetching&&!query.isPending&&<span role="status">正在重读…</span>}</div>
    {(error||query.isError||projects.isError||uncertain)&&<p className="notice" role="alert">{error||query.error?.message||projects.error?.message}{(error||query.isError||uncertain)&&<Button disabled={paused||busy||query.isFetching} onClick={()=>void reread()}>重读资料</Button>}{projects.isError&&<Button disabled={paused||projects.isFetching} onClick={()=>void projects.refetch()}>重读项目</Button>}</p>}
    {uncertain&&<p className="notice" role="alert">核对结果后再继续。<Button disabled={paused||busy||!verified||query.isFetching||query.isError} onClick={()=>{saves.confirm();}}>已核对，保留输入继续</Button></p>}
    {currentDrafts.filter(([,d])=>d.error).map(([key,d])=><p key={key} role="alert" className="notice">{d.ym} {matrixColumns.find(c=>c.field===d.column)?.label}：{d.error}<Button disabled={disabled||busy} onClick={()=>save(key,true)}>重试保存</Button><Button disabled={paused||busy||uncertain} onMouseDown={e=>e.preventDefault()} onClick={()=>{saves.update(drafts=>{const next={...drafts};delete next[key];return next;});}}>取消这项修改</Button></p>)}
    {currentDrafts.length>0&&<Button disabled={paused||busy||uncertain} onMouseDown={e=>e.preventDefault()} onClick={()=>saves.update(drafts=>Object.fromEntries(Object.entries(drafts).filter(([,d])=>d.warehouse!==warehouse)))}>取消本项目修改</Button>}
    {query.isPending?<p role="status" data-page-loading>正在读取过程资料…</p>:query.isError&&!matrix?null:!matrix?<p>暂无有数据的项目。</p>:<>
      {tab===2?<DifferenceGrid matrix={matrix} diffs={diffs} warehouse={warehouse} scale={scale} active={active} />:<>
      <ProcessCells.Provider value={{drafts,warehouse,disabled,source:detailSource,change,save}}>
        <div className="process-matrix-scroll" tabIndex={0} role="region" aria-label="过程资料月度表，可横向滚动"><BoundedTable prepareFonts layoutVersion={displayRows} className="process-matrix" aria-label={`${tabLabels[tab]}，金额单位：元`}>
          <thead><tr className="process-groups"><th scope="col" rowSpan={2}>核算月</th><th scope="colgroup" colSpan={5} className="process-segment">入库</th><th scope="colgroup" colSpan={5} className="process-segment">出库</th><th scope="colgroup" colSpan={4} className="process-segment">机械</th><th scope="colgroup" colSpan={2} className="process-segment">机械（不含税）</th></tr>
            <tr>{matrixColumns.map(column=><th scope="col" key={column.field} aria-label={column.label} className={column.segment?'process-segment':''}>{column.header}</th>)}</tr></thead>
          <tbody>{displayRows.length?displayRows.map(row=><tr key={row.ym}><th scope="row">{row.ym}</th>{matrixColumns.map(column=><td key={column.field} className={`money${column.segment?' process-segment':''}${tab===1&&!column.field.startsWith('mech_')&&matrix.raw.find(raw=>raw.ym===row.ym)&&matrix.raw.find(raw=>raw.ym===row.ym)?.[column.field]!==row[column.field]?' process-adjusted':''}`}>{column.field.startsWith('mech_')?<MechanicalCell data={row} column={column.field}/>:<MaterialCell data={row} column={column.field} label={column.label}/>}</td>)}</tr>):<tr><td colSpan={17} className="process-empty">当前项目没有月度记录</td></tr>}</tbody>
          <tfoot><tr><th scope="row">合计</th>{matrixColumns.map(column=><td key={column.field} className={`money${column.segment?' process-segment':''}`}>{show(matrix.totals[kind][column.field])}</td>)}</tr>
            <tr><th scope="row">总求和（本表）</th>{matrix.segments[kind].map((segment,i)=><td key={segment.name} colSpan={[5,5,4,2][i]} className="money process-segment">{['入库合计','出库合计','机械合计','不含税合计'][i]} {show(segment.total)}</td>)}</tr></tfoot>
        </BoundedTable></div>
      </ProcessCells.Provider></>}
    </>}
    {source&&<BusinessModal open={active&&!blocked} titleId="process-source-title" requestClose={closing.requestClose} className="process-source-dialog"><DialogContents title="确认保存机械费" titleId="process-source-title" closing={closing}>
      <p>{name(source.draft.warehouse)}，{source.draft.ym} {mechLabels[mechKeys.indexOf(source.draft.column)]}</p><p>该项目本月已有机械明细。此格将采用手填金额，原明细保留。</p>
      <p>原金额 {source.draft.expected===null?'未录入':show(source.draft.expected)} → 新金额 {show(source.draft.value.trim()||'0')} 元</p>
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" loading={busy} disabled={disabled} onClick={confirmSave}>确认保存</Button></div>
    </DialogContents></BusinessModal>}
  </section>;
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
