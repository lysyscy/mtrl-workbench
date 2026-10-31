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

export type InvoiceAction = 'correct' | 'allocate' | 'credit' | 'resolve' | 'void';
type Part = { key: string; project_id: number; account_id: number; amount: string };
export const invoiceAmountText = (value: string) => value.replace(/[¥￥,，\s]/g, '');
export function OilInvoiceDialog({ row, mode, source, all, archives, projects, disabled, busy, error, close, submit }: {
  row: OilInvoice; mode: InvoiceAction; source: OilInvoiceOriginal | null; all: OilInvoice[]; archives: OilArchives; projects: Project[];
  disabled: boolean; busy: boolean; error: string; close: () => void; submit: (fields: Record<string, unknown>) => Promise<void>;
}) {
  const facts = (mode === 'correct' || mode === 'credit') && source ? source.recognized : row;
  const [number, setNumber] = useState(facts.invoice_no || ''), [date, setDate] = useState(facts.invoice_date || '');
  const [amount, setAmount] = useState(facts.amount || ''), [card, setCard] = useState(facts.card_no || '');
  const [note, setNote] = useState(''), [parent, setParent] = useState(row.related_invoice_id || 0), [voidDate, setVoidDate] = useState('');
  const [dirty, setDirty] = useState(false), [localError, setLocalError] = useState('');
  const [parts, setParts] = useState<Part[]>(() => row.allocations.length ? row.allocations.map(a => ({ key: randomUUID(), project_id: a.project_id, account_id: a.account_id, amount: row.allocations.length === 1 && facts.amount ? facts.amount : a.amount })) : [{ key: randomUUID(), project_id: 0, account_id: 0, amount: facts.amount || '' }]);
  const closing = useDialogClose({ busy, dirty, close });
  const title = { correct: '更正票面信息', allocate: '整体分配发票', credit: row.kind === 'credit' ? '更正红冲信息' : '登记实际红冲', resolve: '确认保留原票', void: '登记实际作废' }[mode];
  const hasParts = mode === 'correct' || mode === 'allocate' || mode === 'credit';
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
  try { allocated = decimal(parts.reduce((n, p) => n + cents(invoiceAmountText(p.amount)), 0n)); } catch { /* An incomplete draft is not zero. */ }
  async function save(factsOnly = false) {
    if (disabled || busy) return;
    const allocations = factsOnly ? [] : parts.map(({ project_id, account_id, amount }) => ({ project_id, account_id, amount: invoiceAmountText(amount) }));
    if (hasParts && !factsOnly) {
      if (allocations.some(a => !a.project_id || !a.account_id || !a.amount)) { setLocalError('请配套选择项目和账户并填写每项金额。'); return; }
      try { if (cents(allocated) !== cents(invoiceAmountText(amount))) { setLocalError('分配合计必须等于价税合计。'); return; } } catch { setLocalError('请填写有效金额。'); return; }
    }
    if (mode === 'allocate') await submit({ allocations });
    else if (mode === 'resolve') await submit({ note });
    else if (mode === 'void') await submit({ date: voidDate, note });
    else await submit({ invoice_no: number.trim(), invoice_date: date, amount: invoiceAmountText(amount), card_no: card.trim() || null, note, allocations, review_original_id: source?.id ?? null, ...(mode === 'credit' ? { related_invoice_id: parent } : {}) });
  }
  return <BusinessModal open className={`oilcard-invoice-dialog${hasParts ? ' oilcard-invoice-dialog-wide' : ''}`} titleId="oilcard-invoice-dialog-title" requestClose={closing.requestClose}><DialogContents title={title} titleId="oilcard-invoice-dialog-title" closing={closing}>
    <p>发票 {row.invoice_no || `待核 #${row.id}`}{row.amount !== null ? `，${money(row.amount)} 元` : ''}</p>
    <form onSubmit={e => { e.preventDefault(); void save(); }}>
      {(mode === 'correct' || mode === 'credit') && <div className="oilcard-invoice-facts">
        <label>发票号码<Input aria-label="补正发票号码" value={number} disabled={disabled || busy} onChange={e => edit(() => setNumber(e.target.value))} /></label>
        <label>开票日期<DatePicker aria-label="补正开票日期" value={date ? dayjs(date) : null} disabled={disabled || busy} onChange={value => edit(() => setDate(value?.format('YYYY-MM-DD') || ''))} /></label>
        <label>价税合计<Input aria-label="补正价税合计" value={amount} disabled={disabled || busy} onChange={e => edit(() => { setAmount(e.target.value); setParts(ps => ps.length === 1 ? [{ ...ps[0]!, amount: e.target.value }] : ps); })} /></label>
        <label>完整卡号<Input aria-label="补正完整卡号" value={card} placeholder="无法确认可留空" disabled={disabled || busy} onChange={e => edit(() => setCard(e.target.value))} /></label>
      </div>}
      {mode === 'credit' && <label>关联原票<Select aria-label="红冲关联原票" value={parent || null} disabled={disabled || busy} showSearch={{ optionFilterProp: 'label' }} options={all.filter(r => r.id !== row.id && r.status === 'registered' && r.kind === 'normal').map(r => ({ value: r.id, label: `${r.invoice_no}  ${money(r.amount!)}元` }))} onChange={value => edit(() => {
        setParent(value); const selected = all.find(r => r.id === value);
        if (selected?.allocations.length === 1) { const a = selected.allocations[0]!; setParts([{ key: randomUUID(), project_id: a.project_id, account_id: a.account_id, amount }]); }
      })} /></label>}
      {hasParts && <fieldset className="oilcard-invoice-parts"><legend>金额分配</legend>{parts.map((part, index) => <div className="oilcard-invoice-part" key={part.key}>
        <label>项目 {index + 1}<Select aria-label={`分配项目 ${index + 1}`} value={part.project_id || null} disabled={disabled || busy} showSearch={{ optionFilterProp: 'label' }} options={projects.filter(p => p.project_type !== 'shell').map(p => ({ value: p.id, label: projectLabel(p) }))} onChange={value => changePart(part.key, 'project_id', String(value))} /></label>
        <label>用卡账户<Select aria-label={`分配账户 ${index + 1}`} value={part.account_id || null} disabled={disabled || busy} showSearch={{ optionFilterProp: 'label' }} options={archives.accounts.filter(a => a.project_id === part.project_id || a.id === part.account_id).map(a => ({ value: a.id, label: `${a.name}${a.status === 'archived' ? '（归档）' : ''}` }))} onChange={value => changePart(part.key, 'account_id', String(value))} /></label>
        <label>分配金额<Input aria-label={`分配金额 ${index + 1}`} value={part.amount} disabled={disabled || busy} onChange={e => changePart(part.key, 'amount', e.target.value)} /></label>
        <Button disabled={disabled || busy || parts.length === 1} onClick={() => edit(() => setParts(ps => ps.filter(p => p.key !== part.key)))}>移除</Button>
      </div>)}<div className="oilcard-toolbar"><Button disabled={disabled || busy} onClick={() => edit(() => setParts(ps => [...ps, { key: randomUUID(), project_id: 0, account_id: 0, amount: '' }]))}>增加分配</Button><span>分配合计 {allocated ? money(allocated) : '待填写'}</span></div></fieldset>}
      {mode === 'void' && <label>实际作废日期<DatePicker aria-label="实际作废日期" value={voidDate ? dayjs(voidDate) : null} disabled={disabled || busy} onChange={value => edit(() => setVoidDate(value?.format('YYYY-MM-DD') || ''))} /></label>}
      {mode !== 'allocate' && <label>{mode === 'resolve' ? '核对结论' : mode === 'void' ? '作废依据' : mode === 'credit' ? '红冲依据' : '更正说明'}<Input.TextArea aria-label="发票处理说明" value={note} disabled={disabled || busy} onChange={e => edit(() => setNote(e.target.value))} autoSize={{ minRows: 2, maxRows: 4 }} /></label>}
      {mode === 'void' && <p className="muted">本台账将停止计入这张票的开票金额，原分配和原件保留。录错请使用更正票面信息。</p>}
      {(localError || error) && <p className="notice" role="alert">{localError || error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button>{mode === 'correct' && row.status === 'pending' && <Button disabled={disabled || busy || !note.trim()} onClick={() => void save(true)}>仅保存票面，稍后分配</Button>}<Button type="primary" htmlType="submit" disabled={disabled || busy || mode !== 'allocate' && !note.trim()}>{mode === 'allocate' ? '保存整体分配' : mode === 'resolve' ? '确认保留原票' : mode === 'void' ? '登记作废' : mode === 'credit' ? '保存红冲关联与分配' : '保存补正与分配'}</Button></div>
    </form>
  </DialogContents></BusinessModal>;
}
