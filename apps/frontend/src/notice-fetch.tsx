import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import type { Identity } from './api';
import { body, currentMonth } from './notices-api';
import { TimePicker } from './time-picker';
import { DialogContents, useDialogClose } from './dialog-close';
import { SESSION_MODE_BROWSER, SESSION_MODE_HTTP, sessionPayload } from './i8-browser-relay';
import { useI8Session } from './i8-session';
export function NoticeFetch({ me, blocked, close, refresh }: { me: Identity | null; blocked: boolean; close: () => void; refresh: () => Promise<void> }) {
  const [month, setMonth] = useState(currentMonth), [busy, setBusy] = useState(false), [done, setDone] = useState(false), [error, setError] = useState(''), [result, setResult] = useState('');
  const [ignored, setIgnored] = useState<{ bill_no: string; project_name: string; doc_name: string; reason: string }[]>([]);
  // 会话来源来自**账号工作区**的统一选择（「i8 接入」页），不在每个弹窗里各选一套。
  // 缺省 = 直连（`http`）：与改动前**完全一致**，老路径不受这条通道影响。
  const session = useI8Session();
  const mode = session.mode;
  const lock = useRef(false), mounted = useRef(true);
  useEffect(() => { mounted.current = true;  return () => { mounted.current = false; }; }, []);
  const config = useQuery({ queryKey: ['notice-fetch-config'], enabled: !blocked, staleTime: 0, refetchOnMount: 'always', queryFn: async ({ signal }) => {
    const value = await requestJson('/api/m02/config', { signal });
    if (!record(value) || typeof value.ready !== 'boolean' || typeof value.account !== 'string' || typeof value.i8_user !== 'string' || typeof value.message !== 'string') throw new ApiError('i8 绑定读取不完整，请重试。');
    return { ready: value.ready, account: value.account, i8_user: value.i8_user, message: value.message };
  } });
  const initialMonth = useRef(month);
  const closing = useDialogClose({ busy, dirty: !done && month !== initialMonth.current, close });
  const browserBlocked = mode === SESSION_MODE_BROWSER && !session.connected;
  const unavailable = blocked || busy || !me || config.isFetching || !config.data?.ready || config.data.account !== me.account || browserBlocked;
  async function run() {
    if (unavailable || lock.current || !/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) return;
    lock.current = true; setBusy(true); setError('');
    let written = false;
    try {
      // ⚠️ `session_mode` 明确随请求走：`http` 保持产品原有直连与强踢授权；
      //    `browser` 复用浏览器里已登录的 i8 会话（**不登录、不顶号**）。
      //    ⛔ 选了 `browser` 但连接不在时后端会直接失败，不会悄悄退回登录。
      // 会话来源那几个字段统一由 `sessionPayload` 生成：`browser` 连接不在就当场失败，
      // `http` 原样保留既有强踢授权（`allow_kick`），两条路的业务字段完全一样。
      const payload = sessionPayload(session, { allow_kick: true }, { year_month: month, expected_account: me!.account });
      const value = await requestJson('/api/m03/notices/fetch', { method: 'POST', ...body(payload) });
      written = true; if (mounted.current) setDone(true);
      if (!record(value) || typeof value.fetched !== 'number' || typeof value.upserted !== 'number' || !Array.isArray(value.ignored) || !value.ignored.every(x => record(x) && ['bill_no','project_name','doc_name','reason'].every(k => typeof x[k] === 'string'))) throw new ApiError('抓取回执不完整，请到 i8 执行记录核对，勿重复抓取。');
      if (!mounted.current) return;
      setResult(`${value.year_month} 抓取 ${value.fetched} 条，写入 ${value.upserted} 条，本次忽略 ${value.ignored.length} 条。`); setIgnored(value.ignored); setDone(true);
    } catch (failure) { if (mounted.current) setError(`${written ? '抓取已返回，列表或回执尚待核对。' : ''}${failure instanceof Error ? failure.message : '抓取未完成，请核对执行记录后重试。'}`); }
    finally {
      try { await refresh(); }
      catch { if (mounted.current) setError(previous => `${previous}${previous ? ' ' : ''}列表、执行记录或归属待办更新失败，请关闭后重读核对，勿重复抓取。`); }
      finally { lock.current = false; if (mounted.current) setBusy(false); }
    }
  }
  return <BusinessModal open={!blocked} className="project-dialog notice-result-dialog" titleId="notice-fetch-title" requestClose={closing.requestClose}><DialogContents titleId="notice-fetch-title" title="抓取 i8 付款通知书（按月）" closing={closing}><form onSubmit={e => { e.preventDefault(); void run(); }}>
    {config.isError ? <p className="notice" role="alert">{config.error.message}<Button htmlType="button" onClick={() => void config.refetch()}>重读绑定</Button></p> : config.data ? <><p>当前账号：{me?.name || me?.account}，i8：{config.data.i8_user || '未绑定'}</p>{(!config.data.ready || config.data.account !== me?.account) && <p role="alert">{config.data.message || '账号已变化，请关闭后重新打开。'}</p>}</> : <p role="status">正在核对 i8 绑定…</p>}
    {!done && <><div className="time-picker-field"><span>抓取月份</span><TimePicker label="抓取月份" value={month} modes={['月']} disabled={busy || blocked} onChange={value => { setMonth(value); setError(''); }} /></div><p>按所选月份全量抓取，不受本页项目筛选限制。保留人工分类、已修改统计金额与集采实际供应商。</p>
      <div className="notice-fetch-mode">
        <span>会话来源</span>
        <strong>{mode === SESSION_MODE_BROWSER ? '浏览器已有会话' : '工作台直连'}</strong>
        <span className="muted">（在「i8 接入」页切换）</span>
      </div>
      {mode === SESSION_MODE_HTTP
        ? <p>抓取会退出此 i8 账号的其他在线会话；失败不会自动重试。</p>
        : <p>本次取数将由你浏览器里已登录的 i8 标签发出：不登录、不顶号、不把会话材料带出浏览器。连接失效时会明确停止，不会自动重新登录。</p>}
      {browserBlocked && <p className="notice" role="alert">当前选的是「浏览器已有会话」，但浏览器连接不在。请到「i8 接入」页重新连接，或把取数方式切回「工作台直连」。<strong>本次不会改用登录方式。</strong></p>}
    </>}
    {result && <p role="status">{result}</p>}{ignored.length > 0 && <><p>以下单据本次未写入；处理项目归属后须重新抓取。</p><ul className="notice-ignored-list">{ignored.map((x, i) => <li key={i}>{x.bill_no}，{x.project_name}，{x.doc_name}，{x.reason}</li>)}</ul></>}{error && <p className="notice" role="alert">{error}</p>}{busy && <p role="status">正在抓取，请稍候…</p>}<div className="dialog-actions"><Button htmlType="button" disabled={busy} onClick={closing.requestClose}>{done ? '关闭' : '取消'}</Button>{!done && <Button htmlType="submit" className="primary" disabled={unavailable || !month}>确认抓取</Button>}</div>
  </form></DialogContents></BusinessModal>;
}
