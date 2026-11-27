export type SidebarPreference = 'auto' | 'expanded' | 'collapsed';

export const sidebarNarrowWidth = 1080;

export function resolveSidebarCollapsed(preference: SidebarPreference, viewportWidth: number) {
  return preference === 'collapsed' || (preference === 'auto' && viewportWidth <= sidebarNarrowWidth);
}

export function toggleSidebarPreference(preference: SidebarPreference, viewportWidth: number): SidebarPreference {
  return resolveSidebarCollapsed(preference, viewportWidth) ? 'expanded' : 'collapsed';
}
