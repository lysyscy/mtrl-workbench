import { tableWidths } from './table-widths';
import type { GridApi } from 'ag-grid-community';
import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community';

ModuleRegistry.registerModules([AllCommunityModule]);
export const gridTheme = themeQuartz.withParams({ fontFamily: 'var(--fs)', fontSize: 'calc(var(--font-ui-size,13.5) * 1px * var(--fscale))', headerFontSize: 'calc(11.5px * var(--fscale))',
  backgroundColor: 'var(--sf)', foregroundColor: 'var(--tx)', borderColor: 'var(--bd)',
  headerBackgroundColor: 'var(--sf2)', headerTextColor: 'var(--tx2)', accentColor: 'var(--pri)',
  oddRowBackgroundColor: 'var(--sf)', browserColorScheme: 'inherit', rowHoverColor: 'var(--sf2)',
  borderRadius: 0, wrapperBorderRadius: 0 });

// Whole-page tables share compact geometry; dialog tables keep their task-specific sizing.
export function pageGridGeometry(scale = 1) {
  return { rowHeight: 36 * scale, headerHeight: 34 * scale, groupHeaderHeight: 34 * scale };
}

export function fixedWidth(width: number, scale = 1) {
  return { width: width * scale, minWidth: width * scale, maxWidth: width * scale, flex: 0 };
}

export function contentWidth(min: number, max: number, scale = 1, stretch = 0) {
  return { width: min * scale, minWidth: min * scale, maxWidth: max * scale, flex: 0, context: { widthFlex: stretch } };
}

export function textWidth(min: number, max: number, scale = 1, flex = 1) {
  return { minWidth: min * scale, maxWidth: max * scale, flex };
}

// Content sets the preferred share; the container takes priority until usable minima are reached.
const fittedGrids = new WeakMap<GridApi, { run: (measure: boolean) => void }>();
export function fitGridColumns(api: GridApi, root: HTMLElement | null, measure = false) {
  if (!root || api.isDestroyed()) return;
  let state = fittedGrids.get(api);
  if (!state) {
    let frame = 0, needsMeasure = false, pending = false;
    const preferred = new Map<string, number>();
    const fit = () => {
      frame = 0;
      if (api.isDestroyed()) return;
      if (api.getEditingCells().length || (root.contains(document.activeElement) && document.activeElement?.matches('input,select,textarea'))) { pending = true; return; }
      pending = false;
      const columns = api.getAllDisplayedColumns();
      if (!columns.length) return;
      if (needsMeasure) {
        const context = document.createElement('canvas').getContext('2d');
        if (context) for (const column of columns) {
          let width = column.getColDef().minWidth ?? 60;
          for (const cell of root.querySelectorAll<HTMLElement>(`[col-id="${CSS.escape(column.getColId())}"]`)) {
            const css = getComputedStyle(cell); context.font = css.font;
            const text = Math.max(0, ...cell.innerText.split('\n').map(line => context.measureText(line.trim()).width));
            const control = Math.max(0, ...[...cell.querySelectorAll('input,select,button,a.row-button')].map(el => el.getBoundingClientRect().width));
            width = Math.max(width, Math.max(text, control) + parseFloat(css.paddingLeft) + parseFloat(css.paddingRight) + 2);
          }
          preferred.set(column.getColId(), width);
        }
        needsMeasure = false;
      }
      const viewport = root.querySelector<HTMLElement>('.ag-grid-viewport,.ag-body-viewport');
      const scrollbar = root.querySelector<HTMLElement>('.ag-body-vertical-scroll');
      const available = (viewport?.clientWidth ?? 0) - (scrollbar?.getBoundingClientRect().width ?? 0);
      if (!available) return;
      const specs = columns.map(column => { const def = column.getColDef(); return { min: def.minWidth ?? 60, max: def.maxWidth ?? 400, flex: def.context?.widthFlex ?? 0 }; });
      const widths = tableWidths(specs, columns.map(column => preferred.get(column.getColId()) ?? column.getActualWidth()), available, 1);
      const changed = columns.flatMap((column, i) => Math.abs(column.getActualWidth() - widths[i]!) >= .5 ? [{ key: column, newWidth: widths[i]! }] : []);
      if (changed.length) api.setColumnWidths(changed);
    };
    const run = (measure: boolean) => { needsMeasure ||= measure; if (!frame) frame = requestAnimationFrame(fit); };
    const afterEdit = () => { if (pending) run(false); };
    root.addEventListener('focusout', afterEdit);
    api.addEventListener('gridPreDestroyed', () => { cancelAnimationFrame(frame); root.removeEventListener('focusout', afterEdit); });
    state = { run }; fittedGrids.set(api, state);
  }
  state.run(measure);
}
