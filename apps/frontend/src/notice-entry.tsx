import { lazy, Suspense } from 'react';
import { useQuery } from '@tanstack/react-query';
import { readProjects, requestJson } from './api';
import type { Identity } from './api';
import { noticeListQuery } from './notice-list';

const NoticesPage = lazy(() => import('./notices').then(module => ({ default: module.NoticesPage })));

export function NoticeEntry(props: { me: Identity | null; blocked: boolean; active: boolean }) {
  const enabled = props.active && !props.blocked;
  const query = useQuery({ ...noticeListQuery, enabled, refetchOnMount: 'always' });
  const projects = useQuery({ queryKey: ['projects', 'all'], enabled, queryFn: async ({ signal }) =>
    readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  // Commit the read observer while the table and its editors load.
  return <Suspense fallback={<p role="status" data-page-loading>正在读取付款通知书…</p>}>
    <NoticesPage {...props} query={query} projects={projects} />
  </Suspense>;
}
