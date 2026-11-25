import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import Button from 'antd/es/button';
import Segmented from 'antd/es/segmented';
import { ReadGrid } from './business-grid';
import { BoundedGrid } from './bounded-grid';
import { ReadFailure, ReadPlaceholder, ReadStatusLane, readPhase } from './read-region';
import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router';
import { ApiError, record, requestJson, uncertainWrite } from './api';
import type { Identity } from './api';
import { duration, readRecords, recordLabel, recordScope, recordSource, sourceNames } from './i8-api';
import type { RunRecord } from './i8-api';
import type { SessionMode } from './i8-browser-relay';
import { useI8Session } from './i8-session';
import { JcFetchReceipt } from './jc-fetch-receipt';
import { I8FetchReceiptDialog } from './i8-fetch-receipt';
import type { ReceiptSource } from './i8-api';
import { DialogPresence } from './workspace-motion';

function receiptSource(row: RunRecord): ReceiptSource | 'contracts' | null {
  const source = recordSource(row);
  return source === 'notices' || source === 'settlement' || source === 'inventory' || source === 'contracts' ? source : null;
}

function Status({ row }: { row: RunRecord }) {
  const unit = row.run_type === 'print' || row.run_type === 'export_pdf' ? '张' : '条';
  const success = recordSource(row) === 'contracts' ? `完成（匹配 ${row.success_count} 条）` : `成功 ${row.success_count} ${unit}`;
  const text = ({ success, failed: '失败', partial: `部分成功 ${row.success_count} / ${row.success_count + row.fail_count} ${unit}`, running: '执行中' } as Record<string, string>)[row.status] ?? `其他状态：${row.status}`;
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
  const session = useI8Session();
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
      if (session.mode === 'browser' && session.maintaining) void session.connect(false);
    } catch (failure) { setNeedsRead(uncertainWrite(failure) || failure instanceof ApiError && failure.status === 409); setError(failure instanceof Error ? failure.message : '保存失败，请重读配置。'); }
    finally { lock.current = false; setSaving(false); }
  }
  return <><div className="i8-server"><label>i8 服务器<Select<string> aria-label="i8 服务器" value={value ?? null} options={options} onChange={next => setSelected(next)} disabled={blocked || !me || saving || config.isFetching || needsRead} loading={config.isFetching}/></label><Button onClick={() => void save()} loading={saving} disabled={blocked || !me || !config.data || config.isFetching || needsRead || value === config.data.address}>保存</Button></div>{(error || config.isError) && <ReadError message={error || config.error?.message || '读取失败'} retry={() => void reread()} label="重读配置" />}</>;
}
/**
 * 「i8 接入」：浏览器会话通道的连接区（`TAIL-476`）。
 *
 * 连接与各业务弹窗共用账号工作区的 I8SessionProvider。
 */
function I8BrowserRelay() {
  const session = useI8Session();
  const connected = session.connected;
  const state = session.state;
  const extensionReady = session.extensionReady;
  const modeOptions: { value: SessionMode; label: string }[] = [
    { value: 'http', label: '工作台直连' },
    { value: 'browser', label: '浏览器已有会话' },
  ];
  return <div className="i8-relay">
    <h2>i8 接入 · 浏览器会话</h2>
    <p className="i8-relay-note">
      工作台自动查找已授权站点的 i8 标签，复用浏览器当前登录态。
    </p>
    <div className="i8-relay-row">
      <label>取数方式
        <Segmented<SessionMode> aria-label="取数方式" value={session.mode} options={modeOptions}
          onChange={next => session.selectMode(next)} disabled={session.busy}/>
      </label>
    </div>
    <div className="i8-relay-row">
      <Tag className={`status-tag status-${connected ? 'positive' : session.maintaining ? 'pending' : 'neutral'}`}>{connected ? '已连接' : session.maintaining ? '正在连接' : '未连接'}</Tag>
      {connected && state?.origin ? <span className="i8-relay-origin">站点 {state.origin}</span> : ''}
      {connected && state?.i8_user ? <span className="i8-relay-origin">绑定账号 {state.i8_user}</span> : ''}
      {connected && (state?.expected_org_name || state?.expected_org_code)
        ? <span className="i8-relay-origin">取数组织 {state.expected_org_name}{state.expected_org_code ? `（${state.expected_org_code}）` : ''}</span>
        : ''}
      {session.maintaining
        ? <Button onClick={() => void session.disconnect()}>{connected ? '断开' : '停止连接'}</Button>
        : <Button htmlType="button" onClick={() => void session.connect()} loading={session.busy} disabled={!extensionReady}>连接浏览器会话</Button>}
    </div>
    {session.mode === 'browser' && session.connectionCode === 'permission-required' &&
      <Button htmlType="button" onClick={() => void session.requestPermission()}>授权 i8 站点</Button>}
    {!extensionReady && !connected && <p className="i8-relay-note">没检测到浏览器扩展：请按安装说明装好「工作台 i8 会话桥」（装一次即可，扩展 ID 是固定的），刷新本页后再点连接。</p>}
    {session.maintaining && <p className="i8-relay-note">短暂断网后会自动恢复连接。请在 i8 标签页处理登录，已发出的抓取可在执行记录中核对。</p>}
    {session.notice && <p role="status" className="i8-relay-note">{session.notice}</p>}
  </div>;
}
export function I8Page({ blocked, me }: { blocked: boolean; me: Identity | null }) {
  const [limit, setLimit] = useState(50);
  const [type, setType] = useState('all');
  const [receipt, setReceipt] = useState<{ id: number; source: ReceiptSource | 'contracts' } | null>(null);
  const historySection = useRef<HTMLDetailsElement>(null);
  const { hash, key } = useLocation();
  const records = useQuery({ queryKey: ['i8-records', limit], enabled: !blocked && !!me, queryFn: async ({ signal }) => readRecords(await requestJson(`/api/m02/fetch/records?limit=${limit}`, { signal })), refetchOnMount: 'always' });
  const visible = records.data?.filter(row => type === 'all' || row.run_type === type) ?? [];
  const readState = readPhase(records, (records.data?.length ?? 0) === 0);
  const placeheld = readState === 'idle' || readState === 'reading' || readState === 'error';
  useEffect(() => {
    if (blocked || placeheld || hash !== '#execution-records') return;
    const frame = requestAnimationFrame(() => {
      const section = historySection.current;
      if (!section) return;
      section.open = true;
      section.scrollIntoView({ block: 'start' });
    });
    return () => cancelAnimationFrame(frame);
  }, [blocked, hash, key, placeheld]);
  return <section data-page-chrome className="i8-page page-shell page-shell--flow" data-page-layout="flow" aria-labelledby="page-title">
    <div className="i8-block">
      <I8Server blocked={blocked} me={me}/>
      <I8BrowserRelay/>
      <h2>抓取结果回显</h2>
      <ReadStatusLane phase={readState} announce="正在读取执行记录…" className="i8-read-status">
        {(readState === 'error' || readState === 'stale') && <ReadFailure read={records} retained="执行记录更新失败，保留上次结果。"/>}
      </ReadStatusLane>
      {placeheld
        ? <div className="i8-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={6} quiet={readState === 'error'}/></div>
        : <>
        <ReadGrid table="i8-latest" className="i8-latest" label="各来源最近结果" domLayout="autoHeight" rows={(Object.keys(sourceNames) as (keyof typeof sourceNames)[]).map(source=>({source,row:(records.data??[]).find(item=>recordSource(item)===source)}))} rowId={item=>item.source} columns={[
          {colId:'source',headerName:'来源',valueGetter:p=>sourceNames[p.data!.source]},
          {colId:'scope',headerName:'范围',valueGetter:p=>p.data!.row?recordScope(p.data!.row):'—'},
          {colId:'result',headerName:'最近结果',cellRenderer:({data}:{data:{row:RunRecord|undefined}})=>data.row?<Status row={data.row}/>:'最近 '+limit+' 条中暂无记录'},
          {colId:'time',headerName:'开始时间',valueGetter:p=>p.data!.row?when(p.data!.row.started_at):'—'},
        ]}/>
        <details id="execution-records" ref={historySection} className="i8-history" open>
          <summary>执行记录</summary>
          <div className="i8-record-tools"><label>读取范围<Select aria-label="读取范围" value={limit} onChange={setLimit} options={[50,100,200].map(value=>({value,label:`最近 ${value} 条`}))}/></label><label>动作<Select aria-label="动作" value={type} onChange={setType} options={[['all','全部'],['fetch','抓取'],['sync','同步'],['print','打印'],['export_pdf','导出 PDF']].map(([value,label])=>({value,label}))}/></label>{records.isFetching && <span role="status">正在更新记录…</span>}</div>
          {visible.length === 0
            ? <p className="state">{(records.data ?? []).length === 0 ? '还没有执行记录。完成抓取、同步或打印后可在这里核对。' : '当前读取范围内没有这类执行记录。'}</p>
            : <BoundedGrid maxHeight="min(55dvh, 600px)" minRows={4} table="i8-records" className="i8-records" label="执行记录列表" rows={visible} rowId={row=>String(row.id)} columns={[
            {field:'started_at',headerName:'开始时间',valueFormatter:p=>when(p.value)},
            {colId:'action',headerName:'动作',valueGetter:p=>recordLabel(p.data!)},
            {colId:'target',headerName:'范围 / 对象',valueGetter:p=>p.data && recordSource(p.data) === 'contracts' ? recordScope(p.data) : p.data?.target},
            {field:'triggered_by',headerName:'操作人',valueFormatter:p=>p.value==='manual'?'未记录（旧记录）':p.value},
            {colId:'result',headerName:'结果',cellRenderer:({data:row}:{data:RunRecord})=>{
              const source = receiptSource(row);
              return <>
              <Status row={row}/>
              {source && <Button size="small" onClick={() => setReceipt({ id: row.id, source })}>查看明细</Button>}
              {row.error_message && <details className="i8-error"><summary>查看原因</summary><pre>{row.error_message}</pre></details>}
              </>;
            }},
            {colId:'duration',headerName:'耗时',valueGetter:p=>duration(p.data!)},
          ]}/>}
        </details>
      </>}
    </div>
    <DialogPresence>{receipt && (receipt.source === 'contracts'
      ? <JcFetchReceipt active={!blocked} close={() => setReceipt(null)} runId={receipt.id} />
      : <I8FetchReceiptDialog active={!blocked} close={() => setReceipt(null)} runId={receipt.id} source={receipt.source} />)}</DialogPresence>
  </section>;
}
