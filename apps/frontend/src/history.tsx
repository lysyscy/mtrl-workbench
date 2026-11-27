import { resetNoticeTodos } from './notice-todos';
import { DialogPresence } from './workspace-motion';
import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { HistoryDetailsBody, readHistoryDetails } from './history-details';
import type { HistoryDetails } from './history-details';
import { createContext, useContext, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useIsPresent } from 'motion/react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, record, requestJson, uncertainWrite } from './api';
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
type GuardAction = 'history' | 'reload';
type Guard = (action: GuardAction) => string;
const Guards = createContext<Map<string, Guard> | null>(null);
function guardReason(guards: Map<string, Guard> | null, action: GuardAction) {
  for (const reason of guards?.values() ?? []) { const text = reason(action); if (text) return text; }
  return '';
}
export function useReloadProtection() {
  const guards = useContext(Guards);
  const { busy, uncertain } = useHistoryState();
  return () => busy ? '操作历史正在处理，请稍候。' : uncertain ? '操作历史结果待核实，请先重读核对。' : guardReason(guards, 'reload');
}
export function useHistoryGuard(name: string, reason: Guard) {
  const guards = useContext(Guards), id = useId(), present = useIsPresent();
  const current = useRef(reason); current.current = present ? reason : () => '';
  useEffect(() => { const key = `${name}:${id}`; guards?.set(key, action => current.current(action)); return () => { guards?.delete(key); }; }, [guards, name, id]);
}
export function HistoryScope({ children, workspaceGuard = '' }: { children: ReactNode; workspaceGuard?: string }) {
  const currentWorkspaceGuard = useRef(workspaceGuard); currentWorkspaceGuard.current = workspaceGuard;
  const [guards] = useState(() => new Map<string, Guard>([['workspace', () => currentWorkspaceGuard.current]]));
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  const state = useMemo(() => ({ busy, uncertain, setBusy, setUncertain }), [busy, uncertain]);
  return <ReplayState.Provider value={state}><Guards.Provider value={guards}>{children}</Guards.Provider></ReplayState.Provider>;
}
export function HistoryControls({ me, blocked, guard }: { me: Identity | null; blocked: boolean; guard: string }) {
  const client = useQueryClient(), guards = useContext(Guards);
  const owner = me ? `${me.id}:${me.account}` : 'anonymous';
  const history = useQuery({ queryKey: ['history', owner], enabled: Boolean(me) && !blocked,
    queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
  const { busy, uncertain, setBusy, setUncertain } = useHistoryState();
  const [feedback, setFeedback] = useState('');
  const [confirmation, setConfirmation] = useState<{ direction: 'undo' | 'redo'; item: HistoryItem; details: HistoryDetails } | null>(null);
  // Replay has its own lock; a page guard for this modal would block its confirmation.
  const closing = useDialogClose({ busy, dirty: false, close: () => setConfirmation(null), open: Boolean(confirmation), active: false });
  const lock = useRef(false), alive = useRef(true), request = useRef<AbortController | null>(null);
  const state = useRef({ me, blocked, guard }); state.current = { me, blocked, guard };
  useEffect(() => { alive.current = true; return () => { alive.current = false; request.current?.abort(); }; }, []);
  function protectedReason(ownConfirmation = false) {
    if (!state.current.me || state.current.blocked) return '当前账号暂不能操作。';
    if (state.current.guard) return state.current.guard;
    const reason = guardReason(guards, 'history'); if (reason) return reason;
    const dialogs = document.querySelectorAll('.ant-modal-wrap:not([style*="display: none"]):not(.business-modal-leaving *),dialog[open]');
    if ([...dialogs].some(dialog => !ownConfirmation || !dialog.querySelector('.history-confirm-dialog'))) return '请先关闭弹窗。';
    return '';
  }
  async function reload() {
    if (lock.current || !state.current.me || state.current.blocked) return;
    lock.current = true; setBusy(true);
    try { await client.invalidateQueries({}, { throwOnError: true }); if (alive.current) { setUncertain(false); setFeedback('已重新读取，请核对操作结果。'); } }
    catch { if (alive.current) setFeedback('读取失败，请重读核对；勿重复撤销或重做。'); }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  async function replay(direction: 'undo' | 'redo', expected?: HistoryItem) {
    if (lock.current || uncertain) return;
    const reason = protectedReason(Boolean(expected)); if (reason) { setFeedback(reason); return; }
    lock.current = true; setBusy(true); setFeedback('');
    const controller = new AbortController(); request.current = controller;
    let sent = false, confirmed = false;
    try {
      const latest = await client.fetchQuery({ queryKey: ['history', owner], staleTime: 0,
        queryFn: async ({ signal }) => readHistory(await requestJson('/api/history/status', { signal })) });
      if (!alive.current || protectedReason(Boolean(expected))) return;
      const item = latest[direction];
      if (!item || expected && item.id !== expected.id) { setConfirmation(null); setFeedback('可操作的历史已变化，请重新查看后再确认。'); return; }
      if (!expected) {
        const details = readHistoryDetails(await requestJson(`/api/history/${direction}/details?operation_id=${item.id}`,
          { signal: controller.signal }), item);
        if (alive.current && !protectedReason()) setConfirmation({ direction, item, details });
        return;
      }
      sent = true;
      const result = await requestJson(`/api/history/${direction}`, { method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation_id: item.id }) });
      if (!record(result) || result.ok !== true) throw new ApiError('操作结果未确认。');
      confirmed = true; setConfirmation(null);
      void resetNoticeTodos(client);
      await client.invalidateQueries({}, { throwOnError: true });
      if (alive.current) setFeedback(direction === 'undo' ? '已撤销。' : '已重做。');
    } catch (error) {
      if (alive.current) {
        const unknown = confirmed || sent && uncertainWrite(error);
        setUncertain(unknown); if (unknown) setConfirmation(null);
        setFeedback(confirmed ? '操作已完成，重读失败，请重读核对；勿重复撤销或重做。' : unknown ? '操作结果待核实，请重读核对；勿重复撤销或重做。' : error instanceof Error ? error.message : '操作历史读取失败，请重试。');
      }
    } finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  return <div className="history-tools">{(['undo', 'redo'] as const).map(direction => <Button key={direction}
    disabled={!me || blocked || busy || uncertain || Boolean(guard) || !history.data?.[direction]}
    title={guard || history.data?.[direction]?.label || history.data?.notice || '当前没有适用操作'}
    onClick={() => void replay(direction)}>
    <svg className="history-direction-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d={direction === 'undo' ? 'm9 6-5 5 5 5m-5-5h10a5 5 0 0 1 5 5v2' : 'm15 6 5 5-5 5m5-5H10a5 5 0 0 0-5 5v2'} />
    </svg>
    {direction === 'undo' ? '撤销' : '重做'}
  </Button>)}
    {(feedback || history.isError) && <span role="status">{feedback || '操作历史未能读取。'}</span>}
    {(uncertain || history.isError) && <Button disabled={busy || blocked} onClick={() => void reload()}>重读核对</Button>}
    <DialogPresence>{confirmation && <BusinessModal open={!blocked} layout="scroll-body" requestClose={closing.requestClose}
      className={`history-confirm-dialog history-details-dialog${confirmation.item.count > 1 ? ' history-details-batch' : ''}`} titleId="history-confirm-title">
      <DialogContents title={`${confirmation.direction === 'undo' ? '撤销' : '重做'} · ${confirmation.item.label}`} titleId="history-confirm-title" closing={closing}>
        <div className="dialog-body history-details-scroll">
          <HistoryDetailsBody records={confirmation.details.records} />
          {feedback && <p className="notice" role="alert">{feedback}</p>}
        </div>
        <div className="history-details-footer">
          {confirmation.item.count > 1 && <span>本次整批执行</span>}
          <div className="dialog-actions">
            <Button autoFocus disabled={busy} onClick={closing.requestClose}>取消</Button>
            <Button type="primary" danger={confirmation.details.records.some(item => item.removes)} loading={busy}
              disabled={blocked || uncertain} onClick={() => void replay(confirmation.direction, confirmation.item)}>
              {confirmation.direction === 'undo' ? '确认撤销' : '确认重做'}
            </Button>
          </div>
        </div>
      </DialogContents>
    </BusinessModal>}</DialogPresence>
  </div>;
}
