import Button from 'antd/es/button';
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
import { contentWidth, fitGridColumns, fixedWidth, gridTheme } from './grid';
import { EnumTag } from './enum-tag';
import { useHistoryGuard } from './history';
import { contractMoneyKeys, contractWrite, readContracts } from './contracts-api';
import type { ContractRow } from './contracts-api';
import { cents, money, receipt } from './notices-api';
import { ContractEditor } from './contract-dialog';
import { ContractFetch, ContractSettings } from './contract-tools';
import './contracts.css';

function decimalCents(value:bigint){const abs=value<0n?-value:value;return `${value<0n?'-':''}${abs/100n}.${String(abs%100n).padStart(2,'0')}`;}
const initialFilters=()=>({projects:[] as number[],tag:'纳入台账',arch:'',supplier:'',amount:''});
export function ContractsPage({ me,blocked,active }: { me:Identity|null;blocked:boolean;active:boolean }) {
  const client=useQueryClient(),grid=useRef<GridApi<ContractRow>|null>(null),root=useRef<HTMLDivElement>(null),lock=useRef(false),pendingFocus=useRef(0);
  const [filters,setFilters]=useState(initialFilters),[search,setSearch]=useState(''),[picked,setPicked]=useState<Set<number>>(()=>new Set()),[trade,setTrade]=useState(false);
  const [editors,setEditors]=useState<Record<string,{row:ContractRow|null}>>({}),[editorId,setEditorId]=useState<string|null>(null),[tool,setTool]=useState<'fetch'|'party'|'ignore'|null>(null);
  function openEditor(row:ContractRow|null){const key=row?String(row.id):'new';setEditors(old=>old[key]?old:{...old,[key]:{row}});setEditorId(key);}
  function closeEditor(key:string){setEditors(old=>{const next={...old};delete next[key];return next;});setEditorId(current=>current===key?null:current);}
  const [busy,setBusy]=useState(false),[feedback,setFeedback]=useState(''),[error,setError]=useState(''),[uncertain,setUncertain]=useState(false);
  const [params]=useSearchParams();
  const query=useQuery({queryKey:['contracts'],enabled:!blocked&&active,refetchOnMount:'always',queryFn:async({signal})=>readContracts(await requestJson('/api/m11/list',{signal}))});
  const projects=useQuery({queryKey:['projects','all'],enabled:!blocked&&active,queryFn:async({signal})=>readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  const rows=query.data?.rows??[], projectRows=projects.data??[];
  const shown=useMemo(()=>rows.filter(row=>(!filters.tag||row.tag===filters.tag)&&(!filters.arch||row.arch===filters.arch)&&(!filters.projects.length||projectRows.some(p=>filters.projects.includes(p.id)&&p.warehouse_name===row.project_key))&&(!filters.supplier||row.supplier.includes(filters.supplier.trim()))&&(!filters.amount||(filters.amount==='empty'?cents(row.contract_amt)===0n:cents(row.contract_amt)!==0n))&&(!search.trim()||[row.material,row.contract_no,row.supplier,row.trade_co,row.remark,row.payment_term,row.payment_method,projectRows.find(p=>p.warehouse_name===row.project_key)?.disp].some(x=>x?.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())))),[rows,projectRows,filters,search]);
  const totalRow=shown.length?[{id:-1,material:'合计',...Object.fromEntries(contractMoneyKeys.map(key=>[key,decimalCents(shown.reduce((sum,row)=>sum+cents(row[key]??'0'),0n))]))} as ContractRow]:[];
  const selected=rows.filter(row=>picked.has(row.id)),hidden=selected.filter(row=>!shown.some(v=>v.id===row.id)).length;
  const unavailable=blocked||!active||!me||busy||uncertain||query.isPending||query.isError||query.isFetching;
  useHistoryGuard('contracts',()=>busy||lock.current?'集采合同正在处理，请稍候。':uncertain?'合同操作结果待核实，请先重读。':'');
  useEffect(()=>{const valid=new Set(rows.map(row=>row.id));setPicked(old=>{const next=new Set([...old].filter(id=>valid.has(id)));return next.size===old.size?old:next;});},[rows]);
  useEffect(()=>{if(!active)return;const id=Number(params.get('contract'));if(id>0&&query.data){const row=query.data.rows.find(row=>row.id===id);pendingFocus.current=id;if(row){setFilters(old=>({...old,tag:'',projects:[]}));setSearch('');openEditor(row);grid.current?.ensureNodeVisible(node=>node.data?.id===id,'middle');}else {setEditorId(null);setError('合同已不在列表中，请重读核对。');}}},[params.get('contract'),active,Boolean(query.data)]);
  useEffect(()=>{if(!blocked&&active&&grid.current)fitGridColumns(grid.current,root.current);},[active,blocked]);
  async function refresh(){await client.invalidateQueries({predicate:q=>q.queryKey[0]!=='contract-detail'&&q.queryKey[0]!=='notice-maintenance'},{throwOnError:true});}
  async function reread(){try{await refresh();setUncertain(false);setError('');setFeedback('已重读，请核对合同状态与关联。');}catch(failure){setError(failure instanceof Error?failure.message:'重读失败，请重试。');}}
  async function tag(ids:number[],value:string){
    if(unavailable||lock.current||!ids.length)return;
    lock.current=true;setBusy(true);setError('');setFeedback('');let written=false;
    try{const result=await contractWrite('/api/m11/tag',{ids,tag:value});written=true;setFeedback(receipt(result));setPicked(old=>new Set([...old].filter(id=>!ids.includes(id))));await refresh();}
    catch(failure){setUncertain(true);setError(`${written?'标记已保存，列表重读失败。':'标记结果待核实。'}${failure instanceof Error?failure.message:'请重读核对。'}勿重复操作。`);}
    finally{lock.current=false;setBusy(false);}
  }
  const state=useRef({unavailable,picked,shown,tag});state.current={unavailable,picked,shown,tag};
  const scale=Number(me?.ui_scale_css??1);
  const columns=useMemo<ColDef<ContractRow>[]>(()=>[
    {colId:'select',headerName:'选择',...fixedWidth(48,scale),sortable:false,pinned:'left',headerComponent:()=> <input type="checkbox" aria-label="选择当前合同" checked={shown.length>0&&shown.every(r=>picked.has(r.id))} onChange={e=>setPicked(old=>{const next=new Set(old);for(const row of state.current.shown){if(e.target.checked)next.add(row.id);else next.delete(row.id);}return next;})}/>,cellRenderer:(p:ICellRendererParams<ContractRow>)=>p.node.rowPinned?'':<input type="checkbox" aria-label={`选择合同${p.data!.contract_no||p.data!.material}`} checked={state.current.picked.has(p.data!.id)} onChange={e=>setPicked(old=>{const next=new Set(old);if(e.target.checked)next.add(p.data!.id);else next.delete(p.data!.id);return next;})}/>},
    ...(query.data?.columns??[]).filter(c=>c.key!=='ops'&&(trade||!['trade_co','trade_contract_amt','trade_inv_sum'].includes(c.key))).map(c=>{
      const numeric=(contractMoneyKeys as readonly string[]).includes(c.key);
      const min=c.key==='project_seq'?42:c.key==='date'||c.key==='ret_date'?86:numeric?116:c.key==='contract_no'?100:c.key==='material'?92:c.key==='supplier'?114:c.key==='remark'?110:c.key==='payment_method'?106:c.key==='payment_term'?80:74;
      return {field:c.key as keyof ContractRow,headerName:c.key==='tag'?'纳入状态':c.label.replace('（自动）',''),...contentWidth(min,c.key==='remark'||c.key==='supplier'?250:Math.max(min,145),scale,['material','supplier','remark'].includes(c.key)?1:0),wrapHeaderText:true,autoHeaderHeight:true,wrapText:!numeric,autoHeight:true,cellClass:numeric?'money':'',...(c.key==='material'?{pinned:'left' as const}:{}),
        comparator:numeric?(a:string|null,b:string|null)=>cents(a??'0')<cents(b??'0')?-1:cents(a??'0')>cents(b??'0')?1:0:undefined,
        cellRenderer:(p:ICellRendererParams<ContractRow>)=>{
          if(p.node.rowPinned)return c.key==='material'?'合计':numeric?money(p.value??'0'):'';
          const row=p.data!;
          if(c.key==='material')return <div className="contract-object"><Button size="small" onClick={()=>{openEditor(row);}}>{row.material||'材料名未填'}</Button><small>{projectRows.find(p=>p.warehouse_name===row.project_key)?.disp||(projects.isPending?'项目读取中…':'项目未匹配')}</small></div>;
          if(c.key==='tag'||c.key==='arch')return <Tag className={`enum-tag ${c.key==='tag'?(row.tag==='纳入台账'?'status-positive':'status-neutral'):(row.arch==='已存档'?'status-positive':row.arch==='资产处'?'status-pending':'status-neutral')}`}>{String(p.value||'未存档')}</Tag>;
          if(c.key==='payment_method')return row.payment_method?<EnumTag kind="payMethod" value={row.payment_method}/>:<span className="muted">未约定</span>;
          return numeric?(p.value===null?'未确定':money(String(p.value))):String(p.value??'');
        }} as ColDef<ContractRow>;
    }),
    {colId:'actions',headerName:'操作',...contentWidth(94,140,scale),sortable:false,wrapText:true,autoHeight:true,cellRenderer:(p:ICellRendererParams<ContractRow>)=>p.node.rowPinned?'':<div className="contract-row-actions"><Button size="small" disabled={state.current.unavailable} onClick={()=>void state.current.tag([p.data!.id],p.data!.tag==='纳入台账'?'不纳入':'纳入台账')}>{p.data!.tag==='纳入台账'?'不纳入':'纳入'}</Button><Button size="small" onClick={()=>{openEditor(p.data!);}}>维护</Button></div>}
  ],[query.data?.columns,trade,scale,shown,picked,projectRows,projects.isPending]);
  return <section className="contracts-page" aria-labelledby="page-title"><div className="contract-toolbar"><div><Button className="primary" disabled={unavailable} onClick={()=>openEditor(null)}>新增合同</Button><Button disabled={unavailable} onClick={()=>setTool('fetch')}>抓取采购合同</Button><Button onClick={()=>setTrade(old=>!old)}>{trade?'隐藏':'显示'}贸易公司列</Button></div><div><Button disabled={blocked||!active} onClick={()=>setTool('party')}>甲方单位分类</Button><Button disabled={blocked||!active} onClick={()=>setTool('ignore')}>项目忽略名单</Button><Button disabled={blocked||busy} onClick={()=>void reread()}>重读</Button></div></div>
    <div className="contract-filters"><label>项目<ProjectPicker projects={projectRows} selected={filters.projects} multiple label="合同筛选项目" emptyLabel="全部项目" disabled={blocked||projects.isPending} pick={ids=>setFilters(old=>({...old,projects:ids}))}/></label><label>纳入状态<Select aria-label="纳入状态" value={filters.tag} options={['',...(query.data?.tags??[])].map(value=>({value,label:value||'全部'}))} onChange={tag=>setFilters(old=>({...old,tag}))}/></label><label>存档情况<Select aria-label="合同存档筛选" value={filters.arch} options={['','未存档','资产处','已存档'].map(value=>({value,label:value||'全部'}))} onChange={arch=>setFilters(old=>({...old,arch}))}/></label><label>供应商<Input value={filters.supplier} onChange={e=>setFilters(old=>({...old,supplier:e.target.value}))}/></label><label>合同金额<Select aria-label="合同金额筛选" value={filters.amount} options={[{value:'',label:'全部'},{value:'empty',label:'为空（待补）'},{value:'value',label:'非空'}]} onChange={amount=>setFilters(old=>({...old,amount}))}/></label><label>搜索<Input value={search} allowClear onChange={e=>setSearch(e.target.value)}/></label><Button onClick={()=>{setFilters(initialFilters());setSearch('');}}>重置</Button></div>
    <div className="contract-selection"><span>显示 {shown.length} 条 · 已勾选 {selected.length} 行{hidden>0?`（列表外 ${hidden} 行）`:''}</span>{picked.size>0&&<Button size="small" onClick={()=>setPicked(new Set())}>清空勾选</Button>}<div>{(query.data?.tags??[]).map(value=><Button key={value} disabled={unavailable||!picked.size||hidden>0} title={hidden?'请先清空搜索或调整筛选核对勾选范围':''} onClick={()=>void tag([...picked],value)}>批量{value}</Button>)}</div></div>
    {(feedback||busy||query.isFetching&&!query.isPending)&&<p className="contract-feedback" role="status">{busy?'正在保存…':query.isFetching?'正在更新合同，保留当前列表…':feedback}</p>}
    {(error||query.isError||projects.isError)&&<p className="notice" role="alert">{error||(query.isError?`合同更新失败，保留上次结果。${query.error.message}`:projects.error?.message)}<Button onClick={()=>void reread()}>重读核对</Button></p>}
    {query.isPending?<p role="status">正在读取集采合同…</p>:<div className="contracts-grid" ref={root}><AgGridReact<ContractRow> theme={gridTheme} rowData={shown} columnDefs={columns} defaultColDef={{sortable:true,resizable:true,suppressMovable:true}} getRowId={p=>String(p.data.id)} pinnedBottomRowData={totalRow} rowHeight={60*scale} headerHeight={42*scale} suppressCellFocus={false} suppressScrollOnNewData suppressColumnVirtualisation onGridReady={e=>{grid.current=e.api;fitGridColumns(e.api,root.current,true);}} onFirstDataRendered={e=>fitGridColumns(e.api,root.current,true)} onGridSizeChanged={e=>fitGridColumns(e.api,root.current)} onRowDataUpdated={e=>{fitGridColumns(e.api,root.current);if(pendingFocus.current){const id=pendingFocus.current;pendingFocus.current=0;e.api.ensureNodeVisible(node=>node.data?.id===id,'middle');}}} overlayNoRowsTemplate="没有符合条件的合同，可调整筛选。"/></div>}
    {Object.entries(editors).map(([key,editor])=><ContractEditor key={key} row={editor.row} me={me} projects={projectRows} methods={query.data?.payment_methods??[]} blocked={blocked||!active||editorId!==key} close={()=>closeEditor(key)} refresh={refresh} announce={setFeedback}/>)}
    {tool==='fetch'&&<ContractFetch me={me} blocked={blocked||!active} close={()=>setTool(null)} refresh={refresh}/>}
    {(tool==='party'||tool==='ignore')&&<ContractSettings kind={tool} me={me} blocked={blocked||!active} close={()=>setTool(null)} refresh={refresh}/>}
  </section>;
}
