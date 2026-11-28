import { createElement } from 'react';
import type { ReactNode } from 'react';
import type { ColDef, ColGroupDef, ICellRendererParams, ValueFormatterParams } from 'ag-grid-community';
import type { TextGridColumn } from './grid-layout';

import { readLayout } from './grid-layout-callback';
import type { LayoutInput } from './grid-layout-callback';

export function initialLayoutColumns<T>(definitions: (ColDef<T> | ColGroupDef<T>)[]): (ColDef<T> | ColGroupDef<T>)[] {
  return definitions.map(definition => {
    if ('children' in definition) return {...definition, children: initialLayoutColumns(definition.children)};
    const {width, flex, autoHeight: _autoHeight, autoHeaderHeight: _autoHeaderHeight, ...rest} = definition;
    return {...rest, ...(width === undefined ? {} : {initialWidth: width}),
      ...(flex === undefined ? {} : {initialFlex:flex??0}),
      suppressAutoSize: rest.suppressAutoSize ?? Boolean(rest.wrapText || rest.cellRenderer || rest.cellRendererSelector)};
  });
}

export function rendererLayoutColumns<T>(definitions: (ColDef<T> | ColGroupDef<T>)[], context?: unknown,
  signature?: (row: T, column: string, pinned: boolean) => string): TextGridColumn<T>[] {
  return definitions.flatMap(definition => {
    if ('children' in definition) return rendererLayoutColumns(definition.children, context, signature);
    const id = definition.colId ?? definition.field!;
    const input = (row: T, pinned: boolean): LayoutInput<T> => ({data: row, node: {rowPinned: pinned ? 'bottom' : null}});
    const params = (row: T, pinned: boolean) => {
      const cell = input(row, pinned);
      const value = typeof definition.valueGetter === 'function' ? readLayout(definition.valueGetter, cell)
        : definition.field ? (row as Record<string, unknown>)[definition.field] : undefined;
      return {...cell, value, colDef: definition, context} as ICellRendererParams<T>;
    };
    const colSpan = definition.colSpan;
    return [{ id, wrap: Boolean(definition.wrapText), ...(typeof definition.cellClass === 'string' ? {className: definition.cellClass} : {}),
      ...(colSpan ? {span:(row:T,pinned:boolean) => {
        const span = readLayout(colSpan, input(row, pinned));
        return typeof span === 'number' ? span : 1;
      }} : {}),
      text: (row: T, pinned = false) => { const p = params(row, pinned); return String(typeof definition.valueFormatter === 'function' ? definition.valueFormatter(p as ValueFormatterParams<T>) : p.value ?? ''); },
      ...(definition.cellRenderer || definition.cellRendererSelector ? {render: (row: T, pinned: boolean): ReactNode => {
        const p = params(row, pinned), selected = definition.cellRendererSelector?.(p), component = selected?.component ?? definition.cellRenderer;
        return component ? createElement(component, {...p, ...selected?.params}) : typeof definition.valueFormatter === 'function' ? definition.valueFormatter(p as ValueFormatterParams<T>) : String(p.value ?? '');
      }, signature: (row: T, pinned: boolean) => signature?.(row, id, pinned) ?? JSON.stringify(row)} : {}) }];
  });
}
