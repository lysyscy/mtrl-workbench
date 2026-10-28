import type { ColumnResizedEvent, GridApi } from 'ag-grid-community';

type Widths = Record<string, number>;
type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem' | 'removeItem'>;
export function gridWidthKey(owner: string, table: string) {
  return `mtrl:grid-widths:v1:${JSON.stringify([owner, table])}`;
}
export function readGridWidths(storage: Storage, key: string): Widths {
  const text = storage.getItem(key);
  if (!text) return {};
  const saved: unknown = JSON.parse(text);
  if (!saved || typeof saved !== 'object' || !('version' in saved) || saved.version !== 1 || !('widths' in saved) || !saved.widths || typeof saved.widths !== 'object' || Array.isArray(saved.widths)) throw new Error('无效的列宽设置');
  return Object.fromEntries(Object.entries(saved.widths).filter(([id, width]) => id && typeof width === 'number' && Number.isFinite(width) && width > 0 && width <= 10000));
}

// Persist only deliberate header resizes. AG Grid owns bounds, width ownership and flex.
export function bindGridWidths(api: GridApi, options: {
  owner: string; table: string; storage: () => Storage; scale: () => number;
  changed: (custom: boolean, error: string) => void;
}) {
  const key = gridWidthKey(options.owner, options.table);
  let widths: Widths = {}, error = '';
  try { widths = readGridWidths(options.storage(), key); }
  catch { error = '浏览器未能读取列宽设置，当前使用自动列宽。'; }
  const notify = () => options.changed(Object.keys(widths).length > 0, error);
  const save = () => {
    try {
      if (Object.keys(widths).length) options.storage().setItem(key, JSON.stringify({version: 1, widths}));
      else options.storage().removeItem(key);
      error = '';
    } catch { error = Object.keys(widths).length ? '列宽仅本次有效，浏览器未能保存。' : '已恢复自动列宽，但浏览器未能清除旧设置，刷新后可能恢复旧列宽。'; }
    notify();
  };
  const apply = () => {
    if (api.isDestroyed()) return;
    const state = Object.entries(widths).flatMap(([colId, width]) => {
      const column = api.getColumn(colId), definition = column?.getColDef();
      if (!column || !definition || definition.minWidth === definition.maxWidth && definition.minWidth !== undefined) return [];
      return [{colId, width: Math.max(definition.minWidth ?? 20, Math.min(definition.maxWidth ?? Infinity, width * options.scale())), flex: null}];
    });
    if (state.length) api.applyColumnState({state});
  };
  const resized = (event: ColumnResizedEvent) => {
    if (event.source !== 'uiColumnResized' || !event.finished) return;
    for (const column of event.columns ?? (event.column ? [event.column] : [])) {
      const definition = column.getColDef();
      if (definition.minWidth === definition.maxWidth && definition.minWidth !== undefined) continue;
      widths[column.getColId()] = column.getActualWidth() / options.scale();
    }
    save();
  };
  const fit = () => {
    if (api.isDestroyed()) return;
    const columns = api.getAllDisplayedColumns().filter(column => !Object.hasOwn(widths, column.getColId()) && !column.getFlex() && !column.getColDef().suppressAutoSize);
    if (columns.length) api.autoSizeColumns(columns, true);
  };
  const reset = () => {
    if (api.isDestroyed()) return;
    // Native reset releases user width ownership. Restore every other column attribute.
    const state = api.getColumnState().map(({width: _width, flex: _flex, ...rest}) => rest);
    widths = {};
    api.resetColumnState();
    api.applyColumnState({state, applyOrder: true});
    save();
    fit();
  };
  api.addEventListener('columnResized', resized);
  api.addEventListener('newColumnsLoaded', apply);
  apply(); notify();
  return {apply, fit, reset, dispose: () => {
    if (!api.isDestroyed()) { api.removeEventListener('columnResized', resized); api.removeEventListener('newColumnsLoaded', apply); }
  }};
}
