import App from 'antd/es/app';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import { useHistoryGuard } from './history';
import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { BusinessGrid, ReadGrid } from './business-grid';
import { ProjectDragImage } from './project-drag-image';
import { contentWidth, fixedWidth, fullTextWidth } from './grid';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, readProjects, record, requestJson, uncertainWrite } from './api';
import type { Identity, Project } from './api';
import { DialogContents, useDialogClose } from './dialog-close';

type ArchiveProject = Project & { parent_shell_id: number | null; match_keywords: string[]; is_placeholder: boolean };
type Candidate = { id: number; disp: string; warehouse_name: string; status: string; is_placeholder: boolean };
type Pending = { full_name: string; warehouse_name?: string; candidates?: Candidate[]; warehouses?: string[]; reason?: string };
type PendingList = { items: Pending[]; source: { at?: string; target?: string }; dropped_items?: { full_name: string; why_text: string }[] };
type Trail = { at: string; project: string; field_label: string; before: string; after: string; by: string };
type Impact = { can_delete: boolean; message: string; groups: { label: string; count: number; rows: Record<string, unknown>[] }[] };
type Connection = { account: string; i8_user: string; ready: boolean; message: string };
type DialogState = { kind: 'create' } | { kind: 'delete'; project: ArchiveProject } | { kind: 'promote' | 'archive'; item: Pending } | { kind: 'sync'; source: 'warehouses' | 'common-projects' };
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
  return <Input type="number" min="1" step="1" aria-label={`排序：${label(project)}`} title="全局序号；归档项目排在最后" value={position} disabled={disabled} onChange={e => setPosition(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }} onBlur={() => { const n = Number(position); if (Number.isInteger(n) && n > 0 && n !== project.ord) void move(project.id, n).then(saved => { if (saved !== null) setPosition(String(saved)); }); else setPosition(String(project.ord)); }} />;
}
type EditableField = 'name_full' | 'disp' | 'match_keywords';
type ProjectDraft = { value: string; error: string; pending: boolean; uncertain: boolean };
const fieldKey = (id: number, field: EditableField) => `${id}:${field}`;
function ProjectField({ project, field, disabled, readDisabled, draft, changeDraft, save, reread }: {
  project: ArchiveProject; field: EditableField; disabled: boolean; readDisabled: boolean; draft: ProjectDraft | undefined;
  changeDraft: (draft: ProjectDraft | null) => void; save: (project: ArchiveProject, field: EditableField, value: string) => Promise<void>;
  reread: (project: ArchiveProject, field: EditableField) => Promise<void>;
}) {
  const value = field === 'match_keywords' ? project.match_keywords.join(' | ') : project[field];
  const fieldName = { name_full: '项目全名', disp: '展示名', match_keywords: '关键词' }[field];
  const pending = draft?.pending ?? false, uncertain = draft?.uncertain ?? false;
  const input = draft?.value ?? value, error = draft?.error ?? '', errorId = `project-${project.id}-${field}-error`;
  function commit() {
    if (disabled || pending || uncertain || !draft || input === value) return;
    if (field === 'name_full' && !input.trim()) { changeDraft({ ...draft, error: '请填写项目全名。' }); return; }
    void save(project, field, input.trim());
  }
  return <div className="project-field"><Input className="record-value" aria-label={`${fieldName}：${label(project)}`} aria-describedby={error ? errorId : undefined} aria-invalid={Boolean(error)} value={input} disabled={disabled} readOnly={pending || uncertain} title={field === 'match_keywords' ? '多个关键词用 | 分隔；离开此格保存' : input || '留空取仓库名'} placeholder={field === 'disp' ? '留空取仓库名' : field === 'match_keywords' ? '多个关键词用 | 分隔' : undefined} onChange={e => changeDraft(e.target.value === value ? null : { value: e.target.value, error: '', pending: false, uncertain: false })} onBlur={commit} onKeyDown={e => {
    if (e.nativeEvent.isComposing) return;
    if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); }
    if (e.key === 'Escape' && !pending && !uncertain) { e.preventDefault(); changeDraft(null); }
  }} />{error && <p id={errorId} className="project-cell-error" role="alert">{error}</p>}{uncertain && <Button className="project-cell-recheck" disabled={pending || readDisabled} aria-label={`重读核对：${fieldName}：${label(project)}`} onClick={() => void reread(project, field)}>重读核对</Button>}</div>;
}
export function Projects({ me, blocked }: { me: Identity | null; blocked: boolean }) {
  const client = useQueryClient();
  const { message } = App.useApp();
  const [params] = useSearchParams();
  const [sort, setSort] = useState<{ key: string; descending: boolean } | null>(null);
  const [status, setStatus] = useState('active'), [type, setType] = useState('all'), [keyword, setKeyword] = useState('');
  const [modal, setModal] = useState<DialogState | null>(null), [feedback, setFeedback] = useState(''), [busy, setBusy] = useState(false);
  const [statusEdit, setStatusEdit] = useState<{ id: number; value: Project['status'] } | null>(null), [statusErrors, setStatusErrors] = useState<Record<number,string>>({});
  const [drafts, setDrafts] = useState<Record<string, ProjectDraft>>({});
  const [inlineSaving, setInlineSaving] = useState(0), [dragged, setDragged] = useState<number | null>(null), [previewOrder, setPreviewOrder] = useState<number[] | null>(null);
  const lock = useRef(false), mounted = useRef(true), dragging = useRef<number | null>(null), dragOrder = useRef<number[]|null>(null), gridApi = useRef<GridApi<ArchiveProject> | null>(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const projects = useQuery({ queryKey: ['project-archive'], enabled: !blocked, queryFn: ({ signal }) => archiveProjects(signal) });
  const pending = useQuery({ queryKey: ['project-promote-pending'], enabled: !blocked, queryFn: async ({ signal }) => object<PendingList>(await requestJson('/api/m01/promote-pending', { signal }), x => Array.isArray(x.items) && record(x.source)) });
  const archive = useQuery({ queryKey: ['project-archive-pending'], enabled: !blocked, queryFn: async ({ signal }) => object<PendingList>(await requestJson('/api/m01/archive-pending', { signal }), x => Array.isArray(x.items) && record(x.source)) });
  const trails = useQuery({ queryKey: ['project-trails'], enabled: !blocked, queryFn: async ({ signal }) => { const value = await requestJson('/api/m01/trails?limit=8', { signal }); if (!Array.isArray(value)) throw new ApiError('修改留痕读取不完整。'); return value as Trail[]; } });
  const all = projects.data ?? [];
  const ordered = previewOrder ? [...all].sort((a, b) => previewOrder.indexOf(a.id) - previewOrder.indexOf(b.id)) : all;
  const rows = ordered.filter(p => (status === 'all' || p.status === status) && (type === 'all' || p.project_type === type) && [p.disp, p.name_full, p.warehouse_name ?? ''].some(text => text.includes(keyword.trim())));
  const cellValue = (p: ArchiveProject, key: string) => key === 'project_type' ? typeNames[p.project_type] : key === 'status' ? (p.status === 'active' ? '在建' : '归档') : key === 'parent' ? all.find(item => item.id === p.parent_shell_id)?.name_full ?? '' : key === 'keywords' ? p.match_keywords.join('、') : String(p[key as keyof ArchiveProject] ?? '');
  if (sort) rows.sort((a, b) => Number(a.status === 'archived') - Number(b.status === 'archived') || cellValue(a, sort.key).localeCompare(cellValue(b, sort.key), 'zh', { numeric: true }) * (sort.descending ? -1 : 1));
  useEffect(()=>{if(!sort&&gridApi.current&&!gridApi.current.isDestroyed())gridApi.current.applyColumnState({defaultState:{sort:null}});},[sort]);
  useHistoryGuard('projects', () => busy || lock.current || inlineSaving > 0 ? '项目档案正在保存，请稍候。' : Object.values(drafts).some(draft => draft.uncertain) ? '项目保存结果待核实，请先重读核对。' : Object.keys(drafts).length ? '请先保存或取消项目格内的修改。' : '');
  const editableDisabled = blocked || !me || busy || projects.isError || projects.isPending;
  const unavailable = editableDisabled || inlineSaving > 0;
  async function refresh() {
    await Promise.all([client.invalidateQueries({ queryKey: ['projects'] }), client.invalidateQueries({ queryKey: ['project-archive'] }), client.invalidateQueries({ queryKey: ['project-promote-pending'] }), client.invalidateQueries({ queryKey: ['project-archive-pending'] }), client.invalidateQueries({ queryKey: ['project-trails'] }), client.invalidateQueries({ queryKey: ['i8-records'] }), client.invalidateQueries({ queryKey: ['history'] })]);
  }
  async function run(action: () => Promise<unknown>, success: string): Promise<boolean> {
    if (blocked || !me || lock.current) return false;
    lock.current = true; setBusy(true); setFeedback('');
    try { await action(); if (!mounted.current) return false; void message.success(success); await refresh(); return true; }
    catch (error) { if (mounted.current) setFeedback(messageOf(error)); return false; }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  function changeDraft(id: number, field: EditableField, draft: ProjectDraft | null) {
    if (!mounted.current) return;
    setDrafts(old => { const next = { ...old }, key = fieldKey(id, field); if (draft) next[key] = draft; else delete next[key]; return next; });
  }
  async function saveField(project: ArchiveProject, field: EditableField, value: string) {
    if (editableDisabled) return;
    changeDraft(project.id, field, { value, error: '', pending: true, uncertain: false });
    setInlineSaving(count => count + 1); let written = false;
    try {
      const result = await requestJson(`/api/m01/projects/${project.id}`, { method: 'PUT', ...body({ [field]: field === 'match_keywords' ? value.split('|').map(x => x.trim()).filter(Boolean) : value }) }); written = true;
      const saved = readProjects([result])[0]!;
      if (saved.id !== project.id || !record(result) || field === 'match_keywords' && (!Array.isArray(result.match_keywords) || !result.match_keywords.every(x => typeof x === 'string'))) throw new ApiError('保存回执不完整。');
      const confirmed = field === 'match_keywords' ? result.match_keywords as string[] : saved[field];
      client.setQueryData<ArchiveProject[]>(['project-archive'], old => old?.map(item => item.id === project.id ? { ...item, [field]: confirmed } : item));
      await refresh();
      changeDraft(project.id, field, null);
    } catch (failure) {
      const uncertain = written || uncertainWrite(failure);
      changeDraft(project.id, field, { value, pending: false, uncertain, error: `${uncertain ? '保存结果待核实，请重读核对，勿重复保存。' : '未保存，已保留输入。'}${messageOf(failure)}` });
    } finally { if (mounted.current) setInlineSaving(count => count - 1); }
  }
  async function rereadField(project: ArchiveProject, field: EditableField) {
    const draft = drafts[fieldKey(project.id, field)];
    if (!draft?.uncertain || draft.pending || blocked || !me || busy) return;
    changeDraft(project.id, field, { ...draft, pending: true }); setInlineSaving(count => count + 1);
    try {
      const current = await client.fetchQuery({ queryKey: ['project-archive'], staleTime: 0, queryFn: ({ signal }) => archiveProjects(signal) });
      const saved = current.find(item => item.id === project.id);
      if (!saved) throw new ApiError('档案不在读取结果内，请联系维护人员核对。');
      const normalize = (value: string) => field === 'match_keywords' ? [...new Set(value.split('|').map(item => item.trim()).filter(Boolean))].join(' | ') : value.trim();
      const actual = field === 'match_keywords' ? saved.match_keywords.join(' | ') : saved[field];
      changeDraft(project.id, field, normalize(actual) === normalize(draft.value) ? null : { ...draft, pending: false, uncertain: false, error: `已重读核对，当前值为「${actual || '空'}」。本次输入已保留，可继续保存或按 Esc 放弃。` });
      void client.invalidateQueries({ queryKey: ['projects'] }); void client.invalidateQueries({ queryKey: ['project-trails'] }); void client.invalidateQueries({ queryKey: ['history'] });
    } catch (failure) {
      changeDraft(project.id, field, { ...draft, pending: false, error: `保存结果待核实，输入已保留。${messageOf(failure)}` });
    } finally { if (mounted.current) setInlineSaving(count => count - 1); }
  }
  const fieldInput = (project: ArchiveProject, field: EditableField) => <ProjectField project={project} field={field} disabled={editableDisabled} readDisabled={blocked || !me || busy} draft={drafts[fieldKey(project.id, field)]} changeDraft={draft => changeDraft(project.id, field, draft)} save={saveField} reread={rereadField} />;
  function endDrag() { dragging.current = null; dragOrder.current=null; setDragged(null); setPreviewOrder(null); }
  async function changeStatus(project: ArchiveProject, value: Project['status']) {
    if (unavailable || lock.current || value === project.status) return;
    lock.current = true; setBusy(true); setStatusEdit({ id: project.id, value });
    setStatusErrors(old => ({ ...old, [project.id]: '' })); let written = false;
    try {
      const result = await requestJson(`/api/m01/projects/${project.id}/status`, { method: 'PUT', ...body({ status: value }) }); written = true;
      if (!mounted.current) return;
      void message.success(record(result) && typeof result.message === 'string' ? result.message : `「${label(project)}」状态已保存。`);
      await refresh();
    } catch (failure) { if (mounted.current) setStatusErrors(old => ({ ...old, [project.id]: `${written ? '已保存，请重读核对。' : '未保存，已恢复原状态。'}${messageOf(failure)}` })); }
    finally { lock.current = false; if (mounted.current) { setBusy(false); setStatusEdit(null); } }
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
    const ids:number[]=[];
    gridApi.current?.forEachNodeAfterFilterAndSort(node=>{if(node.data&&!node.rowPinned)ids.push(node.data.id);});
    if(!ids.length){setFeedback('项目列表尚未准备好，请稍候。');return;}
    await run(async () => {
      const result = object<{ content_b64: string; filename: string }>(await requestJson('/api/m01/projects/export', { method: 'POST', ...body({ ids }) }), x => typeof x.content_b64 === 'string' && typeof x.filename === 'string' && !/[\\/:]/.test(x.filename));
      if (!mounted.current) return;
      const blob = new Blob([Uint8Array.from(atob(result.content_b64), c => c.charCodeAt(0))], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = result.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, `已按显示顺序导出 ${ids.length} 个项目。`);
  }
  const scale=Number(me?.ui_scale_css)||1;
  const gridState=useRef({all,fieldInput,statusEdit,statusErrors,unavailable,editableDisabled,pending:pending.data,changeStatus,move,setModal});
  gridState.current={all,fieldInput,statusEdit,statusErrors,unavailable,editableDisabled,pending:pending.data,changeStatus,move,setModal};
  useEffect(()=>{gridApi.current?.refreshCells({force:true});},[drafts,statusEdit,statusErrors,unavailable,editableDisabled]);
  const phidWidth=fullTextWidth(all.map(p=>p.phid||'—'),scale).minWidth;
  const columns=useMemo<ColDef<ArchiveProject>[]>(()=>[
    {colId:'sequence',headerName:'序号',...fixedWidth(220,scale),rowDrag:()=>!gridState.current.unavailable,cellRenderer:({data:p}:ICellRendererParams<ArchiveProject>)=>{if(!p)return null;const state=gridState.current,inGroup=state.all.filter(item=>item.status===p.status),at=inGroup.findIndex(item=>item.id===p.id);return <div className="project-order"><OrderInput project={p} disabled={state.unavailable} move={state.move}/><Button aria-label={`上移：${label(p)}`} disabled={state.unavailable||at===0} onClick={()=>void state.move(p.id,'up')}>↑</Button><Button aria-label={`下移：${label(p)}`} disabled={state.unavailable||at===inGroup.length-1} onClick={()=>void state.move(p.id,'down')}>↓</Button></div>;}},
    ...[['project_type','项目类型'],['disp','展示名'],['warehouse_name','仓库名'],['name_full','项目全名'],['phid','信息化编号'],['status','状态'],['parent','父壳'],['keywords','关键词']].map(([key,title]):ColDef<ArchiveProject>=>({colId:key!,headerName:title!,sortable:true,...contentWidth(key==='phid'?phidWidth/scale:key==='status'?110:140,key==='name_full'?400:320,scale,key==='name_full'?2:key==='disp'?1:0),
      valueGetter:({data:p})=>p?key==='project_type'?typeNames[p.project_type]:key==='status'?p.status==='active'?'在建':'归档':key==='parent'?gridState.current.all.find(item=>item.id===p.parent_shell_id)?.name_full??'':key==='keywords'?p.match_keywords.join('、'):String(p[key as keyof ArchiveProject]??''):'',
      comparator:(a,b)=>String(a??'').localeCompare(String(b??''),'zh',{numeric:true}),
      cellRenderer:({data:p}:ICellRendererParams<ArchiveProject>)=>{if(!p)return null;const state=gridState.current;
        if(key==='project_type')return <Tag className={`enum-tag project-type project-type-${p.project_type}`}>{typeNames[p.project_type]}</Tag>;
        if(key==='disp')return p.project_type==='shell'?'—':state.fieldInput(p,'disp');
        if(key==='name_full')return p.parent_shell_id?<span title="具体小微借壳全名，不可单独修改">{p.name_full}</span>:state.fieldInput(p,'name_full');
        if(key==='warehouse_name')return <><span>{p.warehouse_name||'—'}</span>{p.is_placeholder&&<span className="project-placeholder-label">无仓库（历史项目）</span>}</>;
        if(key==='status')return <><Select className="project-status" aria-label={`状态：${label(p)}`} aria-describedby={state.statusErrors[p.id]?`project-status-error-${p.id}`:undefined} disabled={state.unavailable} value={state.statusEdit?.id===p.id?state.statusEdit.value:p.status} onChange={value=>void state.changeStatus(p,value)} options={[{value:'active',label:'在建'},{value:'archived',label:'归档'}]} labelRender={option=><Tag className={`status-tag ${option.value==='active'?'status-info':'status-neutral'}`}>{option.label}</Tag>}/>{state.statusErrors[p.id]&&<p id={`project-status-error-${p.id}`} role="alert">{state.statusErrors[p.id]}</p>}</>;
        if(key==='keywords')return p.project_type==='small'?state.fieldInput(p,'match_keywords'):p.match_keywords.join('、')||'—';
        if(key==='parent')return state.all.find(item=>item.id===p.parent_shell_id)?.name_full||'—';
        return p.phid||'—';
      }})),
    {colId:'actions',headerName:'操作',...contentWidth(96,160,scale),cellRenderer:({data:p}:ICellRendererParams<ArchiveProject>)=>{if(!p)return null;const state=gridState.current,match=state.pending?.items.find(item=>item.candidates?.some(c=>c.id===p.id&&c.is_placeholder));return <div className="project-row-actions">{p.is_placeholder&&match&&<Button disabled={state.unavailable} onClick={()=>state.setModal({kind:'promote',item:match})}>扶正</Button>}<Button danger disabled={state.unavailable} onClick={()=>state.setModal({kind:'delete',project:p})}>删除</Button></div>;}}
  ],[scale,phidWidth]);
  return <section data-page-chrome className="projects-page" aria-labelledby="page-title">{params.get('bill') && <p><Link to={`/notices?notice=${encodeURIComponent(params.get('notice')??'')}`}>返回通知书 {params.get('bill')} 继续核对</Link></p>}
    <div className="project-toolbar"><Button htmlType="submit" disabled={unavailable} onClick={() => setModal({ kind: 'create' })}>＋ 手工建档</Button><Button htmlType="submit" disabled={unavailable} onClick={() => setModal({ kind: 'sync', source: 'warehouses' })}>同步仓库名单</Button><Button htmlType="submit" disabled={unavailable} onClick={() => setModal({ kind: 'sync', source: 'common-projects' })}>同步常用项目列表</Button><Button htmlType="submit" className="primary" disabled={unavailable || !rows.length} onClick={() => void exportRows()}>导出 Excel</Button></div>
    {!me && <p className="state">登录后可维护项目和导出。</p>}
    <form className="filters" onSubmit={e => e.preventDefault()}><label>状态<Select aria-label="项目状态筛选" value={status} onChange={setStatus} options={[{value:'active',label:'在建'},{value:'archived',label:'归档'},{value:'all',label:'全部'}]}/></label><label>项目类型<Select aria-label="项目类型筛选" value={type} onChange={setType} options={[{value:'all',label:'全部'},...Object.entries(typeNames).map(([value,label])=>({value,label}))]}/></label><label className="search">项目<Input aria-label="项目搜索" type="search" value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="全名、仓库名或展示名" /></label><Button htmlType="submit" onClick={() => { setStatus('active'); setType('all'); setKeyword(''); setSort(null); }}>重置</Button></form>
    {feedback && <p className="notice project-feedback" role="alert">{feedback}</p>}
    {[pending, archive].map((query, index) => query.isError ? <p className="notice" key={index} role="alert">{query.error.message}<Button htmlType="submit" onClick={() => void query.refetch()}>重读待办</Button></p> : query.data && (query.data.items.length > 0 || query.data.dropped_items?.length) ? <div className="project-pending" key={index}><h2>{index === 0 ? '待人工指认' : '待人工建档'}</h2><p className="project-source">{query.data.source.target}，{query.data.source.at}</p>{query.data.items.map((item, i) => <div className="project-task" key={`${item.full_name}:${item.warehouse_name ?? i}`}><span>{item.full_name}{item.warehouse_name ? `，${item.warehouse_name}` : ''}</span><Button htmlType="submit" disabled={unavailable} onClick={() => setModal({ kind: index === 0 ? 'promote' : 'archive', item })}>{index === 0 ? '选择档案扶正' : '选择仓库建档'}</Button></div>)}{query.data.dropped_items?.length ? <details><summary>已不属当前待办的项目</summary>{query.data.dropped_items.map((item, i) => <p key={i}>{item.full_name}：{item.why_text}</p>)}</details> : null}</div> : null)}
    {projects.isError && projects.data && <p className="notice" role="alert">项目更新失败，保留上次结果。{projects.error.message}<Button htmlType="submit" onClick={() => void projects.refetch()}>重读项目</Button></p>}{projects.isPending ? <p role="status" className="state">正在读取项目…</p> : projects.isError && !projects.data ? <p className="notice" role="alert">{projects.error.message}<Button htmlType="submit" onClick={() => void projects.refetch()}>重读项目</Button></p> : <><p className="result">共 {rows.length} 个项目</p>{!rows.length ? <p className="state">没有符合条件的项目。可调整筛选，或手工建档、同步名单。</p> : <BusinessGrid table="projects" className="project-table" label="项目列表" rows={rows} columns={columns} rowId={p=>String(p.id)} scale={scale} domLayout="normal" style={{height:'65dvh'}} grid={{onGridReady:e=>{gridApi.current=e.api;},dragAndDropImageComponent:ProjectDragImage,isRowValidDropPosition:p=>({allowed:!unavailable&&p.source.data?.status===p.overNode?.data?.status,highlight:true}),animateRows:dragged!==null&&!window.matchMedia('(prefers-reduced-motion: reduce)').matches,postSortRows:e=>{e.nodes.sort((a,b)=>Number(a.data?.status==='archived')-Number(b.data?.status==='archived'));},onSortChanged:e=>{const column=e.api.getColumnState().find(c=>c.sort);setSort(column?{key:column.colId,descending:column.sort==='desc'}:null);},onRowDragEnter:e=>{if(unavailable)return;dragging.current=e.node.data?.id??null;setDragged(dragging.current);dragOrder.current=all.map(p=>p.id);setPreviewOrder(dragOrder.current);},onRowDragMove:e=>{const source=all.find(p=>p.id===dragging.current),target=e.overNode?.data;if(unavailable||!source||!target||source.status!==target.status||source.id===target.id)return;const ids=all.map(p=>p.id),from=ids.indexOf(source.id),to=ids.indexOf(target.id);ids.splice(from,1);ids.splice(to,0,source.id);dragOrder.current=ids;setPreviewOrder(ids);},onRowDragEnd:e=>{const id=dragging.current,source=all.find(p=>p.id===id);if(id&&source&&e.overNode?.data?.status===source.status&&!unavailable){const position=(dragOrder.current??all.map(p=>p.id)).indexOf(id)+1;dragging.current=null;setDragged(null);void move(id,position).finally(()=>setPreviewOrder(null));}else endDrag();},onRowDragCancel:endDrag,onRowDragLeave:endDrag,getRowClass:p=>(p.data?.is_placeholder?'project-placeholder ':'')+(p.data?.id===dragged?'project-dragging':''),rowDragText:p=>p.rowNode?.data?label(p.rowNode.data):'项目'}} />}</>}
    {trails.isError ? <p className="notice" role="alert">{trails.error.message}<Button htmlType="submit" onClick={() => void trails.refetch()}>重读留痕</Button></p> : trails.data?.length ? <details className="project-trails" open><summary>修改留痕（全名 / 状态）</summary><ReadGrid table="project-trails" label="修改留痕" domLayout="autoHeight" rows={trails.data} rowId={(_row)=>String(trails.data!.indexOf(_row))} columns={[
      {field:'at',headerName:'时间'}, {field:'project',headerName:'项目'}, {field:'field_label',headerName:'字段'},
      {colId:'before',headerName:'改前值',valueGetter:p=>trailValue(p.data!,p.data!.before)},
      {colId:'after',headerName:'改后值',valueGetter:p=>trailValue(p.data!,p.data!.after)}, {field:'by',headerName:'改动人'},
    ]}/></details> : null}
    {modal && <ProjectDialog state={modal} me={me} blocked={blocked} close={() => setModal(null)} refresh={refresh} announce={text => { void message.success(text); }} />}
  </section>;
}
function ProjectDialog({ state, me, blocked, close, refresh, announce }: { state: DialogState; me: Identity | null; blocked: boolean; close: () => void; refresh: () => Promise<void>; announce: (message: string) => void }) {
  const p = 'project' in state ? state.project : null, item = 'item' in state ? state.item : null;
  const [full, setFull] = useState(p?.name_full ?? ''), [disp, setDisp] = useState(p?.disp ?? '');
  const [choice, setChoice] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [done, setDone] = useState(false), [receipt, setReceipt] = useState(''), [samples, setSamples] = useState<Record<string, unknown>[]>([]);
  const lock = useRef(false), mounted = useRef(true);
  useEffect(() => { mounted.current = true;  return () => { mounted.current = false; }; }, []);
  const impact = useQuery({ queryKey: ['project-impact', p?.id], enabled: state.kind === 'delete' && !blocked, queryFn: async ({ signal }) => object<Impact>(await requestJson(`/api/m01/projects/${p!.id}/delete-impact`, { signal }), x => typeof x.can_delete === 'boolean' && typeof x.message === 'string' && Array.isArray(x.groups)), staleTime: 0 });
  const connection = useQuery({ queryKey: ['project-sync-config'], enabled: state.kind === 'sync' && !blocked, queryFn: async ({ signal }) => object<Connection>(await requestJson('/api/m02/config', { signal }), x => typeof x.account === 'string' && typeof x.i8_user === 'string' && typeof x.ready === 'boolean' && typeof x.message === 'string'), staleTime: 0, refetchOnMount: 'always' });
  const title = state.kind === 'sync' ? `同步${state.source === 'warehouses' ? '仓库名单' : '常用项目列表'}` : ({ create: '手工建档，无仓库项目', delete: '删除项目档案', promote: '人工指认，扶正', archive: '选择仓库建档' } as const)[state.kind];
  const initial = useRef(JSON.stringify([full,disp,choice]));
  const closing = useDialogClose({ busy, dirty: !done && JSON.stringify([full,disp,choice]) !== initial.current, close });
  const cannot = blocked || !me || busy || (state.kind === 'delete' && (!impact.data?.can_delete || impact.isFetching || impact.isError)) || (state.kind === 'sync' && (!connection.data?.ready || connection.isFetching || connection.isError || connection.data.account !== me?.account));
  async function save() {
    if (cannot || lock.current) return;
    if (state.kind === 'create' && !full.trim()) { setError('请填写项目全名。'); return; }
    if ((state.kind === 'promote' || state.kind === 'archive') && !choice) { setError('请先选择一项。'); return; }
    lock.current = true; setBusy(true); setError('');
    let written = false;
    try {
      let result: unknown;
      if (state.kind === 'create') result = await requestJson('/api/m01/projects', { method: 'POST', ...body({ project_type: 'normal', name_full: full.trim(), disp: disp.trim() || full.trim() }) });
      else if (state.kind === 'delete') result = await requestJson(`/api/m01/projects/${p!.id}?confirmed=true`, { method: 'DELETE' });
      else if (state.kind === 'promote') result = await requestJson('/api/m01/promote', { method: 'POST', ...body({ project_id: Number(choice), warehouse_name: item!.warehouse_name, full_name: item!.full_name }) });
      else if (state.kind === 'archive') result = await requestJson('/api/m01/archive-row', { method: 'POST', ...body({ warehouse_name: choice, full_name: item!.full_name }) });
      else if (state.kind === 'sync') {
        result = await requestJson(`/api/m02/sync/${state.source}?${new URLSearchParams({ allow_kick: 'true', expected_account: me!.account })}`, { method: 'POST' });
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
  return <BusinessModal open={!blocked} className={`project-dialog${state.kind === 'sync' ? ' project-sync-dialog' : ''}`} titleId="project-dialog-title" requestClose={closing.requestClose}><DialogContents titleId="project-dialog-title" title={title} closing={closing}><form onSubmit={e => { e.preventDefault(); void save(); }}>{p && <p>{label(p)}</p>}{item && <p>{item.full_name}{item.warehouse_name ? `，${item.warehouse_name}` : ''}</p>}
    {state.kind === 'create' && <><label>项目全名<Input aria-label="项目全名" autoFocus required value={full} disabled={busy} onChange={e => setFull(e.target.value)} /></label><label>展示名<Input aria-label="展示名" value={disp} disabled={busy} placeholder="留空取项目全名" onChange={e => setDisp(e.target.value)} /></label></>}
    {state.kind === 'promote' && <label>指定档案<Select aria-label="指定档案" autoFocus value={choice} disabled={busy} onChange={setChoice} options={[{value:'',label:'请选择档案'},...(item!.candidates??[]).map(c=>({value:String(c.id),label:`${c.disp||c.warehouse_name}，${c.warehouse_name}${c.status==='archived'?'（归档）':''}${!c.is_placeholder?'（已有仓库，不可扶正）':''}`,disabled:!c.is_placeholder}))]}/></label>}
    {state.kind === 'archive' && <><label>仓库<Select aria-label="仓库" autoFocus value={choice} disabled={busy} onChange={setChoice} options={[{value:'',label:'请选择仓库'},...(item!.warehouses??[]).map(value=>({value,label:value}))]}/></label><p>只为选中的仓库建档，其余仓库不建行。</p></>}
    {state.kind === 'delete' && <>{impact.isPending ? <p role="status">正在核对关联影响…</p> : impact.isError ? <p className="notice" role="alert">{impact.error.message}<Button htmlType="button" onClick={() => void impact.refetch()}>重读影响</Button></p> : <><p className={impact.data.can_delete ? 'danger' : ''}>{impact.data.message}</p>{impact.data.groups.filter(g => g.count > 0).map((g, i) => <details key={i}><summary>{g.label}：{g.count} 条（保留）</summary>{g.rows.map((row, j) => <p key={j}>{['bill_no', 'contract_no', 'batch_no', 'ym', 'year_month', 'doc_date', 'supplier', 'item_name', 'name_full'].map(key => row[key]).filter(v => typeof v === 'string' && v).join('，') || `记录 ${row.id ?? j + 1}`}</p>)}</details>)}</>}</>}
    {state.kind === 'sync' && <>{connection.isPending ? <p role="status">正在核对当前账号的 i8 绑定…</p> : connection.isError ? <p className="notice" role="alert">{connection.error.message}<Button htmlType="button" onClick={() => void connection.refetch()}>重读绑定</Button></p> : <><dl className="project-sync-account"><div><dt>当前账号</dt><dd>{me?.name || me?.account}</dd></div><div><dt>i8 账号</dt><dd>{connection.data.i8_user || '未绑定'}</dd></div></dl>{(!connection.data.ready || connection.data.account !== me?.account) && <p role="alert">{connection.data.message || '账号已变化，请关闭后重新打开。'}</p>}</>}{!done && <p className="project-sync-summary">{state.source === 'warehouses' ? '从 i8 读取仓库名单，将唯一匹配的占位档案扶正；保留原档案及业务关联，需人工核对的逐项列出。' : '从 i8 读取常用项目列表，更新项目档案与待建档项。'}同步可能重新登录 i8，并使该账号其他会话下线。</p>}{receipt && <p role="status">{receipt}</p>}{samples.length > 0 && <details open><summary>{state.source === 'warehouses' ? '扶正与待处理明细' : '需处理项目'}</summary>{samples.map((sample, i) => <p key={i}>{['warehouse_name', 'name_full', 'owner_full_name', 'reason'].map(key => sample[key]).filter(v => typeof v === 'string' && v).join('，')}</p>)}</details>}</>}
    {error && <p className="notice" role="alert">{error}</p>}{busy && <p role="status">正在执行，请稍候…</p>}<div className="dialog-actions"><Button htmlType="button" disabled={busy} onClick={closing.requestClose}>{done ? '关闭' : '取消'}</Button>{!done && <Button htmlType="submit" className={state.kind === 'delete' ? 'danger' : 'primary'} disabled={cannot}>{state.kind === 'delete' ? '确认删除' : state.kind === 'sync' ? '确认同步' : '保存'}</Button>}</div>
  </form></DialogContents></BusinessModal>;
}
