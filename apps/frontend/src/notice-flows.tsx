import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { BoundedGrid } from './bounded-grid';
import { numberColumnWidth } from './grid';
import { DialogContents, useDialogClose } from './dialog-close';
import { EnumTag } from './enum-tag';
import { loadFlows } from './flow-api';
import type { Flow } from './flow-api';
import { cents, decimal, money } from './notices-api';
import type { NoticeRow } from './notices-api';

type FlowGridRow = Pick<Flow, 'flow_no' | 'amount'> & Partial<Flow>;

export function NoticeFlows({ notice, scale, blocked, close }: { notice: NoticeRow; scale: number; blocked: boolean; close: () => void }) {
  const closing = useDialogClose({ busy: false, dirty: false, close, active: !blocked });
  const query = useQuery({ queryKey: ['notice-flows', notice.notice_id], enabled: !blocked, refetchOnWindowFocus: false,
    queryFn: async ({ signal }) => loadFlows(signal, notice.notice_id) });
  const rows = query.data ?? [];
  const paid = decimal(rows.reduce((sum, flow) => flow.status === 'revoked' ? sum : sum + cents(flow.amount), 0n));
  return <BusinessModal open={!blocked} layout="pane" className="project-dialog notice-dialog notice-flows-dialog" titleId="notice-flows-title" requestClose={closing.requestClose}><DialogContents title={`${notice.bill_no}，付款流水`} titleId="notice-flows-title" closing={closing}>
    <dl className="notice-flow-summary">
      <div><dt>项目</dt><dd>{notice.project_display || '—'}</dd></div>
      <div><dt>收款单位</dt><dd>{notice.payee || '—'}</dd></div>
      <div><dt>审批金额</dt><dd className="money">{money(notice.amount_approved)} 元</dd></div>
      <div><dt>已付金额</dt><dd className="money">{money(notice.amount_paid)} 元</dd></div>
    </dl>
    {query.isPending ? <p role="status">正在读取付款流水…</p> : query.isError ? <p className="notice" role="alert">{query.error.message}<Button htmlType="button" onClick={() => void query.refetch()}>重试读取</Button></p> : !rows.length ? <p role="status">暂无付款流水。</p> : <BoundedGrid<FlowGridRow> fill minRows={4} scale={scale} table="notice-flows" className="notice-flows-table" label="付款流水明细"
      rows={rows} totals={[{ flow_no: '实付合计', amount: paid }]} rowId={flow=>String(flow.id ?? 'total')} columns={[
      {field:'flow_no',headerName:'流水号'},
      {field:'status_label',headerName:'状态',cellRenderer:({data:flow}:{data:FlowGridRow})=>flow.status &&
        <span className={'status-tag '+(flow.status==='revoked'?'status-neutral':'status-positive')}>{flow.status_label}</span>},
      {field:'pay_date',headerName:'付款日期'},
      {field:'amount',headerName:'付款金额（元）',...numberColumnWidth([...rows.map(row=>money(row.amount)), money(paid)], scale),cellClass:'money',valueFormatter:p=>money(p.value)},
      {field:'pay_method',headerName:'付款方式',cellRenderer:({value}:{value?:string})=>value && <EnumTag kind="payMethod" value={value}/>},
      {field:'remark',headerName:'备注',valueFormatter:p=>p.node?.rowPinned?'':p.value||'—'},
      {field:'created_by',headerName:'登记人',valueFormatter:p=>p.node?.rowPinned?'':p.value||'—'},
      {field:'revoke_reason',headerName:'撤销原因',valueFormatter:p=>p.node?.rowPinned?'':p.value||'—'},
    ]}/>}
    <div className="dialog-actions">
      <Link to={`/ledger?notice=${notice.notice_id}`} onClick={closing.requestClose}>前往付款流水</Link>
      <Button htmlType="button" onClick={closing.requestClose}>关闭</Button>
    </div>
  </DialogContents></BusinessModal>;
}
