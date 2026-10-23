import type { GridApi, SizeColumnsToContentStrategy } from 'ag-grid-community';
import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community';

ModuleRegistry.registerModules([AllCommunityModule]);
export const gridTheme = themeQuartz.withParams({ fontFamily: 'var(--fs)', fontSize: 'calc(12.5px * var(--fscale))',
  backgroundColor: 'var(--sf)', foregroundColor: 'var(--tx)', borderColor: 'var(--bd)',
  headerBackgroundColor: 'var(--sf2)', headerTextColor: 'var(--tx2)', accentColor: 'var(--pri)',
  oddRowBackgroundColor: 'var(--sf)', browserColorScheme: 'inherit', rowHoverColor: 'var(--sf2)',
  borderRadius: 0, wrapperBorderRadius: 0 });

export function fixedWidth(width: number, scale = 1) {
  return { width: width * scale, minWidth: width * scale, maxWidth: width * scale, flex: 0 };
}

const contentSizedGrids = new WeakSet<GridApi>();
export const contentSizing: SizeColumnsToContentStrategy = {
  type: 'fitCellContents', scaleUpToFitGridWidth: true, continuous: true,
  shouldAutoSizeColumns: ({ reason, api }) => {
    if (reason === 'viewportChanged' || api.getEditingCells().length || document.activeElement?.closest('.ag-cell input,.ag-cell select,.ag-cell textarea')) return false;
    if (reason === 'dataChanged') {
      if (contentSizedGrids.has(api)) return false;
      if (api.getDisplayedRowCount()) contentSizedGrids.add(api);
    }
    return true;
  },
};

export function contentWidth(min: number, max: number, scale = 1) {
  return { minWidth: min * scale, maxWidth: max * scale, flex: 0 };
}

export function textWidth(min: number, max: number, scale = 1, flex = 1) {
  return { minWidth: min * scale, maxWidth: max * scale, flex };
}
