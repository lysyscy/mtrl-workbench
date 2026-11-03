import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import { useRef, useState } from 'react';
import { projectLabel } from './api';
import type { Project } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { OilDateText } from './oilcard-date';
import type { OilArchives } from './oilcard-api';
import type { OilTransferFields } from './oilcard-ledger-api';
import { randomUUID } from './random-id';

type Endpoint = { project: number; account: number; remark: string };
export function OilTransferDialog({ archives, projects, disabled, busy, error, close, submit }: {
  archives: OilArchives; projects: Project[]; disabled: boolean; busy: boolean; error: string; close: () => void;
  submit: (fields: OilTransferFields) => Promise<void>;
}) {
  const [outgoing, setOutgoing] = useState<Endpoint>({ project: 0, account: 0, remark: '' });
  const [incoming, setIncoming] = useState<Endpoint>({ project: 0, account: 0, remark: '' });
  const [amount, setAmount] = useState(''), [date, setDate] = useState('');
  const requestId = useRef(randomUUID());
  const closing = useDialogClose({ busy, dirty: Boolean(amount || date || outgoing.project || outgoing.account || outgoing.remark || incoming.project || incoming.account || incoming.remark), close });
  const locked = disabled || busy;
  function changeEndpoint(side: 'out' | 'in', field: keyof Endpoint, value: string) {
    const update = side === 'out' ? setOutgoing : setIncoming;
    update(old => {
      const next = { ...old, [field]: field === 'remark' ? value : Number(value) };
      if (field === 'project') {
        const candidates = archives.accounts.filter(account => account.project_id === next.project);
        next.account = candidates.length === 1 ? candidates[0]!.id : candidates.some(account => account.id === old.account) ? old.account : 0;
      }
      return next;
    });
  }
  const valid = outgoing.project && outgoing.account && incoming.project && incoming.account && outgoing.account !== incoming.account && amount.trim();
  return <BusinessModal open className="oilcard-transfer-dialog" titleId="oilcard-transfer-title" requestClose={closing.requestClose}><DialogContents title="转账" titleId="oilcard-transfer-title" closing={closing}>
    <form onSubmit={e => { e.preventDefault(); if (!locked && valid) void submit({ request_id: requestId.current,
      out_project_id: outgoing.project, out_account_id: outgoing.account, in_project_id: incoming.project, in_account_id: incoming.account,
      amount, date_text: date, out_remark: outgoing.remark, in_remark: incoming.remark }); }}>
      <div className="oilcard-transfer-sides">{([{ side: 'out', label: '转出', data: outgoing }, { side: 'in', label: '转入', data: incoming }] as const).map(item => <fieldset key={item.side}><legend>{item.label}</legend>
        <label>项目<Select aria-label={`${item.label}项目`} value={item.data.project || undefined} disabled={locked} placeholder="请选择项目" showSearch={{ optionFilterProp: 'label' }} onChange={value => changeEndpoint(item.side, 'project', String(value))} options={projects.filter(project => project.project_type !== 'shell').map(project => ({ value: project.id, label: `${projectLabel(project)}${project.status === 'archived' ? '（项目归档）' : ''}` }))} /></label>
        <label>用卡账户<Select aria-label={`${item.label}用卡账户`} value={item.data.account || undefined} disabled={locked || !item.data.project} placeholder="请选择账户" showSearch={{ optionFilterProp: 'label' }} onChange={value => changeEndpoint(item.side, 'account', String(value))} options={archives.accounts.filter(account => account.project_id === item.data.project).map(account => ({ value: account.id, label: `${account.name}${account.status === 'archived' ? '（归档）' : ''}` }))} /></label>
        <label>备注<Input aria-label={`${item.label}备注`} value={item.data.remark} disabled={locked} onChange={e => changeEndpoint(item.side, 'remark', e.target.value)} /></label>
      </fieldset>)}</div>
      <div className="oilcard-transfer-common"><label>转账金额<Input aria-label="转账金额" value={amount} disabled={locked} placeholder="填写正数" onChange={e => setAmount(e.target.value)} /></label>
        <label>日期<OilDateText label="转账日期" value={date} disabled={locked} change={setDate} save={() => {}} /></label></div>
      {outgoing.account > 0 && outgoing.account === incoming.account && <p className="notice" role="alert">转入和转出请选择不同用卡账户。</p>}
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" htmlType="submit" disabled={locked || !valid}>登记转账</Button></div>
    </form></DialogContents></BusinessModal>;
}
