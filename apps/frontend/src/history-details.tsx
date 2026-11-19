import './history-details.css';
import Button from 'antd/es/button';
import { useId, useState } from 'react';
import { ApiError, record } from './api';

const initialRecords = 5;
type Change = { label: string; current: string | null; result: string | null };
type HistoryRecord = { type: string; name: string; area: string; context: string[]; fields: Change[]; removes: boolean };
export type HistoryDetails = { id: number; records: HistoryRecord[] };

function isText(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}
function isChange(value: unknown): value is Change {
  return record(value) && typeof value.label === 'string' && isText(value.current) && isText(value.result);
}
function isHistoryRecord(value: unknown): value is HistoryRecord {
  return record(value) && typeof value.type === 'string' && typeof value.name === 'string'
    && typeof value.area === 'string' && typeof value.removes === 'boolean'
    && Array.isArray(value.context) && value.context.every(text => typeof text === 'string')
    && Array.isArray(value.fields) && value.fields.every(isChange);
}

export function readHistoryDetails(value: unknown, expected: { id: number; count: number }): HistoryDetails {
  if (!record(value) || value.id !== expected.id || !Array.isArray(value.records)
      || value.records.length !== expected.count || !value.records.every(isHistoryRecord)) {
    throw new ApiError('变更详情未能核对，请重新打开操作。');
  }
  return { id: expected.id, records: value.records };
}

function show(value: string | null) {
  return value === null || value === '' ? '未填写' : value;
}
function countLabel(count: number, type?: string) {
  return type === '通知书' || type === '发票' ? `${count} 张${type}` : `${count} 条${type ?? '记录'}`;
}

function groupChanges(records: HistoryRecord[]) {
  const label = records[0]?.fields[0]?.label;
  if (records.length < 2 || !label || !records.every(item => item.fields.length === 1 && item.fields[0]?.label === label)) return [];
  const counts = new Map<string, { current: string | null; result: string | null; count: number }>();
  for (const { fields: [change] } of records) {
    const { current, result } = change!;
    const key = JSON.stringify([current, result]);
    const previous = counts.get(key);
    counts.set(key, { current, result, count: (previous?.count ?? 0) + 1 });
  }
  return counts.size <= 4 ? [...counts.values()] : [];
}

function ObjectIdentity({ item, showType = false }: { item: HistoryRecord; showType?: boolean }) {
  return <div className="history-details-identity">
    <strong>{showType && !item.name.startsWith(item.type) ? `${item.type} ` : ''}{item.name}</strong>
    {item.context.map(value => <span key={value}>{value}</span>)}
  </div>;
}

export function HistoryDetailsBody({ records }: { records: HistoryRecord[] }) {
  const [expanded, setExpanded] = useState(false);
  const rowsId = useId();
  const batch = records.length > 1;
  const single = records[0];
  const type = records.every(item => item.type === single?.type) ? single?.type : undefined;
  const area = records.every(item => item.area === single?.area) ? single?.area : '多个业务区域';
  const groups = groupChanges(records);
  const visible = batch && !expanded ? records.slice(0, initialRecords) : records;
  return <div className="history-details-body">
    <div className="history-details-scope"><strong>{area}</strong><span>{countLabel(records.length, type)}</span></div>
    {!batch && single && <div className="history-details-object"><ObjectIdentity item={single} /></div>}
    {batch && (groups.length > 0 || records.length > initialRecords) && <div className="history-details-summary">
      {groups.length > 0 && <ul aria-label="按变化汇总">
        {groups.map(({ current, result, count }, index) => <li key={index}>
          {show(current)} → {show(result)} <strong>{count} {type === '通知书' || type === '发票' ? '张' : '条'}</strong>
        </li>)}
      </ul>}
      {records.length > initialRecords && <Button type="link" aria-expanded={expanded} aria-controls={rowsId}
        onClick={() => setExpanded(value => !value)}>{expanded ? '收起部分明细' : `查看其余 ${countLabel(records.length - initialRecords, type)}`}</Button>}
    </div>}
    <table id={rowsId} className="history-details-table" aria-label="本次变更">
      <thead><tr>{batch && <th scope="col">{type ?? '业务对象'}</th>}
        <th scope="col">字段或范围</th><th scope="col">当前</th><th scope="col">执行后</th>
      </tr></thead>
      {visible.map((item, index) => <tbody key={index}>
        {item.fields.length === 0 ? <tr>
          {batch && <th scope="row"><ObjectIdentity item={item} showType={!type} /></th>}
          <td colSpan={3}>此记录暂无可显示的字段明细。</td>
        </tr> : item.fields.map((change, position) => <tr key={change.label}>
          {batch && position === 0 && <th scope="rowgroup" rowSpan={item.fields.length}>
            <ObjectIdentity item={item} showType={!type} />
          </th>}
          <th scope="row">{change.label}</th>
          <td>{show(change.current)}</td><td className="history-details-result">{show(change.result)}</td>
        </tr>)}
      </tbody>)}
    </table>
  </div>;
}
