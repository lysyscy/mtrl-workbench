import type { ColDef, ColGroupDef } from 'ag-grid-community';

interface WidthBounds {
  autoMin: number | undefined;
  autoMax: number | undefined;
  manualMin: number | undefined;
  manual: boolean;
}
const key = 'manualWidthBounds';

// Opt in at the page boundary. Ordinary grids retain their existing native bounds.
export function manualGridColumns<T>(columns: ColDef<T>[], scale: number, textMinimums?: Record<string, number>): ColDef<T>[];
export function manualGridColumns<T>(columns: (ColDef<T> | ColGroupDef<T>)[], scale: number, textMinimums?: Record<string, number>): (ColDef<T> | ColGroupDef<T>)[];
export function manualGridColumns<T>(columns: (ColDef<T> | ColGroupDef<T>)[], scale: number, textMinimums: Record<string, number> = {}): (ColDef<T> | ColGroupDef<T>)[] {
  return columns.map(column => {
    if ('children' in column) return {...column, children: manualGridColumns(column.children, scale, textMinimums)};
    if (column.resizable === false || column.minWidth !== undefined && column.minWidth === column.maxWidth) return column;
    const id = column.colId ?? String(column.field), minimum = textMinimums[id];
    const bounds: WidthBounds = {autoMin: column.minWidth, autoMax: column.maxWidth, manualMin: minimum === undefined ? column.minWidth : minimum * scale, manual: false};
    return {...column, context: {...column.context, [key]: bounds}};
  });
}

export function widthModeColumns<T>(columns: (ColDef<T> | ColGroupDef<T>)[], manualIds: ReadonlySet<string>): (ColDef<T> | ColGroupDef<T>)[] {
  let changed = false;
  const next = columns.map(column => {
    if ('children' in column) {
      const children = widthModeColumns(column.children, manualIds);
      if (children === column.children) return column;
      changed = true;
      return {...column, children};
    }
    const bounds: WidthBounds | undefined = column.context?.[key];
    if (!bounds) return column;
    const manual = manualIds.has(column.colId ?? String(column.field));
    if (manual === bounds.manual) return column;
    changed = true;
    const {minWidth: _min, maxWidth: _max, ...rest} = column;
    const min = manual ? bounds.manualMin : bounds.autoMin, max = manual ? undefined : bounds.autoMax;
    return {...rest, ...(min === undefined ? {} : {minWidth: min}), ...(max === undefined ? {} : {maxWidth: max}),
      context: {...column.context, [key]: {...bounds, manual}}};
  });
  return changed ? next : columns;
}
