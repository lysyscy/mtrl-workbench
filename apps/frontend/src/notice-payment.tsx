import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import { body, cents, decimal, money, readNotices, receipt } from './notices-api';
import type { NoticeRow } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';

export interface PayOverride { value: string; basis: string }
const basis = (row: NoticeRow) => `${row.amount_approved}:${row.amount_paid}`;
export function paymentValue(row: NoticeRow, overrides: Record<number, PayOverride>): string {
  const draft = overrides[row.notice_id];
  return draft?.basis === basis(row) ? draft.value : row.pay_amount;
}
function amount(raw: string): string | null {
  const value = raw.replace(/[,，\s¥￥]/g, '');
  return /^-?\d+(?:\.\d{1,2})?$/.test(value) ? decimal(cents(value)) : null;
}
export function PayAmountCell({ row, override, disabled, change }: { row: NoticeRow; override: PayOverride | undefined; disabled: boolean; change: (row: NoticeRow, value: string) => void }) {
  const shown = override?.basis === basis(row) ? override.value : row.pay_amount;
  const [value,setValue] = useState(shown), [error,setError] = useState('');
  useEffect(() => { setValue(shown);setError(''); }, [shown,row.amount_approved,row.amount_paid]);
  function commit() {
    const parsed = value.trim() ? amount(value) : decimal(cents(row.amount_approved)-cents(row.amount_paid));
    if (parsed === null) { setError('金额不合法，请修改'); return; }
    setError('');setValue(parsed);change(row,parsed);
  }
  return <span><input aria-label={`${row.bill_no}付款金额`} aria-invalid={Boolean(error)} inputMode="decimal" title="仅本次会话有效；清空恢复审批金额减已付金额" disabled={disabled} value={value} onChange={e => setValue(e.target.value)} onBlur={commit} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault();commit(); } if (e.key === 'Escape') { setValue(shown);setError(''); } }} />{error && <small role="alert">{error}</small>}</span>;
}
interface PaymentDraft { amount: string; pay_method: string }
interface FlowReceipt { notice_id: number; flow_no: string; amount: string; pay_date: string; pay_method: string; remark: string }
export function NoticePayment({ ids, overrides, blocked, remove, close, paid, refresh, announce }: { ids: number[]; overrides: Record<number,PayOverride>; blocked: boolean; remove: (id: number) => void; close: () => void; paid: (ids: number[]) => void; refresh: () => Promise<void>; announce: (message: string) => void }) {
  const dialog = useRef<HTMLDialogElement>(null), lock = useRef(false), requestId = useRef(''), removing = useRef<number | null>(null);
  const originalIds = useRef(ids), drafts = useRef<Record<number,PaymentDraft>>({});
  const [revision,setRevision] = useState(0), [phase,setPhase] = useState<'edit'|'sending'|'saved'|'uncertain'>('edit');
  const [date,setDate] = useState(() => new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()));
  const [remark,setRemark] = useState(''), [error,setError] = useState(''), [message,setMessage] = useState(''), [flows,setFlows] = useState<FlowReceipt[]>([]), [refreshFailed,setRefreshFailed] = useState(false);
  const query = useQuery({ queryKey: ['notice-payment',originalIds.current], enabled: !blocked && phase === 'edit', retry: false, refetchOnWindowFocus: false, queryFn: async ({signal}) => {
    const value = await requestJson('/api/m03/notice-list?period=',{signal});
    if (!record(value) || !Array.isArray(value.payment_methods) || !value.payment_methods.every(v => typeof v === 'string') || !value.payment_methods.length) throw new ApiError('付款方式读取不完整，请重试。');
    return { rows: readNotices(value), methods: value.payment_methods as string[] };
  } });
  useEffect(() => { if (blocked) dialog.current?.close(); else if (!dialog.current?.open) dialog.current?.showModal(); }, [blocked]);
  const initialDate = useRef(date), initialDrafts = useRef<Record<number,PaymentDraft>>({});
  const rows = ids.map(id => query.data?.rows.find(row => row.notice_id === id)).filter((row): row is NoticeRow => Boolean(row));
  const excluded = rows.filter(row => row.is_excluded || row.is_revoked), targets = rows.filter(row => !row.is_excluded && !row.is_revoked);
  const missing = ids.filter(id => !rows.some(row => row.notice_id === id));
  function draft(row: NoticeRow): PaymentDraft { const fallback = { amount: paymentValue(row,overrides), pay_method: row.planned_pay_method || '现汇' }; initialDrafts.current[row.notice_id] ??= fallback; return drafts.current[row.notice_id] ?? fallback; }
  function update(row: NoticeRow, field: keyof PaymentDraft, value: string) { drafts.current[row.notice_id] = {...draft(row),[field]:value};setRevision(revision+1); }
  function reason(row: NoticeRow): string { return row.pay_block_reason || (cents(paymentValue(row,overrides)) <= 0n ? '本次应付不大于0，请调整付款金额' : ''); }
  const invalid = targets.some(row => reason(row)), busy = phase === 'sending', editable = phase === 'edit';
  const dirty = phase !== 'saved' && (date !== initialDate.current || Boolean(remark) || Object.entries(drafts.current).some(([id,value]) => { const initial = initialDrafts.current[Number(id)]; return !initial || value.amount !== initial.amount || value.pay_method !== initial.pay_method; }));
  const closing = useDialogClose({ busy, dirty, close: () => { const id = removing.current; removing.current = null; if (id !== null) remove(id); close(); } });
  const paymentClosing = { ...closing, resume: () => { removing.current = null; closing.resume(); } };
  function removeRow(id: number) { if(ids.length===1) { removing.current = id; closing.requestClose(); } else remove(id); }
  async function reread() {
    setRefreshFailed(false);
    try { await refresh(); } catch { setRefreshFailed(true); }
  }
  async function submit() {
    if (blocked || lock.current || !editable || invalid || missing.length || !targets.length || query.isFetching || query.isError) return;
    const next: Record<string,PaymentDraft> = {}, errors: string[] = [];
    for (const row of targets) {
      const d = draft(row), normalized = amount(d.amount), ceiling = cents(paymentValue(row,overrides));
      if (normalized === null || cents(normalized) <= 0n) errors.push(`${row.bill_no}：付款金额须大于0`);
      else if (cents(normalized) > ceiling) errors.push(`${row.bill_no}：付款金额超出本次应付 ${money(paymentValue(row,overrides))}`);
      if (d.pay_method === '其他' && !remark.trim()) errors.push(`${row.bill_no}：选择其他须填本批付款备注`);
      next[String(row.notice_id)] = {...d,amount:normalized ?? d.amount};
    }
    if (!date) errors.push('请填写付款日期');
    if (errors.length) { setError(errors.join('；'));return; }
    lock.current=true;setPhase('sending');setError('');
    requestId.current ||= crypto.randomUUID();
    let saved = false;
    try {
      const value = await requestJson('/api/m03/actions/batch-pay',{method:'POST',...body({ids:targets.map(row => row.notice_id),drafts:next,pay_date:date,remark:remark.trim(),request_id:requestId.current})});
      saved=true;setPhase('saved');paid(targets.map(row => row.notice_id));
      const text = receipt(value);setMessage(text);announce(text);
      if (!record(value) || !Array.isArray(value.flows) || !Array.isArray(value.created) || value.flows.length !== value.created.length || !value.flows.every(f => record(f) && Number.isSafeInteger(f.notice_id) && ['flow_no','amount','pay_date','pay_method','remark'].every(k => typeof f[k] === 'string'))) throw new ApiError('付款已登记，流水回执不完整，请到付款流水核对，勿重复付款。');
      setFlows(value.flows as FlowReceipt[]);
      const skipped = targets.filter(row => !(value.created as number[]).includes(row.notice_id));
      if (skipped.length) setMessage(`${text}；本次未登记：${skipped.map(row => row.bill_no).join('、')}，请重读核对状态。`);
      await reread();
    } catch (failure) {
      if (!saved) {
        const rejected = failure instanceof ApiError && failure.status > 0 && failure.status < 500;
        setPhase(rejected ? 'edit' : 'uncertain');
        if (rejected) void query.refetch();
      }
      setError(`${saved ? '付款已登记，勿重复提交。' : failure instanceof ApiError && failure.status > 0 && failure.status < 500 ? '整批未登记，输入已保留。' : '提交结果尚未核实，请重读列表并到付款流水核对，勿重复付款。'}${failure instanceof Error ? failure.message : '请重读核对。'}`);
    } finally { lock.current=false; }
  }
  return <dialog ref={dialog} className="project-dialog notice-pay-dialog" aria-labelledby="notice-pay-title" {...closing.dialogProps}><DialogContents title={phase === 'saved' ? '付款结果' : '批量付款'} titleId="notice-pay-title" closing={paymentClosing}>
    {query.isPending && editable ? <p role="status">正在核对付款记录…</p> : query.isError && editable ? <p className="notice" role="alert">{query.error.message}<button onClick={() => void query.refetch()}>重读</button></p> : <>
      {message && <p role="status" className="notice-feedback">{message}</p>}
      {editable && <p>任一校验不通过，整批不产生流水；选「其他」须填备注。</p>}
      {excluded.length > 0 && <p className="notice" role="alert">已排除 {excluded.length} 条：{excluded.map(row => `${row.bill_no}（${row.pay_block_reason}）`).join('、')}</p>}
      {missing.length > 0 && <p className="notice" role="alert">{missing.length} 条记录已不在列表，请关闭并重新勾选核对。</p>}
      {editable && invalid && <p className="notice" role="alert">请移出不可付记录，或关闭后处理其状态。集采未关联的记录须先关联合同。</p>}
      {phase === 'saved' ? flows.length > 0 && <div className="notice-pay-table"><table><thead><tr>{['单据编码','付款流水号','付款日期','方式','实付金额','备注'].map(t => <th key={t}>{t}</th>)}</tr></thead><tbody>{flows.map(flow => <tr key={flow.flow_no}><td>{rows.find(row => row.notice_id===flow.notice_id)?.bill_no}</td><td>{flow.flow_no}</td><td>{flow.pay_date}</td><td>{flow.pay_method}</td><td className="money">{money(flow.amount)}</td><td>{flow.remark || '—'}</td></tr>)}</tbody></table></div> : <div className="notice-pay-table"><table><thead><tr>{['单据编码','付款项目','审批状态','审批金额','已付金额','本次应付','实际付款方式','本次付款金额','操作'].map(t => <th key={t}>{t}</th>)}</tr></thead><tbody>{targets.map(row => <tr key={row.notice_id}><td>{row.bill_no}</td><td title={row.project_name}>{row.project_display}</td><td>{row.approve_status || '未批'}</td><td className="money">{money(row.amount_approved)}</td><td className="money">{money(row.amount_paid)}</td><td className="money">{money(paymentValue(row,overrides))}</td><td>{reason(row) ? <span className="notice-tag rule">{reason(row)}</span> : <select aria-label={`${row.bill_no}实际付款方式`} disabled={!editable||blocked} value={draft(row).pay_method} onChange={e => update(row,'pay_method',e.target.value)}>{query.data?.methods.map(method => <option key={method}>{method}</option>)}</select>}</td><td>{!reason(row) && <input aria-label={`${row.bill_no}本次付款金额`} inputMode="decimal" disabled={!editable||blocked} value={draft(row).amount} onChange={e => update(row,'amount',e.target.value)} />}</td><td><button disabled={!editable||blocked} onClick={() => removeRow(row.notice_id)}>移出</button></td></tr>)}</tbody><tfoot><tr><th colSpan={5}>合计（元）</th><td className="money">{money(decimal(targets.reduce((sum,row) => sum+cents(paymentValue(row,overrides)),0n)))}</td><td></td><td className="money">{targets.every(row => amount(draft(row).amount)!==null) ? money(decimal(targets.reduce((sum,row) => sum+cents(amount(draft(row).amount)!),0n))) : '待核对'}</td><td></td></tr></tfoot></table></div>}
      {phase !== 'saved' && <div className="notice-pay-fields"><label>付款日期<input type="date" value={date} disabled={!editable||blocked} onChange={e => setDate(e.target.value)} /></label><label>本批付款备注<input value={remark} disabled={!editable||blocked} onChange={e => setRemark(e.target.value)} /></label></div>}
    </>}
    {error && <p className="notice" role="alert">{error}</p>}
    {refreshFailed && <p className="notice" role="alert">付款已登记，列表尚待重读核对。<button onClick={() => void reread()}>重读核对</button></p>}
    <div className="dialog-actions"><button disabled={busy} onClick={closing.requestClose}>{phase === 'saved' ? '关闭' : '取消'}</button>{phase === 'uncertain' && <button onClick={() => void reread()}>重读列表核对</button>}{editable && <button className="primary" disabled={blocked||busy||query.isPending||query.isFetching||query.isError||invalid||Boolean(missing.length)||!targets.length} onClick={() => void submit()}>确认付款</button>}{busy && <span role="status">正在提交…</span>}</div>
  </DialogContents></dialog>;
}