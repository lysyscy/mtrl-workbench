export interface BoundedGridEstimateInput {
  rowCount: number;
  pinnedBottomCount?: number;
  scale?: number;
  hasHorizontalScroll?: boolean;
}

export interface BoundedGridMinInput {
  minRows: number;
  rowCount: number;
  pinnedBottomCount?: number;
  scale?: number;
  hasHorizontalScroll?: boolean;
}

export interface BoundedPaneSpec {
  id: string;
  naturalHeight: number;
  minHeight: number;
  weight: number;
}

const BASE_ROW_HEIGHT = 36;
const BASE_HEADER_HEIGHT = 34;
const BASE_HSCROLL_HEIGHT = 15;
const GRID_BORDER_PX = 2;

export function estimateBoundedGridHeight({
  rowCount,
  pinnedBottomCount = 0,
  scale = 1,
  hasHorizontalScroll = false,
}: BoundedGridEstimateInput): number {
  const rowHeight = BASE_ROW_HEIGHT * scale;
  const headerHeight = BASE_HEADER_HEIGHT * scale;
  const bodyHeight = rowCount > 0 ? rowCount * rowHeight : Math.max(Math.ceil(rowHeight * 1.5), 48);
  const pinnedHeight = pinnedBottomCount * rowHeight;
  const hScroll = hasHorizontalScroll ? Math.ceil(BASE_HSCROLL_HEIGHT * scale) : 0;
  return Math.ceil(headerHeight + bodyHeight + pinnedHeight + hScroll + GRID_BORDER_PX);
}

export function boundedGridMinHeight({
  minRows,
  rowCount,
  pinnedBottomCount = 0,
  scale = 1,
  hasHorizontalScroll = false,
}: BoundedGridMinInput): number {
  const rowHeight = BASE_ROW_HEIGHT * scale;
  const headerHeight = BASE_HEADER_HEIGHT * scale;
  const effectiveRows = rowCount > 0 ? Math.min(rowCount, Math.max(1, minRows)) : 1;
  const bodyHeight = rowCount > 0 ? effectiveRows * rowHeight : Math.max(Math.ceil(rowHeight * 1.5), 48);
  const pinnedHeight = pinnedBottomCount * rowHeight;
  const hScroll = hasHorizontalScroll ? Math.ceil(BASE_HSCROLL_HEIGHT * scale) : 0;
  return Math.ceil(headerHeight + bodyHeight + pinnedHeight + hScroll + GRID_BORDER_PX);
}

/**
 * Water-filling proportional height allocator for 1..N bounded scrollable panes:
 * - Short content hugs its natural height without leaving empty space.
 * - When one pane is short and another is long, the short pane yields its surplus.
 * - When multiple panes exceed their targets, remaining space is split by `weight`
 *   while guaranteeing each pane's `min(naturalHeight, minHeight)` floor.
 * - When even the floors exceed `available` (very short viewport / 1.4x scale),
 *   every pane keeps its readable floor so outer container fallback scroll takes over.
 */
export function allocateBoundedHeights(
  available: number,
  panes: readonly BoundedPaneSpec[],
): Record<string, number> {
  const result: Record<string, number> = {};
  if (!panes.length) return result;

  const normalized = panes.map(pane => {
    const natural = Math.max(0, Math.ceil(pane.naturalHeight));
    const effectiveMin = Math.min(natural, Math.max(0, Math.ceil(pane.minHeight)));
    const weight = pane.weight > 0 ? pane.weight : 1;
    return { id: pane.id, natural, effectiveMin, weight };
  });

  const budget = Math.max(0, Math.floor(available));
  const totalNatural = normalized.reduce((sum, pane) => sum + pane.natural, 0);
  if (totalNatural <= budget) {
    for (const pane of normalized) result[pane.id] = pane.natural;
    return result;
  }

  const totalMin = normalized.reduce((sum, pane) => sum + pane.effectiveMin, 0);
  if (totalMin >= budget) {
    for (const pane of normalized) result[pane.id] = pane.effectiveMin;
    return result;
  }

  let remaining = budget;
  let active = [...normalized];

  while (active.length > 0) {
    const totalWeight = active.reduce((sum, pane) => sum + pane.weight, 0);
    let locked = false;
    const nextActive: typeof active = [];

    for (const pane of active) {
      const target = remaining * (pane.weight / totalWeight);
      if (pane.natural <= target) {
        result[pane.id] = pane.natural;
        remaining -= pane.natural;
        locked = true;
      } else {
        nextActive.push(pane);
      }
    }
    if (locked) {
      active = nextActive;
      continue;
    }

    const afterFloor: typeof active = [];
    for (const pane of active) {
      const target = remaining * (pane.weight / totalWeight);
      if (pane.effectiveMin >= target) {
        result[pane.id] = pane.effectiveMin;
        remaining -= pane.effectiveMin;
        locked = true;
      } else {
        afterFloor.push(pane);
      }
    }
    if (locked) {
      active = afterFloor;
      continue;
    }

    let used = 0;
    for (let i = 0; i < active.length; i += 1) {
      const pane = active[i]!;
      const share = i === active.length - 1
        ? Math.max(pane.effectiveMin, Math.min(pane.natural, Math.floor(remaining - used)))
        : Math.max(pane.effectiveMin, Math.min(pane.natural, Math.floor(remaining * (pane.weight / totalWeight))));
      result[pane.id] = share;
      used += share;
    }
    break;
  }

  return result;
}
