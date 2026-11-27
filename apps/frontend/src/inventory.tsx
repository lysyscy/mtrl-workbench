import { useAmountComparator } from './use-amount-comparator';
import { DialogPresence } from './workspace-motion';
import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import Select from 'antd/es/select';
import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, GridApi, ICellRendererParams, ModelUpdatedEvent } from 'ag-grid-community';
import { readProjects, requestJson } from './api';
import type { Identity } from './api';
import { ProjectPicker, reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { cacheFontMeasurement, contentWidth, fixedWidth, gridTheme, numberColumnWidth, fullTextWidth } from './grid';
import { money } from './notices-api';
import { coarseRows, effectiveValues, fields, getInventory, sumRows } from './inventory-api';
import type { Field, InventoryRow } from './inventory-api';
import { InventoryAdjust } from './inventory-adjust';
import { InventoryFetch } from './inventory-fetch';
import { useReportFetchPending } from './i8-report-fetch';
import { SettlementExport } from './settlement-export';
import { readHistory, useHistoryGuard } from './history';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
import { valueFilterColumn } from './grid-value-filter';
import { compareFilterValues, normalizeDateFilterValue } from './grid-value-filter-model';
import { ReadFailure, ReadPlaceholder, ReadStatusLane, readPhase } from './read-region';

type InventoryGridRow = InventoryRow & { located?: true };
interface FilteredView {
  source: InventoryGridRow[];
  model: string;
  rows: InventoryGridRow[];
}

const defaultColumn: ColDef<InventoryGridRow> = {resizable:true,suppressMovable:true,wrapHeaderText:true};
const inventoryRowId = (row: InventoryRow) => String(row.id);
const formatFilterAmount = (value: unknown) => money(String(value));
const emptyResult = '当前筛选条件下没有库存单据';
// AG Grid resets a column filter if its handler changes when widths are reapplied.
const filterColumns = fields.map(([field, headerName, type]) => ({
  field, type,
  definition: valueFilterColumn<InventoryGridRow>({
    field, headerName,
    ...(field === 'doc_date' ? { comparator: (a, b) => compareFilterValues(a, b, 'date') } : {}),
  }, {
    kind: field === 'doc_date' ? 'date' : type === 'num' ? 'number' : 'text',
    value: row => field === 'doc_date' ? normalizeDateFilterValue(row.doc_date) : row[field],
    keepVisible: (row: InventoryGridRow) => row.located === true,
    ...(type === 'num' ? { format: formatFilterAmount } : {}),
  }),
}));
const layoutColumns = fields.map(([id,,type]) => ({ id, text: (row: InventoryRow) => type === 'num' ? row[id] ? money(row[id]) : '' : row[id] ?? '', wrap: type !== 'num' && !['doc_no','doc_date','biz_type'].includes(id), className: 'inventory-cell-text' }));
const totalsOf = (rows: InventoryRow[]) => rows.length ? [{id:-1,doc_no:'合计',qty:sumRows(rows,'qty'),amount:sumRows(rows,'amount'),adj_amount:sumRows(rows,'adj_amount'),tax_total:sumRows(rows,'tax_total')}] : [];

function inventoryWidths(rows: InventoryRow[], totals: ReturnType<typeof totalsOf>, scale: number) {
  const widths: Partial<Record<Field, ReturnType<typeof contentWidth>>> = {};
  const withTotals = [...rows, ...totals];
  for (const [field, , type] of fields) {
    if (type === 'num') {
      const values = new Set<string>();
      for (const row of withTotals) {
        const value = row[field as keyof typeof row];
        if (value != null && value !== '') values.add(String(value));
      }
      widths[field] = numberColumnWidth([...values].map(value => money(value)), scale);
    } else if (field === 'doc_no' || field === 'doc_date' || field === 'biz_type') {
      widths[field] = fullTextWidth(rows.map(row => row[field]), scale);
    }
  }
  return widths;
}

export function InventoryPage({me,blocked,active}:{me:Identity|null;blocked:boolean;active:boolean}) {
  const location = useLocation(), navigate = useNavigate();
  const rawTarget = active ? new URLSearchParams(location.search).get('row') : null;
  const target = rawTarget && /^\d+$/.test(rawTarget) && Number.isSafeInteger(Number(rawTarget)) && Number(rawTarget) > 0 ? Number(rawTarget) : null;
  function clearLocation() { const params = new URLSearchParams(location.search); params.delete('row'); void navigate({ pathname: location.pathname, search: params.toString() }, { replace: true }); }
  const client = useQueryClient(), root = useRef<HTMLDivElement>(null);
  const [period,setPeriod] = useState(reportMonth), [ids,setIds] = useState<number[]>([]), [direction,setDirection] = useState('全部'), [onlyAdjusted,setOnlyAdjusted] = useState(false);
  const [filtered,setFiltered] = useState<FilteredView | null>(null);
  const lastFiltered = useRef<FilteredView | null>(null);
  const [editing,setEditing] = useState<InventoryRow|null>(null), [fetchMonth,setFetchMonth] = useState<string|null>(null);
  const [pending,setPending] = useState<InventoryRow|null>(null);
  const {month:fetchPending, update:updateFetchPending, error:storageError} = useReportFetchPending('inventory', me?.account ?? '');
  useHistoryGuard('inventory-pending',() => pending ? '库存调整正在处理或结果待核实，请先重读核对。' : fetchPending ? '库存抓取正在处理或结果待核实，请先核对执行记录。' : '');
  const query = useQuery({queryKey:['inventory'],enabled:active && !blocked,queryFn:({signal}) => getInventory(signal)});
  const projects = useQuery({queryKey:['projects','active'],enabled:active && !blocked,queryFn:async({signal}) => readProjects(await requestJson('/api/m01/projects',{signal}))});
  const warehouses = ids.map(id => projects.data?.find(p => p.id === id)?.warehouse_name ?? '__unavailable__');
  const displayedRows=useMemo(()=>(query.data?.rows??[]).map(row=>{const values=effectiveValues(row);return {...row,...values,amount:row.amount};}),[query.data]);
  const coarse = useMemo(() => coarseRows(displayedRows,period,warehouses,direction,onlyAdjusted),[displayedRows,period,warehouses.join('\0'),direction,onlyAdjusted]);
  const gridRows = useMemo<InventoryGridRow[]>(() => {
    if (target === null) return coarse;
    const row = displayedRows.find(row => row.id === target);
    // Update the node even when locating the only row already in the coarse result.
    return row ? [{ ...row, located: true }] : [];
  }, [coarse, displayedRows, target]);
  const rows = target === null && filtered?.source === gridRows ? filtered.rows : gridRows;
  const scale = Number(me?.ui_scale_css ?? 1), paused = blocked || !active;
  async function reload() {
    await client.invalidateQueries({refetchType:'none'});
    await client.cancelQueries({queryKey:['inventory']});
    const data = await client.fetchQuery({queryKey:['inventory'],staleTime:0,queryFn:({signal}) => getInventory(signal)});
    if(me){const queryKey=['history',`${me.id}:${me.account}`];await client.cancelQueries({queryKey,exact:true});await client.fetchQuery({queryKey,staleTime:0,queryFn:async({signal})=>readHistory(await requestJson('/api/history/status',{signal}))});}
    return data;
  }
  const grid = useRef<GridApi<InventoryGridRow> | null>(null);
  const syncVisibleRows = useCallback(({ api }: ModelUpdatedEvent<InventoryGridRow>) => {
    const source = api.getGridOption('rowData');
    const previous = lastFiltered.current;
    if (!source || !api.isColumnFilterPresent()) {
      if (previous) { lastFiltered.current = null; setFiltered(null); }
      return;
    }
    const model = JSON.stringify(api.getFilterModel());
    // Sizing and sorting also update the model, but do not change the filtered row set.
    if (previous?.source === source && previous.model === model) return;
    const rows: InventoryGridRow[] = [];
    api.forEachNodeAfterFilter(node => { if (node.data) rows.push(node.data); });
    const next = { source, model, rows };
    lastFiltered.current = next;
    setFiltered(next);
  }, []);
  const controls = useRef({ unavailable: false, pendingId: null as number | null });
  const coarseTotals = useMemo(() => totalsOf(coarse), [coarse]);
  const totals = useMemo(() => rows === coarse ? coarseTotals : totalsOf(rows), [rows, coarse, coarseTotals]);
  // Clearing column filters returns to this same immutable coarse result.
  const coarseWidths = useMemo(() => cacheFontMeasurement(() => inventoryWidths(coarse, coarseTotals, scale)),
    [coarse, coarseTotals, scale]);
  const widths = useMemo(() => rows === coarse ? coarseWidths() : inventoryWidths(rows, totals, scale), [rows, totals, scale, coarse, coarseWidths]);
  const compareAmounts = useAmountComparator(displayedRows);
  const columns = useMemo<ColDef<InventoryGridRow>[]>(() => ([
    ...filterColumns.map(({field,type,definition}):ColDef<InventoryGridRow> => ({...definition,wrapText:type !== 'num' && !['doc_no','doc_date','biz_type'].includes(field),
      ...(type === 'num' ? {cellClass:'money',valueFormatter:(p:{value:unknown}) => p.value === '' || p.value == null ? '' : formatFilterAmount(p.value),comparator:compareAmounts} : {}),
      ...(field === 'doc_no' ? {pinned:'left' as const} : {}),
      ...(widths[field] ?? contentWidth(['seq','unit'].includes(field)?40:field==='spec'?56:['wbs_name','cbs_name'].includes(field)?60:field==='material_property'?64:76,['seq','unit'].includes(field)?85:300,scale,['material','vendor','warehouse','spec','wbs_name','cbs_name'].includes(field)?1:0)),
      ...(['doc_no','doc_date','biz_type'].includes(field)?{cellClass:'inventory-identifier',suppressAutoSize:true}:{}),
    })),
    {colId:'actions',headerName:'调整单',pinned:'right',sortable:false,...fixedWidth(100,scale),cellRenderer:(p:ICellRendererParams<InventoryGridRow>) => p.data && !p.node.rowPinned && <Button size="small" disabled={controls.current.unavailable || Boolean(controls.current.pendingId !== null && controls.current.pendingId !== p.data.id)} onClick={() => { if (!controls.current.unavailable && (controls.current.pendingId === null || controls.current.pendingId === p.data!.id)) setEditing(p.data!); }}>{p.data.adjusted ? '查看 / 调整' : '办理调整'}</Button>},
  ] satisfies ColDef<InventoryGridRow>[]),[scale, widths, compareAmounts]);
  const presentation = useGridPresentation<InventoryGridRow>({ table: 'inventory', root, active: active && !blocked, rows, totals: totals as InventoryGridRow[], columns, measurement:layoutColumns, scope: JSON.stringify([period,[...ids].sort(),direction,onlyAdjusted,filtered?.model,target]), identity: [...ids].sort().join(','), rowId: inventoryRowId, scale });
  useLayoutEffect(() => {
    controls.current = { unavailable: paused || query.isError || query.isFetching || presentation.state === 'updating', pendingId: pending?.id ?? null };
    if (active) grid.current?.refreshCells({ force: true, columns: ['actions'] });
  }, [active, paused, query.isError, query.isFetching, pending, presentation.state]);
  const editRow = editing && (query.data?.rows.find(r => r.id === editing.id) ?? editing);
  const editMissing = Boolean(editing && query.data && !query.data.rows.some(r => r.id === editing.id));
  // Inventory keeps one read state for its table: the first read holds the reserved box with a
  // quiet skeleton, a failed reread keeps the rows it already published, and the status lane
  // reports either case without adding a line above the table.
  const readState = readPhase(query, query.data !== undefined && query.data.rows.length === 0);
  const placeheld = readState === 'idle' || readState === 'reading' || readState === 'error';
  const singleMonth = /^\d{4}-\d{2}$/.test(period);
  return <section className="wb-surface inventory-page page-shell page-shell--fill" data-page-layout="fill" aria-label="库存单据与调整单">
    <div className="inventory-toolbar" data-page-chrome>
      <div className="inventory-toolbar-field"><span>核算期间</span><TimePicker singleEntry label="库存核算期间" value={period} modes={['月','跨月','年','全部']} onChange={setPeriod} disabled={paused} /></div>
      <ProjectPicker label="库存项目" projects={(projects.data ?? []).filter(p => query.data?.projects.includes(p.warehouse_name ?? ''))} selected={ids} pick={setIds} multiple emptyLabel="全部项目" disabled={paused || projects.isPending || projects.isError} />
      <label className="inventory-toolbar-field">方向<Select aria-label="库存方向" value={direction} onChange={setDirection} options={['全部','入库','出库'].map(value => ({value,label:value}))} disabled={paused} /></label>
      <Checkbox checked={onlyAdjusted} disabled={paused} onChange={e => setOnlyAdjusted(e.target.checked)}>只看被调整行</Checkbox>
      <Button disabled={paused || !me || Boolean(pending)} onClick={() => setFetchMonth(fetchPending ?? (singleMonth ? period : reportMonth()))}>{fetchPending ? '核对抓取…' : '按月抓取…'}</Button>
      <div className="inventory-toolbar-field">
        <SettlementExport url={`/api/m08/inventory/export?${new URLSearchParams({period})}`} scope={`${period} 库存（含数据透视表）`} paused={paused} disabled={query.isPending || query.isError || !singleMonth}>
          <p>按核算期间导出全部项目；不受本页项目、方向和列筛选限制。</p><p>读取最近抓取的源文件，不叠加调整单。包含原单明细、过程资料透视、安全文明施工费透视；没有缓存时请先抓取。</p>
        </SettlementExport>
        {!singleMonth && <span className="inventory-export-hint">导出请选择单月</span>}
      </div>
      <span className="inventory-count" aria-live="polite" aria-atomic="true"><span className="inventory-count-feedback" key={`${rows.length}:${query.data?.rows.length ?? 0}`}>{query.data ? `${rows.length} / ${query.data.rows.length} 行` : '尚未读取'}</span></span>
    </div>
    {rawTarget !== null && <p className="inventory-location" role="status">{target === null ? '定位参数无效。' : query.data ? rows.length ? `已定位 ${rows[0]!.doc_no} #${rows[0]!.seq}` : '原行已不在当前库存中，请重读核对。' : '正在定位库存原行…'}<Button disabled={paused} onClick={clearLocation}>清除定位</Button><span>清除后恢复原筛选</span></p>}
    {pending && <p className="inventory-warning" role="alert">{pending.doc_no} #{pending.seq} 的调整结果待核实。<Button disabled={paused} onClick={() => setEditing(pending)}>核对这条调整</Button></p>}
    {storageError && <p className="notice" role="alert">{storageError}</p>}
    <ReadStatusLane phase={readState} announce="正在读取库存单据…" className="inventory-read-status">{(readState === 'error' || readState === 'stale') && <ReadFailure read={query} retained={query.data ? '读取更新失败，保留上次读取的内容。' : undefined} />}{projects.isError && <ReadFailure read={projects} label="项目清单" retained="项目清单更新未成功，保留上次结果。" />}</ReadStatusLane>
    {placeheld ? <div className="inventory-grid page-fill-stage inventory-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={8} quiet={readState === 'error'} /></div> : <PreparedGrid presentation={presentation} className="inventory-grid page-fill-stage" errorClassName="notice" grid={{theme:gridTheme,alwaysShowVerticalScroll:true,rowBuffer:2,
      rowData:gridRows,enableFilterHandlers:true,popupParent:document.body,onModelUpdated:syncVisibleRows,
      getRowId:p=>String(p.data.id),defaultColDef:defaultColumn,suppressScrollOnNewData:true,suppressColumnVirtualisation:true,
      localeText:{noRowsToShow:emptyResult,noMatchingRows:emptyResult},onGridReady:e=>{grid.current=e.api;}}} />}
    <DialogPresence>{editRow && <InventoryAdjust key={editRow.id} row={editRow} properties={query.data?.materialProperties??[]} adjustment={query.data?.adjustments.find(a => a.row_id === editRow.id)} me={editMissing ? null : me} paused={paused} close={() => setEditing(null)} reload={reload} unknown={Boolean(pending)} onUnknown={value => setPending(value ? editRow : null)} missing={editMissing} />}</DialogPresence>
    <DialogPresence>{fetchMonth !== null && <InventoryFetch month={fetchMonth} me={me} paused={paused} close={() => setFetchMonth(null)} refresh={async() => {await reload();}} pending={Boolean(fetchPending)} onPending={updateFetchPending} />}</DialogPresence>
  </section>;
}
