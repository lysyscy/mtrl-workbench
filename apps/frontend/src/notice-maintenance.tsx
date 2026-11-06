import { BusinessDate } from './time-picker';
import { ProjectPicker } from './ledger-controls';
import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { ApiError, record, requestJson } from './api';
import type { Project } from './api';
import { body, categories, currentMonth, receipt } from './notices-api';
import type { NoticeRow } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';
import { SESSION_MODE_BROWSER, sessionPayload } from './i8-browser-relay';
import { useI8Session } from './i8-session';

export type Draft = { row_id: string; doc_date: string; bill_no: string; bill_name: string; biz_type: string; payee: string; category: string; amount_approved: string; stat_settle: string; stat_paid: string; ownership_id: string; approve_status: string };
export function manualDraft(row?: NoticeRow): Draft {
  return { row_id: row ? String(row.notice_id) : '', doc_date: row?.doc_date ?? `${currentMonth()}-01`, bill_no: row?.bill_no ?? '', bill_name: row?.bill_name ?? '', biz_type: row?.biz_type ?? '', payee: row?.payee ?? '', category: row?.category ?? 'material', amount_approved: row?.amount_approved ?? '0', stat_settle: row?.stat_settle ?? '0', stat_paid: row?.stat_paid ?? '0', ownership_id: row?.ownership_id ? String(row.ownership_id) : '', approve_status: row?.approve_status ?? '已批' };
}
export function DraftField({ draft, field, label, disabled, projects }: { draft: Draft; field: keyof Draft; label: string; disabled: boolean; projects: Project[] }) {
  const [value, setValue] = useState(draft[field]);
  const choose = (next: string) => { draft[field] = next; setValue(next); };
  if (field === 'ownership_id') return <ProjectPicker projects={projects.filter(p => p.project_type !== 'shell')} selected={value ? [Number(value)] : []} pick={ids => choose(String(ids[0] ?? ''))} label={`草稿${label}`} disabled={disabled} />;
  if (field === 'doc_date') return <BusinessDate label={`草稿${label}`} value={value} onChange={choose} disabled={disabled} />;
  const options = field === 'category' ? Object.entries(categories) : field === 'approve_status' ? [['已批','已批'],['未批','未批']] : null;
  return options ? <select aria-label={`草稿${label}`} defaultValue={draft[field]} disabled={disabled} onChange={e => { draft[field] = e.target.value; }}>{options.map(([v,t]) => <option key={v} value={v}>{t}</option>)}</select> : <input autoFocus={!draft.row_id && field === 'bill_no'} aria-label={`草稿${label}`} type="text" inputMode={['amount_approved','stat_settle','stat_paid'].includes(field) ? 'decimal' : undefined} defaultValue={draft[field]} disabled={disabled} onChange={e => { draft[field] = e.target.value; }} />;
}
export type NoticeDialogState = { kind: 'delete' | 'ownership'; row: NoticeRow } | { kind: 'link'; row: NoticeRow };

function strings(value: unknown): string[] { if (!Array.isArray(value) || !value.every(x => typeof x === 'string')) throw new ApiError('候选读取不完整，请重读。'); return value; }
function resultObject(value: unknown) { if (!record(value)) throw new ApiError('读取不完整，请重试。'); return value; }
interface NoticeDialogProps { state: Exclude<NoticeDialogState, {kind:'link'}>; projects: Project[]; blocked: boolean; close: () => void; refresh: () => Promise<unknown>; announce: (message: string) => void }
export function NoticeDialog({ state, projects, blocked, close, refresh, announce }: NoticeDialogProps) {
  const { row, kind } = state, lock = useRef(false);
  const [newName,setNewName] = useState(''), [forceWarehouse,setForceWarehouse] = useState(false), [warehouse,setWarehouse] = useState<{name:string;found:boolean;degraded:boolean;owners:string[];from_cache:boolean;cached_at:string;message:string}|null>(null);
  const [busy,setBusy] = useState(false), [done,setDone] = useState(false), [error,setError] = useState(''), [value,setValue] = useState(''), [keyword,setKeyword] = useState('');
  const query = useQuery({ queryKey: ['notice-maintenance',kind,row.notice_id,row.bill_no], enabled: !blocked, staleTime: 0, refetchOnMount: 'always', queryFn: async ({ signal }) => {
    const path = kind === 'delete' ? '/api/m03/actions/manual-delete-impact' : '/api/m01/ownership';
    const data = resultObject(await requestJson(path, { method: 'POST', signal, ...body(kind === 'ownership' ? { name_full: row.project_name, doc_name: row.bill_name } : { notice_id: row.notice_id }) }));
    if (kind === 'ownership' && (!Array.isArray(data.candidates) || !data.candidates.every(x => record(x) && typeof x.key === 'string' && typeof x.display === 'string'))) throw new ApiError('归属候选读取不完整，请重读。');
    if (kind === 'delete' && (typeof data.message !== 'string' || !Array.isArray(data.effects))) throw new ApiError('删除影响读取不完整，请重读。');
    return data;
  } });
  const data = query.data;
  const ownership = kind === 'ownership' && data ? data.candidates as { key: string; display: string; archived: boolean }[] : [];
  const initialValue = useRef('');
  const closing = useDialogClose({ busy, dirty: !done && (value !== initialValue.current || Boolean(newName || keyword || forceWarehouse)), close });
  const unavailable = blocked || busy || done || query.isFetching || !data;
  // 取数方式来自账号工作区的统一选择（「i8 接入」页）：查仓库名单也是一次 i8 取数，
  // 必须跟其它抓取入口一样带 `session_mode`，否则选了浏览器方式这里还是会去登录（可能顶号）。
  const session = useI8Session();
  const browserBlocked = session.mode === SESSION_MODE_BROWSER && !session.connected;
  const warehouseQueryTitle = session.mode === SESSION_MODE_BROWSER
    ? '本次只查名单，不建档：查询由你浏览器里已登录的 i8 标签发出，不登录、不顶号；连接不在时会直接停下。'
    : '查询可能重新登录 i8，并使该账号其他会话下线；此次只查名单，不建档。';
  async function write(path: string, payload: unknown) {
    if (blocked || busy || done || lock.current) return;
    lock.current = true; setBusy(true); setError(''); let saved = false;
    try {
      const response = await requestJson(path,{ method: 'POST', ...body(payload) }); saved = true; setDone(true);
      const message = receipt(response);
      announce(message); await refresh(); close();
    } catch (failure) { setError(`${saved ? '操作已保存，但读取尚待核对；请关闭后重读，勿重复保存。' : ''}${failure instanceof Error ? failure.message : '操作未完成，请重试。'}`); }
    finally { setBusy(false);lock.current = false; }
  }
  async function checkWarehouse() {
    if (blocked || busy || done || browserBlocked || !newName.trim() || lock.current) return;
    lock.current=true;setBusy(true);setError('');
    try {
      // ⚠️ 会话来源必须随请求走：`browser` 缺连会当场失败（⛔ 不退回登录、也不带强踢授权）；
      //    `http` 保持原有的强踢授权，与改动前一致。
      const payload=sessionPayload(session,{allow_kick:true},{warehouse_name:newName.trim()});
      const r=resultObject(await requestJson('/api/m03/notices/warehouse-check',{method:'POST',...body(payload)}));
      if(typeof r.found!=='boolean'||typeof r.degraded!=='boolean'||typeof r.message!=='string'||typeof r.from_cache!=='boolean'||typeof r.cached_at!=='string')throw new ApiError('仓库名单回执不完整，请重新查询。');
      setWarehouse({name:newName.trim(),found:r.found,degraded:r.degraded,owners:strings(r.owners),from_cache:r.from_cache,cached_at:r.cached_at,message:r.message});setForceWarehouse(false);
    }catch(failure){setError(failure instanceof Error?failure.message:'查询失败，请重试。');}
    finally{setBusy(false);lock.current=false;}
  }
  const warehouseReady=value!=='new'||warehouse?.name===newName.trim()&&(warehouse.found&&!warehouse.degraded||forceWarehouse);
  function submit() {
    if (unavailable) return;
    if (kind === 'delete') void write('/api/m03/actions/manual-delete',{ notice_id: row.notice_id });
    if (kind === 'ownership' && value && warehouseReady) void write('/api/m03/notices/ownership-assign',{ doc_name: row.bill_name, keyword, ...(value==='new'?{shell_id:data?.shell_id,new_small_name:newName.trim()}:{small_id:Number(value)}) });
  }
  const title = { delete: '删除手动通知书', link: '关联集采合同', ownership: '指定项目归属' }[kind];
  return <BusinessModal open={!blocked} className={`project-dialog notice-dialog`} titleId="notice-maintenance-title" requestClose={closing.requestClose}><DialogContents title={title} titleId="notice-maintenance-title" closing={closing}><form onSubmit={e => { e.preventDefault();submit(); }}><p>{row.bill_no}，{row.bill_name}，{kind === 'ownership' ? row.project_name : row.project_display}</p>
    {query.isPending && <p role="status">正在读取…</p>}{query.isError && <p className="notice" role="alert">{query.error.message}<Button htmlType="button" onClick={() => void query.refetch()}>重读候选</Button></p>}
    {kind === 'delete' && data && <><p className="danger">{receipt(data)}</p><dl>{[['项目',data.project_name],['单据日期',data.doc_date],['统计结算金额',data.stat_settle],['统计付款金额',data.stat_paid],['已付金额（流水）',data.amount_paid]].map(([label,number]) => <div key={String(label)}><dt>{String(label)}</dt><dd>{String(number)}</dd></div>)}</dl><ul>{(data.effects as string[]).map(effect => <li key={effect}>{effect.replace(/\*\*/g,'')}</li>)}</ul></>}
    {kind === 'ownership' && data && <><p>{String(data.reason)}。关键词须出现在单据名称里；补完档案后须重新抓取，不改本条既有关系。</p><label>归属小微<select value={value} disabled={busy || done} onChange={e => setValue(e.target.value)}><option value="">请选择</option>{ownership.map(p => <option key={p.key} value={projects.find(project => project.warehouse_name === p.key)?.id ?? ''}>{p.display}{p.archived ? '（归档）' : ''}</option>)}{Boolean(data.shell_id)&&<option value="new">新建具体小微</option>}</select></label>{value==='new'&&<><label>新小微仓库名<input value={newName} disabled={busy||done} onChange={e=>{setNewName(e.target.value);setWarehouse(null);setForceWarehouse(false);}} /></label><p>{warehouseQueryTitle}</p>{browserBlocked&&<p className="notice" role="alert">当前选的是「浏览器已有会话」，但浏览器连接不在。请到「i8 接入」页重新连接，或把取数方式切回「工作台直连」。<strong>本次不会改用登录方式。</strong></p>}<Button htmlType="button" disabled={busy||done||browserBlocked||!newName.trim()} onClick={()=>void checkWarehouse()}>查询 i8 仓库名单</Button>{warehouse&&<div><p>{warehouse.degraded?'未取到名单，不等于名单里没有。':warehouse.found?`名单中有该仓库，所属项目：${warehouse.owners.join('、')}`:'名单中没有该仓库；将来同步可能重复建档。'}</p>{warehouse.from_cache&&<p>使用上次名单：{warehouse.cached_at||'时间未知'}</p>}{warehouse.found&&!warehouse.owners.includes(row.project_name)&&<p className="danger">该仓库所属项目与本条壳全名不一致，请核对。</p>}<p>{warehouse.message.replace(/<[^>]*>/g,'').replace(/\*\*/g,'')}</p>{(!warehouse.found||warehouse.degraded)&&<label className="notice-choice"><input type="checkbox" disabled={busy||done} checked={forceWarehouse} onChange={e=>setForceWarehouse(e.target.checked)} />已了解上述结果，仍按此名建档</label>}</div>}</>}<label>关键词<input value={keyword} disabled={busy || done} onChange={e => setKeyword(e.target.value)} /></label><Link to={`/projects?notice=${row.notice_id}&bill=${encodeURIComponent(row.bill_no)}`}>到项目档案核对 {row.bill_no}</Link></>}
    {error && <p className="notice" role="alert">{error}</p>}<div className="dialog-actions"><Button htmlType="button" disabled={busy} onClick={closing.requestClose}>{done ? '关闭' : '取消'}</Button>{!done && <Button htmlType="submit" className={kind === 'delete' ? 'danger' : 'primary'} disabled={unavailable || (kind === 'ownership' && !value) || (kind === 'ownership' && (!keyword||!warehouseReady||value==='new'&&!newName.trim()))}>{kind === 'delete' ? '确认删除' : '确认补充档案'}</Button>}</div>
  </form></DialogContents></BusinessModal>;
}

export function OwnershipPending({ blocked, disabled = blocked, open }: { blocked: boolean; disabled?: boolean; open: (row: NoticeRow) => void }) {
  const query=useQuery({queryKey:['notice-ownership-pending'],enabled:!blocked,refetchOnMount:'always',queryFn:async({signal})=>{
    const r=resultObject(await requestJson('/api/m03/notices/unresolved',{signal}));
    if(!Array.isArray(r.items)||!r.items.every(x=>record(x)&&['bill_no','doc_name','project_name','reason'].every(k=>typeof x[k]==='string')))throw new ApiError('归属待办读取不完整，请重读。');
    return r.items as {bill_no:string;doc_name:string;project_name:string;reason:string}[];
  }});
  return query.isError ? <p className="notice" role="alert">{query.error.message}<Button htmlType="submit" onClick={()=>void query.refetch()}>重读归属待办</Button></p> : query.data?.length ? <details className="notice-ownership" open><summary>待指定归属，{query.data.length} 条（本次未写入）</summary>{query.data.map((r,i)=><p key={`${r.bill_no}:${i}`}>{r.bill_no}，{r.project_name}，{r.doc_name}，{r.reason}<Button htmlType="submit" disabled={disabled} onClick={()=>open({notice_id:0,bill_no:r.bill_no,bill_name:r.doc_name,project_name:r.project_name,project_display:r.project_name} as NoticeRow)}>指定归属</Button></p>)}</details> : null;
}
