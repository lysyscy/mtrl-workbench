import { DialogPresence } from './workspace-motion';
import Button from 'antd/es/button';
import App from 'antd/es/app';
import Input from 'antd/es/input';
import Checkbox from 'antd/es/checkbox';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ColGroupDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { ApiError, readProjects, record, requestFile, requestJson, uncertainWrite } from './api';
import type { Identity, Project } from './api';
import { pageGridGeometry, fixedWidth, gridTheme, textWidth } from './grid';
import { EllipsisText, completeColumnWidth } from './grid-text';
import { companySummaryRows, internalAmount, mechanicalMoney as money, readDetail, readInternalSave, readWorkbenchPage, readWorkResult, reconcileDetailDraft } from './mechanical-api';
import { DetailsTable, MechanicalDialog, detailKey, mechanicalNumberWidth } from './mechanical-details';
import { useCellSaveQueue } from './use-cell-save';
import { TimePicker } from './time-picker';
import { currentMonth } from './business-time';
import { useHistoryGuard } from './history';
import { MechanicalWork } from './mechanical-work';
import { body } from './notices-api';
import type { Category, CompanySummaryRow, DetailDraft, DetailRow, InternalColumn, WorkbenchPage } from './mechanical-api';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
import { FirstReadRegion, ReadFailure, ReadPlaceholder, ReadStatusLane, readPhase } from './read-region';
import { ProjectExport, ProjectSelectionOrder } from './ledger-controls';
const summaryRowId = (row: SummaryRow) => row.id;
// These cells stay one line; let the existing native row-height path size them.
const summaryMeasurement = {textOnly:Array.from({length:15},(_,index)=>`c${index}`)};
const plateKeywords = (text: string) => [...new Set(text.split('\n').map(word => word.trim()).filter(Boolean))];

interface InternalDraft { kind: 'internal'; warehouse: string; ym: string; column: InternalColumn; value: string; version: number; error: string }
type MechanicalDraft = DetailDraft | InternalDraft;
const isInternalDraft = (draft: MechanicalDraft): draft is InternalDraft => 'kind' in draft;
const internalKey = (warehouse: string, ym: string, column: InternalColumn) => JSON.stringify(['internal',warehouse,ym,column]);
interface InternalEditing { writable: boolean; resetVersion: number; value: (id: string,column: InternalColumn) => string | undefined; change: (id: string,column: InternalColumn,value: string) => void; save: (id: string,column: InternalColumn) => void }
function InternalCell({ id, column, value, label, editing }: { id: string; column: InternalColumn; value: string; label: string; editing: React.RefObject<InternalEditing> }) {
  const {resetVersion}=editing.current;
  const [text,setText]=useState(()=>editing.current.value(id,column)??value);
  useEffect(()=>{setText(editing.current.value(id,column)??value);},[value,id,column,editing,resetVersion]);
  return <Input aria-label={label} inputMode="decimal" className="mechanical-internal-input money" disabled={!editing.current.writable} value={text} onChange={event=>{setText(event.target.value);editing.current.change(id,column,event.target.value);}} onBlur={()=>editing.current.save(id,column)} onKeyDown={event=>{event.stopPropagation();if(event.key==='Enter'&&!event.nativeEvent.isComposing){event.preventDefault();event.currentTarget.blur();}}} />;
}
type SummaryRow = CompanySummaryRow;
const groupLabels = ['零租', '包月', '周材', '内租（租赁公司）', '内租（工程公司）'];
function Summary({ scale, ym, projects, detail, internal, data, warehouses, active }: { active: boolean; scale: number; ym: string; data:WorkbenchPage; warehouses:string[]; internal: InternalEditing; projects: {warehouse:string;id:number}[]; detail: (sheet: number, projectId: string) => void }) {
  const api = useRef<GridApi<SummaryRow> | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const fitHeight = useCallback(() => {
    const grid = api.current, element = root.current;
    if (!grid || grid.isDestroyed() || !element) return;
    const scale = Number(getComputedStyle(element).getPropertyValue('--fscale')) || 1;
    const last = grid.getDisplayedRowAtIndex(grid.getDisplayedRowCount() - 1);
    const horizontal = element.querySelector('.ag-body-horizontal-scroll');
    const natural = (element.querySelector('.ag-header')?.getBoundingClientRect().height ?? 68 * scale)
      + (last ? (last.rowTop ?? 0) + (last.rowHeight ?? 36 * scale) : 36 * scale)
      + (element.querySelector('.ag-grid-pinned-bottom-rows')?.getBoundingClientRect().height ?? grid.getPinnedBottomRow(0)?.rowHeight ?? 0)
      + (horizontal?.getBoundingClientRect().height ?? 0) + 2;
    const height = Math.ceil(Math.min(natural, Math.max(200 * scale, window.innerHeight - element.getBoundingClientRect().top - 16 * scale)));
    if (Math.abs(element.getBoundingClientRect().height - height) > .5) element.style.height = `${height}px`;
  }, []);
  useEffect(() => {
    window.addEventListener('resize', fitHeight); void document.fonts.ready.then(fitHeight);
    return () => { window.removeEventListener('resize', fitHeight); };
  }, [fitHeight]);
  const current=useRef(internal);current.current=internal;
  useEffect(()=>{api.current?.refreshCells({force:true});},[internal.writable,internal.resetVersion]);
  const rows = useMemo(() => companySummaryRows(data, ym, projects), [data, ym, projects]);
  const openDetail = useRef(detail); openDetail.current = detail;
  const renderInternal = useCallback((params: ICellRendererParams<SummaryRow,string>) => {
    const index = params.colDef?.field === 'c12' ? 3 : 4;
    return params.node.rowPinned ? money(params.value) : <InternalCell id={params.data!.id} column={index === 3 ? 'mech_1' : 'mech_0'} value={params.value ?? ''} label={`${params.data?.c1} ${groupLabels[index]}`} editing={current} />;
  }, []);
  const renderDetail = useCallback((params: ICellRendererParams<SummaryRow,string>) => {
    const index = params.colDef?.field === 'c9' ? 0 : 1;
    return params.node.rowPinned ? money(params.value) : <Button className="mechanical-amount-button" aria-label={`${params.data?.c1} ${groupLabels[index]}明细`} onClick={() => openDetail.current(index + 1, params.data?.id ?? '')}>{money(params.value)}</Button>;
  }, []);
  const columns = useMemo<(ColDef<SummaryRow> | ColGroupDef<SummaryRow>)[]>(() => [
    { field: 'c0', headerName: '序号', pinned: 'left', ...fixedWidth(48, scale) },
    { field: 'c1', headerName: '项目名称', pinned: 'left', ...textWidth(120, 200, scale), wrapText: false, autoHeight: false, cellRenderer: (p: ICellRendererParams<SummaryRow,string>) => <EllipsisText text={p.value ?? ''} /> },
    { headerName: '开工日期', children: [{ field: 'c2', headerName: '年', ...completeColumnWidth(rows.map(row=>row.c2), '年', scale) }, { field: 'c3', headerName: '月', ...completeColumnWidth(rows.map(row=>row.c3), '月', scale), cellClass: 'mechanical-group-end', headerClass: 'mechanical-group-end' }] },
    ...['开工累计费用（元）', '本月产生费用（元）'].map((name, group) => ({ headerName: name, headerClass: 'mechanical-group-end', children: groupLabels.map((label, index): ColDef<SummaryRow> => ({
      field: `c${4 + group * 5 + index}`, headerName: label, ...mechanicalNumberWidth(rows.map(row => money(row[`c${4 + group * 5 + index}`])), scale, group === 1 && index !== 2,1), minWidth: Math.max(mechanicalNumberWidth(rows.map(row => money(row[`c${4 + group * 5 + index}`])), scale, group === 1 && index !== 2).minWidth, completeColumnWidth([],label,scale).minWidth), wrapText: false, autoHeight: false, valueFormatter:p=>money(p.value), cellClass: index === 4 ? 'money mechanical-group-end' : 'money', headerClass: index === 4 ? 'mechanical-group-end' : '',
      ...(group===1&&index>2?{cellRenderer:renderInternal}:{}),
      ...(group === 1 && index < 2 ? { cellRenderer: renderDetail } : {}),
    })) })),
    { field: 'c14', headerName: '备注', ...textWidth(72, 144, scale), wrapText: false, autoHeight: false, cellRenderer: (p: ICellRendererParams<SummaryRow,string>) => <EllipsisText text={p.value ?? ''} /> },
  ], [scale, rows, renderInternal, renderDetail]);
  const bodyRows = useMemo(() => rows.slice(0, -1), [rows]), total = useMemo(() => rows.slice(-1), [rows]);
  const scope = `${ym}:${warehouses.join('\0')}`;
  const presentation = useGridPresentation({table: 'mechanical-summary', root, active, rows: bodyRows, totals: total, columns, measurement:summaryMeasurement, rowId: summaryRowId, scale, scope, identity: scope});
  useLayoutEffect(() => { if (presentation.state === 'ready') fitHeight(); }, [presentation.state, fitHeight]);
  return <PreparedGrid presentation={presentation} className="mechanical-grid grid-single-line" role="region" aria-label="公司汇总" grid={{theme:gridTheme,defaultColDef:{sortable:false,resizable:true,suppressMovable:true,wrapText:false,autoHeight:false,wrapHeaderText:false,autoHeaderHeight:false},getRowId:params=>params.data.id,groupHeaderHeight:pageGridGeometry(scale).groupHeaderHeight,suppressColumnVirtualisation:true,enableCellTextSelection:true,ensureDomOrder:true,onGridSizeChanged:fitHeight,onModelUpdated:fitHeight,onColumnResized:fitHeight,onGridReady:event=>{
        api.current = event.api;
        // Header wrapping and scrollbar visibility can settle after the first data render.
        const observer = new ResizeObserver(fitHeight);
        for (const selector of ['.ag-header','.ag-body-horizontal-scroll','.ag-grid-pinned-bottom-rows']) {
          const element = root.current?.querySelector(selector); if (element) observer.observe(element);
        }
        const visibility = new MutationObserver(fitHeight), scrollbar = root.current?.querySelector('.ag-body-horizontal-scroll');
        if (scrollbar) visibility.observe(scrollbar, { attributes: true, attributeFilter: ['class','style'] });
        event.api.addEventListener('gridPreDestroyed', () => { observer.disconnect(); visibility.disconnect(); });
      }}} />;
}
function MechanicalExport({ owner, month, projects, defaults, unavailable, paused, message }: {
  owner: string; month: string; projects: Project[]; defaults: number[]; unavailable: string; paused: boolean; message: (text: string) => void;
}) {
  const request = useRef<AbortController | null>(null), lock = useRef(false);
  const current = useRef({ owner, month, unavailable, paused }); current.current = { owner, month, unavailable, paused };
  useEffect(() => {
    request.current?.abort(); request.current = null;
    return () => { request.current?.abort(); };
  }, [owner, month, unavailable, paused]);
  const valid = () => current.current.owner === owner && current.current.month === month && !current.current.unavailable && !current.current.paused && !request.current?.signal.aborted;
  async function run(action: () => Promise<void>): Promise<string | null> {
    if (current.current.owner !== owner || current.current.month !== month || current.current.unavailable || current.current.paused || lock.current) return null;
    lock.current = true; request.current = new AbortController();
    try { await action(); return null; }
    catch (error) { return valid() ? error instanceof Error ? error.message : '导出失败，请重试。' : null; }
    finally { lock.current = false; }
  }
  return <ProjectExport kind="mechanical" owner={owner} projects={projects} project={0} defaultProjects={defaults}
    unavailable={unavailable} paused={paused} run={run} valid={valid} signal={undefined} message={message}
    title="导出台账" description={`${month}，生成含公司汇总、零租明细、包月明细、年度汇总的一个 Excel 工作簿。`}
    summary={count => `已选 ${count} 个项目，按以下顺序导出。`} success="机械费台账已导出。"
    exportFile={chosen => requestFile(`/api/m06/workbench/export?${new URLSearchParams({ ym: month, projects: JSON.stringify(chosen.map(item => item.warehouse_name!)) })}`, request.current!.signal)} />;
}
export function MechanicalPage({ me, blocked, exportGuard, active, onHistoryGuard }: { me: Identity | null; blocked: boolean; exportGuard: string; active: boolean; onHistoryGuard: (reason: string) => void }) {
  const {message: toast} = App.useApp();
  const client = useQueryClient();
  const [month, setMonth] = useState(()=>{const [year,month]=currentMonth().split('-');return new Date(Date.UTC(Number(year),Number(month)-2,15)).toISOString().slice(0,7);}); const [ids, setIds] = useState<number[] | null>(null);
  const [pickerIds,setPickerIds]=useState<number[]>([]); const [pickerOrder,setPickerOrder]=useState<number[]>([]);
  const [pickerBaseline,setPickerBaseline]=useState<number[]>([]),[keywordsBaseline,setKeywordsBaseline]=useState('');
  const [message, setMessage] = useState('');
  const projects = useQuery({ queryKey: ['projects', 'all'], enabled: !blocked, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const state = useQuery({ queryKey: ['mechanical-state',month], enabled: !blocked, queryFn: async ({ signal }) => readWorkbenchPage(await requestJson('/api/m06/workbench/page?ym='+encodeURIComponent(month), { signal }), month) });
  const candidates = useMemo(() => projects.data?.filter(project => state.data?.warehouses.includes(project.warehouse_name ?? '')) ?? [], [projects.data, state.data]);
  const selected = useMemo(() => ids ?? (state.data?.shown.flatMap(warehouse => candidates.filter(project => project.warehouse_name === warehouse).map(project => project.id)) ?? []), [ids, state.data, candidates]);
  const warehouses = useMemo(() => selected.flatMap(id => candidates.find(project => project.id === id)?.warehouse_name ?? []), [selected, candidates]);
  const summaryProjects = useMemo(() => selected.flatMap(id => { const warehouse = candidates.find(project => project.id === id)?.warehouse_name; return warehouse ? [{ warehouse, id }] : []; }), [selected, candidates]);
  const ym = month;
  const scopeMismatch = selected.length !== warehouses.length;
  const scopeError = scopeMismatch ? '所选项目范围已变化，请重新选择。' : projects.isError || state.isError ? '项目或月份读取失败，请先重新读取。' : '';
  const scope = JSON.stringify([ym, warehouses]);
  useEffect(() => { setMessage(''); }, [scope, blocked, exportGuard, scopeError]);
  const [tab, setTab] = useState<'summary' | 'zero' | 'monthly' | 'work'>('summary');
  const [temporary, setTemporary] = useState(''); const [problemsOnly, setProblemsOnly] = useState(false);
  const [detailReview, setDetailReview] = useState<{ key: string; showDraft: boolean } | null>(null);
  const [operating,setWriting] = useState(false); const writeLock = useRef(false);
  const savedRevisions=useRef(new Map<string,number>());
  const [needsRead,setNeedsRead] = useState(false);
  const [dialog,setDialog] = useState<'plate' | 'projects' | null>(null); const [keywords,setKeywords] = useState('');
  const [resetVersion,resetInternal]=useState(0);
  const internalSubmitted=useRef<{draft:InternalDraft;signature:string}|null>(null);
  const detailSubmitted = useRef<DetailDraft | null>(null);
  const [verifying, setVerifying] = useState(false);
  const saves=useCellSaveQueue<MechanicalDraft,WorkbenchPage>({
    enabled:Boolean(me)&&active&&!blocked,canWrite:!operating&&!needsRead&&!state.isError&&Boolean(state.data),
    read:readForSave,
    write:async(draft,signal)=>{
      if(isInternalDraft(draft)){
        const effective=client.getQueryData<WorkbenchPage>(['mechanical-state',draft.ym])?.effective.find(item=>item.warehouse===draft.warehouse&&item.ym===draft.ym);
        if(!effective)throw new Error('内租原金额尚未取得，请重新读取后重试。');
        const value=internalAmount(draft.value)!;
        internalSubmitted.current={draft,signature:effective.signature};
        try{
          const response=await requestJson('/api/m06/workbench/internal-save',{method:'POST',signal,...body({warehouse:draft.warehouse,ym:draft.ym,values:{[draft.column]:value},effective_signature:effective.signature})});
          readInternalSave(response,draft.warehouse,draft.ym,draft.column,value);
        }catch(error){if(!uncertainWrite(error))internalSubmitted.current=null;throw error;}
        return;
      }
      let saved;
      try {
        const response=await requestJson('/api/m06/workbench/details-save',{method:'POST',signal,...body({warehouse:draft.warehouse,ym:draft.ym,category:draft.category,revision:draft.revision,rows:draft.rows})});
        try {
          saved=readDetail(response);
          if(!record(response)||response.ok!==true||saved.warehouse!==draft.warehouse||saved.ym!==draft.ym||saved.category!==draft.category||saved.revision!==draft.revision+1)throw new Error();
        } catch { throw new ApiError('明细保存回执不完整，请重读核对。',0,'invalid_receipt'); }
      } catch (error) {
        if (uncertainWrite(error)) detailSubmitted.current = draft;
        throw error;
      }
      draft.revision=saved.revision;savedRevisions.current.set(detailKey(draft.warehouse,draft.ym,draft.category),saved.revision);
      await client.cancelQueries({queryKey:['mechanical-state',saved.ym],exact:true});
      client.setQueryData<WorkbenchPage>(['mechanical-state',saved.ym],old=>old?{...old,details:[...old.details.filter(detail=>detailKey(detail.warehouse,detail.ym,detail.category)!==detailKey(saved.warehouse,saved.ym,saved.category)),saved]}:old);
    },
    acknowledge:(current,submitted)=>{
      if(isInternalDraft(submitted)){
        internalSubmitted.current=null;
        return current.version===submitted.version?undefined:current;
      }
      return !isInternalDraft(current)&&current.version!==submitted.version?{...current,revision:submitted.revision}:undefined;
    },
    validate:draft=>isInternalDraft(draft)&&internalAmount(draft.value)===null?'内租须填写非负金额，最多两位小数。':'',
    saved:()=>'',stopOnRejection:true,recoverInterrupted:true,
    describe:draft=>`${draft.warehouse}，${draft.ym}${isInternalDraft(draft)?draft.column==='mech_0'?'，工程公司内租 ':'，租赁公司内租 ':' '}`,
  },{key:'mechanical-details',label:'机械费'});
  const writing=operating||saves.busy;
  const writable = Boolean(me) && active && !blocked && !operating && !needsRead && !saves.uncertain && Boolean(state.data) && !state.isError;
  const category: Category = tab === 'monthly' ? 'monthly' : 'zero';
  const reviewed = detailReview ? saves.drafts[detailReview.key] : undefined;
  const reviewing = reviewed && !isInternalDraft(reviewed) && reviewed.conflicted && reviewed.ym === ym && reviewed.category === category ? reviewed : undefined;
  const editingWarehouses = reviewing ? [reviewing.warehouse] : temporary ? warehouses.filter(w => w === temporary) : warehouses;
  const label = (warehouse: string) => candidates.find(p => p.warehouse_name === warehouse)?.disp || warehouse;
  const detail = useCallback((index: number, projectId: string) => {
    const warehouse = projects.data?.find(project => String(project.id) === projectId)?.warehouse_name;
    if (warehouse) { setTab(index === 2 ? 'monthly' : 'zero');setTemporary(warehouse);setProblemsOnly(false);setDetailReview(null); }
  },[projects.data]);
  useEffect(() => {setTemporary('');setProblemsOnly(false);setDialog(current=>current==='projects'?'projects':null);},[scope]);
  function edit(warehouse: string, rows: DetailRow[]) {
    if (!writable) return;
    const key=detailKey(warehouse,ym,category);
    const saved=state.data?.details.find(d => detailKey(d.warehouse,d.ym,d.category)===key);
    saves.update(current=>{
      const entry=current[key],previous=entry&&!isInternalDraft(entry)?entry:undefined;
      if (previous?.conflicted) return current;
      return {...current,[key]:{warehouse,ym,category,revision:previous?.revision??Math.max(saved?.revision??0,savedRevisions.current.get(key)??0),rows,version:(previous?.version??0)+1,error:''}};
    });
  }
  async function readForSave(draft?: MechanicalDraft): Promise<WorkbenchPage> {
    const data = await readMonth(draft?.ym ?? month);
    if (!draft || draft !== detailSubmitted.current) return data;
    const key = detailKey(draft.warehouse, draft.ym, draft.category);
    const saved = data.details.find(detail => detailKey(detail.warehouse, detail.ym, detail.category) === key);
    saves.update(drafts => {
      const current = drafts[key];
      if (!current || isInternalDraft(current)) return drafts;
      const next = { ...drafts };
      const recovered = reconcileDetailDraft(current, draft, saved);
      if (recovered) next[key] = recovered;
      else delete next[key];
      return next;
    });
    return data;
  }
  async function readMonth(readMonth:string){
    // Other kept-alive pages read their stale data when next activated.
    await client.invalidateQueries({refetchType:'none'});
    await client.cancelQueries({queryKey:['mechanical-state',readMonth],exact:true});
    const data=await client.fetchQuery({queryKey:['mechanical-state',readMonth],staleTime:0,queryFn:async({signal})=>readWorkbenchPage(await requestJson('/api/m06/workbench/page?ym='+encodeURIComponent(readMonth),{signal}),readMonth)});
    await client.invalidateQueries({queryKey:['history',me?`${me.id}:${me.account}`:'anonymous'],exact:true},{throwOnError:true});
    return data;
  }
  async function refresh() {
    try {await readMonth(month);setNeedsRead(false);if(needsRead){setMessage('');void toast.success('已重新读取');}return true;}
    catch {setNeedsRead(true);setMessage('修改已保存，但重新读取失败。请重新读取后再办理，未保存输入保留。');return false;}
  }
  async function operate(action: () => Promise<void>) {
    if(!writable || writeLock.current || saves.busy)return;writeLock.current=true;setWriting(true);setMessage('');
    try{await action();}catch(error){setMessage(error instanceof Error ? error.message : '修改未完成，输入已保留，请核对后重试。');}
    finally{writeLock.current=false;setWriting(false);}
  }
  async function saveSettings(values: Record<string,unknown>, saved: () => void, message: string) {
    await operate(async()=>{
      const payload={revision:state.data?.settings.revision,...values};
      try {
        const result=await requestJson('/api/m06/workbench/settings',{method:'POST',...body(payload)});
        readWorkResult(result,'settings',payload);
        if(!record(result)||result.revision!==Number(payload.revision)+1||Object.entries(values).some(([key,value])=>JSON.stringify(result[key])!==JSON.stringify(value)))throw new ApiError('设置保存回执与本次修改不符。',0,'invalid_receipt');
      }
      catch(error) {
        if(uncertainWrite(error)){setNeedsRead(true);throw new Error('设置保存结果待核实，请重新读取核对；输入已保留。');}
        throw error;
      }
      saved();setDialog(null);if(await refresh())void toast.success(message);
    });
  }
  async function rereadSettings() {
    if(writing||state.isFetching)return;
    if(!await refresh()){setMessage('设置保存结果仍待核实，重新读取失败；输入已保留。');return;}
    const latest=client.getQueryData<WorkbenchPage>(['mechanical-state',month]);
    // An explicit recovery read may acknowledge an already-saved draft; background reads never reset it.
    if(latest&&dialog==='plate'&&JSON.stringify(plateKeywords(keywords))===JSON.stringify(latest.settings.plate_keywords))setKeywordsBaseline(JSON.stringify(plateKeywords(keywords)));
    if(latest&&dialog==='projects'&&JSON.stringify(pickerOrder.filter(id=>pickerIds.includes(id)).flatMap(id=>candidates.find(p=>p.id===id)?.warehouse_name??[]))===JSON.stringify(latest.shown)){const selected=pickerOrder.filter(id=>pickerIds.includes(id));setPickerBaseline(selected);setIds(selected);setTemporary('');}
    setMessage('已重新读取，请核对设置后继续。');
  }
  const detailGroups = editingWarehouses.map(warehouse => {
    const key = detailKey(warehouse, ym, category);
    const entry = saves.drafts[key];
    const draft = entry && !isInternalDraft(entry) ? entry : undefined;
    return {
      warehouse, name: label(warehouse),
      saved: state.data?.details.find(detail => detailKey(detail.warehouse, detail.ym, detail.category) === key),
      draft: !draft?.conflicted || detailReview?.key === key && detailReview.showDraft ? draft : undefined,
      locked: Boolean(draft?.conflicted),
    };
  });
  const internal:InternalEditing={writable,resetVersion,value:(id,column)=>{
    const warehouse=candidates.find(p=>String(p.id)===id)?.warehouse_name;
    const draft=warehouse?saves.drafts[internalKey(warehouse,ym,column)]:undefined;
    return draft&&isInternalDraft(draft)?draft.value:undefined;
  },change:(id,column,value)=>{
    const warehouse=candidates.find(p=>String(p.id)===id)?.warehouse_name;if(!warehouse||!writable)return;
    const key=internalKey(warehouse,ym,column);
    saves.update(current=>({...current,[key]:{kind:'internal',warehouse,ym,column,value,version:(current[key]?.version??0)+1,error:''}}));
  },save:(id,column)=>{
    const warehouse=candidates.find(p=>String(p.id)===id)?.warehouse_name;if(!warehouse||!writable)return;
    saves.save(internalKey(warehouse,ym,column));
  }};
  function cancelFailedDraft(key:string,draft:MechanicalDraft){
    if(isInternalDraft(draft))resetInternal(version=>version+1);
    if (detailReview?.key === key) setDetailReview(null);
    saves.update(current=>{const next={...current};delete next[key];return next;});
  }
  function reviewDetail(key: string, draft: DetailDraft, showDraft: boolean) {
    setMonth(draft.ym); setTab(draft.category); setTemporary(''); setProblemsOnly(false);
    setDetailReview({ key, showDraft });
  }
  async function rereadCells() {
    setVerifying(true);
    try { await saves.reread(); }
    finally { setVerifying(false); }
  }
  function confirmCellRead(){
    if(!saves.verified||writing||verifying||blocked)return;
    const submitted=internalSubmitted.current;
    saves.confirm();
    detailSubmitted.current = null;
    if(!submitted||internalSubmitted.current!==submitted)return;
    internalSubmitted.current=null;
    saves.update(current=>{
      const next={...current};
      const draft=submitted.draft,key=internalKey(draft.warehouse,draft.ym,draft.column),expected=internalAmount(draft.value);
      const effective=client.getQueryData<WorkbenchPage>(['mechanical-state',draft.ym])?.effective.find(item=>item.warehouse===draft.warehouse&&item.ym===draft.ym);
      if(current[key]?.version===draft.version&&effective&&effective.signature!==submitted.signature&&expected!==null&&internalAmount(effective.values[draft.column]??'')===expected)delete next[key];
      return next;
    });
  }
  function openPicker(){setTemporary('');setDetailReview(null);setMessage('');const order=[...selected,...candidates.map(p=>p.id).filter(id=>!selected.includes(id))];setPickerOrder(order);setPickerIds([...selected]);setPickerBaseline([...selected]);setDialog('projects');}
  const pickerSelection=pickerOrder.filter(id=>pickerIds.includes(id));
  const settingsDirty=dialog==='plate'?JSON.stringify(plateKeywords(keywords))!==keywordsBaseline:dialog==='projects'&&JSON.stringify(pickerSelection)!==JSON.stringify(pickerBaseline);
  const settingsFeedback=(message||needsRead)&&<p className="notice" role="alert">{message||'设置操作结果待核实，请重新读取核对；输入已保留。'}{needsRead&&<Button disabled={writing||state.isFetching||blocked} onClick={()=>void rereadSettings()}>重新读取</Button>}</p>;
  const exportUnavailable = !me ? '登录后可导出。' : exportGuard || (blocked ? '账号待核实，请稍候。' : writing ? '机械费正在保存，请稍候。' : needsRead||saves.uncertain ? '机械费操作结果待核实，请先重新读取。' : Object.keys(saves.drafts).length ? '请先处理机械费未保存输入。' : projects.isError || state.isError ? '项目或月份读取失败，请先重新读取。' : projects.isFetching || state.isFetching ? '正在核对项目和月份，请稍候。' : !ym ? '请选择报表月份。' : '');
  function exportControl(){const owner=me ? `${me.id}:${me.account}` : 'anonymous';return <MechanicalExport key={owner} owner={owner} month={ym} projects={candidates} defaults={selected} unavailable={exportUnavailable} paused={blocked||!active} message={text=>{void toast.success(text);}}/>;}
  const historyGuard = writing ? '机械费正在保存，请稍候。' : needsRead||saves.uncertain ? '机械费操作结果待核实，请返回重新读取。' : Object.keys(saves.drafts).length || settingsDirty ? '机械费有未保存输入，请先处理。' : '';
  useHistoryGuard('mechanical', () => historyGuard);
  useEffect(() => { onHistoryGuard(historyGuard); }, [onHistoryGuard, historyGuard]);
  useEffect(() => () => onHistoryGuard(''), [onHistoryGuard]);
  const error = projects.error || state.error;
  const monthRead = readPhase(state);
  const readBody = <ReadPlaceholder rows={6} quiet={monthRead==='error'} />;
  return <section className="mechanical-card page-shell page-shell--flow" data-page-layout="flow" aria-labelledby="page-title"><div data-page-chrome className="mechanical-toolbar">
    <div className="mechanical-month"><span>月份</span><TimePicker label="月份" modes={['月']} value={ym} disabled={blocked||writing} onChange={value=>{setMonth(value);setDetailReview(null);}} /></div>
    <div className="mechanical-tabs" role="group" aria-label="机械费报表">{([['summary','表1 公司汇总'],['zero','表2 零租明细'],['monthly','表3 包月明细'],['work','核对工作台']] as const).map(([id,name])=><Button key={id} disabled={writing} aria-pressed={tab===id} onClick={()=>{setTab(id);setTemporary('');setProblemsOnly(false);setDetailReview(null);}}>{name}</Button>)}</div>
    <div className="mechanical-project-entry"><Button disabled={blocked||writing||state.isFetching} onClick={openPicker}>显示项目</Button></div>
    </div>
    {tab==='summary'&&<div data-page-chrome className="mechanical-summary-tools"><strong>公司汇总</strong><span className="muted">金额单位：元</span><div className="mechanical-project-tools">{exportControl()}</div></div>}
    {needsRead && <p className="notice" role="alert">保存后需要重新读取。<Button onClick={()=>void refresh()}>重新读取</Button></p>}
    {saves.uncertain&&<p className="notice" role="alert">{saves.error||'已重读，请核对保存结果后继续。'}<Button disabled={blocked||writing||verifying||state.isFetching} onClick={()=>void rereadCells()}>{internalSubmitted.current?'重读内租':'重读明细'}</Button><Button disabled={blocked||writing||verifying||!saves.verified||state.isFetching||state.isError} onClick={confirmCellRead}>已核对，继续</Button></p>}
    <ReadStatusLane phase={monthRead} announce="正在读取机械报表…" className="mechanical-read-status">
      {(monthRead==='error'||monthRead==='stale')&&<ReadFailure read={state}/>}
      {projects.isError&&<ReadFailure read={projects} label="项目清单" retained="项目清单更新未成功，保留上次结果。"/>}
    </ReadStatusLane>
    {(tab==='zero'||tab==='monthly') && <div className="mechanical-edit-tools"><strong>{category==='zero'?'零租设备月报':'包月外租设备月报'}</strong>{temporary&&<><span>临时筛选：{label(temporary)}</span><Button onClick={()=>{setTemporary('');}}>取消筛选</Button></>}<label><Checkbox checked={problemsOnly} onChange={e=>{setProblemsOnly(e.target.checked);}} >仅看待补字段</Checkbox></label><span className="mechanical-tools-spacer" /><Button disabled={!writable||writing||state.isFetching} onClick={()=>{const text=(state.data?.settings.plate_keywords??[]).join('\n');setKeywords(text);setKeywordsBaseline(JSON.stringify(plateKeywords(text)));setMessage('');setDialog('plate');}}>车牌规则</Button>{exportControl()}</div>}
    {Object.entries(saves.drafts).filter(([,draft])=>draft.error).map(([key,draft])=>
      <div key={key} className="mechanical-feedback">
        <span role="alert">{label(draft.warehouse)}，{draft.ym} {isInternalDraft(draft)?(draft.column==='mech_0'?'工程公司内租':'租赁公司内租'):(draft.category==='zero'?'零租明细':'包月明细')}：{draft.error}</span>
        {!isInternalDraft(draft) && draft.conflicted ? <>
          <Button size="small" disabled={blocked||writing||verifying} onClick={()=>reviewDetail(key,draft,false)}>查看已保存明细</Button>
          <Button size="small" disabled={blocked||writing||verifying} onClick={()=>reviewDetail(key,draft,true)}>查看保留输入</Button>
          {reviewing === draft && <span role="status">表中显示{detailReview?.showDraft ? '保留输入' : '已保存明细'}</span>}
        </> : <Button size="small" disabled={!writable||writing} onMouseDown={e=>e.preventDefault()} onClick={()=>saves.save(key,true)}>重试保存</Button>}
        <Button size="small" disabled={!me||!active||blocked||writing||saves.uncertain} onMouseDown={e=>e.preventDefault()} onClick={()=>cancelFailedDraft(key,draft)}>取消这项修改</Button>
      </div>)}
    <FirstReadRegion phase={state.data && projects.data ? 'content' : (!state.data && state.isError) || (!projects.data && projects.isError) ? 'error' : 'pending'} placeholder={<div className="mechanical-read-body"><ReadPlaceholder rows={6} quiet={(!state.data && state.isError) || (!projects.data && projects.isError)} /></div>}>
    {(tab==='zero'||tab==='monthly') && <>
      {state.data ? <DetailsTable scale={Number(me?.ui_scale_css)||1} groups={detailGroups} ym={ym} category={category} keywords={state.data.settings.plate_keywords} problemsOnly={problemsOnly} writable={writable} change={edit} save={warehouse=>saves.save(detailKey(warehouse,ym,category))} /> : <div className="mechanical-read-body">{readBody}</div>}

    </>}
    {tab==='work'&&(state.data?<MechanicalWork me={me} data={state.data} warehouses={warehouses} label={label} writable={writable} busy={writing} paused={blocked||!active} operate={operate} refresh={refresh} added={warehouse=>{const project=candidates.find(p=>p.warehouse_name===warehouse);if(project&&!selected.includes(project.id))setIds([...selected,project.id]);}} />:<div className="mechanical-read-body">{readBody}</div>)}
    {scopeError && !error && <p className="notice" role="alert">{scopeError}</p>}
    {!ym ? <p className="state" role="status">暂无已保存月份，请在现有工作区保存后再查看。</p> : !warehouses.length && (monthRead==='ready'||monthRead==='empty') ? <p className="state" role="status">请选择项目查看报表。</p> : null}
    {!scopeMismatch && tab==='summary' && (state.data ? (warehouses.length > 0 && <Summary active={active} scale={Number(me?.ui_scale_css) || 1} key={ym} ym={ym} projects={summaryProjects} detail={detail} internal={internal} data={state.data} warehouses={warehouses} />) : <div className="mechanical-read-body">{readBody}</div>)}
    </FirstReadRegion>
    <DialogPresence>{dialog==='projects'&&<MechanicalDialog layout="pane" className="mechanical-project-dialog" title="选择显示项目及顺序" close={()=>setDialog(null)} busy={writing} paused={blocked||!active} dirty={settingsDirty}
      footer={requestClose=><><Button disabled={writing} onClick={requestClose}>取消</Button><Button type="primary" disabled={!writable} onClick={()=>void saveSettings({shown_projects:pickerSelection.flatMap(id=>candidates.find(p=>p.id===id)?.warehouse_name??[])},()=>{setIds(pickerSelection);setTemporary('');},'显示项目及顺序已保存。')}>应用项目选择</Button></>}>
      <p>按勾选项目显示，顺序可调整；其他项目的数据保留。</p>
      <ProjectSelectionOrder projects={pickerOrder.flatMap(id=>candidates.filter(project=>project.id===id))} selected={pickerSelection} choose={setPickerIds} move={(index,offset)=>{const next=[...pickerOrder];[next[index+offset],next[index]]=[next[index]!,next[index+offset]!];setPickerOrder(next);}} disabled={writing} label="显示项目选择与顺序" />
      {settingsFeedback}
    </MechanicalDialog>}</DialogPresence>

    <DialogPresence>{dialog==='plate'&&<MechanicalDialog layout="scroll-body" className="mechanical-plate-dialog" title="无需车牌设备关键词" close={()=>setDialog(null)} busy={writing} paused={blocked||!active} dirty={settingsDirty}
      footer={requestClose=><><Button disabled={writing} onClick={requestClose}>取消</Button><Button type="primary" disabled={writing||!writable} onClick={()=>void saveSettings({plate_keywords:plateKeywords(keywords)},()=>{},'车牌规则已保存。')}>保存规则</Button></>}><label>每行一个关键词<Input.TextArea aria-label="无需车牌设备关键词" value={keywords} disabled={writing} onChange={e=>setKeywords(e.target.value)} /></label>{settingsFeedback}</MechanicalDialog>}</DialogPresence>
    {message && !needsRead && <p className="mechanical-feedback" role="status">{message}</p>}
  </section>;
}
