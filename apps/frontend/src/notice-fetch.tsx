import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import type { Identity } from './api';
import { body, currentMonth } from './notices-api';
import { TimePicker } from './time-picker';
import { DialogContents, useDialogClose } from './dialog-close';
export function NoticeFetch({ me, blocked, close, refresh }: { me: Identity | null; blocked: boolean; close: () => void; refresh: () => Promise<void> }) {
  const [month, setMonth] = useState(currentMonth), [busy, setBusy] = useState(false), [done, setDone] = useState(false), [error, setError] = useState(''), [result, setResult] = useState('');
  const [ignored, setIgnored] = useState<{ bill_no: string; project_name: string; doc_name: string; reason: string }[]>([]);
  const dialog = useRef<HTMLDialogElement>(null), lock = useRef(false), mounted = useRef(true);
  useEffect(() => { mounted.current = true; dialog.current?.showModal(); return () => { mounted.current = false; }; }, []);
  useEffect(() => { if (blocked) dialog.current?.close(); else if (!dialog.current?.open) dialog.current?.showModal(); }, [blocked]);
  const config = useQuery({ queryKey: ['notice-fetch-config'], enabled: !blocked, staleTime: 0, refetchOnMount: 'always', queryFn: async ({ signal }) => {
    const value = await requestJson('/api/m02/config', { signal });
    if (!record(value) || typeof value.ready !== 'boolean' || typeof value.account !== 'string' || typeof value.i8_user !== 'string' || typeof value.message !== 'string') throw new ApiError('i8 绑定读取不完整，请重试。');
    return { ready: value.ready, account: value.account, i8_user: value.i8_user, message: value.message };
  } });
  const initialMonth = useRef(month);
  const closing = useDialogClose({ busy, dirty: !done && month !== initialMonth.current, close });
  const unavailable = blocked || busy || !me || config.isFetching || !config.data?.ready || config.data.account !== me.account;
  async function run() {
    if (unavailable || lock.current || !/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) return;
    lock.current = true; setBusy(true); setError('');
    let written = false;
    try {
      const value = await requestJson('/api/m03/notices/fetch', { method: 'POST', ...body({ year_month: month, allow_kick: true, expected_account: me!.account }) });
      written = true; if (mounted.current) setDone(true);
      if (!record(value) || typeof value.fetched !== 'number' || typeof value.upserted !== 'number' || !Array.isArray(value.ignored) || !value.ignored.every(x => record(x) && ['bill_no','project_name','doc_name','reason'].every(k => typeof x[k] === 'string'))) throw new ApiError('抓取回执不完整，请到 i8 执行记录核对，勿重复抓取。');
      if (!mounted.current) return;
      setResult(`${value.year_month} 抓取 ${value.fetched} 条，写入 ${value.upserted} 条，本次忽略 ${value.ignored.length} 条。`); setIgnored(value.ignored); setDone(true);
      await refresh();
    } catch (failure) { if (mounted.current) setError(`${written ? '抓取已返回，列表或回执尚待核对。' : ''}${failure instanceof Error ? failure.message : '抓取未完成，请核对执行记录后重试。'}`); }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  return <dialog ref={dialog} className="project-dialog" aria-labelledby="notice-fetch-title" {...closing.dialogProps}><DialogContents titleId="notice-fetch-title" title="抓取 i8 付款通知书（按月）" closing={closing}><form onSubmit={e => { e.preventDefault(); void run(); }}>
    {config.isError ? <p className="notice" role="alert">{config.error.message}<button type="button" onClick={() => void config.refetch()}>重读绑定</button></p> : config.data ? <><p>当前账号：{me?.name || me?.account} · i8：{config.data.i8_user || '未绑定'}</p>{(!config.data.ready || config.data.account !== me?.account) && <p role="alert">{config.data.message || '账号已变化，请关闭后重新打开。'}</p>}</> : <p role="status">正在核对 i8 绑定…</p>}
    {!done && <><div className="time-picker-field"><span>抓取月份</span><TimePicker label="抓取月份" value={month} modes={['月']} disabled={busy || blocked} onChange={value => { setMonth(value); setError(''); }} /></div><p>按所选月份全量抓取，不受本页项目筛选限制。保留人工分类、已修改统计金额与集采实际供应商。</p><p>抓取会退出此 i8 账号的其他在线会话；失败不会自动重试。</p></>}
    {result && <p role="status">{result}</p>}{ignored.length > 0 && <><p>以下单据本次未写入；处理项目归属后须重新抓取。</p><ul>{ignored.map((x, i) => <li key={i}>{x.bill_no} · {x.project_name} · {x.doc_name} · {x.reason}</li>)}</ul></>}{error && <p className="notice" role="alert">{error}</p>}{busy && <p role="status">正在抓取，请稍候…</p>}<div className="dialog-actions"><button type="button" disabled={busy} onClick={closing.requestClose}>{done ? '关闭' : '取消'}</button>{!done && <button className="primary" disabled={unavailable || !month} type="submit">确认抓取</button>}</div>
  </form></DialogContents></dialog>;
}
