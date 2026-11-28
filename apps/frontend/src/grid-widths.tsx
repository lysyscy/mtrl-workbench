import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { flushSync } from 'react-dom';
import type { ComponentType, RefObject } from 'react';
import type { ColDef, ColGroupDef, GridApi, IHeaderParams, SizeColumnsToContentStrategy } from 'ag-grid-community';
import Button from 'antd/es/button';
import { bindGridWidths, gridWidthPreferences } from './grid-width-state';
import { bindContentColumnWidths } from './grid-content-widths';
import type { ColumnWidthData } from './grid-content-widths';
import { GridWidthOwner } from './grid-width-owner';
import { manualGridColumns, widthModeColumns } from './grid-manual-widths';

export function useGridWidths<T = unknown>(table: string, root: RefObject<HTMLElement | null>, scale: number, active: boolean,
  { content, resetOnContainerResize = !content }: { content?: ColumnWidthData<T>; resetOnContainerResize?: boolean } = {}) {
  const owner = useContext(GridWidthOwner),[layoutRevision,setLayoutRevision]=useState(0),[dragging,setDragging]=useState<string|null>(null);
  const preferences=useMemo(()=>gridWidthPreferences(owner,table,()=>window.localStorage),[owner,table]);
  const revision=useSyncExternalStore(preferences.subscribe,preferences.getSnapshot);
  const manualIds=useMemo(()=>new Set([...Object.keys(preferences.getWidths()),...(dragging?[dragging]:[])]),[preferences,revision,dragging]);
  const current = useRef({scale, active,layoutKey:`${scale}:${layoutRevision}`,dragging,content});
  current.current = {scale, active,layoutKey:`${scale}:${layoutRevision}`,dragging,content};
  const binding = useRef<ReturnType<typeof bindGridWidths> | null>(null), cleanup = useRef<(() => void) | null>(null);
  const contentBinding = useRef<ReturnType<typeof bindContentColumnWidths<T>> | null>(null);
  const strategy = useMemo<SizeColumnsToContentStrategy>(() => ({
    type: 'fitCellContents', skipHeader: true,
    get columnLimits() {
      return Object.entries(preferences.getWidths()).map(([colId, width]) => {
        const pixels = width * current.current.scale;
        return {colId, minWidth:pixels, maxWidth:pixels};
      });
    },
  }), [preferences]);
  const attach = useCallback((api: GridApi) => {
    cleanup.current?.();
    const controller = bindGridWidths(api, {owner, table, storage: () => window.localStorage, scale: () => current.current.scale,
      layoutKey:()=>current.current.layoutKey,
      activeDragId:()=>current.current.dragging,
      dragFinished:()=>setDragging(null),
      changed: (_custom, _error, reset) => {if(reset)setLayoutRevision(n=>n+1);}});
    binding.current = controller;
    const node = root.current;
    const fitted = node && current.current.content ? bindContentColumnWidths<T>(api, node, () => current.current,
      id => Object.hasOwn(preferences.getWidths(), id)) : null;
    contentBinding.current = fitted;
    const capture=(event:PointerEvent)=>{
      if(event.button!==0)return;
      const target=event.target instanceof Element?event.target:null;
      const id=target?.closest('.ag-header-cell-resize')?.closest('.ag-header-cell')?.getAttribute('col-id');
      if(id){
        controller.beginDrag(id);
        const column=api.getColumn(id);
        if(column?.getFlex())api.applyColumnState({state:[{colId:id,width:column.getActualWidth(),flex:null}]});
        flushSync(()=>setDragging(id));
      }
    };
    node?.addEventListener('pointerdown',capture,true);
    let width=node?.clientWidth??0;
    const resize = node && resetOnContainerResize ? new ResizeObserver(() => {
      const next = node.clientWidth;
      if (!next || next === width) return;
      width = next;
      setLayoutRevision(n => n + 1);
    }) : null;
    if(node)resize?.observe(node);
    cleanup.current = () => {node?.removeEventListener('pointerdown',capture,true);resize?.disconnect();fitted?.dispose();controller.dispose();};
    api.addEventListener('gridPreDestroyed', cleanup.current);
  }, [owner, table, root, resetOnContainerResize, preferences]);
  useEffect(() => () => cleanup.current?.(), []);
  useLayoutEffect(() => { binding.current?.apply(); }, [scale, active,layoutRevision]);
  useLayoutEffect(() => { contentBinding.current?.schedule(); }, [active, scale, layoutRevision, revision, content?.rows, content?.totals]);
  const fit = useCallback((includeFlex = false) => {
    binding.current?.fit(includeFlex);
    return contentBinding.current?.fit();
  }, []);
  const columns=useCallback(<T,>(definitions:(ColDef<T>|ColGroupDef<T>)[])=>widthModeColumns(manualGridColumns(definitions),manualIds),[manualIds]);
  return {attach, strategy,columns,savedWidths:preferences.getWidths(),custom:Object.keys(preferences.getWidths()).length>0,error:preferences.getError(),layoutKey:current.current.layoutKey, reset: () => binding.current?.reset(),fit};
}

export const GridWidthContext=createContext<ReturnType<typeof useGridWidths>|null>(null);
function WidthHeader(params:IHeaderParams&{originalHeader?:ComponentType<IHeaderParams>;compactReset?:boolean}) {
  const widths=useContext(GridWidthContext),Original=params.originalHeader;
  return <span className="grid-width-header" data-compact={params.compactReset || undefined}>
    {!params.compactReset && <span>{Original?<Original {...params}/>:params.displayName}</span>}{widths&&<span className="grid-width-tools" data-page-chrome>
    <Button type="text" size="small" aria-label="恢复自动列宽" disabled={!widths.custom&&!widths.error} title={widths.error||'恢复自动列宽（保留排序、筛选和勾选）'}
      onPointerDown={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();widths.reset();}}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10a9 9 0 1 1 2.6 8.4M3 4v6h6" /></svg></Button>
    {widths.error&&<span className="sr-only" role="status">{widths.error}</span>}
  </span>}</span>;
}
export function useGridWidthColumns<T>(columns:(ColDef<T>|ColGroupDef<T>)[],
  savedWidths: Readonly<Record<string, number>>, preferred?: string) {
  return useMemo(()=>{
    const leaves:ColDef<T>[]=[];
    const collect=(items:(ColDef<T>|ColGroupDef<T>)[])=>items.forEach(column=>{
      if('children'in column)collect(column.children);
      else if(!column.hide&&!column.headerComponent&&column.resizable!==false)leaves.push(column);
    });
    collect(columns);
    const fits=(column:ColDef<T>)=>(savedWidths[column.colId??String(column.field)]
      ??column.minWidth??column.width??column.initialWidth??88)>=80;
    const reset=leaves.find(column=>(column.colId??column.field)===preferred&&(fits(column)||column.context?.columnContent))
      ??leaves.find(column=>column.context?.columnContent?.kind==='demand'&&fits(column))
      ??leaves.find(fits)??leaves[0];
    const visit=(items:(ColDef<T>|ColGroupDef<T>)[]):(ColDef<T>|ColGroupDef<T>)[]=>items.map(column=>{
      if('children'in column)return {...column,children:visit(column.children)};
      const {flex,initialFlex,...fixed}=column;
      const leaf:ColDef<T>=column.pinned&&(flex!==undefined||initialFlex!==undefined)?{...fixed,suppressAutoSize:column.suppressAutoSize??true}:column;
      if(column!==reset)return leaf;
      const params=leaf.headerComponentParams??{};
      return {...leaf,headerComponentParams:{...params,originalHeader:params.innerHeaderComponent,innerHeaderComponent:WidthHeader,
        compactReset:!fits(column)}};
    });
    return visit(columns);
  },[columns,savedWidths,preferred]);
}
