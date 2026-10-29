import type { ColDef, ColGroupDef, ColumnResizedEvent, GridApi } from 'ag-grid-community';

type Widths = Record<string, number>;
type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem' | 'removeItem'>;
type Channel = { widths: Widths; error: string; revision: number; readers: Set<() => void>; listeners: Set<(reset: boolean) => void> };
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
function channelFor(owner: string, table: string, storage: () => Storage) {
  const key=gridWidthKey(owner,table);
  let channel=channels.get(key);
  if(!channel){
    channel={widths:{},error:'',revision:0,readers:new Set(),listeners:new Set()};
    try{channel.widths=readGridWidths(storage(),key);}catch{channel.error='浏览器未能读取列宽设置，当前使用自动列宽。';}
    channels.set(key,channel);
  }
  return {key,channel};
}
function releaseChannel(key:string,channel:Channel){if(!channel.listeners.size&&!channel.readers.size)channels.delete(key);}
// React reads the same persisted-preference channel as the native state binding.
// This is preference state only; actual column widths continue to live in AG.
export function gridWidthPreferences(owner:string,table:string,storage:()=>Storage){
  const {key,channel}=channelFor(owner,table,storage);
  return {
    getSnapshot:()=>channel.revision,
    getWidths:()=>channel.widths,
    getError:()=>channel.error,
    subscribe:(listener:()=>void)=>{channel.readers.add(listener);return()=>{channel.readers.delete(listener);releaseChannel(key,channel);};},
  };
}

// Persist only deliberate header resizes. AG Grid owns bounds, width ownership and flex.
export function bindGridWidths(api: GridApi, options: {
  owner: string; table: string; storage: () => Storage; scale: () => number;
  changed: (custom: boolean, error: string, reset?: boolean) => void;
  layoutKey?: () => string;
  activeDragId?: () => string | null;
  dragFinished?: () => void;
}) {
  const {key,channel:shared}=channelFor(options.owner,options.table,options.storage);
  let pendingReset=false;
  const boundsReady=()=>{
    const drag=options.activeDragId?.();
    const ids=new Set([...Object.keys(shared.widths),...(drag?[drag]:[])]);
    const current=(columns:(ColDef|ColGroupDef)[]):boolean=>columns.every(column=>'children'in column?current(column.children):!column.context?.manualWidthBounds||column.context.manualWidthBounds.manual===ids.has(column.colId??String(column.field)));
    return current(api.getGridOption('columnDefs')??[]);
  };
  const notify = (reset = false) => options.changed(Object.keys(shared.widths).length > 0, shared.error, reset);
  const publish = (reset = false, origin?: (reset:boolean)=>void) => {
    shared.revision++;
    [...shared.readers].forEach(listener=>listener());
    queueMicrotask(()=>[...shared.listeners].forEach(listener => {
      if (shared.listeners.has(listener)) { if(listener===origin)notify();else listener(reset); }
    }));
  };
  const save = () => {
    try {
      if (Object.keys(shared.widths).length) options.storage().setItem(key, JSON.stringify({version: 1, widths: shared.widths}));
      else options.storage().removeItem(key);
      shared.error = '';
    } catch { shared.error = Object.keys(shared.widths).length ? '列宽仅本次有效，浏览器未能保存。' : '已恢复自动列宽，但浏览器未能清除旧设置，刷新后可能恢复旧列宽。'; }
  };
  const apply = () => {
    if (api.isDestroyed()) return;
    // A preference change can precede React's column-def commit. Wait for its
    // already-materialised bounds instead of temporarily clamping a saved width.
    if(!boundsReady())return;
    const state = Object.entries(shared.widths).flatMap(([colId, width]) => {
      const column = api.getColumn(colId), definition = column?.getColDef();
      if (!column || !definition || definition.minWidth === definition.maxWidth && definition.minWidth !== undefined) return [];
      const target=Math.max(definition.minWidth??20,Math.min(definition.maxWidth??Infinity,width*options.scale()));
      return Math.abs(column.getActualWidth()-target)<.1&&!column.getFlex()?[]:[{colId,width:target,flex:null}];
    });
    if (state.length) api.applyColumnState({state});
  };
  const resized = (event: ColumnResizedEvent) => {
    if (event.source !== 'uiColumnResized' || !event.finished) return;
    const id=options.activeDragId?.(),target=id?api.getColumn(id):null;
    for (const column of target?[target]:event.columns ?? (event.column ? [event.column] : [])) {
      const definition = column.getColDef();
      if (definition.minWidth === definition.maxWidth && definition.minWidth !== undefined) continue;
      shared.widths[column.getColId()] = column.getActualWidth() / options.scale();
    }
    save();
    publish(false,receive);
    options.dragFinished?.();
  };
  const fit = () => {
    if (api.isDestroyed()) return;
    const columns = api.getAllDisplayedColumns().filter(column => !Object.hasOwn(shared.widths, column.getColId()) && !column.getFlex() && !column.getColDef().suppressAutoSize);
    if (columns.length) api.autoSizeColumns(columns, true);
  };
  const resetNative = () => {
    if (api.isDestroyed()) return;
    // Native reset releases user width ownership. Restore every other column attribute.
    const state = api.getColumnState().map(({width: _width, flex: _flex, ...rest}) => rest);
    api.resetColumnState();
    api.applyColumnState({state, applyOrder: true});
    fit();
  };
  const reset = () => { shared.widths = {}; save(); publish(true); };
  const receive = (reset: boolean) => { if(reset)pendingReset=true;else apply();notify(reset); };
  let columnLayout = options.layoutKey?.() ?? String(options.scale());
  const columnsLoaded = () => {
    if(!boundsReady())return;
    const nextLayout = options.layoutKey?.() ?? String(options.scale());
    // Initial widths do not update existing native columns when type shrinks.
    // Wait for the new definitions, then restore reader state and saved widths.
    if (pendingReset||nextLayout !== columnLayout) { pendingReset=false;columnLayout = nextLayout; resetNative(); }
    apply();
  };
  shared.listeners.add(receive);
  api.addEventListener('columnResized', resized);
  const cancelled=()=>options.dragFinished?.();
  api.addEventListener('dragCancelled', cancelled);
  api.addEventListener('newColumnsLoaded', columnsLoaded);
  apply(); notify();
  return {apply, fit, reset, dispose: () => {
    shared.listeners.delete(receive);
    releaseChannel(key,shared);
    if (!api.isDestroyed()) { api.removeEventListener('columnResized', resized); api.removeEventListener('newColumnsLoaded', columnsLoaded); api.removeEventListener('dragCancelled', cancelled); }
  }};
}
