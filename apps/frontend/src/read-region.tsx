import './read-region.css';
import Button from 'antd/es/button';
import type { ReactNode } from 'react';

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
