import { createElement, Fragment, useLayoutEffect, useRef, useState } from 'react';
import { createPortal, flushSync } from 'react-dom';
import type { ReactNode, RefObject } from 'react';
import type { ColDef, ColGroupDef, GridApi, IRowNode } from 'ag-grid-community';
import { loadElementFonts, loadTextFonts } from './appearance-ready';

// Opt-in preparation. Rich cells render through a portal in the owning React tree,
// keeping their real router, appearance and editor context during bounded measurement.
export interface TextGridColumn<T> {
  id: string;
  text: (row: T, pinned?: boolean) => string;
  wrap: boolean;
  className?: string;
  render?: (row: T, pinned: boolean) => ReactNode;
  signature?: (row: T, pinned: boolean) => string;
  span?: (row: T, pinned: boolean) => number;
}

// React/AG treats a replacement renderer definition as a new component even if
// row IDs and values are unchanged. Defer that replacement through an input session.
const sizingKeys = ['width','initialWidth','minWidth','maxWidth','flex','initialFlex'] as const;
function initialSizing<T>(columns:(ColDef<T>|ColGroupDef<T>)[]):(ColDef<T>|ColGroupDef<T>)[]{
  return columns.map(column=>{
    if('children'in column)return {...column,children:initialSizing(column.children)};
    const {width,flex,...rest}=column;return {...rest,...(width===undefined?{}:{initialWidth:width}),...(flex===undefined?{}:{initialFlex:flex??0})};
  });
}
// Column state stays in AG Grid. Content-only definition updates keep the same
// sizing suggestions, while replacing business renderers/formatters normally.
function retainSizing<T>(columns:(ColDef<T>|ColGroupDef<T>)[], previous:(ColDef<T>|ColGroupDef<T>)[]):(ColDef<T>|ColGroupDef<T>)[] {
  const old=new Map(previous.flatMap(column=>'children'in column?[]:[[column.colId??column.field,column] as const]));
  return columns.map(column=>{
    if('children'in column){const group=previous.find(item=>'children'in item&&item.groupId===column.groupId&&item.headerName===column.headerName);return {...column,children:retainSizing(column.children,group&&'children'in group?group.children:[])};}
    const prior=old.get(column.colId??column.field);if(!prior)return column;
    const next={...column};for(const key of sizingKeys){delete next[key];const value=prior[key];if(typeof value==='number')next[key]=value;else if(key==='flex'&&value===null)next.flex=null;}
    if(prior.context?.manualWidthBounds)next.context={...next.context,manualWidthBounds:prior.context.manualWidthBounds};
    return next;
  });
}
export function useRetainedGridColumns<T>(columns: (ColDef<T>|ColGroupDef<T>)[], root: RefObject<HTMLElement | null>, layoutKey: string|number = '') {
  const [displayed, setDisplayed] = useState(()=>initialSizing(columns));
  const applied=useRef(layoutKey);
  useLayoutEffect(() => {
    const node = root.current; let frame = 0;
    const publish = () => {
      if (node?.contains(document.activeElement) && document.activeElement?.matches('input:not([type=checkbox]):not([type=radio]),select,textarea')) return;
      const changed=applied.current!==layoutKey;
      setDisplayed(previous=>changed?initialSizing(columns):retainSizing(initialSizing(columns),previous));
      applied.current=layoutKey;
    };
    const released = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(publish); };
    publish(); node?.addEventListener('focusout', released);
    return () => { cancelAnimationFrame(frame); node?.removeEventListener('focusout', released); };
  }, [columns, root, layoutKey]);
  return displayed;
}

export function useTextGridLayout<T>({ root, active, rows, totals, columns, rowId, minimum, headerMinimum, scope, identity, fontRoot, fit }: {
  root: RefObject<HTMLElement | null>; fontRoot?: RefObject<HTMLElement | null>; active: boolean; rows: T[]; totals: T[];
  scope: string; identity: string; columns: TextGridColumn<T>[]; rowId: (row: T) => string; minimum: number; headerMinimum: number;
  fit?: () => void;
}) {
  const [measurement, setMeasurement] = useState<ReactNode>(null);
  const [api, attach] = useState<GridApi<T> | null>(null);
  const [state, setState] = useState<'preparing' | 'updating' | 'ready' | 'error'>('preparing');
  const [error, setError] = useState(''), [retry, setRetry] = useState(0);
  const configured = useRef<GridApi<T> | null>(null), rowSize = useRef({minimum,rowId});
  rowSize.current = {minimum,rowId};
  const ready = useRef(false), heights = useRef(new Map<string, number>());
  const fitted = useRef('');
  const cache = useRef(new Map<string, number>()), geometry = useRef('');
  const headerSize = useRef({ key: '', height: headerMinimum });
  const prepared = useRef<{ grid: GridApi<T>; rows: T[]; totals: T[]; columns: TextGridColumn<T>[]; rowId: (row: T) => string; geometry: string; scope: string; identity: string; errors:string } | null>(null);
  const appliedScope = useRef(scope), appliedIdentity = useRef(identity);
  useLayoutEffect(() => {
    const node = root.current;
    if (!api || !node || !active) return;
    const grid = api;
    if (configured.current !== grid) { ready.current = false; setState('preparing'); grid.setGridOption('getRowHeight', p => p.data ? heights.current.get(rowSize.current.rowId(p.data)) ?? rowSize.current.minimum : rowSize.current.minimum); configured.current = grid; }
    let disposed = false, version = 0, frame = 0, pendingEdit = false;
    const cancelled = (run: number) => disposed || run !== version || grid.isDestroyed();
    const editable = () => grid.getEditingCells().length > 0 || node.contains(document.activeElement) && document.activeElement?.matches('input,select,textarea');
    const geometryStamp = () => {
      const css = getComputedStyle(node!.querySelector('.ag-root') ?? node!);
      return `${node!.clientWidth}:${grid.getGridOption('domLayout') === 'autoHeight' ? 'natural' : node!.clientHeight}:${css.fontFamily}:${css.fontSize}:${css.fontWeight}:${css.lineHeight}:${minimum}:${headerMinimum}:${grid.getAllDisplayedColumns().map(c => `${c.getColId()}:${c.getActualWidth()}:${c.getColDef().headerName ?? ''}`).join('|')}`;
    };
    const schedule = () => { if (ready.current) setState('updating'); version++; cancelAnimationFrame(frame); frame = requestAnimationFrame(() => { void prepare(version); }); };
    async function prepare(run: number) {
      if (cancelled(run) || !node!.clientWidth) return;
      // Retained pages and duplicate resize notifications reuse the applied layout.
      // An immutable value update is not a layout request. Only changed multiline
      // prose/errors or a real range/column/font/viewport change need measurement.
      const previous = prepared.current;
      const errors=[...node!.querySelectorAll('.ag-row [role=alert],.ag-row .has-error,.ag-row .process-cell-error')].map(element=>element.textContent).join('\n');
      const layoutChanged=!previous||previous.grid!==grid||previous.scope!==scope||previous.identity!==identity||previous.geometry!==geometryStamp();
      const sameRows=(current:T[],old:T[])=>current.length===old.length&&current.every((row,index)=>rowId(row)===rowId(old[index]!));
      const proseChanged=(current:T[],old:T[],pinned:boolean)=>current.some((row,index)=>{
        if(row===old[index])return false;
        return columns.filter(column=>column.wrap).some(column=>{
          const prior=previous?.columns.find(item=>item.id===column.id);if(!prior)return true;
          const before=prior.text(old[index]!,pinned),after=column.text(row,pinned);
          return before!==after&&!(/^[\d\s,.%¥￥()+−+—-]*$/.test(before)&&/^[\d\s,.%¥￥()+−+—-]*$/.test(after));
        });
      });
      if (previous&&!layoutChanged&&previous.errors===errors&&sameRows(rows,previous.rows)&&sameRows(totals,previous.totals)&&!proseChanged(rows,previous.rows,false)&&!proseChanged(totals,previous.totals,true)) {
        const now = performance.now();
        node!.dataset.layoutTiming = JSON.stringify({started:now,fonts:now,applied:now,measured:0,reused:true,minimum,rows:rows.length,width:node!.clientWidth});
        prepared.current={...previous,rows,totals,columns,rowId};
        setState('ready'); setError(''); return;
      }
      if (editable()) { pendingEdit = true; return; }
      pendingEdit = false;
      const started = performance.now();
      let host: HTMLDivElement | undefined;
      try {
        const wrapping = columns.filter(c => c.wrap || c.render);
        const body = [...new Set(wrapping.flatMap(column => rows.map(row => column.text(row))))].join('') + '0123456789,.-';
        const footer = columns.flatMap(column => totals.map(row => column.text(row, true))).join('');
        await Promise.all([fontRoot?.current ? loadElementFonts(fontRoot.current) : Promise.resolve(), loadTextFonts(body, [400]), loadTextFonts(footer, [600]),
          loadTextFonts(grid.getAllDisplayedColumns().map(c => c.getColDef().headerName ?? '').join(''), [500])]);
        if (cancelled(run) || !node!.clientWidth || editable()) return;
        if(layoutChanged&&fitted.current!==`${scope}:${identity}:${geometryStamp()}`){fit?.();fitted.current=`${scope}:${identity}:${geometryStamp()}`;}
        const fontsAt = performance.now();
        const displayed = grid.getAllDisplayedColumns();
        const viewport = node!.querySelector<HTMLElement>('.ag-grid-viewport,.ag-body-viewport');
        if (!viewport) throw new Error('表格尺寸准备失败，请重试。');
        const context = document.createElement('canvas').getContext('2d')!;
        host = document.createElement('div'); host.className = 'ag-row grid-layout-measure'; host.ariaHidden = 'true'; host.inert = true;
        Object.assign(host.style, { display: 'block', position: 'fixed', left: '-100000px', top: '0', height: 'auto', width: 'max-content', visibility: 'hidden', pointerEvents: 'none', contain: 'layout style' });
        node!.querySelector('.ag-root')!.append(host);
        const sample = document.createElement('div'); sample.className = 'ag-cell ag-cell-wrap-text'; host.append(sample);
        const css = getComputedStyle(sample);
        const sampleText = document.createElement('div'); sampleText.className = wrapping[0]?.className ?? ''; sampleText.textContent = '国0'; sample.append(sampleText);
        const textCss = getComputedStyle(sampleText);
        const bodyFont = `${textCss.fontSize} ${textCss.fontFamily}`, singleLine = Math.ceil(parseFloat(textCss.lineHeight) + parseFloat(css.paddingTop) + parseFloat(css.paddingBottom) + 2);
        const canFitLine = textCss.letterSpacing === 'normal' && textCss.wordSpacing === '0px';
        context.font = css.font;
        const padding=parseFloat(css.paddingLeft)+parseFloat(css.paddingRight)||16;
        const plannedWidths = displayed.map(col => col.getActualWidth());
        const widthById = new Map(displayed.map((col,i) => [col.getColId(),plannedWidths[i]!]));
        const key = `${css.font}:${css.lineHeight}:${minimum}:${displayed.map(c => `${c.getColId()}:${widthById.get(c.getColId())}`).join('|')}`;
        if (geometry.current !== key) { cache.current.clear(); geometry.current = key; }
        host.replaceChildren();
        const rowCss = getComputedStyle(host), rowBorder = (parseFloat(rowCss.borderTopWidth) || 0) + (parseFloat(rowCss.borderBottomWidth) || 0);
        const jobs = new Map<string, { text: string; column: TextGridColumn<T>; width: number; weight: string; row: T; pinned: boolean }>();
        function cellKey(row: T, column: TextGridColumn<T>, pinned: boolean) {
          const span = Math.max(1, Math.floor(column.span?.(row,pinned) ?? 1));
          let width = widthById.get(column.id) ?? 0;
          if (span !== 1) {
            const start = displayed.findIndex(col=>col.getColId()===column.id);
            width = plannedWidths.slice(start,start+span).reduce((sum,value)=>sum+value,0);
          }
          const weight = pinned ? '600' : '400', text = column.text(row, pinned);
          return { key: `${column.id}\0${width}\0${weight}\0${column.signature?.(row, pinned) ?? text}`, text, width, weight, column, row, pinned };
        }
        // Compute each domain text/signature once; applying measured heights must
        // not repeat formatter work across every row and wrapping column.
        const plannedRows: {id: string; cells: string[]}[] = [];
        for (const [data, pinned] of [[rows, false], [totals, true]] as const) for (const row of data) {
          const cells = wrapping.map(column => {
            const cell = cellKey(row, column, pinned);
            if (!cache.current.has(cell.key)) jobs.set(cell.key, cell);
            return cell.key;
          });
          plannedRows.push({id:rowId(row),cells});
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
        for (const row of plannedRows) {
          let height = minimum;
          for (const key of row.cells) height = Math.max(height, cache.current.get(key)!);
          next.set(row.id, height);
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
        heights.current = next;
        if (Math.abs((grid.getGridOption('headerHeight') ?? headerMinimum) - header) >= .5) grid.setGridOption('headerHeight', header);
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
            const scrollbarReady = !rows.length || !horizontal || Boolean(grid.getGridOption('suppressHorizontalScroll')) || (!needsHorizontal || horizontal.offsetHeight > 0);
            return scrollbarReady && grid.isAnimationFrameQueueEmpty() && expected.every(id => ids.has(id));
          };
          while (!mounted()) {
            await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
            if (cancelled(run)) return;
          }
        }
        if (scope !== appliedScope.current) viewport.scrollTop = 0;
        // Publishing rows can reveal the vertical scrollbar and shrink flex columns.
        // Never cache heights measured at the previous widths under that new geometry.
        const finalColumns = grid.getAllDisplayedColumns();
        if (finalColumns.length !== displayed.length || finalColumns.some((column, i) => column.getColId() !== displayed[i]!.getColId() || column.getActualWidth() !== plannedWidths[i])) {
          prepared.current = null;
          schedule(); return;
        }
        appliedScope.current = scope; appliedIdentity.current = identity;
        node!.dataset.layoutTiming = JSON.stringify({ started, fonts: fontsAt, applied: performance.now(), measured: jobs.size, reused: false, minimum, rows: rows.length, width: node!.clientWidth });
        prepared.current = { grid, rows, totals, columns, rowId, geometry: geometryStamp(), scope, identity, errors };
        ready.current = true; setState('ready'); setError('');
      } catch (failure) {
        if (!cancelled(run)) { setError(failure instanceof Error ? failure.message : '表格尺寸准备失败，请重试。'); setState(ready.current ? 'ready' : 'error'); }
      } finally { setMeasurement(null); host?.remove(); }
    }
    let width = node.clientWidth, height = node.clientHeight, font = getComputedStyle(node).font;
    const resize = new ResizeObserver(() => { const next = node.clientWidth, nextHeight = node.clientHeight; const changed = next !== width || grid.getGridOption('domLayout') !== 'autoHeight' && nextHeight !== height; width = next; height = nextHeight; if (next && changed) schedule(); });
    resize.observe(node);
    const appearance = new MutationObserver(() => { const next = getComputedStyle(node).font; if (next !== font) { font = next; schedule(); } });
    appearance.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class'] });
    const resized = (event: { finished?: boolean }) => { if (event.finished) schedule(); };
    grid.addEventListener('columnResized', resized);
    const afterEdit = () => { if (pendingEdit) schedule(); };
    // Every uncached measurement awaits its own text/control fonts before reading dimensions.
    // Unrelated page font shards must not invalidate an already prepared grid.
    node.addEventListener('focusout', afterEdit);
    schedule();
    return () => { disposed = true; cancelAnimationFrame(frame); resize.disconnect(); appearance.disconnect(); grid.removeEventListener('columnResized', resized); node.removeEventListener('focusout', afterEdit); };
  }, [api, active, root, rows, totals, columns, rowId, minimum, headerMinimum, scope, identity, fontRoot, retry,fit]);
  return { attach, state, error, measurement, concealed: ready.current && appliedIdentity.current !== identity, retry: () => setRetry(n => n + 1) };
}
