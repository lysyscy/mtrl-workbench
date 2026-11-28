import {
  ClientSideRowModelModule, ClientSideRowModelApiModule, PinnedRowModule, CellStyleModule, RowStyleModule, CellApiModule,
  RowApiModule, ColumnApiModule, RenderApiModule, EventApiModule, ScrollApiModule, ValueCacheModule,
  LocaleModule, RowAutoHeightModule, TooltipModule, CellSpanModule, CustomEditorModule, ColumnAutoSizeModule,
  ModuleRegistry, provideGlobalGridOptions, themeQuartz, RowDragModule, CustomFilterModule, RowSelectionModule,
} from 'ag-grid-community';
import type { SuppressKeyboardEventParams } from 'ag-grid-community';

ModuleRegistry.registerModules([
  ClientSideRowModelModule, ClientSideRowModelApiModule, PinnedRowModule, CellStyleModule, RowStyleModule, CellApiModule,
  RowApiModule, ColumnApiModule, RenderApiModule, EventApiModule, ScrollApiModule, ValueCacheModule,
  LocaleModule, RowAutoHeightModule, TooltipModule, CellSpanModule, CustomEditorModule, ColumnAutoSizeModule, RowDragModule, CustomFilterModule, RowSelectionModule,
]);
const editorKeys = new Set([
  'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'PageUp', 'PageDown',
  'Backspace', 'Delete', 'Enter', 'Escape', 'Tab', ' ',
]);
const editorShortcuts = new Set(['a', 'c', 'd', 'v', 'x', 'y', 'z']);

function suppressEditorKeyboardEvent({ event, editing }: SuppressKeyboardEventParams) {
  if (editing) return false;
  const target = event.target;
  if (!(target instanceof HTMLElement) || !(target.isContentEditable || target.closest('input, textarea, select, [role="combobox"]'))) return false;
  return event.isComposing || editorKeys.has(event.key) ||
    ((event.ctrlKey || event.metaKey) && editorShortcuts.has(event.key.toLowerCase()));
}

provideGlobalGridOptions({
  animateRows: false, enableCellTextSelection: true, ensureDomOrder: true,
  defaultColDef: { suppressKeyboardEvent: suppressEditorKeyboardEvent },
}, 'deep');
export const gridTheme = themeQuartz.withParams({ fontFamily: 'var(--fs)', fontSize: 'calc(var(--font-ui-size,13.5) * 1px * var(--fscale))', headerFontSize: 'calc(12px * var(--fscale))', cellHorizontalPadding: 'calc(4px * var(--fscale))',
  backgroundColor: 'var(--sf)', foregroundColor: 'var(--tx)', borderColor: 'var(--bd)',
  headerBackgroundColor: 'var(--sf2)', headerTextColor: 'var(--tx2)', accentColor: 'var(--pri)',
  oddRowBackgroundColor: 'var(--sf)', browserColorScheme: 'inherit', rowHoverColor: 'var(--sf2)',
  borderRadius: 0, wrapperBorderRadius: 0 });

export function pageGridGeometry(scale = 1) {
  return { rowHeight: 36 * scale, headerHeight: 34 * scale, groupHeaderHeight: 34 * scale };
}

export function fixedWidth(width: number, scale = 1) {
  return { width: width * scale, minWidth: width * scale, maxWidth: width * scale, flex: 0, resizable: false, suppressAutoSize: true };
}

export function contentWidth(min: number, max: number, scale = 1, stretch = 0) {
  return { initialWidth: min * scale, minWidth: min * scale, ...(stretch ? {initialFlex:stretch} : {maxWidth:max * scale}) };
}

interface ColumnTextSample {
  current: { font: string; ready: Promise<FontFaceSet>; texts: Set<string>; longest: string; width: number } | undefined;
}

export function cachedNumberColumnWidths() {
  const fields = new Map<string, ColumnTextSample>();
  return (key: string, values: readonly unknown[], scale: number, editable = false) => {
    let field = fields.get(key);
    if (!field) {
      field = { current: undefined };
      fields.set(key, field);
    }
    return numberColumnWidth(values, scale, editable, 0, field);
  };
}

export function numberColumnWidth(values: readonly unknown[], scale = Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))||1, editable = false, stretch = 0, sample?: ColumnTextSample) {
  const css = getComputedStyle(document.documentElement), fontSize = Number(css.getPropertyValue('--font-ui-size')) || 13.5;
  const context = document.createElement('canvas').getContext('2d')!;
  context.font = `600 ${fontSize * scale}px ${css.fontFamily}`;
  const texts = new Set(values.map(value => String(value ?? ''))).add('0.00');
  const ready = sample && document.fonts.ready;
  const last = sample?.current;
  const prior = last && last.font === context.font && last.ready === ready && document.fonts.status === 'loaded' && texts.has(last.longest) ? last : undefined;
  let widest = prior?.width ?? 0, longest = prior?.longest ?? '0.00';
  for (const text of texts) {
    if (prior?.texts.has(text)) continue;
    const width = context.measureText(text).width;
    if (width > widest) { widest = width; longest = text; }
  }
  if (sample && ready) {
    sample.current = document.fonts.status === 'loaded' && ready === document.fonts.ready
      ? { font: context.font, ready, texts, longest, width: widest } : undefined;
  }
  const minimum = Math.ceil(widest / scale + (editable ? 24 : 12));
  return contentWidth(minimum, Math.max(minimum, 180), scale, stretch);
}

export function cacheFontMeasurement<T>(measure: () => T) {
  let saved: { family: string; size: string; ready: Promise<FontFaceSet>; value: T } | undefined;
  return () => {
    const css = getComputedStyle(document.documentElement);
    const family = css.fontFamily, size = css.getPropertyValue('--font-ui-size'), ready = document.fonts.ready;
    if (saved?.family === family && saved.size === size && saved.ready === ready && document.fonts.status === 'loaded') return saved.value;
    const value = measure();
    if (document.fonts.status === 'loaded' && ready === document.fonts.ready) saved = { family, size, ready, value };
    return value;
  };
}

export function fullTextWidth(values:readonly string[],scale=Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))||1) {
  const css=getComputedStyle(document.documentElement),context=document.createElement('canvas').getContext('2d')!;
  context.font=`500 ${(Number(css.getPropertyValue('--font-ui-size'))||13.5)*scale}px ${css.fontFamily}`;
  let widest = 0;
  for (const value of new Set(values)) widest = Math.max(widest, context.measureText(value).width);
  const min = Math.ceil(widest / scale + 12);
  return contentWidth(min,Math.max(min,300),scale);
}
export function textWidth(min: number, max: number, scale = 1, flex = 1) {
  return { minWidth: min * scale, maxWidth: max * scale, flex };
}
