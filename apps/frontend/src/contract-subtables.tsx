import { DialogPresence } from './workspace-motion';
import Button from 'antd/es/button';
import Pagination from 'antd/es/pagination';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useHref, useLinkClickHandler } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ApiError, requestJson } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { contractHistoryDate } from './contracts-api';
import type { ContractRow } from './contracts-api';
import { useHistoryGuard } from './history';
import { live, money, readNotices } from './notices-api';
import { draftProblem, loadSubtables } from './contract-subtables-api';
import type { SubtableKind } from './contract-subtables-api';
import type { InvoiceRow, PaymentDisplayRow } from './contract-subtables-api';
import { subtableOverage } from './contract-subtable-overage';
import { subtableDraftDirty as draftDirty } from './contract-subtable-workspace';
import type { ContractSubtableWorkspace, SubtableView } from './contract-subtable-workspace';
import { ReadGrid } from './business-grid';
import { numberColumnWidth, pageGridGeometry, textWidth } from './grid';
import { completeColumnWidth } from './grid-text';
import { BusinessDate } from './time-picker';
import { ReadFailure, ReadPlaceholder, ReadStatusLane, readPhase } from './read-region';

function completeMoneyWidth(values: string[], scale: number) {
  const amount = numberColumnWidth(values, scale), complete = completeColumnWidth(values, '金额（元）', scale);
  const minWidth = Math.max(amount.minWidth, complete.minWidth);
  return { ...complete, initialWidth: minWidth, minWidth };
}

/**
 * 明细表格的高度：按行数算自然高度，只有超过可用高度上限（CSS 变量 --subtable-detail-max）才封顶。
 * 表格走 AG 原生普通布局，滚动发生在表格内部，表头与合计行由表格自己固定，不靠外层容器滚。
 */
function detailHeight(scale: number, rows: number): string {
  const { rowHeight, headerHeight } = pageGridGeometry(scale);
  const natural = Math.ceil(headerHeight + (rows + 1) * rowHeight + 2);
  return `min(${natural}px, var(--subtable-detail-max))`;
}

function NoticeButton({ id, children }: { id: number; children: ReactNode }) {
  const to = `/notices?notice=${id}`, href = useHref(to), onClick = useLinkClickHandler<HTMLAnchorElement>(to);
  return <Button size="small" href={href} onClick={onClick}>{children}</Button>;
}

function WarningMark() {
  return <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false"><path d="M12 4.6 20.6 20H3.4z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/><path d="M12 10v4.4M12 17.2v.1" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg>;
}

export function ContractSubtables({ contractId, historyDate, workspace, writable, paused, onlyKind, summaryRow, contracts = [] }: {
  contractId: number; historyDate: string; workspace: ContractSubtableWorkspace;
  writable: boolean; paused: boolean; onlyKind?: SubtableKind; summaryRow?: ContractRow; contracts?: ContractRow[];
}) {
  const root = useRef<HTMLDivElement>(null), guard = useId();
  const [referencing, setReferencing] = useState(false);
  const focused = useRef<SubtableView['focus']>(null);
  const [linkPage, setLinkPage] = useState(1);
  const linkPageSize = 8;
  const labels: Record<SubtableKind, string> = { supplier: historyDate ? '历史未结金额' : '供应商发票', trade: '贸易公司发票', payment: '手工付款' };
  const state = workspace.view(contractId);
  const query = useQuery({ queryKey: ['contract-subtables', contractId], enabled: !paused, staleTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: false, retry: (count, failure) => count < 1 && !(failure instanceof ApiError && failure.status >= 400 && failure.status < 500), retryDelay: 500, queryFn: ({ signal }) => loadSubtables(contractId, signal) });
  useEffect(() => { if (!paused) void workspace.activate(contractId, historyDate); }, [workspace, contractId, historyDate, paused]);
  useHistoryGuard(guard, () => paused ? '' : state?.busy ? '合同子表正在保存，请稍候。' : state?.uncertain ? '合同子表保存结果待确认，正在自动核对，可刷新页面恢复。' : state?.dirty ? '合同子表有未保存输入，请先处理。' : '');

  useEffect(() => {
    const focus = state?.focus;
    if (!focus || focus === focused.current || query.isFetching || paused) return;
    const target = root.current?.querySelector<HTMLElement>(`[data-subtable="${focus.kind}"][data-row="${focus.id}"]`);
    if (target && (!root.current?.contains(document.activeElement) || document.activeElement?.tagName === 'BUTTON')) {
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: 'nearest' });
    }
    if (target) focused.current = focus;
  }, [state?.focus, query.data, query.isFetching, paused]);

  const unavailable = !writable || paused || !state || state.busy || state.uncertain || query.isFetching || query.isError || !query.data;
  // 首读保留明细表框；失败反馈按需占行，正常状态不留空行。
  const readState = readPhase(query);
  const placeheld = readState === 'idle' || readState === 'reading' || readState === 'error';

  async function save(kind: SubtableKind, deleting = false) { if (!unavailable) await workspace.submit(contractId, kind, deleting); }
  function input(kind: SubtableKind, key: 'date' | 'amount', value: string) { workspace.edit(contractId, kind, key, value); }
  function draftRow(kind: SubtableKind) {
    if (!state) return null;
    const retry = state.retry.includes(kind);
    return <div className="subtable-draft subtable-entry">
      <label>{kind === 'supplier' && historyDate ? '核对截至日' : '日期'}<BusinessDate label={kind === 'supplier' && historyDate ? '核对截至日' : labels[kind] + '日期'} value={state.drafts[kind].date} disabled={!writable || paused || state.busy || state.uncertain} onChange={value => input(kind, 'date', value)}/></label>
      <label>金额（元）<Input aria-label={kind === 'supplier' && historyDate ? '历史未结金额（元）' : labels[kind] + '金额（元）'} inputMode="decimal" value={state.drafts[kind].amount} disabled={!writable || paused || state.busy || state.uncertain} onChange={e => input(kind, 'amount', e.target.value)}/></label>
      {kind === 'payment' && <span>手工录入</span>}
      <div className="subtable-draft-actions">
        <Button htmlType="button" className="primary" disabled={unavailable} onClick={() => void save(kind)}>{retry ? `重试上次${labels[kind]}` : `新增${labels[kind]}`}</Button>
        <Button htmlType="button" disabled={!writable || paused || state.busy || state.uncertain || !draftDirty(state.drafts[kind])} onClick={() => workspace.discard(contractId, kind)}>取消</Button>
      </div>
    </div>;
  }
  function remove(kind: SubtableKind, row: { id: number; date: string; amount: string }) { workspace.selectDeletion(contractId, { kind, ...row }); }
  const data = query.data, scale = Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1;
  const linkedNotices = [...new Set((data?.payments ?? []).filter(p => p.source === 'notice').map(p => p.notice_id!))];
  const currentLinkPage = Math.max(1, Math.min(linkPage, Math.ceil(linkedNotices.length / linkPageSize)));
  const invoiceRows = (kind: 'supplier' | 'trade') => data?.[kind === 'supplier' ? 'supplier_invoices' : 'trade_invoices'] ?? [];
  // Standalone invoice dialogs share bounded flex; the embedded editor keeps its existing sizing.
  const invoiceWidth = (width: ReturnType<typeof completeColumnWidth>, max: number, flex: number) => onlyKind === 'supplier' || onlyKind === 'trade'
    ? { ...width, maxWidth: Math.max(width.minWidth, max * scale), initialFlex: flex } : width;

  /** 超额提醒：只看本侧已保存累计与本侧合同额；历史未结汇总不套发票提醒。 */
  function overageLine(kind: 'supplier' | 'trade') {
    if (!data || !summaryRow) return null;
    // 历史未结汇总走的是"截至日余额"口径，不套发票超额提醒。
    if (kind === 'supplier' && historyDate) return null;
    const saved = kind === 'supplier' ? data.inv_sum : data.trade_inv_sum;
    const contract = kind === 'supplier' ? summaryRow.contract_amt : summaryRow.trade_contract_amt;
    const draft = state?.drafts[kind];
    const pending = draft && !draftProblem(draft) ? draft.amount : '';
    const info = subtableOverage({ side: kind, savedTotal: saved, contractAmount: contract, pendingAmount: pending });
    if (info.missingContract || info.contract === null) return <p className="subtable-overage" data-state="unknown">合同额缺失，无法判断超额。</p>;
    if (!info.over && !info.projectedOver) return null;
    return <div className="subtable-overage" data-state="warning" role="status">
      <span className="subtable-overage-mark"><WarningMark/></span>
      <div className="subtable-overage-lines">
        {info.over && <p>累计 {money(info.saved)} 元 / 合同额 {money(info.contract)} 元，超出 {info.excessRatio}%。</p>}
        {info.projectedOver && <p>本次保存后将超额：累计 {money(info.projected)} 元 / 合同额 {money(info.contract)} 元，超出 {info.projectedExcessRatio}%。</p>}
      </div>
    </div>;
  }

  return <div ref={root} className="contract-subtables" onKeyDown={e => { if (e.key === 'Enter' && e.target instanceof HTMLInputElement && !e.nativeEvent.isComposing) e.preventDefault(); }} aria-label="合同发票与付款明细">
    {(!onlyKind || onlyKind === 'payment') && <div className="subtable-heading">{!onlyKind && <h3>发票与付款</h3>}<div className="subtable-tools">{onlyKind === 'payment' && <Button htmlType="button" disabled={unavailable} onClick={() => setReferencing(true)}>从付款域引用</Button>}</div></div>}
    {onlyKind && summaryRow && <div className="subtable-summary">
      <dl className="subtable-summary-facts">
        <div><dt>供应商</dt><dd>{onlyKind === 'trade' ? summaryRow.trade_co || '未填' : summaryRow.supplier || '未填'}</dd></div>
        <div><dt>材料名</dt><dd>{summaryRow.material || '未填'}</dd></div>
        <div><dt>{onlyKind === 'payment' ? '结算金额' : '合同金额'}</dt><dd className="money">{onlyKind === 'payment' ? `${money(data?.settle ?? summaryRow.settle)} 元` : onlyKind === 'trade' ? (summaryRow.trade_contract_amt === null ? '—' : `${money(summaryRow.trade_contract_amt)} 元`) : `${money(summaryRow.contract_amt)} 元`}</dd></div>
      </dl>
      {onlyKind !== 'payment' && overageLine(onlyKind)}
    </div>}
    {state?.storageWarning && <p className="subtable-storage-note" role="status">{state.storageWarning}</p>}
    <ReadStatusLane phase={readState} announce="正在读取合同子表…" className="subtable-read-status">
      {(readState === 'error' || readState === 'stale') && <ReadFailure read={query} retained="明细更新失败，保留上次结果。"/>}
    </ReadStatusLane>
    {data ? <>{historyDate && <p className="subtable-history-note">历史未结金额，核对截至日 {historyDate}；已扣除此前付款，请勿重复录入。</p>}{!onlyKind && <div className="subtable-totals">{[['结算金额', data.settle], ['付款金额', data.pay_sum], ['欠款金额', data.debt]].map(([label, value]) => <span key={label}>{label}<strong>{money(value!)} 元</strong></span>)}</div>}
      <div className="subtable-invoices">{(['supplier', 'trade'] as const).filter(kind => (!onlyKind || kind === onlyKind) && (kind === 'supplier' || data.trade_co || data.trade_invoices.length || state && draftDirty(state.drafts.trade))).map(kind => <section key={kind} aria-label={labels[kind]}>
        <div className="subtable-section-head">{(!onlyKind || onlyKind !== 'payment') && <h4>{labels[kind]}{kind === 'trade' && data.trade_co ? `，${data.trade_co}` : kind === 'supplier' && data.supplier ? `，${data.supplier}` : ''}</h4>}<span className="subtable-count">共 {invoiceRows(kind).length} 条</span></div>
        {onlyKind === undefined && overageLine(kind)}
        <div className="subtable-detail-scroll">
          <ReadGrid singleLine manualWidths table={'contract-invoices-' + kind} className="subtable-invoice-table" label={labels[kind] + '明细'} domLayout="normal" style={{ height: detailHeight(scale, invoiceRows(kind).length) }} rows={invoiceRows(kind)} rowId={row => String(row.id)} totals={[{ id: -1, kind, date: kind === 'supplier' && historyDate ? '历史未结合计' : '发票合计', amount: kind === 'supplier' ? data.inv_sum : data.trade_inv_sum }]} columns={[
            { field: 'date', headerName: kind === 'supplier' && historyDate ? '核对截至日' : '发票日期', ...invoiceWidth(completeColumnWidth([...invoiceRows(kind).map(row => row.date || '日期未填'), kind === 'supplier' && historyDate ? '历史未结合计' : '发票合计'], kind === 'supplier' && historyDate ? '核对截至日' : '发票日期', scale), 170, 1), cellRenderer: ({ data: row, node }: { data: InvoiceRow; node: { rowPinned: unknown } }) => node.rowPinned ? row.date : <div tabIndex={-1} data-subtable={kind} data-row={row.id}>{row.date || '日期未填'}</div> },
            { field: 'amount', headerName: '金额（元）', ...invoiceWidth(completeMoneyWidth([...invoiceRows(kind).map(row => money(row.amount)), money(kind === 'supplier' ? data.inv_sum : data.trade_inv_sum)], scale), 240, 1.5), cellClass: 'money', valueFormatter: p => money(p.value) },
            { colId: 'actions', headerName: '操作', ...invoiceWidth(completeColumnWidth(['删除发票'], '操作', scale, 24), 160, 1), cellRenderer: ({ data: row, node }: { data: InvoiceRow; node: { rowPinned: unknown } }) => node.rowPinned ? null : <Button htmlType="button" danger size="small" disabled={unavailable} onClick={() => remove(kind, row)}>删除发票</Button> },
          ]}/>
        </div>
        {draftRow(kind)}
      </section>)}</div>
      {(!onlyKind || onlyKind === 'payment') && <section aria-label="合同付款明细">{!onlyKind && <div className="subtable-heading"><h4>付款明细</h4><Button htmlType="button" disabled={unavailable} onClick={() => setReferencing(true)}>从付款域引用</Button></div>}<div className="subtable-section-head"><span className="subtable-count">共 {data.payment_display_rows.length} 条</span></div><div className="subtable-detail-scroll"><ReadGrid singleLine manualWidths table="contract-payments" className="subtable-payment-table" label="合同付款记录" domLayout="normal" style={{ height: detailHeight(scale, data.payment_display_rows.length) }} rows={data.payment_display_rows} rowId={row => row.id + ':' + (row.flow_id ?? row.display_kind)} totals={[{ id: -1, date: '合同付款合计', amount: data.pay_sum, source: 'manual', notice_id: null, display_kind: 'manual' }]} columns={[
        { field: 'date', headerName: '付款日期', ...completeColumnWidth([...data.payment_display_rows.map(row => row.date || '日期未填'), '合同付款合计', '最近实际付款日'], '付款日期', scale), autoHeight: true, cellRenderer: ({ data: row, node }: { data: PaymentDisplayRow; node: { rowPinned: unknown } }) => node.rowPinned ? row.date : <div tabIndex={-1} data-subtable="payment" data-row={row.id}>{row.date || '日期未填'}{row.display_kind === 'stat' && row.date && <small>最近实际付款日</small>}</div> },
        { field: 'amount', headerName: '金额（元）', ...completeMoneyWidth([...data.payment_display_rows.map(row => money(row.amount)), money(data.pay_sum)], scale), cellClass: 'money', valueFormatter: p => money(p.value) },
        { colId: 'source', headerName: '来源与口径', ...textWidth(240, 420, scale, 1), wrapText: true, autoHeight: true, cellRenderer: ({ data: row, node }: { data: PaymentDisplayRow; node: { rowPinned: unknown } }) => node.rowPinned ? null : row.display_kind === 'manual' ? '手工录入' : <span className="subtable-payment-source"><NoticeButton id={row.notice_id!}>查看通知书</NoticeButton><small>{row.display_kind === 'flow' ? '实际付款（统计一致）' : '统计累计，与实际付款有差异'}</small></span> },
        { colId: 'actions', headerName: '操作', ...completeColumnWidth(['删除手工付款', '回通知书改关联'], '操作', scale, 24), cellRenderer: ({ data: row, node }: { data: PaymentDisplayRow; node: { rowPinned: unknown } }) => node.rowPinned ? null : row.source === 'manual' ? <Button htmlType="button" danger size="small" disabled={unavailable} onClick={() => remove('payment', row)}>删除手工付款</Button> : <span className="muted">回通知书改关联</span> },
      ]}/></div>{draftRow('payment')}</section>}
      {(!onlyKind || onlyKind === 'payment') && linkedNotices.length > 0 && <div className="subtable-linked-group"><div className="subtable-links"><span>已关联通知书</span>{linkedNotices.slice((currentLinkPage - 1) * linkPageSize, currentLinkPage * linkPageSize).map((id, index) => <NoticeButton key={id} id={id}>通知书 {(currentLinkPage - 1) * linkPageSize + index + 1}</NoticeButton>)}</div>{linkedNotices.length > linkPageSize && <Pagination aria-label="已关联通知书分页" size="small" current={currentLinkPage} pageSize={linkPageSize} total={linkedNotices.length} showSizeChanger={false} onChange={setLinkPage}/>}</div>}
    </> : placeheld && <div className="subtable-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={5} quiet={readState === 'error'}/></div>}
    <DialogPresence>{referencing && <ContractPaymentReference contractId={contractId} contracts={contracts} paused={paused} writable={writable} workspace={workspace} close={() => setReferencing(false)}/>}</DialogPresence>
    {state?.deleting && (!onlyKind || state.deleting.kind === onlyKind) && <div className="subtable-delete" role="group" aria-label="确认删除子行"><p>删除{labels[state.deleting.kind]}：{state.deleting.date || '日期未填'}，{money(state.deleting.amount)} 元？</p><Button htmlType="button" disabled={state.busy} onClick={() => workspace.selectDeletion(contractId, null)}>取消删除</Button><Button htmlType="button" danger disabled={unavailable} onClick={() => void save(state.deleting!.kind, true)}>确认删除</Button></div>}
    {state?.feedback && <p role="status">{state.feedback}</p>}{state?.error && <p className="notice" role="alert">{state.error}</p>}
  </div>;
}

export function ContractSubtableDialog({ row, kind, contracts, workspace, paused, writable, close }: {
  row: ContractRow; kind: SubtableKind; contracts: ContractRow[]; workspace: ContractSubtableWorkspace; paused: boolean; writable: boolean; close: () => void;
}) {
  const state = workspace.view(row.id), historyDate = contractHistoryDate(row.remark), titleId = useId();
  const closing = useDialogClose({ busy: Boolean(state?.busy), dirty: Boolean(state && draftDirty(state.drafts[kind])), active: !paused, close: () => {
    workspace.discard(row.id, kind);
    close();
  } });
  const title = kind === 'payment' ? '付款子表' : kind === 'trade' ? '贸易公司发票子表' : historyDate ? '历史未结金额' : '供应商发票子表';
  return <BusinessModal open={!paused} centered={false} className={`project-dialog contract-subtable-dialog${kind === 'payment' ? '' : ' contract-invoice-dialog'}`} titleId={titleId} requestClose={closing.requestClose}><DialogContents title={title} titleId={titleId} closing={closing}>
    <ContractSubtables contractId={row.id} historyDate={historyDate} contracts={contracts} workspace={workspace} writable={writable} paused={paused} onlyKind={kind} summaryRow={row}/>
    <div className="dialog-actions"><Button htmlType="button" disabled={Boolean(state?.busy)} onClick={closing.requestClose}>关闭</Button></div>
  </DialogContents></BusinessModal>;
}

function ContractPaymentReference({ contractId, contracts, paused, writable, workspace, close }: {
  contractId: number; contracts: ContractRow[]; paused: boolean; writable: boolean; workspace: ContractSubtableWorkspace; close: () => void;
}) {
  const state = workspace.view(contractId);
  const [selected, setSelected] = useState<number | undefined>(), [saved, setSaved] = useState(false), [error, setError] = useState('');
  const lock = useRef(false), titleId = useId();
  const closing = useDialogClose({ busy: Boolean(state?.busy), dirty: !saved && selected !== undefined, close, active: !paused });
  const query = useQuery({ queryKey: ['contract-payment-candidates', contractId], enabled: !paused, staleTime: 0, refetchOnMount: 'always', retry: false, queryFn: async ({ signal }) => readNotices(await requestJson('/api/m03/notice-list?period=', { signal })) });
  const used = new Set(contracts.flatMap(row => row.notice_ids));
  const candidates = (query.data ?? []).filter(row => live(row) && row.category === 'jc' && !used.has(row.notice_id));
  const chosen = candidates.find(row => row.notice_id === selected);
  const unavailable = paused || !writable || Boolean(state?.busy || state?.uncertain) || saved || query.isFetching || query.isError || !chosen;
  async function reference() {
    if (unavailable || lock.current || !chosen) return;
    lock.current = true; setError('');
    try {
      const result = await workspace.reference(contractId, chosen.notice_id);
      if (result === 'saved') { setSaved(true); close(); }
      else { if (result === 'written') setSaved(true); setError(workspace.view(contractId)?.error ?? ''); }
    } finally { lock.current = false; }
  }
  return <BusinessModal open={!paused} className="project-dialog contract-payment-reference" titleId={titleId} requestClose={closing.requestClose}><DialogContents title="从付款域引用付款记录" titleId={titleId} closing={closing}>
    <p>按集采实际供应商核对；同一通知书只能引用一次。</p>
    {query.isPending ? <p role="status">正在读取可引用通知书…</p> : query.isError ? <p role="alert" className="notice">{query.error.message}<Button htmlType="button" onClick={() => void query.refetch()}>重读候选</Button></p> : <label className="contract-field">集采通知书<Select aria-label="引用集采通知书" placeholder="请选择通知书" value={selected} disabled={Boolean(state?.busy) || saved || Boolean(state?.uncertain)} onChange={setSelected} getPopupContainer={trigger => (trigger as HTMLElement).closest<HTMLElement>('.ant-modal-container') ?? document.body} options={candidates.map(row => ({ value: row.notice_id, label: `${row.bill_no}，${row.jc_supplier || '未录入供应商'}，${money(row.stat_paid)} 元` }))}/></label>}
    {!query.isPending && !query.isError && !candidates.length && <p>没有可引用的通知书。</p>}
    {error && <p className="notice" role="alert">{error}</p>}
    <div className="dialog-actions"><Button htmlType="button" disabled={Boolean(state?.busy)} onClick={closing.requestClose}>{saved ? '关闭' : '取消'}</Button>{!saved && <Button htmlType="button" type="primary" disabled={unavailable} onClick={() => void reference()}>引用</Button>}</div>
  </DialogContents></BusinessModal>;
}
