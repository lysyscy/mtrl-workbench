import { createElement } from 'react';
import type { ReactNode } from 'react';
import type { ColDef, ICellRendererParams, ValueFormatterParams } from 'ag-grid-community';
import type { TextGridColumn } from './grid-layout';

// Only the opted-in page renderers consume this measurement adapter. They read
// data/value, pinned state and their existing context; they do not invoke row APIs.
export function rendererLayoutColumns<T>(definitions: ColDef<T>[], context?: unknown,
  signature?: (row: T, column: string, pinned: boolean) => string): TextGridColumn<T>[] {
  return definitions.map(definition => {
    const id = definition.colId ?? definition.field!;
    const params = (row: T, pinned: boolean) => ({data: row, value: definition.field ? (row as Record<string, unknown>)[definition.field] : undefined,
      node: {rowPinned: pinned ? 'bottom' : null}, colDef: definition, context} as ICellRendererParams<T>);
    return { id, wrap: Boolean(definition.wrapText), ...(typeof definition.cellClass === 'string' ? {className: definition.cellClass} : {}),
      text: (row: T) => { const p = params(row, false); return String(typeof definition.valueFormatter === 'function' ? definition.valueFormatter(p as ValueFormatterParams<T>) : p.value ?? ''); },
      ...(definition.cellRenderer ? {render: (row: T, pinned: boolean): ReactNode => createElement(definition.cellRenderer, params(row, pinned)),
        signature: (row: T, pinned: boolean) => signature?.(row, id, pinned) ?? JSON.stringify(row)} : {}) };
  });
}
