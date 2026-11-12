import Button from 'antd/es/button';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { ApiError, record, requestJson } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { isJcRule, jcCondition, jcRuleKinds, jcRulesPath } from './jc-rule-data';
import type { JcRule } from './jc-rule-data';
import { ReadFailure } from './read-region';
import { I8ReceiptSummary, receiptCount as count } from './i8-receipt-summary';

export interface ReceiptRow {
  id: string;
  contract: string;
  project: string;
  document: string;
  kind: string;
  reason: string;
  matches: JcRule[];
}

const ownershipReason: Record<string, string> = {
  needs_keyword: '缺少小微识别词',
  needs_choice: '命中多个项目',
  not_archived: '项目未建档',
};

export function readReceiptRows(value: unknown, ignored: boolean): ReceiptRow[] {
  if (!Array.isArray(value)) return [];
  return value.filter(record).map((row, index) => {
    const matches = Array.isArray(row.matches) ? row.matches.filter(isJcRule) : [];
    return {
      id: `${ignored ? 'ignored' : 'unsettled'}-${index}`,
      contract: typeof row.contract_no === 'string' ? row.contract_no : '',
      project: typeof row.project_name === 'string' ? row.project_name : '',
      document: typeof row.doc_name === 'string' ? row.doc_name : '',
      kind: typeof row.kind === 'string' ? row.kind : '',
      reason: ignored ? matches.length ? '规则剔除' : '规则剔除 · 旧记录未保存命中条件'
        : typeof row.kind === 'string' ? ownershipReason[row.kind] ?? '归属待指定' : '归属待指定',
      matches,
    };
  });
}

export function readReceipt(value: unknown) {
  if (record(value) && value.receipt === null) return null;
  if (!record(value) || !record(value.receipt)) throw new ApiError('抓取结果读取不完整，请重试。');
  const item = value.receipt;
  if (typeof item.started_at !== 'string' || typeof item.status !== 'string' || typeof item.matched !== 'number') {
    throw new ApiError('抓取结果读取不完整，请重试。');
  }
  const ignored = readReceiptRows(item.ignored, true);
  const unsettled = readReceiptRows(item.unsettled, false);
  const summary = record(item.summary) ? item.summary : {};
  const groups = Array.isArray(item.ignored_projects) ? item.ignored_projects.flatMap(group =>
    record(group) && typeof group.name === 'string' && count(group.count) !== null
      ? [{ name: group.name, count: Number(group.count) }] : []) : [];
  return {
    id: count(item.id),
    startedAt: item.started_at.replace('T', ' '), status: item.status, matched: item.matched,
    duration: typeof item.duration_seconds === 'number' && item.duration_seconds >= 0 ? item.duration_seconds : null,
    scope: typeof item.scope === 'string' ? item.scope : '',
    sourceCount: count(summary.source_count), identifiedCount: count(summary.identified_count),
    inserted: count(summary.inserted), changed: count(summary.changed), unchanged: count(summary.unchanged),
    materialBlank: count(summary.material_blank),
    syncWarning: typeof item.sync_warning === 'string' ? item.sync_warning.replaceAll('**', '') : '',
    ignoredCount: count(item.ignored_count), unsettledCount: count(item.unsettled_count),
    ignored, unsettled, groups,
  };
}

type Receipt = NonNullable<ReturnType<typeof readReceipt>>;

function ContractEvidence({ row }: { row: ReceiptRow }) {
  return <>
    <div className="i8-receipt-row-heading"><strong>{row.contract || '合同编号未记录'}</strong><span>{row.reason}</span></div>
    <p>{row.project || '项目未记录'}</p>
    <p>{row.document || '单据名未记录'}</p>
    {row.matches.length > 0 && <ul className="jc-receipt-matches">{row.matches.map(rule => <li key={rule.id}>
      {jcRuleKinds[rule.kind]}：{jcCondition(rule)}{rule.reason && `（${rule.reason}）`}
    </li>)}</ul>}
  </>;
}

export function JcReceiptContents({ data, pending = data.unsettled, actions }: {
  data: Receipt; pending?: ReceiptRow[]; actions?: (row: ReceiptRow) => ReactNode;
}) {
  const [keyword, setKeyword] = useState('');
  const needle = keyword.trim().toLowerCase();
  const byProject = new Map<string, ReceiptRow[]>();
  for (const row of data.ignored) {
    const project = row.project.trim() || '(无项目)';
    const rows = byProject.get(project) ?? [];
    rows.push(row);
    byProject.set(project, rows);
  }
  const projects = data.groups.length ? data.groups : [...byProject].map(([name, rows]) => ({ name, count: rows.length }));
  const groups = projects.map(group => ({
    ...group, rows: (byProject.get(group.name) ?? []).filter(row => row.contract.toLowerCase().includes(needle)),
  })).filter(group => !needle || group.rows.length > 0);
  const missingNumber = data.sourceCount !== null && data.identifiedCount !== null && data.sourceCount > data.identifiedCount
    ? data.sourceCount - data.identifiedCount : null;
  return <>
    <I8ReceiptSummary {...data} groups={[
      { counts: [{ label: 'i8 返回', value: data.sourceCount }],
        breakdown: [{ label: '编号缺失', value: missingNumber }] },
      { counts: [{ label: '已匹配', value: data.status === 'failed' ? null : data.matched }],
        breakdown: [
          { label: '新增', value: data.inserted }, { label: '实际变更', value: data.changed },
          { label: '无变更', value: data.unchanged },
        ] },
      { counts: [
          { label: '待指定归属', value: data.unsettledCount, attention: true },
          { label: '规则剔除', value: data.ignoredCount },
        ],
        breakdown: [{ label: '材料名未补齐', value: data.materialBlank || null }] },
    ]} />
    {data.syncWarning && <p className="notice" role="alert">{data.syncWarning}</p>}
    {(data.unsettled.length > 0 || projects.length > 0) ? <div className="jc-receipt-detail" role="region" aria-label="合同抓取明细">
      {pending.length > 0 && <section className="i8-receipt-section" aria-label="待指定归属">
        <h3>待指定归属（{data.unsettledCount === null ? '已记录 ' : ''}{pending.length} 条{
          data.unsettledCount !== null && data.unsettledCount > data.unsettled.length ? '可查看' : ''}）</h3>
        <ul className="i8-receipt-list">{pending.map(row => <li key={row.id}>
          <ContractEvidence row={row} />
          {actions?.(row)}
        </li>)}</ul>
      </section>}
      {projects.length > 0 && <section className="i8-receipt-section" aria-label="规则剔除">
        <div className="i8-receipt-section-head">
          <h3>规则剔除{data.ignoredCount !== null ? `（${data.ignoredCount} 条）` : ''}</h3>
          <input type="search" aria-label="查找被剔除的合同编号" placeholder="搜索合同编号" value={keyword}
            onChange={event => setKeyword(event.target.value)} />
        </div>
        {data.ignoredCount !== null && data.ignoredCount > data.ignored.length && <p className="muted">已记录 {data.ignored.length} 条合同明细，可在其中搜索。</p>}
        {groups.length === 0 && <p className="state">没有找到该合同编号</p>}
        {groups.map(group => <details key={group.name} open={Boolean(needle) || undefined}>
          <summary>{group.name} <span>{needle ? group.rows.length : group.count} 条</span></summary>
          {group.rows.length > 0 ? <ul className="i8-receipt-list">{group.rows.map(row => <li key={row.id}><ContractEvidence row={row} /></li>)}</ul>
            : <p className="state">本组明细未记录</p>}
        </details>)}
      </section>}
    </div> : data.status !== 'failed' && <p className="state">{data.unsettledCount === 0 && data.ignoredCount === 0
      ? '无归属待指定或规则剔除明细' : '该批次未记录归属或剔除明细。'}</p>}
  </>;
}

export function JcFetchReceipt({ active, close, runId, history = true }: {
  active: boolean; close: () => void; runId?: number; history?: boolean;
}) {
  const query = useQuery({
    queryKey: ['jc-fetch-receipt', runId ?? 'latest'],
    enabled: active, staleTime: 0, refetchOnMount: 'always',
    queryFn: async ({ signal }) => readReceipt(await requestJson(
      jcRulesPath + '/receipt' + (runId === undefined ? '' : `?run_id=${runId}`), { signal })),
  });
  const closing = useDialogClose({ busy: false, dirty: false, close, active });
  const data = query.data;
  return <BusinessModal open={active} className="rules-dialog jc-receipt-dialog" titleId="jc-receipt-title" requestClose={closing.requestClose}>
    <DialogContents title={runId === undefined ? '最近一次集采抓取结果' : '集采抓取明细'} titleId="jc-receipt-title" closing={closing}>
      {query.isFetching && <p role="status">正在读取抓取结果…</p>}
      {query.isError && <ReadFailure read={query} />}
      {!query.isFetching && (data ? <JcReceiptContents data={data} /> : !query.isError && <p className="state">暂无集采抓取记录</p>)}
      <div className="dialog-actions jc-receipt-actions">
        {history && <Link to="/i8#execution-records" onClick={close}>i8 接入层 · 执行记录</Link>}
        <Button onClick={closing.requestClose}>关闭</Button>
      </div>
    </DialogContents>
  </BusinessModal>;
}
