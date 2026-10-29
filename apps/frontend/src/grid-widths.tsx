import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { flushSync } from 'react-dom';
import type { ComponentType, RefObject } from 'react';
import type { ColDef, ColGroupDef, GridApi, IHeaderParams, SizeColumnsToContentStrategy } from 'ag-grid-community';
import Button from 'antd/es/button';
import { bindGridWidths, gridWidthPreferences } from './grid-width-state';
import { GridWidthOwner } from './grid-width-owner';
import { widthModeColumns } from './grid-manual-widths';

export function useGridWidths(table: string, root: RefObject<HTMLElement | null>, scale: number, active: boolean) {
  const owner = useContext(GridWidthOwner),[layoutRevision,setLayoutRevision]=useState(0),[dragging,setDragging]=useState<string|null>(null);
  const preferences=useMemo(()=>gridWidthPreferences(owner,table,()=>window.localStorage),[owner,table]);
  const revision=useSyncExternalStore(preferences.subscribe,preferences.getSnapshot);
  const manualIds=useMemo(()=>new Set([...Object.keys(preferences.getWidths()),...(dragging?[dragging]:[])]),[preferences,revision,dragging]);
  const current = useRef({scale, active,layoutKey:`${scale}:${layoutRevision}`,dragging});
  current.current = {scale, active,layoutKey:`${scale}:${layoutRevision}`,dragging};
  const binding = useRef<ReturnType<typeof bindGridWidths> | null>(null), cleanup = useRef<(() => void) | null>(null);
  const strategy = useMemo<SizeColumnsToContentStrategy>(() => ({type: 'fitCellContents', skipHeader: true}), []);
  const attach = useCallback((api: GridApi) => {
    cleanup.current?.();
    const controller = bindGridWidths(api, {owner, table, storage: () => window.localStorage, scale: () => current.current.scale,
      layoutKey:()=>current.current.layoutKey,
      activeDragId:()=>current.current.dragging,
      dragFinished:()=>setDragging(null),
      changed: (_custom, _error, reset) => {if(reset)setLayoutRevision(n=>n+1);}});
    binding.current = controller;
    const node = root.current;
    // Before AG starts its native mouse drag, publish the target's manual bounds
    // through the same React columnDefs path used by saved preferences.
    const capture=(event:PointerEvent)=>{
      if(event.button!==0)return;
      const target=event.target instanceof Element?event.target:null;
      const id=target?.closest('.ag-header-cell-resize')?.closest('.ag-header-cell')?.getAttribute('col-id');
      if(id){
        const column=api.getColumn(id);
        // Releasing a flex column's auto minimum must not shrink it before AG
        // captures the mouse drag's starting width. Native state owns this handoff.
        if(column?.getFlex())api.applyColumnState({state:[{colId:id,width:column.getActualWidth(),flex:null}]});
        flushSync(()=>setDragging(id));
      }
    };
    node?.addEventListener('pointerdown',capture,true);
    let width=node?.clientWidth??0;
    const resize=new ResizeObserver(()=>{const next=node?.clientWidth??0;if(next&&next!==width){width=next;setLayoutRevision(n=>n+1);}});
    if(node)resize.observe(node);
    cleanup.current = () => {node?.removeEventListener('pointerdown',capture,true);resize.disconnect();controller.dispose();};
    api.addEventListener('gridPreDestroyed', cleanup.current);
  }, [owner, table, root]);
  useEffect(() => () => cleanup.current?.(), []);
  useLayoutEffect(() => { binding.current?.apply(); }, [scale, active,layoutRevision]);
  const fit=useCallback(()=>binding.current?.fit(),[]);
  const columns=useCallback(<T,>(definitions:(ColDef<T>|ColGroupDef<T>)[])=>widthModeColumns(definitions,manualIds),[manualIds]);
  return {attach, strategy,columns,custom:Object.keys(preferences.getWidths()).length>0,error:preferences.getError(),layoutKey:current.current.layoutKey, reset: () => binding.current?.reset(),fit};
}

export const GridWidthContext=createContext<ReturnType<typeof useGridWidths>|null>(null);
function WidthHeader(params:IHeaderParams&{originalHeader?:ComponentType<IHeaderParams>}) {
  const widths=useContext(GridWidthContext),Original=params.originalHeader;
  return <span className="grid-width-header"><span>{Original?<Original {...params}/>:params.displayName}</span>{widths&&<span className="grid-width-tools" data-page-chrome>
    <Button type="text" size="small" aria-label="恢复自动列宽" disabled={!widths.custom&&!widths.error} title={widths.error||'恢复自动列宽（保留排序、筛选和勾选）'}
      onPointerDown={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();widths.reset();}}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10a9 9 0 1 1 2.6 8.4M3 4v6h6" /></svg></Button>
    {widths.error&&<span className="sr-only" role="status">{widths.error}</span>}
  </span>}</span>;
}
// Use the native header extension point. One action per grid, without a toolbar row.
export function useGridWidthColumns<T>(columns:(ColDef<T>|ColGroupDef<T>)[]) {
  return useMemo(()=>{
    let added=false;
    const visit=(items:(ColDef<T>|ColGroupDef<T>)[]):(ColDef<T>|ColGroupDef<T>)[]=>items.map(column=>{
      if('children'in column)return {...column,children:visit(column.children)};
      // Pinned columns cannot flex; leaving flex set also makes native reset skip their width.
      const {flex,initialFlex,...fixed}=column;
      const leaf:ColDef<T>=column.pinned&&(flex!==undefined||initialFlex!==undefined)?{...fixed,suppressAutoSize:column.suppressAutoSize??true}:column;
      if(added)return leaf;
      if(leaf.headerComponent||(leaf.minWidth??leaf.width??leaf.initialWidth??88)<80)return leaf;
      added=true;
      const params=leaf.headerComponentParams??{};
      return {...leaf,headerComponentParams:{...params,originalHeader:params.innerHeaderComponent,innerHeaderComponent:WidthHeader}};
    });
    return visit(columns);
  },[columns]);
}
