import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Checkbox from 'antd/es/checkbox';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ColGroupDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { readProjects, record, requestFile, requestJson } from './api';
import type { Identity } from './api';
import { pageGridGeometry, contentWidth, fixedWidth, gridTheme } from './grid';
import { detailSum, mechanicalMoney as money, readDetail, readMechanicalReport, readWorkbench } from './mechanical-api';
import { DetailsTable, MechanicalDialog, detailKey, mechanicalNumberWidth } from './mechanical-details';
import { MechanicalImport } from './mechanical-import';
import { TimePicker } from './time-picker';
import { currentMonth } from './business-time';
import { useHistoryGuard } from './history';
import { MechanicalWork } from './mechanical-work';
import type { Draft } from './mechanical-details';
import { body } from './notices-api';
import type { Category, Detail, Effective, Workbench, MechanicalReport, ReportSheet } from './mechanical-api';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
const summaryRowId = (row: SummaryRow) => row.id;

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
  const columns = useMemo<(ColDef<SummaryRow> | ColGroupDef<SummaryRow>)[]>(() => [
    { field: 'c0', headerName: '序号', pinned: 'left', ...fixedWidth(48, scale) },
    { field: 'c1', headerName: '项目名称', pinned: 'left', ...contentWidth(120, 200, scale), wrapText: true, autoHeight: true },
    { headerName: '开工日期', children: [{ field: 'c2', headerName: '年', ...contentWidth(48, 68, scale) }, { field: 'c3', headerName: '月', ...contentWidth(34, 56, scale), cellClass: 'mechanical-group-end', headerClass: 'mechanical-group-end' }] },
    ...['开工累计费用（元）', '本月产生费用（元）'].map((name, group) => ({ headerName: name, headerClass: 'mechanical-group-end', children: groupLabels.map((label, index): ColDef<SummaryRow> => ({
      field: `c${4 + group * 5 + index}`, headerName: label, ...mechanicalNumberWidth(rows.map(row => money(row[`c${4 + group * 5 + index}`])), scale, group === 1 && index !== 2,1), wrapText: false, autoHeight: true, valueFormatter:p=>money(p.value), cellClass: index === 4 ? 'money mechanical-group-end' : 'money', headerClass: index === 4 ? 'mechanical-group-end' : '',
      ...(group===1&&index>2?{cellRenderer:(params:ICellRendererParams<SummaryRow,string>)=>params.node.rowPinned||!current.current.writable?money(params.value):<InternalCell id={params.data!.id} column={index===3?'mech_1':'mech_0'} value={params.value??''} label={`${params.data?.c1} ${label}`} editing={current} epoch={current.current.epoch} />}:{}),
      ...(group === 1 && index < 2 ? { cellRenderer: (params: ICellRendererParams<SummaryRow, string>) => params.node.rowPinned ? money(params.value) : <Button className="mechanical-amount-button" aria-label={`${params.data?.c1} ${label}明细`} onClick={() => detail(index + 1, params.data?.id ?? '')}>{money(params.value)}</Button> } : {}),
    })) })),
    { field: 'c14', headerName: '备注', ...contentWidth(72, 144, scale), wrapText: true, autoHeight: true },
  ], [scale, detail, rows]);
  const measurement = useMemo(() => ({signature:(row:SummaryRow,id:string,pinned:boolean)=>JSON.stringify([row[id],pinned,internal.writable])}), [internal.writable]);
  const bodyRows = useMemo(() => rows.slice(0, -1), [rows]), total = useMemo(() => rows.slice(-1), [rows]);
  const scope = `${report.ym}:${warehouses.join('\0')}`;
  const presentation = useGridPresentation({root, active, rows: bodyRows, totals: total, columns, measurement, rowId: summaryRowId, scale, scope, identity: scope});
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
function Sheet({ sheet, index, target }: { sheet: ReportSheet; index: number; target: string }) {
  const root = useRef<HTMLDivElement>(null);
  const headers = index === 0 ? 5 : index === 3 ? 1 : 4;
  useEffect(() => {
    if (!target) return;
    const row = root.current?.querySelector<HTMLTableRowElement>(`tr[data-project="${CSS.escape(target)}"]`);
    row?.scrollIntoView({ block: 'center' });
  }, [sheet, target]);
  const firstWidth = index === 3 ? 210 : 60;
  const secondWidth = index === 3 ? 120 : 210;
  const columns = Math.max(...sheet.rows.flatMap(row => row.map(cell => cell.column + cell.colspan - 1)));
  const projectRows = new Map(sheet.project_rows.map(group => [group.row, group.warehouse]));
  function renderRow(cells: ReportSheet['rows'][number], row: number, head: boolean) {
    return <tr key={row} data-project={projectRows.get(row + (head ? 1 : headers + 1))}>{cells.map(cell => { const Tag = head ? 'th' : 'td'; return <Tag key={cell.column} className={cell.column + cell.colspan - 1 <= 2 ? 'mechanical-frozen' : ''} style={cell.column + cell.colspan - 1 <= 2 ? { left: cell.column === 1 ? 0 : `calc(${firstWidth}px * var(--fscale))` } : undefined} rowSpan={cell.rowspan} colSpan={cell.colspan}>{cell.value}</Tag>; })}</tr>;
  }
  return <div ref={root} className="mechanical-sheet" tabIndex={0} role="region" aria-label={sheet.name}><table><caption>{sheet.name}</caption><colgroup>{Array.from({ length: columns }, (_, column) => <col key={column} style={{ width: `calc(${column === 0 ? firstWidth : column === 1 ? secondWidth : 120}px * var(--fscale))` }} />)}</colgroup><thead>{sheet.rows.slice(0, headers).map((cells, row) => renderRow(cells, row, true))}</thead><tbody>{sheet.rows.slice(headers).map((cells, row) => renderRow(cells, row, false))}</tbody></table></div>;
}
export function MechanicalPage({ me, blocked, exportGuard, active }: { me: Identity | null; blocked: boolean; exportGuard: string; active: boolean }) {
  const client = useQueryClient();
  const [month, setMonth] = useState(()=>{const [year,month]=currentMonth().split('-');return new Date(Date.UTC(Number(year),Number(month)-2,15)).toISOString().slice(0,7);}); const [ids, setIds] = useState<number[] | null>(null);
  const [sheet, setSheet] = useState<number | null>(null); const [exportIds,setExportIds]=useState<number[]|null>(null); const [pickerIds,setPickerIds]=useState<number[]>([]); const [pickerOrder,setPickerOrder]=useState<number[]>([]); const [target, setTarget] = useState('');
  const [message, setMessage] = useState(''); const [busy, setBusy] = useState(false);
  const download = useRef<AbortController | null>(null); const previewButton = useRef<HTMLButtonElement>(null);
  const projects = useQuery({ queryKey: ['projects', 'all'], enabled: !blocked, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const state = useQuery({ queryKey: ['mechanical-state',month], enabled: !blocked, queryFn: async ({ signal }) => readWorkbench(await requestJson('/api/m06/workbench?ym='+encodeURIComponent(month), { signal })) });
  const candidates = useMemo(() => projects.data?.filter(project => state.data?.warehouses.includes(project.warehouse_name ?? '')) ?? [], [projects.data, state.data]);
  const selected = useMemo(() => ids ?? (state.data?.shown.flatMap(warehouse => candidates.filter(project => project.warehouse_name === warehouse).map(project => project.id)) ?? []), [ids, state.data, candidates]);
  const warehouses = useMemo(() => selected.flatMap(id => candidates.find(project => project.id === id)?.warehouse_name ?? []), [selected, candidates]);
  const ym = month;
  const scopeError = selected.length !== warehouses.length ? '所选项目范围已变化，请重新选择。' : projects.isError || state.isError ? '项目或月份读取失败，请先重新读取。' : '';
  const scope = JSON.stringify([ym, warehouses]);
  const valid = useRef({ scope, blocked, exportGuard, scopeError }); valid.current = { scope, blocked, exportGuard, scopeError };
  const reportWarehouses=useMemo(()=>exportIds===null?warehouses:exportIds.flatMap(id=>candidates.find(p=>p.id===id)?.warehouse_name??[]),[exportIds,warehouses,candidates]);
  const report = useQuery({ queryKey: ['mechanical-report', ym, reportWarehouses], enabled: !blocked && !scopeError && Boolean(ym) && reportWarehouses.length > 0, queryFn: async ({ signal }) => readMechanicalReport(await requestJson(`/api/m06/workbench/preview?${new URLSearchParams({ ym, projects: JSON.stringify(reportWarehouses) })}`, { signal }), ym, reportWarehouses) });
  useEffect(() => { setSheet(null); setExportIds(null); setTarget(''); setMessage(''); download.current?.abort(); download.current = null; setBusy(false); }, [scope, blocked, exportGuard, scopeError]);
  useEffect(() => {download.current?.abort();download.current=null;setBusy(false);},[exportIds]);
  useEffect(() => () => { download.current?.abort(); }, []);
  const unavailable = !me ? '登录后可下载。' : exportGuard || scopeError || (projects.isFetching || state.isFetching ? '正在核对项目和月份，请稍候。' : blocked ? '账号待核实，请稍候。' : report.isFetching || !report.data || report.isError ? '请先取得完整预览。' : '');
  async function save() {
    if (unavailable || busy || download.current || !report.data) return;
    const controller = new AbortController(); download.current = controller; setBusy(true); setMessage('');
    try {
      const result = await requestFile(`/api/m06/workbench/export?${new URLSearchParams({ ym, projects: JSON.stringify(reportWarehouses), snapshot_token: report.data.snapshot_token })}`, controller.signal);
      if (controller.signal.aborted || valid.current.scope !== scope || valid.current.blocked || valid.current.exportGuard || valid.current.scopeError) return;
      const url = URL.createObjectURL(result.blob); const link = document.createElement('a'); link.href = url; link.download = result.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setMessage('四页文件已导出。');
    } catch (error) { if (!controller.signal.aborted && valid.current.scope === scope) setMessage(error instanceof Error ? error.message : '导出失败，请重新预览后重试。'); }
    finally { if (download.current === controller) { download.current = null; setBusy(false); } }
  }
  const [tab, setTab] = useState<'summary' | 'zero' | 'monthly' | 'work'>('summary');
  const [importOpen,setImportOpen] = useState(false);
  const [temporary, setTemporary] = useState(''); const [problemsOnly, setProblemsOnly] = useState(false);
  const drafts = useRef(new Map<string,Draft>()); const grids = useRef(new Map<string,GridApi<import('./mechanical-api').DetailRow>>());
  const [,render] = useState(0); const [writing,setWriting] = useState(false); const writeLock = useRef(false);
  const [needsRead,setNeedsRead] = useState(false);
  type Confirmation = { name: string; detail: Detail; effective: Effective; columns: string[] };
  const [confirmation,setConfirmation] = useState<Confirmation[] | null>(null);
  const [dialog,setDialog] = useState<'discard' | 'plate' | 'projects' | 'export' | null>(null); const [keywords,setKeywords] = useState('');
  const internalDrafts=useRef(new Map<string,{warehouse:string;ym:string;values:Record<string,string>}>());
  const [internalEpoch,setInternalEpoch]=useState(0);
  const [internalConfirmation,setInternalConfirmation]=useState<{warehouse:string;ym:string;values:Record<string,string>;effective:Effective}[]|null>(null);
  const writable = Boolean(me) && active && !blocked && !writing && !needsRead && Boolean(state.data) && !state.isError;
  const category: Category = tab === 'monthly' ? 'monthly' : 'zero';
  const editingWarehouses = temporary ? warehouses.filter(w => w === temporary) : warehouses;
  const label = (warehouse: string) => candidates.find(p => p.warehouse_name === warehouse)?.disp || warehouse;
  const current = useRef({month,ym,category,editingWarehouses,scope,blocked,active});current.current={month,ym,category,editingWarehouses,scope,blocked,active};
  const detail = useCallback((index: number, projectId: string) => {
    const warehouse = projects.data?.find(project => String(project.id) === projectId)?.warehouse_name;
    if (warehouse) { setSheet(null);setTab(index === 2 ? 'monthly' : 'zero');setTemporary(warehouse);setProblemsOnly(false); }
  },[projects.data]);
  useEffect(() => {setImportOpen(false);setTemporary('');setProblemsOnly(false);setConfirmation(null);setInternalConfirmation(null);setDialog(current=>current==='projects'?'projects':null);},[scope]);
  useEffect(()=>{if(!active){setImportOpen(false);setConfirmation(null);setInternalConfirmation(null);setDialog(null);}},[active]);
  function stopEditors() {grids.current.forEach(grid => {if(!grid.isDestroyed())grid.stopEditing();});}
  function edit(warehouse: string, rows: import('./mechanical-api').DetailRow[]) {
    if (!writable) return;
    const key=detailKey(warehouse,ym,category), previous=drafts.current.get(key);
    const saved=state.data?.details.find(d => detailKey(d.warehouse,d.ym,d.category)===key);
    drafts.current.set(key,{warehouse,ym,category,revision:previous?.revision ?? saved?.revision ?? 0,rows,version:(previous?.version ?? 0)+1});render(n=>n+1);
  }
  async function refresh() {
    try {await client.invalidateQueries({}, {throwOnError:true});setNeedsRead(false);if(needsRead)setMessage('已重新读取。');return true;}
    catch {setNeedsRead(true);setMessage('修改已保存，但重新读取失败。请重新读取后再办理，未保存输入保留。');return false;}
  }
  async function operate(action: () => Promise<void>) {
    if(!writable || writeLock.current)return;writeLock.current=true;setWriting(true);setMessage('');
    try{await action();}catch(error){setMessage(error instanceof Error ? error.message : '修改未完成，输入已保留，请核对后重试。');}
    finally{writeLock.current=false;setWriting(false);}
  }
  async function saveDetails(confirm: boolean) {
    stopEditors();
    const context={...current.current}, targets=[...drafts.current].filter(([,d]) => d.ym===context.ym && d.category===context.category && context.editingWarehouses.includes(d.warehouse));
    let count=0;
    try {
      for(const [key,draft] of targets){
        const saved=readDetail(await requestJson('/api/m06/workbench/details-save',{method:'POST',...body(structuredClone(draft))}));
        await client.cancelQueries({queryKey:['mechanical-state']});
        client.setQueriesData<Workbench>({queryKey:['mechanical-state']},old => old ? {...old,details:[...old.details.filter(d=>detailKey(d.warehouse,d.ym,d.category)!==key),saved]} : old);
        const latest=drafts.current.get(key);
        if(latest?.version===draft.version)drafts.current.delete(key);
        else if(latest)latest.revision=saved.revision;
        count++;render(n=>n+1);
      }
    }catch(error){await refresh();throw new Error(`${count ? '已保存 '+count+' 组，其余输入保留。' : ''}${error instanceof Error ? error.message : '保存失败，请核对后重试。'}`);}
    if(!await refresh())return;
    setMessage(count ? `明细已保存 ${count} 组，有效月值仍待确认。` : '当前范围没有待保存的修改。');
    if(!confirm || current.current.scope!==context.scope || !current.current.active)return;
    if([...drafts.current.values()].some(d=>d.ym===context.ym&&d.category===context.category&&context.editingWarehouses.includes(d.warehouse))){setMessage('明细已保存；继续输入的草稿保留，请先保存后再确认。');return;}
    const latest=readWorkbench(await requestJson('/api/m06/workbench?ym='+encodeURIComponent(context.ym)));
    if(current.current.scope!==context.scope||!current.current.active||current.current.blocked)return;
    const columns=context.category==='zero'?['mech_2','mech_4']:['mech_3','mech_5'];
    setConfirmation(context.editingWarehouses.flatMap(warehouse=>{
      const detail=latest.details.find(d=>d.warehouse===warehouse&&d.ym===context.ym&&d.category===context.category),effective=latest.effective.find(d=>d.warehouse===warehouse&&d.ym===context.ym);
      if(!detail||!effective)return [];
      return [{name:label(warehouse),detail,effective,columns:columns.filter(column=>detail.rows.length&&!detail.blocked_columns[column]?.length&&(effective.values[column]===null||effective.sources[column]?.mode==='detail'))}];
    }));
  }
  async function confirmAmounts(){
    if(!confirmation?.some(item=>item.columns.length)){setMessage('请勾选需要采用的金额。');return;}
    let count=0;
    try{for(const item of confirmation){if(!item.columns.length)continue;await requestJson('/api/m06/workbench/amounts-confirm',{method:'POST',...body({warehouse:item.detail.warehouse,ym:item.detail.ym,category:item.detail.category,revision:item.detail.revision,effective_signature:item.effective.signature,columns:item.columns})});count++;}}
    catch(error){setConfirmation(null);await refresh();throw new Error(`${count ? '已确认 '+count+' 组。' : ''}${error instanceof Error ? error.message : '确认失败，请重新核对。'}`);}
    setConfirmation(null);if(await refresh())setMessage('已确认勾选金额的有效月值。');
  }
  const dirty=[...drafts.current.values()].filter(d=>d.ym===ym&&d.category===category&&editingWarehouses.includes(d.warehouse)).length;
  const internalTargets=[...internalDrafts.current.values()].filter(d=>d.ym===ym&&warehouses.includes(d.warehouse));
  const internal:InternalEditing={epoch:internalEpoch,writable,value:(id,column)=>internalDrafts.current.get(JSON.stringify([id,ym]))?.values[column],change:(id,column,value)=>{const key=JSON.stringify([id,ym]),warehouse=candidates.find(p=>String(p.id)===id)?.warehouse_name;if(!warehouse)return;const old=internalDrafts.current.get(key);internalDrafts.current.set(key,{warehouse,ym,values:{...old?.values,[column]:value}});render(n=>n+1);}};
  function openPicker(kind:'projects'|'export'){stopEditors();setTemporary('');const order=[...selected,...candidates.map(p=>p.id).filter(id=>!selected.includes(id))];setPickerOrder(order);setPickerIds([...selected]);setDialog(kind);}
  function previewButtonControl(){return <Button ref={previewButton} disabled={blocked||writing||projects.isPending||state.isPending||Boolean(scopeError)} onClick={()=>openPicker('export')}>导出预览</Button>;}
  useHistoryGuard('mechanical', () => writing ? '机械费正在保存，请稍候。' : needsRead ? '机械费操作结果待核实，请返回重新读取。' : drafts.current.size || internalDrafts.current.size ? '请先保存或撤销机械费未保存修改。' : '');
  const error = projects.error || state.error || report.error;
  return <section className="mechanical-card" aria-labelledby="page-title"><div data-page-chrome className="mechanical-toolbar">
    <div className="mechanical-month"><span>月份</span><TimePicker label="月份" modes={['月']} value={ym} disabled={blocked||writing} onChange={value=>{stopEditors();setMonth(value);}} /></div>
    <div className="mechanical-tabs" role="group" aria-label="机械费报表">{([['summary','表1 公司汇总'],['zero','表2 零租明细'],['monthly','表3 包月明细'],['work','核对工作台']] as const).map(([id,name])=><Button key={id} disabled={writing} aria-pressed={tab===id&&sheet===null} onClick={()=>{stopEditors();setTab(id);setSheet(null);setExportIds(null);setTemporary('');setProblemsOnly(false);}}>{name}</Button>)}</div>
    <div className="mechanical-preview-entry"><Button disabled={blocked||writing||state.isFetching} onClick={()=>openPicker('projects')}>显示项目</Button><Button disabled={!writable||state.isFetching} onClick={()=>{stopEditors();setImportOpen(true);}}>录入预览</Button></div>
    </div>
    {tab==='summary'&&sheet===null&&<div data-page-chrome className="mechanical-summary-tools"><strong>公司汇总</strong><span className="muted">金额单位：元</span><div className="mechanical-project-tools"><Button disabled={!writable||!internalTargets.length} onClick={()=>setInternalConfirmation(internalTargets.map(d=>({...structuredClone(d),effective:state.data!.effective.find(e=>e.warehouse===d.warehouse&&e.ym===d.ym)!})).filter(d=>d.effective))}>确认内租（{internalTargets.length}项）</Button><Button disabled={!writable||!internalTargets.length} onClick={()=>{for(const [key,d] of internalDrafts.current)if(d.ym===ym&&warehouses.includes(d.warehouse))internalDrafts.current.delete(key);setInternalEpoch(n=>n+1);render(n=>n+1);}}>取消内租修改</Button>{previewButtonControl()}</div></div>}
    {needsRead && <p className="notice" role="alert">保存后需要重新读取。<Button onClick={()=>void refresh()}>重新读取</Button></p>}
    {sheet===null && (tab==='zero'||tab==='monthly') && <>
      <div className="mechanical-edit-tools"><strong>{category==='zero'?'零租设备月报':'包月外租设备月报'}</strong>{temporary&&<><span>临时筛选：{label(temporary)}</span><Button onClick={()=>{stopEditors();setTemporary('');}}>取消筛选</Button></>}<label><Checkbox checked={problemsOnly} onChange={e=>{stopEditors();setProblemsOnly(e.target.checked);}} >仅看待补字段</Checkbox></label><span className="mechanical-tools-spacer" /><Button disabled={!writable||writing||state.isFetching} onClick={()=>{setKeywords((state.data?.settings.plate_keywords??[]).join('\n'));setDialog('plate');}}>车牌规则</Button><Button danger disabled={!dirty||writing||!writable} onClick={()=>setDialog('discard')}>撤销未保存修改</Button><Button disabled={!writable||writing||!dirty} onClick={()=>void operate(()=>saveDetails(false))}>仅保存明细</Button><Button type="primary" disabled={!writable||writing||!editingWarehouses.length||state.isFetching||state.isError} onClick={()=>void operate(()=>saveDetails(true))}>保存并确认汇总</Button>{previewButtonControl()}</div>
      {!state.isError && !state.isPending && <DetailsTable scale={Number(me?.ui_scale_css)||1} groups={editingWarehouses.map(warehouse=>{const key=detailKey(warehouse,ym,category);return {warehouse,name:label(warehouse),saved:state.data?.details.find(d=>detailKey(d.warehouse,d.ym,d.category)===key),draft:drafts.current.get(key)};})} ym={ym} category={category} keywords={state.data?.settings.plate_keywords??[]} problemsOnly={problemsOnly} writable={writable} change={edit} />}

    </>}
    {sheet===null&&tab==='work'&&state.data&&!state.isError&&<MechanicalWork data={state.data} warehouses={warehouses} label={label} writable={writable} busy={writing} operate={operate} refresh={refresh} added={warehouse=>{const project=candidates.find(p=>p.warehouse_name===warehouse);if(project&&!selected.includes(project.id))setIds([...selected,project.id]);}} />}
    {scopeError && !error && <p className="notice" role="alert">{scopeError}</p>}
    {error && !needsRead ? <p className="notice" role="alert">{error.message}<Button onClick={() => { void projects.refetch(); void state.refetch(); void report.refetch(); }}>重新读取</Button></p> : state.isPending || projects.isPending || report.isFetching && !report.data ? <p className="state" role="status">正在读取机械报表…</p> : !ym ? <p className="state" role="status">暂无已保存月份，请在现有工作区保存后再查看。</p> : !warehouses.length ? <p className="state" role="status">请选择项目查看报表。</p> : null}
    {report.data && !scopeError && !report.isError && (sheet===null?warehouses.length:reportWarehouses.length) > 0 && <>
      {sheet === null ? tab==='summary' ? <Summary active={active} scale={Number(me?.ui_scale_css) || 1} key={ym} report={report.data} projectIds={selected} detail={detail} internal={internal} data={state.data!} warehouses={warehouses} /> : null : <>
        <div className="mechanical-preview-tools"><strong>报送导出预览，{ym}</strong><Button onClick={() => { setSheet(null); setExportIds(null); setTarget(''); setTemporary(''); requestAnimationFrame(() => previewButton.current?.focus()); }}>返回查看／编辑</Button><Button disabled={blocked || busy || report.isFetching} onClick={() => { setMessage(''); void report.refetch(); }}>重新预览</Button><Button type="primary" disabled={Boolean(unavailable) || busy} title={unavailable || '下载当前预览的四页文件'} onClick={() => void save()}>{busy ? '正在生成…' : '下载四页Excel'}</Button></div>
        {unavailable && <p className="mechanical-feedback" role="status">{unavailable}</p>}
        <div className="mechanical-continuous-preview">{report.data.sheets.map((item,index)=><Sheet key={item.name} sheet={item} index={index} target={target} />)}</div>
      </>}
    </>}
    {importOpen&&<MechanicalImport writable={writable} keywords={state.data?.settings.plate_keywords??[]} label={label} close={()=>setImportOpen(false)} refresh={refresh} busyChanged={setWriting} draftConflict={batches=>batches.some(b=>drafts.current.has(detailKey(b.warehouse,b.ym,b.category)))} view={batch=>{const project=candidates.find(p=>p.warehouse_name===batch.warehouse);if(project&&!selected.includes(project.id))setIds([...selected,project.id]);setMonth(batch.ym);setTab(batch.category);setSheet(null);setProblemsOnly(false);setImportOpen(false);}} />}
    {(dialog==='projects'||dialog==='export')&&<MechanicalDialog className="mechanical-project-dialog" title={dialog==='projects'?'选择显示项目及顺序':'选择本次报送项目'} close={()=>setDialog(null)} busy={writing}>
      <p>{dialog==='projects'?'按勾选项目显示，顺序可调整；其他项目的数据保留。':'本次选择只用于导出预览。'}</p><div className="mechanical-project-tools"><Button disabled={writing} onClick={()=>setPickerIds([...pickerOrder])}>全选</Button><Button disabled={writing} onClick={()=>setPickerIds([])}>全不选</Button><span>已选 {pickerIds.length} 个项目</span></div>
      <ol className="mechanical-picker-list">{pickerOrder.map((id,index)=><li key={id}><Checkbox disabled={writing} checked={pickerIds.includes(id)} onChange={e=>setPickerIds(previous=>e.target.checked?[...previous,id]:previous.filter(p=>p!==id))}>{candidates.find(p=>p.id===id)?.disp}</Checkbox>{dialog==='projects'&&<span>{([-1,1] as const).map(step=><Button key={step} disabled={writing||index+step<0||index+step>=pickerOrder.length} onClick={()=>{const next=[...pickerOrder];[next[index+step],next[index]]=[next[index]!,next[index+step]!];setPickerOrder(next);}}>{step===-1?'上移':'下移'}</Button>)}</span>}</li>)}</ol>
      <footer><Button disabled={writing} onClick={()=>setDialog(null)}>取消</Button><Button type="primary" disabled={dialog==='projects'?!writable:blocked||writing||!pickerIds.length} onClick={()=>{const next=pickerOrder.filter(id=>pickerIds.includes(id));if(dialog==='export'){setExportIds(next);setTemporary('');setSheet(0);setTarget('');setDialog(null);}else void operate(async()=>{await requestJson('/api/m06/workbench/settings',{method:'POST',...body({revision:state.data?.settings.revision,shown_projects:next.flatMap(id=>candidates.find(p=>p.id===id)?.warehouse_name??[])})});setIds(next);setTemporary('');setDialog(null);if(await refresh())setMessage('显示项目及顺序已保存。');});}}>{dialog==='projects'?'应用项目选择':'生成报送预览'}</Button></footer>
    </MechanicalDialog>}

    {internalConfirmation&&<MechanicalDialog title="确认内租填数" close={()=>setInternalConfirmation(null)} busy={writing}><table><thead><tr><th>项目／月份</th><th>类别</th><th>原有效值</th><th>拟采用值</th></tr></thead><tbody>{internalConfirmation.flatMap(d=>Object.entries(d.values).map(([column,value])=><tr key={d.warehouse+d.ym+column}><td>{label(d.warehouse)}／{d.ym}</td><td>{column==='mech_0'?'工程公司内租':'租赁公司内租'}</td><td className="money">{money(d.effective.values[column])}</td><td className="money">{money(value)}{Number(value)<Number(d.effective.values[column])?'，金额减少，请核实':''}</td></tr>))}</tbody></table><footer><Button disabled={writing} onClick={()=>setInternalConfirmation(null)}>返回修改</Button><Button type="primary" disabled={!writable||writing} onClick={()=>void operate(async()=>{if(internalConfirmation.some(d=>Object.values(d.values).some(value=>!/^\d+(?:\.\d{1,2})?$/.test(value.trim()))))throw new Error('内租须填写非负金额，最多两位小数。');let count=0;try{for(const d of internalConfirmation){await requestJson('/api/m06/workbench/internal-save',{method:'POST',...body({...d,effective_signature:d.effective.signature})});for(const [key,current] of internalDrafts.current)if(current.warehouse===d.warehouse&&current.ym===d.ym&&JSON.stringify(current.values)===JSON.stringify(d.values))internalDrafts.current.delete(key);count++;}}catch(error){setInternalConfirmation(null);await refresh();throw new Error(`已更新 ${count} 组，其余输入保留。${error instanceof Error?error.message:'请重新核对。'}`);}setInternalConfirmation(null);setInternalEpoch(n=>n+1);if(await refresh())setMessage('内租有效月值已确认。');})}>确认更新内租</Button></footer></MechanicalDialog>}
    {confirmation && <MechanicalDialog title="确认有效月值" close={()=>setConfirmation(null)} busy={writing}>
      <p>含税、不含税分别勾选；原人工采用额默认保留。确认后，该格在过程资料中只读。</p><table><thead><tr><th>项目／月份</th><th>金额</th><th>原有效值</th><th>明细汇总</th><th>采用明细</th><th>状态</th></tr></thead><tbody>{confirmation.flatMap((item,index)=>(item.detail.category==='zero'?['mech_2','mech_4']:['mech_3','mech_5']).map((column,offset)=>{
        const total=item.detail.totals[offset?'net':'gross'],old=item.effective.values[column],blocked=!item.detail.rows.length||Boolean(item.detail.blocked_columns[column]?.length),manual=old!=null&&item.effective.sources[column]?.mode!=='detail';
        return <tr key={index+column}><td>{item.name}／{item.detail.ym}</td><td>{offset?'不含税':'含税'}</td><td className="money">{money(old)}</td><td className="money">{money(total)}</td><td><Checkbox aria-label={`采用${item.name}${offset?'不含税':'含税'}明细金额`} disabled={blocked||writing||!writable} checked={item.columns.includes(column)} onChange={e=>setConfirmation(previous=>previous?.map((entry,i)=>i===index?{...entry,columns:e.target.checked?[...entry.columns,column]:entry.columns.filter(c=>c!==column)}:entry)??null)} /></td><td>{blocked?'缺明细或字段待补，保留原值':manual?'人工采用值，勾选后替换':'可确认'}{!blocked&&old!=null&&total!=null&&Number(total)<Number(old)?'，金额减少，请核实':''}</td></tr>;
      }))}</tbody></table><footer><Button disabled={writing} onClick={()=>setConfirmation(null)}>返回</Button><Button type="primary" disabled={writing||!writable} onClick={()=>void operate(confirmAmounts)}>确认勾选金额</Button></footer>
    </MechanicalDialog>}
    {dialog==='discard'&&<MechanicalDialog className="mechanical-discard-dialog" title="撤销未保存修改" close={()=>setDialog(null)} busy={writing}><p>撤销当前范围 {dirty} 个项目的未保存修改，恢复最近已保存明细。</p><footer><Button onClick={()=>setDialog(null)}>保留修改</Button><Button danger onClick={()=>{for(const [key,d] of drafts.current)if(d.ym===ym&&d.category===category&&editingWarehouses.includes(d.warehouse))drafts.current.delete(key);render(n=>n+1);setDialog(null);}}>确认撤销</Button></footer></MechanicalDialog>}
    {dialog==='plate'&&<MechanicalDialog className="mechanical-plate-dialog" title="无需车牌设备关键词" close={()=>setDialog(null)} busy={writing}><label>每行一个关键词<Input.TextArea aria-label="无需车牌设备关键词" value={keywords} disabled={writing} onChange={e=>setKeywords(e.target.value)} /></label><footer><Button disabled={writing} onClick={()=>setDialog(null)}>取消</Button><Button type="primary" disabled={writing||!writable} onClick={()=>void operate(async()=>{await requestJson('/api/m06/workbench/settings',{method:'POST',...body({revision:state.data?.settings.revision,plate_keywords:keywords.split('\n')})});setDialog(null);if(await refresh())setMessage('车牌规则已保存。');})}>保存规则</Button></footer></MechanicalDialog>}
    {message && !needsRead && <p className="mechanical-feedback" role="status">{message}{(needsRead||report.isError) && <Button disabled={busy} onClick={() => void report.refetch()}>重新预览</Button>}</p>}
  </section>;
}
