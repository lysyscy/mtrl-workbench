import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import Button from 'antd/es/button';
import { ReadGrid } from './business-grid';
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
        <ReadGrid table="i8-latest" className="i8-latest" label="各来源最近结果" domLayout="autoHeight" rows={(Object.keys(sourceNames) as (keyof typeof sourceNames)[]).map(source=>({source,row:(records.data??[]).find(item=>recordSource(item)===source)}))} rowId={item=>item.source} columns={[
          {colId:'source',headerName:'来源',valueGetter:p=>sourceNames[p.data!.source]},
          {colId:'scope',headerName:'范围',valueGetter:p=>p.data!.row?recordScope(p.data!.row):'—'},
          {colId:'result',headerName:'最近结果',cellRenderer:({data}:{data:{row:RunRecord|undefined}})=>data.row?<Status row={data.row}/>:'最近 '+limit+' 条中暂无记录'},
          {colId:'time',headerName:'开始时间',valueGetter:p=>p.data!.row?when(p.data!.row.started_at):'—'},
        ]}/>
        <details className="i8-history" open>
          <summary>执行记录</summary>
          <div className="i8-record-tools"><label>读取范围<Select aria-label="读取范围" value={limit} onChange={setLimit} options={[50,100,200].map(value=>({value,label:`最近 ${value} 条`}))}/></label><label>动作<Select aria-label="动作" value={type} onChange={setType} options={[['all','全部'],['fetch','抓取'],['sync','同步'],['print','打印'],['export_pdf','导出 PDF']].map(([value,label])=>({value,label}))}/></label>{records.isFetching && <span role="status">正在更新记录…</span>}</div>
          {visible.length === 0 ? <p className="state">{(records.data ?? []).length === 0 ? '还没有执行记录。完成抓取、同步或打印后可在这里核对。' : '当前读取范围内没有这类执行记录。'}</p> : <ReadGrid table="i8-records" className="i8-records" label="执行记录列表" domLayout="normal" style={{height:'min(60dvh,600px)'}} rows={visible} rowId={row=>String(row.id)} columns={[
            {field:'started_at',headerName:'开始时间',valueFormatter:p=>when(p.value)},
            {colId:'action',headerName:'动作',valueGetter:p=>recordLabel(p.data!)},
            {field:'target',headerName:'范围 / 对象'},
            {field:'triggered_by',headerName:'操作人',valueFormatter:p=>p.value==='manual'?'未记录（旧记录）':p.value},
            {colId:'result',headerName:'结果',cellRenderer:({data:row}:{data:RunRecord})=><><Status row={row}/>{row.error_message&&<details className="i8-error"><summary>查看原因</summary><pre>{row.error_message}</pre></details>}</>},
            {colId:'duration',headerName:'耗时',valueGetter:p=>duration(p.data!)},
          ]}/>}
        </details>
      </>}
    </div>
  </section>;
}
