import Button from 'antd/es/button';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import type { Identity } from './api';
import { body } from './notices-api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { TimePicker } from './time-picker';
import { readRecords, recordSource } from './i8-api';

export function InventoryFetch({month:initial,me,paused,close,refresh,pending,onPending}:{month:string;me:Identity|null;paused:boolean;close:()=>void;refresh:()=>Promise<void>;pending:boolean;onPending:(month:string|null)=>void}) {
  const [month,setMonth] = useState(initial), [busy,setBusy] = useState(false), [sent,setSent] = useState(pending), [error,setError] = useState(''), [result,setResult] = useState('');
  const writeAbort = useRef(new AbortController());
  useEffect(() => { writeAbort.current = new AbortController(); return () => writeAbort.current.abort(); }, []);
  const lock = useRef(false), closing = useDialogClose({busy,dirty:!sent && month !== initial,close,active:!paused});
  const config = useQuery({queryKey:['inventory-fetch-config'],enabled:!paused,staleTime:0,refetchOnMount:'always',queryFn:async({signal}) => {
    const value = await requestJson('/api/m02/config',{signal});
    if (!record(value) || typeof value.ready !== 'boolean' || !['account','i8_user','message'].every(k => typeof value[k] === 'string')) throw new ApiError('i8 绑定读取不完整，请重读。');
    return value as unknown as {ready:boolean;account:string;i8_user:string;message:string};
  }});
  const records = useQuery({queryKey:['inventory-fetch-records'],enabled:false,queryFn:async({signal}) => readRecords(await requestJson('/api/m02/fetch/records?limit=50',{signal}))});
  const [recordsVerified,setRecordsVerified] = useState(false);
  async function rereadRecords() {setRecordsVerified(false);const result = await records.refetch();if (!result.isError) setRecordsVerified(true);}
  const unavailable = paused || busy || sent || pending || !me || config.isFetching || config.isError || !config.data?.ready || config.data.account !== me.account || !/^\d{4}-(0[1-9]|1[0-2])$/.test(month);
  async function run() {
    if (unavailable || lock.current) return;
    lock.current = true;setBusy(true);setSent(true);setError('');onPending(month);let settled = false;
    try {
      const value = await requestJson('/api/m08/fetch',{method:'POST',signal:writeAbort.current.signal,...body({month,confirm:true})});
      if (writeAbort.current.signal.aborted) return;
      if (!record(value) || value.ok !== true || value.ym !== month || typeof value.rows !== 'number' || !record(value.stats) || !['inserted','updated','deleted','kept_with_adjustment'].every(k => typeof value.stats === 'object' && value.stats !== null && typeof (value.stats as Record<string,unknown>)[k] === 'number')) throw new ApiError('抓取回执不完整，请到执行记录核对，勿重复抓取。');
      const s = value.stats;
      settled = true;
      setResult(`${month} 抓取 ${value.rows} 行；插入 ${s.inserted}、更新 ${s.updated}、删除旧源行 ${s.deleted}、保留有调整的源行 ${s.kept_with_adjustment}。`);
      if (record(value.recovery) && typeof value.recovery.message === 'string') {const message = value.recovery.message;setResult(old => `${old} ${message}`);}
    } catch(e) {
      if (writeAbort.current.signal.aborted) return;
      if (e instanceof ApiError && e.status > 0 && e.status < 500 && e.code !== 'invalid_response') settled = true;
      setError(`${e instanceof Error ? e.message : '抓取未完成。'}请核对 i8 执行记录后再安排下一次抓取。`);
    }
    finally {if (!writeAbort.current.signal.aborted) try {await refresh();if (settled) onPending(null);} catch(e) {setError(old => `${old} 列表或执行记录重读失败：${e instanceof Error ? e.message : '请重读核对。'}`);} lock.current = false;setBusy(false);}
  }
  return <BusinessModal open={!paused} requestClose={closing.requestClose} className="inventory-dialog" titleId="inventory-fetch-title"><DialogContents title="按月抓取库存单据" titleId="inventory-fetch-title" closing={closing}>
    {config.isPending ? <p role="status">正在核对 i8 绑定…</p> : config.isError ? <p className="notice" role="alert">{config.error.message}<Button onClick={() => void config.refetch()}>重读绑定</Button></p> : <p>当前账号：{me?.name || me?.account} · i8：{config.data.i8_user || '未绑定'}</p>}
    {!sent && <><label className="inventory-fields">抓取月份<TimePicker label="库存抓取月份" value={month} modes={['月']} onChange={setMonth} disabled={busy || paused} /></label><p>全项目按核算月抓取，不受页面筛选限制；重抓保留调整单。</p><p className="inventory-warning">抓取会退出此 i8 账号的其他在线会话；失败不会自动重试。</p></>}
    {config.data && (!config.data.ready || config.data.account !== me?.account) && <p role="alert">{config.data.message || '账号已变化，请重新打开。'}</p>}
    {result && <p role="status">{result}</p>}{error && <p className="notice" role="alert">{error}</p>}{busy && <p role="status">正在抓取，请稍候…</p>}
    {pending && !busy && <div className="inventory-warning"><p>{initial} 的抓取结果待核实；核对执行记录并确认没有在途任务后再准备下一次。</p><Button disabled={paused || records.isFetching} onClick={() => void rereadRecords()}>读取执行记录</Button>
      {records.isError && <p role="alert">{records.error.message}</p>}{records.data && <><ul>{records.data.filter(r => recordSource(r) === 'inventory').map(r => <li key={r.id}>{r.started_at} · {r.target} · {r.status} · {r.error_message}</li>)}</ul><Button disabled={paused || !recordsVerified || records.isFetching || records.isError || records.data.some(r => recordSource(r) === 'inventory' && r.status === 'running')} onClick={() => {onPending(null);close();}}>已核对，无在途任务</Button></>}
    </div>}
    <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>{sent ? '关闭' : '取消'}</Button>{!sent && <Button type="primary" disabled={unavailable} onClick={() => void run()}>确认按 {month} 抓取</Button>}</div>
  </DialogContents></BusinessModal>;
}
