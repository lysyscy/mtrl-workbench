import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { readProjects, requestJson } from './api';
import type { Identity } from './api';
import { ProjectPicker, reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { pageGridGeometry, contentWidth, fitGridColumns, fixedWidth, gridTheme, numberColumnWidth } from './grid';
import { cents, money } from './notices-api';
import { coarseRows, emptyFilter, fields, filterOn, filterRows, getInventory, sumRows } from './inventory-api';
import type { Field, Filters, InventoryRow } from './inventory-api';
import { InventoryAdjust } from './inventory-adjust';
import { InventoryFetch } from './inventory-fetch';
import { SettlementExport } from './settlement-export';
import { useHistoryGuard } from './history';
import './settlement.css';
import './inventory.css';
import { InventoryText, measureInventoryRows } from './inventory-rows';

const defaultColumn: ColDef<InventoryRow> = {resizable:true,suppressMovable:true};
const totalsOf = (rows: InventoryRow[]) => rows.length ? [{id:-1,doc_no:'合计',qty:sumRows(rows,'qty'),amount:sumRows(rows,'amount'),adj_amount:sumRows(rows,'adj_amount'),tax_total:sumRows(rows,'tax_total')}] : [];

export function InventoryPage({me,blocked,active}:{me:Identity|null;blocked:boolean;active:boolean}) {
  const location = useLocation(), navigate = useNavigate();
  const rawTarget = active ? new URLSearchParams(location.search).get('row') : null;
  const target = rawTarget && /^\d+$/.test(rawTarget) && Number.isSafeInteger(Number(rawTarget)) && Number(rawTarget) > 0 ? Number(rawTarget) : null;
  function clearLocation() { const params = new URLSearchParams(location.search); params.delete('row'); void navigate({ pathname: location.pathname, search: params.toString() }, { replace: true }); }
  const client = useQueryClient(), root = useRef<HTMLDivElement>(null);
  const [period,setPeriod] = useState(reportMonth), [ids,setIds] = useState<number[]>([]), [direction,setDirection] = useState('全部'), [onlyAdjusted,setOnlyAdjusted] = useState(false);
  const [filters,setFilters] = useState<Filters>({}), [column,setColumn] = useState<Field>('material'), [filterOpen,setFilterOpen] = useState(false);
  const [editing,setEditing] = useState<InventoryRow|null>(null), [fetchMonth,setFetchMonth] = useState<string|null>(null);
  const [pending,setPending] = useState<InventoryRow|null>(null);
  const pendingKey = `inventory-fetch-pending:${me?.account ?? ''}`;
  const [fetchPending,setFetchPending] = useState<string|null>(() => {try {return sessionStorage.getItem(pendingKey);} catch {return null;}});
  const [storageError,setStorageError] = useState('');
  useHistoryGuard('inventory-pending',() => pending ? '库存调整正在处理或结果待核实，请先重读核对。' : fetchPending ? '库存抓取正在处理或结果待核实，请先核对执行记录。' : '');
  function updateFetchPending(month:string|null) {
    setFetchPending(month);
    try {if (month) sessionStorage.setItem(pendingKey,month);else sessionStorage.removeItem(pendingKey);setStorageError('');}
    catch {setStorageError('本机未能记住抓取状态；刷新或重开浏览器后请先到 i8 执行记录核对，勿重复抓取。');}
  }
  const query = useQuery({queryKey:['inventory'],enabled:active && !blocked,queryFn:({signal}) => getInventory(signal)});
  const projects = useQuery({queryKey:['projects'],enabled:active && !blocked,queryFn:async({signal}) => readProjects(await requestJson('/api/m01/projects',{signal}))});
  const warehouses = ids.map(id => projects.data?.find(p => p.id === id)?.warehouse_name ?? '__unavailable__');
  const coarse = useMemo(() => coarseRows(query.data?.rows ?? [],period,warehouses,direction,onlyAdjusted),[query.data,period,warehouses.join('\0'),direction,onlyAdjusted]);
  const rows = useMemo(() => target !== null ? (query.data?.rows ?? []).filter(row => row.id === target) : filterRows(coarse,filters),[coarse,filters,target,query.data]);
  const filter = filters[column] ?? emptyFilter(), meta = fields.find(([key]) => key === column)!;
  const values = useMemo(() => filterOpen ? [...new Set(coarse.map(row => row[column]).filter(Boolean))].sort() : [], [coarse, column, filterOpen]);
  const filterCount = Object.values(filters).filter(filterOn).length;
  const scale = Number(me?.ui_scale_css ?? 1), paused = blocked || !active;
  async function reload() {
    await client.cancelQueries({queryKey:['inventory']});
    const data = await client.fetchQuery({queryKey:['inventory'],staleTime:0,queryFn:({signal}) => getInventory(signal)});
    await client.invalidateQueries({predicate:q => q.queryKey[0] !== 'inventory'},{throwOnError:true});
    return data;
  }
  const grid = useRef<GridApi<InventoryRow> | null>(null);
  useLayoutEffect(() => { if (active) measureInventoryRows(grid.current, root.current); }, [active, rows, scale]);
  useEffect(() => {
    const loaded = () => measureInventoryRows(grid.current, root.current);
    document.fonts.addEventListener('loadingdone', loaded);
    return () => document.fonts.removeEventListener('loadingdone', loaded);
  }, []);
  const controls = useRef({ unavailable: false, pendingId: null as number | null });
  controls.current = { unavailable: paused || query.isError || query.isFetching, pendingId: pending?.id ?? null };
  useEffect(() => { if (active) grid.current?.refreshCells({ force: true, columns: ['actions'] }); }, [active, paused, query.isError, query.isFetching, pending]);
  const coarseTotals = useMemo(() => totalsOf(coarse), [coarse]);
  const totals = useMemo(() => rows === coarse ? coarseTotals : totalsOf(rows), [rows, coarse, coarseTotals]);
  const columns = useMemo<ColDef<InventoryRow>[]>(() => [
    ...fields.map(([field,headerName,type]):ColDef<InventoryRow> => ({field,headerName,sortable:true,wrapText:type !== 'num',cellRenderer:type === 'num' ? undefined : InventoryText,
      ...(type === 'num' ? {cellClass:'money',valueFormatter:(p:{value:unknown}) => p.value === '' || p.value == null ? '' : money(String(p.value)),comparator:(a:string,b:string) => !a || !b ? a ? 1 : b ? -1 : 0 : cents(a) < cents(b) ? -1 : cents(a) > cents(b) ? 1 : 0} : {}),
      ...(field === 'doc_no' ? {pinned:'left' as const} : {}),
      ...(type === 'num' ? numberColumnWidth([...rows.map(row => money(row[field])), ...totals.map(row => money((row as Partial<InventoryRow>)[field] ?? ''))], scale) : contentWidth(field === 'doc_no' ? 108 : ['seq','unit','direction'].includes(field) ? 40 : ['doc_date','audit_date'].includes(field) ? 70 : field === 'biz_type' ? 64 : ['spec','wbs_name','cbs_name'].includes(field) ? 72 : 92,['seq','unit','direction'].includes(field) ? 85 : 300,scale,field === 'material' ? 1 : 0)),
    })),
    {colId:'actions',headerName:'调整单',pinned:'right',sortable:false,...fixedWidth(100,scale),cellRenderer:(p:ICellRendererParams<InventoryRow>) => p.data && !p.node.rowPinned && <Button size="small" disabled={controls.current.unavailable || Boolean(controls.current.pendingId !== null && controls.current.pendingId !== p.data.id)} onClick={() => { if (!controls.current.unavailable && (controls.current.pendingId === null || controls.current.pendingId === p.data!.id)) setEditing(p.data!); }}>{p.data.adjusted ? '查看 / 调整' : '办理调整'}</Button>},
  ],[scale, rows, totals]);
  function changeFilter(key:'q'|'min'|'max'|'values',value:string|string[]) {setFilters(old => ({...old,[column]:{...filter,[key]:value}}));}
  const filterProblem = [filter.min,filter.max].some(raw => raw && !Number.isFinite(Number(raw.replace(/,/g,'')))) ? '列数值无效，请修改或清除此列。' : '';
  const editRow = editing && (query.data?.rows.find(r => r.id === editing.id) ?? editing);
  const editMissing = Boolean(editing && query.data && !query.data.rows.some(r => r.id === editing.id));
  return <section className="inventory-page" aria-label="库存单据与调整单">
    <div className="inventory-toolbar"><div><label>核算期间<TimePicker singleEntry label="库存核算期间" value={period} modes={['月','跨月','年','全部']} onChange={setPeriod} disabled={paused} /></label>
      <ProjectPicker label="库存项目" projects={(projects.data ?? []).filter(p => query.data?.projects.includes(p.warehouse_name ?? ''))} selected={ids} pick={setIds} multiple emptyLabel="全部项目" disabled={paused || projects.isPending || projects.isError} />
      <label>方向<Select aria-label="库存方向" value={direction} onChange={setDirection} options={['全部','入库','出库'].map(value => ({value,label:value}))} disabled={paused} /></label>
      <Checkbox checked={onlyAdjusted} disabled={paused} onChange={e => setOnlyAdjusted(e.target.checked)}>只看被调整行</Checkbox></div>
      <div><Button disabled={paused} onClick={() => setFilterOpen(!filterOpen)}>列筛选{filterCount ? `，${filterCount} 列` : ''}</Button><Button disabled={paused || !me || Boolean(pending)} onClick={() => setFetchMonth(fetchPending ?? (/^\d{4}-\d{2}$/.test(period) ? period : reportMonth()))}>{fetchPending ? '核对抓取…' : '按月抓取…'}</Button>
      {!/^\d{4}-\d{2}$/.test(period) && <span>导出请选择单月</span>}<SettlementExport url={`/api/m08/inventory/export?${new URLSearchParams({period})}`} scope={`${period} 库存（含数据透视表）`} paused={paused} disabled={query.isPending || query.isError || !/^\d{4}-\d{2}$/.test(period)}>
        <p>按核算期间导出全部项目；不受本页项目、方向和列筛选限制。</p><p>读取最近抓取的源文件，不叠加调整单。包含原单明细、过程资料透视、安全文明施工费透视；没有缓存时请先抓取。</p>
      </SettlementExport></div>
    </div>
    {rawTarget !== null && <p className="inventory-location" role="status">{target === null ? '定位参数无效。' : query.data ? rows.length ? `已定位 ${rows[0]!.doc_no} #${rows[0]!.seq}` : '原行已不在当前库存中，请重读核对。' : '正在定位库存原行…'}<Button disabled={paused} onClick={clearLocation}>清除定位</Button><span>清除后恢复原筛选</span></p>}
    {pending && <p className="inventory-warning" role="alert">{pending.doc_no} #{pending.seq} 的调整结果待核实。<Button disabled={paused} onClick={() => setEditing(pending)}>核对这条调整</Button></p>}
    {storageError && <p className="notice" role="alert">{storageError}</p>}
    {filterOpen && <div className="inventory-filter"><Select aria-label="筛选列" value={column} onChange={setColumn} options={fields.map(([value,label]) => ({value,label}))} disabled={paused} />
      {meta[2] === 'num' ? <><label>最小值<Input aria-label="列最小值" value={filter.min} disabled={paused} onChange={e => changeFilter('min',e.target.value)} /></label><label>最大值<Input aria-label="列最大值" value={filter.max} disabled={paused} onChange={e => changeFilter('max',e.target.value)} /></label></> : meta[2] === 'text' && <Input aria-label="列包含文字" placeholder="包含…" value={filter.q} disabled={paused} onChange={e => changeFilter('q',e.target.value)} />}
      <Select mode="multiple" aria-label="列值清单" placeholder="值清单（多选）" value={filter.values} onChange={value => changeFilter('values',value)} options={values.map(value => ({value,label:value}))} showSearch={{optionFilterProp:'label'}} disabled={paused} maxTagCount="responsive" />
      <Button disabled={paused} onClick={() => setFilters(old => {const next = {...old};delete next[column];return next;})}>清除此列</Button><Button disabled={paused} onClick={() => setFilters({})}>清除全部列</Button>{filterProblem && <span role="alert">{filterProblem}</span>}</div>}
    <div className="inventory-summary"><span aria-live="polite" aria-atomic="true"><span className="inventory-count-feedback" key={`${rows.length}:${query.data?.rows.length ?? 0}`}>{query.data ? `${rows.length} / ${query.data.rows.length} 行` : '尚未读取'}</span></span>{onlyAdjusted && <Tag className="status-tag status-info">已调整</Tag>}{query.isFetching && <span role="status">正在重读…</span>}</div>
    {query.isError && <p className="notice" role="alert">{query.error.message}{query.data ? ' 保留上次读取的内容。' : ' 尚未读取库存。'}<Button disabled={paused || query.isFetching} onClick={() => void query.refetch()}>重试读取库存</Button></p>}{projects.isError && <p className="notice" role="alert">{projects.error.message}<Button disabled={paused} onClick={() => void projects.refetch()}>重读项目</Button></p>}
    {query.isPending ? <p role="status">正在读取库存单据…</p> : query.data && <div className="inventory-grid" ref={root}><AgGridReact<InventoryRow> theme={gridTheme} rowBuffer={2} rowData={rows} columnDefs={columns} pinnedBottomRowData={totals as InventoryRow[]}
      getRowId={p => String(p.data.id)} defaultColDef={defaultColumn} rowHeight={pageGridGeometry(scale).rowHeight} headerHeight={pageGridGeometry(scale).headerHeight}
      suppressScrollOnNewData suppressColumnVirtualisation overlayNoRowsTemplate="当前筛选条件下没有库存单据"
      onGridReady={e => { grid.current = e.api; fitGridColumns(e.api,root.current,true); measureInventoryRows(e.api,root.current); }} onFirstDataRendered={e => { fitGridColumns(e.api,root.current,true); measureInventoryRows(e.api,root.current); }} onGridSizeChanged={e => { fitGridColumns(e.api,root.current); measureInventoryRows(e.api,root.current); }} onColumnResized={e => measureInventoryRows(e.api,root.current)} /></div>}
    {editRow && <InventoryAdjust key={editRow.id} row={editRow} adjustment={query.data?.adjustments.find(a => a.row_id === editRow.id)} me={editMissing ? null : me} paused={paused} close={() => setEditing(null)} reload={reload} unknown={Boolean(pending)} onUnknown={value => setPending(value ? editRow : null)} missing={editMissing} />}
    {fetchMonth !== null && <InventoryFetch month={fetchMonth} me={me} paused={paused} close={() => setFetchMonth(null)} refresh={async() => {await reload();}} pending={Boolean(fetchPending)} onPending={updateFetchPending} />}
  </section>;
}
