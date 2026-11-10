import { useEffect, useRef, useState } from 'react';
import type { GridOptions } from 'ag-grid-community';
import { GridRowDragImage } from './grid-row-drag-image';
import { useWorkspaceReducedMotion } from './workspace-motion';

type DragOptions<T> = {
  disabled: boolean;
  sourceId: (row: T) => number | null;
  targetId: (source: T, target: T) => number | null;
  orderFor: (source: T) => number[];
  save: (source: T, previous: number[], order: number[]) => Promise<unknown>;
};
type Drag<T> = { source: T; id: number; previous: number[]; order: number[] };
const sameOrder = (a: number[], b: number[]) => a.length === b.length && a.every((id, index) => id === b[index]);

// The grid supplies pointer and row animation. Callers supply complete sibling
// orders, which can include rows hidden by a filter or collapsed into a group.
export function useGridRowDrag<T>({ disabled, sourceId, targetId, orderFor, save }: DragOptions<T>) {
  const reduced = useWorkspaceReducedMotion();
  const current = useRef<Drag<T> | null>(null), saving = useRef(false);
  const [preview, setPreview] = useState<Drag<T> | null>(null);
  const [rowId, setRowId] = useState<string | null>(null);
  function clear() {
    current.current = null;
    setRowId(null);
    if (!saving.current) setPreview(null);
  }
  useEffect(() => { if (disabled) clear(); }, [disabled]);
  function getTarget(source: T | undefined, target: T | undefined) {
    if (disabled || saving.current || !source || !target) return null;
    return targetId(source, target);
  }
  function move(target: T | undefined) {
    const drag = current.current;
    if (!drag) return;
    const id = getTarget(drag.source, target);
    if (id === drag.id) return;
    const to = id === null ? -1 : drag.previous.indexOf(id);
    const order = to < 0 ? drag.previous : drag.previous.filter(id => id !== drag.id);
    if (to >= 0) order.splice(to, 0, drag.id);
    if (!sameOrder(drag.order, order)) {
      const next = { ...drag, order };
      current.current = next;
      setPreview(next);
    }
  }
  const grid: GridOptions<T> = {
    suppressRowDrag: disabled,
    dragAndDropImageComponent: GridRowDragImage,
    animateRows: rowId !== null && !reduced,
    isRowValidDropPosition: p => ({ allowed: getTarget(p.source.data, p.overNode?.data) !== null, highlight: true }),
    onRowDragEnter: ({ node }) => {
      if (disabled || saving.current || !node.data || node.id === undefined) return;
      const source = node.data, id = sourceId(source), previous = orderFor(source);
      if (id === null || !previous.includes(id)) return;
      current.current = { source, id, previous, order: previous };
      setRowId(node.id);
    },
    onRowDragMove: ({ overNode }) => move(overNode?.data),
    onRowDragEnd: ({ overNode }) => {
      const drag = current.current;
      if (!drag || getTarget(drag.source, overNode?.data) === null || sameOrder(drag.previous, drag.order) ||
          !sameOrder(drag.previous, orderFor(drag.source))) { clear(); return; }
      saving.current = true;
      clear();
      void save(drag.source, drag.previous, drag.order).finally(() => { saving.current = false; setPreview(null); });
    },
    onRowDragCancel: clear,
    onRowDragLeave: clear,
  };
  return { grid, preview, rowId };
}

export function rowsInOrder<T>(rows: T[], order: number[] | undefined, idOf: (row: T) => number): T[] {
  if (!order) return rows;
  const ranks = new Map(order.map((id, index) => [id, index]));
  return [...rows].sort((a, b) => (ranks.get(idOf(a)) ?? order.length) - (ranks.get(idOf(b)) ?? order.length));
}
