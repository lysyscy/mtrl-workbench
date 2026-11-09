import { useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import type { ColDef, ColGroupDef, GridApi } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import type { AgGridReactProps } from 'ag-grid-react';
import Button from 'antd/es/button';
import { gridTheme, contentWidth, pageGridGeometry } from './grid';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
import type { GridMeasurement } from './grid-presentation';
import { GridWidthContext, useGridWidthColumns, useGridWidths } from './grid-widths';
import { loadElementFonts } from './appearance-ready';
import { useRetainedGridColumns } from './grid-layout';
import { PageActivity } from './page-activity';
import { manualGridColumns } from './grid-manual-widths';
import { useFirstReadGrid } from './read-region';
const businessTheme=gridTheme.withParams({autoHeightMinBodyHeight:36});
const readColumnDefaults={sortable:false,resizable:true,suppressMovable:true,wrapText:true,autoHeight:true,wrapHeaderText:true,autoHeaderHeight:true};
type BusinessGridProps<T>={
  table: string; rows: T[]; columns: (ColDef<T> | ColGroupDef<T>)[]; rowId: (row: T) => string;
  totals?: T[]; label: string; scope?: string; scale?: number; className?: string; style?: CSSProperties;
  domLayout: 'normal' | 'autoHeight'; context?: unknown;
  rowMinimum?: number;
  gridClassName?: string;
  singleLine?: boolean;
  manualWidths?: boolean;
  measurement?: GridMeasurement<T>;
  grid?: Omit<AgGridReactProps<T>, 'columnDefs' | 'rowHeight' | 'headerHeight' | 'context'>;
};
function businessColumns<T>(columns:(ColDef<T>|ColGroupDef<T>)[],scale:number,singleLine=false):(ColDef<T>|ColGroupDef<T>)[]{
  return columns.map(column=>'children'in column?{...column,children:businessColumns(column.children,scale,singleLine)}:
    {...('initialWidth'in column||'width'in column||'minWidth'in column?{}:contentWidth(88,320,scale,1)),wrapText:!singleLine,
      ...(singleLine?{wrapHeaderText:false,autoHeight:false,autoHeaderHeight:false}:{}),...column});
}

// Small business views use the same native definitions and lifecycle as page grids.
// Each caller chooses its native layout; this component supplies no table schema.
export function BusinessGrid<T>({ table, rows, columns, rowId, totals, label, scope = table, scale: suppliedScale,
  className = '', style, domLayout, grid = {}, context, rowMinimum, gridClassName='',singleLine=false,measurement, initialScroll }: BusinessGridProps<T> & { initialScroll?: 'bottom' }) {
  const root = useRef<HTMLDivElement>(null);
  const api = useRef<GridApi<T> | null>(null), initialScrollApplied = useRef(false);
  const active=useContext(PageActivity);
  const scale = suppliedScale ?? (Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1);
  const totalRows = useMemo(() => totals ?? [], [totals]);
  const definitions = useMemo(() => businessColumns(columns,scale,singleLine), [columns, scale,singleLine]);
  const presentation = useGridPresentation({table, root, active, rows, totals: totalRows, columns: definitions,
    rowId, scale, scope, identity: scope, context,...(measurement===undefined?{}:{measurement}),...(rowMinimum===undefined?{}:{rowMinimum})});
  useLayoutEffect(() => {
    if (initialScroll !== 'bottom' || initialScrollApplied.current || !active || !presentation.visible || presentation.state !== 'ready' || !rows.length) return;
    const last = (api.current?.getDisplayedRowCount() ?? 0) - 1;
    if (last >= 0) {
      api.current?.ensureIndexVisible(last, 'bottom');
      initialScrollApplied.current = true;
    }
  }, [active, initialScroll, presentation.state, presentation.visible, rows.length]);
  return <div className={`business-grid-view ${className}`}>
    <PreparedGrid presentation={presentation} className={'business-grid '+gridClassName+(singleLine?' grid-single-line':'')} style={style} role="region" aria-label={label}
      grid={{theme: businessTheme, domLayout, groupHeaderHeight:pageGridGeometry(scale).groupHeaderHeight, getRowId: p => rowId(p.data),
        suppressColumnVirtualisation: true, suppressCellFocus: true,suppressScrollOnNewData:true,animateRows:false,
        defaultColDef: {sortable: false, resizable: true, suppressMovable: true, wrapHeaderText: true},
        ...grid, onGridReady: event => { api.current = event.api; grid.onGridReady?.(event); }}} />
  </div>;
}

// Repeated small views use AG's native row/header auto height; inputs stay business-owned.
// Keep the richer editor/scroll preparation in BusinessGrid for workspaces.
export function ReadGrid<T>({table,rows,columns,rowId,totals,label,scale:suppliedScale,className='',style,domLayout,grid={},context,singleLine=false,manualWidths=false}:BusinessGridProps<T>) {
  const root=useRef<HTMLDivElement>(null),[api,setApi]=useState<GridApi<T>|null>(null);
  const active=useContext(PageActivity);
  const scale=suppliedScale??(Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))||1);
  const widths=useGridWidths(table,root,scale,active),[ready,setReady]=useState(false),[error,setError]=useState(''),[rendered,setRendered]=useState(0),[retry,setRetry]=useState(0);
  useFirstReadGrid(error ? 'error' : ready ? 'ready' : 'preparing');
  const totalRows=useMemo(()=>totals??[],[totals]);
  const definitions=useMemo(()=>{
    const native=businessColumns(columns,scale,singleLine);
    return manualWidths ? manualGridColumns(native) : native;
  },[columns,scale,singleLine,manualWidths]);
  const defaults=useMemo(()=>singleLine?{...readColumnDefaults,wrapText:false,autoHeight:false,wrapHeaderText:false,autoHeaderHeight:false}:readColumnDefaults,[singleLine]);
  const widthColumns=useGridWidthColumns(definitions);
  const retained=useRetainedGridColumns(widthColumns,root,widths.layoutKey);
  const materialized=useMemo(()=>widths.columns(retained),[retained,widths.columns]);
  useEffect(()=>{if(api&&!rows.length)setRendered(n=>n||1);},[api,rows.length]);
  useEffect(()=>{
    const node=root.current;if(!active||!node||!api||!rendered||ready)return;let cancelled=false,frame=0;
    const nextFrame=()=>new Promise<void>(resolve=>{frame=requestAnimationFrame(()=>resolve());});
    void (async()=>{try {
      await loadElementFonts(node);if(cancelled||api.isDestroyed())return;
      widths.fit();api.resetRowHeights();
      const renderedRows=()=>{
        if(domLayout!=='autoHeight')return true;
        const ids=new Set([...node.querySelectorAll('.ag-row[row-id]')].map(row=>row.getAttribute('row-id')));
        const viewport=node.querySelector<HTMLElement>('.ag-body-horizontal-scroll-viewport');
        const scrollbar=node.querySelector<HTMLElement>('.ag-body-horizontal-scroll');
        const needsScroll=Boolean(api.getGridOption('alwaysShowHorizontalScroll'))||Boolean(viewport&&viewport.scrollWidth>viewport.clientWidth+1);
        return rows.every(row=>ids.has(rowId(row)))&&(!rows.length||!scrollbar||api.getGridOption('suppressHorizontalScroll')||!needsScroll||scrollbar.offsetHeight>0);
      };
      do { await nextFrame(); if(cancelled||api.isDestroyed())return; } while(!api.isAnimationFrameQueueEmpty()||!renderedRows());
      setReady(true);setError('');
    } catch(failure) {if(!cancelled)setError(failure instanceof Error?failure.message:'字体读取失败，请重试。');}})();
    return()=>{cancelled=true;cancelAnimationFrame(frame);};
  },[api,rendered,retry,active,ready,rows,rowId,domLayout,widths.fit]);
  const {onGridReady,onFirstDataRendered,...options}=grid;
  return <GridWidthContext.Provider value={widths}><div className={`business-grid-view ${className}`}>
    <div ref={root} className={'business-grid'+(singleLine?' grid-single-line':'')} role="region" aria-label={label} data-layout-state={error?'error':ready?'ready':'preparing'} inert={!ready} style={{...style,visibility:ready?style?.visibility:'hidden'}}>
      <AgGridReact<T> theme={businessTheme} {...pageGridGeometry(scale)} defaultColDef={defaults} suppressCellFocus suppressColumnVirtualisation
        suppressScrollOnNewData animateRows={false} {...options} domLayout={domLayout} context={context} columnDefs={materialized} rowData={rows} pinnedBottomRowData={totalRows} getRowId={p=>rowId(p.data)} autoSizeStrategy={widths.strategy}
        onGridReady={e=>{widths.attach(e.api);setApi(e.api);onGridReady?.(e);}} onFirstDataRendered={e=>{setRendered(n=>n||1);onFirstDataRendered?.(e);}}/>
    </div>{error&&<p role="alert">{error}<Button onClick={()=>setRetry(n=>n+1)}>重试表格加载</Button></p>}
  </div></GridWidthContext.Provider>;
}
