import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { useQuery } from '@tanstack/react-query';
import { ReadGrid } from './business-grid';
import { numberColumnWidth } from './grid';
import { DialogContents, useDialogClose } from './dialog-close';
import { EnumTag } from './enum-tag';
import { loadFlows } from './flow-api';
import { money } from './notices-api';
import type { NoticeRow } from './notices-api';

export function NoticeFlows({ notice, blocked, close }: { notice: NoticeRow; blocked: boolean; close: () => void }) {
  const closing = useDialogClose({ busy: false, dirty: false, close });
  const query = useQuery({ queryKey: ['notice-flows', notice.notice_id], enabled: !blocked, refetchOnWindowFocus: false,
    queryFn: async ({ signal }) => (await loadFlows(signal)).filter(flow => flow.notice_id === notice.notice_id) });
  return <BusinessModal open={!blocked} className="project-dialog notice-flows-dialog" titleId="notice-flows-title" requestClose={closing.requestClose}><DialogContents title={`${notice.bill_no}，付款流水`} titleId="notice-flows-title" closing={closing}>
    {query.isPending ? <p role="status">正在读取付款流水…</p> : query.isError ? <p className="notice" role="alert">{query.error.message}<Button htmlType="submit" onClick={() => void query.refetch()}>重试读取</Button></p> : !query.data.length ? <p role="status">暂无付款流水。</p> : <ReadGrid manualWidths table="notice-flows" className="notice-flows-table" label="付款流水明细" domLayout="autoHeight" rows={query.data} rowId={flow=>String(flow.id)} columns={[
      {field:'flow_no',headerName:'流水号'},
      {field:'status_label',headerName:'状态',cellRenderer:({data:flow}:{data:NonNullable<typeof query.data>[number]})=><span className={'status-tag '+(flow.status==='revoked'?'status-neutral':'status-positive')}>{flow.status_label}</span>},
      {field:'pay_date',headerName:'付款日期'},
      {field:'amount',headerName:'付款金额（元）',...numberColumnWidth(query.data.map(row=>money(row.amount))),cellClass:'money',valueFormatter:p=>money(p.value)},
      {field:'pay_method',headerName:'付款方式',cellRenderer:({value}:{value:string})=><EnumTag kind="payMethod" value={value}/>},
      {field:'remark',headerName:'备注',valueFormatter:p=>p.value||'—'}, {field:'created_by',headerName:'登记人',valueFormatter:p=>p.value||'—'}, {field:'revoke_reason',headerName:'撤销原因',valueFormatter:p=>p.value||'—'},
    ]}/>}
    <div className="dialog-actions"><Button htmlType="submit" onClick={closing.requestClose}>关闭</Button></div>
  </DialogContents></BusinessModal>;
}
