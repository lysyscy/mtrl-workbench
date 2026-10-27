import type { GridApi } from 'ag-grid-community';
import {
  ClientSideRowModelModule, ClientSideRowModelApiModule, PinnedRowModule, CellStyleModule, RowStyleModule, CellApiModule,
  RowApiModule, ColumnApiModule, RenderApiModule, EventApiModule, ScrollApiModule, ValueCacheModule,
  LocaleModule, RowAutoHeightModule, TooltipModule, CellSpanModule, CustomEditorModule, ColumnAutoSizeModule,
  ModuleRegistry, provideGlobalGridOptions, themeQuartz,
} from 'ag-grid-community';

// Register adopted public modules; their dependencies supply the grid defaults.
ModuleRegistry.registerModules([
  ClientSideRowModelModule, ClientSideRowModelApiModule, PinnedRowModule, CellStyleModule, RowStyleModule, CellApiModule,
  RowApiModule, ColumnApiModule, RenderApiModule, EventApiModule, ScrollApiModule, ValueCacheModule,
  LocaleModule, RowAutoHeightModule, TooltipModule, CellSpanModule, CustomEditorModule, ColumnAutoSizeModule,
]);
// Ordinary reads and reordering stay still; project drag feedback is handled separately.
// Native drag selection/copy is shared by every grid; retain virtualisation.
provideGlobalGridOptions({ animateRows: false, enableCellTextSelection: true, ensureDomOrder: true });
export const gridTheme = themeQuartz.withParams({ fontFamily: 'var(--fs)', fontSize: 'calc(var(--font-ui-size,13.5) * 1px * var(--fscale))', headerFontSize: 'calc(12px * var(--fscale))',
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
  return { initialWidth: min * scale, minWidth: min * scale, ...(stretch ? {initialFlex:stretch} : {maxWidth:max * scale}) };
}

// Size complete values and totals, rather than imposing the same wide floor on every number.
export function numberColumnWidth(values: readonly unknown[], scale = 1, editable = false, stretch = 0) {
  const css = getComputedStyle(document.documentElement), fontSize = Number(css.getPropertyValue('--font-ui-size')) || 13.5;
  const context = document.createElement('canvas').getContext('2d')!;
  context.font = `600 ${fontSize * scale}px ${css.fontFamily}`;
  let widest = context.measureText('0.00').width;
  for (const value of new Set(values.map(value => String(value ?? '')))) widest = Math.max(widest, context.measureText(value).width);
  const minimum = Math.ceil(widest / scale + (editable ? 32 : 20));
  return contentWidth(minimum, Math.max(minimum, 180), scale, stretch);
}

// Auto-size sees rendered rows; full identifiers also protect offscreen values.
export function fullTextWidth(values:readonly string[],scale=1) {
  const css=getComputedStyle(document.documentElement),context=document.createElement('canvas').getContext('2d')!;
  context.font=`500 ${(Number(css.getPropertyValue('--font-ui-size'))||13.5)*scale}px ${css.fontFamily}`;
  const min=Math.ceil(Math.max(0,...[...new Set(values)].map(value=>context.measureText(value).width))/scale+20);
  return contentWidth(min,Math.max(min,300),scale);
}
export function textWidth(min: number, max: number, scale = 1, flex = 1) {
  return { minWidth: min * scale, maxWidth: max * scale, flex };
}

// Public AG APIs own content fitting and flex distribution.
export function freezeGridFlex(api:GridApi,root:HTMLElement) {
  let frozen:{colId:string;flex:number}[]|null=null,frame=0;
  const editing=()=>api.getEditingCells().length>0||root.contains(document.activeElement)&&document.activeElement?.matches('input:not([type=checkbox]):not([type=radio]),select,textarea,[contenteditable=true]');
  const freeze=()=>{
    if(frozen||api.isDestroyed()||!editing())return;
    frozen=api.getColumnState().flatMap(c=>c.flex? [{colId:c.colId,flex:c.flex}]:[]);
    if(frozen.length) api.applyColumnState({state:frozen.map(c=>({colId:c.colId,width:api.getColumn(c.colId)!.getActualWidth(),flex:null}))});
  };
  const restore=()=>{
    if(frozen&&!api.isDestroyed())api.applyColumnState({state:frozen});
    frozen=null;
  };
  const release=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{if(!editing())restore();});};
  root.addEventListener('focusin',freeze);root.addEventListener('focusout',release);
  api.addEventListener('cellEditingStarted',freeze);api.addEventListener('cellEditingStopped',release);
  return()=>{cancelAnimationFrame(frame);root.removeEventListener('focusin',freeze);root.removeEventListener('focusout',release);api.removeEventListener('cellEditingStarted',freeze);api.removeEventListener('cellEditingStopped',release);restore();};
}
const fittedGrids=new WeakMap<GridApi,{run:(measure:boolean)=>void}>();
export function fitGridColumns(api:GridApi,root:HTMLElement|null,measure=false) {
  if(!root||api.isDestroyed())return;
  let state=fittedGrids.get(api);
  if(!state) {
    let frame=0,needsMeasure=false,pending=false;
    const unfreeze=freezeGridFlex(api,root);
    const fit=()=>{
      frame=0;if(api.isDestroyed())return;
      if(api.getEditingCells().length||root.contains(document.activeElement)&&document.activeElement?.matches('input,select,textarea')){pending=true;return;}
      pending=false;
      if(needsMeasure) {
        needsMeasure=false;
        const compact=api.getAllDisplayedColumns().filter(c=>!c.getFlex()&&!c.getColDef().cellRenderer&&c.getColDef().minWidth!==c.getColDef().maxWidth).map(c=>c.getColId());
        if(compact.length)api.autoSizeColumns(compact,true);
      }
    };
    const run=(measure:boolean)=>{needsMeasure||=measure;if(!frame)frame=requestAnimationFrame(fit);};
    const release=()=>{if(pending)run(false);};
    root.addEventListener('focusout',release);
    api.addEventListener('gridPreDestroyed',()=>{cancelAnimationFrame(frame);root.removeEventListener('focusout',release);unfreeze();});
    state={run};fittedGrids.set(api,state);
  }
  state.run(measure);
}
