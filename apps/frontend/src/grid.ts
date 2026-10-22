import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community';

ModuleRegistry.registerModules([AllCommunityModule]);
export const gridTheme = themeQuartz.withParams({ fontFamily: 'var(--fs)', fontSize: 'calc(12.5px * var(--fscale))',
  backgroundColor: 'var(--sf)', foregroundColor: 'var(--tx)', borderColor: 'var(--bd)',
  headerBackgroundColor: 'var(--sf2)', headerTextColor: 'var(--tx2)', accentColor: 'var(--pri)',
  oddRowBackgroundColor: 'var(--sf)', browserColorScheme: 'inherit', rowHoverColor: 'var(--sf2)',
  borderRadius: 0, wrapperBorderRadius: 0 });
