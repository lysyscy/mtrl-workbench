import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { ApiError, record, requestJson } from './api';
import type { Project } from './api';
import { body, categories, currentMonth, money, receipt } from './notices-api';
import type { NoticeRow } from './notices-api';
import { ContractDialog } from './notice-contract';
import { DialogContents, useDialogClose } from './dialog-close';

export type Draft = { row_id: string; doc_date: string; bill_no: string; bill_name: string; biz_type: string; payee: string; category: string; amount_approved: string; stat_settle: string; stat_paid: string; ownership_id: string; approve_status: string };
export function manualDraft(row?: NoticeRow): Draft {
  return { row_id: row ? String(row.notice_id) : '', doc_date: row?.doc_date ?? `${currentMonth()}-01`, bill_no: row?.bill_no ?? '', bill_name: row?.bill_name ?? '', biz_type: row?.biz_type ?? '', payee: row?.payee ?? '', category: row?.category ?? 'material', amount_approved: row?.amount_approved ?? '0', stat_settle: row?.stat_settle ?? '0', stat_paid: row?.stat_paid ?? '0', ownership_id: row?.ownership_id ? String(row.ownership_id) : '', approve_status: row?.approve_status ?? '已批' };
}
export function DraftField({ draft, field, label, disabled, projects }: { draft: Draft; field: keyof Draft; label: string; disabled: boolean; projects: Project[] }) {
  const options = field === 'category' ? Object.entries(categories) : field === 'approve_status' ? [['已批','已批'],['未批','未批']] : field === 'ownership_id' ? [['','请选择项目'],...projects.filter(p => p.project_type !== 'shell').map(p => [String(p.id),`${p.disp || p.warehouse_name}${p.status === 'archived' ? '（归档）' : ''}`])] : null;
  return options ? <select aria-label={`草稿${label}`} defaultValue={draft[field]} disabled={disabled} onChange={e => { draft[field] = e.target.value; }}>{options.map(([v,t]) => <option key={v} value={v}>{t}</option>)}</select> : <input aria-label={`草稿${label}`} type={field === 'doc_date' ? 'date' : 'text'} inputMode={['amount_approved','stat_settle','stat_paid'].includes(field) ? 'decimal' : undefined} defaultValue={draft[field]} disabled={disabled} onChange={e => { draft[field] = e.target.value; }} />;
}
export function StatCell({ row, field, drafts, disabled, save }: { row: NoticeRow; field: 'amount_approved' | 'stat_settle' | 'stat_paid'; drafts: Record<string,string>; disabled: boolean; save: (path: string, payload: unknown) => Promise<boolean> }) {
  const draftKey = `${row.notice_id}:${field}`;
  const [value, setValue] = useState(drafts[draftKey] ?? row[field]); const dirty = useRef(draftKey in drafts), saving = useRef(false);
  useEffect(() => { if (!dirty.current) setValue(row[field]); }, [row[field]]);
  async function commit() {
    if (disabled || saving.current || !dirty.current) return;
    saving.current = true;
    const accepted = await save(field === 'amount_approved' ? '/api/m03/actions/manual-save' : '/api/m03/actions/stat', field === 'amount_approved' ? {...manualDraft(row),amount_approved:value} : { notice_id: row.notice_id, field, value });
    if (accepted) {dirty.current = false;delete drafts[draftKey];}
    saving.current = false;
  }
  return <input className={row.edited_fields.includes(field) ? 'notice-edited' : ''} aria-label={`${row.bill_no}${field === 'amount_approved' ? '审批金额' : field === 'stat_settle' ? '统计结算金额' : '统计付款金额'}`} title={`${dirty.current ? '尚未保存 · ' : ''}${field === 'amount_approved' ? '手动行审批金额；两个统计金额不得超过它' : `上限 = 审批金额 ${money(row.amount_approved)}`}；保存失败保留输入`} inputMode="decimal" value={value} disabled={disabled} onChange={e => { dirty.current = true;drafts[draftKey] = e.target.value; setValue(e.target.value); }} onBlur={() => void commit()} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); void commit(); } if (e.key === 'Escape') { dirty.current = false;delete drafts[draftKey];setValue(row[field]); } }} />;
}
export type NoticeDialogState = { kind: 'delete' | 'supplier' | 'match' | 'link' | 'ownership'; row: NoticeRow };

function strings(value: unknown): string[] { if (!Array.isArray(value) || !value.every(x => typeof x === 'string')) throw new ApiError('候选读取不完整，请重读。'); return value; }
function resultObject(value: unknown) { if (!record(value)) throw new ApiError('读取不完整，请重试。'); return value; }
interface NoticeDialogProps { state: NoticeDialogState; projects: Project[]; blocked: boolean; close: () => void; refresh: () => Promise<void>; announce: (message: string) => void }
export function NoticeDialog(props: NoticeDialogProps) {
  return props.state.kind === 'link' ? <ContractDialog row={props.state.row} blocked={props.blocked} close={props.close} refresh={props.refresh} announce={props.announce} /> : <MaintenanceDialog {...props} />;
}
function MaintenanceDialog({ state, projects, blocked, close, refresh, announce }: NoticeDialogProps) {
  const { row, kind } = state, dialog = useRef<HTMLDialogElement>(null), lock = useRef(false);
  const [newName,setNewName] = useState(''), [warehouseConsent,setWarehouseConsent] = useState(false), [forceWarehouse,setForceWarehouse] = useState(false), [warehouse,setWarehouse] = useState<{name:string;found:boolean;degraded:boolean;owners:string[];from_cache:boolean;cached_at:string;message:string}|null>(null);
  const [busy,setBusy] = useState(false), [done,setDone] = useState(false), [error,setError] = useState(''), [value,setValue] = useState(kind === 'supplier' ? row.jc_supplier : ''), [keyword,setKeyword] = useState('');
  useEffect(() => { if (blocked) dialog.current?.close(); else if (!dialog.current?.open) dialog.current?.showModal(); }, [blocked]);
  const query = useQuery({ queryKey: ['notice-maintenance',kind,row.notice_id,row.bill_no], enabled: !blocked, staleTime: 0, refetchOnMount: 'always', queryFn: async ({ signal }) => {
    const path = kind === 'delete' ? '/api/m03/actions/manual-delete-impact' : kind === 'supplier' || kind === 'match' ? '/api/m03/actions/sup-match' : '/api/m01/ownership';
    const data = resultObject(await requestJson(path, { method: 'POST', signal, ...body(kind === 'ownership' ? { name_full: row.project_name, doc_name: row.bill_name } : { notice_id: row.notice_id }) }));
    if (kind === 'supplier' || kind === 'match') { strings(data.pool); strings(data.cands); }
    if (kind === 'ownership' && (!Array.isArray(data.candidates) || !data.candidates.every(x => record(x) && typeof x.key === 'string' && typeof x.display === 'string'))) throw new ApiError('归属候选读取不完整，请重读。');
    if (kind === 'delete' && (typeof data.message !== 'string' || !Array.isArray(data.effects))) throw new ApiError('删除影响读取不完整，请重读。');
    return data;
  } });
  const data = query.data, pool = data && (kind === 'supplier' || kind === 'match') ? strings(data.pool) : [], cands = data && kind === 'match' ? strings(data.cands) : [];
  const ownership = kind === 'ownership' && data ? data.candidates as { key: string; display: string; archived: boolean }[] : [];
  const initialValue = useRef(kind === 'supplier' ? row.jc_supplier : '');
  const closing = useDialogClose({ busy, dirty: !done && (value !== initialValue.current || Boolean(newName || keyword || forceWarehouse || warehouseConsent)), close });
  const unavailable = blocked || busy || done || query.isFetching || (!data && kind !== 'supplier');
  useEffect(() => { if (kind === 'match' && data && Array.isArray(data.cands) && data.cands.length === 1 && value === initialValue.current) { initialValue.current = String(data.cands[0]); setValue(initialValue.current); } }, [data]);
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
    if (blocked || busy || done || !newName.trim() || !warehouseConsent || lock.current) return;
    lock.current=true;setBusy(true);setError('');
    try {
      const r=resultObject(await requestJson('/api/m03/notices/warehouse-check',{method:'POST',...body({warehouse_name:newName.trim(),allow_kick:true})}));
      if(typeof r.found!=='boolean'||typeof r.degraded!=='boolean'||typeof r.message!=='string'||typeof r.from_cache!=='boolean'||typeof r.cached_at!=='string')throw new ApiError('仓库名单回执不完整，请重新查询。');
      setWarehouse({name:newName.trim(),found:r.found,degraded:r.degraded,owners:strings(r.owners),from_cache:r.from_cache,cached_at:r.cached_at,message:r.message});setForceWarehouse(false);
    }catch(failure){setError(failure instanceof Error?failure.message:'查询失败，请重试。');}
    finally{setBusy(false);setWarehouseConsent(false);lock.current=false;}
  }
  const warehouseReady=value!=='new'||warehouse?.name===newName.trim()&&(warehouse.found&&!warehouse.degraded||forceWarehouse);
  function submit() {
    if (unavailable) return;
    if (kind === 'delete') void write('/api/m03/actions/manual-delete',{ notice_id: row.notice_id });
    if (kind === 'supplier' || kind === 'match') void write('/api/m03/actions/jc-supplier',{ notice_id: row.notice_id, supplier: value.trim() });
    if (kind === 'ownership' && value && warehouseReady) void write('/api/m03/notices/ownership-assign',{ doc_name: row.bill_name, keyword, ...(value==='new'?{shell_id:data?.shell_id,new_small_name:newName.trim()}:{small_id:Number(value)}) });
  }
  const title = { delete: '删除手动通知书', supplier: '集采实际供应商', match: '自动匹配供应商', link: '关联集采合同', ownership: '指定项目归属' }[kind];
  return <dialog className={`project-dialog notice-dialog`} ref={dialog} aria-labelledby="notice-maintenance-title" {...closing.dialogProps}><DialogContents title={title} titleId="notice-maintenance-title" closing={closing}><form onSubmit={e => { e.preventDefault();submit(); }}><p>{row.bill_no} · {row.bill_name} · {kind === 'ownership' ? row.project_name : row.project_display}</p>
    {query.isPending && <p role="status">正在读取…</p>}{query.isError && <p className="notice" role="alert">{query.error.message}<button type="button" onClick={() => void query.refetch()}>重读候选</button></p>}
    {kind === 'delete' && data && <><p className="danger">{receipt(data)}</p><dl>{[['项目',data.project_name],['单据日期',data.doc_date],['统计结算金额',data.stat_settle],['统计付款金额',data.stat_paid],['已付金额（流水）',data.amount_paid]].map(([label,number]) => <div key={String(label)}><dt>{String(label)}</dt><dd>{String(number)}</dd></div>)}</dl><ul>{(data.effects as string[]).map(effect => <li key={effect}>{effect.replace(/\*\*/g,'')}</li>)}</ul></>}
    {(kind === 'supplier' || kind === 'match') && <>{kind === 'match' && data && <><p>{String(data.level_name)} · 命中 {cands.length} 家{cands.length > 1 ? '，请选择，不自动取第一家。' : cands.length === 1 ? '，自动匹配 · 待确认，须人工采用。' : '，可手工指定。'}</p>{data.level === 4 && <p className="danger">仅2字片段命中，请核对供应商全名。</p>}{cands.map(name => <label className="notice-choice" key={name}><input type="radio" name="supplier-candidate" value={name} checked={value === name} disabled={busy} onChange={() => setValue(name)} />{name}</label>)}</>}<label>供应商名称<input autoFocus value={value} maxLength={128} disabled={busy || done} onChange={e => setValue(e.target.value)} /></label>{!pool.length && data && <p>本项目暂无集采合同供应商，可直接录入全名。</p>}{pool.filter(name => name.includes(value)).map(name => <button className="notice-pool" type="button" key={name} disabled={busy || done} onClick={() => setValue(name)}>{name}</button>)}</>}
    {kind === 'ownership' && data && <><p>{String(data.reason)}。关键词须出现在单据名称里；补完档案后须重新抓取，不改本条既有关系。</p><label>归属小微<select value={value} disabled={busy || done} onChange={e => setValue(e.target.value)}><option value="">请选择</option>{ownership.map(p => <option key={p.key} value={projects.find(project => project.warehouse_name === p.key)?.id ?? ''}>{p.display}{p.archived ? '（归档）' : ''}</option>)}{Boolean(data.shell_id)&&<option value="new">新建具体小微</option>}</select></label>{value==='new'&&<><label>新小微仓库名<input value={newName} disabled={busy||done} onChange={e=>{setNewName(e.target.value);setWarehouse(null);setForceWarehouse(false);setWarehouseConsent(false);}} /></label><button type="button" disabled={busy||done||!newName.trim()} onClick={()=>setWarehouseConsent(true)}>查询 i8 仓库名单…</button>{warehouseConsent&&<div><p className="danger">会登录 i8，可能顶掉该账号的在线会话；此次只查名单，不建档。</p><button type="button" disabled={busy||done} onClick={()=>setWarehouseConsent(false)}>取消查询</button><button type="button" disabled={busy||done} onClick={()=>void checkWarehouse()}>确认查询（会顶号）</button></div>}{warehouse&&<div><p>{warehouse.degraded?'未取到名单，不等于名单里没有。':warehouse.found?`名单中有该仓库，所属项目：${warehouse.owners.join('、')}`:'名单中没有该仓库；将来同步可能重复建档。'}</p>{warehouse.from_cache&&<p>使用上次名单：{warehouse.cached_at||'时间未知'}</p>}{warehouse.found&&!warehouse.owners.includes(row.project_name)&&<p className="danger">该仓库所属项目与本条壳全名不一致，请核对。</p>}<p>{warehouse.message.replace(/<[^>]*>/g,'').replace(/\*\*/g,'')}</p>{(!warehouse.found||warehouse.degraded)&&<label className="notice-choice"><input type="checkbox" disabled={busy||done} checked={forceWarehouse} onChange={e=>setForceWarehouse(e.target.checked)} />已了解上述结果，仍按此名建档</label>}</div>}</>}<label>关键词<input value={keyword} disabled={busy || done} onChange={e => setKeyword(e.target.value)} /></label><Link to={`/projects?notice=${row.notice_id}&bill=${encodeURIComponent(row.bill_no)}`} onClick={() => dialog.current?.close()}>到项目档案核对 {row.bill_no}</Link></>}
    {error && <p className="notice" role="alert">{error}</p>}{busy && <p role="status">正在保存…</p>}<div className="dialog-actions"><button type="button" disabled={busy} onClick={closing.requestClose}>{done ? '关闭' : '取消'}</button>{!done && <button type="submit" className={kind === 'delete' ? 'danger' : 'primary'} disabled={unavailable || (['match','link','ownership'].includes(kind) && !value) || (kind === 'ownership' && (!keyword||!warehouseReady||value==='new'&&!newName.trim()))}>{kind === 'delete' ? '确认删除' : kind === 'match' ? '采用' : kind === 'link' ? '确认关联' : kind === 'ownership' ? '确认补充档案' : '保存'}</button>}</div>
  </form></DialogContents></dialog>;
}

export function OwnershipPending({ blocked, open }: { blocked: boolean; open: (row: NoticeRow) => void }) {
  const query=useQuery({queryKey:['notice-ownership-pending'],enabled:!blocked,refetchOnMount:'always',queryFn:async({signal})=>{
    const r=resultObject(await requestJson('/api/m03/notices/unresolved',{signal}));
    if(!Array.isArray(r.items)||!r.items.every(x=>record(x)&&['bill_no','doc_name','project_name','reason'].every(k=>typeof x[k]==='string')))throw new ApiError('归属待办读取不完整，请重读。');
    return r.items as {bill_no:string;doc_name:string;project_name:string;reason:string}[];
  }});
  return query.isError ? <p className="notice" role="alert">{query.error.message}<button onClick={()=>void query.refetch()}>重读归属待办</button></p> : query.data?.length ? <details className="notice-ownership" open><summary>待指定归属 · {query.data.length} 条（本次未写入）</summary>{query.data.map((r,i)=><p key={`${r.bill_no}:${i}`}>{r.bill_no} · {r.project_name} · {r.doc_name} · {r.reason}<button disabled={blocked} onClick={()=>open({notice_id:0,bill_no:r.bill_no,bill_name:r.doc_name,project_name:r.project_name,project_display:r.project_name} as NoticeRow)}>指定归属</button></p>)}</details> : null;
}
