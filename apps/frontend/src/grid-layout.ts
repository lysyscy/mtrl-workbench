import { useLayoutEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type { GridApi } from 'ag-grid-community';
import { loadTextFonts } from './appearance-ready';
import { tableWidths } from './table-widths';

// Opt-in preparation for grids whose wrapping cells render plain text. Rich renderers
// keep their existing sizing until their actual content has a matching preparation path.
export interface TextGridColumn<T> {
  id: string;
  text: (row: T) => string;
  wrap: boolean;
  className?: string;
}

export function useTextGridLayout<T>({ root, active, rows, totals, columns, rowId, minimum, headerMinimum, scope, identity }: {
  root: RefObject<HTMLElement | null>; active: boolean; rows: T[]; totals: T[];
  scope: string; identity: string; columns: TextGridColumn<T>[]; rowId: (row: T) => string; minimum: number; headerMinimum: number;
}) {
  const [api, attach] = useState<GridApi<T> | null>(null);
  const [state, setState] = useState<'preparing' | 'updating' | 'ready' | 'error'>('preparing');
  const [error, setError] = useState(''), [retry, setRetry] = useState(0);
  const configured = useRef<GridApi<T> | null>(null), publishedRows = useRef<T[] | null>(null), publishedTotals = useRef<T[] | null>(null), rowSize = useRef({minimum,rowId});
  rowSize.current = {minimum,rowId};
  const ready = useRef(false), heights = useRef(new Map<string, number>());
  const cache = useRef(new Map<string, number>()), geometry = useRef(''), userWidths = useRef(false);
  const readingAnchor = useRef<{id: string; offset: number; header: number; scope: string} | null>(null), appliedWidth = useRef(0);
  const fitted = useRef(''), appliedScope = useRef(scope), appliedIdentity = useRef(identity);
  useLayoutEffect(() => {
    const node = root.current;
    if (!api || !node || !active) return;
    const grid = api;
    if (configured.current !== grid) { grid.setGridOption('getRowHeight', p => p.data ? heights.current.get(rowSize.current.rowId(p.data)) ?? rowSize.current.minimum : rowSize.current.minimum); configured.current = grid; publishedRows.current = null; publishedTotals.current = null; }
    let disposed = false, version = 0, frame = 0, anchorFrame = 0, pendingEdit = false, preparing = false;
    const cancelled = (run: number) => disposed || run !== version || grid.isDestroyed();
    const editable = () => grid.getEditingCells().length > 0 || node.contains(document.activeElement) && document.activeElement?.matches('input,select,textarea');
    const schedule = () => { if (ready.current) setState('updating'); version++; cancelAnimationFrame(frame); frame = requestAnimationFrame(() => { void prepare(version); }); };
    async function prepare(run: number) {
      if (cancelled(run) || !node!.clientWidth) return;
      if (editable()) { pendingEdit = true; return; }
      pendingEdit = false;
      const started = performance.now(); preparing = true;
      let host: HTMLDivElement | undefined;
      try {
        const wrapping = columns.filter(c => c.wrap);
        const body = [...new Set(wrapping.flatMap(column => rows.map(column.text)))].join('') + '0123456789,.-';
        const footer = columns.flatMap(column => totals.map(column.text)).join('');
        await Promise.all([loadTextFonts(body, [400]), loadTextFonts(footer, [600]),
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
            if (spec) for (const text of new Set([...(spec.wrap ? rows : []), ...totals].map(spec.text))) width = Math.max(width, context.measureText(text).width + padding + 2);
            return width;
          });
          plannedWidths = tableWidths(displayed.map(c => ({ min: c.getColDef().minWidth ?? 60, max: c.getColDef().maxWidth ?? 400, flex: c.getColDef().context?.widthFlex ?? 0 })), preferred, available, 1);

        }
        const widthById = new Map(displayed.map((col,i) => [col.getColId(),plannedWidths[i]!]));
        const key = `${css.font}:${css.lineHeight}:${minimum}:${displayed.map(c => `${c.getColId()}:${widthById.get(c.getColId())}`).join('|')}`;
        if (geometry.current !== key) { cache.current.clear(); geometry.current = key; }
        host.replaceChildren();
        const rowCss = getComputedStyle(host), rowBorder = (parseFloat(rowCss.borderTopWidth) || 0) + (parseFloat(rowCss.borderBottomWidth) || 0);
        const jobs = new Map<string, { text: string; column: TextGridColumn<T>; width: number; weight: string }>();
        function cellKey(row: T, column: TextGridColumn<T>, pinned: boolean) {
          const width = widthById.get(column.id)!, weight = pinned ? '600' : '400', text = column.text(row);
          return { key: `${column.id}\0${weight}\0${text}`, text, width, weight, column };
        }
        for (const [data, pinned] of [[rows, false], [totals, true]] as const) for (const row of data) for (const column of wrapping) {
          const cell = cellKey(row, column, pinned);
          if (!cache.current.has(cell.key)) jobs.set(cell.key, cell);
        }
        // A whole string that fits one actual-font canvas line needs no wrapping DOM.
        // Multiline/long strings still use the browser's real breaking rules below.
        if (canFitLine && singleLine <= minimum) for (const [key, job] of jobs) {
          context.font = `${job.weight} ${bodyFont}`;
          if (!job.text.includes('\n') && context.measureText(job.text).width <= job.width - padding - 2) { cache.current.set(key, minimum); jobs.delete(key); }
        }
        const pending = [...jobs];
        // The measuring DOM is bounded; read each batch after writing it, then release it.
        let yieldedAt = performance.now();
        for (let start = 0; start < pending.length; start += 128) {
          const batch = pending.slice(start, start + 128);
          const elements = batch.map(([, job]) => {
            const cell = document.createElement('div'); cell.className = 'ag-cell ag-cell-wrap-text';
            Object.assign(cell.style, { position: 'relative', height: 'auto', minHeight: '0', width: `${job.width}px`, fontWeight: job.weight });
            const text = document.createElement('div'); text.className = job.column.className ?? ''; text.textContent = job.text; cell.append(text); host!.append(cell); return cell;
          });
          elements.forEach((cell, i) => cache.current.set(batch[i]![0], Math.ceil(cell.getBoundingClientRect().height + rowBorder)));
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
        let header = headerMinimum;
        for (const element of node!.querySelectorAll<HTMLElement>('.ag-header-cell')) {
          const clone = element.cloneNode(true) as HTMLElement;
          Object.assign(clone.style, { position: 'relative', height: 'auto', minHeight: '0', width: `${widthById.get(element.getAttribute('col-id')!) ?? element.offsetWidth}px` });
          for (const label of clone.querySelectorAll<HTMLElement>('.ag-header-cell-label,.ag-header-cell-comp-wrapper')) Object.assign(label.style, { height: 'auto', minHeight: '0' });
          host.append(clone); header = Math.max(header, Math.ceil(clone.getBoundingClientRect().height)); clone.remove();
        }
        if (cancelled(run) || editable()) return;
        const anchor = readingAnchor.current?.scope === scope ? readingAnchor.current : null;
        heights.current = next;
        const widths = displayed.flatMap((col,i) => Math.abs(col.getActualWidth() - plannedWidths[i]!) >= .5 ? [{key:col,newWidth:plannedWidths[i]!}] : []);
        if (widths.length) grid.setColumnWidths(widths);
        fitted.current = widthKey;
        if (Math.abs((grid.getGridOption('headerHeight') ?? headerMinimum) - header) >= .5) grid.setGridOption('headerHeight', header);
        if (publishedRows.current !== rows) { grid.setGridOption('rowData', rows); publishedRows.current = rows; }
        if (publishedTotals.current !== totals) { grid.setGridOption('pinnedBottomRowData', totals); publishedTotals.current = totals; }
        let changed = false;
        grid.forEachNode(n => { if (n.data) { const height = next.get(rowId(n.data)) ?? minimum; if (Math.abs((n.rowHeight ?? 0) - height) >= .1) { n.setRowHeight(height); changed = true; } } });
        if (changed) grid.onRowHeightChanged();
        await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
        if (cancelled(run)) return;
        if (scope !== appliedScope.current) viewport.scrollTop = 0;
        else if (anchor) { const restored = grid.getRowNode(anchor.id); if (restored?.rowTop != null) viewport.scrollTop = Math.round((restored.rowTop + anchor.offset + header - anchor.header) / scrollScale()); }
        appliedScope.current = scope; appliedIdentity.current = identity; appliedWidth.current = node!.clientWidth;
        cancelAnimationFrame(anchorFrame); anchorFrame = requestAnimationFrame(captureAnchor);
        node!.dataset.layoutTiming = JSON.stringify({ started, fonts: fontsAt, applied: performance.now(), measured: jobs.size, rows: rows.length, width: node!.clientWidth, anchor, restored: viewport.scrollTop });
        ready.current = true; setState('ready'); setError('');
      } catch (failure) {
        if (!cancelled(run)) { setError(failure instanceof Error ? failure.message : '表格尺寸准备失败，请重试。'); setState(ready.current ? 'ready' : 'error'); }
      } finally { host?.remove(); if (run === version) preparing = false; }
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
    const scrolled = () => { if (!preparing) { cancelAnimationFrame(anchorFrame); anchorFrame = requestAnimationFrame(captureAnchor); } };
    viewport?.addEventListener('scroll', scrolled, {passive: true});
    let width = node.clientWidth, font = getComputedStyle(node).font;
    const resize = new ResizeObserver(() => { const next = node.clientWidth; if (next && next !== width) { width = next; schedule(); } });
    resize.observe(node);
    const appearance = new MutationObserver(() => { const next = getComputedStyle(node).font; if (next !== font) { font = next; userWidths.current = false; fitted.current = ''; schedule(); } });
    appearance.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class'] });
    const resized = (event: { source: string; finished?: boolean }) => { if (event.source === 'uiColumnResized' && event.finished) { userWidths.current = true; schedule(); } };
    grid.addEventListener('columnResized', resized);
    const afterEdit = () => { if (pendingEdit) schedule(); };
    node.addEventListener('focusout', afterEdit); document.fonts.addEventListener('loadingdone', schedule);
    schedule();
    return () => { disposed = true; cancelAnimationFrame(frame); cancelAnimationFrame(anchorFrame); viewport?.removeEventListener('scroll', scrolled); resize.disconnect(); appearance.disconnect(); grid.removeEventListener('columnResized', resized); node.removeEventListener('focusout', afterEdit); document.fonts.removeEventListener('loadingdone', schedule); };
  }, [api, active, root, rows, totals, columns, rowId, minimum, headerMinimum, scope, identity, retry]);
  return { attach, state, error, concealed: ready.current && appliedIdentity.current !== identity, retry: () => setRetry(n => n + 1) };
}
