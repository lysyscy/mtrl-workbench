import Button from 'antd/es/button';
import App from 'antd/es/app';
import Checkbox from 'antd/es/checkbox';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { readProjects, requestJson } from './api';
import type { Identity } from './api';
import { ProjectPicker } from './ledger-controls';
import { pageGridGeometry, textWidth, fixedWidth, numberColumnWidth, gridTheme } from './grid';
import { manualGridColumns } from './grid-manual-widths';
import { completeColumnWidth, EllipsisText, TextPreview } from './grid-text';
import { GridWidthContext, useGridWidthColumns, useGridWidths } from './grid-widths';
import { EnumTag } from './enum-tag';
import { useHistoryGuard } from './history';
import { contractMoneyKeys, contractWrite, readContracts, contractHistoryDate, contractRemarkText, historyContractRemark } from './contracts-api';
import type { ContractRow } from './contracts-api';
import { cents, money, receipt, searchKey } from './notices-api';
import { ContractEditor, nextContractArchiveNo } from './contract-dialog';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { ContractFetch, ContractSettings } from './contract-tools';
import { ContractExports } from './contract-export';
import { ContractSubtableDialog, hasSubtableDrafts } from './contract-subtables';
import type { SubtableWorkspace } from './contract-subtables';

const defaultColumn: ColDef<ContractRow> = {sortable:true,resizable:true,suppressMovable:true,suppressAutoSize:true,wrapText:false,autoHeight:false,wrapHeaderText:false,autoHeaderHeight:false};

function decimalCents(value:bigint){const abs=value<0n?-value:value;return `${value<0n?'-':''}${abs/100n}.${String(abs%100n).padStart(2,'0')}`;}
const initialFilters=()=>({projects:[] as number[],tag:'纳入台账',arch:''});
type InlineKey='remark'|'arch_no'|'ret_date'|'payment_term'|'payment_method';
type InlineControl={disabled:boolean;methods:string[];drafts:Record<string,string>;change:(id:number,key:InlineKey,value:string)=>void;save:(row:ContractRow,key:InlineKey|'arch',value:string)=>Promise<boolean>;remark:(row:ContractRow,value:string)=>void;next:(row:ContractRow)=>string};
function ContractInlineCell(p:ICellRendererParams<ContractRow>&{editKey:InlineKey;control:()=>InlineControl}){
  const row=p.data!,key=p.editKey,name=`${row.id}:${key}`,control=p.control();
  const value=control.drafts[name]??(key==='remark'?contractRemarkText(row.remark??''):row[key]);
  const [text,setText]=useState(value);
  useEffect(()=>setText(value),[value]);
  if(p.node.rowPinned)return null;
  if(key==='payment_method')return <Select className="contract-inline-select" aria-label={`${row.contract_no||row.material} 合同付款方式`} value={text} disabled={control.disabled} options={['',...control.methods].map(value=>({value,label:value?<EnumTag kind="payMethod" value={value}/>: '未约定'}))} onChange={value=>{setText(value);p.control().change(row.id,key,value);void p.control().save(row,key,value);}}/>;
  return <TextPreview text={text}><Input className="record-value" onDoubleClick={key==='remark'?()=>p.control().remark(row,text):undefined} aria-label={`${row.contract_no||row.material} ${key==='remark'?'备注':key==='arch_no'?'存档号':key==='payment_term'?'账期':'寄回日期'}`} type={key==='ret_date'?'date':'text'} value={text} maxLength={key==='remark'?255-(contractHistoryDate(row.remark)?historyContractRemark(contractHistoryDate(row.remark),'').length:0):key==='arch_no'||key==='payment_term'?32:undefined} disabled={control.disabled} placeholder={key==='arch_no'?control.next(row):'可填'} onChange={e=>{setText(e.target.value);p.control().change(row.id,key,e.target.value);}} onBlur={()=>void p.control().save(row,key,text)} onKeyDown={e=>{if(e.key!=='Enter'||e.nativeEvent.isComposing)return;e.preventDefault();if(key==='arch_no'&&!text.trim()){const next=p.control().next(row);setText(next);p.control().change(row.id,key,next);return;}void p.control().save(row,key,text);}}/></TextPreview>;
}
function ContractRemarkEditor({ row, initial, busy, disabled, paused, error, save, close }: { row:ContractRow;initial:string;busy:boolean;disabled:boolean;paused:boolean;error:string;save:(value:string)=>Promise<boolean>;close:()=>void }) {
  const [text,setText]=useState(initial);
  const closing=useDialogClose({busy,dirty:text!==initial,close,active:!paused});
  const date=contractHistoryDate(row.remark),maxLength=255-(date?historyContractRemark(date,'').length:0);
  return <BusinessModal open={!paused} className="contract-remark-editor" titleId="contract-remark-title" requestClose={closing.requestClose}><DialogContents title="编辑合同备注" titleId="contract-remark-title" closing={closing}>
    <p className="muted">{row.contract_no||row.material}{date?`，历史核对截至 ${date}`:''}</p>
    <Input.TextArea autoFocus aria-label="合同备注全文" value={text} maxLength={maxLength} showCount disabled={busy||disabled} onChange={event=>setText(event.target.value)}/>
    {error&&<p className="notice" role="alert">{error}</p>}
    <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button className="primary" disabled={busy||disabled} onClick={()=>void save(text).then(ok=>{if(ok)close();})}>{busy?'正在保存…':'保存'}</Button></div>
  </DialogContents></BusinessModal>;
}
export function ContractsPage({ me,blocked,active }: { me:Identity|null;blocked:boolean;active:boolean }) {
  const { message }=App.useApp();
  const announce=(text:string)=>{void message.success({key:'contract-success',content:text,duration:3});};
  const client=useQueryClient(),grid=useRef<GridApi<ContractRow>|null>(null),root=useRef<HTMLDivElement>(null),lock=useRef(false),pendingFocus=useRef(0);
  const [filters,setFilters]=useState(initialFilters),[search,setSearch]=useState(''),[picked,setPicked]=useState<Set<number>>(()=>new Set()),[trade,setTrade]=useState(false);
  const [editors,setEditors]=useState<Record<string,{row:ContractRow|null;materialOnly:boolean}>>({}),[editorId,setEditorId]=useState<string|null>(null),[tool,setTool]=useState<'fetch'|'party'|null>(null);
  function openEditor(row:ContractRow|null,materialOnly=Boolean(row)){const key=row?`${row.id}:${materialOnly?'material':'full'}`:'new';setEditors(old=>old[key]?old:{...old,[key]:{row,materialOnly}});setEditorId(key);}
  function closeEditor(key:string){setEditors(old=>{const next={...old};delete next[key];return next;});setEditorId(current=>current===key?null:current);}
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[uncertain,setUncertain]=useState(false);
  const [params]=useSearchParams();
  const [inlineDrafts,setInlineDrafts]=useState<Record<string,string>>({}),[subtable,setSubtable]=useState<{row:ContractRow;kind:'supplier'|'trade'|'payment'}|null>(null);
  const [remarkEditor,setRemarkEditor]=useState<{row:ContractRow;initial:string}|null>(null);
  function openRemark(row:ContractRow,value:string){setRemarkEditor({row,initial:value});}
  const inlineDraftRef=useRef(inlineDrafts);inlineDraftRef.current=inlineDrafts;
  const [subtables,changeSubtables]=useState<SubtableWorkspace>({}),[sort,setSort]=useState('');
  const query=useQuery({queryKey:['contracts'],enabled:!blocked&&active,refetchOnMount:'always',queryFn:async({signal})=>readContracts(await requestJson('/api/m11/list',{signal}))});
  const projects=useQuery({queryKey:['projects','all'],enabled:!blocked&&active,queryFn:async({signal})=>readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  const rows=query.data?.rows??[], projectRows=projects.data??[];
  const needle=searchKey(search);
  const shown=useMemo(()=>rows.filter(row=>(!filters.tag||row.tag===filters.tag)&&(!filters.arch||row.arch===filters.arch)&&(!filters.projects.length||projectRows.some(p=>filters.projects.includes(p.id)&&p.warehouse_name===row.project_key))&&(!needle||[
    projectRows.find(p=>p.warehouse_name===row.project_key)?.disp??'',
    ...(query.data?.columns??[]).filter(column=>column.key!=='ops').flatMap(column=>{
      const value=row[column.key as keyof ContractRow];
      const text=value===null&&(contractMoneyKeys as readonly string[]).includes(column.key)?'未确定':String(value??'');
      return column.type==='date'?[text,text.replaceAll('-','/')]:[text];
    }),
  ].some(value=>searchKey(value).includes(needle)))),[rows,projectRows,filters,needle,query.data?.columns]);
  const totalRow=shown.length?[{id:-1,material:'合计',...Object.fromEntries(contractMoneyKeys.map(key=>[key,decimalCents(shown.reduce((sum,row)=>sum+cents(row[key]??'0'),0n))]))} as ContractRow]:[];
  const selected=rows.filter(row=>picked.has(row.id)),hidden=selected.filter(row=>!shown.some(v=>v.id===row.id)).length;
  const unavailable=blocked||!active||!me||busy||uncertain||query.isPending||query.isError||query.isFetching;
  useHistoryGuard('contracts',()=>busy||lock.current||Object.values(subtables).some(s=>s.busy)?'集采合同正在处理，请稍候。':uncertain||Object.values(subtables).some(s=>s.uncertain)?'合同操作结果待核实，请先重读。':Object.values(subtables).some(hasSubtableDrafts)?'合同子表有未保存输入，请先处理。':Object.keys(inlineDraftRef.current).length?'合同收发登记有未保存输入，请先处理。':'');
  useEffect(()=>{const valid=new Set(rows.map(row=>row.id));setPicked(old=>{const next=new Set([...old].filter(id=>valid.has(id)));return next.size===old.size?old:next;});},[rows]);
  useEffect(()=>{if(!active)return;const id=Number(params.get('contract'));if(id>0&&query.data){const row=query.data.rows.find(row=>row.id===id);pendingFocus.current=id;if(row){setEditorId(null);setFilters({...initialFilters(),tag:''});setSearch('');grid.current?.ensureNodeVisible(node=>node.data?.id===id,'middle');}else {setEditorId(null);setError('合同已不在列表中，请重读核对。');}}},[params.get('contract'),active,Boolean(query.data)]);
  // Uncertain flips do not change row data, so cells must be forced to re-render their disabled state.
  useEffect(()=>{if(active&&grid.current)grid.current.refreshCells({force:true});},[uncertain]);
  async function refresh(){
    await client.invalidateQueries({refetchType:'none'});
    if(me)void client.invalidateQueries({queryKey:['history',`${me.id}:${me.account}`],exact:true});
    await client.cancelQueries({queryKey:['contracts'],exact:true});
    await client.fetchQuery({queryKey:['contracts'],staleTime:0,queryFn:async({signal})=>readContracts(await requestJson('/api/m11/list',{signal}))});
  }
  async function reread(){try{await refresh();setUncertain(false);setError('');announce('已重读合同。');}catch(failure){setError(failure instanceof Error?failure.message:'重读失败，请重试。');}}
  async function tag(ids:number[],value:string){
    if(unavailable||lock.current||!ids.length)return;
    lock.current=true;setBusy(true);setError('');let written=false;
    try{const result=await contractWrite('/api/m11/tag',{ids,tag:value});written=true;setPicked(old=>new Set([...old].filter(id=>!ids.includes(id))));await refresh();announce(receipt(result));}
    catch(failure){setUncertain(true);setError(`${written?'标记已保存，列表重读失败。':'标记结果待核实。'}${failure instanceof Error?failure.message:'请重读核对。'}勿重复操作。`);}
    finally{lock.current=false;setBusy(false);}
  }
  function changeInline(id:number,key:InlineKey,value:string){const next={...inlineDraftRef.current,[`${id}:${key}`]:value};inlineDraftRef.current=next;setInlineDrafts(next);}
  const fieldQueue=useRef(new Map<string,{row:ContractRow;key:InlineKey|'arch';value:string;notify:boolean}>()),fieldSaving=useRef(false);
  const fieldScope=useRef({blocked,active,owner:me?`${me.id}:${me.account}`:'',uncertain});fieldScope.current={blocked,active,owner:me?`${me.id}:${me.account}`:'',uncertain};
  useEffect(()=>{fieldScope.current.blocked=blocked;return()=>{fieldScope.current.blocked=true;fieldQueue.current.clear();};},[]);
  async function saveField(row:ContractRow,key:InlineKey|'arch',value:string,notify=key==='arch'){
    if(blocked||!active||!me||uncertain||query.isError||!query.data)return false;
    const name=`${row.id}:${key}`,owner=fieldScope.current.owner;
    fieldQueue.current.set(name,{row,key,value,notify});
    if(fieldSaving.current||lock.current)return false;
    let completed=true;
    fieldSaving.current=true;lock.current=true;setBusy(true);setError('');
    try{
      while(fieldQueue.current.size){
        const scope=fieldScope.current;if(scope.blocked||!scope.active||scope.uncertain||scope.owner!==owner){completed=false;fieldQueue.current.clear();break;}
        const [draftKey,draft]=fieldQueue.current.entries().next().value!;fieldQueue.current.delete(draftKey);
        const latest=client.getQueryData<{rows:ContractRow[]}>(['contracts'])?.rows.find(r=>r.id===draft.row.id)??draft.row;
        const history=draft.key==='remark'?contractHistoryDate(latest.remark):'',next=history?historyContractRemark(history,draft.value):draft.value.trim();
        let written=false;
        try{
          if(next!==latest[draft.key]){const result=await contractWrite('/api/m11/fields',{id:latest.id,fields:{[draft.key]:next}});written=true;await refresh();if(draft.notify)announce(receipt(result));}
          if(inlineDraftRef.current[draftKey]===draft.value){
            const copy={...inlineDraftRef.current};delete copy[draftKey];inlineDraftRef.current=copy;inlineControl.current.drafts=copy;setInlineDrafts(copy);
            const node=grid.current?.getRowNode(String(latest.id));
            if(node)grid.current?.refreshCells({force:true,rowNodes:[node],columns:[draft.key]});
          }
        }catch(failure){completed=false;fieldQueue.current.clear();setUncertain(true);setError(`${written?'登记已保存，列表重读失败。':'登记结果待核实。'}${failure instanceof Error?failure.message:'请重读核对。'}勿重复操作。`);break;}
      }
    }finally{fieldSaving.current=false;lock.current=false;setBusy(false);}
    return completed;
  }
  const inlineDisabled=blocked||!active||!me||uncertain||query.isPending||query.isError||busy&&!fieldSaving.current;
  const paymentMethodsKey=JSON.stringify(query.data?.payment_methods??[]);
  const inlineControl=useRef<InlineControl>({disabled:inlineDisabled,methods:query.data?.payment_methods??[],drafts:inlineDrafts,change:changeInline,save:saveField,remark:openRemark,next:row=>nextContractArchiveNo(rows,row)});
  inlineControl.current={disabled:inlineDisabled,methods:query.data?.payment_methods??[],drafts:inlineDrafts,change:changeInline,save:saveField,remark:openRemark,next:row=>nextContractArchiveNo(rows,row)};
  useEffect(()=>{if(active)grid.current?.refreshCells({force:true,columns:['remark','arch_no','ret_date','payment_term','payment_method']});},[active,inlineDisabled,paymentMethodsKey]);
  useEffect(()=>{if(active)grid.current?.refreshCells({force:true,columns:['arch_no']});},[active,rows]);
  useEffect(()=>{if(active)grid.current?.refreshCells({force:true,columns:['actions']});},[active,unavailable]);
  const state=useRef({unavailable,picked,shown,tag});state.current={unavailable,picked,shown,tag};
  const scale=Number(me?.ui_scale_css??1);
  const widths=useGridWidths('contracts',root,scale,active&&!blocked);
  const completeWidths=useMemo(()=>Object.fromEntries((query.data?.columns??[]).filter(c=>['project_seq','date','contract_no','payment_term','payment_method','tag','arch','arch_no','ret_date'].includes(c.key)).map(c=>{
    const values=rows.map(row=>String(row[c.key as keyof ContractRow]??''));
    if(c.key==='payment_method')values.push('未约定',...(query.data?.payment_methods??[]));
    if(c.key==='arch_no')values.push(...[...new Map(rows.map(row=>[row.project_key,row])).values()].map(row=>nextContractArchiveNo(rows,row)));
    if(c.key==='ret_date')values.push('2000-12-31');
    const extra=c.key==='payment_method'?44:c.key==='ret_date'?44:['payment_term','arch_no'].includes(c.key)?20:['tag','arch'].includes(c.key)?12:0;
    return [c.key,completeColumnWidth(values,c.key==='tag'?'纳入状态':c.label.replace('（自动）',''),scale,extra)];
  })),[rows,query.data?.columns,query.data?.payment_methods,scale]);
  const baseColumns=useMemo<ColDef<ContractRow>[]>(()=>[
    {colId:'select',headerName:'选择',...fixedWidth(28,scale),sortable:false,pinned:'left',headerComponent:()=> <Checkbox aria-label="选择当前合同" checked={shown.length>0&&shown.every(r=>picked.has(r.id))} onChange={e=>setPicked(old=>{const next=new Set(old);for(const row of state.current.shown){if(e.target.checked)next.add(row.id);else next.delete(row.id);}return next;})}/>,cellRenderer:(p:ICellRendererParams<ContractRow>)=>p.node.rowPinned?'':<Checkbox aria-label={`选择合同${p.data!.contract_no||p.data!.material}`} checked={state.current.picked.has(p.data!.id)} onChange={e=>setPicked(old=>{const next=new Set(old);if(e.target.checked)next.add(p.data!.id);else next.delete(p.data!.id);return next;})}/>},
    ...(query.data?.columns??[]).filter(c=>c.key!=='ops').map(c=>{
      const numeric=(contractMoneyKeys as readonly string[]).includes(c.key);
      // Keep formatted amounts and totals intact before flexible text columns shrink.
      const header=c.key==='tag'?'纳入状态':c.label.replace('（自动）','');
      const values=numeric?[...rows,...totalRow].map(row=>row[c.key as typeof contractMoneyKeys[number]]===null?'未确定':money(row[c.key as typeof contractMoneyKeys[number]]??'0')):[];
      const measured=numeric?numberColumnWidth(values,scale):undefined;
      const amountWidth=measured?completeColumnWidth(values,header,scale,['inv_sum','trade_inv_sum','pay_sum'].includes(c.key)?56:0):undefined;
      if(amountWidth&&measured)amountWidth.minWidth=amountWidth.initialWidth=Math.max(amountWidth.minWidth,measured.minWidth+(['inv_sum','trade_inv_sum','pay_sum'].includes(c.key)?56*scale:0));
      const bounded=c.key==='material'?{initialWidth:260*scale,...textWidth(220,360,scale,0)}:c.key==='remark'?textWidth(110,210,scale,.7):textWidth(120,c.key==='supplier'?260:240,scale,1);
      return {field:c.key as keyof ContractRow,hide:!trade&&['trade_co','trade_contract_amt','trade_inv_sum'].includes(c.key),headerName:header,...(completeWidths[c.key]??amountWidth??bounded),wrapHeaderText:false,autoHeaderHeight:false,wrapText:false,autoHeight:false,cellClass:numeric?'money':completeWidths[c.key]?'contract-identifier':'',...(['project_seq','date','material'].includes(c.key)?{pinned:'left' as const}:{}),...(['remark','arch_no','ret_date','payment_term','payment_method'].includes(c.key)?{cellRenderer:ContractInlineCell,cellRendererParams:{editKey:c.key,control:()=>inlineControl.current}}:{}),
        comparator:numeric?(a:string|null,b:string|null)=>cents(a??'0')<cents(b??'0')?-1:cents(a??'0')>cents(b??'0')?1:0:undefined,
        cellRenderer:['remark','arch_no','ret_date','payment_term','payment_method'].includes(c.key)?ContractInlineCell:(p:ICellRendererParams<ContractRow>)=>{
          if(p.node.rowPinned)return c.key==='material'?'合计':numeric?money(p.value??'0'):'';
          const row=p.data!;
          if(c.key==='material')return <div className="contract-object"><Button size="small" aria-label={`编辑材料名：${row.material||'材料名未填'}`} onClick={()=>{openEditor(row,true);}}><EllipsisText text={row.material||'材料名未填'}/></Button><small><EllipsisText text={projectRows.find(p=>p.warehouse_name===row.project_key)?.disp||(projects.isPending?'项目读取中…':'项目未匹配')}/></small></div>;
          if(c.key==='tag'||c.key==='arch')return <Tag className={`status-tag ${c.key==='tag'?(row.tag==='纳入台账'?'status-positive':'status-neutral'):(row.arch==='已存档'?'status-positive':row.arch==='资产处'?'status-pending':'status-neutral')}`}>{String(p.value||'未存档')}</Tag>;
          if(c.key==='payment_method')return row.payment_method?<EnumTag kind="payMethod" value={row.payment_method}/>:<span className="muted">未约定</span>;
          if(['inv_sum','trade_inv_sum','pay_sum'].includes(c.key)&&!(c.key==='trade_inv_sum'&&!row.trade_co))return <div className="contract-amount-action"><span>{money(String(p.value??'0'))}</span><Button size="small" aria-label={`${row.contract_no||row.material} ${c.key==='inv_sum'?'供应商发票':c.key==='trade_inv_sum'?'贸易公司发票':'付款'}子表`} onClick={()=>setSubtable({row,kind:c.key==='inv_sum'?'supplier':c.key==='trade_inv_sum'?'trade':'payment'})}>子表</Button></div>;
          return numeric?(p.value===null?'未确定':money(String(p.value))):['supplier','trade_co'].includes(c.key)?<EllipsisText text={String(p.value??'')}/>:String(p.value??'');
        }} as ColDef<ContractRow>;
    }),
    {colId:'actions',headerName:'操作',...completeColumnWidth(['不纳入 推进存档'],'操作',scale,48),sortable:false,cellRenderer:(p:ICellRendererParams<ContractRow>)=>p.node.rowPinned?'':<div className="contract-row-actions"><Button size="small" disabled={state.current.unavailable} onClick={()=>void state.current.tag([p.data!.id],p.data!.tag==='纳入台账'?'不纳入':'纳入台账')}>{p.data!.tag==='纳入台账'?'不纳入':'纳入'}</Button><Button size="small" disabled={state.current.unavailable} onClick={()=>void inlineControl.current.save(p.data!,'arch',p.data!.arch==='未存档'?'资产处':p.data!.arch==='资产处'?'已存档':'未存档')}>推进存档</Button></div>}
  ],[query.data?.columns,trade,scale,shown,picked,projectRows,projects.isPending,completeWidths]);
  const columns=useMemo(()=>manualGridColumns(baseColumns),[baseColumns]);
  // Keep the reset action on the material header, clear of complete identifiers.
  const resetColumns=useMemo(()=>columns.filter(c=>c.field==='material'),[columns]);
  const resetColumn=useGridWidthColumns(resetColumns)[0];
  const widthColumns=useMemo(()=>columns.map(c=>c.field==='material'&&resetColumn?resetColumn:c),[columns,resetColumn]);
  const subBusy=Object.values(subtables).some(s=>s.busy), subUncertain=Object.values(subtables).some(s=>s.uncertain), subDirty=Object.values(subtables).some(hasSubtableDrafts);
  const exportUnavailable=blocked||!active?'当前页面暂不可操作。':!me?'请先登录。':busy||subBusy?'合同正在保存，请稍候。':uncertain||subUncertain?'合同操作结果待核实，请先重读。':subDirty?'合同子表有未保存输入，请先处理。':query.isPending||query.isFetching||projects.isPending||projects.isFetching?'正在读取合同及项目，请稍候。':query.isError||projects.isError?'合同或项目读取失败，请先重读。':Object.keys(inlineDrafts).length?'请先保存收发登记输入。':Object.keys(editors).length||tool||subtable||remarkEditor?'请先处理并关闭合同窗口。':'';
  function exportIds(){if(!grid.current)throw new Error('合同列表尚未准备好，请稍候。');const ids:number[]=[];grid.current.forEachNodeAfterFilterAndSort(node=>{if(node.data&&!node.rowPinned)ids.push(node.data.id);});return ids;}
  const pageState=useRef({blocked,active,editorId});pageState.current={blocked,active,editorId};
  function created(id:number){if(pageState.current.blocked||!pageState.current.active||pageState.current.editorId!=='new')return;setFilters({...initialFilters(),tag:''});setSearch('');pendingFocus.current=id;const row=client.getQueryData<{rows:ContractRow[]}>(['contracts'])?.rows.find(r=>r.id===id);closeEditor('new');if(row){grid.current?.ensureNodeVisible(node=>node.data?.id===id,'middle');if(contractHistoryDate(row.remark))setSubtable({row,kind:'supplier'});}}
  return <section className="contracts-page" aria-labelledby="page-title" data-page-chrome data-page-loading={query.isPending||projects.isPending?true:undefined}><div className="contract-toolbar"><h2>集采台账，合同主表</h2><div><Button disabled={unavailable} onClick={()=>setTool('fetch')}>抓取采购合同信息</Button><Button onClick={()=>{if(trade)grid.current?.applyColumnState({state:['trade_co','trade_contract_amt','trade_inv_sum'].map(colId=>({colId,sort:null}))});setTrade(old=>!old);}}>{trade?'隐藏':'显示'}贸易公司列</Button><Button disabled={unavailable} onClick={()=>openEditor(null)}>＋ 手工新增合同</Button><ContractExports owner={me?`${me.id}:${me.account}`:'anonymous'} projects={projectRows} project={filters.projects.length===1?filters.projects[0]!:0} getIds={exportIds} scope={JSON.stringify([filters,search,sort,query.dataUpdatedAt,projects.dataUpdatedAt])} unavailable={exportUnavailable} paused={blocked||!active}/></div></div>
    <div className="contract-selection"><span>已勾选 {selected.length} 行{hidden>0?`（列表外 ${hidden} 行）`:''}</span>{picked.size>0&&<Button size="small" onClick={()=>setPicked(new Set())}>清空勾选</Button>}<div>{(query.data?.tags??[]).map(value=><Button key={value} disabled={unavailable||!picked.size||hidden>0} title={hidden?'请先清空搜索或调整筛选核对勾选范围':''} onClick={()=>void tag([...picked],value)}>批量{value}</Button>)}</div></div>
    <div className="contract-filters"><label>项目<ProjectPicker projects={projectRows} selected={filters.projects} multiple label="合同筛选项目" emptyLabel="全部项目" disabled={blocked||projects.isPending} pick={ids=>setFilters(old=>({...old,projects:ids}))}/></label><label>纳入状态<Select aria-label="纳入状态" value={filters.tag} options={['',...(query.data?.tags??[])].map(value=>({value,label:value||'全部'}))} onChange={tag=>setFilters(old=>({...old,tag}))}/></label><label>存档情况<Select aria-label="合同存档筛选" value={filters.arch} options={['','未存档','资产处','已存档'].map(value=>({value,label:value||'全部'}))} onChange={arch=>setFilters(old=>({...old,arch}))}/></label><label className="contract-search-field">搜索<Input aria-label="搜索" placeholder="搜索各列内容" value={search} allowClear onChange={e=>setSearch(e.target.value)}/></label><Button disabled={blocked||!active} onClick={()=>setTool('party')}>甲方单位分类</Button><Button onClick={()=>{setFilters(initialFilters());setSearch('');}}>重置</Button><span className="contract-filter-count">已勾选 <b>{selected.length}</b> 行 ｜ 显示 <b>{shown.length}</b> 条</span></div>
    {(error||query.isError||projects.isError)&&<p className="notice" role="alert">{error||(query.isError?`合同更新失败，保留上次结果。${query.error.message}`:projects.error?.message)}<Button onClick={()=>void reread()}>重读核对</Button></p>}
    {editors.new&&<ContractEditor key="new" inline subtables={subtables} changeSubtables={changeSubtables} contracts={rows} created={created} row={null} me={me} projects={projectRows} methods={query.data?.payment_methods??[]} blocked={blocked||!active||editorId!=='new'} close={()=>closeEditor('new')} refresh={refresh} announce={announce}/>}
    {query.isPending?<p role="status">正在读取集采合同…</p>:<GridWidthContext.Provider value={widths}><div className="contracts-grid grid-single-line" ref={root}><AgGridReact<ContractRow> theme={gridTheme} rowBuffer={2} rowData={shown} columnDefs={widthColumns} defaultColDef={defaultColumn} autoSizeStrategy={widths.strategy} getRowId={p=>String(p.data.id)} pinnedBottomRowData={totalRow} rowHeight={pageGridGeometry(scale).rowHeight} headerHeight={pageGridGeometry(scale).headerHeight} suppressCellFocus={false} suppressScrollOnNewData suppressColumnVirtualisation onSortChanged={e=>setSort(JSON.stringify(e.api.getColumnState().filter(c=>c.sort).map(c=>[c.colId,c.sort,c.sortIndex])))} onGridReady={e=>{grid.current=e.api;widths.attach(e.api);}} onRowDataUpdated={e=>{if(pendingFocus.current){const id=pendingFocus.current;pendingFocus.current=0;e.api.ensureNodeVisible(node=>node.data?.id===id,'middle');const target=e.api.getRowNode(String(id));if(target?.rowIndex!=null)e.api.setFocusedCell(target.rowIndex,'material');}}} overlayNoRowsTemplate="没有符合条件的合同，可调整筛选。"/></div></GridWidthContext.Provider>}
    {Object.entries(editors).filter(([key])=>key!=='new').map(([key,editor])=><ContractEditor key={key} materialOnly={editor.materialOnly} subtables={subtables} changeSubtables={changeSubtables} contracts={rows} created={created} row={editor.row} me={me} projects={projectRows} methods={query.data?.payment_methods??[]} blocked={blocked||!active||editorId!==key} close={()=>closeEditor(key)} refresh={refresh} announce={announce}/>)}
    {subtable&&<ContractSubtableDialog scale={scale} row={subtable.row} kind={subtable.kind} contracts={rows} workspace={subtables} change={changeSubtables} paused={blocked||!active} writable={!unavailable} close={()=>setSubtable(null)}/>}
    {remarkEditor&&<ContractRemarkEditor key={remarkEditor.row.id} row={remarkEditor.row} initial={remarkEditor.initial} busy={busy} disabled={blocked||!me||uncertain||query.isPending||query.isError} paused={blocked||!active} error={error} save={async value=>{changeInline(remarkEditor.row.id,'remark',value);return saveField(remarkEditor.row,'remark',value,true);}} close={()=>setRemarkEditor(null)}/>}
    {tool==='fetch'&&<ContractFetch me={me} blocked={blocked||!active} close={()=>setTool(null)} refresh={refresh}/>}
    {tool==='party'&&<ContractSettings kind={tool} me={me} blocked={blocked||!active} close={()=>setTool(null)} refresh={refresh}/>}
  </section>;
}
