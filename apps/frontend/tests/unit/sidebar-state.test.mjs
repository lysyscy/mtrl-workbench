import assert from 'node:assert/strict';
import test from 'node:test';
import { resolveSidebarCollapsed, toggleSidebarPreference } from '../../src/sidebar-state.ts';

test('sidebar automatically narrows at 1080px and below', () => {
  assert.equal(resolveSidebarCollapsed('auto', 1920), false);
  assert.equal(resolveSidebarCollapsed('auto', 1081), false);
  assert.equal(resolveSidebarCollapsed('auto', 1080), true);
  assert.equal(resolveSidebarCollapsed('auto', 960), true);
});

test('half-screen sidebar can be expanded and collapsed again', () => {
  const expanded = toggleSidebarPreference('auto', 960);
  assert.equal(resolveSidebarCollapsed(expanded, 960), false);
  const collapsed = toggleSidebarPreference(expanded, 960);
  assert.equal(resolveSidebarCollapsed(collapsed, 960), true);
});

test('manual sidebar choices remain in force across the automatic threshold', () => {
  const collapsed = toggleSidebarPreference('auto', 1920);
  assert.equal(resolveSidebarCollapsed(collapsed, 1920), true);
  assert.equal(resolveSidebarCollapsed(collapsed, 960), true);
  const expanded = toggleSidebarPreference(collapsed, 1920);
  assert.equal(resolveSidebarCollapsed(expanded, 1920), false);
  assert.equal(resolveSidebarCollapsed(expanded, 960), false);
});
