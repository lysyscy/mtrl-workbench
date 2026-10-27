import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Popconfirm from 'antd/es/popconfirm';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { Identity } from './api';
import { cents, decimal, readProjects, requestJson, uncertainWrite } from './api';
import { contentWidth, gridTheme, pageGridGeometry, numberColumnWidth } from './grid';
import { ProjectPicker, reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { useHistoryGuard } from './history';
import { money } from './notices-api';
import { feeWrite, getFees, getFeeYear } from './fees-api';
import type { FeeField, FeeYearRecord, FeeYearRow } from './fees-api';
import { useRetainedGridColumns, useTextGridLayout } from './grid-layout';
import { initialLayoutColumns, rendererLayoutColumns } from './grid-render-layout';
const annualRowId = (row: AnnualRow) => encodeURIComponent(row.item);

type RecordRow = FeeYearRecord;
interface AnnualRow extends FeeYearRow { records: RecordRow[]; automatic: boolean }
interface Draft { row?: RecordRow | undefined; item: string; ym: string; field: FeeField; value: string; error: string }
const recordKey = (row: RecordRow, field: FeeField) => `${row.id}:${field}`;
const blankKey = (item: string, ym: string) => JSON.stringify([item,ym]);
interface Cells {
  expanded: ReadonlySet<string>; toggle: (item: string, open: boolean) => void;
  drafts: Record<string,Draft>; disabled: boolean; structuralDisabled: boolean; remove: (row:RecordRow) => void;
  change: (key: string, draft: Draft) => void; save: (key: string, retry?: boolean) => void;
}
const FeeCells = createContext<Cells | null>(null);
function FeeEditor({ row, item, ym, field }: { row?: RecordRow | undefined; item: string; ym: string; field: FeeField }) {
  const cells = useContext(FeeCells)!;
  const key = row ? recordKey(row,field) : blankKey(item,ym);
  const draft = cells.drafts[key];
  return <Input data-fee-key={key} aria-label={`${ym} ${item || '未命名'}${field === 'item' ? '项名' : '金额'}${row ? ` #${row.id}` : ''}`}
    value={draft?.value ?? (row ? row[field] : '')} disabled={cells.disabled} status={draft?.error ? 'error' : ''}
    title={draft?.error || (draft ? '未保存' : '')} className={field === 'amount' ? 'fee-money-input' : ''}
    onChange={e => cells.change(key,{...draft,row:draft?.row ?? row,item,ym,field,value:e.target.value,error:''})}
    onBlur={() => cells.save(key)} onKeyDown={e => { e.stopPropagation(); if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); cells.save(key,true); } }} />;
}
function NameCell({ data, node }: ICellRendererParams<AnnualRow>) {
  const cells = useContext(FeeCells)!;
  if (!data) return null;
  if (node.rowPinned || !data.manual || !data.records.length) return data.item || '未命名';
  return <details className="fee-record-name-details" open={cells.expanded.has(data.item)} onToggle={e=>cells.toggle(data.item,e.currentTarget.open)}><summary>{data.item || '未命名'}<span>各月项名，{data.records.length} 条</span></summary><div className="fee-record-names">{data.records.map(row => <label key={row.id}><span>{row.ym.slice(5)}月</span><FeeEditor row={row} item={data.item} ym={row.ym} field="item" /><Popconfirm title={`删除 ${row.ym}「${row.item || '未命名'}」 ${money(row.amount)} 元？`} okText="删除" cancelText="取消" disabled={cells.structuralDisabled} onConfirm={() => cells.remove(row)}><Button size="small" danger disabled={cells.structuralDisabled} aria-label={`${row.ym} ${row.item || '未命名'}删除 #${row.id}`}>删除</Button></Popconfirm></label>)}</div></details>;
}
function AmountCell({ data, node, colDef }: ICellRendererParams<AnnualRow>) {
  if (!data) return null;
  const index = Number(colDef?.colId?.slice(6)) - 1;
  const value = data.months[index];
  if (node.rowPinned || !data.manual) return value === null ? '' : money(value!);
  const ym = `${colDef?.headerTooltip}-${String(index+1).padStart(2,'0')}`;
  const records = data.records.filter(row => row.ym === ym);
  const automatic = data.automatic && value !== null && value !== undefined ? decimal(cents(value) - records.reduce((sum,row) => sum + cents(row.amount),0n)) : null;
  return <div className="fee-record-amounts">{data.automatic && <span className="fee-auto-amount">自动 {automatic === null ? '未读取' : money(automatic)}</span>}
    {data.automatic && <span className="muted">手填</span>}{records.length ? records.map(row => <FeeEditor key={row.id} row={row} item={data.item} ym={ym} field="amount" />)
    : <FeeEditor item={data.item} ym={ym} field="amount" />}{(records.length > 1 || data.automatic && records.length > 0) && <span className="muted">合计 {money(value!)}{records.length > 1 ? `，${records.length} 条手填` : ''}</span>}</div>;
}

export function FeesPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const [year,setYear] = useState(() => reportMonth().slice(0,4)), [project,setProject] = useState('');
  const [addMonth,setAddMonth] = useState(reportMonth), [drafts,setDrafts] = useState<Record<string,Draft>>({});
  const [busy,setBusy] = useState(false), [uncertain,setUncertain] = useState(false), [verified,setVerified] = useState(false);
  const [error,setError] = useState(''), [feedback,setFeedback] = useState('');
  const [expanded,setExpanded] = useState<ReadonlySet<string>>(() => new Set());
  const toggle = (item: string, open: boolean) => setExpanded(previous => { if (previous.has(item) === open) return previous; const next = new Set(previous); if (open) next.add(item); else next.delete(item); return next; });
  const client = useQueryClient(), root = useRef<HTMLDivElement>(null), alive = useRef(true), lock = useRef(false), queue = useRef<string[]>([]);
  const abort = useRef(new AbortController());
  const pendingCreate = useRef<{key:string;ym:string;ids:number[]} | null>(null);
  const queryKey = ['fees-year-inline',year,project];
  const projects = useQuery({queryKey:['projects','all'],enabled:active && !blocked,queryFn:async ({signal}) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  const query = useQuery({queryKey,enabled:active && !blocked,queryFn:({signal}) => getFeeYear(year,project,signal)});
  const state = useRef({drafts,active,blocked,uncertain}); state.current = {drafts,active,blocked,uncertain};
  function update(next: Record<string,Draft>) { state.current.drafts = next; setDrafts(next); }
  useEffect(() => { alive.current = true; abort.current = new AbortController(); return () => { alive.current = false; abort.current.abort(); queue.current = []; }; },[]);
  useEffect(() => { if (!project && query.data?.project) setProject(query.data.project); },[project,query.data]);
  useEffect(() => { setAddMonth(`${year}-${reportMonth().slice(5)}`); },[year]);
  useEffect(() => { if (!active || blocked) queue.current = []; },[active,blocked]);
  const dirty = Object.keys(drafts).length > 0;
  useHistoryGuard(`fees:${year}:${project}`,() => lock.current ? '费用正在保存，请稍候。' : state.current.uncertain ? '费用保存结果待核实，请先核对。' : Object.keys(state.current.drafts).length ? '费用有未保存输入，请先处理。' : '');
  const ready = query.data?.year === year && query.data.project === project;
  const disabled = blocked || !active || !me || uncertain || !ready || !query.data?.can_edit || query.isError;
  const paused = blocked || busy || dirty || uncertain;
  async function reload() {
    const focused = document.activeElement instanceof HTMLInputElement && root.current?.contains(document.activeElement) ? {key:document.activeElement.dataset.feeKey,start:document.activeElement.selectionStart,end:document.activeElement.selectionEnd} : null;
    await client.cancelQueries({queryKey,exact:true});
    const data = await client.fetchQuery({queryKey,staleTime:0,queryFn:({signal}) => getFeeYear(year,project,signal)});
    await client.invalidateQueries({predicate:q => JSON.stringify(q.queryKey) !== JSON.stringify(queryKey)});
    if (focused && alive.current) requestAnimationFrame(() => {
      const input = Array.from(root.current?.querySelectorAll<HTMLInputElement>('input[data-fee-key]') ?? []).find(el => el.dataset.feeKey === focused.key);
      if (input && (!document.activeElement || document.activeElement === document.body || document.activeElement instanceof HTMLElement && document.activeElement.dataset.feeKey === focused.key)) { input.focus({preventScroll:true}); input.setSelectionRange(focused.start,focused.end); }
    });
    return data;
  }
  function change(key: string, draft: Draft) {
    const next = {...state.current.drafts,[key]:draft};
    if (draft.value === (draft.row ? draft.row[draft.field] : '') && !lock.current) delete next[key];
    update(next);
  }
  async function drain() {
    if (lock.current || !state.current.active || state.current.blocked || state.current.uncertain || !me) return;
    let key = queue.current.shift(); if (!key) return;
    const draft = state.current.drafts[key]; if (!draft) { void drain(); return; }
    lock.current = true; setBusy(true); setError(''); setFeedback(''); let written = false;
    try {
      const monthly = await getFees(draft.ym,project,abort.current.signal);
      if (!draft.row) {
        if (!draft.value.trim()) { const next={...state.current.drafts};delete next[key];update(next);return; }
        pendingCreate.current = {key,ym:draft.ym,ids:monthly.manuals.map(r => r.id)};
        const id = await feeWrite('add',{ym:draft.ym,project,name:draft.item,raw:draft.value},abort.current.signal); written = true;
        if (!id) throw new Error('新增记录回执不完整，请重读核对。');
        const originalKey=key;key=recordKey({id} as RecordRow,draft.field);
        const next={...state.current.drafts};
        next[key]={...next[originalKey]!,row:{id,index:monthly.manuals.length,item:draft.item,amount:draft.value,ym:draft.ym}};
        delete next[originalKey];update(next);pendingCreate.current=null;
      } else {
        const row=monthly.manuals.find(r => r.id === draft.row!.id);
        if(!row)throw new Error('原记录已不在当前月份，请取消修改后核对。');
        await feeWrite(draft.field === 'item' ? 'name' : 'amount',{ym:draft.ym,project,index:row.index,value:draft.value},abort.current.signal);written=true;
      }
      if (!alive.current) return;
      const next = {...state.current.drafts}; if (next[key]?.value === draft.value) delete next[key]; update(next);
      const data = await reload(); if (!alive.current) return;
      const remaining = {...state.current.drafts};
      for (const [k,d] of Object.entries(remaining)) { const saved = data.records.find(r => r.id === d.row?.id); if (saved) remaining[k] = {...d,row:saved}; }
      update(remaining);setFeedback(`${draft.ym}，${project}，已保存，年度合计 ${money(data.total)}`);
    } catch (failure) {
      if (!alive.current) return;
      const message = failure instanceof Error ? failure.message : '保存失败，请重试。';
      if (written || uncertainWrite(failure)) { state.current.uncertain = true;setUncertain(true);setVerified(false);queue.current=[];setError(`保存结果待核实。${message}请重读核对，勿重复提交。`); }
      else { pendingCreate.current=null;const next={...state.current.drafts};const currentDraft=next[key];if(currentDraft)next[key]={...currentDraft,error:message};update(next);setError(message); }
    } finally { lock.current=false;if(alive.current){setBusy(false);void drain();} }
  }
  function save(key: string, retry=false) {
    const draft=state.current.drafts[key];if(!draft || draft.error && !retry || disabled)return;
    if(!queue.current.includes(key))queue.current.push(key);void drain();
  }
  async function add() {
    if(disabled || lock.current || dirty || query.isFetching)return;
    lock.current=true;setBusy(true);setError('');let written=false;
    const names=new Set(query.data?.rows.map(row=>row.item));
    let name='新项';for(let index=2;names.has(name);index++)name=`新项${index}`;
    try {const id=await feeWrite('add',{ym:addMonth,project,name},abort.current.signal);written=true;await reload();setFeedback(`${addMonth}，已增加手填项`);requestAnimationFrame(()=>{const input=root.current?.querySelector<HTMLInputElement>(`input[data-fee-key="${id}:item"]`);const details=input?.closest('details');if(details)details.open=true;input?.focus();});}
    catch(failure){if(alive.current){const unknown=written || uncertainWrite(failure);state.current.uncertain=unknown;setUncertain(unknown);setVerified(false);setError(`${unknown ? '新增结果待核实，请重读核对，勿重复增加。' : ''}${failure instanceof Error ? failure.message : '新增失败。'}`);}}
    finally{lock.current=false;if(alive.current)setBusy(false);}
  }
  async function remove(record:RecordRow) {
    if(disabled || lock.current || dirty)return;
    lock.current=true;setBusy(true);setError('');let written=false;
    try {const monthly=await getFees(record.ym,project,abort.current.signal);const row=monthly.manuals.find(r=>r.id===record.id);if(!row)throw new Error('原记录已不在当前月份，请重读核对。');await feeWrite('delete',{ym:record.ym,project,index:row.index},abort.current.signal);written=true;const data=await reload();setFeedback(`${record.ym}，已删除「${record.item || '未命名'}」，年度合计 ${money(data.total)}`);}
    catch(failure){if(alive.current){const unknown=written || uncertainWrite(failure);state.current.uncertain=unknown;setUncertain(unknown);setVerified(false);setError(`${unknown?'删除结果待核实，请重读核对。':''}${failure instanceof Error?failure.message:'删除失败。'}`);}}
    finally{lock.current=false;if(alive.current)setBusy(false);}
  }
  async function reread() {
    if(lock.current || blocked || !active)return;
    try {
      const data=await reload();
      const pending=pendingCreate.current;
      if(pending){const added=data.records.filter(r=>r.ym===pending.ym && !pending.ids.includes(r.id));if(added.length===1){const draft=state.current.drafts[pending.key];if(draft){const row=added[0]!;const next={...state.current.drafts};delete next[pending.key];next[recordKey(row,draft.field)]={...draft,row};update(next);}pendingCreate.current=null;}else if(added.length>1)throw new Error('该月有多条新增记录，请先取消保留输入，再逐条核对。');}
      setVerified(true);setError('');setFeedback('已重读，请核对刚才的操作结果。');
    }catch(failure){setError(failure instanceof Error ? failure.message : '重读失败。');}
  }
  const rows = useMemo<AnnualRow[]>(() => query.data?.rows.map(row=>({...row,automatic:row.item===query.data!.auto_name,records:query.data!.records.filter(record=>record.item===row.item)})) ?? [],[query.data]);
  const scale=Number(me?.ui_scale_css ?? 1);
  const columns=useMemo<ColDef<AnnualRow>[]>(()=>[
    {field:'item',headerName:'费用项名称',pinned:'left',autoHeight:true,wrapText:true,...contentWidth(160,300,scale,1),cellRenderer:NameCell},
    {field:'prior',headerName:'往年',cellClass:'money',valueFormatter:p=>p.value===null?'':money(p.value),...numberColumnWidth([query.data?.prior,...rows.map(row=>row.prior)].map(value=>value==null?'':money(value)),scale)},
    ...Array.from({length:12},(_,i):ColDef<AnnualRow>=>({colId:`month-${i+1}`,headerName:`${i+1}月`,headerTooltip:year,cellClass:'money',autoHeight:true,valueGetter:p=>p.data?.months[i],cellRenderer:AmountCell,...numberColumnWidth([query.data?.months[i],...rows.map(row=>row.months[i]),...rows.flatMap(row=>row.records.filter(record=>record.ym===`${year}-${String(i+1).padStart(2,'0')}`).map(record=>record.amount))].map(value=>value==null?'':money(value)),scale,true)})),
    {field:'total',headerName:'累计',headerTooltip:'往年 + 所选年1至12月',cellClass:'money',valueFormatter:p=>money(p.value),...numberColumnWidth([query.data?.total,...rows.map(row=>row.total)].map(value=>value==null?'':money(value)),scale)},
  ],[year,scale,rows,query.data]);
  const totals=useMemo<AnnualRow[]>(()=>query.data?[{item:'合计',manual:false,prior:query.data.prior,months:query.data.months,total:query.data.total,periods:[],records:[],automatic:false}]:[],[query.data]);
  const retained = useRetainedGridColumns(columns,root);
  const gridColumns = useMemo(()=>initialLayoutColumns(retained),[retained]);
  const prepared = useMemo(()=>rendererLayoutColumns(gridColumns,undefined,(row,id,pinned)=>JSON.stringify([row,id,pinned,expanded.has(row.item)])),[gridColumns,expanded]);
  const layout = useTextGridLayout({root,active:active && ready,rows,totals,columns:prepared,rowId:annualRowId,minimum:pageGridGeometry(scale).rowHeight,headerMinimum:pageGridGeometry(scale).headerHeight,scope:year+':'+project,identity:year+':'+project});
  return <section className="fees-page" aria-label="特殊费用">
    <div data-page-chrome className="fee-filters"><label>年份<TimePicker label="费用年份" modes={['年']} value={year} onChange={setYear} disabled={paused} /></label>
      <label>项目<ProjectPicker projects={(projects.data ?? []).filter(p=>p.warehouse_name && p.project_type!=='shell')} selected={(projects.data ?? []).filter(p=>p.warehouse_name===project).map(p=>p.id)} pick={ids=>{const next=projects.data?.find(p=>p.id===ids[0])?.warehouse_name;if(next)setProject(next);}} label="费用项目" disabled={paused || projects.isPending} /></label></div>
    <div data-page-chrome className="fee-toolbar"><div><label>新增核算月<TimePicker label="新增费用核算月" modes={['月']} value={addMonth} onChange={next=>{if(next.startsWith(year))setAddMonth(next);}} disabled={paused} /></label><Button disabled={disabled || busy || dirty || query.isFetching} onClick={()=>void add()}>增加手填项</Button></div><span className="muted">随逐月欠款台账导出，特殊费用月报表</span></div>
    {(busy || feedback) && <p role="status" className="fee-feedback">{busy?'正在保存费用…':feedback}</p>}
    {(error || projects.isError || query.isError) && <p role="alert" className="notice">{error || projects.error?.message || query.error?.message}<Button disabled={busy || blocked} onClick={()=>void reread()}>重读核对</Button></p>}
    {uncertain && <p className="notice" role="alert">核对结果后再继续。<Button disabled={!verified || busy} onClick={()=>{pendingCreate.current=null;state.current.uncertain=false;setUncertain(false);setError('');setFeedback('已确认，请核对保留输入后再保存。');}}>已核对，保留输入继续</Button></p>}
    {Object.entries(drafts).map(([key,d])=><p key={key} className="fee-draft-feedback">{d.ym}，{d.item || '未命名'}，{d.field==='item'?'项名':'金额'}：{d.error || '未保存'} <Button size="small" disabled={busy || blocked || uncertain} onMouseDown={e=>e.preventDefault()} onClick={()=>save(key,true)}>保存</Button><Button size="small" disabled={busy || blocked} onMouseDown={e=>e.preventDefault()} onClick={()=>{const next={...state.current.drafts};delete next[key];update(next);}}>取消这项修改</Button></p>)}
    <p className="fee-record-note muted">同月同名的多条记录分别填写，月合计自动相加；项名旁标明所属月份。</p>
    {query.isPending?<p role="status">正在读取费用…</p>:ready && <FeeCells.Provider value={{expanded,toggle,drafts,disabled,structuralDisabled:disabled || busy || dirty || query.isFetching,remove,change,save}}><div ref={root} className="fees-grid fees-annual-grid" aria-label="特殊费用年度表" data-layout-state={layout.state} data-layout-error={layout.error || undefined} inert={layout.concealed || layout.state === 'preparing' || layout.state === 'error'} style={{visibility:layout.concealed || layout.state === 'preparing' || layout.state === 'error' ? 'hidden' : undefined}}><AgGridReact<AnnualRow> theme={gridTheme} domLayout="autoHeight" columnDefs={gridColumns} getRowId={p=>annualRowId(p.data)}
      defaultColDef={{resizable:true,sortable:false,suppressMovable:true,wrapHeaderText:true,suppressKeyboardEvent:e=>e.event.target instanceof HTMLInputElement}} rowHeight={pageGridGeometry(scale).rowHeight} headerHeight={pageGridGeometry(scale).headerHeight} suppressScrollOnNewData suppressColumnVirtualisation
      animateRows={false} onGridReady={e=>layout.attach(e.api)} /></div>{layout.measurement}{layout.state==='error'&&<p role="alert">{layout.error}<Button onClick={layout.retry}>重试表格加载</Button></p>}</FeeCells.Provider>}
  </section>;
}
