import { useLayoutEffect, useRef, useState } from 'react';
import type { ComponentProps } from 'react';
import { tableWidths } from './table-widths';
import type { TableColumnWidth } from './table-widths';

export function BoundedTable({ columns, children, style, ...props }: ComponentProps<'table'> & { columns: readonly TableColumnWidth[] }) {
  const ref = useRef<HTMLTableElement>(null), [widths, setWidths] = useState<number[]>([]);
  const specification = JSON.stringify(columns);
  useLayoutEffect(() => {
    const table = ref.current, container = table?.parentElement;
    if (!table || !container) return;
    let frame = 0, lastWidth = -1, disposed = false, pending = false;
    let font = getComputedStyle(table).font;
    const fit = () => {
      frame = 0;
      const available = container.clientWidth;
      if (!available) return;
      if (table.contains(document.activeElement) && document.activeElement?.matches('input,select,textarea')) { pending = true; return; }
      pending = false;
      const em = parseFloat(getComputedStyle(table).fontSize), context = document.createElement('canvas').getContext('2d');
      if (!context) return;
      const measured = columns.map(c => c.min * em);
      for (const row of table.querySelectorAll('thead tr,tbody tr')) {
        let index = 0;
        for (const cell of row.querySelectorAll<HTMLTableCellElement>(':scope > th,:scope > td')) {
          if (cell.colSpan === 1 && columns[index]) {
            const css = getComputedStyle(cell); context.font = css.font;
            const text = Math.max(...cell.innerText.split('\n').map(line => context.measureText(line.trim()).width));
            const control = Math.max(0, ...[...cell.querySelectorAll('input,select,button')].map(el => el.getBoundingClientRect().width));
            measured[index] = Math.max(measured[index]!, Math.max(text, control) + parseFloat(css.paddingLeft) + parseFloat(css.paddingRight) + 2);
          }
          index += cell.colSpan;
        }
      }
      const next = tableWidths(columns, measured, available, em);
      setWidths(old => old.length === next.length && old.every((n, i) => Math.abs(n - next[i]!) < .5) ? old : next);
    };
    const schedule = () => { if (!disposed && !frame) frame = requestAnimationFrame(fit); };
    const observer = new ResizeObserver(() => { const width = container.clientWidth; if (width !== lastWidth) { lastWidth = width; schedule(); } });
    const afterEdit = () => { if (pending) schedule(); };
    const fonts = new MutationObserver(() => { const next = getComputedStyle(table).font; if (next !== font) { font = next; schedule(); } });
    fonts.observe(document.documentElement, { attributes: true, attributeFilter: ['class','style'] });
    table.addEventListener('focusout', afterEdit);
    observer.observe(container); schedule(); void document.fonts.ready.then(schedule);
    return () => { disposed = true; observer.disconnect(); fonts.disconnect(); table.removeEventListener('focusout', afterEdit); cancelAnimationFrame(frame); };
  }, [specification]);
  return <table {...props} ref={ref} className={`bounded-table ${props.className ?? ''}`} style={{ ...style, tableLayout: 'fixed', minWidth: 0, maxWidth: 'none', width: widths.length ? widths.reduce((a, b) => a + b, 0) : undefined }}><colgroup>{columns.map((_, i) => <col key={i} style={{ width: widths[i] }} />)}</colgroup>{children}</table>;
}
