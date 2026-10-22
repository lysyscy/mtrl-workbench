import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, readIdentity, record, requestJson } from './api';
import type { Identity } from './api';

interface Address { stored: string; effective: string; env: string; version: string }
function readAddress(value: unknown): Address {
  const item = record(value) && value.ok === true && Array.isArray(value.items) ? value.items.find((item: unknown) => record(item) && item.key === 'i8_base_url') : null;
  if (!record(item) || !['stored', 'effective', 'env', 'version'].every(key => typeof item[key] === 'string')) throw new ApiError('地址配置读取不完整，请重读配置。');
  return item as unknown as Address;
}
export function I8AddressEditor({ me, blocked, onClose }: { me: Identity; blocked: boolean; onClose: () => void }) {
  const key = `mtrl-i8-address:${me.id}:${me.account}`;
  const [draft, setDraft] = useState('');
  const [address, setAddress] = useState<Address | null>(null);
  const [phase, setPhase] = useState<'loading' | 'editing' | 'saving' | 'verify' | 'uncertain'>('loading');
  const [message, setMessage] = useState('');
  const [reading, setReading] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  const mounted = useRef(false), gate = useRef(false), paused = useRef(blocked);
  paused.current = blocked;
  const client = useQueryClient();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; returnFocus.current?.focus(); }; }, []);
  useEffect(() => {
    if (!blocked) dialog.current?.showModal(); else dialog.current?.close();
    return () => dialog.current?.close();
  }, [blocked]);
  useEffect(() => {
    const controller = new AbortController();
    let pending: string | null;
    try { pending = sessionStorage.getItem(key); }
    catch { setMessage('浏览器无法保存操作状态，请检查浏览器存储后重新打开。'); return; }
    if (pending !== null) {
      setDraft(pending); setPhase('uncertain');
      setMessage('上次保存结果待核实，请先重读配置；再次保存会核对是否已变化。');
    }
    void requestJson('/api/m14/settings', { signal: controller.signal }).then(readAddress).then(value => {
      setAddress(value);
      if (pending === null) { setDraft(value.stored); setPhase('editing'); }
    }).catch(error => {
      if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : '配置读取失败，请重读配置。');
    });
    return () => controller.abort();
  }, [key]);
  async function reread() {
    if (gate.current || paused.current) return;
    gate.current = true; setReading(true);
    try {
      const value = readAddress(await requestJson('/api/m14/settings'));
      if (!mounted.current) return;
      setAddress(value);
      await client.invalidateQueries();
      if (!mounted.current) return;
      sessionStorage.removeItem(key); if (phase === 'loading') setDraft(value.stored); setPhase('editing');
      setMessage(phase === 'verify' ? '已保存并重读配置（改动已留痕）。' : '已重读当前配置；再次保存会核对是否已变化。');
    } catch (error) { if (mounted.current) setMessage(error instanceof Error ? error.message : '配置读取失败，请重读配置。'); }
    finally { gate.current = false; if (mounted.current) setReading(false); }
  }
  async function save() {
    if (gate.current || paused.current || phase !== 'editing' || !address) return;
    gate.current = true; setPhase('saving'); setMessage('正在核实账号…');
    let sent = false, accepted = false;
    try {
      const identity = readIdentity(await requestJson('/api/m15/users'));
      if (!identity || identity.id !== me.id || identity.account !== me.account || paused.current || !mounted.current) throw new ApiError('账号已变化或尚未核实，请重新进入页面后操作。', 409);
      // Persist before sending: leaving/reloading the page must not enable a blind retry.
      sessionStorage.setItem(key, draft);
      setMessage('正在保存服务地址…'); sent = true;
      const value = readAddress(await requestJson(`/api/m14/settings?expected_account=${encodeURIComponent(me.account)}&expected_version=${encodeURIComponent(address.version)}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ i8_base_url: draft }),
      }));
      if (value.stored !== draft.trim()) throw new ApiError('保存回执与输入不符，请重读配置后核对。');
      accepted = true;
      if (!mounted.current) return;
      setPhase('verify'); setMessage('已保存，正在重读配置…');
      const current = readAddress(await requestJson('/api/m14/settings'));
      await client.invalidateQueries();
      if (!mounted.current) return;
      sessionStorage.removeItem(key); setAddress(current); setDraft(current.stored); setPhase('editing');
      setMessage(current.stored === value.stored ? '已保存并重读配置（改动已留痕）。' : '本次已保存，配置随后又有变化，请核对当前生效值。');
    } catch (error) {
      if (!mounted.current) return;
      const known = !sent || error instanceof ApiError && ((error.status === 200 && error.rejected) || [400, 401, 403, 409, 422].includes(error.status));
      if (accepted) { setPhase('verify'); setMessage('已保存，重读配置失败。请重读核对，勿重复保存。'); }
      else if (known) {
        try { sessionStorage.removeItem(key); setPhase('editing'); setMessage(error instanceof Error ? error.message : '保存未完成，请核对后重试。'); }
        catch { setPhase('uncertain'); setMessage('保存状态暂时无法清除，请检查浏览器存储后重读配置。'); }
      }
      else { setPhase('uncertain'); setMessage('保存结果待核实，可能已经写入。请先重读配置，勿重复保存。'); }
    } finally { gate.current = false; }
  }
  const locked = phase === 'saving';
  function close() { dialog.current?.close(); onClose(); returnFocus.current?.focus(); }
  return <dialog ref={dialog} className="ledger-export-dialog i8-dialog i8-address-dialog" aria-labelledby="i8-address-title" onCancel={event => { if (locked) event.preventDefault(); else { event.preventDefault(); close(); } }}>
    <form noValidate onSubmit={event => { event.preventDefault(); void save(); }}>
      <h2 id="i8-address-title">i8 连接设置</h2>
      {address && <dl><dt>{phase === 'saving' || phase === 'uncertain' || phase === 'verify' ? '上次读取' : '当前生效'}</dt><dd>{address.effective || '未配置'}（{address.stored ? '界面所设' : '环境配置'}）</dd><dt>环境回落</dt><dd>{address.env || '未配置'}</dd></dl>}
      <label className="i8-address-field">服务地址<input autoFocus type="text" inputMode="url" autoComplete="off" spellCheck={false} value={draft} disabled={blocked || phase !== 'editing'} onChange={event => { setDraft(event.target.value); setMessage(''); }} aria-describedby="i8-address-hint" /></label>
      <p id="i8-address-hint" className="muted">清空并保存后使用环境配置。此处修改全局地址，不会试连或登录 i8。</p>
      {message && <p role={phase === 'saving' || message.startsWith('已保存并') ? 'status' : 'alert'}>{message}</p>}
      <div className="dialog-actions">
        <button type="button" disabled={locked} onClick={close}>{phase === 'uncertain' || phase === 'verify' ? '关闭' : '取消'}</button>
        <button type="button" disabled={blocked || locked || reading} onClick={() => void reread()}>{reading ? '正在重读…' : '重读配置'}</button>
        <button key="save" className="primary" type="submit" disabled={blocked || phase !== 'editing' || reading || !address}>{locked ? '正在保存…' : '保存地址'}</button>
      </div>
    </form>
  </dialog>;
}
