import type { ColDef, ColumnResizedEvent, GridApi } from 'ag-grid-community';
import { loadTextFonts } from './appearance-ready';

type ColumnWidth = { id: string } & (
  | { kind: 'bounded'; width: number }
  | { kind: 'demand'; minimum: number; typical: number; preferred: number; pinned?: boolean }
);

export function allocateColumnWidths(columns: readonly ColumnWidth[], available: number) {
  const base = columns.map(column => column.kind === 'bounded' ? column.width : column.minimum);
  const typical = columns.map(column => column.kind === 'demand' ? column.typical - column.minimum : 0);
  const longer = columns.map(column => column.kind === 'demand' ? column.preferred - column.typical : 0);
  const typicalNeed = typical.reduce((sum, width) => sum + width, 0);
  const longerNeed = longer.reduce((sum, width) => sum + width, 0);
  const extra = Math.max(0, Math.floor(available) - base.reduce((sum, width) => sum + width, 0));
  const toTypical = typicalNeed ? Math.min(1, extra / typicalNeed) : 0;
  const toLongest = longerNeed ? Math.max(0, Math.min(1, (extra - typicalNeed) / longerNeed)) : 0;
  const candidates = columns.filter(column => column.kind === 'demand').filter(column => !column.pinned);
  const withText = candidates.filter(column => column.preferred > column.minimum);
  const fill = new Set((withText.length ? withText : candidates).map(column => column.id));
  const surplus = fill.size ? Math.max(0, extra - typicalNeed - longerNeed) / fill.size : 0;
  let allocated = 0;
  let rounded = 0;
  return new Map(columns.map((column, index) => {
    allocated += typical[index]! * toTypical + longer[index]! * toLongest + (fill.has(column.id) ? surplus : 0);
    const next = Math.round(allocated);
    const width = base[index]! + next - rounded;
    rounded = next;
    return [column.id, width];
  }));
}

type Font = { size?: number; weight?: number; tabular?: boolean };
export interface WidthMeasure {
  text: (value: unknown, font?: Font) => number;
  buttons: (labels: readonly string[], options?: { padding?: number; gap?: number; scalePadding?: boolean; border?: number }) => number;
  px: (width: number) => number;
}
type Sample<T> = (row: T, measure: WidthMeasure, pinned: boolean) => number;
interface ColumnContent<T> {
  kind: ColumnWidth['kind'];
  sample?: Sample<T>;
  minimum?: (measure: WidthMeasure) => number;
}
export interface ColumnWidthData<T> {
  rows: readonly T[];
  totals?: readonly T[];
  readableTextWidth?: number;
  retainBy?: (row: T) => string | number;
}

export function contentColumn<T>(kind: ColumnContent<T>['kind'], sample?: Sample<T>, minimum?: ColumnContent<T>['minimum']) {
  return { initialWidth: 100, initialFlex: 0, suppressAutoSize: true, context: { columnContent: { kind, sample, minimum } } };
}

function columnContent<T>(definition: ColDef<T>): ColumnContent<T> | undefined {
  return definition.context?.columnContent;
}

const horizontalInsets = (css: CSSStyleDeclaration) =>
  [css.paddingLeft, css.paddingRight, css.borderLeftWidth, css.borderRightWidth].reduce((sum, value) => sum + (parseFloat(value) || 0), 0);

function createMeasure(scale: number, body: CSSStyleDeclaration, context: CanvasRenderingContext2D,
  fonts?: Map<number, Set<string>>): WidthMeasure {
  const px = (width: number) => width * scale;
  const metrics = new Map<string, Map<string, number>>();
  const digitsByFont = new Map<string, number>();
  const text: WidthMeasure['text'] = (value, { size, weight = 400, tabular } = {}) => {
    const label = String(value ?? '');
    if (fonts) {
      let group = fonts.get(weight);
      if (!group) fonts.set(weight, group = new Set());
      group.add(label);
      return 0;
    }
    const font = `${weight} ${size === undefined ? body.fontSize : px(size) + 'px'} ${body.fontFamily}`;
    const key = font + (tabular ? ':tabular' : '');
    let widths = metrics.get(key);
    if (!widths) metrics.set(key, widths = new Map());
    const cached = widths.get(label);
    if (cached !== undefined) return cached;
    context.font = font;
    let width = 0;
    let digitWidth = digitsByFont.get(font) ?? 0;
    if (tabular && !digitWidth) {
      digitWidth = Math.max(...Array.from('0123456789', digit => context.measureText(digit).width));
      digitsByFont.set(font, digitWidth);
    }
    for (const line of label.split(/\r?\n/)) {
      const digits = tabular ? line.match(/\d/g)?.length ?? 0 : 0;
      const measured = digits
        ? context.measureText(line.replace(/\d/g, '')).width + digitWidth * digits
        : context.measureText(line).width;
      width = Math.max(width, measured);
    }
    widths.set(label, width);
    return width;
  };
  const buttons: WidthMeasure['buttons'] = (labels, { padding = 8, gap = 4, scalePadding = true, border = 2 } = {}) =>
    labels.reduce((sum, label) => sum + text(label, { size: 12 }) + (scalePadding ? px(2 * padding) : 2 * padding) + border, 0)
      + px(gap) * Math.max(0, labels.length - 1);
  return { text, buttons, px };
}

async function measureColumns<T>(api: GridApi<T>, root: HTMLElement, scale: number, data: ColumnWidthData<T>) {
  const grid = root.querySelector<HTMLElement>('.ag-root');
  const context = document.createElement('canvas').getContext('2d');
  if (!grid || !context) return new Map<string, ColumnWidth>();
  const body = getComputedStyle(grid);
  const sample = grid.querySelector<HTMLElement>('.ag-row:not(.ag-row-pinned) .ag-cell');
  const cellInsets = sample ? horizontalInsets(getComputedStyle(sample)) : 8 * scale + 2;
  const headers = new Map([...grid.querySelectorAll<HTMLElement>('.ag-header-cell[col-id]')].map(element => [element.getAttribute('col-id'), element]));
  const columns = api.getAllDisplayedColumns().flatMap(column => {
    const definition = column.getColDef();
    const content = columnContent(definition);
    if (!content) return [];
    const id = column.getColId();
    const header = headers.get(id);
    const headerCss = header ? getComputedStyle(header) : body;
    const sort = header?.querySelector<HTMLElement>('.ag-sort-ascending-icon');
    const sortIcon = sort?.querySelector<HTMLElement>('.ag-icon');
    const sortSize = sortIcon ? parseFloat(getComputedStyle(sortIcon).fontSize) || 16 : 16;
    const sortPadding = sort ? horizontalInsets(getComputedStyle(sort)) : 4;
    const headerInsets = horizontalInsets(headerCss) + (definition.sortable ? sortSize + sortPadding : 0)
      + (definition.headerComponentParams?.compactReset === false ? 28 * scale : 0);
    const label = definition.headerName ?? id;
    const headerFont = { size: parseFloat(headerCss.fontSize) / scale, weight: Number(headerCss.fontWeight) || 500 };
    const measureCell = content.sample ?? ((row, measure, pinned) =>
      measure.text(definition.field && Object.getOwnPropertyDescriptor(row, definition.field)?.value, { weight: pinned ? 600 : 400 }));
    return [{ id, content, label, headerFont, headerInsets, measureCell, pinned: Boolean(definition.pinned), minWidth: column.getMinWidth() }];
  });
  const measure = (measure: WidthMeasure) => new Map<string, ColumnWidth>(columns.map(column => {
    const { id, content, label, headerFont, headerInsets, measureCell, pinned } = column;
    const floor = Math.max(measure.text(label, headerFont) + headerInsets, (content.minimum?.(measure) ?? 0) + cellInsets);
    let widest = 0;
    const samples: number[] = [];
    for (const row of data.rows) {
      const width = measureCell(row, measure, false);
      widest = Math.max(widest, width);
      if (content.kind === 'demand') samples.push(width);
    }
    for (const row of data.totals ?? []) widest = Math.max(widest, measureCell(row, measure, true));
    const headerWidth = Math.max(column.minWidth, Math.ceil(floor));
    const preferred = Math.max(headerWidth, Math.ceil(widest + cellInsets));
    if (content.kind === 'bounded') return [id, { id, kind: 'bounded', width: preferred }];
    samples.sort((a, b) => a - b);
    const typical = Math.max(headerWidth, Math.ceil((samples[Math.ceil(samples.length * .95) - 1] ?? 0) + cellInsets));
    const shortTextWidth = typical <= 132 * scale ? typical : headerWidth;
    const minimum = Math.max(shortTextWidth, Math.min(typical, Math.ceil((data.readableTextWidth ?? 0) * scale)));
    const width: ColumnWidth = { id, kind: 'demand', minimum, typical, preferred, pinned };
    return [id, width];
  }));
  const fonts = new Map<number, Set<string>>();
  measure(createMeasure(scale, body, context, fonts));
  await Promise.all([...fonts].map(([weight, texts]) => loadTextFonts([...texts].join(''), [weight])));
  return measure(createMeasure(scale, body, context));
}

export function bindContentColumnWidths<T>(api: GridApi<T>, root: HTMLElement, view: () => {
  active: boolean;
  scale: number;
  layoutKey: string;
  content: ColumnWidthData<T> | undefined;
  dragging: string | null;
}, isManual: (id: string) => boolean) {
  type Snapshot = {
    data: ColumnWidthData<T>; key: string; columns: unknown[];
    promise: Promise<Map<string, ColumnWidth>>;
  };
  let snapshot: Snapshot | undefined;
  let applied: { snapshot: Snapshot; widths: Map<string, ColumnWidth> } | undefined;
  let frame = 0;
  let disposed = false;
  const editing = () => api.getEditingCells().length > 0 ||
    root.contains(document.activeElement) && document.activeElement?.matches('input:not([type=checkbox]):not([type=radio]), select, textarea');
  async function fit() {
    const { active, scale, layoutKey: key, content: data, dragging } = view();
    if (disposed || !active || !data || dragging || api.isDestroyed() || !root.clientWidth || editing()) return;
    const displayed = api.getAllDisplayedColumns();
    const columns = displayed.map(column => columnContent(column.getColDef()) ?? column.getColId());
    if (!snapshot || snapshot.key !== key || snapshot.data.rows !== data.rows || snapshot.data.totals !== data.totals
        || snapshot.columns.length !== columns.length || columns.some((column, index) => column !== snapshot?.columns[index])) {
      snapshot = { data, key, columns, promise: measureColumns(api, root, scale, data) };
    }
    const requested = snapshot;
    const measured = await requested.promise;
    const current = view();
    if (disposed || snapshot !== requested || api.isDestroyed() || !current.active || current.dragging
        || current.layoutKey !== key || current.content?.rows !== data.rows || current.content?.totals !== data.totals || editing()) return;

    if (applied?.snapshot !== requested) {
      const prior = applied;
      const retain = data.retainBy;
      const previous = prior?.snapshot.data.rows;
      if (retain && prior?.snapshot.key === key && previous?.length === data.rows.length
          && previous.every((row, index) => retain(row) === retain(data.rows[index]!))) {
        for (const [id, column] of measured) {
          const old = prior.widths.get(id);
          if (column.kind === 'demand' && old?.kind === 'demand') {
            column.minimum = old.minimum;
            column.typical = old.typical;
            column.preferred = old.preferred;
          }
          if (column.kind === 'bounded' && old?.kind === 'bounded') column.width = Math.max(column.width, old.width);
        }
      }
      applied = { snapshot: requested, widths: measured };
    }
    const grid = root.querySelector<HTMLElement>('.ag-root');
    if (!grid?.clientWidth) return;
    const scrollbar = grid.querySelector<HTMLElement>('.ag-body-vertical-scroll:not(.ag-invisible):not(.ag-hidden)');
    const widths = allocateColumnWidths(api.getAllDisplayedColumns().map(column => {
      const id = column.getColId();
      return (!isManual(id) && measured.get(id)) || { id, kind: 'bounded', width: column.getActualWidth() };
    }), grid.clientWidth - (scrollbar?.offsetWidth ?? 0));
    const changes = api.getAllDisplayedColumns().flatMap(column => {
      const id = column.getColId(), newWidth = widths.get(id);
      return newWidth !== undefined && newWidth !== column.getActualWidth() && !isManual(id)
        ? [{ key: id, newWidth }] : [];
    });
    if (changes.length) api.setColumnWidths(changes);
  }
  const schedule = () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => { void fit(); });
  };
  const resized = (event: ColumnResizedEvent<T>) => { if (event.finished && event.source === 'uiColumnResized') schedule(); };
  const events = ['firstDataRendered', 'newColumnsLoaded', 'columnVisible', 'gridSizeChanged', 'dragCancelled'] as const;
  for (const event of events) api.addEventListener(event, schedule);
  api.addEventListener('columnResized', resized);
  root.addEventListener('focusout', schedule);
  const scrollbar = root.querySelector('.ag-body-vertical-scroll');
  const observer = new ResizeObserver(schedule);
  if (scrollbar) observer.observe(scrollbar);
  schedule();
  return { fit, schedule, dispose: () => {
    disposed = true;
    cancelAnimationFrame(frame);
    observer.disconnect();
    root.removeEventListener('focusout', schedule);
    if (!api.isDestroyed()) {
      for (const event of events) api.removeEventListener(event, schedule);
      api.removeEventListener('columnResized', resized);
    }
  } };
}
