import { useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import Button from 'antd/es/button';
import { loadElementFonts } from './appearance-ready';

// Prepare only the first display. Retained pages, refreshes and editing never hide existing content.
export function PageSurface({ active, title, independent = false, children }: { active: boolean; title: string; independent?: boolean; children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null), complete = useRef(false);
  const [ready, setReady] = useState(false), [error, setError] = useState('');
  const client = useQueryClient();
  useLayoutEffect(() => {
    const node = root.current;
    if (!active || complete.current || !node) return;
    let disposed = false, frame = 0, preparing = false;
    function schedule() { if (!disposed && !preparing && !complete.current) { cancelAnimationFrame(frame); frame = requestAnimationFrame(prepare); } }
    async function prepare() {
      if (disposed || preparing) return;
      const failed = independent ? null : node!.querySelector<HTMLElement>('[data-layout-state=error]');
      if (failed) { setError(failed.dataset.layoutError || '表格尺寸准备失败，请重试。'); return; }
      if (node!.querySelector('[data-page-loading]') || !independent && (client.isFetching() || node!.querySelector('[data-layout-state=preparing]'))) return;
      preparing = true;
      // These pages own their table boundaries; only their existing tool areas
      // contribute to the page's first font preparation. Data reads stay parallel.
      const scopes = () => independent ? [...node!.querySelectorAll<HTMLElement>('[data-page-chrome]')] : [node!];
      const text = () => scopes().map(scope => scope.textContent ?? '').join('');
      const before = text();
      try {
        await Promise.all(scopes().map(loadElementFonts));
        if (disposed) return;
        if (independent) {
          preparing = false;
          if (text() !== before) { schedule(); return; }
          complete.current = true; setReady(true); observer.disconnect(); unsubscribe();
          return;
        }
        // Let React/grid layout commit while still mounted at its final width.
        frame = requestAnimationFrame(() => { frame = requestAnimationFrame(() => {
          preparing = false;
          if (disposed) return;
          if (client.isFetching() || text() !== before) { schedule(); return; }
          complete.current = true; setReady(true); observer.disconnect(); unsubscribe();
        }); });
      } catch (failure) {
        if (!disposed) setError(failure instanceof Error ? failure.message : '字体加载失败，请重试。');
        preparing = false;
      }
    }
    const observer = new MutationObserver(schedule);
    observer.observe(node, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['data-layout-state','data-layout-error'] });
    const unsubscribe = client.getQueryCache().subscribe(schedule);
    schedule();
    return () => { disposed = true; observer.disconnect(); unsubscribe(); cancelAnimationFrame(frame); };
  }, [active, client, independent]);
  return <>
    {active && !ready && <div className="page-loading" role={error ? 'alert' : 'status'}>{error || `正在读取${title}…`}{error && <Button onClick={() => window.location.reload()}>{error.startsWith('表格') ? '重试表格加载' : '重试字体加载'}</Button>}</div>}
    <div ref={root} className="page-view" hidden={!active} inert={!active || !ready} style={{ visibility: ready ? undefined : 'hidden' }}>{children}</div>
  </>;
}
