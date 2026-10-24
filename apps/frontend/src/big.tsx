import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ColGroupDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { readProjects, requestJson } from './api';
import type { Identity, Project } from './api';
import { pageGridGeometry, contentWidth, fitGridColumns, fixedWidth, gridTheme } from './grid';
import { ProjectPicker, reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { BoundedTable } from './bounded-table';
import { useHistoryGuard } from './history';
import { money } from './notices-api';
import { SettlementExport } from './settlement-export';
import { getBig, manualKeys, saveBigCell, saveBigSelection, uncertainBig } from './big-api';
import type { AutoKey, BigData, BigRow, DerivedKey, ManualKey, TotalKey } from './big-api';
import './big.css';

type Props = { me: Identity | null; blocked: boolean; active: boolean };
const labels: Record<ManualKey,string> = {open_ym:'开工时间',mech_est:'机械费测算',contract:'合同（预估）价',output_cum:'产值累计（含税）',oil:'工程用油',note:'备注'};
interface Draft { warehouse: string; display: string; key: ManualKey; value: string; original: string; error: string; revision: number }
const keyOf = (warehouse: string,key: ManualKey) => JSON.stringify([warehouse,key]);
interface Cells {
  drafts: Record<string,Draft>; disabled: boolean;
  change: (row: BigRow,key: ManualKey,value: string) => void;
  save: (key: string,retry?: boolean) => void; cancel: (key: string) => void;
  focus: (warehouse: string,key: ManualKey) => void;
}
const BigCells = createContext<Cells | null>(null);
function ManualInput({data,node,colDef,api}: ICellRendererParams<BigRow>) {
  const cells = useContext(BigCells)!;
  if (!data || node.rowPinned) return null;
  const field = colDef!.colId as ManualKey, key = keyOf(data.warehouse,field), draft = cells.drafts[key], cell = data.manual[field];
  return <div className={`big-manual${draft ? ' is-draft' : ''}${draft?.error ? ' has-error' : ''}`}>
    <Input aria-label={`${data.display} · ${labels[field]}`} value={draft?.value ?? cell.value ?? ''} disabled={cells.disabled}
      placeholder="待填" status={draft?.error ? 'error' : ''} title={draft?.error || (draft ? '未保存' : cell.from ? `带入自 ${cell.from}；修改保存为本月值，清空恢复带入` : cell.value === null ? '尚未录入' : '本月录入；清空恢复带入')}
      className={field === 'note' || field === 'open_ym' ? '' : 'big-money-input'}
      onFocus={() => {const width=colDef?.context?.editingWidth;if(width && (api.getColumn(field)?.getActualWidth() ?? 0)<width)api.setColumnWidths([{key:field,newWidth:width}]);}}
      onChange={e => cells.change(data,field,e.target.value)} onBlur={e => {cells.save(key);fitGridColumns(api,e.currentTarget.closest<HTMLElement>('.big-grid'));}} onKeyDown={e => {
        e.stopPropagation(); if(e.nativeEvent.isComposing) return;
        if(e.key === 'Enter') {e.preventDefault();cells.save(key,true);}
        if(e.key === 'Escape') cells.cancel(key);
        if(e.key === 'Tab') {
          const index = manualKeys.indexOf(field), nextIndex = index + (e.shiftKey ? -1 : 1);
          const next = nextIndex >= 0 && nextIndex < manualKeys.length ? node : api.getDisplayedRowAtIndex((node.rowIndex ?? 0) + (e.shiftKey ? -1 : 1));
          if(next?.data) {e.preventDefault();cells.save(key);api.ensureIndexVisible(next.rowIndex ?? 0);cells.focus(next.data.warehouse,manualKeys[(nextIndex+manualKeys.length)%manualKeys.length]!);}
        }
      }} />
    {draft ? <Tag className="big-origin-tag">{draft.error ? '保存失败' : '未保存'}</Tag> : cell.from ? <Tag className="big-carry-tag" title={`带入自 ${cell.from}`}>{cell.from} 带入</Tag> : cell.value !== null ? <span className="big-origin">本月</span> : null}
  </div>;
}

export function BigPage(props: Props) {
  const [ym,setYm] = useState(reportMonth), [visited,setVisited] = useState(() => [ym]);
  const projects = useQuery({queryKey:['projects','all'],enabled:props.active && !props.blocked,queryFn:async({signal}) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  function choose(value: string) {setYm(value);setVisited(old => old.includes(value) ? old : [...old,value]);}
  return <section className="big-page" aria-label="月度会大表">
    <div className="big-period"><label>核算月<TimePicker label="大表核算月" value={ym} onChange={choose} modes={['月']} disabled={props.blocked} /></label></div>
    {visited.map(month => <div className="big-month" key={month} hidden={month !== ym} inert={month !== ym}><BigMonth {...props} ym={month} active={props.active && month === ym} projects={projects.data ?? []} projectsError={projects.error?.message ?? ''} retryProjects={() => void projects.refetch()} /></div>)}
  </section>;
}

function BigMonth({ym,me,blocked,active,projects,projectsError,retryProjects}: Props & {ym:string;projects:Project[];projectsError:string;retryProjects:()=>void}) {
  const root = useRef<HTMLDivElement>(null), api = useRef<GridApi<BigRow> | null>(null), client = useQueryClient();
  const queryKey = ['big',ym];
  const query = useQuery({queryKey,enabled:active && !blocked,queryFn:({signal}) => getBig(ym,signal)});
  const [drafts,setDrafts] = useState<Record<string,Draft>>({}), [busy,setBusy] = useState(false), [uncertain,setUncertain] = useState(false), [verified,setVerified] = useState(false);
  const [error,setError] = useState(''), [feedback,setFeedback] = useState(''), [picking,setPicking] = useState(false), [locate,setLocate] = useState<string | undefined>();
  const writeAbort = useRef(new AbortController());
  useEffect(() => { writeAbort.current = new AbortController(); return () => writeAbort.current.abort(); }, []);
  const lock = useRef(false), queue = useRef<string[]>([]), alive = useRef(true), revision = useRef(0);
  const state = useRef({drafts,active,blocked,uncertain,me,data:query.data});state.current = {drafts,active,blocked,uncertain,me,data:query.data};
  const update = (next: Record<string,Draft>) => {state.current.drafts=next;setDrafts(next);};
  useEffect(() => {alive.current=true;return () => {alive.current=false;queue.current=[];};},[]);
  useEffect(() => {if(!active || blocked) queue.current=[];},[active,blocked]);
  useHistoryGuard(`big:${ym}`,() => lock.current ? '大表正在保存，请稍候。' : state.current.uncertain ? '大表保存结果待核实，请先核对。' : Object.keys(state.current.drafts).length || picking ? '大表有未保存输入，请先处理。' : '');
  const dirty = Object.keys(drafts).length > 0;
  const disabled = blocked || !active || !me || uncertain || query.isPending || query.isError;
  const controlsDisabled = disabled || busy || dirty || query.isFetching;
  async function reload() {
    await client.cancelQueries({queryKey,exact:true});
    return client.fetchQuery({queryKey,staleTime:0,queryFn:({signal}) => getBig(ym,signal)});
  }
  async function refreshOthers() {await client.invalidateQueries({predicate:q => q.queryKey[0] !== 'big' || q.queryKey[1] !== ym});}
  async function drain() {
    if(lock.current || !state.current.active || state.current.blocked || state.current.uncertain || !state.current.me) return;
    const id = queue.current.shift();if(!id) return;
    const draft = state.current.drafts[id];if(!draft || draft.error) {void drain();return;}
    if(!state.current.data?.rows.some(r => r.warehouse === draft.warehouse)) {update({...state.current.drafts,[id]:{...draft,error:'项目已不在大表中，请取消此项或重新选题。'}});return;}
    lock.current=true;setBusy(true);setError('');setFeedback('');let written=false;
    try {
      await saveBigCell(ym,draft.warehouse,draft.key,draft.value,writeAbort.current.signal);written=true;
      if(!alive.current) return;
      const next={...state.current.drafts};
      if(next[id]?.revision === draft.revision) delete next[id];
      else if(next[id]) next[id]={...next[id],original:draft.value};
      update(next);
      await reload();await refreshOthers();
      if(alive.current) setFeedback(`${draft.display} · ${labels[draft.key]} · ${draft.value.trim() ? '已保存到本月' : '已清空，恢复带入'}`);
    } catch(e) {
      if(!alive.current) return;
      const message=e instanceof Error ? e.message : '保存失败，请重试。';
      if(written || uncertainBig(e)) {state.current.uncertain=true;setUncertain(true);setVerified(false);queue.current=[];setError(`${written ? '已保存，重读失败。' : '保存结果待核实。'}${message}请重读核对，勿重复提交。`);}
      else {queue.current=[];const next={...state.current.drafts};if(next[id]) next[id]={...next[id],error:message};update(next);setError(message);}
    } finally {lock.current=false;if(alive.current) {setBusy(false);void drain();}}
  }
  function save(id: string,retry=false) {
    const draft=state.current.drafts[id];if(!draft || !active || blocked || uncertain) return;
    if(draft.error && !retry) return;
    if(retry) update({...state.current.drafts,[id]:{...draft,error:''}});
    if(!queue.current.includes(id)) queue.current.push(id);void drain();
  }
  async function selection(selected: string[]) {
    if(lock.current || controlsDisabled) return false;
    lock.current=true;setBusy(true);setError('');setFeedback('');let written=false;
    try {
      await saveBigSelection(selected,writeAbort.current.signal);written=true;await reload();await refreshOthers();setFeedback('项目与顺序已保存。');return true;
    } catch(e) {
      const message=e instanceof Error ? e.message : '选题保存失败。';
      if(written || uncertainBig(e)) {state.current.uncertain=true;setUncertain(true);setVerified(false);setError(`${written ? '选题已保存，重读失败。' : '选题结果待核实。'}${message}请重读核对。`);}
      else setError(message);
      return false;
    } finally {lock.current=false;setBusy(false);}
  }
  const scale=Number(me?.ui_scale_css ?? 1);
  const [fontsReady,setFontsReady]=useState(false);
  const [rendered,setRendered]=useState(0);
  useEffect(()=>{const frame=requestAnimationFrame(()=>setRendered(n=>n+1));return()=>cancelAnimationFrame(frame);},[scale,active]);
  useEffect(()=>{let live=true;void document.fonts.ready.then(()=>{if(live)setFontsReady(true);});return()=>{live=false;};},[]);
  const columns=useMemo<(ColDef<BigRow>|ColGroupDef<BigRow>)[]>(() => {
    function value(key: AutoKey|DerivedKey|ManualKey,p: {data:BigRow|undefined;node?:{rowPinned?:string|null|undefined}|null}) {
      if(p.node?.rowPinned) return (p.data as unknown as {totals:BigData['totals']})?.totals[key as TotalKey] ?? null;
      if(!p.data) return null;
      return key in p.data.auto ? p.data.auto[key as AutoKey] : key in p.data.derived ? p.data.derived[key as DerivedKey] : p.data.manual[key as ManualKey].value;
    }
    const context = document.createElement('canvas').getContext('2d');
    const font = getComputedStyle(document.documentElement);
    if (context) context.font = `600 ${Number(font.getPropertyValue('--font-ui-size')) || 13.5}px ${font.getPropertyValue('--fs')}`;
    const digitWidth=Math.max(...[...'0123456789'].map(char=>context?.measureText(char).width ?? 8.2));
    const pattern=(text:string)=>text.replace(/[0-9]/g,'0');
    const measured=new Map<string,number>();
    for(const cell of root.current?.querySelectorAll<HTMLElement>('.ag-row-pinned .ag-cell-value') ?? []) {
      const range=document.createRange();range.selectNodeContents(cell);
      const width=range.getBoundingClientRect().width;
      const renderedScale=parseFloat(getComputedStyle(cell).fontSize)/(Number(font.getPropertyValue('--font-ui-size')) || 13.5);
      if(cell.textContent?.trim() && Number.isFinite(width) && width>0 && Math.abs(renderedScale-scale)<.01) measured.set(pattern(cell.textContent.trim()),width / scale);
    }
    const textWidth=(text:string)=>measured.get(pattern(text)) ?? [...text].reduce((width,char)=>width+(/\d/.test(char)?digitWidth:context?.measureText(char).width ?? 8.2),0);
    if(context) context.font=`400 ${Number(font.getPropertyValue('--font-ui-size')) || 13.5}px ${font.getPropertyValue('--fs')}`;
    const dateWidth=Math.ceil((context?.measureText('8888-88').width ?? 58) + 10);
    if(context) context.font=`600 ${Number(font.getPropertyValue('--font-ui-size')) || 13.5}px ${font.getPropertyValue('--fs')}`;
    const amountWidth = (key: AutoKey|DerivedKey|ManualKey, editable = false) => {
      const values = (query.data?.rows ?? []).map(row => value(key,{data:row}));
      values.push(query.data?.totals[key as TotalKey] ?? null);
      const texts = values.map(amount => amount == null ? '—' : key.endsWith('rate') ? `${(Number(amount)*100).toFixed(1)}%` : money(String(amount)));
      const edge=['hw_cum','rent_cum','mat_cum','oil','output_rate'].includes(key)?5:4;
      const width = Math.ceil(Math.max(key.endsWith('rate') ? 20 : editable ? 38 : 0, ...texts.map(text => textWidth(text) + (editable ? 8 : edge))));
      return {...contentWidth(width,Math.max(width + 48,editable ? 160 : 0),scale,1),context:{widthFlex:1,editingWidth:editable ? Math.max(width,160)*scale : undefined}};
    };
    const number=(key:AutoKey|DerivedKey,label:string,tip?:string):ColDef<BigRow> => ({colId:key,headerName:label,headerTooltip:tip ?? label,headerClass:key.endsWith('rate')?'big-rate-header':'',cellClass:'big-money',wrapText:true,autoHeight:true,valueGetter:p=>value(key,p),valueFormatter:p=>p.value==null?(p.node?.rowPinned?'':'—'):key.endsWith('rate') ? `${(Number(p.value)*100).toFixed(1)}%` : money(String(p.value)),...amountWidth(key)});
    const manual=(key:ManualKey):ColDef<BigRow> => ({colId:key,headerName:labels[key],headerTooltip:key==='open_ym'?'开工时间 · YYYY-MM':labels[key],cellClass:key==='note'?'big-manual-cell':'big-manual-cell big-money',wrapText:true,autoHeight:true,valueGetter:p=>value(key,p),cellRendererSelector:p=>p.node.rowPinned?undefined:{component:ManualInput},valueFormatter:p=>p.value==null?'':key==='open_ym'||key==='note'?String(p.value):money(String(p.value)),...(key==='note' ? contentWidth(40,240,scale,1) : key==='open_ym' ? contentWidth(dateWidth,112,scale) : amountWidth(key,true))});
    const boundary = (column: ColDef<BigRow>): ColDef<BigRow> => ({...column,headerClass:`${column.headerClass ?? ''} big-group-start`,cellClass:`${column.cellClass ?? ''} big-group-start`});
    return [
      {headerName:'项目',marryChildren:true,children:[
        {field:'seq',headerName:'序号',pinned:'left',valueGetter:p=>p.node?.rowPinned?'':p.data?.seq,...fixedWidth(Math.max(18,Math.ceil(textWidth(String(query.data?.rows.length ?? 0)) + 4)),scale)},
        {field:'display',headerName:'项目名称',pinned:'left',wrapText:true,autoHeight:true,...contentWidth(46,180,scale,1)},
        {...manual('open_ym'),pinned:'left'},
      ]},
      {headerName:'辅材使用（不含税）',headerClass:'big-group-start',marryChildren:true,children:[boundary(number('hw_cum','焊材累计','提取合计：历史值＋所选年12个月，原单入库金额')),number('hw_mon','焊材当月'),number('qt_cum','三气累计','气体提取合计：历史值＋所选年12个月，原单入库金额'),number('qt_mon','三气当月')]},
      {headerName:'机械使用与测算',headerClass:'big-group-start',marryChildren:true,children:[boundary(number('rent_cum','外租机械开工累计','有效零租含税＋包月含税，开工累计')),number('rent_mon','外租机械当月'),number('lease_cum','设备租赁开工累计','有效内租设备，开工累计'),number('lease_mon','设备租赁当月'),number('total_cum','合计','外租机械开工累计＋设备租赁开工累计'),manual('mech_est'),number('use_rate','使用率','合计÷机械费测算；零分母留空')]},
      {headerName:'产值',headerClass:'big-group-start',marryChildren:true,children:[boundary(number('output_rate','产值完成率','产值累计÷合同（预估）价；零分母留空')),manual('contract'),manual('output_cum')]},
      boundary(number('mat_cum','主材累计（含税）','本项目纳入集采台账的合同结算合计')),boundary(manual('oil')),boundary(manual('note')),
    ];
  },[scale,query.data,fontsReady,rendered]);
  const total=useMemo(() => query.data?.rows.length ? [{warehouse:'__total',display:'合计',totals:query.data.totals} as unknown as BigRow] : [],[query.data]);
  function focus(warehouse:string,key:ManualKey) {
    api.current?.ensureColumnVisible(key);
    requestAnimationFrame(() => root.current?.querySelector<HTMLInputElement>(`[row-id="${CSS.escape(warehouse)}"] [col-id="${key}"] input`)?.focus());
  }
  return <>
    <div className="big-toolbar"><div><Button disabled={controlsDisabled || !!projectsError || !query.data} onClick={()=>setPicking(true)}>选择项目与排序…</Button>
      <Select aria-label="定位大表项目" placeholder="定位项目" value={locate} showSearch={{optionFilterProp:'label'}} options={query.data?.rows.map(r=>({value:r.warehouse,label:r.display})) ?? []} onChange={warehouse=>{setLocate(warehouse);if(!warehouse)return;api.current?.ensureNodeVisible(n=>n.data?.warehouse===warehouse,'middle');requestAnimationFrame(()=>root.current?.querySelector<HTMLElement>(`[row-id="${CSS.escape(warehouse)}"] [col-id="display"]`)?.scrollIntoView({block:'center'}));}} disabled={blocked || !query.data} />
      <span className="big-count">{query.data ? `${query.data.rows.length} 个项目` : ''}</span></div>
      <SettlementExport scope={`${ym} 月度会大表`} url={`/api/m07/big/export?${new URLSearchParams({period:ym})}`} paused={!active || blocked} disabled={controlsDisabled || !query.data?.rows.length}>
        <p>{ym} · {query.data?.rows.length} 个项目 · 原模板 Excel</p><ol className="big-export-list">{query.data?.rows.map(r=><li key={r.warehouse}>{r.display}</li>)}</ol>
      </SettlementExport>
    </div>
    {(busy || feedback) && <p className="big-feedback" role="status">{busy?'正在保存…':feedback}</p>}
    {(error || query.isError || projectsError) && <p className="notice" role="alert">{error || query.error?.message || projectsError}<Button disabled={busy || blocked} onClick={()=>{
      retryProjects();void reload().then(()=>{setError('');setVerified(true);setFeedback('已重读，未保存输入仍保留。');}).catch(e=>setError(e instanceof Error?e.message:'重读失败。'));
    }}>重读核对</Button></p>}
    {uncertain && <p className="notice" role="alert">核对刚才的保存结果后再继续。<Button disabled={!verified || busy || query.isFetching || query.isError} onClick={()=>{state.current.uncertain=false;setUncertain(false);setError('');setFeedback('已确认，请核对保留输入后再保存。');}}>已核对，继续</Button></p>}
    {Object.entries(drafts).map(([id,d])=><div className="big-draft" key={id}><span>{d.display} · {labels[d.key]}：{d.value || '清空，恢复带入'}{d.error && <span role="alert"> · {d.error}</span>}</span>
      <Button size="small" disabled={disabled || busy} onMouseDown={e=>e.preventDefault()} onClick={()=>save(id,true)}>保存这项</Button>
      <Button size="small" disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>{queue.current=queue.current.filter(k=>k!==id);const next={...state.current.drafts};delete next[id];update(next);}}>取消修改</Button></div>)}
    {query.isPending ? <p role="status">正在读取月度会大表…</p> : query.data && <BigCells.Provider value={{drafts,disabled,save,focus,
      change:(row,key,value)=>{const id=keyOf(row.warehouse,key),old=state.current.drafts[id];const next={...state.current.drafts,[id]:{warehouse:row.warehouse,display:row.display,key,value,original:old?.original??row.manual[key].value??'',error:'',revision:++revision.current}};if(!lock.current && value===next[id]!.original) delete next[id];update(next);},
      cancel:id=>{if(lock.current)return;queue.current=queue.current.filter(k=>k!==id);const next={...state.current.drafts};delete next[id];update(next);}}}>
      {!query.data.mat_available && <p className="notice">主材累计暂不可得，请先核对集采取数。</p>}
      <div className={`big-grid${query.data.rows.length ? '' : ' is-empty'}`} ref={root}><AgGridReact<BigRow> theme={gridTheme} domLayout="autoHeight" rowData={query.data.rows} columnDefs={columns} pinnedBottomRowData={total}
        getRowId={p=>p.data.warehouse} defaultColDef={{resizable:false,sortable:false,suppressMovable:true,wrapHeaderText:true,autoHeaderHeight:true,suppressKeyboardEvent:e=>e.event.target instanceof HTMLInputElement}}
        rowHeight={pageGridGeometry(scale).rowHeight} headerHeight={pageGridGeometry(scale).headerHeight} groupHeaderHeight={pageGridGeometry(scale).groupHeaderHeight} suppressScrollOnNewData suppressColumnVirtualisation
        overlayNoRowsTemplate={`<span>${query.data.candidates.length ? '未选择项目，请使用“选择项目与排序”。' : '当前没有在建非壳项目，请核对项目档案。'}</span>`}
        onGridReady={e=>{api.current=e.api;fitGridColumns(e.api,root.current,true);}} onFirstDataRendered={e=>{setRendered(n=>n+1);fitGridColumns(e.api,root.current,true);}} onGridSizeChanged={e=>fitGridColumns(e.api,root.current)} onRowDataUpdated={e=>{setRendered(n=>n+1);fitGridColumns(e.api,root.current,true);}} /></div>
    </BigCells.Provider>}
    {picking && query.data && <ProjectOrder data={query.data} projects={projects} busy={busy} disabled={controlsDisabled} paused={!active || blocked} save={selection} close={()=>setPicking(false)} />}
  </>;
}

function ProjectOrder({data,projects,busy,disabled,paused,save,close}:{data:BigData;projects:Project[];busy:boolean;disabled:boolean;paused:boolean;save:(selected:string[])=>Promise<boolean>;close:()=>void}) {
  const available=projects.filter(p=>data.candidates.some(c=>c.warehouse===p.warehouse_name));
  const [selected,setSelected]=useState(()=>[...data.selected]);
  const dirty=selected.join('\0')!==data.selected.join('\0');
  const closing=useDialogClose({busy,dirty,close,active:!paused});
  function move(index:number,offset:number) {const next=[...selected];[next[index],next[index+offset]]=[next[index+offset]!,next[index]!];setSelected(next);}
  const missing=data.candidates.some(c=>!available.some(p=>p.warehouse_name===c.warehouse));
  return <BusinessModal open={!paused} requestClose={closing.requestClose} titleId="big-order-title" className="big-order-dialog"><DialogContents title="选择项目与排序" titleId="big-order-title" closing={closing}>
    <ProjectPicker projects={available} selected={selected.flatMap(wh=>available.filter(p=>p.warehouse_name===wh).map(p=>p.id))} pick={ids=>setSelected(ids.flatMap(id=>{const p=available.find(p=>p.id===id);return p?.warehouse_name?[p.warehouse_name]:[];}))} multiple label="大表项目" disabled={busy || disabled || missing} emptyLabel="未选择项目" />
    <p className="big-order-summary">{selected.length} 个项目 · 页面与导出同序</p>
    {missing && <p className="notice" role="alert">项目档案已变化，请关闭后重读再选。</p>}
    <div className="big-order-table"><BoundedTable columns={[{min:4,max:5},{min:10,max:30,flex:1},{min:12,max:14}]}><thead><tr><th>顺序</th><th>项目名称</th><th>调整顺序</th></tr></thead><tbody>{selected.map((wh,i)=><tr key={wh}><td>{i+1}</td><td>{data.candidates.find(c=>c.warehouse===wh)?.display}</td><td><Button size="small" aria-label={`上移${data.candidates.find(c=>c.warehouse===wh)?.display}`} disabled={busy || disabled || i===0} onClick={()=>move(i,-1)}>上移</Button> <Button size="small" aria-label={`下移${data.candidates.find(c=>c.warehouse===wh)?.display}`} disabled={busy || disabled || i===selected.length-1} onClick={()=>move(i,1)}>下移</Button></td></tr>)}</tbody></BoundedTable></div>
    {!selected.length && <p>保存后大表为空；以后可重新选择项目。</p>}
    <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" loading={busy} disabled={disabled || missing || !dirty} onClick={()=>void save([...selected]).then(ok=>{if(ok)close();})}>保存项目与顺序</Button></div>
  </DialogContents></BusinessModal>;
}
