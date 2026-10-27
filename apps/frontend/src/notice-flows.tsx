import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { useQuery } from '@tanstack/react-query';
import { BoundedTable } from './bounded-table';
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
    {query.isPending ? <p role="status">正在读取付款流水…</p> : query.isError ? <p className="notice" role="alert">{query.error.message}<Button htmlType="submit" onClick={() => void query.refetch()}>重试读取</Button></p> : !query.data.length ? <p role="status">暂无付款流水。</p> : <div className="notice-flows-table"><BoundedTable>
      <thead><tr>{['流水号','状态','付款日期','付款金额（元）','付款方式','备注','登记人','撤销原因'].map(label => <th key={label}>{label}</th>)}</tr></thead>
      <tbody>{query.data.map(flow => <tr key={flow.id}><td>{flow.flow_no}</td><td><span className={`status-tag ${flow.status === 'revoked' ? 'status-neutral' : 'status-positive'}`}>{flow.status_label}</span></td><td>{flow.pay_date}</td><td className="money">{money(flow.amount)}</td><td><EnumTag kind="payMethod" value={flow.pay_method} /></td><td>{flow.remark || '—'}</td><td>{flow.created_by || '—'}</td><td>{flow.revoke_reason || '—'}</td></tr>)}</tbody>
    </BoundedTable></div>}
    <div className="dialog-actions"><Button htmlType="submit" onClick={closing.requestClose}>关闭</Button></div>
  </DialogContents></BusinessModal>;
}
