import './read-region.css';
import Button from 'antd/es/button';
import { createContext, useContext, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { PageActivity } from './page-activity';

type GridPreparation = 'preparing' | 'ready' | 'error';
type FirstReadRegistration = { register: (id: symbol) => () => void; update: (id: symbol, state: GridPreparation) => void };
const FirstReadContext = createContext<FirstReadRegistration | null>(null);

// The two grid adapters participate without exposing their count or DOM to pages.
export function useFirstReadGrid(state: GridPreparation) {
  const region = useContext(FirstReadContext), active = useContext(PageActivity), id = useRef(Symbol('first-read-grid'));
  useLayoutEffect(() => active ? region?.register(id.current) : undefined, [region, active]);
  useLayoutEffect(() => { if (active) region?.update(id.current, state); }, [region, active, state]);
}

export function FirstReadRegion({ phase, children, placeholder, canPublish = true, onSettledChange, onPublished, className, style }: {
  phase: 'pending' | 'content' | 'error'; children: ReactNode; placeholder: ReactNode;
  canPublish?: boolean; onSettledChange?: (settled: boolean) => void; onPublished?: () => void; className?: string | undefined; style?: CSSProperties;
}) {
  const active = useContext(PageActivity);
  const grids = useRef(new Map<symbol, GridPreparation>());
  const [revision, setRevision] = useState(0), [published, setPublished] = useState(false);
  const callback = useRef(onSettledChange); callback.current = onSettledChange;
  const publishedCallback = useRef(onPublished); publishedCallback.current = onPublished;
  const notified = useRef<boolean | undefined>(undefined);
  const registry = useMemo<FirstReadRegistration>(() => ({
    register(id) { grids.current.set(id, 'preparing'); setRevision(n => n + 1); return () => { if (grids.current.delete(id)) setRevision(n => n + 1); }; },
    update(id, state) { if (grids.current.has(id) && grids.current.get(id) !== state) { grids.current.set(id, state); setRevision(n => n + 1); } },
  }), []);
  // Once a successor has been released, a retry must not hide it again.
  const settled = notified.current === true || published || (phase === 'error' && canPublish);
  useLayoutEffect(() => {
    if (!published && active && phase === 'content' && canPublish && [...grids.current.values()].every(value => value !== 'preparing')) setPublished(true);
  }, [active, canPublish, phase, published, revision]);
  useLayoutEffect(() => {
    if (notified.current !== settled) { notified.current = settled; callback.current?.(settled); }
  }, [settled]);
  useLayoutEffect(() => { if (published) publishedCallback.current?.(); }, [published]);
  const state = published ? 'ready' : phase === 'error' ? 'error' : phase === 'pending' ? 'pending' : 'preparing';
  return <FirstReadContext.Provider value={registry}><div className={className ? `first-read-region ${className}` : 'first-read-region'} style={style} data-first-read-state={state}>
    {!published && placeholder}
    {(published || phase === 'content') && <div className={published ? 'first-read-content' : 'first-read-content first-read-measuring'} inert={!published}>{children}</div>}
  </div></FirstReadContext.Provider>;
}

/** The minimal read query shape a region needs to describe itself. */
export interface ReadLike<T = unknown> {
  isPending: boolean;
  isFetching: boolean;
  isError: boolean;
  error: Error | null;
  data: T | undefined;
  refetch: () => unknown;
}

/**
 * idle: no permitted read yet, so nothing is announced.
 * reading: a read is in flight and there is nothing to show.
 * ready / empty: a result is on screen (empty means it has no rows).
 * error: the read failed and nothing is on screen.
 * stale: a result is on screen but its refresh failed.
 */
export type ReadPhase = 'idle' | 'reading' | 'ready' | 'empty' | 'error' | 'stale';

export function readPhase(read: ReadLike, empty = false): ReadPhase {
  if (read.isError) return read.data === undefined ? 'error' : 'stale';
  if (read.data === undefined) return read.isPending && read.isFetching ? 'reading' : 'idle';
  return empty ? 'empty' : 'ready';
}

/**
 * Neutral rows that occupy a region whose content is not known yet. They reuse
 * the region's row geometry and carry no values, counts or percentages.
 *
 * `quiet` keeps the same rows as pure space: a region that failed before it had
 * anything to show still holds its area, but nothing there suggests a read is
 * still running.
 */
export function ReadPlaceholder({ rows = 4, quiet = false }: { rows?: number; quiet?: boolean }) {
  return (
    <div className={quiet ? 'read-placeholder read-placeholder-quiet' : 'read-placeholder'} aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => <span key={index} />)}
    </div>
  );
}

/**
 * One fixed lane a region reports its read state in. It is present in every state, so a failure,
 * a running read or a retained result never adds a line and never moves the region's table.
 *
 * A region with more than one read (its own result plus a secondary list it depends on) passes one
 * `ReadFailure` per read: they sit side by side in this same lane, each with its own retry button.
 * The consuming page keeps its own class so it can set the lane's spacing; this component only
 * owns the shared geometry.
 */
export function ReadStatusLane({ phase, announce, className, children }: {
  phase: ReadPhase; announce?: string; className?: string; children?: ReactNode;
}) {
  return (
    <div className={className ? `read-status ${className}` : 'read-status'} data-read-phase={phase} aria-busy={phase === 'reading' || undefined}>
      {children}
      {phase === 'reading' && <p className="read-announce" role="status">{announce ?? '正在读取…'}</p>}
    </div>
  );
}

/**
 * In-place failure with retry; a result still on screen stays and says it is old.
 *
 * The message is wrapped so a consumer can keep the row one line tall (ellipsis) instead of
 * letting a long message wrap and change the region's height.
 */
export function ReadFailure({ read, retained, label }: { read: ReadLike; retained?: ReactNode; label?: string }) {
  const note = read.data === undefined ? null : (retained ?? '更新未成功，保留上次结果。');
  return (
    <p className="notice" role="alert">
      <span className="read-failure-text">{label ? `${label}：` : null}{note}{read.error?.message}</span>
      <Button htmlType="submit" onClick={() => void read.refetch()}>重试读取</Button>
    </p>
  );
}
