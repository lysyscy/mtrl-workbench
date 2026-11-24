import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import type { GridApi } from 'ag-grid-community';
import { ReadGrid } from './business-grid';
import { pageGridGeometry } from './grid';
import { boundedGridMinHeight, estimateBoundedGridHeight } from './bounded-grid-layout';

export interface BoundedGridMetrics {
  naturalHeight: number;
  minHeight: number;
  hasHorizontalScroll: boolean;
}

type ReadGridBaseProps<T> = Omit<Parameters<typeof ReadGrid<T>>[0], 'domLayout'>;

export interface BoundedGridProps<T> extends ReadGridBaseProps<T> {
  /** Minimum readable data rows when height is constrained (default 4). */
  minRows?: number;
  /** Optional CSS max-height cap for scroll-body modals or page sections. */
  maxHeight?: string | undefined;
  /** Participates as a flex-shrinking bounded pane inside a `pane` modal. */
  fill?: boolean;
  /** Externally allocated pixel height (e.g. multi-table pane split). */
  height?: number | undefined;
  /** Reports measured natural/min heights to a parent pane coordinator. */
  onMetrics?: ((metrics: BoundedGridMetrics) => void) | undefined;
}

/**
 * Shared bounded inner-scroll data grid primitive built on AG Grid native `domLayout="normal"`.
 * - Short tables hug their actual content height (no empty interior gap).
 * - Overflowing tables scroll vertically inside the grid with pinned headers and pinned bottom totals.
 * - Accounts for actual rendered wrapped row heights and horizontal scrollbar presence.
 */
export function BoundedGrid<T>({
  rows,
  totals,
  scale: suppliedScale,
  className = '',
  style,
  grid = {},
  minRows = 4,
  maxHeight,
  fill = false,
  height,
  onMetrics,
  ...rest
}: BoundedGridProps<T>) {
  const scale = suppliedScale ?? (Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1);
  const totalsCount = totals?.length ?? 0;
  const wrapperRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<GridApi<T> | null>(null);
  const onMetricsRef = useRef(onMetrics);
  onMetricsRef.current = onMetrics;

  const [metrics, setMetrics] = useState<BoundedGridMetrics>(() => ({
    naturalHeight: estimateBoundedGridHeight({ rowCount: rows.length, pinnedBottomCount: totalsCount, scale }),
    minHeight: boundedGridMinHeight({ minRows, rowCount: rows.length, pinnedBottomCount: totalsCount, scale }),
    hasHorizontalScroll: false,
  }));

  const publish = useCallback((next: BoundedGridMetrics) => {
    setMetrics(previous => {
      if (
        Math.abs(previous.naturalHeight - next.naturalHeight) < 1
        && Math.abs(previous.minHeight - next.minHeight) < 1
        && previous.hasHorizontalScroll === next.hasHorizontalScroll
      ) {
        return previous;
      }
      return next;
    });
  }, []);

  useEffect(() => {
    onMetricsRef.current?.(metrics);
  }, [metrics]);

  const measure = useCallback(() => {
    const wrapper = wrapperRef.current;
    const gridEl = wrapper?.querySelector<HTMLElement>('.business-grid');
    const api = apiRef.current;
    const geom = pageGridGeometry(scale);
    if (!gridEl || !api || api.isDestroyed()) {
      publish({
        naturalHeight: estimateBoundedGridHeight({ rowCount: rows.length, pinnedBottomCount: totalsCount, scale }),
        minHeight: boundedGridMinHeight({ minRows, rowCount: rows.length, pinnedBottomCount: totalsCount, scale }),
        hasHorizontalScroll: false,
      });
      return;
    }

    const headerEl = gridEl.querySelector<HTMLElement>('.ag-header, .ag-grid-pinned-top-rows');
    const headerH = headerEl && headerEl.getBoundingClientRect().height > 0
      ? headerEl.getBoundingClientRect().height
      : geom.headerHeight;

    const pinnedEl = gridEl.querySelector<HTMLElement>('.ag-grid-pinned-bottom-rows, .ag-floating-bottom');
    const pinnedH = totalsCount > 0
      ? (pinnedEl && pinnedEl.getBoundingClientRect().height > 0
        ? pinnedEl.getBoundingClientRect().height
        : totalsCount * geom.rowHeight)
      : 0;

    const hViewport = gridEl.querySelector<HTMLElement>('.ag-body-horizontal-scroll-viewport, .ag-grid-viewport');
    const hScrollEl = gridEl.querySelector<HTMLElement>('.ag-body-horizontal-scroll');
    const hScrollVisible = Boolean(hScrollEl && !hScrollEl.classList.contains('ag-invisible') && !hScrollEl.classList.contains('ag-hidden'));
    const needsHScroll = Boolean(
      api.getGridOption('alwaysShowHorizontalScroll')
      || hScrollVisible
      || (hViewport && hViewport.scrollWidth > hViewport.clientWidth + 1),
    );
    const hScrollH = needsHScroll && !api.getGridOption('suppressHorizontalScroll')
      ? (hScrollEl && hScrollVisible && hScrollEl.offsetHeight > 0 ? hScrollEl.offsetHeight : Math.ceil(15 * scale))
      : 0;

    const count = api.getDisplayedRowCount();
    let bodyH = Math.max(Math.ceil(geom.rowHeight * 1.5), 48);
    if (count > 0) {
      const last = api.getDisplayedRowAtIndex(count - 1);
      const measured = last && typeof last.rowTop === 'number' && typeof last.rowHeight === 'number'
        ? last.rowTop + last.rowHeight
        : count * geom.rowHeight;
      bodyH = measured > 0 ? measured : count * geom.rowHeight;
    }

    const naturalHeight = Math.ceil(headerH + bodyH + pinnedH + hScrollH + 2);
    const effectiveMinRows = count > 0 ? Math.min(count, Math.max(1, minRows)) : 1;
    let minBodyH = count > 0 ? effectiveMinRows * geom.rowHeight : Math.max(Math.ceil(geom.rowHeight * 1.5), 48);
    if (count > 0) {
      const floorRow = api.getDisplayedRowAtIndex(Math.min(count, Math.ceil(effectiveMinRows)) - 1);
      if (floorRow && typeof floorRow.rowTop === 'number' && typeof floorRow.rowHeight === 'number') {
        const floorMeasured = floorRow.rowTop + floorRow.rowHeight;
        if (floorMeasured > 0) {
          minBodyH = Math.min(floorMeasured, Math.ceil(effectiveMinRows * geom.rowHeight * 2));
        }
      }
    }
    const minHeight = Math.min(naturalHeight, Math.ceil(headerH + minBodyH + pinnedH + hScrollH + 2));
    publish({ naturalHeight, minHeight, hasHorizontalScroll: needsHScroll });
  }, [minRows, publish, rows.length, scale, totalsCount]);

  useLayoutEffect(() => {
    measure();
  }, [measure, rows]);

  const measureRef = useRef(measure);
  measureRef.current = measure;

  const boxStyle: CSSProperties = { ...style };
  if (height !== undefined) {
    boxStyle.height = `${Math.max(0, Math.floor(height))}px`;
    boxStyle.flex = 'none';
  } else if (fill) {
    boxStyle.flex = `0 1 ${metrics.naturalHeight}px`;
    boxStyle.minHeight = `${metrics.minHeight}px`;
    boxStyle.maxHeight = maxHeight ? `min(${metrics.naturalHeight}px, ${maxHeight})` : `${metrics.naturalHeight}px`;
  } else if (maxHeight) {
    boxStyle.height = `min(${metrics.naturalHeight}px, ${maxHeight})`;
    boxStyle.flex = 'none';
  } else {
    boxStyle.height = `${metrics.naturalHeight}px`;
    boxStyle.flex = 'none';
  }

  const { onGridReady, onFirstDataRendered, onModelUpdated, onRowDataUpdated, onGridSizeChanged, onColumnResized, ...gridRest } = grid;

  return (
    <div ref={wrapperRef} className={`bounded-grid${fill ? ' bounded-grid-fill' : ''}${className ? ` ${className}` : ''}`} style={boxStyle}>
      <ReadGrid<T>
        {...rest}
        rows={rows}
        {...(totals === undefined ? {} : { totals })}
        scale={scale}
        domLayout="normal"
        grid={{
          ...gridRest,
          onGridReady: event => {
            apiRef.current = event.api;
            const gridEl = wrapperRef.current?.querySelector<HTMLElement>('.business-grid');
            const observer = new ResizeObserver(() => measureRef.current());
            for (const selector of ['.ag-header', '.ag-grid-pinned-top-rows', '.ag-grid-pinned-bottom-rows', '.ag-floating-bottom', '.ag-body-horizontal-scroll', '.ag-grid-scrolling-rows', '.ag-center-cols-container']) {
              const target = gridEl?.querySelector<HTMLElement>(selector);
              if (target) observer.observe(target);
            }
            const mutations = new MutationObserver(() => measureRef.current());
            const scrollbar = gridEl?.querySelector<HTMLElement>('.ag-body-horizontal-scroll');
            if (scrollbar) mutations.observe(scrollbar, { attributes: true, attributeFilter: ['class', 'style'] });
            event.api.addEventListener('gridPreDestroyed', () => {
              apiRef.current = null;
              observer.disconnect();
              mutations.disconnect();
            });
            measureRef.current();
            onGridReady?.(event);
          },
          onFirstDataRendered: event => {
            measureRef.current();
            onFirstDataRendered?.(event);
          },
          onModelUpdated: event => {
            measureRef.current();
            onModelUpdated?.(event);
          },
          onRowDataUpdated: event => {
            measureRef.current();
            onRowDataUpdated?.(event);
          },
          onGridSizeChanged: event => {
            measureRef.current();
            onGridSizeChanged?.(event);
          },
          onColumnResized: event => {
            measureRef.current();
            onColumnResized?.(event);
          },
        }}
      />
    </div>
  );
}
