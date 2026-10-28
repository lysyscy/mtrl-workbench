import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Checkbox from 'antd/es/checkbox';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ColGroupDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { ApiError, readProjects, record, requestFile, requestJson, uncertainWrite } from './api';
import type { Identity, Project } from './api';
import { pageGridGeometry, contentWidth, fixedWidth, gridTheme } from './grid';
import { detailSum, mechanicalMoney as money, readDetail, readMechanicalReport, readWorkbench, readWorkResult } from './mechanical-api';
import { DetailsTable, MechanicalDialog, detailKey, mechanicalNumberWidth } from './mechanical-details';
import { useCellSaveQueue } from './use-cell-save';
import { TimePicker } from './time-picker';
import { currentMonth } from './business-time';
import { useHistoryGuard } from './history';
import { MechanicalWork } from './mechanical-work';
import type { Draft } from './mechanical-details';
import { body } from './notices-api';
import type { Category, Effective, Workbench, MechanicalReport } from './mechanical-api';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
import { ReadGrid } from './business-grid';
import { ProjectExport } from './ledger-controls';
const summaryRowId = (row: SummaryRow) => row.id;
const plateKeywords = (text: string) => [...new Set(text.split('\n').map(word => word.trim()).filter(Boolean))];

interface InternalEditing { epoch: number; writable: boolean; value: (id: string,column: string) => string | undefined; change: (id: string,column: string,value: string) => void }
function InternalCell({ id, column, value, label, editing, epoch }: { id: string; column: string; value: string; label: string; editing: React.RefObject<InternalEditing>; epoch: number }) {
  const [text,setText]=useState(()=>editing.current.value(id,column)??value);
  useEffect(()=>{setText(editing.current.value(id,column)??value);},[value,id,column,editing,epoch]);
  return <Input aria-label={label} inputMode="decimal" className="mechanical-internal-input money" value={text} onChange={event=>{setText(event.target.value);editing.current.change(id,column,event.target.value);}} />;
}
interface SummaryRow { id: string; [column: string]: string }
const groupLabels = ['零租', '包月', '周材', '内租（租赁公司）', '内租（工程公司）'];
function Summary({ scale, report, projectIds, detail, internal, data, warehouses, active }: { active: boolean; scale: number; data:Workbench; warehouses:string[]; internal: InternalEditing; report: MechanicalReport; projectIds: number[]; detail: (sheet: number, projectId: string) => void }) {
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
      + (horizontal && getComputedStyle(horizontal).visibility !== 'hidden' ? horizontal.getBoundingClientRect().height : 0) + 2;
    const height = Math.ceil(Math.min(natural, Math.max(200 * scale, window.innerHeight - element.getBoundingClientRect().top - 16 * scale)));
    if (Math.abs(element.getBoundingClientRect().height - height) > .5) element.style.height = `${height}px`;
  }, []);
  useEffect(() => {
    window.addEventListener('resize', fitHeight); void document.fonts.ready.then(fitHeight);
    return () => { window.removeEventListener('resize', fitHeight); };
  }, [fitHeight]);
  const current=useRef(internal);current.current=internal;
  useEffect(()=>{api.current?.refreshCells({force:true});},[internal.epoch,internal.writable]);
  const rows = useMemo(() => report.sheets[0]!.rows.slice(5).map((cells, index) => {
    const row: SummaryRow = { id: String(projectIds[index] ?? 'total') };
    for (const cell of cells) row[`c${cell.column - 1}`] = cell.value;
    const warehouse=warehouses[index];
    if(warehouse){const summary=data.summary.find(item=>item.warehouse===warehouse&&item.ym===report.ym),history=data.histories.find(item=>item.warehouse===warehouse);const monthly=history&&record(history.original_months)&&record(history.original_months[report.ym])?history.original_months[report.ym]:null;row.c6=summary?.cumulative.weekly??'';row.c11=record(monthly)&&typeof monthly.weekly==='string'?monthly.weekly:'';row.c14=summary?.note??'';}
    else if(index===warehouses.length){row.c6=detailSum(data.summary.filter(item=>item.ym===report.ym&&warehouses.includes(item.warehouse)).map(item=>item.cumulative.weekly))??'';row.c11=detailSum(data.effective.filter(item=>item.ym===report.ym&&warehouses.includes(item.warehouse)).map(item=>item.values.weekly))??'';}
    return row;
  }), [report, projectIds, data, warehouses]);
  const openDetail = useRef(detail); openDetail.current = detail;
  const renderInternal = useCallback((params: ICellRendererParams<SummaryRow,string>) => {
    const index = params.colDef?.field === 'c12' ? 3 : 4;
    return params.node.rowPinned || !current.current.writable ? money(params.value) : <InternalCell id={params.data!.id} column={index === 3 ? 'mech_1' : 'mech_0'} value={params.value ?? ''} label={`${params.data?.c1} ${groupLabels[index]}`} editing={current} epoch={current.current.epoch} />;
  }, []);
  const renderDetail = useCallback((params: ICellRendererParams<SummaryRow,string>) => {
    const index = params.colDef?.field === 'c9' ? 0 : 1;
    return params.node.rowPinned ? money(params.value) : <Button className="mechanical-amount-button" aria-label={`${params.data?.c1} ${groupLabels[index]}明细`} onClick={() => openDetail.current(index + 1, params.data?.id ?? '')}>{money(params.value)}</Button>;
  }, []);
  const columns = useMemo<(ColDef<SummaryRow> | ColGroupDef<SummaryRow>)[]>(() => [
    { field: 'c0', headerName: '序号', pinned: 'left', ...fixedWidth(48, scale) },
    { field: 'c1', headerName: '项目名称', pinned: 'left', ...contentWidth(120, 200, scale), wrapText: true, autoHeight: true },
    { headerName: '开工日期', children: [{ field: 'c2', headerName: '年', ...contentWidth(48, 68, scale) }, { field: 'c3', headerName: '月', ...contentWidth(34, 56, scale), cellClass: 'mechanical-group-end', headerClass: 'mechanical-group-end' }] },
    ...['开工累计费用（元）', '本月产生费用（元）'].map((name, group) => ({ headerName: name, headerClass: 'mechanical-group-end', children: groupLabels.map((label, index): ColDef<SummaryRow> => ({
      field: `c${4 + group * 5 + index}`, headerName: label, ...mechanicalNumberWidth(rows.map(row => money(row[`c${4 + group * 5 + index}`])), scale, group === 1 && index !== 2,1), wrapText: false, autoHeight: true, valueFormatter:p=>money(p.value), cellClass: index === 4 ? 'money mechanical-group-end' : 'money', headerClass: index === 4 ? 'mechanical-group-end' : '',
      ...(group===1&&index>2?{cellRenderer:renderInternal}:{}),
      ...(group === 1 && index < 2 ? { cellRenderer: renderDetail } : {}),
    })) })),
    { field: 'c14', headerName: '备注', ...contentWidth(72, 144, scale), wrapText: true, autoHeight: true },
  ], [scale, rows, renderInternal, renderDetail]);
  const measurement = useMemo(() => ({signature:(row:SummaryRow,id:string,pinned:boolean)=>JSON.stringify([row[id],pinned,internal.writable])}), [internal.writable]);
  const bodyRows = useMemo(() => rows.slice(0, -1), [rows]), total = useMemo(() => rows.slice(-1), [rows]);
  const scope = `${report.ym}:${warehouses.join('\0')}`;
  const presentation = useGridPresentation({table: 'mechanical-summary', root, active, rows: bodyRows, totals: total, columns, measurement, rowId: summaryRowId, scale, scope, identity: scope});
  useLayoutEffect(() => { if (presentation.state === 'ready') fitHeight(); }, [presentation.state, fitHeight]);
  return <PreparedGrid presentation={presentation} className="mechanical-grid" role="region" aria-label="公司汇总" grid={{theme:gridTheme,defaultColDef:{sortable:false,resizable:true,suppressMovable:true,wrapHeaderText:true},getRowId:params=>params.data.id,groupHeaderHeight:pageGridGeometry(scale).groupHeaderHeight,suppressColumnVirtualisation:true,enableCellTextSelection:true,ensureDomOrder:true,onGridSizeChanged:fitHeight,onModelUpdated:fitHeight,onColumnResized:fitHeight,onGridReady:event=>{
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
export function MechanicalPage({ me, blocked, exportGuard, active }: { me: Identity | null; blocked: boolean; exportGuard: string; active: boolean }) {
  const scale=Number(me?.ui_scale_css)||1;
  const client = useQueryClient();
  const [month, setMonth] = useState(()=>{const [year,month]=currentMonth().split('-');return new Date(Date.UTC(Number(year),Number(month)-2,15)).toISOString().slice(0,7);}); const [ids, setIds] = useState<number[] | null>(null);
  const [pickerIds,setPickerIds]=useState<number[]>([]); const [pickerOrder,setPickerOrder]=useState<number[]>([]);
  const [pickerBaseline,setPickerBaseline]=useState<number[]>([]),[keywordsBaseline,setKeywordsBaseline]=useState('');
  const [message, setMessage] = useState('');
  const projects = useQuery({ queryKey: ['projects', 'all'], enabled: !blocked, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const state = useQuery({ queryKey: ['mechanical-state',month], enabled: !blocked, queryFn: async ({ signal }) => readWorkbench(await requestJson('/api/m06/workbench?ym='+encodeURIComponent(month), { signal })) });
  const candidates = useMemo(() => projects.data?.filter(project => state.data?.warehouses.includes(project.warehouse_name ?? '')) ?? [], [projects.data, state.data]);
  const selected = useMemo(() => ids ?? (state.data?.shown.flatMap(warehouse => candidates.filter(project => project.warehouse_name === warehouse).map(project => project.id)) ?? []), [ids, state.data, candidates]);
  const warehouses = useMemo(() => selected.flatMap(id => candidates.find(project => project.id === id)?.warehouse_name ?? []), [selected, candidates]);
  const ym = month;
  const scopeError = selected.length !== warehouses.length ? '所选项目范围已变化，请重新选择。' : projects.isError || state.isError ? '项目或月份读取失败，请先重新读取。' : '';
  const scope = JSON.stringify([ym, warehouses]);
  const report = useQuery({ queryKey: ['mechanical-report', ym, warehouses], enabled: !blocked && !scopeError && Boolean(ym) && warehouses.length > 0, queryFn: async ({ signal }) => readMechanicalReport(await requestJson(`/api/m06/workbench/preview?${new URLSearchParams({ ym, projects: JSON.stringify(warehouses) })}`, { signal }), ym, warehouses) });
  useEffect(() => { setMessage(''); }, [scope, blocked, exportGuard, scopeError]);
  const [tab, setTab] = useState<'summary' | 'zero' | 'monthly' | 'work'>('summary');
  const [temporary, setTemporary] = useState(''); const [problemsOnly, setProblemsOnly] = useState(false);
  const [,render] = useState(0); const [operating,setWriting] = useState(false); const writeLock = useRef(false);
  const savedRevisions=useRef(new Map<string,number>());
  const [needsRead,setNeedsRead] = useState(false);
  const [dialog,setDialog] = useState<'discard' | 'plate' | 'projects' | null>(null); const [keywords,setKeywords] = useState('');
  const internalDrafts=useRef(new Map<string,{warehouse:string;ym:string;values:Record<string,string>}>());
  const [internalEpoch,setInternalEpoch]=useState(0);
  const [internalConfirmation,setInternalConfirmation]=useState<{warehouse:string;ym:string;values:Record<string,string>;effective:Effective}[]|null>(null);
  const saves=useCellSaveQueue<Draft,Workbench>({
    enabled:Boolean(me)&&active&&!blocked,canWrite:!operating&&!needsRead&&!state.isError&&Boolean(state.data),
    read:readDetails,
    write:async(draft,signal)=>{
      const response=await requestJson('/api/m06/workbench/details-save',{method:'POST',signal,...body({warehouse:draft.warehouse,ym:draft.ym,category:draft.category,revision:draft.revision,rows:structuredClone(draft.rows)})});
      let saved;try{saved=readDetail(response);if(!record(response)||response.ok!==true||saved.warehouse!==draft.warehouse||saved.ym!==draft.ym||saved.category!==draft.category||saved.revision!==draft.revision+1)throw new Error();}
      catch{throw new ApiError('明细保存回执不完整，请重读核对。',0,'invalid_receipt');}
      draft.revision=saved.revision;savedRevisions.current.set(detailKey(draft.warehouse,draft.ym,draft.category),saved.revision);
      await client.cancelQueries({queryKey:['mechanical-state']});
      client.setQueriesData<Workbench>({queryKey:['mechanical-state']},old=>old?{...old,details:[...old.details.filter(detail=>detailKey(detail.warehouse,detail.ym,detail.category)!==detailKey(saved.warehouse,saved.ym,saved.category)),saved]}:old);
    },
    acknowledge:(current,submitted)=>current.version===submitted.version?undefined:{...current,revision:submitted.revision},
    saved:()=>'',stopOnRejection:true,
    describe:draft=>`${draft.warehouse}，${draft.ym} `,
  },{key:'mechanical-details',label:'机械明细'});
  const writing=operating||saves.busy;
  const writable = Boolean(me) && active && !blocked && !operating && !needsRead && !saves.uncertain && Boolean(state.data) && !state.isError;
  const category: Category = tab === 'monthly' ? 'monthly' : 'zero';
  const editingWarehouses = temporary ? warehouses.filter(w => w === temporary) : warehouses;
  const label = (warehouse: string) => candidates.find(p => p.warehouse_name === warehouse)?.disp || warehouse;
  const detail = useCallback((index: number, projectId: string) => {
    const warehouse = projects.data?.find(project => String(project.id) === projectId)?.warehouse_name;
    if (warehouse) { setTab(index === 2 ? 'monthly' : 'zero');setTemporary(warehouse);setProblemsOnly(false); }
  },[projects.data]);
  useEffect(() => {setTemporary('');setProblemsOnly(false);setInternalConfirmation(null);setDialog(current=>current==='projects'?'projects':null);},[scope]);
  function edit(warehouse: string, rows: import('./mechanical-api').DetailRow[]) {
    if (!writable) return;
    const key=detailKey(warehouse,ym,category);
    const saved=state.data?.details.find(d => detailKey(d.warehouse,d.ym,d.category)===key);
    saves.update(current=>{const previous=current[key];return {...current,[key]:{warehouse,ym,category,revision:previous?.revision??Math.max(saved?.revision??0,savedRevisions.current.get(key)??0),rows,version:(previous?.version??0)+1,error:''}};});
  }
  async function readDetails(){
    await client.cancelQueries({queryKey:['mechanical-state']});
    const data=await client.fetchQuery({queryKey:['mechanical-state',month],staleTime:0,queryFn:({signal})=>requestJson('/api/m06/workbench?ym='+encodeURIComponent(month),{signal}).then(readWorkbench)});
    await client.invalidateQueries({predicate:q=>q.queryKey[0]!=='mechanical-state'},{throwOnError:true});
    return data;
  }
  async function refresh() {
    try {await client.invalidateQueries({}, {throwOnError:true});setNeedsRead(false);if(needsRead)setMessage('已重新读取。');return true;}
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
      saved();setDialog(null);if(await refresh())setMessage(message);
    });
  }
  async function rereadSettings() {
    if(writing||state.isFetching)return;
    if(!await refresh()){setMessage('设置保存结果仍待核实，重新读取失败；输入已保留。');return;}
    const latest=client.getQueryData<Workbench>(['mechanical-state',month]);
    // An explicit recovery read may acknowledge an already-saved draft; background reads never reset it.
    if(latest&&dialog==='plate'&&JSON.stringify(plateKeywords(keywords))===JSON.stringify(latest.settings.plate_keywords))setKeywordsBaseline(JSON.stringify(plateKeywords(keywords)));
    if(latest&&dialog==='projects'&&JSON.stringify(pickerOrder.filter(id=>pickerIds.includes(id)).flatMap(id=>candidates.find(p=>p.id===id)?.warehouse_name??[]))===JSON.stringify(latest.shown)){const selected=pickerOrder.filter(id=>pickerIds.includes(id));setPickerBaseline(selected);setIds(selected);setTemporary('');}
    setMessage('已重新读取，请核对设置后继续。');
  }
  const dirty=Object.values(saves.drafts).filter(d=>d.ym===ym&&d.category===category&&editingWarehouses.includes(d.warehouse)).length;
  const internalTargets=[...internalDrafts.current.values()].filter(d=>d.ym===ym&&warehouses.includes(d.warehouse));
  const internal:InternalEditing={epoch:internalEpoch,writable,value:(id,column)=>internalDrafts.current.get(JSON.stringify([id,ym]))?.values[column],change:(id,column,value)=>{const key=JSON.stringify([id,ym]),warehouse=candidates.find(p=>String(p.id)===id)?.warehouse_name;if(!warehouse)return;const old=internalDrafts.current.get(key);internalDrafts.current.set(key,{warehouse,ym,values:{...old?.values,[column]:value}});render(n=>n+1);}};
  function openPicker(){setTemporary('');setMessage('');const order=[...selected,...candidates.map(p=>p.id).filter(id=>!selected.includes(id))];setPickerOrder(order);setPickerIds([...selected]);setPickerBaseline([...selected]);setDialog('projects');}
  const pickerSelection=pickerOrder.filter(id=>pickerIds.includes(id));
  const settingsDirty=dialog==='plate'?JSON.stringify(plateKeywords(keywords))!==keywordsBaseline:dialog==='projects'&&JSON.stringify(pickerSelection)!==JSON.stringify(pickerBaseline);
  const settingsFeedback=(message||needsRead)&&<p className="notice" role="alert">{message||'设置操作结果待核实，请重新读取核对；输入已保留。'}{needsRead&&<Button disabled={writing||state.isFetching||blocked} onClick={()=>void rereadSettings()}>重新读取</Button>}</p>;
  const exportUnavailable = !me ? '登录后可导出。' : exportGuard || (blocked ? '账号待核实，请稍候。' : writing ? '机械费正在保存，请稍候。' : needsRead||saves.uncertain ? '机械费操作结果待核实，请先重新读取。' : Object.keys(saves.drafts).length ? '请先处理机械费未保存输入。' : projects.isError || state.isError ? '项目或月份读取失败，请先重新读取。' : projects.isFetching || state.isFetching ? '正在核对项目和月份，请稍候。' : !ym ? '请选择报表月份。' : '');
  function exportControl(){const owner=me ? `${me.id}:${me.account}` : 'anonymous';return <MechanicalExport key={owner} owner={owner} month={ym} projects={candidates} defaults={selected} unavailable={exportUnavailable} paused={blocked||!active} message={setMessage}/>;}
  useHistoryGuard('mechanical', () => writing ? '机械费正在保存，请稍候。' : needsRead||saves.uncertain ? '机械费操作结果待核实，请返回重新读取。' : Object.keys(saves.drafts).length || internalDrafts.current.size || settingsDirty ? '请先处理机械费未保存修改。' : '');
  const error = projects.error || state.error || report.error;
  return <section className="mechanical-card" aria-labelledby="page-title"><div data-page-chrome className="mechanical-toolbar">
    <div className="mechanical-month"><span>月份</span><TimePicker label="月份" modes={['月']} value={ym} disabled={blocked||writing} onChange={value=>{setMonth(value);}} /></div>
    <div className="mechanical-tabs" role="group" aria-label="机械费报表">{([['summary','表1 公司汇总'],['zero','表2 零租明细'],['monthly','表3 包月明细'],['work','核对工作台']] as const).map(([id,name])=><Button key={id} disabled={writing} aria-pressed={tab===id} onClick={()=>{setTab(id);setTemporary('');setProblemsOnly(false);}}>{name}</Button>)}</div>
    <div className="mechanical-project-entry"><Button disabled={blocked||writing||state.isFetching} onClick={openPicker}>显示项目</Button></div>
    </div>
    {tab==='summary'&&<div data-page-chrome className="mechanical-summary-tools"><strong>公司汇总</strong><span className="muted">金额单位：元</span><div className="mechanical-project-tools"><Button disabled={!writable||!internalTargets.length} onClick={()=>setInternalConfirmation(internalTargets.map(d=>({...structuredClone(d),effective:state.data!.effective.find(e=>e.warehouse===d.warehouse&&e.ym===d.ym)!})).filter(d=>d.effective))}>确认内租（{internalTargets.length}项）</Button><Button disabled={!writable||!internalTargets.length} onClick={()=>{for(const [key,d] of internalDrafts.current)if(d.ym===ym&&warehouses.includes(d.warehouse))internalDrafts.current.delete(key);setInternalEpoch(n=>n+1);render(n=>n+1);}}>取消内租修改</Button>{exportControl()}</div></div>}
    {needsRead && <p className="notice" role="alert">保存后需要重新读取。<Button onClick={()=>void refresh()}>重新读取</Button></p>}
    {(saves.error||saves.uncertain)&&<p className="notice" role="alert">{saves.error||'已重读，请核对保存结果后继续。'}{saves.uncertain&&<Button disabled={blocked||writing||state.isFetching} onClick={()=>void saves.reread()}>重读明细</Button>}{saves.uncertain&&<Button disabled={blocked||writing||!saves.verified||state.isFetching||state.isError} onClick={()=>saves.confirm()}>已核对，继续</Button>}</p>}
    {(tab==='zero'||tab==='monthly') && <>
      <div className="mechanical-edit-tools"><strong>{category==='zero'?'零租设备月报':'包月外租设备月报'}</strong>{temporary&&<><span>临时筛选：{label(temporary)}</span><Button onClick={()=>{setTemporary('');}}>取消筛选</Button></>}<label><Checkbox checked={problemsOnly} onChange={e=>{setProblemsOnly(e.target.checked);}} >仅看待补字段</Checkbox></label><span className="mechanical-tools-spacer" /><Button disabled={!writable||writing||state.isFetching} onClick={()=>{const text=(state.data?.settings.plate_keywords??[]).join('\n');setKeywords(text);setKeywordsBaseline(JSON.stringify(plateKeywords(text)));setMessage('');setDialog('plate');}}>车牌规则</Button><Button danger disabled={!dirty||writing||!writable} onClick={()=>setDialog('discard')}>撤销未保存修改</Button>{exportControl()}</div>
      {!state.isError && !state.isPending && <DetailsTable scale={Number(me?.ui_scale_css)||1} groups={editingWarehouses.map(warehouse=>{const key=detailKey(warehouse,ym,category);return {warehouse,name:label(warehouse),saved:state.data?.details.find(d=>detailKey(d.warehouse,d.ym,d.category)===key),draft:saves.drafts[key]};})} ym={ym} category={category} keywords={state.data?.settings.plate_keywords??[]} problemsOnly={problemsOnly} writable={writable} change={edit} save={warehouse=>saves.save(detailKey(warehouse,ym,category),true)} />}

    </>}
    {tab==='work'&&state.data&&!state.isError&&<MechanicalWork data={state.data} warehouses={warehouses} label={label} writable={writable} busy={writing} paused={blocked||!active} operate={operate} refresh={refresh} added={warehouse=>{const project=candidates.find(p=>p.warehouse_name===warehouse);if(project&&!selected.includes(project.id))setIds([...selected,project.id]);}} />}
    {scopeError && !error && <p className="notice" role="alert">{scopeError}</p>}
    {error && !needsRead ? <p className="notice" role="alert">{error.message}<Button onClick={() => { void projects.refetch(); void state.refetch(); void report.refetch(); }}>重新读取</Button></p> : state.isPending || projects.isPending || report.isFetching && !report.data ? <p className="state" role="status">正在读取机械报表…</p> : !ym ? <p className="state" role="status">暂无已保存月份，请在现有工作区保存后再查看。</p> : !warehouses.length ? <p className="state" role="status">请选择项目查看报表。</p> : null}
    {report.data && !scopeError && !report.isError && warehouses.length > 0 && tab==='summary' && <Summary active={active} scale={Number(me?.ui_scale_css) || 1} key={ym} report={report.data} projectIds={selected} detail={detail} internal={internal} data={state.data!} warehouses={warehouses} />}
    {dialog==='projects'&&<MechanicalDialog className="mechanical-project-dialog" title="选择显示项目及顺序" close={()=>setDialog(null)} busy={writing} paused={blocked||!active} dirty={settingsDirty}>{requestClose=><>
      <p>按勾选项目显示，顺序可调整；其他项目的数据保留。</p><div className="mechanical-project-tools"><Button disabled={writing} onClick={()=>setPickerIds([...pickerOrder])}>全选</Button><Button disabled={writing} onClick={()=>setPickerIds([])}>全不选</Button><span>已选 {pickerIds.length} 个项目</span></div>
      <ol className="mechanical-picker-list">{pickerOrder.map((id,index)=><li key={id}><Checkbox disabled={writing} checked={pickerIds.includes(id)} onChange={e=>setPickerIds(previous=>e.target.checked?[...previous,id]:previous.filter(p=>p!==id))}>{candidates.find(p=>p.id===id)?.disp}</Checkbox><span>{([-1,1] as const).map(step=><Button key={step} disabled={writing||index+step<0||index+step>=pickerOrder.length} onClick={()=>{const next=[...pickerOrder];[next[index+step],next[index]]=[next[index]!,next[index+step]!];setPickerOrder(next);}}>{step===-1?'上移':'下移'}</Button>)}</span></li>)}</ol>
      {settingsFeedback}<footer><Button disabled={writing} onClick={requestClose}>取消</Button><Button type="primary" disabled={!writable} onClick={()=>void saveSettings({shown_projects:pickerSelection.flatMap(id=>candidates.find(p=>p.id===id)?.warehouse_name??[])},()=>{setIds(pickerSelection);setTemporary('');},'显示项目及顺序已保存。')}>应用项目选择</Button></footer>
    </>}</MechanicalDialog>}

    {internalConfirmation&&<MechanicalDialog title="确认内租填数" close={()=>setInternalConfirmation(null)} busy={writing} paused={blocked||!active}><ReadGrid table="mechanical-internal-confirm" label="内租确认清单" domLayout="autoHeight" rows={internalConfirmation.flatMap(d=>Object.entries(d.values).map(([column,value])=>({id:JSON.stringify([d.warehouse,d.ym,column]),d,column,value})))} rowId={row=>row.id} columns={[
        {colId:'project',headerName:'项目／月份',valueGetter:p=>label(p.data!.d.warehouse)+'／'+p.data!.d.ym},
        {colId:'category',headerName:'类别',valueGetter:p=>p.data!.column==='mech_0'?'工程公司内租':'租赁公司内租'},
        {colId:'old',headerName:'原有效值',...mechanicalNumberWidth(internalConfirmation.flatMap(d=>Object.keys(d.values).map(column=>money(d.effective.values[column]))),scale),cellClass:'money',valueGetter:p=>money(p.data!.d.effective.values[p.data!.column])},
        {colId:'next',headerName:'拟采用值',...mechanicalNumberWidth(internalConfirmation.flatMap(d=>Object.values(d.values).map(money)),scale),cellClass:'money wrap-note',valueGetter:p=>money(p.data!.value)+(Number(p.data!.value)<Number(p.data!.d.effective.values[p.data!.column])?'，金额减少，请核实':'')},
      ]}/><footer><Button disabled={writing} onClick={()=>setInternalConfirmation(null)}>返回修改</Button><Button type="primary" disabled={!writable||writing} onClick={()=>void operate(async()=>{if(internalConfirmation.some(d=>Object.values(d.values).some(value=>!/^\d+(?:\.\d{1,2})?$/.test(value.trim()))))throw new Error('内租须填写非负金额，最多两位小数。');let count=0;try{for(const d of internalConfirmation){await requestJson('/api/m06/workbench/internal-save',{method:'POST',...body({...d,effective_signature:d.effective.signature})});for(const [key,current] of internalDrafts.current)if(current.warehouse===d.warehouse&&current.ym===d.ym&&JSON.stringify(current.values)===JSON.stringify(d.values))internalDrafts.current.delete(key);count++;}}catch(error){setInternalConfirmation(null);await refresh();throw new Error(`已更新 ${count} 组，其余输入保留。${error instanceof Error?error.message:'请重新核对。'}`);}setInternalConfirmation(null);setInternalEpoch(n=>n+1);if(await refresh())setMessage('内租有效月值已确认。');})}>确认更新内租</Button></footer></MechanicalDialog>}
    {dialog==='discard'&&<MechanicalDialog className="mechanical-discard-dialog" title="撤销未保存修改" close={()=>setDialog(null)} busy={writing} paused={blocked||!active}><p>撤销当前范围 {dirty} 个项目的未保存修改，恢复最近已保存明细。</p><footer><Button onClick={()=>setDialog(null)}>保留修改</Button><Button danger onClick={()=>{saves.update(current=>Object.fromEntries(Object.entries(current).filter(([,d])=>d.ym!==ym||d.category!==category||!editingWarehouses.includes(d.warehouse))));saves.clearFeedback();setDialog(null);}}>确认撤销</Button></footer></MechanicalDialog>}
    {dialog==='plate'&&<MechanicalDialog className="mechanical-plate-dialog" title="无需车牌设备关键词" close={()=>setDialog(null)} busy={writing} paused={blocked||!active} dirty={settingsDirty}>{requestClose=><><label>每行一个关键词<Input.TextArea aria-label="无需车牌设备关键词" value={keywords} disabled={writing} onChange={e=>setKeywords(e.target.value)} /></label>{settingsFeedback}<footer><Button disabled={writing} onClick={requestClose}>取消</Button><Button type="primary" disabled={writing||!writable} onClick={()=>void saveSettings({plate_keywords:plateKeywords(keywords)},()=>{},'车牌规则已保存。')}>保存规则</Button></footer></>}</MechanicalDialog>}
    {message && !needsRead && <p className="mechanical-feedback" role="status">{message}</p>}
  </section>;
}
