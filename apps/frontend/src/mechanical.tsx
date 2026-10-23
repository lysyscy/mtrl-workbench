import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ColGroupDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { readProjects, requestFile, requestJson } from './api';
import type { Identity } from './api';
import { ProjectPicker } from './ledger-controls';
import { gridTheme } from './grid';
import { mechanicalMoney as money, readDetail, readMechanicalReport, readWorkbench } from './mechanical-api';
import { Details, MechanicalDialog, detailKey } from './mechanical-details';
import { MechanicalImport } from './mechanical-import';
import { TimePicker } from './time-picker';
import type { Draft } from './mechanical-details';
import { body } from './notices-api';
import type { Category, Detail, Effective, Workbench, MechanicalReport, ReportSheet } from './mechanical-api';

interface InternalEditing { epoch: number; writable: boolean; value: (id: string,column: string) => string | undefined; change: (id: string,column: string,value: string) => void }
function InternalCell({ id, column, value, label, editing, epoch }: { id: string; column: string; value: string; label: string; editing: React.RefObject<InternalEditing>; epoch: number }) {
  const [text,setText]=useState(()=>editing.current.value(id,column)??value);
  useEffect(()=>{setText(editing.current.value(id,column)??value);},[value,id,column,editing,epoch]);
  return <input aria-label={label} inputMode="decimal" className="mechanical-internal-input money" value={text} onChange={event=>{setText(event.target.value);editing.current.change(id,column,event.target.value);}} />;
}
interface SummaryRow { id: string; [column: string]: string }
const groupLabels = ['零租', '包月', '周材费', '租赁公司内租', '工程公司内租'];
function Summary({ report, projectIds, detail, internal }: { internal: InternalEditing; report: MechanicalReport; projectIds: number[]; detail: (sheet: number, projectId: string) => void }) {
  const api = useRef<GridApi<SummaryRow> | null>(null);
  const current=useRef(internal);current.current=internal;
  useEffect(()=>{api.current?.refreshCells({force:true});},[internal.epoch,internal.writable]);
  const [find, setFind] = useState(''); const [feedback, setFeedback] = useState('');
  const scale = Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1;
  const rows = useMemo(() => report.sheets[0]!.rows.slice(5).map((cells, index) => {
    const row: SummaryRow = { id: String(projectIds[index] ?? 'total') };
    for (const cell of cells) row[`c${cell.column - 1}`] = cell.value;
    return row;
  }), [report, projectIds]);
  const columns = useMemo<(ColDef<SummaryRow> | ColGroupDef<SummaryRow>)[]>(() => [
    { field: 'c0', headerName: '序号', pinned: 'left', width: 60 * scale },
    { field: 'c1', headerName: '项目', pinned: 'left', width: 210 * scale, wrapText: true, autoHeight: true },
    { headerName: '开工年月', children: [{ field: 'c2', headerName: '年', width: 75 * scale }, { field: 'c3', headerName: '月', width: 65 * scale, cellClass: 'mechanical-group-end', headerClass: 'mechanical-group-end' }] },
    ...['累计', '当月'].map((name, group) => ({ headerName: name, headerClass: 'mechanical-group-end', children: groupLabels.map((label, index): ColDef<SummaryRow> => ({
      field: `c${4 + group * 5 + index}`, headerName: label, width: (index > 2 ? 140 : 112) * scale, cellClass: index === 4 ? 'money mechanical-group-end' : 'money', headerClass: index === 4 ? 'mechanical-group-end' : '',
      ...(group===1&&index>2?{cellRenderer:(params:ICellRendererParams<SummaryRow,string>)=>params.node.rowPinned||!current.current.writable?params.value??'—':<InternalCell id={params.data!.id} column={index===3?'mech_1':'mech_0'} value={params.value??''} label={`${params.data?.c1} ${label}`} editing={current} epoch={current.current.epoch} />}:{}),
      ...(group === 1 && index < 2 ? { cellRenderer: (params: ICellRendererParams<SummaryRow, string>) => params.node.rowPinned || !params.value ? params.value ?? '' : <button className="mechanical-link" aria-label={`${params.data?.c1} ${label}明细`} onClick={() => detail(index + 1, params.data?.id ?? '')}>{params.value}</button> } : {}),
    })) })),
    { field: 'c14', headerName: '备注', width: 160 * scale, wrapText: true, autoHeight: true },
  ], [scale, detail]);
  function locate() {
    if (!find.trim()) return;
    const index = rows.slice(0, -1).findIndex(row => row.c1?.includes(find.trim()));
    if (index < 0) { setFeedback('没有匹配项目，请调整名称。'); return; }
    api.current?.ensureIndexVisible(index, 'middle'); api.current?.setFocusedCell(index, 'c1'); setFeedback('');
  }
  return <>
    <form className="mechanical-locate" onSubmit={event => { event.preventDefault(); locate(); }}><label>定位项目<input value={find} onChange={event => setFind(event.target.value)} onKeyDown={event => { if (event.nativeEvent.isComposing && event.key === 'Enter') event.preventDefault(); }} /></label><button type="submit">定位</button>{feedback && <span role="status">{feedback}</span>}</form>
    <div className="mechanical-grid" role="region" aria-label="公司汇总">
      <AgGridReact<SummaryRow> theme={gridTheme} rowData={rows.slice(0, -1)} pinnedBottomRowData={rows.slice(-1)} columnDefs={columns} defaultColDef={{ sortable: false, resizable: true, suppressMovable: true, wrapHeaderText: true, autoHeaderHeight: true }} getRowId={params => params.data.id} rowHeight={34 * scale} headerHeight={34 * scale} groupHeaderHeight={30 * scale} onGridReady={event => { api.current = event.api; }} />
    </div>
  </>;
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
  const [month, setMonth] = useState(''); const [ids, setIds] = useState<number[] | null>(null);
  const [sheet, setSheet] = useState<number | null>(null); const [target, setTarget] = useState('');
  const [message, setMessage] = useState(''); const [busy, setBusy] = useState(false);
  const download = useRef<AbortController | null>(null); const previewButton = useRef<HTMLButtonElement>(null);
  const projects = useQuery({ queryKey: ['projects', 'all', ''], enabled: !blocked, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const state = useQuery({ queryKey: ['mechanical-state',month], enabled: !blocked, queryFn: async ({ signal }) => readWorkbench(await requestJson('/api/m06/workbench?ym='+encodeURIComponent(month), { signal })) });
  const candidates = useMemo(() => projects.data?.filter(project => state.data?.warehouses.includes(project.warehouse_name ?? '')) ?? [], [projects.data, state.data]);
  const selected = useMemo(() => ids ?? (state.data?.shown.flatMap(warehouse => candidates.filter(project => project.warehouse_name === warehouse).map(project => project.id)) ?? []), [ids, state.data, candidates]);
  const warehouses = useMemo(() => selected.flatMap(id => candidates.find(project => project.id === id)?.warehouse_name ?? []), [selected, candidates]);
  const ym = month || state.data?.months.at(-1) || new Date(new Date().getFullYear(),new Date().getMonth()-1,15).toISOString().slice(0,7);
  useEffect(()=>{if(!month&&state.data)setMonth(ym);},[month,state.data,ym]);
  const scopeError = selected.length !== warehouses.length ? '所选项目范围已变化，请重新选择。' : projects.isError || state.isError ? '项目或月份读取失败，请先重新读取。' : '';
  const scope = JSON.stringify([ym, warehouses]);
  const valid = useRef({ scope, blocked, exportGuard, scopeError }); valid.current = { scope, blocked, exportGuard, scopeError };
  const report = useQuery({ queryKey: ['mechanical-report', ym, warehouses], enabled: !blocked && !scopeError && Boolean(ym) && warehouses.length > 0, queryFn: async ({ signal }) => readMechanicalReport(await requestJson(`/api/m06/workbench/preview?${new URLSearchParams({ ym, projects: JSON.stringify(warehouses) })}`, { signal }), ym, warehouses) });
  useEffect(() => { setSheet(null); setTarget(''); setMessage(''); download.current?.abort(); download.current = null; setBusy(false); }, [scope, blocked, exportGuard, scopeError]);
  useEffect(() => () => { download.current?.abort(); }, []);
  const unavailable = !me ? '登录后可下载。' : exportGuard || scopeError || (projects.isFetching || state.isFetching ? '正在核对项目和月份，请稍候。' : blocked ? '账号待核实，请稍候。' : report.isFetching || !report.data || report.isError ? '请先取得完整预览。' : '');
  async function save() {
    if (unavailable || busy || download.current || !report.data) return;
    const controller = new AbortController(); download.current = controller; setBusy(true); setMessage('');
    try {
      const result = await requestFile(`/api/m06/workbench/export?${new URLSearchParams({ ym, projects: JSON.stringify(warehouses), snapshot_token: report.data.snapshot_token })}`, controller.signal);
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
  const [dialog,setDialog] = useState<'discard' | 'plate' | 'projects' | null>(null); const [keywords,setKeywords] = useState('');
  const internalDrafts=useRef(new Map<string,{warehouse:string;ym:string;values:Record<string,string>}>());
  const [internalEpoch,setInternalEpoch]=useState(0);
  const [internalConfirmation,setInternalConfirmation]=useState<{warehouse:string;ym:string;values:Record<string,string>;effective:Effective}[]|null>(null);
  const history = useQuery({queryKey:['history',me?.account],enabled:!blocked && Boolean(me),queryFn:({signal}) => requestJson('/api/history/status',{signal})});
  const writable = Boolean(me) && !blocked && !needsRead && Boolean(state.data) && !state.isError;
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
  async function replay(direction:'undo'|'redo'){
    const status=await requestJson('/api/history/status');
    const item=typeof status==='object'&&status!==null ? (status as Record<string,unknown>)[direction] : null;
    if(!item||typeof item!=='object'||!('id' in item))return;
    await requestJson('/api/history/'+direction,{method:'POST',...body({operation_id:item.id})});
    if(await refresh())setMessage(direction==='undo'?'已撤销。':'已重做。');
  }
  const dirty=[...drafts.current.values()].filter(d=>d.ym===ym&&d.category===category&&editingWarehouses.includes(d.warehouse)).length;
  const historyData=typeof history.data==='object'&&history.data!==null ? history.data as Record<string,unknown> : {};
  const internalTargets=[...internalDrafts.current.values()].filter(d=>d.ym===ym&&warehouses.includes(d.warehouse));
  const internal:InternalEditing={epoch:internalEpoch,writable,value:(id,column)=>internalDrafts.current.get(JSON.stringify([id,ym]))?.values[column],change:(id,column,value)=>{const key=JSON.stringify([id,ym]),warehouse=candidates.find(p=>String(p.id)===id)?.warehouse_name;if(!warehouse)return;const old=internalDrafts.current.get(key);internalDrafts.current.set(key,{warehouse,ym,values:{...old?.values,[column]:value}});render(n=>n+1);}};
  const historyControls=<div className="ledger-tools">{(['undo','redo'] as const).map(direction=><button key={direction} disabled={!writable||writing||(drafts.current.size>0||internalDrafts.current.size>0)||!historyData[direction]} title={drafts.current.size||internalDrafts.current.size?'请先保存或撤销未保存修改':typeof historyData.notice==='string'&&historyData.notice?historyData.notice:direction==='undo'?'暂无可撤销的操作':'暂无可重做的操作'} onClick={()=>void operate(()=>replay(direction))}>{direction==='undo'?'撤销':'重做'}</button>)}</div>;
  const error = projects.error || state.error || report.error;
  return <section className="mechanical-card" aria-labelledby="page-title"><div className="mechanical-toolbar">
    {active && document.getElementById('history-controls') && createPortal(historyControls,document.getElementById('history-controls')!)}
    <div className="mechanical-tabs" role="group" aria-label="机械费报表">{([['summary','表1·公司汇总'],['zero','表2·零租明细'],['monthly','表3·包月明细'],['work','核对工作台']] as const).map(([id,name])=><button key={id} aria-pressed={tab===id&&sheet===null} onClick={()=>{stopEditors();setTab(id);setSheet(null);setTemporary('');setProblemsOnly(false);}}>{name}</button>)}</div>
    <div className="mechanical-preview-entry"><button disabled={!writable||writing||state.isFetching} onClick={()=>{stopEditors();setImportOpen(true);}}>录入原报明细</button><button ref={previewButton} disabled={Boolean(scopeError) || !report.data || report.isFetching || report.isError} onClick={() => { stopEditors();setTemporary('');setSheet(0); setTarget(''); }}>四页报送预览</button></div>
    <div className="filters"><span>月份</span><TimePicker label="月份" modes={['月']} value={ym} disabled={blocked} onChange={value=>{stopEditors();setMonth(value);}} /><ProjectPicker projects={candidates} selected={selected} pick={value=>{stopEditors();setIds(value);}} multiple label="报表项目" disabled={blocked || projects.isPending || state.isPending} /></div>
    <div className="mechanical-project-tools"><button disabled={!writable||writing||state.isFetching} onClick={()=>setDialog('projects')}>保存显示项目及顺序</button>{tab==='summary'&&sheet===null&&<><button disabled={!writable||writing||!internalTargets.length} onClick={()=>{for(const [key,d] of internalDrafts.current)if(d.ym===ym&&warehouses.includes(d.warehouse))internalDrafts.current.delete(key);setInternalEpoch(n=>n+1);render(n=>n+1);}}>取消内租修改</button><button disabled={!writable||writing||!internalTargets.length} onClick={()=>setInternalConfirmation(internalTargets.map(d=>({...structuredClone(d),effective:state.data!.effective.find(e=>e.warehouse===d.warehouse&&e.ym===d.ym)!})).filter(d=>d.effective))}>确认内租（{internalTargets.length}项）</button></>}</div>
    </div>
    {needsRead && <p className="notice" role="alert">保存后需要重新读取。<button onClick={()=>void refresh()}>重新读取</button></p>}
    {sheet===null && (tab==='zero'||tab==='monthly') && <>
      <div className="mechanical-edit-tools">{temporary&&<><span>临时筛选：{label(temporary)}</span><button onClick={()=>{stopEditors();setTemporary('');}}>取消筛选</button></>}<label><input type="checkbox" checked={problemsOnly} onChange={e=>{stopEditors();setProblemsOnly(e.target.checked);}} />仅看待补字段</label><span>待保存 {dirty} 组</span><button disabled={!writable||writing||state.isFetching} onClick={()=>{setKeywords((state.data?.settings.plate_keywords??[]).join('\n'));setDialog('plate');}}>车牌规则</button><button disabled={!dirty||writing||!writable} onClick={()=>setDialog('discard')}>撤销未保存修改</button><button disabled={!writable||writing||!dirty} onClick={()=>void operate(()=>saveDetails(false))}>仅保存明细</button><button disabled={!writable||writing||!editingWarehouses.length||state.isFetching||state.isError} onClick={()=>void operate(()=>saveDetails(true))}>保存并确认汇总</button></div>
      {!state.isError && !state.isPending && editingWarehouses.map(warehouse=>{const key=detailKey(warehouse,ym,category);return <Details key={key} name={label(warehouse)} warehouse={warehouse} ym={ym} category={category} saved={state.data?.details.find(d=>detailKey(d.warehouse,d.ym,d.category)===key)} effective={state.data?.effective.find(d=>d.warehouse===warehouse&&d.ym===ym)} draft={drafts.current.get(key)} keywords={state.data?.settings.plate_keywords??[]} problemsOnly={problemsOnly} writable={writable} change={rows=>edit(warehouse,rows)} register={api=>{if(api)grids.current.set(key,api);else grids.current.delete(key);}} />;})}
    </>}
    {sheet===null&&tab==='work'&&<div className="mechanical-work-table"><table><thead><tr><th>项目</th><th>报表费用累计</th><th>班组使用累计（含i6）</th><th>待处理差额</th><th>班组使用累计</th><th>项目结算＋班组审批</th><th>待处理差额</th><th>明细</th></tr></thead><tbody>{warehouses.map(warehouse=>{const relations=state.data?.relations.filter(r=>r.warehouse===warehouse)??[];return <tr key={warehouse}><th>{label(warehouse)}</th>{['report','internal'].flatMap(relation=>['left','right','pending'].map(field=><td key={relation+field} className="money">{money(relations.find(r=>r.relation===relation)?.[field as 'left'|'right'|'pending'])}</td>))}<td>{(['zero','monthly'] as const).map(category=><button key={category} className="mechanical-link" onClick={()=>{setTab(category);setTemporary(warehouse);}}>{category==='zero'?'零租':'包月'}</button>)}</td></tr>;})}</tbody></table><p className="muted">取数采纳、差额处理与跟进事项待后续接入。</p></div>}
    {scopeError && !error && <p className="notice" role="alert">{scopeError}</p>}
    {error && !needsRead ? <p className="notice" role="alert">{error.message}<button onClick={() => { void projects.refetch(); void state.refetch(); void report.refetch(); }}>重新读取</button></p> : state.isPending || projects.isPending || report.isFetching ? <p className="state" role="status">正在读取机械报表…</p> : !ym ? <p className="state" role="status">暂无已保存月份，请在现有工作区保存后再查看。</p> : !warehouses.length ? <p className="state" role="status">请选择项目查看报表。</p> : null}
    {report.data && !scopeError && !report.isError && !report.isFetching && warehouses.length > 0 && <>
      {report.data.warnings.length > 0 && <details className="mechanical-warnings"><summary>报表待核对（{report.data.warnings.length}）</summary><ul>{report.data.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
      {sheet === null ? tab==='summary' ? <Summary key={ym} report={report.data} projectIds={selected} detail={detail} internal={internal} /> : null : <>
        <div className="mechanical-preview-tools"><button onClick={() => { setSheet(null); setTarget(''); setTemporary(''); requestAnimationFrame(() => previewButton.current?.focus()); }}>返回公司汇总</button><div role="group" aria-label="四页报表">{report.data.sheets.map((item, index) => <button key={item.name} aria-pressed={sheet === index} onClick={() => { setSheet(index); setTarget(''); }}>{item.name}</button>)}</div><button disabled={Boolean(unavailable) || busy} title={unavailable || '下载当前预览的四页文件'} onClick={() => void save()}>{busy ? '正在生成…' : '下载四页Excel'}</button></div>
        {unavailable && <p className="mechanical-feedback" role="status">{unavailable}</p>}
        <Sheet key={sheet} sheet={report.data.sheets[sheet]!} index={sheet} target={target} />
      </>}
    </>}
    {importOpen&&<MechanicalImport writable={writable} keywords={state.data?.settings.plate_keywords??[]} label={label} close={()=>setImportOpen(false)} refresh={refresh} busyChanged={setWriting} draftConflict={batches=>batches.some(b=>drafts.current.has(detailKey(b.warehouse,b.ym,b.category)))} view={batch=>{const project=candidates.find(p=>p.warehouse_name===batch.warehouse);if(project&&!selected.includes(project.id))setIds([...selected,project.id]);setMonth(batch.ym);setTab(batch.category);setSheet(null);setProblemsOnly(false);setImportOpen(false);}} />}
    {dialog==='projects'&&<MechanicalDialog title="显示项目及顺序" close={()=>setDialog(null)} busy={writing}><ol>{selected.map((id,index)=><li key={id}>{candidates.find(p=>p.id===id)?.disp}<button disabled={writing||index===0} onClick={()=>{const next=[...selected];[next[index-1],next[index]]=[next[index]!,next[index-1]!];setIds(next);}}>上移</button><button disabled={writing||index===selected.length-1} onClick={()=>{const next=[...selected];[next[index+1],next[index]]=[next[index]!,next[index+1]!];setIds(next);}}>下移</button></li>)}</ol><footer><button disabled={writing} onClick={()=>setDialog(null)}>返回</button><button disabled={!writable||writing} onClick={()=>void operate(async()=>{await requestJson('/api/m06/workbench/settings',{method:'POST',...body({revision:state.data?.settings.revision,shown_projects:warehouses})});setDialog(null);if(await refresh())setMessage('显示项目及顺序已保存。');})}>保存显示名单</button></footer></MechanicalDialog>}
    {internalConfirmation&&<MechanicalDialog title="确认内租填数" close={()=>setInternalConfirmation(null)} busy={writing}><table><thead><tr><th>项目／月份</th><th>类别</th><th>原有效值</th><th>拟采用值</th></tr></thead><tbody>{internalConfirmation.flatMap(d=>Object.entries(d.values).map(([column,value])=><tr key={d.warehouse+d.ym+column}><td>{label(d.warehouse)}／{d.ym}</td><td>{column==='mech_0'?'工程公司内租':'租赁公司内租'}</td><td>{money(d.effective.values[column])}</td><td>{money(value)}{Number(value)<Number(d.effective.values[column])?' · 金额减少，请核实':''}</td></tr>))}</tbody></table><footer><button disabled={writing} onClick={()=>setInternalConfirmation(null)}>返回修改</button><button disabled={!writable||writing} onClick={()=>void operate(async()=>{if(internalConfirmation.some(d=>Object.values(d.values).some(value=>!/^\d+(?:\.\d{1,2})?$/.test(value.trim()))))throw new Error('内租须填写非负金额，最多两位小数。');let count=0;try{for(const d of internalConfirmation){await requestJson('/api/m06/workbench/internal-save',{method:'POST',...body({...d,effective_signature:d.effective.signature})});for(const [key,current] of internalDrafts.current)if(current.warehouse===d.warehouse&&current.ym===d.ym&&JSON.stringify(current.values)===JSON.stringify(d.values))internalDrafts.current.delete(key);count++;}}catch(error){setInternalConfirmation(null);await refresh();throw new Error(`已更新 ${count} 组，其余输入保留。${error instanceof Error?error.message:'请重新核对。'}`);}setInternalConfirmation(null);setInternalEpoch(n=>n+1);if(await refresh())setMessage('内租有效月值已确认。');})}>确认更新内租</button></footer></MechanicalDialog>}
    {confirmation && <MechanicalDialog title="确认有效月值" close={()=>setConfirmation(null)} busy={writing}>
      <p>含税、不含税分别勾选；原人工采用额默认保留。确认后，该格在过程资料中只读。</p><table><thead><tr><th>项目／月份</th><th>金额</th><th>原有效值</th><th>明细汇总</th><th>采用明细</th><th>状态</th></tr></thead><tbody>{confirmation.flatMap((item,index)=>(item.detail.category==='zero'?['mech_2','mech_4']:['mech_3','mech_5']).map((column,offset)=>{
        const total=item.detail.totals[offset?'net':'gross'],old=item.effective.values[column],blocked=!item.detail.rows.length||Boolean(item.detail.blocked_columns[column]?.length),manual=old!=null&&item.effective.sources[column]?.mode!=='detail';
        return <tr key={index+column}><td>{item.name}／{item.detail.ym}</td><td>{offset?'不含税':'含税'}</td><td className="money">{money(old)}</td><td className="money">{money(total)}</td><td><input type="checkbox" aria-label={`采用${item.name}${offset?'不含税':'含税'}明细金额`} disabled={blocked||writing||!writable} checked={item.columns.includes(column)} onChange={e=>setConfirmation(previous=>previous?.map((entry,i)=>i===index?{...entry,columns:e.target.checked?[...entry.columns,column]:entry.columns.filter(c=>c!==column)}:entry)??null)} /></td><td>{blocked?'缺明细或字段待补，保留原值':manual?'人工采用值，勾选后替换':'可确认'}{!blocked&&old!=null&&total!=null&&Number(total)<Number(old)?' · 金额减少，请核实':''}</td></tr>;
      }))}</tbody></table><footer><button disabled={writing} onClick={()=>setConfirmation(null)}>返回</button><button disabled={writing||!writable} onClick={()=>void operate(confirmAmounts)}>确认勾选金额</button></footer>
    </MechanicalDialog>}
    {dialog==='discard'&&<MechanicalDialog title="撤销未保存修改" close={()=>setDialog(null)} busy={writing}><p>撤销当前范围 {dirty} 个项目的未保存修改，恢复最近已保存明细。</p><footer><button onClick={()=>setDialog(null)}>保留修改</button><button onClick={()=>{for(const [key,d] of drafts.current)if(d.ym===ym&&d.category===category&&editingWarehouses.includes(d.warehouse))drafts.current.delete(key);render(n=>n+1);setDialog(null);}}>确认撤销</button></footer></MechanicalDialog>}
    {dialog==='plate'&&<MechanicalDialog title="无需车牌设备关键词" close={()=>setDialog(null)} busy={writing}><label>每行一个关键词<textarea aria-label="无需车牌设备关键词" value={keywords} disabled={writing} onChange={e=>setKeywords(e.target.value)} /></label><footer><button disabled={writing} onClick={()=>setDialog(null)}>取消</button><button disabled={writing||!writable} onClick={()=>void operate(async()=>{await requestJson('/api/m06/workbench/settings',{method:'POST',...body({revision:state.data?.settings.revision,plate_keywords:keywords.split('\n')})});setDialog(null);if(await refresh())setMessage('车牌规则已保存。');})}>保存规则</button></footer></MechanicalDialog>}
    {message && !needsRead && <p className="mechanical-feedback" role="status">{message}{(needsRead||report.isError) && <button disabled={busy} onClick={() => void report.refetch()}>重新预览</button>}</p>}
  </section>;
}
