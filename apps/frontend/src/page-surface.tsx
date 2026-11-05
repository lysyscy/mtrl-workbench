import { useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { loadElementFonts } from './appearance-ready';
import { PageActivity } from './page-activity';
import { WorkspaceReloadButton } from './page-error';

// Keep inactive grids at the content area's size so their layout queues can settle.
// The retained page stays outside both the interaction and accessibility trees.
const retainedBox: CSSProperties = { display: 'block', position: 'absolute', inset: 0, visibility: 'hidden', pointerEvents: 'none', zIndex: -1 };

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
      if (disposed || preparing) return;
      preparing = true;
      // These pages own their table boundaries; only their existing tool areas
      // contribute to the page's first font preparation. Data reads stay parallel.
      const scopes = () => [...node!.querySelectorAll<HTMLElement>('[data-page-chrome]')];
      const text = () => scopes().map(scope => scope.textContent ?? '').join('');
      const before = text();
      try {
        await Promise.all(scopes().map(loadElementFonts));
        if (disposed) return;
        preparing = false;
        if (node!.querySelector('[data-page-loading]')) return;
        if (text() !== before) { schedule(); return; }
        complete.current = true; setReady(true); observer.disconnect(); unsubscribe();
      } catch (failure) {
        if (!disposed) {
          setError(failure instanceof Error ? failure.message : '字体加载失败，请重试。');
          observer.disconnect(); unsubscribe(); cancelAnimationFrame(frame);
        }
        preparing = false;
      }
    }
    const observer = new MutationObserver(schedule);
    observer.observe(node, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['data-layout-state','data-layout-error'] });
    const unsubscribe = client.getQueryCache().subscribe(schedule);
    schedule();
    return () => { disposed = true; observer.disconnect(); unsubscribe(); cancelAnimationFrame(frame); };
  }, [active, client]);
  return <>
    {active && !ready && <div className="page-loading" role={error ? 'alert' : 'status'}>{error || `正在读取${title}…`}{error && <WorkspaceReloadButton>重试字体加载</WorkspaceReloadButton>}</div>}
    <div ref={root} className="page-view" hidden={!active} inert={!active || !ready} aria-hidden={active ? undefined : true} style={active ? { visibility: ready ? undefined : 'hidden' } : retainedBox}><PageActivity.Provider value={active}>{children}</PageActivity.Provider></div>
  </>;
}
