import { useLayoutEffect, useRef, useState } from 'react';
import type { ComponentProps } from 'react';
import Button from 'antd/es/button';
import { loadElementFonts } from './appearance-ready';
import { tableWidths } from './table-widths';
import type { TableColumnWidth } from './table-widths';

export function BoundedTable({ columns, children, style, prepareFonts = false, layoutVersion, ...props }: ComponentProps<'table'> & { columns: readonly TableColumnWidth[]; prepareFonts?: boolean; layoutVersion?: unknown }) {
  const ref = useRef<HTMLTableElement>(null), [widths, setWidths] = useState<number[]>([]);
  const specification = JSON.stringify(columns);
  const [ready,setReady] = useState(!prepareFonts), [error,setError] = useState(''), [retry,setRetry] = useState(0);
  const prepared = useRef(!prepareFonts), [fitWidth,setFitWidth] = useState(-1);
  useLayoutEffect(() => { if (prepareFonts && widths.length && prepared.current && ref.current?.parentElement?.clientWidth === fitWidth) setReady(true); }, [prepareFonts,widths,fitWidth]);
  useLayoutEffect(() => {
    const table = ref.current, container = table?.parentElement;
    if (!table || !container) return;
    let frame = 0, lastWidth = -1, disposed = false, pending = false;
    let font = getComputedStyle(table).font;
    const fit = () => {
      frame = 0;
      const started = performance.now();
      const available = container.clientWidth;
      if (!available) return;
      if (table.contains(document.activeElement) && document.activeElement?.matches('input,select,textarea')) { pending = true; return; }
      pending = false;
      const em = parseFloat(getComputedStyle(table).fontSize), context = document.createElement('canvas').getContext('2d');
      if (!context) return;
      const measured = columns.map(c => c.min * em);
      const occupied = columns.map(() => 0);
      for (const row of table.querySelectorAll('thead tr,tbody tr')) {
        let index = 0;
        for (const cell of row.querySelectorAll<HTMLTableCellElement>(':scope > th,:scope > td')) {
          while (occupied[index]) index++;
          if (cell.colSpan === 1 && columns[index]) {
            const css = getComputedStyle(cell); context.font = css.font;
            const text = Math.max(...(cell.getAttribute('aria-label') ?? cell.innerText).split('\n').map(line => context.measureText(line.trim()).width));
            const control = Math.max(0, ...[...cell.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLButtonElement>('input,select,button')].map(el => {
              if (!(el instanceof HTMLInputElement) || ['checkbox','radio'].includes(el.type)) return el.getBoundingClientRect().width;
              // A percentage-sized editor describes its allocated cell, not its content.
              // Measuring that width feeds the previous project's layout into the next fit.
              const inputCss = getComputedStyle(el); context.font = inputCss.font;
              return Math.max(parseFloat(inputCss.minWidth) || 0, context.measureText(el.value || el.placeholder || '0.00').width +
                (parseFloat(inputCss.paddingLeft) || 0) + (parseFloat(inputCss.paddingRight) || 0) +
                (parseFloat(inputCss.borderLeftWidth) || 0) + (parseFloat(inputCss.borderRightWidth) || 0) + 16);
            }));
            measured[index] = Math.max(measured[index]!, Math.max(text, control) + parseFloat(css.paddingLeft) + parseFloat(css.paddingRight) + 2);
          }
          for (let i = index; i < index + cell.colSpan; i++) occupied[i] = cell.rowSpan;
          index += cell.colSpan;
        }
        for (let i = 0; i < occupied.length; i++) occupied[i] = Math.max(0, occupied[i]! - 1);
      }
      const next = tableWidths(columns, measured, available, em);
      prepared.current = true; setFitWidth(available);
      table.dataset.fitTiming = JSON.stringify({started,applied:performance.now(),columns:columns.length,width:available,rows:table.rows.length});
      setWidths(old => old.length === next.length && old.every((n, i) => Math.abs(n - next[i]!) < .5) ? old : next);
    };
    const prepare = async () => {
      frame = 0;
      try { if (prepareFonts) await loadElementFonts(table); if (!disposed) { fit(); setError(''); } }
      catch (failure) { if (!disposed) setError(failure instanceof Error ? failure.message : '字体准备失败，请重试。'); }
    };
    const schedule = () => { if (!disposed && !frame) frame = requestAnimationFrame(() => { void prepare(); }); };
    const observer = new ResizeObserver(() => { const width = container.clientWidth; if (width !== lastWidth) { lastWidth = width; schedule(); } });
    const afterEdit = () => { if (pending) schedule(); };
    const fonts = new MutationObserver(() => { const next = getComputedStyle(table).font; if (next !== font) { font = next; schedule(); } });
    fonts.observe(document.documentElement, { attributes: true, attributeFilter: ['class','style'] });
    table.addEventListener('focusout', afterEdit);
    observer.observe(container); if (prepareFonts) void prepare(); else fit(); lastWidth = container.clientWidth; if (!prepareFonts) void document.fonts.ready.then(schedule);
    return () => { disposed = true; observer.disconnect(); fonts.disconnect(); table.removeEventListener('focusout', afterEdit); cancelAnimationFrame(frame); };
  }, [specification,prepareFonts,layoutVersion,retry]);
  return <>{error&&<p role="alert">{error}<Button onClick={()=>setRetry(n=>n+1)}>重试表格加载</Button></p>}<table {...props} ref={ref} data-page-loading={prepareFonts && !ready && !error ? true : undefined} data-layout-state={prepareFonts ? error ? 'error' : ready ? 'ready' : 'preparing' : undefined} inert={prepareFonts && !ready} className={`bounded-table ${props.className ?? ''}`} style={{ ...style, visibility:prepareFonts && !ready ? 'hidden' : style?.visibility, tableLayout: 'fixed', minWidth: 0, maxWidth: 'none', width: widths.length ? widths.reduce((a, b) => a + b, 0) : undefined }}><colgroup>{columns.map((_, i) => <col key={i} style={{ width: widths[i] }} />)}</colgroup>{children}</table></>;
}
