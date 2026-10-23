import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import { money } from './notices-api';
import type { Flow } from './flow-api';
import { DialogContents, useDialogClose } from './dialog-close';
export function FlowRevoke({ flow, blocked, close, completed }: { flow: Flow; blocked: boolean; close: () => void; completed: (notice: number | null, text: string) => void }) {
  const dialog = useRef<HTMLDialogElement>(null), client = useQueryClient(), lock = useRef(false);
  const [reason,setReason] = useState(''), [choice,setChoice] = useState(''), [busy,setBusy] = useState(false), [error,setError] = useState('');
  const info = useQuery({ queryKey: ['flow-revoke',flow.id], staleTime: 0, gcTime: 0, queryFn: async ({signal}) => {
    const value = await requestJson(`/api/m05/flows/${flow.id}/revoke-info`,{signal});
    if (!record(value) || typeof value.manual !== 'boolean' || typeof value.expected !== 'string') throw new ApiError('撤销信息不完整，请重开窗口。');
    return { manual: value.manual, expected: value.expected };
  }});
  useEffect(() => { if (blocked) dialog.current?.close(); else if (!dialog.current?.open) dialog.current?.showModal(); },[blocked]);
  const closing = useDialogClose({ busy, dirty: Boolean(reason || choice), close });
  async function submit() {
    if (blocked || lock.current || !reason.trim() || !info.data || info.data.manual && !choice) return;
    lock.current=true;setBusy(true);setError('');
    try {
      const params = new URLSearchParams({reason:reason.trim(),stat_choice:choice,expected:info.data.expected});
      const result=await requestJson(`/api/m05/flows/${flow.id}/revoke?${params}`,{method:'POST'});
      if (!record(result) || result.flow_id !== flow.id || result.status !== 'revoked') throw new ApiError('撤销结果未确认，请重新读取核对。');
      const effect=record(result.jc_effect) ? result.jc_effect : null;
      completed(flow.notice_id,`已撤销流水 ${flow.flow_no || '—'}。${effect ? `集采付款金额 ${money(String(effect.before))} → ${money(String(effect.after))} 元。${effect.protected ? '已保留人工统计付款金额。' : ''}` : ''}`);
      close();
      try { await client.invalidateQueries({predicate:query=>query.queryKey[0]!=='flow-revoke'}, {throwOnError:true}); }
      catch { completed(flow.notice_id,'撤销已完成，部分页面重读失败，请重试读取；勿重复撤销。'); }
    } catch (failure) { setError(failure instanceof Error ? failure.message : '撤销失败，请重试。'); }
    finally {lock.current=false;setBusy(false);}
  }
  return <dialog ref={dialog} className="flow-revoke" aria-labelledby="revoke-title" {...closing.dialogProps}><DialogContents title={<>撤销付款流水 · {flow.flow_no || '—'}</>} titleId="revoke-title" closing={closing}>
    <p>撤销后已付金额减少，付款状态重新判定。</p>
    <dl><dt>单据编码</dt><dd>{flow.doc_no || '—'}</dd><dt>付款项目</dt><dd>{flow.project_display || '—'}</dd><dt>付款金额</dt><dd>{money(flow.amount)} 元</dd><dt>付款日期 / 方式</dt><dd>{flow.pay_date || '—'} / {flow.pay_method || '—'}</dd></dl>
    {info.isPending && <p role="status">正在读取撤销信息…</p>}
    {info.isError && <p role="alert">{info.error.message}<button onClick={() => void info.refetch()}>重试</button></p>}
    {info.data?.manual && <fieldset disabled={busy || blocked}><legend>统计付款金额</legend><label><input type="radio" name="stat-choice" value="keep" checked={choice==='keep'} onChange={() => setChoice('keep')} />保留人工值</label><label><input type="radio" name="stat-choice" value="auto" checked={choice==='auto'} onChange={() => setChoice('auto')} />恢复按有效流水自动算</label></fieldset>}
    <label>撤销原因<input aria-label="撤销原因" value={reason} onChange={e=>setReason(e.target.value)} disabled={busy || blocked} /></label>
    {error && <p className="notice" role="alert">{error}</p>}
    <footer><button disabled={busy} onClick={closing.requestClose}>取消</button><button className="danger" disabled={busy || blocked || !reason.trim() || !info.data || info.data.manual && !choice} onClick={() => void submit()}>{busy?'正在撤销…':'确认撤销'}</button></footer>
  </DialogContents></dialog>;
}
