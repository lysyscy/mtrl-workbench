import Button from 'antd/es/button';
import { useQuery } from '@tanstack/react-query';
import { record, requestJson } from './api';
import { readFetchReceipt } from './i8-api';
import type { FetchReceipt, ReceiptSource } from './i8-api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { I8ReceiptSummary, receiptCount } from './i8-receipt-summary';
import { ReadFailure } from './read-region';

const titles: Record<ReceiptSource, string> = {
  notices: '付款通知书', settlement: '收发结存', inventory: '库存单据',
};

const text = (value: unknown) => typeof value === 'string' ? value : '';

export function I8FetchReceiptContents({ data, historical = false }: { data: FetchReceipt; historical?: boolean }) {
  const notice = data.source === 'notices';
  const count = (key: string) => receiptCount(data.summary[key]);
  const unsettled = count('unsettled');
  const unsettledLabel = notice ? '待指定归属' : '待指认仓库';
  const unit = notice ? '条' : '行';
  const counts = notice ? [
    { label: '新增', value: count('created') },
    { label: '实际变更', value: count('updated') },
  ] : [
    { label: '新增', value: count('inserted'), unit },
    { label: '刷新已有', value: count('updated'), unit },
    { label: '删除旧源行', value: count('deleted'), unit },
    data.source === 'settlement'
      ? { label: '保留手工行', value: count('kept_manual'), unit }
      : { label: '保留有调整的源行', value: count('kept_with_adjustment'), unit },
  ];
  return <>
    <I8ReceiptSummary {...data} groups={[
      { counts: [{ label: notice ? '抓取单据' : '读取明细', value: count('total'), unit }] },
      notice ? { counts: [{ label: '写入', value: count('written') }], breakdown: counts } : { counts },
      { counts: [
        { label: unsettledLabel, value: unsettled, unit: notice ? '条' : '个', attention: true },
        ...(notice ? [{ label: '标记剔除', value: count('excluded') }] : []),
      ], breakdown: notice ? [] : [
        { label: '自动扶正', value: count('promote') || null, unit: '个' },
        { label: '自动建档', value: count('create') || null, unit: '个' },
      ] },
    ]} />
    {data.error && <p className="notice" role="alert">{data.error}</p>}
    {data.warning && <p className="notice" role="alert">{data.warning.replaceAll('**', '')}</p>}
    {data.note && <p className="muted">{data.note.replaceAll('**', '')}</p>}
    {historical && data.status !== 'failed' && data.status !== 'empty' && count('written') === null && counts.every(item => item.value === null) &&
      <p className="muted">该批次未记录写入统计。</p>}
    {data.items && data.items.length > 0 && <section className="i8-receipt-section" aria-label={unsettledLabel}>
      <h3>{unsettledLabel}{unsettled !== null && unsettled > data.items.length ? `（已记录 ${data.items.length} 项）` : ''}</h3>
      {!historical && notice && <p>这些单据本次未写入。处理项目归属后重新抓取。</p>}
      <ul className="i8-receipt-list">{data.items.map((row, index) => <li key={index}>
        <div className="i8-receipt-row-heading">
          <strong>{text(row[notice ? 'bill_no' : 'warehouse_name']) || '编号或名称未记录'}</strong>
          {text(row.reason) && <span>{text(row.reason)}</span>}
        </div>
        <p>{text(row[notice ? 'project_name' : 'full_name']) || text(row.owner_full_name)}</p>
        {text(row.doc_name) && <p>{text(row.doc_name)}</p>}
      </li>)}</ul>
    </section>}
    {historical && data.status !== 'failed' && (data.items === null || (unsettled ?? 0) > 0 && !data.items.length) &&
      <p className="muted">该批次未记录待处理明细。</p>}
  </>;
}

export function I8FetchReceiptDialog({ source, runId, active, close }: {
  source: ReceiptSource; runId: number; active: boolean; close: () => void;
}) {
  const query = useQuery({
    queryKey: ['i8-fetch-receipt', source, runId], enabled: active,
    queryFn: async ({ signal }) => {
      const value = await requestJson(`/api/m02/fetch/records/${runId}/receipt`, { signal });
      if (record(value) && value.receipt === null) return null;
      return readFetchReceipt(record(value) ? value.receipt : null, source);
    },
  });
  const closing = useDialogClose({ busy: false, dirty: false, close, active });
  return <BusinessModal open={active} className="rules-dialog jc-receipt-dialog" titleId="i8-receipt-title" requestClose={closing.requestClose}>
    <DialogContents title={`${titles[source]}抓取明细`} titleId="i8-receipt-title" closing={closing}>
      {query.isFetching && <p role="status">正在读取抓取结果…</p>}
      {query.isError && <ReadFailure read={query} />}
      {query.data && <I8FetchReceiptContents data={query.data} historical />}
      {query.data === null && <p className="state">该批次未记录抓取明细。</p>}
      <div className="dialog-actions"><Button onClick={closing.requestClose}>关闭</Button></div>
    </DialogContents>
  </BusinessModal>;
}
