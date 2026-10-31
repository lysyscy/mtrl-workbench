import Button from 'antd/es/button';
import Select from 'antd/es/select';
import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { Project } from './api';
import { cents, decimal, money, projectLabel } from './api';
import { BusinessGrid } from './business-grid';
import { contentWidth, fullTextWidth } from './grid';
import { getOilReconciliation } from './oilcard-ledger-api';
import type { OilReconciliationRow } from './oilcard-ledger-api';
import type { OilAccount, OilArchives, OilCard } from './oilcard-api';

type Row = { key: string; group: string; kind: 'primary' | 'account' | 'total'; title: string; account?: OilAccount; card?: OilCard; primary?: OilCard; allocation?: OilReconciliationRow; amount: string | null; invoiced?: string; difference?: string };
export function OilReconciliationSheet({ archives, projects, active, blocked, scale, remark, openLedger }: {
  archives: OilArchives; projects: Project[]; active: boolean; blocked: boolean; scale: number;
  remark: (kind: 'card' | 'account', row: OilCard | OilAccount) => ReactNode; openLedger: () => void;
}) {
  const query = useQuery({ queryKey: ['oilcard-reconciliation'], enabled: active && !blocked, queryFn: ({ signal }) => getOilReconciliation(signal) });
  const [status, setStatus] = useState('active'), [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const rows = useMemo<Row[]>(() => {
    const cards = new Map(archives.cards.map(card => [card.id, card])), accounts = new Map(archives.accounts.map(account => [account.id, account]));
    const groups = new Map<string, { primary?: OilCard; children: Row[] }>();
    for (const card of archives.cards.filter(card => card.kind === 'primary')) groups.set(String(card.id), { primary: card, children: [] });
    for (const allocation of query.data?.rows ?? []) {
      const account = accounts.get(allocation.account_id); if (!account || status !== 'all' && account.status !== status) continue;
      const card = allocation.card_id ? cards.get(allocation.card_id) : undefined, group = String(allocation.primary_card_id ?? 'unassigned');
      if (!groups.has(group)) groups.set(group, { children: [] });
      groups.get(group)!.children.push({ key: `account:${account.id}:${allocation.project_id}:${allocation.card_id}`, group, kind: 'account', account, ...(card ? { card } : {}), allocation,
        title: projects.find(p => p.id === allocation.project_id) ? projectLabel(projects.find(p => p.id === allocation.project_id)!) : `项目 #${allocation.project_id}`, amount: allocation.total_amount, invoiced: allocation.invoiced_amount, difference: allocation.difference_amount });
    }
    return [...groups].flatMap(([group, value]) => [{ key: `primary:${group}`, group, kind: 'primary' as const,
      title: value.primary ? `主卡 ${value.primary.card_no || `卡号待补 #${value.primary.id}`}` : '未关联主卡', amount: null, ...(value.primary ? { primary: value.primary } : {}) }, ...(collapsed.has(group) ? [] : value.children)]);
  }, [archives, projects, query.data, status, collapsed]);
  // 折叠只改变显示，金额范围仍取本状态下所有账户归属。
  const amount = useMemo(() => decimal((query.data?.rows ?? []).filter(r => status === 'all' || archives.accounts.find(a => a.id === r.account_id)?.status === status).reduce((sum, r) => sum + cents(r.total_amount), 0n)), [query.data, archives, status]);
  const sums = useMemo(() => {
    const included = (query.data?.rows ?? []).filter(r => status === 'all' || archives.accounts.find(a => a.id === r.account_id)?.status === status);
    return { invoiced: decimal(included.reduce((n, r) => n + cents(r.invoiced_amount), 0n)), difference: decimal(included.reduce((n, r) => n + cents(r.difference_amount), 0n)) };
  }, [query.data, archives, status]);
  const amountWidth = fullTextWidth([money(amount), ...rows.map(row => row.amount === null ? '' : money(row.amount))], scale).minWidth;
  const columns = useMemo<ColDef<Row>[]>(() => [
    { colId: 'project', headerName: '项目', ...contentWidth(200, 420, scale, 1), valueGetter: p => p.data?.title ?? '', cellRenderer: ({ data }: ICellRendererParams<Row>) => !data ? null : data.kind === 'primary' ? <div className="oilcard-primary"><Button size="small" aria-label={`${collapsed.has(data.group) ? '展开' : '收起'} ${data.title}`} onClick={() => setCollapsed(old => { const next = new Set(old); if (next.has(data.group)) next.delete(data.group); else next.add(data.group); return next; })}>{collapsed.has(data.group) ? '展开' : '收起'}</Button><strong>{data.title}</strong></div> : data.title },
    { colId: 'account', headerName: '用卡账户', ...contentWidth(160, 320, scale, 1), valueGetter: p => p.data?.account?.name ?? '', cellRenderer: ({ data }: ICellRendererParams<Row>) => data?.account && <span>{data.account.name}{data.allocation?.current === false && <small className="muted">（历史关联）</small>}</span> },
    { colId: 'card', headerName: '副卡', ...contentWidth(200, 350, scale, 1), valueGetter: p => p.data?.kind === 'account' ? p.data.card?.card_no || (p.data.card ? `卡号待补 #${p.data.card.id}` : '未关联卡片') : '' },
    { field: 'amount', headerName: '充值累计', cellClass: 'money', ...contentWidth(Math.max(130, amountWidth / scale), 240, scale), valueFormatter: p => p.value === null || p.value === undefined ? '' : money(p.value) },
    { field: 'invoiced', headerName: '开票累计', cellClass: 'money', ...contentWidth(Math.max(130, fullTextWidth([money(sums.invoiced), ...rows.map(r => money(r.invoiced || '0.00'))], scale).minWidth / scale), 240, scale), valueFormatter: p => p.value === undefined ? '' : money(p.value) },
    { field: 'difference', headerName: '差额', cellClass: 'money', ...contentWidth(Math.max(130, fullTextWidth([money(sums.difference), ...rows.map(r => money(r.difference || '0.00'))], scale).minWidth / scale), 240, scale), valueFormatter: p => p.value === undefined ? '' : money(p.value) },
    { colId: 'remark', headerName: '备注', ...contentWidth(200, 500, scale, 2), cellRenderer: ({ data }: ICellRendererParams<Row>) => data?.primary ? remark('card', data.primary) : data?.account ? remark('account', data.account) : '' },
  ], [scale, amountWidth, collapsed, remark, rows, sums]);
  const totals = useMemo<Row[]>(() => [{ key: 'total', group: '', kind: 'total', title: '合计', amount, ...sums }], [amount, sums]);
  return <section aria-label="账户充值与开票核对"><div data-page-chrome className="oilcard-toolbar"><Button onClick={openLedger}>查看充值与发票</Button><label>账户状态<Select aria-label="核对账户状态" value={status} onChange={setStatus} options={[{ value: 'active', label: '在用' }, { value: 'archived', label: '归档' }, { value: 'all', label: '全部' }]} /></label></div>
    {query.isError && <p className="notice" role="alert">{query.error.message}<Button disabled={blocked} onClick={() => void query.refetch()}>重读账户累计</Button></p>}
    {query.isPending ? <p role="status" data-page-loading>正在核对充值累计…</p> : query.data && (rows.length ? <BusinessGrid table="oilcard-reconciliation" rows={rows} columns={columns} totals={totals} rowId={row => row.key} scale={scale} label="账户充值累计" domLayout="autoHeight" grid={{ rowClassRules: { 'oilcard-primary-row': p => p.data?.kind === 'primary' } }} /> : <p className="state">尚无符合条件的用卡账户。可在用卡账户工作表建档。</p>)}
  </section>;
}
