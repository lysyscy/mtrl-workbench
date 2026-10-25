import { useLayoutEffect } from 'react';
import type { GridApi, ICellRendererParams, IRowNode } from 'ag-grid-community';
import type { InventoryRow } from './inventory-api';

const pending = new WeakSet<GridApi<InventoryRow>>();

export function measureInventoryRows(api: GridApi<InventoryRow> | null, root: HTMLElement | null) {
  if (!api || !root || api.isDestroyed() || pending.has(api)) return;
  pending.add(api);
  queueMicrotask(() => {
    pending.delete(api);
    if (api.isDestroyed() || !root.clientWidth) return;
    const cells = [...root.querySelectorAll<HTMLElement>('.inventory-cell-text[data-row]')];
    const first = cells[0], cell = first?.closest<HTMLElement>('.ag-cell');
    const row = first?.closest<HTMLElement>('.ag-row');
    if (!cell || !row) return;
    const css = getComputedStyle(cell);
    const padding = [css.paddingTop, css.paddingBottom, css.borderTopWidth, css.borderBottomWidth]
      .reduce((sum, value) => sum + (parseFloat(value) || 0), 0);
    const border = row.offsetHeight - row.clientHeight;
    const minimum = api.getGridOption('rowHeight') ?? 36;
    const heights = new Map<IRowNode<InventoryRow>, number>();
    // Read all natural content sizes before any row-height write can invalidate layout.
    for (const content of cells) {
      const node = api.getRowNode(content.dataset.row!);
      if (node) heights.set(node, Math.max(heights.get(node) ?? minimum,
        Math.ceil(content.getBoundingClientRect().height + padding + border)));
    }
    let changed = false;
    for (const [node, height] of heights) {
      if (Math.abs((node.rowHeight ?? minimum) - height) < .5) continue;
      node.setRowHeight(height); changed = true;
    }
    if (changed) api.onRowHeightChanged();
  });
}

export function InventoryText(params: ICellRendererParams<InventoryRow>) {
  useLayoutEffect(() => measureInventoryRows(params.api, params.eGridCell.closest('.inventory-grid')));
  return <div className="inventory-cell-text" data-row={params.node.rowPinned ? undefined : params.node.id}>{params.value ?? ''}</div>;
}
