import { useMemo } from 'react';
import type { ComponentProps, RefObject } from 'react';
import Button from 'antd/es/button';
import { AgGridReact } from 'ag-grid-react';
import type { AgGridReactProps } from 'ag-grid-react';
import type { ColDef, ColGroupDef } from 'ag-grid-community';
import { pageGridGeometry } from './grid';
import { useRetainedGridColumns, useTextGridLayout } from './grid-layout';
import type { TextGridColumn } from './grid-layout';
import { initialLayoutColumns, rendererLayoutColumns } from './grid-render-layout';
import { GridWidthContext, useGridWidthColumns, useGridWidths } from './grid-widths';

export type GridMeasurement<T> = TextGridColumn<T>[] | {
  signature?: (row: T, column: string, pinned: boolean) => string;
  textOnly?: readonly string[];
};
const details = Symbol('grid-presentation');

// A page supplies business columns and scope; this module owns their rendering,
// measurement and publication as one lifecycle. Observations support page labels
// and existing actions without exposing attach/portal/retry ordering to callers.
export function useGridPresentation<T>({table, columns, context, measurement, scale, rowMinimum, ...layout}: {
  columns: (ColDef<T> | ColGroupDef<T>)[]; context?: unknown; measurement?: GridMeasurement<T>;
  root: RefObject<HTMLDivElement | null>; fontRoot?: RefObject<HTMLElement | null>; active: boolean;
  table: string; rows: T[]; totals: T[]; rowId: (row: T) => string; scope: string; identity: string; scale: number;
  rowMinimum?: number;
}) {
  const widths = useGridWidths(table, layout.root, scale, layout.active);
  const retained = useRetainedGridColumns(columns, layout.root,`${widths.layoutKey}:${layout.scope}`);
  const materialized=useMemo(()=>widths.columns(retained),[retained,widths.columns]);
  const widthColumns=useGridWidthColumns(materialized);
  const definitions = useMemo(() => initialLayoutColumns(widthColumns), [widthColumns]);
  const prepared = useMemo(() => {
    if (Array.isArray(measurement)) return measurement;
    return rendererLayoutColumns(definitions, context, measurement?.signature).map(column => {
      if (!measurement?.textOnly?.includes(column.id)) return column;
      const {render: _render, signature: _signature, ...text} = column;
      return text;
    });
  }, [definitions, context, measurement]);
  const geometry = {...pageGridGeometry(scale),...(rowMinimum===undefined?{}:{rowHeight:rowMinimum})};
  const preparation = useTextGridLayout({...layout, columns: prepared, minimum: geometry.rowHeight, headerMinimum: geometry.headerHeight,fit:widths.fit});
  return {state: preparation.state, visible: !preparation.concealed && preparation.state !== 'preparing' && preparation.state !== 'error',
    [details]: {root: layout.root, definitions, context, geometry, preparation, widths, rows: layout.rows, totals: layout.totals, active: layout.active}};
}

export function PreparedGrid<T>({presentation, grid, errorClassName, scrollClassName, attachRoot = true, ...container}: Omit<ComponentProps<'div'>, 'ref' | 'children'> & {
  presentation: ReturnType<typeof useGridPresentation<T>>;
  grid: Omit<AgGridReactProps<T>, 'columnDefs' | 'rowHeight' | 'headerHeight' | 'context'>;
  errorClassName?: string;
  scrollClassName?: string;
  // The ledger measures its existing outer region, including the side heading.
  attachRoot?: boolean;
}) {
  const {visible} = presentation, {root, definitions, context, geometry, preparation, widths, rows, totals} = presentation[details];
  const {onGridReady, ...options} = grid;
  const surface = <div {...container} ref={attachRoot ? root : undefined} inert={!visible} style={{...container.style, visibility: visible ? container.style?.visibility : 'hidden'}}
      data-layout-state={preparation.state} data-layout-error={preparation.error || undefined} aria-busy={preparation.state !== 'ready'}>
      <AgGridReact<T> {...options} autoSizeStrategy={widths.strategy} columnDefs={definitions} rowData={rows} pinnedBottomRowData={totals} context={context} rowHeight={geometry.rowHeight} headerHeight={geometry.headerHeight}
        onGridReady={event => { widths.attach(event.api); preparation.attach(event.api); onGridReady?.(event); }} />
    </div>;
  return <GridWidthContext.Provider value={widths}>
    {scrollClassName ? <div className={scrollClassName}>{surface}</div> : surface}
    {preparation.measurement}
    {preparation.error && <p className={errorClassName} role="alert">{preparation.error}<Button onClick={preparation.retry}>重试表格加载</Button></p>}
  </GridWidthContext.Provider>;
}
