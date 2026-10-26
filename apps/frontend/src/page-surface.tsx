import { useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import Button from 'antd/es/button';
import { loadElementFonts } from './appearance-ready';

// Prepare only the first display. Retained pages, refreshes and editing never hide existing content.
export function PageSurface({ active, title, children }: { active: boolean; title: string; children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null), complete = useRef(false);
  const [ready, setReady] = useState(false), [error, setError] = useState('');
  const client = useQueryClient();
  useLayoutEffect(() => {
    const node = root.current;
    if (!active || complete.current || !node) return;
    let disposed = false, frame = 0, preparing = false;
    function schedule() { if (!disposed && !preparing && !complete.current) { cancelAnimationFrame(frame); frame = requestAnimationFrame(prepare); } }
    async function prepare() {
      if (disposed || preparing || client.isFetching() || node!.querySelector('[data-page-loading]')) return;
      preparing = true;
      const text = node!.textContent ?? '';
      try {
        await loadElementFonts(node!);
        if (disposed) return;
        // Let React/grid layout commit while still mounted at its final width.
        frame = requestAnimationFrame(() => { frame = requestAnimationFrame(() => {
          preparing = false;
          if (disposed) return;
          if (client.isFetching() || node!.textContent !== text) { schedule(); return; }
          complete.current = true; setReady(true); observer.disconnect(); unsubscribe();
        }); });
      } catch (failure) {
        if (!disposed) setError(failure instanceof Error ? failure.message : '字体加载失败，请重试。');
        preparing = false;
      }
    }
    const observer = new MutationObserver(schedule);
    observer.observe(node, { childList: true, subtree: true, characterData: true });
    const unsubscribe = client.getQueryCache().subscribe(schedule);
    schedule();
    return () => { disposed = true; observer.disconnect(); unsubscribe(); cancelAnimationFrame(frame); };
  }, [active, client]);
  return <>
    {active && !ready && <div className="page-loading" role={error ? 'alert' : 'status'}>{error || `正在读取${title}…`}{error && <Button onClick={() => window.location.reload()}>重试字体加载</Button>}</div>}
    <div ref={root} className="page-view" hidden={!active} inert={!active || !ready} style={{ visibility: ready ? undefined : 'hidden' }}>{children}</div>
  </>;
}
