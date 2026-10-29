import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import Button from 'antd/es/button';
import { ReadGrid } from './business-grid';
import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, record, requestJson, uncertainWrite } from './api';
import type { Identity } from './api';
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
const servers = [
  {value: 'http://106.46.169.212:30785', label: '电信 · 106.46.169.212:30785'},
  {value: 'http://123.7.182.39:30785', label: '联通 · 123.7.182.39:30785'},
  {value: 'http://192.168.8.80:30785', label: '内网 · 192.168.8.80:30785'},
];
function readAddress(value: unknown) {
  const item = record(value) && Array.isArray(value.items) ? value.items.find((item: unknown) => record(item) && item.key === 'i8_base_url') : null;
  if (!record(item) || typeof item.effective !== 'string' || typeof item.version !== 'string') throw new ApiError('服务器配置读取不完整，请重读。');
  return {address: item.effective.replace(/\/+$/, ''), version: item.version};
}
function I8Server({blocked, me}: {blocked: boolean; me: Identity | null}) {
  const client = useQueryClient(), lock = useRef(false);
  const [selected, setSelected] = useState<string | null>(null), [saving, setSaving] = useState(false), [error, setError] = useState(''), [needsRead, setNeedsRead] = useState(false);
  const config = useQuery({queryKey: ['i8-server'], enabled: !blocked, retry: false, queryFn: async ({signal}) => readAddress(await requestJson('/api/m14/settings', {signal}))});
  const value = selected ?? config.data?.address;
  const options = value && !servers.some(item => item.value === value) ? [...servers, {value, label: value}] : servers;
  async function reread() { try { await config.refetch({throwOnError: true}); setNeedsRead(false); setError(''); } catch (failure) { setError(failure instanceof Error ? failure.message : '读取失败'); } }
  async function save() {
    if (blocked || !me || lock.current || needsRead || !config.data || !value || value === config.data.address) return;
    lock.current = true; setSaving(true); setError('');
    try {
      const query = new URLSearchParams({expected_account: me.account, expected_version: config.data.version});
      const result = readAddress(await requestJson('/api/m14/settings?' + query, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({i8_base_url: value})}));
      if (result.address !== value) throw new ApiError('服务器保存结果待核实，请重读配置。');
      client.setQueryData(['i8-server'], result); setSelected(null); await client.invalidateQueries({queryKey: ['i8-config']});
    } catch (failure) { setNeedsRead(uncertainWrite(failure) || failure instanceof ApiError && failure.status === 409); setError(failure instanceof Error ? failure.message : '保存失败，请重读配置。'); }
    finally { lock.current = false; setSaving(false); }
  }
  return <><div className="i8-server"><label>i8 服务器<Select<string> aria-label="i8 服务器" value={value ?? null} options={options} onChange={next => setSelected(next)} disabled={blocked || !me || saving || config.isFetching || needsRead} loading={config.isFetching}/></label><Button onClick={() => void save()} loading={saving} disabled={blocked || !me || !config.data || config.isFetching || needsRead || value === config.data.address}>保存</Button></div>{(error || config.isError) && <ReadError message={error || config.error?.message || '读取失败'} retry={() => void reread()} label="重读配置" />}</>;
}
export function I8Page({ blocked, me }: { blocked: boolean; me: Identity | null }) {
  const [limit, setLimit] = useState(50);
  const [type, setType] = useState('all');
  const records = useQuery({ queryKey: ['i8-records', limit], enabled: !blocked, queryFn: async ({ signal }) => readRecords(await requestJson(`/api/m02/fetch/records?limit=${limit}`, { signal })), refetchOnMount: 'always' });
  const visible = records.data?.filter(row => type === 'all' || row.run_type === type) ?? [];
  return <section data-page-chrome data-page-loading={records.isPending||undefined} className="i8-page" aria-labelledby="page-title">
    <div className="i8-block">
      <I8Server blocked={blocked} me={me}/>
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
