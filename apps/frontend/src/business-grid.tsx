import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import type { ColDef, ColGroupDef, GridApi } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import type { AgGridReactProps } from 'ag-grid-react';
import Button from 'antd/es/button';
import { gridTheme, contentWidth, pageGridGeometry } from './grid';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
import { GridWidthContext, useGridWidthColumns, useGridWidths } from './grid-widths';
import { loadElementFonts } from './appearance-ready';
import { useRetainedGridColumns } from './grid-layout';
import { PageActivity } from './page-activity';
const businessTheme=gridTheme.withParams({autoHeightMinBodyHeight:36});
const readColumnDefaults={sortable:false,resizable:true,suppressMovable:true,wrapText:true,autoHeight:true,wrapHeaderText:true,autoHeaderHeight:true};
type BusinessGridProps<T>={
  table: string; rows: T[]; columns: (ColDef<T> | ColGroupDef<T>)[]; rowId: (row: T) => string;
  totals?: T[]; label: string; scope?: string; scale?: number; className?: string; style?: CSSProperties;
  domLayout: 'normal' | 'autoHeight'; context?: unknown;
  rowMinimum?: number;
  gridClassName?: string;
  grid?: Omit<AgGridReactProps<T>, 'columnDefs' | 'rowHeight' | 'headerHeight' | 'context'>;
};
function businessColumns<T>(columns:(ColDef<T>|ColGroupDef<T>)[],scale:number):(ColDef<T>|ColGroupDef<T>)[]{
  return columns.map(column=>'children'in column?{...column,children:businessColumns(column.children,scale)}:
    {...('initialWidth'in column||'width'in column||'minWidth'in column?{}:contentWidth(88,320,scale,1)),wrapText:true,...column});
}

// Small business views use the same native definitions and lifecycle as page grids.
// Each caller chooses its native layout; this component supplies no table schema.
export function BusinessGrid<T>({ table, rows, columns, rowId, totals, label, scope = table, scale: suppliedScale,
  className = '', style, domLayout, grid = {}, context, rowMinimum, gridClassName='' }: BusinessGridProps<T>) {
  const root = useRef<HTMLDivElement>(null);
  const active=useContext(PageActivity);
  const scale = suppliedScale ?? (Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1);
  const totalRows = useMemo(() => totals ?? [], [totals]);
  const definitions = useMemo(() => businessColumns(columns,scale), [columns, scale]);
  const presentation = useGridPresentation({table, root, active, rows, totals: totalRows, columns: definitions,
    rowId, scale, scope, identity: scope, context,...(rowMinimum===undefined?{}:{rowMinimum})});
  return <div className={`business-grid-view ${className}`}>
    <PreparedGrid presentation={presentation} className={'business-grid '+gridClassName} style={style} role="region" aria-label={label}
      grid={{theme: businessTheme, domLayout, groupHeaderHeight:pageGridGeometry(scale).groupHeaderHeight, getRowId: p => rowId(p.data),
        suppressColumnVirtualisation: true, suppressCellFocus: true,
        defaultColDef: {sortable: false, resizable: true, suppressMovable: true, wrapHeaderText: true},
        ...grid}} />
  </div>;
}

// Repeated small views use AG's native row/header auto height; inputs stay business-owned.
// Keep the richer editor/scroll preparation in BusinessGrid for workspaces.
export function ReadGrid<T>({table,rows,columns,rowId,totals,label,scale:suppliedScale,className='',style,domLayout,grid={},context}:BusinessGridProps<T>) {
  const root=useRef<HTMLDivElement>(null),[api,setApi]=useState<GridApi<T>|null>(null);
  const active=useContext(PageActivity);
  const scale=suppliedScale??(Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))||1);
  const widths=useGridWidths(table,root,scale,active),[ready,setReady]=useState(false),[error,setError]=useState(''),[rendered,setRendered]=useState(0),[retry,setRetry]=useState(0);
  const totalRows=useMemo(()=>totals??[],[totals]);
  const definitions=useMemo(()=>businessColumns(columns,scale),[columns,scale]);
  const widthColumns=useGridWidthColumns(definitions);
  const retained=useRetainedGridColumns(widthColumns,root);
  useEffect(()=>{if(api&&!rows.length)setRendered(n=>n||1);},[api,rows.length]);
  useEffect(()=>{
    const node=root.current;if(!active||!node||!api||!rendered)return;let cancelled=false;
    void loadElementFonts(node).then(()=>{if(!cancelled&&!api.isDestroyed()){widths.fit();api.resetRowHeights();setReady(true);setError('');}},failure=>{if(!cancelled)setError(failure instanceof Error?failure.message:'字体读取失败，请重试。');});
    return()=>{cancelled=true;};
  },[api,rendered,retry,active]);
  const {onGridReady,onFirstDataRendered,...options}=grid;
  return <GridWidthContext.Provider value={widths}><div className={`business-grid-view ${className}`}>
    <div ref={root} className="business-grid" role="region" aria-label={label} data-layout-state={error?'error':ready?'ready':'preparing'} inert={!ready} style={{...style,visibility:ready?'visible':'hidden'}}>
      <AgGridReact<T> theme={businessTheme} {...pageGridGeometry(scale)} defaultColDef={readColumnDefaults} suppressCellFocus suppressColumnVirtualisation
        {...options} domLayout={domLayout} context={context} columnDefs={retained} rowData={rows} pinnedBottomRowData={totalRows} getRowId={p=>rowId(p.data)} autoSizeStrategy={widths.strategy}
        onGridReady={e=>{widths.attach(e.api);setApi(e.api);onGridReady?.(e);}} onFirstDataRendered={e=>{setRendered(n=>n||1);onFirstDataRendered?.(e);}}/>
    </div>{error&&<p role="alert">{error}<Button onClick={()=>setRetry(n=>n+1)}>重试表格加载</Button></p>}
  </div></GridWidthContext.Provider>;
}
