import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import { useRef, useState } from 'react';
import { money, projectLabel } from './api';
import type { Project } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import type { OilAccount, OilArchives, OilCard, OilReplacementFields } from './oilcard-api';
import type { OilAttributionFields, OilEntry } from './oilcard-ledger-api';
import { randomUUID } from './random-id';

const cardLabel = (card?: OilCard) => card ? card.card_no || `卡号待补 #${card.id}` : '未关联卡片';
type DialogState = { archives: OilArchives; disabled: boolean; busy: boolean; error: string; close: () => void };

export function OilReplacementDialog({ account, archives, disabled, busy, error, close, submit }: DialogState & {
  account: OilAccount; submit: (fields: OilReplacementFields) => Promise<void>;
}) {
  const [mode, setMode] = useState<'new' | 'existing'>('new'), [card, setCard] = useState<number | undefined>();
  const [number, setNumber] = useState(''), [parent, setParent] = useState<number | undefined>(), [remark, setRemark] = useState('');
  const request = useRef(randomUUID()), locked = disabled || busy;
  const closing = useDialogClose({ busy, dirty: Boolean(mode === 'existing' || card || number || parent || remark), close });
  return <BusinessModal open className="oilcard-association-dialog" titleId="oilcard-replacement-title" requestClose={closing.requestClose}><DialogContents title="换卡" titleId="oilcard-replacement-title" closing={closing}>
    <p>{account.name}，当前卡片：{cardLabel(archives.cards.find(item => item.id === account.card_id))}</p>
    <form onSubmit={e => { e.preventDefault(); if (!locked && (mode === 'new' || card)) void submit({ request_id: request.current,
      card_id: mode === 'existing' ? card ?? null : null, new_card: mode === 'new' ? { card_no: number.trim() || null, parent_card_id: parent ?? null, remark } : null }); }}>
      <label>换入卡片<Select aria-label="换入卡片方式" value={mode} disabled={locked} onChange={setMode} options={[{ value: 'new', label: '建立新副卡' }, { value: 'existing', label: '选择已有副卡' }]} /></label>
      {mode === 'new' ? <>
        <label>新卡完整卡号<Input aria-label="新卡完整卡号" value={number} disabled={locked} placeholder="未知可留空" maxLength={128} onChange={e => setNumber(e.target.value)} /></label>
        <label>所属主卡<Select aria-label="新卡所属主卡" value={parent} allowClear disabled={locked} placeholder="无" showSearch={{ optionFilterProp: 'label' }} onChange={setParent} options={archives.cards.filter(item => item.kind === 'primary').map(item => ({ value: item.id, label: cardLabel(item) }))} /></label>
        <label>新卡备注<Input aria-label="新卡备注" value={remark} disabled={locked} onChange={e => setRemark(e.target.value)} /></label>
      </> : <label>已有副卡<Select aria-label="换入已有副卡" value={card} disabled={locked} placeholder="请选择另一张副卡" showSearch={{ optionFilterProp: 'label' }} onChange={setCard} options={archives.cards.filter(item => item.kind === 'secondary' && item.id !== account.card_id).map(item => ({ value: item.id, label: cardLabel(item) }))} /></label>}
      <p className="muted">旧卡及原账务保留，仅此账户改用新卡。卡号录错请在实体油卡表更正原卡号。</p>
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" htmlType="submit" disabled={locked || mode === 'existing' && !card}>保存换卡</Button></div>
    </form></DialogContents></BusinessModal>;
}

export function OilAttributionDialog({ row, archives, projects, disabled, busy, error, close, submit }: DialogState & {
  row: OilEntry; projects: Project[]; submit: (fields: OilAttributionFields) => Promise<void>;
}) {
  const [project, setProject] = useState(row.project_id), [account, setAccount] = useState(row.account_id), [card, setCard] = useState(row.card_id);
  const locked = disabled || busy, dirty = project !== row.project_id || account !== row.account_id || card !== row.card_id;
  const closing = useDialogClose({ busy, dirty, close });
  const candidates = archives.accounts.filter(item => item.project_id === project || item.id === row.account_id && project === row.project_id);
  function chooseProject(id: number) {
    const options = archives.accounts.filter(item => item.project_id === id || item.id === row.account_id && id === row.project_id);
    setProject(id); setAccount(options.length === 1 ? options[0]!.id : options.some(item => item.id === account) ? account : 0);
  }
  return <BusinessModal open className="oilcard-association-dialog" titleId="oilcard-attribution-title" requestClose={closing.requestClose}><DialogContents title="更正历史关联" titleId="oilcard-attribution-title" closing={closing}>
    <p>充值记录 #{row.id}，{row.date_text || '日期未知'}，{money(row.amount)} 元</p>
    <p className="muted">原卡片：{cardLabel(archives.cards.find(item => item.id === row.card_id))}。此次选择只更正本笔账务，账户当前用卡关系保持。</p>
    <form onSubmit={e => { e.preventDefault(); if (!locked && account && dirty) void submit({ project_id: project, account_id: account, card_id: card }); }}>
      <label>项目<Select aria-label="历史关联项目" value={project} disabled={locked} showSearch={{ optionFilterProp: 'label' }} onChange={chooseProject} options={projects.filter(item => item.project_type !== 'shell').map(item => ({ value: item.id, label: `${projectLabel(item)}${item.status === 'archived' ? '（项目归档）' : ''}` }))} /></label>
      <label>用卡账户<Select aria-label="历史关联用卡账户" value={account || undefined} disabled={locked} placeholder="请选择账户" showSearch={{ optionFilterProp: 'label' }} onChange={value => setAccount(value ?? 0)} options={candidates.map(item => ({ value: item.id, label: `${item.name}${item.status === 'archived' ? '（归档）' : ''}${item.project_id !== project ? '（历史关联）' : ''}` }))} /></label>
      <label>本笔实体卡<Select aria-label="历史关联实体卡" value={card ?? 0} disabled={locked} showSearch={{ optionFilterProp: 'label' }} onChange={value => setCard(value || null)} options={[{ value: 0, label: '未关联卡片' }, ...archives.cards.filter(item => item.kind === 'secondary').map(item => ({ value: item.id, label: cardLabel(item) }))]} /></label>
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" htmlType="submit" disabled={locked || !account || !dirty}>保存更正</Button></div>
    </form></DialogContents></BusinessModal>;
}
