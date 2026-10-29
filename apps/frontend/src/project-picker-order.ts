import type { Project } from './api';

export function projectPickerProjects(projects: readonly Project[], multiple: boolean): Project[] {
  const candidates = projects.filter(item => !multiple || item.project_type !== 'shell');
  return multiple ? candidates : candidates.sort((a, b) =>
    Number(a.status === 'archived') - Number(b.status === 'archived') || a.ord - b.ord);
}
