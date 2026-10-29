import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ComponentType, RefObject } from 'react';
import type { ColDef, ColGroupDef, GridApi, IHeaderParams, SizeColumnsToContentStrategy } from 'ag-grid-community';
import Button from 'antd/es/button';
import { bindGridWidths } from './grid-width-state';
import { GridWidthOwner } from './grid-width-owner';

export function useGridWidths(table: string, root: RefObject<HTMLElement | null>, scale: number, active: boolean) {
  const owner = useContext(GridWidthOwner),[layoutRevision,setLayoutRevision]=useState(0),current = useRef({scale, active,layoutKey:`${scale}:${layoutRevision}`});
  current.current = {scale, active,layoutKey:`${scale}:${layoutRevision}`};
  const binding = useRef<ReturnType<typeof bindGridWidths> | null>(null), cleanup = useRef<(() => void) | null>(null);
  const [status, setStatus] = useState({custom: false, error: ''});
  const strategy = useMemo<SizeColumnsToContentStrategy>(() => ({type: 'fitCellContents', skipHeader: true}), []);
  const attach = useCallback((api: GridApi) => {
    cleanup.current?.();
    const controller = bindGridWidths(api, {owner, table, storage: () => window.localStorage, scale: () => current.current.scale,
      layoutKey:()=>current.current.layoutKey,
      changed: (custom, error, reset) => {setStatus({custom, error});if(reset)setLayoutRevision(n=>n+1);}});
    binding.current = controller;
    const node = root.current;
    let width=node?.clientWidth??0;
    const resize=new ResizeObserver(()=>{const next=node?.clientWidth??0;if(next&&next!==width){width=next;setLayoutRevision(n=>n+1);}});
    if(node)resize.observe(node);
    cleanup.current = () => {resize.disconnect();controller.dispose();};
    api.addEventListener('gridPreDestroyed', cleanup.current);
  }, [owner, table, root]);
  useEffect(() => () => cleanup.current?.(), []);
  useLayoutEffect(() => { binding.current?.apply(); }, [scale, active,layoutRevision]);
  const fit=useCallback(()=>binding.current?.fit(),[]);
  return {attach, strategy, ...status,layoutKey:current.current.layoutKey, reset: () => binding.current?.reset(),fit};
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
