export interface ReceiptCount {
  label: string;
  value: number | null;
  unit?: string;
  attention?: boolean;
}

interface ReceiptGroup {
  counts?: ReceiptCount[];
  breakdown?: ReceiptCount[];
}

const statusLabels: Record<string, string> = {
  success: '抓取完成', failed: '抓取失败', partial: '部分完成',
  running: '抓取进行中', empty: '本次无明细',
};

export function receiptCount(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function Counts({ counts, className }: { counts: ReceiptCount[]; className: string }) {
  if (!counts.length) return null;
  return <div className={className}>{counts.map(({ label, value, unit = '条', attention }) =>
    <span key={label} className={attention && value !== null && value > 0 ? 'i8-receipt-count is-attention' : 'i8-receipt-count'}>
      {label} <span className="i8-receipt-count-value"><b>{value}</b> {unit}</span>
    </span>
  )}</div>;
}

export function I8ReceiptSummary({ status, startedAt, scope, duration, groups }: {
  status: string; startedAt: string; scope: string; duration: number | null; groups: ReceiptGroup[];
}) {
  const visible = groups.map(({ counts = [], breakdown = [] }) => ({
    counts: counts.filter(item => item.value !== null),
    breakdown: breakdown.filter(item => item.value !== null),
  })).filter(group => group.counts.length || group.breakdown.length);
  return <div className="i8-receipt-summary" role="status">
    <div className="i8-receipt-meta">
      <strong>{statusLabels[status] ?? '状态未记录'}</strong>
      {startedAt && <time>{startedAt.replace('T', ' ')}</time>}
      <span>{scope || '范围未记录'}</span>
      {duration !== null && <span>耗时 {duration.toFixed(1)} 秒</span>}
    </div>
    {visible.length > 0 && <div className="i8-receipt-counts">{visible.map(group =>
      <div className="i8-receipt-count-group" key={(group.counts[0] ?? group.breakdown[0])?.label}>
        <Counts counts={group.counts} className="i8-receipt-count-row" />
        <Counts counts={group.breakdown} className="i8-receipt-count-breakdown" />
      </div>
    )}</div>}
  </div>;
}
