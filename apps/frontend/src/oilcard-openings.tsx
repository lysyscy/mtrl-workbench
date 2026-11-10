import Button from 'antd/es/button';
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ColDef } from 'ag-grid-community';
import { money, projectLabel } from './api';
import type { Project } from './api';
import { ReadGrid } from './business-grid';
import type { OilArchives } from './oilcard-api';
import { getOilOpenings } from './oilcard-ledger-api';
import type { OilOpening } from './oilcard-ledger-api';

export function OilOpeningHistory({ archives, projects, enabled, scale }: {
  archives: OilArchives; projects: Project[]; enabled: boolean; scale: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const query = useQuery({ queryKey: ['oilcard-openings'], enabled, queryFn: ({ signal }) => getOilOpenings(signal) });
  const columns = useMemo<ColDef<OilOpening>[]>(() => [
    { headerName: '项目', valueGetter: ({ data }) => { const project = projects.find(p => p.id === data?.project_id); return project ? projectLabel(project) : `项目 #${data?.project_id}`; } },
    { headerName: '用卡账户', valueGetter: ({ data }) => archives.accounts.find(a => a.id === data?.account_id)?.name ?? `账户 #${data?.account_id}` },
    { field: 'amount', headerName: '金额', cellClass: 'money', valueFormatter: p => money(p.value) },
    { field: 'cutoff_ym', headerName: '截至月' },
    { field: 'date_text', headerName: '原日期或标记' },
    { field: 'remark', headerName: '备注' },
    { field: 'source_note', headerName: '来源说明' },
  ], [archives, projects]);
  // During a staged release, existing confirmed amounts remain visible until
  // the separately authorized conversion has put them into the ledger.
  if (query.data?.rows.length === 0 && !query.isError) return null;
  return <div className="oilcard-openings" aria-label="已确认充值期初">
    <div className="oilcard-opening-summary">
      <span>已确认充值期初{query.data && <> <strong>{money(query.data.total_amount)}</strong> · {query.data.rows.length} 笔</>}</span>
      {Boolean(query.data?.rows.length) && <Button size="small" aria-expanded={expanded} aria-controls="oilcard-opening-details" onClick={() => setExpanded(value => !value)}>{expanded ? '收起明细' : '查看明细'}</Button>}
      {query.isPending && <span className="muted">读取中…</span>}
      {query.isError && <span role="alert">{query.error.message} <Button size="small" disabled={!enabled} onClick={() => void query.refetch()}>重读期初</Button></span>}
    </div>
    {expanded && query.data && <div id="oilcard-opening-details">
      <p className="muted">已计入账户核对的充值累计，以下日期台账合计只统计台账内明细。</p>
      <ReadGrid table="oilcard-openings" label="充值期初明细" rows={query.data.rows} columns={columns} rowId={row => String(row.id)} scale={scale} domLayout="autoHeight" />
    </div>}
  </div>;
}
