import Button from 'antd/es/button';
import { useRef, useState } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import { confirmWrite, record, requestJson, uncertainWrite } from './api';
import { BusinessModal } from './business-modal';
import { ReadGrid } from './business-grid';
import { DialogContents, useDialogClose } from './dialog-close';
import { useHistoryGuard } from './history';
import { JcFetchReceipt } from './jc-fetch-receipt';
import { jcCondition, jcRuleKinds, jcRulesPath } from './jc-rule-data';
import type { JcRule, JcRuleKind } from './jc-rule-data';
import { body } from './notices-api';
import { FirstReadRegion, ReadFailure, ReadPlaceholder, ReadStatusLane, readPhase } from './read-region';
import { DialogPresence } from './workspace-motion';

const blank = { kind: 'project' as JcRuleKind, name_full: '', contract_no: '', bill_name_keyword: '', reason: '' };
type Draft = typeof blank;
type Editor = { type: 'add'; draft: Draft } | { type: 'delete'; rule: JcRule };
const kinds = Object.keys(jcRuleKinds) as JcRuleKind[];

export function JcRules({ query, active, writable, selected, clearSelection, onPublished }: {
  query: UseQueryResult<JcRule[], Error>; active: boolean; writable: boolean;
  selected: number | null; clearSelection: () => void; onPublished: () => void;
}) {
  const [filter, setFilter] = useState<JcRuleKind | ''>('');
  const [editor, setEditor] = useState<Editor | null>(null);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const draft = editor?.type === 'add' ? editor.draft : null;
  const dirty = !!draft && (draft.kind !== blank.kind || !!(draft.name_full || draft.contract_no || draft.bill_name_keyword || draft.reason));
  const closing = useDialogClose({ busy, dirty, close: () => setEditor(null), active });
  useHistoryGuard('jc-ignore', () => lock.current ? '集采剔除规则正在保存，请稍候。' : '');
  const rows = query.data;
  const visible = (rows ?? []).filter(row => selected !== null || !filter || row.kind === filter);
  const readState = readPhase(query, rows?.length === 0);
  const canWrite = writable && rows !== undefined && !query.isError && !busy;
  const valid = !draft ? true : draft.kind === 'contract' ? !!draft.contract_no.trim()
    : !!draft.name_full.trim() && (draft.kind === 'project' || !!draft.bill_name_keyword.trim());

  function open(next: Editor) {
    if (!canWrite || lock.current) return;
    setError('');
    setEditor(next);
  }

  function update(patch: Partial<Draft>) {
    if (!draft || lock.current) return;
    setEditor({ type: 'add', draft: { ...draft, ...patch } });
  }

  async function save() {
    if (!editor || !canWrite || !valid || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    setFeedback('');
    try {
      const result = await requestJson(jcRulesPath + (editor.type === 'delete' ? `/${editor.rule.id}` : ''),
        editor.type === 'add' ? { method: 'POST', ...body(editor.draft) } : { method: 'DELETE' });
      confirmWrite(record(result) && result.ok === true, '保存回执不完整。');
      setEditor(null);
      setFeedback(record(result) && typeof result.message === 'string' ? result.message : '已保存');
      await query.refetch();
    } catch (failure) {
      setError(uncertainWrite(failure) ? '结果待确认，可以重试本次操作。'
        : failure instanceof Error ? failure.message : '规则保存失败。');
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return <div className="rules-block">
    <div className="rules-head">
      <h2>集采合同抓取剔除{rows && <span className="rules-count">（{rows.length} 条）</span>}</h2>
      <div className="rules-head-tools">
        <Button disabled={!active} onClick={() => setReceiptOpen(true)}>最近抓取结果</Button>
        <Button className="primary" disabled={!canWrite} onClick={() => open({ type: 'add', draft: blank })}>＋ 新增剔除规则</Button>
      </div>
    </div>
    <div className="rules-filter">
      <label>条件类型 <select value={selected !== null ? '' : filter} onChange={event => {
        clearSelection();
        setFilter(event.target.value as JcRuleKind | '');
      }}>
        <option value="">全部</option>
        {kinds.map(kind => <option key={kind} value={kind}>{jcRuleKinds[kind]}</option>)}
      </select></label>
    </div>
    <ReadStatusLane phase={readState} announce="正在读取集采剔除规则…" className="rules-read-status">
      {(readState === 'error' || readState === 'stale') && <ReadFailure read={query} retained="规则更新失败，保留上次结果。" />}
    </ReadStatusLane>
    <FirstReadRegion phase={rows !== undefined ? 'content' : readState === 'error' ? 'error' : 'pending'} onPublished={onPublished}
      placeholder={<div className="rules-table rules-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={4} quiet={readState === 'error'} /></div>}>
      {feedback && <p className="rules-receipt" role="status">{feedback}</p>}
      {visible.length === 0 ? <p className="state">{rows?.length ? '没有此类型的规则' : '暂无剔除规则'}</p>
        : <ReadGrid table="jc-ignore-rules" className="rules-table" label="集采剔除规则" domLayout="autoHeight" rows={visible} rowId={row => String(row.id)} columns={[
          {colId:'condition',headerName:'匹配条件',valueGetter:p=>jcCondition(p.data!),cellRenderer:({data:row}:{data:JcRule})=>
            <div id={`rule-procurement-${row.id}`} className={selected === row.id ? 'rules-located' : undefined}>
              <span className="rules-condition-kind">{jcRuleKinds[row.kind]}</span>{jcCondition(row)}
            </div>},
          {field:'reason',headerName:'业务理由',valueFormatter:p=>p.value || '—'},
          {colId:'added',headerName:'操作人 / 加入时间',valueGetter:p=>[p.data?.operator,p.data?.created_at].filter(Boolean).join(' · ') || '—'},
          {colId:'actions',headerName:'操作',cellRenderer:({data:row}:{data:JcRule})=>
            <Button danger disabled={!canWrite} onClick={() => open({ type: 'delete', rule: row })}>删除</Button>},
        ]}/>}
    </FirstReadRegion>
    <DialogPresence>{editor && <BusinessModal open={active} className="rules-dialog" titleId="jc-rule-title" requestClose={closing.requestClose}>
      <DialogContents title={draft ? '新增集采剔除规则' : '删除集采剔除规则'} titleId="jc-rule-title" closing={closing}>
        <form onSubmit={event => { event.preventDefault(); void save(); }}>
          {draft && <>
            <label>匹配条件<select value={draft.kind} disabled={busy} onChange={event => update({ kind: event.target.value as JcRuleKind })}>
              {kinds.map(kind => <option key={kind} value={kind}>{jcRuleKinds[kind]}</option>)}
            </select></label>
            {draft.kind !== 'contract' && <label>i8 项目全名<input required maxLength={512} value={draft.name_full} disabled={busy} onChange={event => update({ name_full: event.target.value })}/></label>}
            {draft.kind === 'contract' && <label>完整合同编号<input required maxLength={64} value={draft.contract_no} disabled={busy} onChange={event => update({ contract_no: event.target.value })}/></label>}
            {draft.kind === 'keyword' && <label>单据名关键词<input required maxLength={512} value={draft.bill_name_keyword} disabled={busy} onChange={event => update({ bill_name_keyword: event.target.value })}/></label>}
            <label>业务理由（选填）<input maxLength={255} value={draft.reason} disabled={busy} onChange={event => update({ reason: event.target.value })}/></label>
          </>}
          {editor.type === 'delete' && <p>{jcRuleKinds[editor.rule.kind]} · {jcCondition(editor.rule)}<br/>删除后，下次抓取按剩余规则判断。</p>}
          {error && <p className="notice" role="alert">{error}</p>}
          <div className="dialog-actions">
            <Button htmlType="button" disabled={busy} onClick={closing.requestClose}>取消</Button>
            <Button htmlType="submit" className={draft ? 'primary' : 'danger'} disabled={!canWrite || !valid}>
              {busy ? '正在保存…' : draft ? '新增' : '删除'}
            </Button>
          </div>
        </form>
      </DialogContents>
    </BusinessModal>}</DialogPresence>
    <DialogPresence>{receiptOpen && <JcFetchReceipt active={active} close={() => setReceiptOpen(false)} />}</DialogPresence>
  </div>;
}
