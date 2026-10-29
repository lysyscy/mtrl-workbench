import test from 'node:test';
import assert from 'node:assert/strict';
import { projectPickerProjects } from '../../src/project-picker-order.ts';

test('single project candidates follow archive order and preserve equal-ord input order', () => {
  const projects = [
    { id: 1, ord: 1, status: 'archived', project_type: 'normal', disp: '归档项目' },
    { id: 2, ord: 8, status: 'active', project_type: 'normal', disp: '后序项目' },
    { id: 3, ord: 2, status: 'active', project_type: 'normal', disp: '乙项目' },
    { id: 4, ord: 2, status: 'active', project_type: 'normal', disp: '甲项目' },
    { id: 5, ord: 9, status: 'archived', project_type: 'normal', disp: '后序归档' },
  ];
  const original = structuredClone(projects);
  assert.deepEqual(projectPickerProjects(projects, false).map(project => project.id), [3, 4, 2, 1, 5]);
  assert.deepEqual(projects, original);
});

test('multiple candidates keep caller order and shell exclusion for independent export ordering', () => {
  const projects = [
    { id: 1, ord: 9, status: 'active', project_type: 'normal' },
    { id: 2, ord: 2, status: 'active', project_type: 'shell' },
    { id: 3, ord: 1, status: 'active', project_type: 'normal' },
  ];
  assert.deepEqual(projectPickerProjects(projects, true).map(project => project.id), [1, 3]);
});
