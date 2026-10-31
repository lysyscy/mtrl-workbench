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
import type { OilArchives } from './oilcard-api';
import type { OilInvoice, OilInvoiceOriginal } from './oilcard-invoice-api';

export type InvoiceAction = 'edit' | 'resolve' | 'delete';
type Part = { key: string; project_id: number; account_id: number; amount: string };
export const invoiceAmountText = (value: string) => value.replace(/[¥￥,，\s]/g, '');
export function OilInvoiceDialog({ row, mode, source, archives, projects, disabled, busy, error, close, submit }: {
  row: OilInvoice; mode: InvoiceAction; source: OilInvoiceOriginal | null; archives: OilArchives; projects: Project[];
  disabled: boolean; busy: boolean; error: string; close: () => void; submit: (fields: Record<string, unknown>) => Promise<void>;
}) {
  const facts = mode === 'edit' && source ? source.recognized : row;
  const [number, setNumber] = useState(facts.invoice_no || ''), [date, setDate] = useState(facts.invoice_date || '');
  const [amount, setAmount] = useState(facts.amount || ''), [card, setCard] = useState(facts.card_no || '');
  const [note, setNote] = useState('');
  const [dirty, setDirty] = useState(false), [localError, setLocalError] = useState('');
  const [parts, setParts] = useState<Part[]>(() => row.allocations.length ? row.allocations.map(a => ({ key: randomUUID(), project_id: a.project_id, account_id: a.account_id, amount: row.allocations.length === 1 && facts.amount ? facts.amount : a.amount })) : [{ key: randomUUID(), project_id: 0, account_id: 0, amount: facts.amount || '' }]);
  const closing = useDialogClose({ busy, dirty, close });
  const title = { edit: '修改发票', resolve: '确认保留原票', delete: '删除发票' }[mode];
  const hasParts = mode === 'edit';
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
  let allocated = '';
  try { allocated = parts.length === 1 ? decimal(cents(invoiceAmountText(amount))) : decimal(parts.reduce((n, p) => n + cents(invoiceAmountText(p.amount)), 0n)); } catch { /* An incomplete draft is not zero. */ }
  async function save(factsOnly = false) {
    if (disabled || busy) return;
    const allocations = factsOnly ? [] : parts.map(part => ({ project_id: part.project_id, account_id: part.account_id, amount: invoiceAmountText(parts.length === 1 ? amount : part.amount) }));
    if (hasParts && !factsOnly) {
      if (allocations.some(a => !a.project_id || !a.account_id || !a.amount)) { setLocalError('请配套选择项目和账户并填写每项金额。'); return; }
      try { if (cents(allocated) !== cents(invoiceAmountText(amount))) { setLocalError('分配合计必须等于价税合计。'); return; } } catch { setLocalError('请填写有效金额。'); return; }
    }
    if (mode === 'resolve') await submit({ note });
    else if (mode === 'delete') await submit({});
    else await submit({ invoice_no: number.trim(), invoice_date: date, amount: invoiceAmountText(amount), card_no: card.trim() || null, note, allocations, review_original_id: source?.id ?? null, ...(row.kind === 'credit' ? { related_invoice_id: row.related_invoice_id } : {}) });
  }
  return <BusinessModal open className={`oilcard-invoice-dialog${hasParts ? ' oilcard-invoice-dialog-wide' : ''}`} titleId="oilcard-invoice-dialog-title" requestClose={closing.requestClose}><DialogContents title={title} titleId="oilcard-invoice-dialog-title" closing={closing}>
    <p>发票 {row.invoice_no || `待核 #${row.id}`}{row.amount !== null ? `，${money(row.amount)} 元` : ''}</p>
    <form onSubmit={e => { e.preventDefault(); void save(); }}>
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
      </div>)}<div className="oilcard-toolbar"><Button disabled={disabled || busy} onClick={() => edit(() => setParts(ps => [...ps.map(p => ps.length === 1 ? { ...p, amount } : p), { key: randomUUID(), project_id: 0, account_id: 0, amount: '' }]))}>分给更多账户</Button>{parts.length > 1 && <span>分配合计 {allocated ? money(allocated) : '待填写'}</span>}</div></fieldset>}
      {mode !== 'delete' && <label>{mode === 'resolve' ? '核对结论' : '修改说明'}<Input.TextArea aria-label="发票处理说明" value={note} disabled={disabled || busy} onChange={e => edit(() => setNote(e.target.value))} autoSize={{ minRows: 2, maxRows: 4 }} /></label>}
      {mode === 'delete' && <p>从台账删除这张发票并扣除对应开票金额，原件保留。可用顶部“撤销”恢复。</p>}
      {(localError || error) && <p className="notice" role="alert">{localError || error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button>{mode === 'edit' && row.status === 'pending' && <Button disabled={disabled || busy || !note.trim()} onClick={() => void save(true)}>暂不分配</Button>}<Button type="primary" danger={mode === 'delete'} htmlType="submit" disabled={disabled || busy || mode !== 'delete' && !note.trim()}>{mode === 'delete' ? '删除' : mode === 'resolve' ? '确认保留原票' : '保存修改'}</Button></div>
    </form>
  </DialogContents></BusinessModal>;
}
