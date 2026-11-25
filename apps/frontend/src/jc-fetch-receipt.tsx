import Button from 'antd/es/button';
import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ColDef } from 'ag-grid-community';
import { requestJson } from './api';
import { BusinessGrid } from './business-grid';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { textWidth } from './grid';
import { completeColumnWidth } from './grid-text';
import { jcCondition, jcRuleKinds, jcRulesPath } from './jc-rule-data';
import { readReceipt } from './jc-fetch-receipt-data';
import type { Receipt, ReceiptRow } from './jc-fetch-receipt-data';
import { ReadFailure } from './read-region';
import { I8ReceiptSummary } from './i8-receipt-summary';

const matchedStatus = {
  inserted: '新增',
  updated: '实际变更',
  unchanged: '无变更',
} as const;

type MatchedRow = NonNullable<Receipt['matchedItems']>[number];
const matchedRowId = (row: MatchedRow) => row.id;
const showValue = ({ value }: { value?: string | null }) => value || '—';

function MatchedTable({ rows, unchanged = false }: { rows: MatchedRow[]; unchanged?: boolean }) {
  const scale = Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1;
  const columns = useMemo<ColDef<MatchedRow>[]>(() => [
    { field: 'status', headerName: '状态', ...completeColumnWidth(Object.values(matchedStatus), '状态', scale), wrapText: false,
      valueFormatter: ({ data }) => data ? matchedStatus[data.status] : '',
      cellClass: ({ data }) => data?.status === 'unchanged' ? 'muted' : data?.status === 'inserted' ? 'jc-receipt-added' : '' },
    { field: 'contract', headerName: '合同编号', ...completeColumnWidth(rows.map(row => row.contract), '合同编号', scale) },
    { field: 'project', headerName: '项目', ...textWidth(112, 240, scale), valueFormatter: showValue },
    { field: 'document', headerName: '单据名 / 材料名', ...textWidth(164, 360, scale, 2), cellRenderer: ({ data }: { data?: MatchedRow }) => data && <div>
      {data.document || '—'}{data.material && <div className="muted">材料名：{data.material}</div>}
    </div> },
    { field: 'supplier', headerName: '供应商', ...textWidth(112, 240, scale), valueFormatter: showValue },
    { field: 'date', headerName: '合同日期', ...completeColumnWidth(rows.map(row => row.date), '合同日期', scale),
      wrapText: false, valueFormatter: showValue },
    { field: 'amount', headerName: 'i8 合同金额', ...completeColumnWidth(rows.map(row => row.amount), 'i8 合同金额', scale),
      wrapText: false, cellClass: 'money', valueFormatter: showValue },
  ], [rows, scale]);
  return <BusinessGrid table={unchanged ? 'jc-receipt-unchanged' : 'jc-receipt-matched'} className="jc-receipt-matched-grid"
    label={unchanged ? '无变更合同明细' : '匹配合同明细'} rows={rows} columns={columns} rowId={matchedRowId}
    scale={scale} domLayout="autoHeight" />;
}

function MatchedContracts({ items, total }: { items: Receipt['matchedItems']; total: number | null }) {
  const [showUnchanged, setShowUnchanged] = useState(false);
  const { unchanged, visible } = useMemo(() => {
    const unchanged = items?.filter(item => item.status === 'unchanged') ?? [];
    return { unchanged, visible: unchanged.length > 8 ? items?.filter(item => item.status !== 'unchanged') : items };
  }, [items]);
  return <section className="i8-receipt-section" aria-label="已匹配合同">
    <h3>已匹配合同</h3>
    {items === null ? <p className="state">该批次未记录逐条合同明细。</p>
      : total === 0 ? <p className="state">本次没有匹配到合同。</p> : <>
        {total !== null && total > items.length && <p className="muted">
          共 {total} 条，显示 {items.length} 条，其余 {total - items.length} 条未记录。
        </p>}
        {visible && visible.length > 0 && <MatchedTable rows={visible} />}
        {unchanged.length > 8 && <details onToggle={event => setShowUnchanged(event.currentTarget.open)}>
          <summary>无变更合同 <span>{unchanged.length} 条可查看</span></summary>
          {showUnchanged && <MatchedTable rows={unchanged} unchanged />}
        </details>}
      </>}
  </section>;
}

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
    <div className="jc-receipt-detail">
      {pending.length > 0 && <section className="i8-receipt-section" aria-label="待指定归属">
        <h3>待指定归属（{data.unsettledCount === null ? '已记录 ' : ''}{pending.length} 条{
          data.unsettledCount !== null && data.unsettledCount > data.unsettled.length ? '可查看' : ''}）</h3>
        <ul className="i8-receipt-list">{pending.map(row => <li key={row.id}>
          <ContractEvidence row={row} />
          {actions?.(row)}
        </li>)}</ul>
      </section>}
      {data.status !== 'failed' && <MatchedContracts items={data.matchedItems} total={data.matchedItemsTotal} />}
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
      {!data.unsettled.length && !projects.length && data.status !== 'failed' && <p className="state">{
        data.unsettledCount === 0 && data.ignoredCount === 0
          ? '无归属待指定或规则剔除明细' : '该批次未记录归属或剔除明细。'
      }</p>}
    </div>
  </>;
}

export function JcFetchReceipt({ active, close, runId }: {
  active: boolean; close: () => void; runId: number;
}) {
  const query = useQuery({
    queryKey: ['jc-fetch-receipt', runId],
    enabled: active, staleTime: 0, refetchOnMount: 'always',
    queryFn: async ({ signal }) => readReceipt(await requestJson(
      `${jcRulesPath}/receipt?run_id=${runId}`, { signal })),
  });
  const closing = useDialogClose({ busy: false, dirty: false, close, active });
  const data = query.data;
  return <BusinessModal open={active} layout="scroll-body" className="rules-dialog jc-receipt-dialog" titleId="jc-receipt-title" requestClose={closing.requestClose}>
    <DialogContents title="集采抓取明细" titleId="jc-receipt-title" closing={closing}
      footer={<div className="dialog-actions">
        <Button onClick={closing.requestClose}>关闭</Button>
      </div>}>
      {query.isFetching && <p role="status">正在读取抓取结果…</p>}
      {query.isError && <ReadFailure read={query} />}
      {!query.isFetching && (data ? <JcReceiptContents data={data} /> : !query.isError && <p className="state">未找到该批集采抓取记录</p>)}
    </DialogContents>
  </BusinessModal>;
}
