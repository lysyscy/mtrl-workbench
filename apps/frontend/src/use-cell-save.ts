import { useEffect, useRef, useSyncExternalStore } from 'react';
import { useHistoryGuard } from './history';
import { CellSaveQueue } from './cell-save';
import type { CellSaveOptions } from './cell-save';

export function useCellSaveQueue<D extends { error: string }, R>(options: CellSaveOptions<D, R>,
  history: { key: string; label: string; pending?: boolean }) {
  const current = useRef(options); current.current = options;
  const queue = useRef<CellSaveQueue<D, R> | null>(null);
  if (!queue.current) queue.current = new CellSaveQueue(() => current.current);
  const saves = queue.current;
  const snapshot = useSyncExternalStore(saves.subscribe, saves.getSnapshot);
  useEffect(() => { saves.mount(); return saves.dispose; }, [saves]);
  useEffect(() => { if (!options.enabled) saves.pause(); }, [saves, options.enabled]);
  useHistoryGuard(history.key, () => {
    const value = saves.getSnapshot();
    return value.busy ? `${history.label}正在保存，请稍候。` : value.uncertain ? `${history.label}结果待核实，请先重读核对。`
      : Object.keys(value.drafts).length || history.pending ? `${history.label}有未保存输入，请先处理。` : '';
  });
  return { ...snapshot, update: saves.update, save: saves.save, run: saves.run, reread: saves.reread,
    confirm: saves.confirm, clearFeedback: saves.clearFeedback, reconcile: saves.reconcile };
}
