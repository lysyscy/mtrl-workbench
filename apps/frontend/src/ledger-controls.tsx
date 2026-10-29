import { BusinessModal } from './business-modal';
import { ReadGrid } from './business-grid';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import Radio from 'antd/es/radio';
import Select from 'antd/es/select';
import theme from 'antd/es/theme';
import type { Project } from './api';
import { projectLabel, requestFile } from './api';
import { DialogContents, useDialogClose } from './dialog-close';

export function ProjectPicker({ projects: allProjects, selected, pick, multiple = false, label, disabled = false, initiallyOpen = false, emptyLabel = '请选择项目' }: {
  projects: Project[]; selected: number[]; pick: (ids: number[]) => void; multiple?: boolean; label: string; disabled?: boolean; initiallyOpen?: boolean; emptyLabel?: string;
}) {
  const { token } = theme.useToken();
  const projects = allProjects.filter(item => !multiple || item.project_type !== 'shell');
  const [open, setOpen] = useState(initiallyOpen);
  const chosen = selected.map(id => projects.find(item => item.id === id));
  const summary = chosen.length ? chosen.map(item => item ? projectLabel(item) : '项目已失效').join('、') : emptyLabel;
  const options = (['active', 'archived'] as const).map(status => ({ label: status === 'active' ? '在用项目' : '归档项目',
    options: projects.filter(item => item.status === status).map(item => ({ value: item.id, label: projectLabel(item), title: projectLabel(item) })) }));
  const invalid = selected.filter(id => !projects.some(item => item.id === id));
  if (invalid.length) options.push({ label: '已失效', options: invalid.map(value => ({ value, label: '项目已失效', title: '请重新选择项目' })) });
  const listHeight = Math.min((12 + options.filter(group => group.options.length).length) * token.controlHeight, Math.max(token.controlHeight, window.innerHeight - 160));
  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);
  return <span className="business-project-picker" title={summary} style={{ width: `${Math.min(36, Math.max(10, summary.length + 5))}em` }}
    onKeyDown={event => { if (event.key === 'Escape' && open) { event.stopPropagation(); setOpen(false); } }}>
    <Select aria-label={label} value={multiple ? selected : selected[0] ?? null} {...(multiple ? { mode: 'multiple' as const } : {})}
      placeholder={emptyLabel} disabled={disabled} open={open && !disabled} onOpenChange={setOpen}
      showSearch={{ optionFilterProp: 'label' }} options={options} maxTagCount={0} maxTagPlaceholder={() => summary}
      listHeight={listHeight}
      classNames={{ popup: { root: 'business-project-popup ag-custom-component-popup' } }}
      popupMatchSelectWidth={Math.min(560, Math.max(280, summary.length * 14 + 70))}
      getPopupContainer={trigger => (trigger as HTMLElement).closest<HTMLElement>('.ant-modal-container') ?? document.body}
      onChange={(value: number | number[]) => pick(Array.isArray(value) ? value : [value])}
      optionRender={option => <span className="business-project-option">{multiple ? <Checkbox checked={selected.includes(Number(option.value))} tabIndex={-1} aria-hidden /> : <Radio checked={selected.includes(Number(option.value))} tabIndex={-1} aria-hidden />}<span title={String(option.label)}>{option.label}</span></span>}
      popupRender={menu => <>{multiple && <div className="business-project-actions" onMouseDown={event => event.preventDefault()}><Button onClick={() => pick(projects.map(item => item.id))}>全选</Button><Button onClick={() => pick([])}>清空</Button></div>}{menu}</>}
      notFoundContent={projects.length ? '没有匹配的项目' : '暂无可选项目'} />
  </span>;
}

export function reportMonth() {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' }).formatToParts(new Date());
  const year = Number(parts.find(part => part.type === 'year')?.value); const month = Number(parts.find(part => part.type === 'month')?.value);
  return new Date(Date.UTC(year, month - 2, 1)).toISOString().slice(0, 7);
}

interface ExportScopeProps {
  kind: string; owner: string; projects: Project[]; project: number; defaultProjects?: number[]; unavailable: string;
  run: (action: () => Promise<void>, projects: number[]) => Promise<string | null>;
  message: (text: string) => void; valid: () => boolean; signal: AbortSignal | undefined; paused: boolean;
}

export function LedgerExport(props: ExportScopeProps & { kind: 'ledger' | 'debt' }) {
  const { kind } = props;
  const month = reportMonth();
  return <ProjectExport {...props} title={kind === 'ledger' ? '逐月台账导出' : '总欠款汇总导出'}
    description={kind === 'ledger' ? `报告月 ${month}，每项目3表，多项目ZIP` : '实时汇总，一项目一行，无欠款数据的项目不出行'}
    summary={count => kind === 'ledger' ? count === 1 ? '将生成1个工作簿。' : `选了${count}个项目，将生成一个zip。` : `已选 ${count} 个项目，按以下顺序导出。`}
    success={kind === 'ledger' ? '台账已导出。' : '总欠款已导出。'}
    exportFile={(chosen, signal) => {
      const params = new URLSearchParams({ projects: chosen.map(item => item.warehouse_name!).join(',') });
      if (kind === 'ledger') params.set('ym', month);
      return requestFile(`/api/m05/${kind === 'ledger' ? 'ledger' : 'debt'}/export?${params}`, signal);
    }} />;
}

export function ProjectSelectionOrder({ projects, selected, choose, move, disabled, label = '导出项目选择与顺序' }: {
  projects: Project[]; selected: number[]; choose: (ids: number[]) => void; move: (index: number, offset: number) => void; disabled: boolean; label?: string;
}) {
  return <>
    <div className="export-project-actions"><Button disabled={disabled} onClick={() => choose(projects.map(item => item.id))}>全选</Button><Button disabled={disabled} onClick={() => choose([])}>全不选</Button><span role="status">已选 {selected.length} 个项目</span></div>
    <div className="export-project-list" role="group" aria-label={label}>{projects.map((item, index) => <div className="export-project-row" key={item.id}>
      <Checkbox disabled={disabled} checked={selected.includes(item.id)} onChange={event => choose(projects.filter(p => p.id === item.id ? event.target.checked : selected.includes(p.id)).map(p => p.id))}><span title={projectLabel(item)}>{projectLabel(item)}</span></Checkbox>
      <div><Button aria-label={`上移${projectLabel(item)}`} disabled={disabled || index === 0} onClick={() => move(index, -1)}>上移</Button><Button aria-label={`下移${projectLabel(item)}`} disabled={disabled || index === projects.length - 1} onClick={() => move(index, 1)}>下移</Button></div>
    </div>)}</div>
    {!projects.length && <p className="muted">暂无可选项目</p>}
  </>;
}

export function ProjectExport({ kind, owner, projects, project, defaultProjects, unavailable, run, message, valid, signal, paused, title, description, summary, success, exportFile }: ExportScopeProps & {
  title: string; description: string; summary: (count: number) => string; success: string;
  exportFile: (projects: Project[], signal?: AbortSignal) => Promise<{ blob: Blob; filename: string }>;
}) {
  const [open, setOpen] = useState(false); const [ids, setIds] = useState<number[] | null>(null);
  const singleList = kind === 'ledger' || kind === 'debt' || kind === 'mechanical';
  const [order, setOrder] = useState<number[]>([]);
  const [confirm, setConfirm] = useState(false);
  const [feedback, setFeedback] = useState(''); const [busy, setBusy] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const [preferenceError, setPreferenceError] = useState('');
  const preferenceKey = `mtrl:export-projects:v1:${encodeURIComponent(owner)}:${kind}`;
  const initial = defaultProjects ?? (project ? [project] : []);
  const selected = (ids ?? initial).filter(id => projects.some(item => item.id === id));
  const chosen = selected.flatMap(id => { const item = projects.find(item => item.id === id); return item ? [item] : []; });
  const ordered = [...order, ...projects.map(item => item.id).filter(id => !order.includes(id))].flatMap(id => { const item = projects.find(item => item.id === id); return item ? [item] : []; });
  const scopeError = chosen.length !== selected.length ? '项目范围已变化，请重新选择。' : chosen.some(item => !item.warehouse_name?.trim()) ? '所选项目尚未建仓，请调整范围。' : '';
  const reason = unavailable || scopeError;
  const close = () => { setOpen(false); if (!paused && valid()) requestAnimationFrame(() => trigger.current?.focus()); };
  // Selection is an auto-saved preference, not an unsubmitted business draft.
  const closing = useDialogClose({ busy, dirty: false, close });
  function choose(next: number[]) {
    setIds(next); setFeedback('');
    try { localStorage.setItem(preferenceKey, JSON.stringify(next)); setPreferenceError(''); }
    catch { setPreferenceError('本机未能记住选择，刷新后需重选。请检查浏览器是否允许保存数据。'); }
  }
  function restore() {
    try {
      const saved = localStorage.getItem(preferenceKey);
      const value: unknown = saved === null ? initial : JSON.parse(saved);
      if (!Array.isArray(value) || !value.every(id => Number.isSafeInteger(id) && id > 0)) throw new Error('Invalid export preference');
      const restored = [...new Set<number>(value)].filter(id => projects.some(item => item.id === id));
      setOrder([...restored, ...projects.map(item => item.id).filter(id => !restored.includes(id))]);
      choose(restored);
    } catch { setOrder(projects.map(item => item.id)); setIds([]); setPreferenceError('本机记忆未能读取，请重新选择；本次仍可导出。'); }
  }
  const move = (index: number, offset: number) => {
    const next = [...selected]; [next[index], next[index + offset]] = [next[index + offset]!, next[index]!]; choose(next);
  };
  function moveProject(index: number, offset: number) {
    const next = ordered.map(item => item.id);
    [next[index], next[index + offset]] = [next[index + offset]!, next[index]!];
    setOrder(next); choose(next.filter(id => selected.includes(id)));
  }
  async function save() {
    if (reason || busy || !chosen.length) return;
    setBusy(true); setFeedback('');
    const snapshot = [...chosen];
    try {
      const failure = await run(async () => {
        const result = await exportFile(snapshot, signal);
        if (!valid() || signal?.aborted) return;
        const url = URL.createObjectURL(result.blob); const link = document.createElement('a'); link.href = url; link.download = result.filename; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000); close(); message(success);
      }, snapshot.map(item => item.id));
      if (valid() && failure) setFeedback(failure);
    } finally { setBusy(false); }
  }
  return <>
    <Button htmlType="submit" ref={trigger} className="ledger-export-toggle" aria-haspopup="dialog" aria-disabled={Boolean(unavailable)} title={unavailable || title} onClick={() => {
      if (unavailable) return;
      restore();
      setFeedback(''); setConfirm(false); setOpen(true);
    }}>{title}…</Button>
    {open && createPortal(<BusinessModal open={open && !paused} className={`ledger-export-dialog${singleList ? ' ledger-project-export' : ''}`} titleId={`${kind}-export-title`} requestClose={closing.requestClose}><DialogContents title={title} titleId={`${kind}-export-title`} closing={closing}>
      <p>{description}</p>
      <p className="muted">项目与顺序自动记在本机，关闭不撤销选择；清除浏览器数据或换设备需重选。</p>
      {preferenceError && <p className="notice" role="alert">{preferenceError}</p>}
      {singleList ? <>
        <ProjectSelectionOrder projects={ordered} selected={selected} choose={choose} move={moveProject} disabled={busy} />
        <p className="muted">{summary(chosen.length)}</p>
      </> : !confirm ? <>
        <ProjectPicker projects={projects} selected={selected} pick={choose} multiple initiallyOpen label="导出项目" emptyLabel="请选择项目" disabled={busy} />
        <p>已选 {chosen.length} 个项目</p>
      </> : <>
        <p>{summary(chosen.length)}</p>
        <><Button disabled={busy} onClick={()=>choose([...chosen].sort((a,b)=>projectLabel(a).localeCompare(projectLabel(b),'zh')).map(item=>item.id))}>项目排序</Button><ReadGrid table={'export-project-order-'+kind} className="export-table" label="导出项目顺序" domLayout="autoHeight" rows={chosen} rowId={item=>String(item.id)} columns={[
          {colId:'sequence',headerName:'顺序',valueGetter:p=>chosen.findIndex(item=>item.id===p.data!.id)+1},
          {colId:'project',headerName:'项目',valueGetter:p=>projectLabel(p.data!)},
          {colId:'actions',headerName:'调整顺序',cellRenderer:({data:item}:{data:Project})=>{const index=chosen.findIndex(p=>p.id===item.id);return <><Button aria-label={'上移'+projectLabel(item)} disabled={busy||index===0} onClick={()=>move(index,-1)}>上移</Button> <Button aria-label={'下移'+projectLabel(item)} disabled={busy||index===chosen.length-1} onClick={()=>move(index,1)}>下移</Button></>; }},
        ]}/></>
      </>}
      {(reason || feedback) && <p className="notice" role="alert">{reason || feedback}</p>}
      {busy && <p role="status">正在生成文件…</p>}
      <div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>关闭</Button>{singleList ? <Button htmlType="submit" className="primary" disabled={Boolean(reason)||busy||!chosen.length} onClick={()=>void save()}>保存到本地</Button> : confirm ? <><Button htmlType="submit" disabled={busy} onClick={() => { setFeedback(''); setConfirm(false); }}>返回选择</Button><Button htmlType="submit" className="primary" disabled={Boolean(reason) || busy || !chosen.length} onClick={() => void save()}>保存到本地</Button></> : <Button htmlType="submit" className="primary" disabled={Boolean(reason) || !chosen.length} onClick={() => { setFeedback(''); setConfirm(true); }}>确认清单</Button>}</div>
    </DialogContents></BusinessModal>, document.body)}
  </>;
}
