import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ComponentType, RefObject } from 'react';
import type { ColDef, ColGroupDef, GridApi, IHeaderParams, SizeColumnsToContentStrategy } from 'ag-grid-community';
import Button from 'antd/es/button';
import { freezeGridFlex } from './grid';
import { bindGridWidths } from './grid-width-state';
import { GridWidthOwner } from './grid-width-owner';

export function useGridWidths(table: string, root: RefObject<HTMLElement | null>, scale: number, active: boolean) {
  const owner = useContext(GridWidthOwner), current = useRef({scale, active});
  current.current = {scale, active};
  const binding = useRef<ReturnType<typeof bindGridWidths> | null>(null), cleanup = useRef<(() => void) | null>(null);
  const [status, setStatus] = useState({custom: false, error: ''});
  const editing = (api: GridApi) => api.getEditingCells().length > 0 || Boolean(root.current?.contains(document.activeElement) && document.activeElement?.matches('input:not([type=checkbox]):not([type=radio]),select,textarea,[contenteditable=true]'));
  const strategy = useMemo<SizeColumnsToContentStrategy>(() => ({type: 'fitCellContents', continuous: true, skipHeader: true,
    shouldAutoSizeColumns: ({api, reason}) => reason !== 'viewportChanged' && current.current.active && !editing(api),
  }), [root]);
  const attach = useCallback((api: GridApi) => {
    cleanup.current?.();
    const controller = bindGridWidths(api, {owner, table, storage: () => window.localStorage, scale: () => current.current.scale,
      changed: (custom, error) => setStatus({custom, error})});
    binding.current = controller;
    const node = root.current, unfreeze = node ? freezeGridFlex(api, node) : () => {};
    let frame = 0;
    const released = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => { if (!api.isDestroyed() && current.current.active && !editing(api)) controller.fit(); }); };
    node?.addEventListener('focusout', released);
    api.addEventListener('cellEditingStopped', released);
    cleanup.current = () => { cancelAnimationFrame(frame); node?.removeEventListener('focusout', released); if (!api.isDestroyed()) api.removeEventListener('cellEditingStopped', released); unfreeze(); controller.dispose(); };
    api.addEventListener('gridPreDestroyed', cleanup.current);
  }, [owner, table, root]);
  useEffect(() => () => cleanup.current?.(), []);
  useLayoutEffect(() => { binding.current?.apply(); if (active) binding.current?.fit(); }, [scale, active]);
  return {attach, strategy, ...status, reset: () => binding.current?.reset(), fit: () => binding.current?.fit()};
}

export const GridWidthContext=createContext<ReturnType<typeof useGridWidths>|null>(null);
function WidthHeader(params:IHeaderParams&{originalHeader?:ComponentType<IHeaderParams>}) {
  const widths=useContext(GridWidthContext),Original=params.originalHeader;
  return <span className="grid-width-header"><span>{Original?<Original {...params}/>:params.displayName}</span>{widths&&<span className="grid-width-tools" data-page-chrome>
    <Button type="text" size="small" aria-label="恢复自动列宽" disabled={!widths.custom&&!widths.error} title={widths.error||'恢复自动列宽（保留排序、筛选和勾选）'}
      onPointerDown={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();widths.reset();}}>↺</Button>
    {widths.error&&<span className="sr-only" role="status">{widths.error}</span>}
  </span>}</span>;
}
// Use the native header extension point. One action per grid, without a toolbar row.
export function useGridWidthColumns<T>(columns:(ColDef<T>|ColGroupDef<T>)[]) {
  return useMemo(()=>{
    let added=false;
    const visit=(items:(ColDef<T>|ColGroupDef<T>)[]):(ColDef<T>|ColGroupDef<T>)[]=>items.map(column=>{
      if(added)return column;
      if('children'in column)return {...column,children:visit(column.children)};
      if(column.headerComponent||(column.minWidth??column.width??column.initialWidth??88)<80)return column;
      added=true;
      const params=column.headerComponentParams??{};
      return {...column,headerComponentParams:{...params,originalHeader:params.innerHeaderComponent,innerHeaderComponent:WidthHeader}};
    });
    return visit(columns);
  },[columns]);
}
