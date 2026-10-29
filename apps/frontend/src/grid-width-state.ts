import type { ColumnResizedEvent, DragStartedEvent, GridApi } from 'ag-grid-community';
import { widthModeColumns } from './grid-manual-widths';

type Widths = Record<string, number>;
type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem' | 'removeItem'>;
type Channel = { widths: Widths; error: string; listeners: Set<(reset: boolean) => void> };
const channels = new Map<string, Channel>();
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
  changed: (custom: boolean, error: string, reset?: boolean) => void;
  layoutKey?: () => string;
}) {
  const key = gridWidthKey(options.owner, options.table);
  let channel = channels.get(key);
  if (!channel) {
    channel = {widths: {}, error: '', listeners: new Set()};
    try { channel.widths = readGridWidths(options.storage(), key); }
    catch { channel.error = '浏览器未能读取列宽设置，当前使用自动列宽。'; }
    channels.set(key, channel);
  }
  const shared = channel;
  let dragging: string | null = null;
  const syncBounds = (ids = new Set(Object.keys(shared.widths))) => {
    const columns = api.getGridOption('columnDefs');
    if (!columns) return;
    const next = widthModeColumns(columns, ids);
    if (next === columns) return;
    const state = api.getColumnState();
    api.setGridOption('columnDefs', next);
    api.applyColumnState({state});
  };
  const notify = (reset = false) => options.changed(Object.keys(shared.widths).length > 0, shared.error, reset);
  const publish = (reset = false, origin?: (reset:boolean)=>void) => queueMicrotask(()=>[...shared.listeners].forEach(listener => {
    if (shared.listeners.has(listener)) { if(listener===origin)notify();else listener(reset); }
  }));
  const save = () => {
    try {
      if (Object.keys(shared.widths).length) options.storage().setItem(key, JSON.stringify({version: 1, widths: shared.widths}));
      else options.storage().removeItem(key);
      shared.error = '';
    } catch { shared.error = Object.keys(shared.widths).length ? '列宽仅本次有效，浏览器未能保存。' : '已恢复自动列宽，但浏览器未能清除旧设置，刷新后可能恢复旧列宽。'; }
  };
  const apply = () => {
    if (api.isDestroyed()) return;
    syncBounds(new Set([...Object.keys(shared.widths), ...(dragging ? [dragging] : [])]));
    const state = Object.entries(shared.widths).flatMap(([colId, width]) => {
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
      shared.widths[column.getColId()] = column.getActualWidth() / options.scale();
    }
    save();
    publish(false,receive);
  };
  const dragStarted = (event: DragStartedEvent) => {
    const handle = event.target.closest('.ag-header-cell-resize');
    const id = handle?.closest('.ag-header-cell')?.getAttribute('col-id');
    if (!id) return;
    dragging = id;
    syncBounds(new Set([...Object.keys(shared.widths), id]));
  };
  const dragStopped = () => { dragging = null; syncBounds(); };
  const fit = () => {
    if (api.isDestroyed()) return;
    const columns = api.getAllDisplayedColumns().filter(column => !Object.hasOwn(shared.widths, column.getColId()) && !column.getFlex() && !column.getColDef().suppressAutoSize);
    if (columns.length) api.autoSizeColumns(columns, true);
  };
  const resetNative = () => {
    if (api.isDestroyed()) return;
    dragging = null;
    syncBounds();
    // Native reset releases user width ownership. Restore every other column attribute.
    const state = api.getColumnState().map(({width: _width, flex: _flex, ...rest}) => rest);
    api.resetColumnState();
    api.applyColumnState({state, applyOrder: true});
    fit();
  };
  const reset = () => { shared.widths = {}; save(); publish(true); };
  const receive = (reset: boolean) => { if (reset) resetNative(); else apply(); notify(reset); };
  let columnLayout = options.layoutKey?.() ?? String(options.scale());
  const columnsLoaded = () => {
    const nextLayout = options.layoutKey?.() ?? String(options.scale());
    // Initial widths do not update existing native columns when type shrinks.
    // Wait for the new definitions, then restore reader state and saved widths.
    if (nextLayout !== columnLayout) { columnLayout = nextLayout; resetNative(); }
    apply();
  };
  shared.listeners.add(receive);
  api.addEventListener('columnResized', resized);
  api.addEventListener('dragStarted', dragStarted);
  api.addEventListener('dragStopped', dragStopped);
  api.addEventListener('dragCancelled', dragStopped);
  api.addEventListener('newColumnsLoaded', columnsLoaded);
  apply(); notify();
  return {apply, fit, reset, dispose: () => {
    shared.listeners.delete(receive);
    if (!shared.listeners.size) channels.delete(key);
    if (!api.isDestroyed()) { api.removeEventListener('columnResized', resized); api.removeEventListener('newColumnsLoaded', columnsLoaded); api.removeEventListener('dragStarted', dragStarted); api.removeEventListener('dragStopped', dragStopped); api.removeEventListener('dragCancelled', dragStopped); }
  }};
}
