import { useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type { GridApi, SizeColumnsToContentStrategy } from 'ag-grid-community';
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
  return {attach, strategy, ...status, reset: () => binding.current?.reset()};
}

export function GridWidthControls({widths, disabled = false}: {widths: ReturnType<typeof useGridWidths>; disabled?: boolean}) {
  return <div className="grid-width-tools" data-page-chrome>
    {widths.error && <span role="status">{widths.error}</span>}
    <Button size="small" disabled={disabled || !widths.custom && !widths.error} onClick={widths.reset} title="清除本表手调列宽，保留排序、筛选和勾选">恢复自动列宽</Button>
  </div>;
}
