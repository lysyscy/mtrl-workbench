import Button from 'antd/es/button';
import { EnumTag } from './enum-tag';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ComponentProps } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useIsFetching, useQuery } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { ApiError, record, requestJson, readProjects } from './api';
import { LedgerPage } from './ledger';
import { ProjectPicker } from './ledger-controls';
import { body, cents, currentMonth, decimal, money, searchKey } from './notices-api';
import { loadFlows, saveBlob } from './flow-api';
import type { Flow } from './flow-api';
import { FlowRevoke } from './flow-revoke';
import { fitGridColumns, contentWidth, gridTheme } from './grid';
import './flow.css';
import { TimePicker, timeMatches } from './time-picker';
interface Bar { key: string; label: string; amount: string }
interface Debt { project: string; jc: string; material: string; mech: string }
interface Stats { granularity: string; buckets: string[]; right: string[]; counts: number[]; selected: { bucket: string; projects: Bar[]; total: string; count: number } }
const initial = () => ({ period:currentMonth(), projects: [] as number[], method:'', status:'effective', keyword:'', notice:0 });
function Bars({ rows, choose, selected }: { rows: Bar[]; choose?: (key:string) => void; selected?: string | undefined }) {
  const max=rows.reduce((value,row)=> { const n=cents(row.amount);return n<0n ? -n>value?-n:value : n>value?n:value; },1n);
  return <div className="flow-bars">{rows.map(row => {
    const value=cents(row.amount), width=Number((value<0n?-value:value)*10000n/max)/100;
    const content=[<span key="name" className="bar-name">{row.label}</span>,<span key="track" className="bar-track"><i className={value<0n?'negative':''} style={{width:`${width}%`}} /></span>,<span key="amount" className="money">{money(row.amount)}</span>];
    return choose ? <Button htmlType="submit" key={row.key} className="flow-bar" aria-pressed={selected===row.key} onClick={()=>choose(row.key)} title="筛选下方付款流水，再点一次取消">{content}</Button> : <div key={row.key} className="flow-bar">{content}</div>;
  })}</div>;
}
function ReadState({ query }: { query: {isPending:boolean;isError:boolean;error:Error|null;refetch:()=>unknown} }) {
  return query.isError ? <p className="notice" role="alert">{query.error?.message}<Button htmlType="submit" onClick={()=>void query.refetch()}>重试读取</Button></p> : query.isPending ? <p role="status">正在读取…</p> : null;
}
export function FlowPage(props: ComponentProps<typeof LedgerPage>) {
  const [params] = useSearchParams();
  const [filter,setFilter]=useState(initial), [search,setSearch]=useState(''), [guard,setGuard]=useState(''), [revoke,setRevoke]=useState<Flow|null>(null), [feedback,setFeedback]=useState(''), [error,setError]=useState(''), [exporting,setExporting]=useState(false);
  const [gran,setGran]=useState('week'),[year,setYear]=useState(Number(currentMonth().slice(0,4))),[quarter,setQuarter]=useState(Math.ceil(Number(currentMonth().slice(5))/3)),[bucket,setBucket]=useState('');
  const api=useRef<GridApi<Flow>|null>(null), gridRoot=useRef<HTMLDivElement>(null), flowSection=useRef<HTMLElement>(null), locatePending=useRef(false);
  const ledgerLoading=useIsFetching({queryKey:['ledger']});
  const enabled=props.active && !props.blocked;
  const flows=useQuery({queryKey:['flows'],enabled,queryFn:({signal})=>loadFlows(signal)});
  const debt=useQuery({queryKey:['debt'],enabled,queryFn:async({signal}):Promise<Debt[]>=>{
    const data=await requestJson('/api/m05/debt',{signal});
    if(!record(data)||!Array.isArray(data.by_project_category))throw new ApiError('欠款读取不完整，请重试。');
    return data.by_project_category.map(row=>{ if(!record(row)||typeof row.project!=='string')throw new ApiError('欠款读取不完整，请重试。');return {project:row.project,jc:String(row.jc),material:String(row.material),mech:String(row.mech)}; });
  }});
  const stats=useQuery({queryKey:['payment-stats',gran,year,quarter,bucket],enabled,queryFn:async({signal}):Promise<Stats>=>{
    const data=await requestJson(`/api/m05/stats?${new URLSearchParams({granularity:gran,year:String(year),quarter:String(quarter),bucket})}`,{signal});
    if(!record(data)||!Array.isArray(data.buckets)||!Array.isArray(data.right)||!record(data.selected))throw new ApiError('付款统计读取不完整，请重试。');return data as unknown as Stats;
  }});
  useEffect(()=>{ if(enabled){void flows.refetch();void debt.refetch();void stats.refetch();} },[props.active]);
  useEffect(()=>{ if (!props.active) return; const id=Number(params.get('notice'));if(id>0){locatePending.current=true;setFilter({...initial(),period:'全部',status:'',notice:id});setSearch('');} },[params.get('notice'),props.active]);
  useEffect(()=>{if(enabled&&!flows.isPending&&!ledgerLoading&&props.project>0&&locatePending.current){locatePending.current=false;requestAnimationFrame(()=>flowSection.current?.scrollIntoView({block:'start'}));}},[params,enabled,flows.isPending,ledgerLoading,props.project]);
  const projectQuery=useQuery({queryKey:['projects','all',''],enabled,queryFn:async({signal})=>readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  const projects=useMemo(()=>(projectQuery.data??[]).filter(project=>(flows.data??[]).some(row=>row.project_id===project.id)||filter.projects.includes(project.id)),[projectQuery.data,flows.data,filter.projects]);
  const rows=useMemo(()=>(flows.data??[]).filter(row=> {
    const f=filter, needle=searchKey(f.keyword);
    const time=timeMatches(f.period,row.pay_date);
    return time&&(!f.projects.length||f.projects.includes(row.project_id??0))&&(!f.notice||f.notice===row.notice_id)&&(!f.method||row.pay_method===f.method)&&(!f.status||f.status===row.status)&&(!needle||Object.values(row).some(value=>value!==null&&searchKey(String(value)).includes(needle)));
  }),[flows.data,filter]);
  const effective=rows.filter(row=>row.status==='effective'),total=decimal(effective.reduce((n,row)=>n+cents(row.amount),0n));
  const writable=Boolean(props.me)&&enabled&&!flows.isFetching&&!flows.isError&&!guard;
  const current=useRef({writable,open:setRevoke});current.current={writable,open:setRevoke};
  const scale=Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))||1;
  const columns=useMemo<ColDef<Flow>[]>(()=> { const list:ColDef<Flow>[]=[
    {field:'doc_no',tooltipField:'doc_no',headerName:'单据编码',...contentWidth(145,195,scale),cellRenderer:(p:ICellRendererParams<Flow>)=>p.data?.notice_id&&p.value?<Link className="text-link" to={`/notices?notice=${p.data.notice_id}`}>{p.value}</Link>:p.value||'—'},
    {field:'doc_date',tooltipField:'doc_date',headerName:'通知书日期',...contentWidth(100,150,scale)},{field:'bill_name',headerName:'通知书名称',...contentWidth(100,320,scale,1),wrapText:true,autoHeight:true},
    {field:'project_display',headerName:'付款项目',...contentWidth(85,280,scale,1),wrapText:true,autoHeight:true},{field:'payee',headerName:'收款单位',...contentWidth(100,320,scale,1),wrapText:true,autoHeight:true},{field:'category_label',headerName:'分类',...contentWidth(60,90,scale),cellRenderer:(p:ICellRendererParams<Flow>)=><EnumTag kind="category" value={p.value}/>},
    {field:'amount_approved',headerName:'审批金额',...contentWidth(110,175,scale),cellClass:'money',valueFormatter:p=>p.value===null||p.value===undefined?'—':money(p.value),comparator:(a,b)=>Number(a??0)-Number(b??0)},
    {field:'pay_date',tooltipField:'pay_date',headerName:'付款日期',...contentWidth(100,150,scale)},{field:'amount',headerName:'付款金额',...contentWidth(110,175,scale),cellClass:'money',valueFormatter:p=>p.value?money(p.value):'',comparator:(a,b)=>Number(a)-Number(b)},
    {field:'pay_method',headerName:'实际付款方式',...contentWidth(100,150,scale),cellRenderer:(p:ICellRendererParams<Flow>)=><EnumTag kind="payMethod" value={p.value}/>},{field:'remark',headerName:'备注',...contentWidth(90,320,scale,1),wrapText:true,autoHeight:true},{field:'created_by',tooltipField:'created_by',headerName:'操作人',...contentWidth(70,120,scale)},
    {field:'status_label',headerName:'状态',...contentWidth(90,260,scale,1),wrapText:true,autoHeight:true,cellRenderer:(p:ICellRendererParams<Flow>)=>p.data?<span><span className={`status-tag ${p.data.status==='effective'?'status-positive':'status-neutral'}`}>{p.data.status_label}</span>{p.data.revoke_reason&&<span>（{p.data.revoke_reason}）</span>}</span>:''},
    {colId:'actions',headerName:'操作',...contentWidth(76,100,scale),sortable:false,cellRenderer:(p:ICellRendererParams<Flow>)=>p.data?.status==='effective'?<Button htmlType="submit" className="danger" disabled={!current.current.writable} onClick={()=>current.current.open(p.data!)}>撤销</Button>:null},
  ]; return list; },[scale]);
  useEffect(()=>{api.current?.refreshCells({force:true});},[writable]);
  async function exportFlows() {
    if(exporting||!props.me||!enabled||flows.isError)return;
    setExporting(true);setError('');
    try {
      const ids:number[]=[];api.current?.forEachNodeAfterFilterAndSort(node=>{if(node.data)ids.push(node.data.id);});
      const data=await requestJson('/api/m05/flows/export',{method:'POST',...body({ids})});
      if(!record(data)||typeof data.content_b64!=='string'||typeof data.filename!=='string')throw new ApiError('导出结果不完整，请重试。');
      const bytes=Uint8Array.from(atob(data.content_b64),c=>c.charCodeAt(0));saveBlob(new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}),data.filename);setFeedback(`已导出 ${data.rows} 条付款流水。`);
    } catch(failure){setError(failure instanceof Error?failure.message:'导出失败，请重试。');}finally{setExporting(false);}
  }
  function chooseProject(key:string) {
    const project=projectQuery.data?.find(p=>p.warehouse_name===key);
    // Stats entries with no flows still remain a real filter, rather than silently showing all.
    const id=project?.id??0;
    setFilter(f=>({...f,projects:f.projects.length===1&&f.projects[0]===id?[]:[id]}));
    flowSection.current?.scrollIntoView({block:'start',behavior:'smooth'});
  }
  const categories=[['jc','集采'],['material','辅材'],['mech','机械']] as const;
  const trend=(stats.data?.buckets??[]).map((key,i)=>({key,label:gran==='month'?key:key+' 起',amount:stats.data!.right[i]??'0.00'}));
  return <div className="flow-workspace">
    <div className="debt-overviews">{categories.map(([key,label])=><section className="flow-card" key={key}><h2>按项目看{label}欠款</h2><div className="flow-card-body"><ReadState query={debt}/>{debt.data&&(()=>{const items=debt.data.filter(row=>cents(row[key])!==0n).sort((a,b)=>cents(a[key])>cents(b[key])?-1:1);return items.length?<Bars rows={items.map((row,index)=>({key:String(index),label:row.project,amount:row[key]}))}/>:<p className="muted">暂无{label}未结清欠款</p>;})()}</div></section>)}</div>
    <LedgerPage {...props} onExportGuard={value=>{setGuard(value);props.onExportGuard(value);}}/>
    <section className="flow-card" aria-labelledby="stats-title"><div className="flow-card-head payment-stat-head"><h2 id="stats-title">付款统计</h2><div><Button htmlType="submit" aria-pressed={gran==='week'} onClick={()=>{setGran('week');setBucket('');}}>按周（周一至周日）</Button><Button htmlType="submit" aria-pressed={gran==='month'} onClick={()=>{setGran('month');setBucket('');}}>按月</Button></div></div><div className="flow-card-body">
      <ReadState query={stats}/>{stats.data&&<div className="payment-stat-columns"><div><div className="flow-toolbar"><strong>按项目</strong><TimePicker label={gran==='week'?'统计周':'统计月'} value={bucket||stats.data.selected.bucket.slice(0,gran==='week'?10:7)} modes={gran==='week'?['周']:['月']} onChange={setBucket}/><span>合计 {money(stats.data.selected.total)} 元 · {stats.data.selected.count} 笔</span></div>{stats.data.selected.projects.length?<Bars rows={stats.data.selected.projects} choose={chooseProject} selected={projects.find(p=>filter.projects.includes(p.id))?.warehouse_name??undefined}/>:<p className="muted">该时段没有付款。</p>}</div><div><div className="flow-toolbar"><strong>按{gran==='week'?'周':'月'}</strong><TimePicker label="统计窗口" value={gran==='week'?`${year}Q${quarter}`:String(year)} modes={gran==='week'?['季度']:['年']} onChange={value=>{setYear(Number(value.slice(0,4)));if(gran==='week')setQuarter(Number(value.slice(5)));}}/><span>窗口合计 {money(decimal(trend.reduce((n,row)=>n+cents(row.amount),0n)))} 元</span></div><Bars rows={trend}/></div></div>}
    </div></section>
    <section ref={flowSection} className="flow-card" aria-labelledby="flows-title"><div className="flow-card-head"><h2 id="flows-title">付款流水（实际付款记录）</h2><Button htmlType="submit" disabled={!props.me||!enabled||!rows.length||flows.isFetching||flows.isError||exporting||Boolean(guard)} title={guard||''} onClick={()=>void exportFlows()}>{exporting?'正在导出…':'导出 Excel'}</Button></div>
      <div className="flow-toolbar"><div className="time-picker-field"><span>付款时间</span><TimePicker label="付款时间" value={filter.period} modes={['月','跨月','年','全部']} onChange={period=>setFilter(f=>({...f,period}))} /></div>
      <span>付款项目</span><ProjectPicker projects={projects} selected={filter.projects} multiple emptyLabel="全部项目" pick={ids=>setFilter(f=>({...f,projects:ids}))} label="付款项目"/>
      <label>实际付款方式<select value={filter.method} onChange={e=>setFilter(f=>({...f,method:e.target.value}))}><option value="">全部</option>{['现汇','承兑','供应链','其他'].map(v=><option key={v}>{v}</option>)}</select></label><label>状态<select value={filter.status} onChange={e=>setFilter(f=>({...f,status:e.target.value}))}><option value="">全部</option><option value="effective">生效</option><option value="revoked">已撤销</option></select></label>
      <form onSubmit={e=>{e.preventDefault();setFilter(f=>({...f,keyword:search}));}}><label>关键词<input value={search} onChange={e=>setSearch(e.target.value)}/></label><Button htmlType="submit">搜索</Button></form><Button htmlType="submit" onClick={()=>{setFilter(initial());setSearch('');}}>重置</Button><span>显示 {rows.length} 条</span>{filter.notice>0&&<Button htmlType="submit" onClick={()=>setFilter(f=>({...f,notice:0}))}>清除通知书定位</Button>}{filter.projects.includes(0)&&<span>待指定归属</span>}
      </div><ReadState query={flows}/>{feedback&&<p role="status">{feedback}</p>}{error&&<p className="notice" role="alert">{error}</p>}{guard&&<p className="muted">{guard}</p>}
      {flows.data&&<><div className="flow-grid" ref={gridRoot} style={{height:Math.min(420,(Math.max(rows.length,1)*38+58)*scale)}}><AgGridReact<Flow> theme={gridTheme} onFirstDataRendered={e=>fitGridColumns(e.api,gridRoot.current,true)} onGridSizeChanged={e=>fitGridColumns(e.api,gridRoot.current)} onNewColumnsLoaded={e=>fitGridColumns(e.api,gridRoot.current,true)} suppressColumnVirtualisation enableCellTextSelection ensureDomOrder rowData={rows} columnDefs={columns} defaultColDef={{cellDataType:false,sortable:true,resizable:false,suppressMovable:true,wrapHeaderText:true,autoHeaderHeight:true}} getRowId={p=>String(p.data.id)} rowHeight={38*scale} headerHeight={34*scale} onGridReady={e=>{api.current=e.api;}} overlayNoRowsTemplate="当前筛选没有付款流水。"/></div><div className="flow-total">合计（生效 {effective.length} 条）<b>{money(total)} 元</b></div></>}
    </section>
    {revoke&&<FlowRevoke key={revoke.id} flow={revoke} blocked={!writable} close={()=>setRevoke(null)} completed={(notice,text)=>{if(notice)window.dispatchEvent(new CustomEvent('payment-revoked',{detail:notice}));setFeedback(text);}}/>}
  </div>;
}
