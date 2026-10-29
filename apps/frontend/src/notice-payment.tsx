import Input from 'antd/es/input';
import type { Project } from './api';
import { BusinessDate } from './time-picker';
import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { ReadGrid } from './business-grid';
import { PaymentGrid } from './notice-payment-grid';
import { numberColumnWidth,fullTextWidth } from './grid';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, confirmWrite, uncertainWrite, record, requestJson, projectLabel } from './api';
import { body, cents, decimal, money, readNotices, receipt } from './notices-api';
import { readPaymentContext } from './payment-context';
import type { PaymentContext } from './payment-context';
import { PaymentTerms } from './payment-terms';
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
export function NoticePayment({ ids, overrides, projects, blocked, remove, close, paid, refresh, announce }: { ids: number[]; overrides: Record<number,PayOverride>; projects: Project[]; blocked: boolean; remove: (id: number) => void; close: () => void; paid: (ids: number[]) => void; refresh: () => Promise<void>; announce: (message: string) => void }) {
  const lock = useRef(false), requestId = useRef(''), removing = useRef<number | null>(null);
  const active = useRef(true), currentBlocked = useRef(blocked), preflight = useRef<AbortController | null>(null);
  currentBlocked.current = blocked;
  useEffect(() => { active.current=true;return () => { active.current=false;preflight.current?.abort(); }; }, []);
  useEffect(() => { if (blocked) preflight.current?.abort(); }, [blocked]);
  const originalIds = useRef(ids), drafts = useRef<Record<number,Partial<PaymentDraft>>>({});
  const [revision,setRevision] = useState(0), [phase,setPhase] = useState<'edit'|'checking'|'confirm'|'sending'|'saved'|'uncertain'>('edit');
  const [date,setDate] = useState(() => new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()));
  const [remark,setRemark] = useState(''), [error,setError] = useState(''), [message,setMessage] = useState(''), [flows,setFlows] = useState<FlowReceipt[]>([]), [refreshFailed,setRefreshFailed] = useState(false);
  const query = useQuery({ queryKey: ['notice-payment',originalIds.current], enabled: !blocked && phase === 'edit', retry: false, refetchOnWindowFocus: false, queryFn: async ({signal}) => {
    const value = await requestJson(`/api/m03/payment-preview?${new URLSearchParams(originalIds.current.map(id => ['ids',String(id)]))}`,{signal});
    if (!record(value) || !Array.isArray(value.payment_methods) || !value.payment_methods.every(v => typeof v === 'string') || !value.payment_methods.length) throw new ApiError('付款方式读取不完整，请重试。');
    return { rows: readNotices(value), methods: value.payment_methods as string[] };
  } });
  const defaults = useRef<Record<number,string>>({});
  const confirmed = useRef<{ ids: number[]; drafts: Record<string,PaymentDraft>; pay_date: string; remark: string } | null>(null);
  const [checked,setChecked] = useState<PaymentContext | null>(null);
  const initialDate = useRef(date), initialDrafts = useRef<Record<number,PaymentDraft>>({});
  const rows = ids.map(id => query.data?.rows.find(row => row.notice_id === id)).filter((row): row is NoticeRow => Boolean(row)).map(row => { const project = projects.find(item => item.id === row.ownership_id); return project ? { ...row, project_display: projectLabel(project) } : row; });
  const excluded = rows.filter(row => row.is_excluded || row.is_revoked), targets = rows.filter(row => !row.is_excluded && !row.is_revoked);
  const missing = ids.filter(id => !rows.some(row => row.notice_id === id));
  const targetIds = targets.map(row => row.notice_id);
  const context = useQuery({ queryKey: ['notice-payment-context',targetIds,date], enabled: !blocked && phase === 'edit' && Boolean(query.data) && !missing.length && Boolean(targets.length) && Boolean(date), retry: false, refetchOnWindowFocus: false,
    queryFn: ({signal}) => readPaymentContext(targetIds,date,query.data!.methods,signal) });
  if (!blocked && context.isFetchedAfterMount && context.isSuccess && !context.isFetching) {
    for (const item of context.data.rows) defaults.current[item.notice_id] ??= item.default_pay_method;
  }
  function draft(row: NoticeRow): PaymentDraft { const fallback = { amount: paymentValue(row,overrides), pay_method: defaults.current[row.notice_id] || row.planned_pay_method || '现汇' }; initialDrafts.current[row.notice_id] = fallback; return {...fallback,...drafts.current[row.notice_id]}; }
  function update(row: NoticeRow, field: keyof PaymentDraft, value: string) { drafts.current[row.notice_id] = {...drafts.current[row.notice_id],[field]:value};setRevision(revision+1); }
  function reason(row: NoticeRow): string { return row.pay_block_reason || (cents(paymentValue(row,overrides)) <= 0n ? '本次应付不大于0，请调整付款金额' : ''); }
  const invalid = targets.some(row => reason(row)), busy = phase === 'checking' || phase === 'sending', editable = phase === 'edit';
  const dirty = phase !== 'saved' && (date !== initialDate.current || Boolean(remark) || Object.entries(drafts.current).some(([id,value]) => { const initial = initialDrafts.current[Number(id)]; return !initial || value.amount !== undefined && value.amount !== initial.amount || value.pay_method !== undefined && value.pay_method !== initial.pay_method; }));
  const closing = useDialogClose({ busy, dirty, close: () => { const id = removing.current; removing.current = null; if (id !== null) remove(id); close(); } });
  const paymentClosing = { ...closing, resume: () => { removing.current = null; closing.resume(); } };
  function removeRow(id: number) { if(ids.length===1) { removing.current = id; closing.requestClose(); } else remove(id); }
  async function reread() {
    setRefreshFailed(false);
    try { await refresh(); } catch { setRefreshFailed(true); }
  }
  async function submit() {
    if (blocked || lock.current || !editable || invalid || missing.length || !targets.length || query.isFetching || query.isError || context.isPending || context.isFetching || context.isError) return;
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
    lock.current=true;setPhase('checking');setError('');
    try {
      const controller = new AbortController();preflight.current=controller;
      const latest = await readPaymentContext(targetIds,date,query.data!.methods,controller.signal);
      if (!active.current) return;
      if (currentBlocked.current) { setPhase('edit');return; }
      setChecked(latest);
      confirmed.current = {ids:targetIds,drafts:next,pay_date:date,remark:remark.trim()};
      if (!latest.available || latest.rows.some(row => row.term_warning)) { setPhase('confirm'); return; }
      await sendPayment();
    } catch (failure) {
      if (!active.current) return;
      setError(`合同账期核对失败，输入已保留。${failure instanceof Error ? failure.message : '请重试。'}`);setPhase('edit');
    } finally { lock.current=false; }
  }
  async function sendPayment() {
    const payload = confirmed.current;
    if (!payload || !active.current || currentBlocked.current) return;
    setPhase('sending');
    requestId.current ||= crypto.randomUUID();
    let saved = false;
    try {
      const value = await requestJson('/api/m03/actions/batch-pay',{method:'POST',...body({...payload,request_id:requestId.current})});
      if (!active.current) return;
      confirmWrite(record(value) && value.ok === true, '付款结果待核实，请到付款流水核对，勿重复提交。');
      saved=true;setPhase('saved');paid(targets.map(row => row.notice_id));
      const text = receipt(value);setMessage(text);announce(text);
      if (!record(value) || !Array.isArray(value.flows) || !Array.isArray(value.created) || value.flows.length !== value.created.length || !value.flows.every(f => record(f) && Number.isSafeInteger(f.notice_id) && ['flow_no','amount','pay_date','pay_method','remark'].every(k => typeof f[k] === 'string'))) throw new ApiError('付款已登记，流水回执不完整，请到付款流水核对，勿重复付款。');
      setFlows(value.flows as FlowReceipt[]);
      const skipped = targets.filter(row => !(value.created as number[]).includes(row.notice_id));
      if (skipped.length) setMessage(`${text}；本次未登记：${skipped.map(row => row.bill_no).join('、')}，请重读核对状态。`);
      await reread();
    } catch (failure) {
      if (!active.current) return;
      if (!saved) {
        const rejected = !uncertainWrite(failure);
        setPhase(rejected ? 'edit' : 'uncertain');
        if (rejected) void query.refetch();
      }
      setError(`${saved ? '付款已登记，勿重复提交。' : !uncertainWrite(failure) ? '整批未登记，输入已保留。' : '提交结果尚未核实，请重读列表并到付款流水核对，勿重复付款。'}${failure instanceof Error ? failure.message : '请重读核对。'}`);
    } finally { lock.current=false; }
  }
  async function continuePayment() {
    if (blocked || lock.current || phase !== 'confirm') return;
    lock.current=true;
    try { await sendPayment(); } finally { lock.current=false; }
  }
  const shownContext = phase === 'edit' ? (context.isFetching || context.isError ? undefined : context.data) : checked;
  return <BusinessModal open={!blocked} className={`project-dialog notice-pay-dialog${phase === 'saved' ? ' notice-pay-result' : ''}`} titleId="notice-pay-title" requestClose={closing.requestClose}><DialogContents title={phase === 'saved' ? '付款结果' : '批量付款'} titleId="notice-pay-title" closing={paymentClosing}>
    {query.isPending && editable ? <p role="status">正在核对付款记录…</p> : query.isError && editable ? <p className="notice" role="alert">{query.error.message}<Button htmlType="submit" onClick={() => void query.refetch()}>重读</Button></p> : <>
      {message && <p role="status" className="notice-feedback">{message}</p>}
      {excluded.length > 0 && <p className="notice" role="alert">已排除 {excluded.length} 条：{excluded.map(row => `${row.bill_no}（${row.pay_block_reason}）`).join('、')}</p>}
      {missing.length > 0 && <p className="notice" role="alert">{missing.length} 条记录已不在列表，请关闭并重新勾选核对。</p>}
      {phase === 'saved' ? flows.length > 0 && <ReadGrid manualWidths table="notice-payment-receipt" className="notice-pay-table" label="付款流水回执" domLayout="autoHeight" rows={flows} rowId={flow=>flow.flow_no} columns={[
        {colId:'bill',headerName:'单据编码',...fullTextWidth(rows.map(row=>row.bill_no)),wrapText:false,valueGetter:p=>rows.find(row=>row.notice_id===p.data!.notice_id)?.bill_no??''},
        {field:'flow_no',headerName:'付款流水号'}, {field:'pay_date',headerName:'付款日期'}, {field:'pay_method',headerName:'方式'},
        {field:'amount',headerName:'实付金额',...numberColumnWidth(flows.map(flow=>money(flow.amount))),cellClass:'money',valueFormatter:p=>money(p.value)},
        {field:'remark',headerName:'备注',valueFormatter:p=>p.value||'—'},
      ]}/> : <PaymentGrid rows={targets} due={row=>paymentValue(row,overrides)} draft={draft} update={update} remove={removeRow} disabled={!editable||blocked} waiting={!context.data&&context.isPending} methods={query.data?.methods??[]} normalize={amount} warningIds={shownContext?.rows.filter(item=>item.term_warning).map(item=>item.notice_id)??[]} />}
      {phase !== 'saved' && <div className="notice-pay-fields"><label>付款日期<BusinessDate label="付款日期" value={date} disabled={!editable||blocked} onChange={setDate} /></label><label>本批付款备注<Input aria-label="本批付款备注" value={remark} disabled={!editable||blocked} onChange={e => setRemark(e.target.value)} /></label></div>}
      {editable && context.isFetching && <p role="status">正在核对合同账期…</p>}
      {editable && context.isError && <p className="notice" role="alert">合同账期核对失败，输入已保留。{context.error.message}<Button onClick={() => void context.refetch()}>重试账期核对</Button></p>}
      {phase !== 'saved' && shownContext?.available === false && <p className="payment-confirmation" role="alert">账期提醒暂未启用，请按合同人工核对；原有付款校验继续执行。</p>}
      {phase !== 'saved' && shownContext?.available && <PaymentTerms rows={shownContext.rows} project={id => rows.find(row => row.notice_id === id)?.project_display || '—'} amount={id => { const row = rows.find(row => row.notice_id === id); return row ? amount(draft(row).amount) : null; }} />}
      {phase === 'confirm' && <p className="payment-confirmation" role="alert">{checked?.available ? '该合同存在未满账期的发票，请核对本次付款。仍要继续付款吗？' : '本次未完成账期判断，请按合同人工核对后决定是否继续付款。'}</p>}

    </>}
    {error && <p className="notice" role="alert">{error}</p>}
    {refreshFailed && <p className="notice" role="alert">{phase === 'saved' ? '付款已登记，列表尚待重读核对。' : '列表重读失败，提交结果尚未核实，请到付款流水核对，勿重复付款。'}<Button htmlType="submit" onClick={() => void reread()}>重读核对</Button></p>}
    <div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>{phase === 'saved' ? '关闭' : '取消'}</Button>{phase === 'uncertain' && <Button htmlType="submit" onClick={() => void reread()}>重读列表核对</Button>}{editable && <Button htmlType="submit" className="primary" disabled={blocked||busy||query.isPending||query.isFetching||query.isError||context.isPending||context.isFetching||context.isError||!date||invalid||Boolean(missing.length)||!targets.length} onClick={() => void submit()}>确认付款</Button>}{phase === 'confirm' && <><Button onClick={() => { confirmed.current=null;setPhase('edit'); }}>返回修改</Button><Button className="primary" onClick={() => void continuePayment()}>继续付款</Button></>}{busy && <span role="status">{phase === 'checking' ? '正在核对合同账期…' : '正在提交…'}</span>}</div>
  </DialogContents></BusinessModal>;
}
