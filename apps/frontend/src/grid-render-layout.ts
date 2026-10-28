import { createElement } from 'react';
import type { ReactNode } from 'react';
import type { ColDef, ColGroupDef, ICellRendererParams, ValueFormatterParams, ValueGetterParams } from 'ag-grid-community';
import type { TextGridColumn } from './grid-layout';

// Only the opted-in page renderers consume this measurement adapter. They read
// data/value, pinned state and their existing context; they do not invoke row APIs.
// Keep grouped report definitions, but give the shared preparer sole ownership of dimensions.
export function initialLayoutColumns<T>(definitions: (ColDef<T> | ColGroupDef<T>)[]): (ColDef<T> | ColGroupDef<T>)[] {
  return definitions.map(definition => {
    if ('children' in definition) return {...definition, children: initialLayoutColumns(definition.children)};
    const {width, autoHeight: _autoHeight, autoHeaderHeight: _autoHeaderHeight, ...rest} = definition;
    return {...rest, ...(width === undefined ? {} : {initialWidth: width}),
      suppressAutoSize: rest.suppressAutoSize ?? Boolean(rest.wrapText || rest.cellRenderer || rest.cellRendererSelector)};
  });
}

export function rendererLayoutColumns<T>(definitions: (ColDef<T> | ColGroupDef<T>)[], context?: unknown,
  signature?: (row: T, column: string, pinned: boolean) => string): TextGridColumn<T>[] {
  return definitions.flatMap(definition => {
    if ('children' in definition) return rendererLayoutColumns(definition.children, context, signature);
    const id = definition.colId ?? definition.field!;
    const params = (row: T, pinned: boolean) => {
      const p = {data: row, value: definition.field ? (row as Record<string, unknown>)[definition.field] : undefined,
        node: {rowPinned: pinned ? 'bottom' : null}, colDef: definition, context} as ICellRendererParams<T>;
      if (typeof definition.valueGetter === 'function') p.value = definition.valueGetter(p as unknown as ValueGetterParams<T>);
      return p;
    };
    return [{ id, wrap: Boolean(definition.wrapText), ...(typeof definition.cellClass === 'string' ? {className: definition.cellClass} : {}),
      text: (row: T, pinned = false) => { const p = params(row, pinned); return String(typeof definition.valueFormatter === 'function' ? definition.valueFormatter(p as ValueFormatterParams<T>) : p.value ?? ''); },
      ...(definition.cellRenderer || definition.cellRendererSelector ? {render: (row: T, pinned: boolean): ReactNode => {
        const p = params(row, pinned), selected = definition.cellRendererSelector?.(p), component = selected?.component ?? definition.cellRenderer;
        return component ? createElement(component, {...p, ...selected?.params}) : typeof definition.valueFormatter === 'function' ? definition.valueFormatter(p as ValueFormatterParams<T>) : String(p.value ?? '');
      }, signature: (row: T, pinned: boolean) => signature?.(row, id, pinned) ?? JSON.stringify(row)} : {}) }];
  });
}
