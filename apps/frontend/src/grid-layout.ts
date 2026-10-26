import { createElement, Fragment, useLayoutEffect, useRef, useState } from 'react';
import { createPortal, flushSync } from 'react-dom';
import type { ReactNode, RefObject } from 'react';
import type { GridApi, IRowNode } from 'ag-grid-community';
import { loadElementFonts, loadTextFonts } from './appearance-ready';
import { tableWidths } from './table-widths';

// Opt-in preparation. Rich cells render through a portal in the owning React tree,
// keeping their real router, appearance and editor context during bounded measurement.
export interface TextGridColumn<T> {
  id: string;
  text: (row: T, pinned?: boolean) => string;
  wrap: boolean;
  className?: string;
  render?: (row: T, pinned: boolean) => ReactNode;
  signature?: (row: T, pinned: boolean) => string;
}

// React/AG treats a replacement renderer definition as a new component even if
// row IDs and values are unchanged. Defer that replacement through an input session.
export function useRetainedGridColumns<T>(columns: T[], root: RefObject<HTMLElement | null>) {
  const [displayed, setDisplayed] = useState(columns);
  useLayoutEffect(() => {
    const node = root.current; let frame = 0;
    const publish = () => {
      if (node?.contains(document.activeElement) && document.activeElement?.matches('input,select,textarea')) return;
      setDisplayed(columns);
    };
    const released = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(publish); };
    publish(); node?.addEventListener('focusout', released);
    return () => { cancelAnimationFrame(frame); node?.removeEventListener('focusout', released); };
  }, [columns, root]);
  return displayed;
}

export function useTextGridLayout<T>({ root, active, rows, totals, columns, rowId, minimum, headerMinimum, scope, identity, fontRoot }: {
  root: RefObject<HTMLElement | null>; fontRoot?: RefObject<HTMLElement | null>; active: boolean; rows: T[]; totals: T[];
  scope: string; identity: string; columns: TextGridColumn<T>[]; rowId: (row: T) => string; minimum: number; headerMinimum: number;
}) {
  const [measurement, setMeasurement] = useState<ReactNode>(null);
  const [api, attach] = useState<GridApi<T> | null>(null);
  const [state, setState] = useState<'preparing' | 'updating' | 'ready' | 'error'>('preparing');
  const [error, setError] = useState(''), [retry, setRetry] = useState(0);
  const configured = useRef<GridApi<T> | null>(null), publishedRows = useRef<T[] | null>(null), publishedTotals = useRef<T[] | null>(null), rowSize = useRef({minimum,rowId});
  rowSize.current = {minimum,rowId};
  const ready = useRef(false), heights = useRef(new Map<string, number>());
  const cache = useRef(new Map<string, number>()), geometry = useRef(''), userWidths = useRef(false);
  const readingAnchor = useRef<{id: string; offset: number; header: number; scope: string} | null>(null), appliedWidth = useRef(0), appliedHeight = useRef(0);
  const restoredTop = useRef<number | null>(null), appliedGeometry = useRef('');
  const headerSize = useRef({ key: '', height: headerMinimum });
  const prepared = useRef<{ grid: GridApi<T>; rows: T[]; totals: T[]; columns: TextGridColumn<T>[]; rowId: (row: T) => string; geometry: string; scope: string; identity: string } | null>(null);
  const fitted = useRef(''), appliedScope = useRef(scope), appliedIdentity = useRef(identity);
  useLayoutEffect(() => {
    const node = root.current;
    if (!api || !node || !active) return;
    const grid = api;
    if (configured.current !== grid) { ready.current = false; setState('preparing'); grid.setGridOption('getRowHeight', p => p.data ? heights.current.get(rowSize.current.rowId(p.data)) ?? rowSize.current.minimum : rowSize.current.minimum); configured.current = grid; publishedRows.current = null; publishedTotals.current = null; }
    let disposed = false, version = 0, frame = 0, anchorFrame = 0, pendingEdit = false, preparing = false;
    const cancelled = (run: number) => disposed || run !== version || grid.isDestroyed();
    const editable = () => grid.getEditingCells().length > 0 || node.contains(document.activeElement) && document.activeElement?.matches('input,select,textarea');
    const geometryStamp = () => {
      const css = getComputedStyle(node!.querySelector('.ag-root') ?? node!);
      return `${node!.clientWidth}:${node!.clientHeight}:${css.fontFamily}:${css.fontSize}:${css.fontWeight}:${css.lineHeight}:${minimum}:${headerMinimum}:${grid.getAllDisplayedColumns().map(c => `${c.getColId()}:${c.getActualWidth()}:${c.getColDef().headerName ?? ''}`).join('|')}`;
    };
    const schedule = () => { if (ready.current) setState('updating'); version++; cancelAnimationFrame(frame); frame = requestAnimationFrame(() => { void prepare(version); }); };
    async function prepare(run: number) {
      if (cancelled(run) || !node!.clientWidth) return;
      // Retained pages and duplicate resize notifications reuse the applied layout.
      // Immutable row/column inputs plus actual geometry still invalidate on refresh, scale or manual resize.
      const previous = prepared.current;
      if (previous?.grid === grid && previous.rows === rows && previous.totals === totals && previous.columns === columns && previous.rowId === rowId && previous.scope === scope && previous.identity === identity && previous.geometry === geometryStamp()) {
        setState('ready'); setError(''); return;
      }
      if (editable()) { pendingEdit = true; return; }
      pendingEdit = false;
      const started = performance.now(); preparing = true;
      let host: HTMLDivElement | undefined;
      try {
        const wrapping = columns.filter(c => c.wrap || c.render);
        const body = [...new Set(wrapping.flatMap(column => rows.map(row => column.text(row))))].join('') + '0123456789,.-';
        const footer = columns.flatMap(column => totals.map(row => column.text(row, true))).join('');
        await Promise.all([fontRoot?.current ? loadElementFonts(fontRoot.current) : Promise.resolve(), loadTextFonts(body, [400]), loadTextFonts(footer, [600]),
          loadTextFonts(grid.getAllDisplayedColumns().map(c => c.getColDef().headerName ?? '').join(''), [500])]);
        if (cancelled(run) || !node!.clientWidth || editable()) return;
        const fontsAt = performance.now();
        const displayed = grid.getAllDisplayedColumns();
        const viewport = node!.querySelector<HTMLElement>('.ag-grid-viewport,.ag-body-viewport');
        if (!viewport) throw new Error('表格尺寸准备失败，请重试。');
        // Reserve the vertical scrollbar before measuring widths, including an empty result.
        const available = viewport.clientWidth - (node!.querySelector<HTMLElement>('.ag-body-vertical-scroll')?.offsetWidth ?? 0);
        const widthKey = `${available}:${minimum}:${getComputedStyle(node!).font}`;
        const context = document.createElement('canvas').getContext('2d')!;
        host = document.createElement('div'); host.className = 'ag-row grid-layout-measure'; host.ariaHidden = 'true'; host.inert = true;
        Object.assign(host.style, { display: 'block', position: 'fixed', left: '-100000px', top: '0', height: 'auto', width: 'max-content', visibility: 'hidden', pointerEvents: 'none' });
        node!.querySelector('.ag-root')!.append(host);
        const sample = document.createElement('div'); sample.className = 'ag-cell ag-cell-wrap-text'; host.append(sample);
        const css = getComputedStyle(sample);
        const sampleText = document.createElement('div'); sampleText.className = wrapping[0]?.className ?? ''; sampleText.textContent = '国0'; sample.append(sampleText);
        const textCss = getComputedStyle(sampleText);
        const bodyFont = `${textCss.fontSize} ${textCss.fontFamily}`, singleLine = Math.ceil(parseFloat(textCss.lineHeight) + parseFloat(css.paddingTop) + parseFloat(css.paddingBottom) + 2);
        const canFitLine = textCss.letterSpacing === 'normal' && textCss.wordSpacing === '0px';
        context.font = css.font;
        const padding = parseFloat(css.paddingLeft) + parseFloat(css.paddingRight) || 16;
        let plannedWidths = displayed.map(col => col.getActualWidth());
        if (!userWidths.current && (fitted.current !== widthKey || displayed.some(col => col.getActualWidth() < (col.getColDef().minWidth ?? 0)))) {
          const preferred = displayed.map(col => {
            const spec = columns.find(c => c.id === col.getColId());
            let width = col.getColDef().minWidth ?? col.getActualWidth();
            if (spec) for (const text of new Set([...(spec.wrap ? rows.map(row => spec.text(row)) : []), ...totals.map(row => spec.text(row, true))])) width = Math.max(width, context.measureText(text).width + padding + 2);
            return width;
          });
          plannedWidths = tableWidths(displayed.map(c => ({ min: c.getColDef().minWidth ?? 60, max: c.getColDef().maxWidth ?? 400, flex: c.getColDef().context?.widthFlex ?? 0 })), preferred, available, 1);

        }
        const widthById = new Map(displayed.map((col,i) => [col.getColId(),plannedWidths[i]!]));
        const key = `${css.font}:${css.lineHeight}:${minimum}:${displayed.map(c => `${c.getColId()}:${widthById.get(c.getColId())}`).join('|')}`;
        const geometryChanged = appliedGeometry.current !== key;
        if (geometry.current !== key) { cache.current.clear(); geometry.current = key; }
        host.replaceChildren();
        const rowCss = getComputedStyle(host), rowBorder = (parseFloat(rowCss.borderTopWidth) || 0) + (parseFloat(rowCss.borderBottomWidth) || 0);
        const jobs = new Map<string, { text: string; column: TextGridColumn<T>; width: number; weight: string; row: T; pinned: boolean }>();
        function cellKey(row: T, column: TextGridColumn<T>, pinned: boolean) {
          const width = widthById.get(column.id)!, weight = pinned ? '600' : '400', text = column.text(row, pinned);
          return { key: `${column.id}\0${weight}\0${column.signature?.(row, pinned) ?? text}`, text, width, weight, column, row, pinned };
        }
        for (const [data, pinned] of [[rows, false], [totals, true]] as const) for (const row of data) for (const column of wrapping) {
          const cell = cellKey(row, column, pinned);
          if (!cache.current.has(cell.key)) jobs.set(cell.key, cell);
        }
        // A whole string that fits one actual-font canvas line needs no wrapping DOM.
        // Multiline/long strings still use the browser's real breaking rules below.
        if (canFitLine && singleLine <= minimum) for (const [key, job] of jobs) {
          context.font = `${job.weight} ${bodyFont}`;
          if (!job.column.render && !job.text.includes('\n') && context.measureText(job.text).width <= job.width - padding - 2) { cache.current.set(key, minimum); jobs.delete(key); }
        }
        const pending = [...jobs];
        // The measuring DOM is bounded; read each batch after writing it, then release it.
        let yieldedAt = performance.now();
        for (let start = 0; start < pending.length; start += 128) {
          const batch = pending.slice(start, start + 128);
          const elements = batch.map(([, job]) => {
            const cell = document.createElement('div'); cell.className = `ag-cell ag-cell-not-inline-editing ${job.column.wrap ? 'ag-cell-wrap-text' : ''} ${job.column.className ?? ''}`;
            cell.setAttribute('col-id', job.column.id);
            Object.assign(cell.style, { position: 'relative', height: 'auto', minHeight: '0', width: `${job.width}px`, fontWeight: job.weight });
            host!.append(cell);
            if (!job.column.render) { const text = document.createElement('div'); text.className = job.column.className ?? ''; text.textContent = job.text; cell.append(text); }
            return cell;
          });
          if (batch.some(([, job]) => job.column.render)) {
            flushSync(() => setMeasurement(createElement(Fragment, null, ...batch.flatMap(([, job], index) => job.column.render ? [createPortal(
              createElement('div', {className: 'ag-cell-wrapper', style: {width: '100%', height: 'auto'}}, createElement('span', {className: 'ag-cell-value', style: {width: '100%'}}, job.column.render(job.row, job.pinned))), elements[index]!, batch[index]![0])]
              : []))));
          }
          if (batch.some(([, job]) => job.column.render)) {
            // Only the rich controls actually measured here contribute labels and font weights.
            await loadElementFonts(host);
            if (cancelled(run)) return;
          }
          elements.forEach((cell, i) => cache.current.set(batch[i]![0], Math.ceil(cell.getBoundingClientRect().height + rowBorder)));
          if (batch.some(([, job]) => job.column.render)) flushSync(() => setMeasurement(null));
          host.replaceChildren();
          if (start + 128 < pending.length && performance.now() - yieldedAt > 8) { await new Promise<void>(resolve => requestAnimationFrame(() => resolve())); yieldedAt = performance.now(); }
          if (cancelled(run)) return;
        }
        const next = new Map<string, number>();
        for (const [data, pinned] of [[rows, false], [totals, true]] as const) for (const row of data) {
          let height = minimum;
          for (const column of wrapping) height = Math.max(height, cache.current.get(cellKey(row, column, pinned).key)!);
          next.set(rowId(row), height);
        }
        // Header text uses the actual header structure and final width, including sort space.
        const headerKey = `${key}:${headerMinimum}:${displayed.map(c => c.getColDef().headerName ?? '').join('|')}`;
        let header = headerSize.current.key === headerKey ? headerSize.current.height : headerMinimum;
        if (headerSize.current.key !== headerKey) for (const element of node!.querySelectorAll<HTMLElement>('.ag-header-cell')) {
          const clone = element.cloneNode(true) as HTMLElement;
          Object.assign(clone.style, { position: 'relative', height: 'auto', minHeight: '0', width: `${widthById.get(element.getAttribute('col-id')!) ?? element.offsetWidth}px` });
          for (const label of clone.querySelectorAll<HTMLElement>('.ag-header-cell-label,.ag-header-cell-comp-wrapper')) Object.assign(label.style, { height: 'auto', minHeight: '0' });
          host.append(clone); header = Math.max(header, Math.ceil(clone.getBoundingClientRect().height)); clone.remove();
        }
        headerSize.current = { key: headerKey, height: header };
        if (cancelled(run) || editable()) return;
        const anchor = readingAnchor.current?.scope === scope ? readingAnchor.current : null;
        const contentChanged = publishedRows.current !== rows;
        heights.current = next;
        const widths = displayed.flatMap((col,i) => Math.abs(col.getActualWidth() - plannedWidths[i]!) >= .5 ? [{key:col,newWidth:plannedWidths[i]!}] : []);
        if (widths.length) grid.setColumnWidths(widths);
        fitted.current = widthKey;
        if (Math.abs((grid.getGridOption('headerHeight') ?? headerMinimum) - header) >= .5) grid.setGridOption('headerHeight', header);
        if (publishedRows.current !== rows) { grid.setGridOption('rowData', rows); publishedRows.current = rows; }
        if (publishedTotals.current !== totals) { grid.setGridOption('pinnedBottomRowData', totals); publishedTotals.current = totals; }
        let changed = false;
        const applyHeight = (n: IRowNode<T>) => { if (n.data) { const height = next.get(rowId(n.data)) ?? minimum; if (Math.abs((n.rowHeight ?? 0) - height) >= .1) { n.setRowHeight(height); changed = true; } } };
        grid.forEachNode(applyHeight); for (let i = 0; i < grid.getPinnedBottomRowCount(); i++) { const node = grid.getPinnedBottomRow<T>(i); if (node) applyHeight(node); }
        if (changed) grid.onRowHeightChanged();
        await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
        if (cancelled(run)) return;
        // Natural-height reports render the whole known result. A complete row model
        // can precede React's last row commit; publish after that actual dependency.
        if (grid.getGridOption('domLayout') === 'autoHeight') {
          const expected = rows.map(rowId);
          const mounted = () => {
            const ids = new Set([...node!.querySelectorAll('.ag-row[row-id]')].map(row => row.getAttribute('row-id')));
            const center = node!.querySelector<HTMLElement>('.ag-body-horizontal-scroll-viewport');
            const horizontal = node!.querySelector<HTMLElement>('.ag-body-horizontal-scroll');
            // AG can finish its row queue before its real horizontal scrollbar
            // takes space. Natural-height reports publish after that dependency too.
            const needsHorizontal = Boolean(grid.getGridOption('alwaysShowHorizontalScroll')) || Boolean(center && center.scrollWidth > center.clientWidth + 1);
            const scrollbarReady = !horizontal || Boolean(grid.getGridOption('suppressHorizontalScroll')) || (!needsHorizontal || horizontal.offsetHeight > 0);
            return scrollbarReady && grid.isAnimationFrameQueueEmpty() && expected.every(id => ids.has(id));
          };
          while (!mounted()) {
            await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
            if (cancelled(run)) return;
          }
        }
        if (scope !== appliedScope.current) viewport.scrollTop = 0;
        else if (anchor && (geometryChanged || contentChanged || node!.clientWidth !== appliedWidth.current || node!.clientHeight !== appliedHeight.current)) {
          const restored = grid.getRowNode(anchor.id);
          if (restored?.rowTop != null) {
            viewport.scrollTop = Math.round((restored.rowTop + anchor.offset) / scrollScale());
            await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
            if (cancelled(run)) return;
            let element = node!.querySelector<HTMLElement>(`.ag-row[row-id="${CSS.escape(anchor.id)}"]`);
            if (!element) {
              grid.ensureNodeVisible(restored, 'top');
              await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
              if (cancelled(run)) return;
              element = node!.querySelector<HTMLElement>(`.ag-row[row-id="${CSS.escape(anchor.id)}"]`);
            }
            // Keep the row relative to the header bottom as type changes. The
            // native viewport includes header/footer geometry and AG floors its
            // stretch offset. Correct against the actual row, not a second estimate.
            if (element) viewport.scrollTop += (element.getBoundingClientRect().top - viewport.getBoundingClientRect().top - (header - anchor.offset)) / scrollScale();
            await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
            if (cancelled(run)) return;
          }
        }
        appliedGeometry.current = key; appliedScope.current = scope; appliedIdentity.current = identity; appliedWidth.current = node!.clientWidth; appliedHeight.current = node!.clientHeight;
        restoredTop.current = viewport.scrollTop;
        cancelAnimationFrame(anchorFrame); if (!anchor || scope !== anchor.scope) anchorFrame = requestAnimationFrame(captureAnchor);
        node!.dataset.layoutTiming = JSON.stringify({ started, fonts: fontsAt, applied: performance.now(), measured: jobs.size, minimum, rows: rows.length, width: node!.clientWidth, anchor, restored: viewport.scrollTop });
        prepared.current = { grid, rows, totals, columns, rowId, geometry: geometryStamp(), scope, identity };
        ready.current = true; setState('ready'); setError('');
      } catch (failure) {
        if (!cancelled(run)) { setError(failure instanceof Error ? failure.message : '表格尺寸准备失败，请重试。'); setState(ready.current ? 'ready' : 'error'); }
      } finally { setMeasurement(null); host?.remove(); if (run === version) preparing = false; }
    }
    const viewport = node.querySelector<HTMLElement>('.ag-grid-viewport,.ag-body-viewport');
    function scrollScale() {
      const last = grid.getDisplayedRowAtIndex(grid.getDisplayedRowCount() - 1), range = grid.getVerticalPixelRange();
      const modelHeight = (last?.rowTop ?? 0) + (last?.rowHeight ?? 0), max = viewport ? viewport.scrollHeight - viewport.clientHeight : 0;
      // AG compresses very tall row models into a smaller native scroll range.
      return max > 0 ? Math.max(1, (modelHeight - (range.bottom - range.top)) / max) : 1;
    }
    function captureAnchor() {
      if (disposed || preparing || !viewport || node!.clientWidth !== appliedWidth.current || scope !== appliedScope.current) return;
      const box = viewport.getBoundingClientRect();
      // Anchor a row the reader can actually see, rather than AG's offscreen row buffer.
      const visible = [...node!.querySelectorAll<HTMLElement>('.ag-row[row-id]')].find(element => {
        const rect = element.getBoundingClientRect();
        return grid.getRowNode(element.getAttribute('row-id')!) && rect.top >= box.top && rect.top < box.bottom;
      });
      if (visible) { const header = grid.getGridOption('headerHeight') ?? headerMinimum; readingAnchor.current = {id: visible.getAttribute('row-id')!, offset: header - (visible.getBoundingClientRect().top - box.top), header, scope}; }

    }
    // Programmatic restoration may round in a compressed scroll range. Keep the
    // requested reading anchor until the reader actually scrolls, so the residual
    // never becomes the input for the next restoration.
    const scrolled = () => { if (!preparing && viewport?.scrollTop !== restoredTop.current) { cancelAnimationFrame(anchorFrame); anchorFrame = requestAnimationFrame(captureAnchor); } };
    viewport?.addEventListener('scroll', scrolled, {passive: true});
    let width = node.clientWidth, height = node.clientHeight, font = getComputedStyle(node).font;
    const resize = new ResizeObserver(() => { const next = node.clientWidth, nextHeight = node.clientHeight; if (next && (next !== width || nextHeight !== height)) { width = next; height = nextHeight; schedule(); } });
    resize.observe(node);
    const appearance = new MutationObserver(() => { const next = getComputedStyle(node).font; if (next !== font) { font = next; userWidths.current = false; fitted.current = ''; schedule(); } });
    appearance.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class'] });
    const resized = (event: { source: string; finished?: boolean }) => { if (event.source === 'uiColumnResized' && event.finished) { userWidths.current = true; schedule(); } };
    grid.addEventListener('columnResized', resized);
    const afterEdit = () => { if (pendingEdit) schedule(); };
    // Every uncached measurement awaits its own text/control fonts before reading dimensions.
    // Unrelated page font shards must not invalidate an already prepared grid.
    node.addEventListener('focusout', afterEdit);
    schedule();
    return () => { disposed = true; cancelAnimationFrame(frame); cancelAnimationFrame(anchorFrame); viewport?.removeEventListener('scroll', scrolled); resize.disconnect(); appearance.disconnect(); grid.removeEventListener('columnResized', resized); node.removeEventListener('focusout', afterEdit); };
  }, [api, active, root, rows, totals, columns, rowId, minimum, headerMinimum, scope, identity, fontRoot, retry]);
  return { attach, state, error, measurement, concealed: ready.current && appliedIdentity.current !== identity, retry: () => setRetry(n => n + 1) };
}
