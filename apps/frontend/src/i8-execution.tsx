import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { NavLink } from 'react-router';
import { ApiError, readIdentity, record, requestJson } from './api';
import type { Identity } from './api';
import { actionLabel, executeI8, readAction } from './i8-api';
import type { I8Action } from './i8-api';
import './i8.css';

interface Execution { action: I8Action; startedAt: string; phase: 'pending' | 'success' | 'partial' | 'failed' | 'uncertain'; message: string }
interface ExecutionContext { execution: Execution | null; busy: boolean; prepare: (action: I8Action) => void; dismiss: () => void; acknowledge: () => void }
const Context = createContext<ExecutionContext | null>(null);
function restore(key: string): Execution | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(key) ?? 'null');
    if (!record(value) || !readAction(value.action) || typeof value.startedAt !== 'string' || !Number.isFinite(Date.parse(value.startedAt)) || typeof value.message !== 'string' || !['pending', 'success', 'partial', 'failed', 'uncertain'].includes(String(value.phase))) return null;
    const execution = value as unknown as Execution;
    return execution.phase === 'pending' ? { ...execution, phase: 'uncertain', message: '上次任务的回执尚未确认，任务可能仍在执行。请先核对执行记录。' } : execution;
  } catch { return null; }
}
export function useI8Execution(): ExecutionContext {
  const context = useContext(Context);
  if (!context) throw new Error('Missing i8 execution owner');
  return context;
}
export function I8ExecutionProvider({ me, blocked, children }: { me: Identity | null; blocked: boolean; children: ReactNode }) {
  const key = `mtrl-i8:${me?.id ?? 0}:${me?.account ?? ''}`;
  const [execution, setExecution] = useState<Execution | null>(() => restore(key));
  const [prepared, setPrepared] = useState<I8Action | null>(null);
  const [allowKick, setAllowKick] = useState(false);
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const gate = useRef(false);
  const mounted = useRef(false);
  const paused = useRef(blocked); paused.current = blocked;
  const dialog = useRef<HTMLDialogElement>(null);
  const client = useQueryClient();
  const busy = execution?.phase === 'pending' || execution?.phase === 'uncertain';
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (prepared && !blocked) dialog.current?.showModal(); else dialog.current?.close();
    return () => dialog.current?.close();
  }, [prepared, blocked]);
  useEffect(() => {
    if (execution?.phase !== 'pending') return;
    const update = () => setElapsed(Math.max(0, Math.floor((Date.now() - Date.parse(execution.startedAt)) / 1000)));
    update(); const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [execution]);
  function publish(next: Execution | null) {
    if (next) sessionStorage.setItem(key, JSON.stringify(next)); else sessionStorage.removeItem(key);
    if (mounted.current) setExecution(next);
  }
  function prepare(action: I8Action) {
    if (!me || paused.current || busy || gate.current) return;
    setAllowKick(false); setError(''); setPrepared(action);
  }
  async function start() {
    if (!prepared || !me || paused.current || busy || gate.current) return;
    gate.current = true;
    const action = prepared, kick = allowKick;
    const pending: Execution = { action, startedAt: new Date().toISOString(), phase: 'pending', message: '正在核实账号…' };
    try { publish(pending); } catch { setError('浏览器无法保存任务状态，请检查浏览器存储后重试。'); gate.current = false; return; }
    setPrepared(null);
    let sent = false;
    try {
      const identity = readIdentity(await requestJson('/api/m15/users'));
      if (!identity || identity.id !== me.id || identity.account !== me.account || paused.current || !mounted.current) throw new ApiError('账号已变化或尚未核实，请重新进入页面后操作。', 409);
      publish({ ...pending, message: '正在执行，等待 i8 回执…' });
      sent = true;
      const result = await executeI8(action, me.account, kick);
      publish({ ...pending, phase: result.partial ? 'partial' : 'success', message: result.message });
    } catch (failure) {
      const known = !sent || (failure instanceof ApiError && (failure.status === 401 || failure.status === 403 || failure.status === 409 || ['external_service', 'must_report', 'not_configured'].includes(failure.code)));
      const message = failure instanceof ApiError && failure.code === 'external_service' ? 'i8 这次取数未完成，请查看执行记录，核对账号、配置及网络后重新准备。' : failure instanceof Error ? failure.message : '执行未完成，请查看执行记录。';
      try { publish({ ...pending, phase: known ? 'failed' : 'uncertain', message: known ? message : '未收到完整回执，任务可能仍在执行或已经写入。请先核对执行记录，再决定是否重新抓取。' }); }
      catch { if (mounted.current) setExecution({ ...pending, phase: 'uncertain', message: '回执状态保存失败，请先核对执行记录。' }); }
    } finally {
      gate.current = false;
      if (mounted.current) void client.invalidateQueries();
    }
  }
  return <Context.Provider value={{ execution, busy, prepare, dismiss: () => setPrepared(null), acknowledge: () => { if (execution?.phase === 'uncertain' && !gate.current) { try { publish(null); setError(''); } catch { setError('任务状态无法清除，请检查浏览器存储。'); } } } }}>
    {error && <p className="notice" role="alert">{error}</p>}
    {execution?.phase === 'pending' && <div className="i8-progress" role="status"><strong>{actionLabel(execution.action)}</strong><span>{execution.message} · 已等待 {elapsed} 秒</span><NavLink to="/i8">查看任务</NavLink></div>}
    {children}
    <dialog ref={dialog} className="ledger-export-dialog i8-dialog" aria-labelledby="i8-confirm-title" onCancel={() => setPrepared(null)}>
      <form onSubmit={event => { event.preventDefault(); void start(); }}>
        <h2 id="i8-confirm-title">{prepared ? actionLabel(prepared) : '确认执行'}</h2>
        <p>将使用当前账号绑定的 i8 账号执行；可能需要登录 i8。抓取失败不会自动重试。</p>
        <label className="i8-kick"><input type="checkbox" checked={allowKick} onChange={event => setAllowKick(event.target.checked)} />允许强踢该 i8 账号的其他在线会话</label>
        <p className="muted">未勾选时，遇到在线冲突将停止；勾选后可能中断同事正在使用的 i8。</p>
        <div className="dialog-actions"><button type="button" onClick={() => setPrepared(null)}>取消</button><button className="primary" type="submit" disabled={blocked || busy}>{allowKick ? '确认强踢并执行' : '确认执行'}</button></div>
      </form>
    </dialog>
  </Context.Provider>;
}
