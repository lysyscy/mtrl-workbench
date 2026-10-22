import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, readProjects, record, requestJson } from './api';
import type { Identity, Project } from './api';
import './projects.css';

type ArchiveProject = Project & { parent_shell_id: number | null; match_keywords: string[]; is_placeholder: boolean };
type Candidate = { id: number; disp: string; warehouse_name: string; status: string; is_placeholder: boolean };
type Pending = { full_name: string; warehouse_name?: string; candidates?: Candidate[]; warehouses?: string[]; reason?: string };
type PendingList = { items: Pending[]; source: { at?: string; target?: string }; dropped_items?: { full_name: string; why_text: string }[] };
type Trail = { at: string; project: string; field_label: string; before: string; after: string; by: string };
type Impact = { can_delete: boolean; message: string; groups: { label: string; count: number; rows: Record<string, unknown>[] }[] };
type Connection = { account: string; i8_user: string; ready: boolean; message: string };
type DialogState = { kind: 'create' } | { kind: 'edit' | 'status' | 'keywords' | 'delete' | 'type'; project: ArchiveProject } | { kind: 'promote' | 'archive'; item: Pending } | { kind: 'sync'; source: 'warehouses' | 'common-projects' };
const typeNames = { normal: '普通项目', shell: '小微壳', small: '具体小微' };
const label = (p: Project) => p.disp || p.name_full;
const trailValue = (trail: Trail, value: string) => trail.field_label === '项目状态' ? ({ active: '在建', archived: '归档' } as Record<string, string>)[value] ?? value : trail.field_label === '项目类型' ? (typeNames as Record<string, string>)[value] ?? value : value;
const messageOf = (e: unknown) => e instanceof Error ? e.message : '操作未完成，请重试。';
const body = (value: unknown) => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });
function object<T>(value: unknown, check: (item: Record<string, unknown>) => boolean): T {
  if (!record(value) || !check(value)) throw new ApiError('读取结果不完整，请重试。');
  return value as T;
}
async function archiveProjects(signal: AbortSignal): Promise<ArchiveProject[]> {
  const raw = await requestJson('/api/m01/projects?status=all', { signal });
  const projects = readProjects(raw);
  return projects.map((project, i) => {
    const item = (raw as Record<string, unknown>[])[i]!;
    if ((item.parent_shell_id !== null && typeof item.parent_shell_id !== 'number') || !Array.isArray(item.match_keywords) || !item.match_keywords.every(x => typeof x === 'string') || typeof item.is_placeholder !== 'boolean') throw new ApiError('项目档案不完整，请重读。');
    return { ...project, parent_shell_id: item.parent_shell_id as number | null, match_keywords: item.match_keywords as string[], is_placeholder: item.is_placeholder };
  });
}
function OrderInput({ project, disabled, move }: { project: ArchiveProject; disabled: boolean; move: (id: number, position: number) => Promise<number | null> }) {
  const [position, setPosition] = useState(String(project.ord));
  useEffect(() => setPosition(String(project.ord)), [project.ord]);
  return <input type="number" min="1" step="1" aria-label={`排序：${label(project)}`} title="全局序号；归档项目排在最后" value={position} disabled={disabled} onChange={e => setPosition(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }} onBlur={() => { const n = Number(position); if (Number.isInteger(n) && n > 0 && n !== project.ord) void move(project.id, n).then(saved => { if (saved !== null) setPosition(String(saved)); }); else setPosition(String(project.ord)); }} />;
}
export function Projects({ me, blocked }: { me: Identity | null; blocked: boolean }) {
  const client = useQueryClient();
  const [params] = useSearchParams();
  const [sort, setSort] = useState<{ key: string; descending: boolean } | null>(null);
  const [status, setStatus] = useState('active'), [type, setType] = useState('all'), [keyword, setKeyword] = useState('');
  const [modal, setModal] = useState<DialogState | null>(null), [feedback, setFeedback] = useState(''), [busy, setBusy] = useState(false);
  const lock = useRef(false), mounted = useRef(true), dragging = useRef<number | null>(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const projects = useQuery({ queryKey: ['project-archive'], enabled: !blocked, queryFn: ({ signal }) => archiveProjects(signal) });
  const pending = useQuery({ queryKey: ['project-promote-pending'], enabled: !blocked, queryFn: async ({ signal }) => object<PendingList>(await requestJson('/api/m01/promote-pending', { signal }), x => Array.isArray(x.items) && record(x.source)) });
  const archive = useQuery({ queryKey: ['project-archive-pending'], enabled: !blocked, queryFn: async ({ signal }) => object<PendingList>(await requestJson('/api/m01/archive-pending', { signal }), x => Array.isArray(x.items) && record(x.source)) });
  const trails = useQuery({ queryKey: ['project-trails'], enabled: !blocked, queryFn: async ({ signal }) => { const value = await requestJson('/api/m01/trails?limit=8', { signal }); if (!Array.isArray(value)) throw new ApiError('修改留痕读取不完整。'); return value as Trail[]; } });
  const all = projects.data ?? [];
  const rows = all.filter(p => (status === 'all' || p.status === status) && (type === 'all' || p.project_type === type) && [p.disp, p.name_full, p.warehouse_name ?? ''].some(text => text.includes(keyword.trim())));
  const cellValue = (p: ArchiveProject, key: string) => key === 'project_type' ? typeNames[p.project_type] : key === 'status' ? (p.status === 'active' ? '在建' : '归档') : key === 'parent' ? all.find(item => item.id === p.parent_shell_id)?.name_full ?? '' : key === 'keywords' ? p.match_keywords.join('、') : String(p[key as keyof ArchiveProject] ?? '');
  if (sort) rows.sort((a, b) => Number(a.status === 'archived') - Number(b.status === 'archived') || cellValue(a, sort.key).localeCompare(cellValue(b, sort.key), 'zh', { numeric: true }) * (sort.descending ? -1 : 1));
  const heading = (key: string, text: string) => <th aria-sort={sort?.key === key ? sort.descending ? 'descending' : 'ascending' : 'none'}><button className="project-sort" onClick={() => setSort(sort?.key === key ? sort.descending ? null : { key, descending: true } : { key, descending: false })}>{text} {sort?.key === key ? sort.descending ? '↓' : '↑' : '↕'}</button></th>;
  const unavailable = blocked || !me || busy || projects.isError || projects.isPending;
  async function refresh() {
    await Promise.all([client.invalidateQueries({ queryKey: ['projects'] }), client.invalidateQueries({ queryKey: ['project-archive'] }), client.invalidateQueries({ queryKey: ['project-promote-pending'] }), client.invalidateQueries({ queryKey: ['project-archive-pending'] }), client.invalidateQueries({ queryKey: ['project-trails'] }), client.invalidateQueries({ queryKey: ['i8-records'] })]);
  }
  async function run(action: () => Promise<unknown>, success: string): Promise<boolean> {
    if (blocked || !me || lock.current) return false;
    lock.current = true; setBusy(true); setFeedback('');
    try { await action(); if (!mounted.current) return false; setFeedback(success); await refresh(); return true; }
    catch (error) { if (mounted.current) setFeedback(messageOf(error)); return false; }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function move(id: number, position: number | 'up' | 'down') {
    const p = all.find(item => item.id === id); if (!p) return null; setSort(null);
    let saved: number | null = null;
    // The API inserts within a status group; fields and drop targets use global positions.
    const ok = await run(async () => {
      const ordered = readProjects(await requestJson(`/api/m01/projects/${id}/ord`, { method: 'PUT', ...body(typeof position === 'number' ? { to_position: Math.max(1, position - (p.status === 'archived' ? all.filter(item => item.status === 'active').length : 0)) } : { direction: position }) }));
      saved = ordered.find(item => item.id === id)?.ord ?? null;
    }, `「${label(p)}」排序已保存；归档项目仍排在最后。`);
    return ok ? saved : null;
  }
  async function exportRows() {
    const ids = rows.map(p => p.id);
    await run(async () => {
      const result = object<{ content_b64: string; filename: string }>(await requestJson('/api/m01/projects/export', { method: 'POST', ...body({ ids }) }), x => typeof x.content_b64 === 'string' && typeof x.filename === 'string' && !/[\\/:]/.test(x.filename));
      if (!mounted.current) return;
      const blob = new Blob([Uint8Array.from(atob(result.content_b64), c => c.charCodeAt(0))], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = result.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, `已按显示顺序导出 ${ids.length} 个项目。`);
  }
  return <section className="projects-page" aria-labelledby="page-title">{params.get('bill') && <p><Link to={`/notices?notice=${encodeURIComponent(params.get('notice')??'')}`}>返回通知书 {params.get('bill')} 继续核对</Link></p>}
    <div className="project-toolbar"><button disabled={unavailable} onClick={() => setModal({ kind: 'create' })}>＋ 手工建档</button><button disabled={unavailable} onClick={() => setModal({ kind: 'sync', source: 'warehouses' })}>同步仓库名单</button><button disabled={unavailable} onClick={() => setModal({ kind: 'sync', source: 'common-projects' })}>同步常用项目列表</button><button className="primary" disabled={unavailable || !rows.length} onClick={() => void exportRows()}>导出 Excel</button></div>
    {!me && <p className="state">登录后可维护项目和导出。</p>}
    <form className="filters" onSubmit={e => e.preventDefault()}><label>状态<select value={status} onChange={e => setStatus(e.target.value)}><option value="active">在建</option><option value="archived">归档</option><option value="all">全部</option></select></label><label>项目类型<select value={type} onChange={e => setType(e.target.value)}><option value="all">全部</option>{Object.entries(typeNames).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label><label className="search">项目<input type="search" value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="全名、仓库名或展示名" /></label><button onClick={() => { setStatus('active'); setType('all'); setKeyword(''); setSort(null); }}>重置</button></form>
    {feedback && <p className="project-feedback" role="status">{feedback}</p>}{busy && <p className="state" role="status">正在处理，请稍候…</p>}
    {[pending, archive].map((query, index) => query.isError ? <p className="notice" key={index} role="alert">{query.error.message}<button onClick={() => void query.refetch()}>重读待办</button></p> : query.data && (query.data.items.length > 0 || query.data.dropped_items?.length) ? <div className="project-pending" key={index}><h2>{index === 0 ? '待人工指认' : '待人工建档'}</h2><p className="project-source">{query.data.source.target} · {query.data.source.at}</p>{query.data.items.map((item, i) => <div className="project-task" key={`${item.full_name}:${item.warehouse_name ?? i}`}><span>{item.full_name}{item.warehouse_name ? ` · ${item.warehouse_name}` : ''}</span><button disabled={unavailable} onClick={() => setModal({ kind: index === 0 ? 'promote' : 'archive', item })}>{index === 0 ? '选择档案扶正' : '选择仓库建档'}</button></div>)}{query.data.dropped_items?.length ? <details><summary>已不属当前待办的项目</summary>{query.data.dropped_items.map((item, i) => <p key={i}>{item.full_name}：{item.why_text}</p>)}</details> : null}</div> : null)}
    {projects.isPending ? <p role="status" className="state">正在读取项目…</p> : projects.isError ? <p className="notice" role="alert">{projects.error.message}<button onClick={() => void projects.refetch()}>重读项目</button></p> : <><p className="result">共 {rows.length} 个项目{projects.isFetching ? ' · 正在更新…' : ''}</p>{!rows.length ? <p className="state">没有符合条件的项目。可调整筛选，或手工建档、同步名单。</p> : <div className="table-scroll project-table" tabIndex={0} role="region" aria-label="项目列表"><table><thead><tr><th>序号</th>{heading('project_type', '项目类型')}{heading('disp', '展示名')}{heading('warehouse_name', '仓库名')}{heading('name_full', '项目全名')}{heading('phid', '信息化编号')}{heading('status', '状态')}{heading('parent', '父壳')}{heading('keywords', '关键词')}<th>操作</th></tr></thead><tbody>{rows.map((p, i) => {
      const previous = rows[i - 1]; const inGroup = all.filter(item => item.status === p.status), at = inGroup.findIndex(item => item.id === p.id);
      const match = pending.data?.items.find(item => item.candidates?.some(c => c.id === p.id && c.is_placeholder));
      return <tr key={p.id} className={p.is_placeholder ? 'project-placeholder' : ''} onDragOver={e => { const source = all.find(item => item.id === dragging.current); if (source && source.status === p.status && source.id !== p.id) e.preventDefault(); }} onDrop={e => { e.preventDefault(); const id = dragging.current; dragging.current = null; if (id && all.find(item => item.id === id)?.status === p.status && !unavailable) void move(id, all.findIndex(item => item.id === p.id) + 1); }}>
        <td>{status === 'all' && p.status === 'archived' && previous?.status !== 'archived' && <span className="archive-divider">归档</span>}<div className="project-order"><button draggable={!unavailable} disabled={unavailable} title="拖动调整全局顺序；也可填序号或用上移、下移" aria-label={`拖动排序：${label(p)}`} onDragStart={e => { dragging.current = p.id; e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(p.id)); }} onDragEnd={() => { dragging.current = null; }}>⠿</button><OrderInput project={p} disabled={unavailable} move={move} /><button aria-label={`上移：${label(p)}`} disabled={unavailable || at === 0} onClick={() => void move(p.id, 'up')}>↑</button><button aria-label={`下移：${label(p)}`} disabled={unavailable || at === inGroup.length - 1} onClick={() => void move(p.id, 'down')}>↓</button></div></td>
        <td><button className={`project-type project-type-${p.project_type}`} title="纠正项目类型" disabled={unavailable} onClick={() => setModal({ kind: 'type', project: p })}>{typeNames[p.project_type]}</button></td><td>{p.project_type === 'shell' ? '—' : p.disp || '—'}</td><td>{p.warehouse_name || '—'}{p.is_placeholder && <span className="project-placeholder-label">无仓库（历史项目）</span>}</td><td>{p.name_full}</td><td>{p.phid || '—'}</td><td><button className="project-link" disabled={unavailable} onClick={() => setModal({ kind: 'status', project: p })}>{p.status === 'active' ? '在建' : '归档'}</button></td><td>{all.find(item => item.id === p.parent_shell_id)?.name_full || '—'}</td><td>{p.match_keywords.join('、') || '—'}</td><td><div className="project-row-actions"><button className="project-link" disabled={unavailable} onClick={() => setModal({ kind: 'edit', project: p })}>编辑</button>{p.is_placeholder && match && <button className="project-link" disabled={unavailable} onClick={() => setModal({ kind: 'promote', item: match })}>扶正</button>}{p.project_type === 'small' && <button className="project-link" disabled={unavailable} onClick={() => setModal({ kind: 'keywords', project: p })}>改关键词</button>}<button className="project-link danger" disabled={unavailable} onClick={() => setModal({ kind: 'delete', project: p })}>删除</button></div></td>
      </tr>;
    })}</tbody></table></div>}</>}
    {trails.isError ? <p className="notice" role="alert">{trails.error.message}<button onClick={() => void trails.refetch()}>重读留痕</button></p> : trails.data?.length ? <details className="project-trails" open><summary>修改留痕（全名 / 状态）</summary><div className="table-scroll"><table><thead><tr><th>时间</th><th>项目</th><th>字段</th><th>改前值</th><th>改后值</th><th>改动人</th></tr></thead><tbody>{trails.data.map((t, i) => <tr key={i}><td>{t.at}</td><td>{t.project}</td><td>{t.field_label}</td><td>{trailValue(t, t.before)}</td><td>{trailValue(t, t.after)}</td><td>{t.by}</td></tr>)}</tbody></table></div></details> : null}
    {modal && <ProjectDialog state={modal} me={me} blocked={blocked} close={() => setModal(null)} refresh={refresh} announce={setFeedback} />}
  </section>;
}
function ProjectDialog({ state, me, blocked, close, refresh, announce }: { state: DialogState; me: Identity | null; blocked: boolean; close: () => void; refresh: () => Promise<void>; announce: (message: string) => void }) {
  const p = 'project' in state ? state.project : null, item = 'item' in state ? state.item : null;
  const [full, setFull] = useState(p?.name_full ?? ''), [disp, setDisp] = useState(p?.disp ?? ''), [status, setStatus] = useState(p?.status ?? 'active');
  const [newType, setNewType] = useState(''), [warehouse, setWarehouse] = useState(p?.warehouse_name ?? '');
  const [keywords, setKeywords] = useState(p?.match_keywords.join(' | ') ?? ''), [choice, setChoice] = useState(''), [kick, setKick] = useState(false);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [done, setDone] = useState(false), [receipt, setReceipt] = useState(''), [samples, setSamples] = useState<Record<string, unknown>[]>([]);
  const dialog = useRef<HTMLDialogElement>(null), lock = useRef(false), mounted = useRef(true);
  useEffect(() => { mounted.current = true; dialog.current?.showModal(); return () => { mounted.current = false; }; }, []);
  useEffect(() => { if (blocked) dialog.current?.close(); else if (!dialog.current?.open) dialog.current?.showModal(); }, [blocked]);
  const impact = useQuery({ queryKey: ['project-impact', p?.id], enabled: state.kind === 'delete' && !blocked, queryFn: async ({ signal }) => object<Impact>(await requestJson(`/api/m01/projects/${p!.id}/delete-impact`, { signal }), x => typeof x.can_delete === 'boolean' && typeof x.message === 'string' && Array.isArray(x.groups)), staleTime: 0 });
  const connection = useQuery({ queryKey: ['project-sync-config'], enabled: state.kind === 'sync' && !blocked, queryFn: async ({ signal }) => object<Connection>(await requestJson('/api/m02/config', { signal }), x => typeof x.account === 'string' && typeof x.i8_user === 'string' && typeof x.ready === 'boolean' && typeof x.message === 'string'), staleTime: 0, refetchOnMount: 'always' });
  const title = state.kind === 'sync' ? `同步${state.source === 'warehouses' ? '仓库名单' : '常用项目列表'}` : ({ create: '手工建档 · 无仓库项目', edit: '编辑项目', type: '纠正项目类型', status: '修改项目状态', keywords: '小微识别关键词', delete: '删除项目档案', promote: '人工指认 · 扶正', archive: '选择仓库建档' } as const)[state.kind];
  const cannot = blocked || !me || busy || (state.kind === 'delete' && (!impact.data?.can_delete || impact.isFetching || impact.isError)) || (state.kind === 'sync' && (!connection.data?.ready || connection.isFetching || connection.isError || connection.data.account !== me?.account));
  async function save() {
    if (cannot || lock.current) return;
    if (['create', 'edit'].includes(state.kind) && !full.trim()) { setError('请填写项目全名。'); return; }
    if ((state.kind === 'promote' || state.kind === 'archive') && !choice) { setError('请先选择一项。'); return; }
    if (state.kind === 'type' && (!newType || (newType === 'normal' && !warehouse.trim()))) { setError('请选择类型；改为普通项目时请填写仓库名。'); return; }
    lock.current = true; setBusy(true); setError(''); setKick(false);
    let written = false;
    try {
      let result: unknown;
      if (state.kind === 'create') result = await requestJson('/api/m01/projects', { method: 'POST', ...body({ project_type: 'normal', name_full: full.trim(), disp: disp.trim() || full.trim() }) });
      else if (state.kind === 'edit') result = await requestJson(`/api/m01/projects/${p!.id}`, { method: 'PUT', ...body({ ...(p!.parent_shell_id ? {} : { name_full: full.trim() }), ...(p!.project_type === 'shell' ? {} : { disp: disp.trim() }) }) });
      else if (state.kind === 'type') result = await requestJson(`/api/m01/projects/${p!.id}/type`, { method: 'PUT', ...body({ project_type: newType, warehouse_name: warehouse.trim() }) });
      else if (state.kind === 'status') result = await requestJson(`/api/m01/projects/${p!.id}/status`, { method: 'PUT', ...body({ status }) });
      else if (state.kind === 'keywords') result = await requestJson(`/api/m01/projects/${p!.id}`, { method: 'PUT', ...body({ match_keywords: keywords.split('|').map(x => x.trim()).filter(Boolean) }) });
      else if (state.kind === 'delete') result = await requestJson(`/api/m01/projects/${p!.id}?confirmed=true`, { method: 'DELETE' });
      else if (state.kind === 'promote') result = await requestJson('/api/m01/promote', { method: 'POST', ...body({ project_id: Number(choice), warehouse_name: item!.warehouse_name, full_name: item!.full_name }) });
      else if (state.kind === 'archive') result = await requestJson('/api/m01/archive-row', { method: 'POST', ...body({ warehouse_name: choice, full_name: item!.full_name }) });
      else if (state.kind === 'sync') {
        result = await requestJson(`/api/m02/sync/${state.source}?${new URLSearchParams({ allow_kick: String(kick), expected_account: me!.account })}`, { method: 'POST' });
        const sync = object<{ degraded: boolean; message: string; count: number; sample: Record<string, unknown>[] }>(result, x => typeof x.degraded === 'boolean' && typeof x.message === 'string' && typeof x.count === 'number' && Array.isArray(x.sample));
        if (sync.degraded) { await refresh(); throw new ApiError(sync.message || '同步未完成，请核对执行记录后重试。'); }
        if (mounted.current) { setReceipt(sync.message || `已同步 ${sync.count} 条。`); setSamples(sync.sample); setDone(true); }
      }
      written = true;
      if (!mounted.current) return;
      if (state.kind !== 'sync') { announce(record(result) && typeof result.message === 'string' ? result.message : `「${p ? label(p) : item?.full_name || full.trim()}」已保存。`); close(); }
      await refresh();
    } catch (failure) { if (mounted.current) setError(written ? `已写入，但列表暂时未更新。${messageOf(failure)}` : messageOf(failure)); }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  return <dialog ref={dialog} className="project-dialog" aria-labelledby="project-dialog-title" onCancel={e => { e.preventDefault(); if (!busy) close(); }}><form onSubmit={e => { e.preventDefault(); void save(); }}><h2 id="project-dialog-title">{title}</h2>{p && <p>{label(p)}</p>}{item && <p>{item.full_name}{item.warehouse_name ? ` · ${item.warehouse_name}` : ''}</p>}
    {(state.kind === 'create' || state.kind === 'edit') && <><label>项目全名<input autoFocus required value={full} readOnly={Boolean(p?.parent_shell_id)} title={p?.parent_shell_id ? '具体小微借壳全名，不可单独修改' : ''} disabled={busy} onChange={e => setFull(e.target.value)} /></label>{p?.parent_shell_id && <p>具体小微借壳全名，不可单独修改。</p>}{p?.project_type !== 'shell' && <label>展示名<input value={disp} disabled={busy} placeholder={state.kind === 'create' ? '留空取项目全名' : '留空取仓库名'} onChange={e => setDisp(e.target.value)} /></label>}</>}
    {state.kind === 'type' && <><label>目标类型<select autoFocus value={newType} disabled={busy} onChange={e => setNewType(e.target.value)}><option value="">请选择类型</option><option value="normal" disabled={p?.project_type === 'normal'}>普通项目</option><option value="shell" disabled={p?.project_type === 'shell'}>小微壳</option></select></label>{newType === 'normal' && <label>仓库名<input required value={warehouse} disabled={busy} onChange={e => setWarehouse(e.target.value)} /></label>}<p>类型修改会留痕。小微壳不挂仓库；具体小微由建档流程产生。</p></>}
    {state.kind === 'status' && <label>状态<select value={status} disabled={busy} onChange={e => setStatus(e.target.value as Project['status'])}><option value="active">在建</option><option value="archived">归档</option></select></label>}
    {state.kind === 'keywords' && <label>关键词（多个用 | 分隔）<input autoFocus value={keywords} disabled={busy} onChange={e => setKeywords(e.target.value)} /></label>}
    {state.kind === 'promote' && <label>指定档案<select autoFocus value={choice} disabled={busy} onChange={e => setChoice(e.target.value)}><option value="">请选择档案</option>{item!.candidates?.map(c => <option key={c.id} value={c.id} disabled={!c.is_placeholder}>{c.disp || c.warehouse_name} · {c.warehouse_name}{c.status === 'archived' ? '（归档）' : ''}{!c.is_placeholder ? '（已有仓库，不可扶正）' : ''}</option>)}</select></label>}
    {state.kind === 'archive' && <><label>仓库<select autoFocus value={choice} disabled={busy} onChange={e => setChoice(e.target.value)}><option value="">请选择仓库</option>{item!.warehouses?.map(wh => <option key={wh} value={wh}>{wh}</option>)}</select></label><p>只为选中的仓库建档，其余仓库不建行。</p></>}
    {state.kind === 'delete' && <>{impact.isPending ? <p role="status">正在核对关联影响…</p> : impact.isError ? <p className="notice" role="alert">{impact.error.message}<button type="button" onClick={() => void impact.refetch()}>重读影响</button></p> : <><p className={impact.data.can_delete ? 'danger' : ''}>{impact.data.message}</p>{impact.data.groups.filter(g => g.count > 0).map((g, i) => <details key={i}><summary>{g.label}：{g.count} 条（保留）</summary>{g.rows.map((row, j) => <p key={j}>{['bill_no', 'contract_no', 'batch_no', 'ym', 'year_month', 'doc_date', 'supplier', 'item_name', 'name_full'].map(key => row[key]).filter(v => typeof v === 'string' && v).join(' · ') || `记录 ${row.id ?? j + 1}`}</p>)}</details>)}</>}</>}
    {state.kind === 'sync' && <>{connection.isPending ? <p role="status">正在核对当前账号的 i8 绑定…</p> : connection.isError ? <p className="notice" role="alert">{connection.error.message}<button type="button" onClick={() => void connection.refetch()}>重读绑定</button></p> : <><p>当前账号：{me?.name || me?.account} · i8：{connection.data.i8_user || '未绑定'}</p>{(!connection.data.ready || connection.data.account !== me?.account) && <p role="alert">{connection.data.message || '账号已变化，请关闭后重新打开。'}</p>}</>}{!done && <><p>将登录 i8 并同步名单。默认遇到在线会话冲突即停止；失败后不会自动重试。</p><label className="project-kick"><input type="checkbox" checked={kick} disabled={busy} onChange={e => setKick(e.target.checked)} />允许强踢：会退出此 i8 账号的其他在线会话</label></>}{receipt && <p role="status">{receipt}</p>}{samples.length > 0 && <details open><summary>{state.source === 'warehouses' ? '名单样例' : '需处理项目'}</summary>{samples.map((sample, i) => <p key={i}>{['warehouse_name', 'name_full', 'owner_full_name', 'reason'].map(key => sample[key]).filter(v => typeof v === 'string' && v).join(' · ')}</p>)}</details>}</>}
    {error && <p className="notice" role="alert">{error}</p>}{busy && <p role="status">正在执行，请稍候…</p>}<div className="dialog-actions"><button type="button" disabled={busy} onClick={close}>{done ? '关闭' : '取消'}</button>{!done && <button className={state.kind === 'delete' ? 'danger' : 'primary'} disabled={cannot} type="submit">{state.kind === 'delete' ? '确认删除' : state.kind === 'sync' ? kick ? '确认允许强踢并同步' : '确认同步' : '保存'}</button>}</div>
  </form></dialog>;
}
