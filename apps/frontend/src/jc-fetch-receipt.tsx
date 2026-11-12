import Button from 'antd/es/button';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { ApiError, record, requestJson } from './api';
import { ReadGrid } from './business-grid';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { isJcRule, jcCondition, jcRuleKinds, jcRulesPath } from './jc-rule-data';
import type { JcRule } from './jc-rule-data';
import { ReadFailure } from './read-region';

interface ReceiptRow {
  id: string;
  contract: string;
  project: string;
  document: string;
  reason: string;
  matches: JcRule[];
}

const ownershipReason: Record<string, string> = {
  needs_keyword: '缺少小微识别词',
  needs_choice: '命中多个项目',
  not_archived: '项目未建档',
};

function readReceiptRows(value: unknown, ignored: boolean): ReceiptRow[] {
  if (!Array.isArray(value)) return [];
  return value.filter(record).map((row, index) => {
    const matches = Array.isArray(row.matches) ? row.matches.filter(isJcRule) : [];
    return {
      id: `${ignored ? 'ignored' : 'unsettled'}-${index}`,
      contract: typeof row.contract_no === 'string' ? row.contract_no : '',
      project: typeof row.project_name === 'string' ? row.project_name : '',
      document: typeof row.doc_name === 'string' ? row.doc_name : '',
      reason: ignored ? matches.length ? '规则剔除' : '规则剔除 · 旧记录未保存命中条件'
        : typeof row.kind === 'string' ? ownershipReason[row.kind] ?? '归属待指定' : '归属待指定',
      matches,
    };
  });
}

function readReceipt(value: unknown) {
  if (record(value) && value.receipt === null) return null;
  if (!record(value) || !record(value.receipt)) throw new ApiError('抓取结果读取不完整，请重试。');
  const item = value.receipt;
  if (typeof item.started_at !== 'string' || typeof item.status !== 'string' || typeof item.matched !== 'number') {
    throw new ApiError('抓取结果读取不完整，请重试。');
  }
  const ignored = readReceiptRows(item.ignored, true);
  const unsettled = readReceiptRows(item.unsettled, false);
  return {
    startedAt: item.started_at.replace('T', ' '), status: item.status, matched: item.matched,
    ignored: typeof item.ignored_count === 'number' ? item.ignored_count : null,
    unsettled: typeof item.unsettled_count === 'number' ? item.unsettled_count : null,
    rows: [...unsettled, ...ignored],
  };
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
  const total = data && data.ignored !== null && data.unsettled !== null ? data.ignored + data.unsettled : null;
  const status = data?.status === 'success' ? '抓取完成'
    : data?.status === 'failed' ? '抓取失败' : data?.status === 'partial' ? '部分完成' : '抓取进行中';
  return <BusinessModal open={active} className="rules-dialog jc-receipt-dialog" titleId="jc-receipt-title" requestClose={closing.requestClose}>
    <DialogContents title={runId === undefined ? '最近一次集采抓取结果' : '集采抓取明细'} titleId="jc-receipt-title" closing={closing}>
      {query.isFetching && <p role="status">正在读取抓取结果…</p>}
      {query.isError && <ReadFailure read={query} />}
      {!query.isFetching && (data ? <>
        <div className="jc-receipt-summary">
          <time>{data.startedAt}</time><strong>{status}</strong>
          {data.status !== 'failed' && <span>已匹配 {data.matched} 份合同</span>}
          {data.unsettled !== null && <span>归属待指定 {data.unsettled} 份</span>}
          {data.ignored !== null && <span>规则剔除 {data.ignored} 份</span>}
        </div>
        {data.rows.length > 0 && <>
          <ReadGrid table="jc-fetch-receipt" className="rules-table jc-receipt-table" label="合同抓取明细" domLayout="autoHeight"
            rows={data.rows} rowId={row => row.id} columns={[
              {field:'contract',headerName:'合同编号',valueFormatter:p=>p.value || '—'},
              {field:'project',headerName:'i8 项目',valueFormatter:p=>p.value || '—'},
              {field:'document',headerName:'单据名',valueFormatter:p=>p.value || '—'},
              {field:'reason',headerName:'原因',cellRenderer:({data:row}:{data:ReceiptRow})=><div>
                <div>{row.reason}</div>
                {row.matches.length > 0 && <ul className="jc-receipt-matches">{row.matches.map(rule => <li key={rule.id}>
                  {jcRuleKinds[rule.kind]} · {jcCondition(rule)}{rule.reason && `（${rule.reason}）`}
                </li>)}</ul>}
              </div>},
            ]} />
          {total !== null && total > data.rows.length && <p className="muted">本次记录保留了 {total} 份中的 {data.rows.length} 份合同明细。</p>}
        </>}
        {data.rows.length === 0 && data.status !== 'failed' && <p className="state">无归属待指定或规则剔除明细</p>}
      </> : !query.isError && <p className="state">暂无集采抓取记录</p>)}
      <div className="dialog-actions jc-receipt-actions">
        {history && <Link to="/i8#execution-records" onClick={close}>i8 接入层 · 执行记录</Link>}
        <Button onClick={closing.requestClose}>关闭</Button>
      </div>
    </DialogContents>
  </BusinessModal>;
}
