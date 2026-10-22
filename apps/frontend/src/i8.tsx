import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { Identity } from './api';
import { requestJson } from './api';
import { duration, readConfig, readPlan, readRecords, recordLabel, recordScope, recordSource, sourceNames } from './i8-api';
import type { RunRecord } from './i8-api';
import { actionLabel } from './i8-api';
import { useI8Execution } from './i8-execution';
import { I8AddressEditor } from './i8-settings';

function Status({ row }: { row: RunRecord }) {
  const unit = row.run_type === 'print' || row.run_type === 'export_pdf' ? '张' : '条';
  const text = ({ success: `成功 ${row.success_count} ${unit}`, failed: '失败', partial: `部分成功 ${row.success_count} / ${row.success_count + row.fail_count} ${unit}`, running: '执行中' } as Record<string, string>)[row.status] ?? `其他状态：${row.status}`;
  const tone = ['success', 'failed', 'partial', 'running'].includes(row.status) ? row.status : 'unknown';
  return <span className={`i8-status i8-${tone}`}>{text}</span>;
}
function ReadError({ message, retry, label }: { message: string; retry: () => void; label: string }) {
  return <div className="notice" role="alert"><span>{message}</span><button onClick={retry}>{label}</button></div>;
}
const when = (value: string) => value.replace('T', ' ');
export function I8Page({ me, blocked }: { me: Identity | null; blocked: boolean }) {
  const [month, setMonth] = useState(() => { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`; });
  const [limit, setLimit] = useState(50);
  const [type, setType] = useState('all');
  const [reviewed, setReviewed] = useState(false);
  const [editingAddress, setEditingAddress] = useState(false);
  const { execution, busy, prepare, dismiss, acknowledge } = useI8Execution();
  useEffect(() => { setReviewed(false); }, [execution?.startedAt]);
  const config = useQuery({ queryKey: ['i8-config', me?.id ?? 0], enabled: !blocked, queryFn: async ({ signal }) => readConfig(await requestJson('/api/m02/config', { signal }), me?.account ?? ''), refetchOnMount: 'always' });
  const plan = useQuery({ queryKey: ['i8-plan', month], enabled: !blocked && /^\d{4}-(0[1-9]|1[0-2])$/.test(month), queryFn: async ({ signal }) => readPlan(await requestJson(`/api/m02/fetch/plan?year_month=${encodeURIComponent(month)}`, { signal }), month) });
  const records = useQuery({ queryKey: ['i8-records', limit], enabled: !blocked, queryFn: async ({ signal }) => readRecords(await requestJson(`/api/m02/fetch/records?limit=${limit}`, { signal })), refetchOnMount: 'always' });
  const reason = !me ? '登录后才能抓取。' : config.isError ? 'i8 配置尚未核实，请先重读配置。' : !config.data ? '正在读取 i8 配置…' : !config.data.ready ? (config.data.message || 'i8 配置尚未就绪，请核对配置。') : busy ? '上一任务尚未结束或回执待核实。' : !plan.data || plan.isError ? '请先核对有效的抓取月份及单据日期。' : '';
  const visible = records.data?.filter(row => type === 'all' || row.run_type === type) ?? [];
  return <section className="i8-page" aria-labelledby="i8-title">
    <div className="card-head"><h1 id="i8-title">i8 接入层</h1></div>
    <div className="i8-block">
      <h2>手动抓取付款通知书</h2>
      <form className="i8-manual" onSubmit={event => { event.preventDefault(); if (!reason && !blocked) prepare({ kind: 'notices', month }); }}>
        <label>抓取月份<input type="month" value={month} onChange={event => { dismiss(); setMonth(event.target.value); }} /></label>
        <button type="submit" className="primary" disabled={blocked || Boolean(reason)} title={reason || undefined}>准备抓取</button>
      </form>
      {plan.isError ? <ReadError message={plan.error.message} retry={() => void plan.refetch()} label="重新换算" /> : plan.data ? <p className="i8-period" role="status">单据日期 {plan.data.start_date} 至 {plan.data.end_date}（含首尾）</p> : <p className="i8-period" role="status">{month ? '正在换算单据日期…' : '请选择抓取月份。'}</p>}
      <p className="i8-note">刷新源数据，保留统计金额、人工分类、集采实际供应商及调整单。</p>
      {reason && (!config.data || config.data.ready) && <p className="i8-note">{reason}</p>}
      {execution && <div className={`i8-receipt i8-${execution.phase}`} role={execution.phase === 'failed' || execution.phase === 'uncertain' ? 'alert' : 'status'}>
        <strong>{actionLabel(execution.action)} · {({ pending: '执行中', success: '成功', partial: '部分成功', failed: '未完成', uncertain: '结果待核实' })[execution.phase]}</strong>
        <p>{execution.message}</p>
        <p className="muted">开始于 {new Date(execution.startedAt).toLocaleString('sv-SE', { hour12: false })}</p>
      </div>}
      {execution?.phase === 'uncertain' && <div className="i8-recovery">
        <button disabled={records.isFetching || blocked} onClick={() => void records.refetch()}>核对执行记录</button>
        <label><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />已核对记录，并确认没有仍在执行的任务</label>
        <button disabled={!reviewed || !records.isSuccess || records.isFetching || records.dataUpdatedAt < Date.parse(execution.startedAt) || blocked} onClick={() => { acknowledge(); setReviewed(false); }}>结束核对，允许重新准备</button>
      </div>}
    </div>
    <details className="i8-config" open>
      <summary>i8 配置</summary>
      {config.isPending ? <p role="status">正在读取配置…</p> : config.isError ? <ReadError message={config.error.message} retry={() => void config.refetch()} label="重读配置" /> : <>
        <dl><dt>服务地址</dt><dd>{config.data.base_url || '未配置'} <span className="muted">（{config.data.source === 'page' ? '界面所设' : '环境配置'}）</span></dd><dt>当前 i8 账号</dt><dd>{config.data.i8_user || '未绑定'}</dd></dl>
        {config.data.message && <p className="i8-note">{config.data.message}</p>}
        <button disabled={blocked || !me} title={!me ? '登录后才能修改。' : undefined} onClick={() => setEditingAddress(true)}>修改服务地址</button>
      </>}
    </details>
    {editingAddress && me && <I8AddressEditor me={me} blocked={blocked} onClose={() => setEditingAddress(false)} />}
    <div className="i8-block">
      <h2>最近结果</h2>
      {records.isPending ? <p role="status">正在读取执行记录…</p> : records.isError ? <ReadError message={records.error.message} retry={() => void records.refetch()} label="重读记录" /> : <>
        <div className="table-scroll i8-latest" role="region" aria-label="各来源最近结果" tabIndex={0}><table><thead><tr><th>来源</th><th>范围</th><th>最近结果</th><th>开始时间</th></tr></thead><tbody>{(Object.keys(sourceNames) as (keyof typeof sourceNames)[]).map(source => {
          const row = records.data.find(item => recordSource(item) === source);
          return <tr key={source}><td>{sourceNames[source]}</td><td>{row ? recordScope(row) : '—'}</td><td>{row ? <Status row={row} /> : `最近 ${limit} 条中暂无记录`}</td><td>{row ? when(row.started_at) : '—'}</td></tr>;
        })}</tbody></table></div>
        <details className="i8-history" open>
          <summary>执行记录</summary>
          <div className="i8-record-tools"><label>读取范围<select aria-label="读取范围" value={limit} onChange={event => setLimit(Number(event.target.value))}><option value={50}>最近 50 条</option><option value={100}>最近 100 条</option><option value={200}>最近 200 条</option></select></label><label>动作<select aria-label="动作" value={type} onChange={event => setType(event.target.value)}><option value="all">全部</option><option value="fetch">抓取</option><option value="sync">同步</option><option value="print">打印</option><option value="export_pdf">导出 PDF</option></select></label>{records.isFetching && <span role="status">正在更新记录…</span>}</div>
          {visible.length === 0 ? <p className="state">{records.data.length === 0 ? '还没有执行记录。完成抓取、同步或打印后可在这里核对。' : '当前读取范围内没有这类执行记录。'}</p> : <div className="table-scroll i8-records" role="region" aria-label="执行记录列表" tabIndex={0}><table><thead><tr><th>开始时间</th><th>动作</th><th>范围 / 对象</th><th>操作人</th><th>结果</th><th>耗时</th></tr></thead><tbody>{visible.map(row => <tr key={row.id}>
            <td>{when(row.started_at)}</td><td>{recordLabel(row)}</td><td>{row.target}</td><td>{row.triggered_by === 'manual' ? '未记录（旧记录）' : row.triggered_by}</td><td><Status row={row} />{row.error_message && <details className="i8-error"><summary>查看原因</summary><pre>{row.error_message}</pre></details>}</td><td>{duration(row)}</td>
          </tr>)}</tbody></table></div>}
        </details>
      </>}
    </div>
  </section>;
}
