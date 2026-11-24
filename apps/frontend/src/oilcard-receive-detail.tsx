import Button from 'antd/es/button';
import Select from 'antd/es/select';
import { useEffect, useId, useRef, useState } from 'react';
import { cents, money, projectLabel } from './api';
import type { Project } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import type { OilAccount, OilArchives, OilCard } from './oilcard-api';
import type { OilInvoice } from './oilcard-invoice-api';

const stateLabel = (status: 'active' | 'archived') => status === 'active' ? '在用' : '已归档';
const projectName = (projects: Project[], account: OilAccount) => {
  const project = projects.find(row => row.id === account.project_id);
  return project ? projectLabel(project) : '项目待核对';
};
const cardNumber = (card: OilCard) => card.card_no || '卡号待补';

function cardGroups(archives: OilArchives, cards: OilCard[]) {
  return cards.map(card => ({ card, accounts: archives.accounts.filter(account => account.card_id === card.id) }));
}

function receiptRelations(archives: OilArchives, cardNo: string | null) {
  const card = cardNo ? archives.cards.find(row => row.card_no === cardNo) : undefined;
  const primary = card?.kind === 'primary' ? card : archives.cards.find(row => row.id === card?.parent_card_id);
  const cards = card?.kind === 'secondary' ? [card] : archives.cards.filter(row => primary && row.parent_card_id === primary.id);
  const candidates = card?.status === 'active' ? cardGroups(archives, cards)
    .filter(group => group.card.status === 'active')
    .flatMap(group => group.accounts.filter(account => account.status === 'active')) : [];
  return { primary, cards, candidates };
}

export function OilCardRelationsTable({ archives, projects, cards }: {
  archives: OilArchives; projects: Project[]; cards: OilCard[];
}) {
  if (!cards.length) return <p className="state">此主卡暂无副卡。</p>;
  return <div className="oilcard-relations-scroll"><table className="oilcard-relations-table" aria-label="副卡与账户对应关系">
    <thead><tr><th scope="col">副卡卡号</th><th scope="col">实体卡状态</th><th scope="col">用卡账户</th><th scope="col">账户状态</th></tr></thead>
    {cardGroups(archives, cards).map(({ card, accounts }) => <tbody key={card.id}>{accounts.length ? accounts.map((account, index) => <tr key={account.id}>
      {index === 0 && <><th scope="rowgroup" rowSpan={accounts.length}>{cardNumber(card)}</th><td rowSpan={accounts.length}>{stateLabel(card.status)}</td></>}
      <td>{account.name}<small>{projectName(projects, account)}</small></td><td>{stateLabel(account.status)}</td>
    </tr>) : <tr><th scope="row">{cardNumber(card)}</th><td>{stateLabel(card.status)}</td><td colSpan={2}>未关联账户</td></tr>}</tbody>)}
  </table></div>;
}

export function OilArchiveAccountDialog({ account, card, busy, error, close, confirm }: {
  account: OilAccount; card: OilCard; busy: boolean; error: string; close: () => void; confirm: (together: boolean) => void;
}) {
  const closing = useDialogClose({ busy, dirty: false, close });
  return <BusinessModal open className="oilcard-invoice-dialog" titleId="oilcard-archive-account" requestClose={closing.requestClose}>
    <DialogContents title="归档用卡账户" titleId="oilcard-archive-account" closing={closing}>
      <p>「{account.name}」是副卡 {cardNumber(card)} 上最后一个在用账户。可保留副卡在用，也可选择一并归档。</p>
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="dialog-actions">
        <Button autoFocus disabled={busy} onClick={closing.requestClose}>取消</Button>
        <Button disabled={busy} onClick={() => confirm(true)}>归档账户和副卡</Button>
        <Button type="primary" disabled={busy} onClick={() => confirm(false)}>仅归档账户</Button>
      </div>
    </DialogContents>
  </BusinessModal>;
}

export function canConfirmOilAttribution(invoice: OilInvoice) {
  return invoice.status === 'pending' && invoice.kind === 'normal' && !invoice.deleted &&
    Boolean(invoice.invoice_no && invoice.invoice_date && invoice.amount && cents(invoice.amount) > 0n);
}

export function OilReceiveDetails({ archives, projects, invoice, disabled, back, confirm, onInspect }: {
  archives: OilArchives; projects: Project[]; invoice: OilInvoice; disabled: boolean;
  back: () => void; confirm: (invoice: OilInvoice, account: OilAccount) => void; onInspect: () => void;
}) {
  const id = useId(), [accountId, setAccountId] = useState<number | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);
  const { primary, cards, candidates } = receiptRelations(archives, invoice.card_no);
  const choices = candidates.length ? candidates : archives.accounts;
  const account = choices.find(row => row.id === accountId);
  return <section className="oilcard-receive-detail" aria-label="发票归属详情">
    <Button size="small" disabled={disabled} onClick={back}>返回收票结果</Button>
    <h3 ref={heading} tabIndex={-1}>归属核对 <span>{invoice.invoice_no || '票号待核'}</span></h3>
    <p>票备注卡号 <strong>{invoice.card_no ?? '未识别'}</strong>{primary && primary.card_no !== invoice.card_no && <> · 所属主卡 {cardNumber(primary)}</>}{invoice.amount && <> · 价税合计 {money(invoice.amount)}</>}</p>
    {cards.length > 0 && <OilCardRelationsTable archives={archives} projects={projects} cards={cards} />}
    {canConfirmOilAttribution(invoice) ? <>
      <p>{candidates.length ? candidates.length + ' 个在用候选账户，请核对实际归属。' : '当前没有匹配的在用账户，可从档案选择实际归属。'}</p>
      <div className="oilcard-receive-actions">
        <label htmlFor={id}>归属账户<Select id={id} aria-label="归属账户" placeholder="请选择账户" value={accountId}
          showSearch={{ optionFilterProp: 'label' }} disabled={disabled} onChange={setAccountId}
          options={choices.map(row => ({ value: row.id, label: row.name + ' · ' + projectName(projects, row) + (row.status === 'archived' ? '（已归档）' : '') }))} /></label>
        <Button type="primary" disabled={disabled || !account} onClick={() => { if (account) confirm(invoice, account); }}>确认归属并入账</Button>
      </div>
    </> : <>
      {invoice.allocations.length > 0 && <p role="status">已入账：{invoice.allocations.map(part => archives.accounts.find(row => row.id === part.account_id)?.name || '账户 #' + part.account_id).join('、')}</p>}
      {invoice.reason && <p>{invoice.reason}</p>}
      <Button disabled={disabled} onClick={onInspect}>核对发票</Button>
    </>}
  </section>;
}

export type OilPdfUpload = { file: File; message: string; invoiceId: number | null; pending: boolean };

export function OilPdfReceiveDialog({ mode, archives, projects, invoices, uploads, preparing, busy, disabled, uncertain, verified, error,
  receive, resume, reread, acceptRead, confirm, inspect, close }: {
  mode: 'pdf' | 'pending'; archives: OilArchives; projects: Project[]; invoices: OilInvoice[]; uploads: OilPdfUpload[];
  preparing: boolean; busy: boolean; disabled: boolean; uncertain: boolean; verified: boolean; error: string;
  receive: (files: File[]) => void; resume: () => void; reread: () => void; acceptRead: () => void;
  confirm: (invoice: OilInvoice, account: OilAccount) => void; inspect: (invoice: OilInvoice) => void; close: () => void;
}) {
  const id = useId(), [selectedId, setSelectedId] = useState(0), [files, setFiles] = useState<File[]>([]);
  const closing = useDialogClose({ busy: preparing || busy || uncertain, dirty: false, close });
  const invoice = invoices.find(row => row.id === selectedId);
  const pending = invoices.filter(row => row.status === 'pending');
  const list = mode === 'pending' ? pending.map(row => ({ title: row.invoice_no || '发票 #' + row.id, message: row.reason, invoice: row })) :
    uploads.map(upload => {
      const row = invoices.find(item => item.id === upload.invoiceId);
      const message = upload.pending && row?.status === 'registered' ? '归属已确认，发票已入账。' : upload.message || '等待上传';
      return { title: upload.file.name, message, invoice: row };
    });
  const title = mode === 'pdf' ? '上传PDF收票' : '发票归属核对';
  const blocked = preparing || busy || disabled || uncertain;
  return <BusinessModal open layout="pane" className="oilcard-receive-dialog" titleId="oilcard-pdf-receive" requestClose={closing.requestClose}>
    <DialogContents title={title} titleId="oilcard-pdf-receive" closing={closing}>
      {error && <p role="alert" className="notice">{error}</p>}
      {uncertain && <p role="alert" className="notice">结果待核实，请重新读取，再确认本次结果。</p>}
      {invoice ? <OilReceiveDetails key={invoice.id} invoice={invoice} archives={archives} projects={projects} disabled={blocked}
        back={() => setSelectedId(0)} confirm={confirm} onInspect={() => inspect(invoice)} /> : <>
        {mode === 'pdf' && <>
          <label htmlFor={id}>发票PDF<input id={id} type="file" accept="application/pdf,.pdf" multiple disabled={blocked}
            onChange={event => setFiles(Array.from(event.currentTarget.files ?? []))} /></label>
          <Button type="primary" loading={preparing} disabled={blocked || !files.length} onClick={() => { receive(files); setFiles([]); }}>上传并入账</Button>
          {preparing && <p role="status">已处理 {uploads.filter(item => item.message).length} / {uploads.length} 份</p>}
        </>}
        {list.length > 0 ? <div className="oilcard-relations-scroll"><table className="oilcard-relations-table" aria-label="逐项收票结果">
          <thead><tr><th scope="col">发票</th><th scope="col">核对事项</th><th scope="col">操作</th></tr></thead>
          <tbody>{list.map((item, index) => <tr key={mode === 'pending' && item.invoice ? item.invoice.id : index}>
            <th scope="row">{item.title}</th><td className="oilcard-receipt-message">{item.message}</td>
            <td>{item.invoice && <Button size="small" disabled={blocked} onClick={() => setSelectedId(item.invoice!.id)}>
              {item.invoice.status === 'pending' ? '确认归属' : '查看回执'}</Button>}</td>
          </tr>)}</tbody>
        </table></div> : mode === 'pending' && <p className="state">当前没有待确认发票。</p>}
        {mode === 'pdf' && !preparing && uploads.some(item => !item.message) && <Button disabled={blocked} onClick={resume}>继续上传剩余PDF</Button>}
      </>}
      <div className="dialog-actions">
        {error && <Button disabled={busy || preparing} onClick={reread}>重新读取并核对</Button>}
        {uncertain && <Button disabled={busy || !verified} onClick={acceptRead}>已核对结果</Button>}
        <Button disabled={busy || preparing || uncertain} onClick={closing.requestClose}>关闭</Button>
      </div>
    </DialogContents>
  </BusinessModal>;
}
