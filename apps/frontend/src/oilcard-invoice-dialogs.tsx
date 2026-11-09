import Button from 'antd/es/button';
import DatePicker from 'antd/es/date-picker';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import dayjs from 'dayjs';
import { useState } from 'react';
import { cents, decimal, money, projectLabel } from './api';
import type { Project } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { randomUUID } from './random-id';
import { OilDateText } from './oilcard-date';
import type { OilArchives } from './oilcard-api';
import type { OilInvoice, OilInvoiceOriginal, OilManualInvoiceFields } from './oilcard-invoice-api';

export type InvoiceAction = 'edit' | 'resolve' | 'delete';
type Part = { key: string; project_id: number; account_id: number; amount: string };
export const invoiceAmountText = (value: string) => value.replace(/[¥￥,，\s]/g, '');
type DialogAction = {
  row: OilInvoice; mode: InvoiceAction; source: OilInvoiceOriginal | null;
  submit: (fields: Record<string, unknown>) => Promise<void>;
} | {
  row: OilInvoice | undefined; mode: 'manual'; source?: never;
  submit: (fields: OilManualInvoiceFields) => Promise<void>;
};
export function OilInvoiceDialog(props: DialogAction & {
  archives: OilArchives; projects: Project[]; disabled: boolean; busy: boolean; error: string; close: () => void;
}) {
  const { row, mode, source, archives, projects, disabled, busy, error, close } = props;
  const manual = mode === 'manual';
  const facts = mode === 'edit' && source ? source.recognized : row;
  const [number, setNumber] = useState(facts?.invoice_no || ''), [date, setDate] = useState(manual ? row?.manual_date_text ?? '' : facts?.invoice_date || '');
  const [amount, setAmount] = useState(facts?.amount || ''), [card, setCard] = useState(facts?.card_no || '');
  const [cutoff, setCutoff] = useState(row?.manual_cutoff_ym ?? ''), [remark, setRemark] = useState(row?.remark ?? '');
  const [note, setNote] = useState('');
  const [dirty, setDirty] = useState(false), [localError, setLocalError] = useState('');
  const [parts, setParts] = useState<Part[]>(() => row?.allocations.length ? row.allocations.map(a => ({ key: randomUUID(), project_id: a.project_id, account_id: a.account_id, amount: row.allocations.length === 1 && facts?.amount ? facts.amount : a.amount })) : [{ key: randomUUID(), project_id: 0, account_id: 0, amount: facts?.amount || '' }]);
  const closing = useDialogClose({ busy, dirty, close });
  const title = { edit: '修改发票', resolve: '确认保留原票', delete: '删除发票', manual: row ? '修改手工登记' : '手动增行' }[mode];
  const hasParts = mode === 'edit' || manual;
  const hasDate = /^\d{4}-\d{2}-\d{2}$/.test(date.trim());
  const edit = (callback: () => void) => { setDirty(true); setLocalError(''); callback(); };
  function changePart(key: string, field: 'project_id' | 'account_id' | 'amount', value: string) {
    edit(() => setParts(rows => rows.map(p => {
      if (p.key !== key) return p;
      if (field === 'project_id') {
        const candidates = archives.accounts.filter(a => a.project_id === Number(value));
        return { ...p, project_id: Number(value), account_id: candidates.length === 1 ? candidates[0]!.id : 0 };
      }
      return { ...p, [field]: field === 'account_id' ? Number(value) : value };
    })));
  }
  let allocated = '', invoiceTotal = '', remaining: bigint | null = null;
  try { invoiceTotal = decimal(cents(invoiceAmountText(amount))); } catch { /* An incomplete draft is not zero. */ }
  try {
    allocated = parts.length === 1 ? invoiceTotal : decimal(parts.reduce((n, p) => n + cents(invoiceAmountText(p.amount)), 0n));
    if (invoiceTotal && allocated) {
      const target = cents(invoiceTotal);
      remaining = (target < 0n ? -1n : 1n) * (target - cents(allocated));
    }
  } catch { /* Keep the invoice target visible while allocations are incomplete. */ }
  async function save(factsOnly = false) {
    if (disabled || busy) return;
    const allocations = factsOnly ? [] : parts.map(part => ({ project_id: part.project_id, account_id: part.account_id, amount: invoiceAmountText(parts.length === 1 ? amount : part.amount) }));
    if (hasParts && !factsOnly) {
      if (allocations.some(a => !a.project_id || !a.account_id || !a.amount)) { setLocalError('请配套选择项目和账户并填写每项金额。'); return; }
      try { if (cents(allocated) !== cents(invoiceAmountText(amount))) { setLocalError('分配合计必须等于价税合计。'); return; } } catch { setLocalError('请填写有效金额。'); return; }
    }
    if (props.mode === 'manual') await props.submit({ invoice_no: number.trim(), date_text: date, cutoff_ym: hasDate ? null : cutoff.trim() || null, amount: invoiceAmountText(amount), remark, allocations });
    else if (props.mode === 'resolve') await props.submit({ note });
    else if (props.mode === 'delete') await props.submit({});
    else await props.submit({ invoice_no: number.trim(), invoice_date: date, amount: invoiceAmountText(amount), card_no: card.trim() || null, note, allocations, review_original_id: source?.id ?? null, ...(props.row.kind === 'credit' ? { related_invoice_id: props.row.related_invoice_id } : {}) });
  }
  return <BusinessModal open className={`oilcard-invoice-dialog${hasParts ? ' oilcard-invoice-dialog-wide' : ''}`} titleId="oilcard-invoice-dialog-title" requestClose={closing.requestClose}><DialogContents title={title} titleId="oilcard-invoice-dialog-title" closing={closing}>
    {manual ? <p>保存后计入所选账户的已开金额。票号和日期按已有资料填写。</p> : <p>{row?.manual_request_id && !row.invoice_no ? '手工登记' : '发票'} {row?.invoice_no || `#${row?.id}`}{row?.amount != null ? `，${money(row.amount)} 元` : ''}</p>}
    <form onSubmit={e => { e.preventDefault(); void save(); }}>
      {manual && <div className="oilcard-invoice-facts">
        <label>价税合计<Input aria-label="手工登记价税合计" inputMode="decimal" value={amount} disabled={disabled || busy} onChange={e => edit(() => setAmount(e.target.value))} /></label>
        <label>开票日期或原标记<OilDateText label="手工登记日期或原标记" value={date} disabled={disabled || busy} change={value => edit(() => setDate(value))} save={() => {}} /></label>
        {!hasDate && <label>历史截至月<Input aria-label="历史截至月" placeholder="YYYY-MM，可留空" maxLength={7} value={cutoff} disabled={disabled || busy} onChange={e => edit(() => setCutoff(e.target.value))} /></label>}
        <label>发票号码<Input aria-label="手工登记发票号码" placeholder="已有真实票号时填写" value={number} maxLength={20} disabled={disabled || busy} onChange={e => edit(() => setNumber(e.target.value))} /></label>
      </div>}
      {mode === 'edit' && <div className="oilcard-invoice-facts">
        <label>发票号码<Input aria-label="补正发票号码" value={number} disabled={disabled || busy} onChange={e => edit(() => setNumber(e.target.value))} /></label>
        <label>开票日期<DatePicker aria-label="补正开票日期" value={date ? dayjs(date) : null} disabled={disabled || busy} onChange={value => edit(() => setDate(value?.format('YYYY-MM-DD') || ''))} /></label>
        <label>价税合计<Input aria-label="补正价税合计" value={amount} disabled={disabled || busy} onChange={e => edit(() => { setAmount(e.target.value); setParts(ps => ps.length === 1 ? [{ ...ps[0]!, amount: e.target.value }] : ps); })} /></label>
        <label>完整卡号<Input aria-label="补正完整卡号" value={card} placeholder="无法确认可留空" disabled={disabled || busy} onChange={e => edit(() => setCard(e.target.value))} /></label>
      </div>}
      {hasParts && <fieldset className="oilcard-invoice-parts"><legend>项目与账户</legend>{parts.map((part, index) => <div className={`oilcard-invoice-part${parts.length === 1 ? ' oilcard-invoice-part-single' : ''}`} key={part.key}>
        <label>项目 {index + 1}<Select aria-label={`分配项目 ${index + 1}`} value={part.project_id || null} disabled={disabled || busy} showSearch={{ optionFilterProp: 'label' }} options={projects.filter(p => p.project_type !== 'shell').map(p => ({ value: p.id, label: projectLabel(p) }))} onChange={value => changePart(part.key, 'project_id', String(value))} /></label>
        <label>用卡账户<Select aria-label={`分配账户 ${index + 1}`} value={part.account_id || null} disabled={disabled || busy} showSearch={{ optionFilterProp: 'label' }} options={archives.accounts.filter(a => a.project_id === part.project_id || a.id === part.account_id).map(a => ({ value: a.id, label: `${a.name}${a.status === 'archived' ? '（归档）' : ''}` }))} onChange={value => changePart(part.key, 'account_id', String(value))} /></label>
        {parts.length > 1 && <><label>分配金额<Input aria-label={`分配金额 ${index + 1}`} value={part.amount} disabled={disabled || busy} onChange={e => changePart(part.key, 'amount', e.target.value)} /></label><Button disabled={disabled || busy} onClick={() => edit(() => setParts(ps => ps.filter(p => p.key !== part.key)))}>移除</Button></>}
      </div>)}<div className="oilcard-toolbar"><Button disabled={disabled || busy} onClick={() => edit(() => setParts(ps => [...ps.map(p => ps.length === 1 ? { ...p, amount } : p), { key: randomUUID(), project_id: 0, account_id: 0, amount: '' }]))}>分给更多账户</Button>{parts.length > 1 && <div className="oilcard-allocation-summary" role="status">
        <span>已分配 {allocated ? money(allocated) : '待填写'}</span><span>票面 {invoiceTotal ? money(invoiceTotal) : '待填写'}</span>
        {remaining !== null && <span className={remaining === 0n ? undefined : 'oilcard-allocation-gap'}>{remaining === 0n ? '分配一致' : `${remaining > 0n ? '待分配' : '超分'} ${money(decimal(remaining < 0n ? -remaining : remaining))}`}</span>}
      </div>}</div></fieldset>}
      {manual && <label>备注<Input aria-label="手工登记备注" value={remark} disabled={disabled || busy} onChange={e => edit(() => setRemark(e.target.value))} /></label>}
      {!manual && mode !== 'delete' && <label>{mode === 'resolve' ? '核对结论' : '修改说明'}（必填）<Input.TextArea aria-label="发票处理说明" aria-required="true" placeholder={mode === 'edit' ? '请填写本次修改原因' : undefined} value={note} disabled={disabled || busy} onChange={e => edit(() => setNote(e.target.value))} autoSize={{ minRows: 2, maxRows: 4 }} /></label>}
      {mode === 'delete' && <p>从台账删除此行并扣除对应开票金额。{row?.originals.length ? '原件保留。' : ''}可用顶部“撤销”恢复。</p>}
      {(localError || error) && <p className="notice" role="alert">{localError || error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button>{mode === 'edit' && row?.status === 'pending' && <Button disabled={disabled || busy || !note.trim()} onClick={() => void save(true)}>暂不分配</Button>}<Button type="primary" danger={mode === 'delete'} htmlType="submit" disabled={disabled || busy || !manual && mode !== 'delete' && !note.trim()}>{mode === 'delete' ? '删除' : mode === 'resolve' ? '确认保留原票' : manual && !row ? '登记已开金额' : '保存修改'}</Button></div>
    </form>
  </DialogContents></BusinessModal>;
}
