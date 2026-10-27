import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import Button from 'antd/es/button';
import { BoundedTable } from './bounded-table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { requestJson } from './api';
import { duration, readRecords, recordLabel, recordScope, recordSource, sourceNames } from './i8-api';
import type { RunRecord } from './i8-api';

function Status({ row }: { row: RunRecord }) {
  const unit = row.run_type === 'print' || row.run_type === 'export_pdf' ? '张' : '条';
  const text = ({ success: `成功 ${row.success_count} ${unit}`, failed: '失败', partial: `部分成功 ${row.success_count} / ${row.success_count + row.fail_count} ${unit}`, running: '执行中' } as Record<string, string>)[row.status] ?? `其他状态：${row.status}`;
  const tone = ['success', 'failed', 'partial', 'running'].includes(row.status) ? row.status : 'unknown';
  return <Tag className={`status-tag status-${tone==='success'?'positive':tone==='failed'?'negative':tone==='partial'||tone==='running'?'pending':'neutral'}`}>{text}</Tag>;
}
function ReadError({ message, retry, label }: { message: string; retry: () => void; label: string }) {
  return <div className="notice" role="alert"><span>{message}</span><Button htmlType="submit" onClick={retry}>{label}</Button></div>;
}
const when = (value: string) => value.replace('T', ' ');
export function I8Page({ blocked }: { blocked: boolean }) {
  const [limit, setLimit] = useState(50);
  const [type, setType] = useState('all');
  const records = useQuery({ queryKey: ['i8-records', limit], enabled: !blocked, queryFn: async ({ signal }) => readRecords(await requestJson(`/api/m02/fetch/records?limit=${limit}`, { signal })), refetchOnMount: 'always' });
  const visible = records.data?.filter(row => type === 'all' || row.run_type === type) ?? [];
  return <section data-page-chrome data-page-loading={records.isPending||undefined} className="i8-page" aria-labelledby="page-title">
    <div className="i8-block">
      <h2>抓取结果回显</h2>{records.isError && records.data && <ReadError message={`记录更新失败，保留上次结果。${records.error.message}`} retry={() => void records.refetch()} label="重读记录" />}
      {records.isPending ? <p role="status">正在读取执行记录…</p> : records.isError && !records.data ? <ReadError message={records.error.message} retry={() => void records.refetch()} label="重读记录" /> : <>
        <div className="table-scroll i8-latest" role="region" aria-label="各来源最近结果" tabIndex={0}><BoundedTable><thead><tr><th>来源</th><th>范围</th><th>最近结果</th><th>开始时间</th></tr></thead><tbody>{(Object.keys(sourceNames) as (keyof typeof sourceNames)[]).map(source => {
          const row = (records.data ?? []).find(item => recordSource(item) === source);
          return <tr key={source}><td>{sourceNames[source]}</td><td>{row ? recordScope(row) : '—'}</td><td>{row ? <Status row={row} /> : `最近 ${limit} 条中暂无记录`}</td><td>{row ? when(row.started_at) : '—'}</td></tr>;
        })}</tbody></BoundedTable></div>
        <details className="i8-history" open>
          <summary>执行记录</summary>
          <div className="i8-record-tools"><label>读取范围<Select aria-label="读取范围" value={limit} onChange={setLimit} options={[50,100,200].map(value=>({value,label:`最近 ${value} 条`}))}/></label><label>动作<Select aria-label="动作" value={type} onChange={setType} options={[['all','全部'],['fetch','抓取'],['sync','同步'],['print','打印'],['export_pdf','导出 PDF']].map(([value,label])=>({value,label}))}/></label>{records.isFetching && <span role="status">正在更新记录…</span>}</div>
          {visible.length === 0 ? <p className="state">{(records.data ?? []).length === 0 ? '还没有执行记录。完成抓取、同步或打印后可在这里核对。' : '当前读取范围内没有这类执行记录。'}</p> : <div className="table-scroll i8-records" role="region" aria-label="执行记录列表" tabIndex={0}><BoundedTable><thead><tr><th>开始时间</th><th>动作</th><th>范围 / 对象</th><th>操作人</th><th>结果</th><th>耗时</th></tr></thead><tbody>{visible.map(row => <tr key={row.id}>
            <td>{when(row.started_at)}</td><td>{recordLabel(row)}</td><td>{row.target}</td><td>{row.triggered_by === 'manual' ? '未记录（旧记录）' : row.triggered_by}</td><td><Status row={row} />{row.error_message && <details className="i8-error"><summary>查看原因</summary><pre>{row.error_message}</pre></details>}</td><td>{duration(row)}</td>
          </tr>)}</tbody></BoundedTable></div>}
        </details>
      </>}
    </div>
  </section>;
}
