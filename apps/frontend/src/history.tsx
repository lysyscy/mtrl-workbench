import Button from 'antd/es/button';
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import type { Identity } from './api';

interface HistoryItem { id: number; label: string; count: number }
export function readHistory(value: unknown): { undo: HistoryItem | null; redo: HistoryItem | null; notice: string } {
  if (!record(value)) throw new ApiError('操作历史未能读取，请重试。');
  function item(value: unknown): HistoryItem | null {
    if (value === null) return null;
    if (!record(value) || !Number.isSafeInteger(value.id) || typeof value.label !== 'string' || typeof value.count !== 'number') throw new ApiError('操作历史未能读取，请重试。');
    return { id: Number(value.id), label: value.label, count: value.count };
  }
  return { undo: item(value.undo), redo: item(value.redo), notice: typeof value.notice === 'string' ? value.notice : '' };
}
const ReplayState = createContext({ busy: false, uncertain: false, setBusy: (_value: boolean) => {}, setUncertain: (_value: boolean) => {} });
export const useHistoryState = () => useContext(ReplayState);
export function HistoryGate({ children }: { children: ReactNode }) {
  const { busy, uncertain } = useHistoryState();
  return <div className="history-gate" inert={busy || uncertain} aria-busy={busy}>{children}</div>;
}
const Guards = createContext<Map<string, () => string> | null>(null);
export function useHistoryGuard(name: string, reason: () => string) {
  const guards = useContext(Guards), current = useRef(reason); current.current = reason;
  useEffect(() => { guards?.set(name, () => current.current()); return () => { guards?.delete(name); }; }, [guards, name]);
}
export function HistoryScope({ children }: { children: ReactNode }) {
  const [guards] = useState(() => new Map<string, () => string>());
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  return <ReplayState.Provider value={{ busy, uncertain, setBusy, setUncertain }}><Guards.Provider value={guards}>{children}</Guards.Provider></ReplayState.Provider>;
}
export function HistoryControls({ me, blocked, guard }: { me: Identity | null; blocked: boolean; guard: string }) {
  const client = useQueryClient(), guards = useContext(Guards);
  const owner = me ? `${me.id}:${me.account}` : 'anonymous';
  const history = useQuery({ queryKey: ['history', owner], enabled: Boolean(me) && !blocked,
    queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
  const { busy, uncertain, setBusy, setUncertain } = useHistoryState();
  const [feedback, setFeedback] = useState('');
  const lock = useRef(false), alive = useRef(true), request = useRef<AbortController | null>(null);
  const state = useRef({ me, blocked, guard }); state.current = { me, blocked, guard };
  useEffect(() => { alive.current = true; return () => { alive.current = false; request.current?.abort(); }; }, []);
  function protectedReason() {
    if (!state.current.me || state.current.blocked) return '当前账号暂不能操作。';
    if (state.current.guard) return state.current.guard;
    for (const reason of guards?.values() ?? []) { const text = reason(); if (text) return text; }
    if (document.querySelector('.ant-modal-wrap:not([style*="display: none"]),dialog[open]')) return '请先关闭弹窗。';
    return '';
  }
  async function reload() {
    if (lock.current || !state.current.me || state.current.blocked) return;
    lock.current = true; setBusy(true);
    try { await client.invalidateQueries({}, { throwOnError: true }); if (alive.current) { setUncertain(false); setFeedback('已重新读取，请核对操作结果。'); } }
    catch { if (alive.current) setFeedback('读取失败，请重读核对；勿重复撤销或重做。'); }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  async function replay(direction: 'undo' | 'redo') {
    if (lock.current || uncertain) return;
    const reason = protectedReason(); if (reason) { setFeedback(reason); return; }
    lock.current = true; setBusy(true); setFeedback('');
    const controller = new AbortController(); request.current = controller;
    let sent = false;
    try {
      const latest = await client.fetchQuery({ queryKey: ['history', owner], staleTime: 0,
        queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
      if (!alive.current || protectedReason()) return;
      const item = latest[direction]; if (!item) return;
      sent = true;
      const result = await requestJson(`/api/history/${direction}`, { method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation_id: item.id }) });
      if (!record(result) || result.ok !== true) throw new ApiError('操作结果未确认。');
      await client.invalidateQueries({}, { throwOnError: true });
      if (alive.current) setFeedback(direction === 'undo' ? '已撤销。' : '已重做。');
    } catch (error) {
      if (alive.current) { setUncertain(sent); setFeedback(sent ? '操作结果待核实，请重读核对；勿重复撤销或重做。' : error instanceof Error ? error.message : '操作历史读取失败，请重试。'); }
    } finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  const replayRef = useRef(replay); replayRef.current = replay;
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if (event.defaultPrevented || !(event.ctrlKey || event.metaKey) || event.altKey || event.isComposing) return;
      if (event.target instanceof Element && event.target.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[role="combobox"],.ag-custom-component-popup,.ant-dropdown')) return;
      const key = event.key.toLowerCase(), direction = key === 'z' ? event.shiftKey ? 'redo' : 'undo' : key === 'y' ? 'redo' : null;
      if (!direction || protectedReason()) return;
      event.preventDefault(); void replayRef.current(direction);
    };
    window.addEventListener('keydown', listener); return () => window.removeEventListener('keydown', listener);
  }, []);
  return <div className="history-tools">{(['undo', 'redo'] as const).map(direction => <Button key={direction}
    disabled={!me || blocked || busy || uncertain || Boolean(guard) || !history.data?.[direction]}
    title={guard || history.data?.[direction]?.label || history.data?.notice || '当前没有适用操作'}
    onClick={() => void replay(direction)}>{direction === 'undo' ? '撤销' : '重做'}</Button>)}
    {(feedback || history.isError || history.data?.notice) && <span role="status">{feedback || (history.isError ? '操作历史未能读取。' : history.data?.notice)}</span>}
    {(uncertain || history.isError) && <Button disabled={busy || blocked} onClick={() => void reload()}>重读核对</Button>}
  </div>;
}
