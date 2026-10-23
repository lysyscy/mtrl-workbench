import { BoundedTable } from './bounded-table';
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { Project } from './api';
import { projectLabel, requestFile } from './api';
import { DialogContents, useDialogClose } from './dialog-close';
import './project-picker.css';

export function ProjectPicker({ projects, selected, pick, multiple = false, label, disabled = false, initiallyOpen = false, emptyLabel = '请选择项目' }: {
  projects: Project[]; selected: number[]; pick: (ids: number[]) => void; multiple?: boolean; label: string; disabled?: boolean; initiallyOpen?: boolean; emptyLabel?: string;
}) {
  const [open, setOpen] = useState(false); const [keyword, setKeyword] = useState('');
  const trigger = useRef<HTMLButtonElement>(null); const panel = useRef<HTMLDivElement>(null); const name = useId();
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const chosen = projects.filter(item => selected.includes(item.id));
  const summary = chosen.length ? chosen.map(projectLabel).join('、') : emptyLabel;
  const matches = projects.filter(item => projectLabel(item).toLocaleLowerCase().includes(keyword.trim().toLocaleLowerCase()));
  const close = () => panel.current?.hidePopover();
  useEffect(() => { if (disabled) close(); else if (initiallyOpen) panel.current?.showPopover(); }, [disabled, initiallyOpen]);
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const anchor = trigger.current?.getBoundingClientRect(), pop = panel.current?.getBoundingClientRect();
      if (!anchor || !pop) return;
      const gap = 6, viewport = document.documentElement.clientWidth;
      setPosition({ left: Math.max(gap, Math.min(anchor.left, viewport - pop.width - gap)), top: Math.max(gap, Math.min(anchor.bottom + gap, window.innerHeight - pop.height - gap)) });
    };
    place(); window.addEventListener('resize', place); window.addEventListener('scroll', place, true);
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); };
  }, [open, keyword, projects]);
  return <div className="ledger-project project-picker" onKeyDown={event => { if (open && event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); trigger.current?.focus(); } }}>
    <button ref={trigger} type="button" className={open ? 'on' : ''} aria-label={label} aria-expanded={open} aria-controls={`${name}-options`} disabled={disabled} title={summary} onClick={() => { if (open) close(); else panel.current?.showPopover(); }}><span>{summary}</span><svg aria-hidden="true" viewBox="0 0 12 12"><path d="m3 4.5 3 3 3-3" /></svg></button>
    <div ref={panel} className="ledger-project-menu" id={`${name}-options`} popover="auto" style={position} onToggle={event => setOpen(event.newState === 'open')} role="group" aria-label={multiple ? '导出项目候选' : '查看项目候选'}>
      <label className="project-picker-search"><span>搜索项目</span><input type="search" value={keyword} onChange={event => setKeyword(event.target.value)} /></label>
      {multiple && <div className="picker-actions"><button type="button" onClick={() => pick(projects.map(item => item.id))}>全选</button><button type="button" onClick={() => pick([])}>清空</button></div>}
      <div className="picker-options">{(['active', 'archived'] as const).map(status => {
        const items = matches.filter(item => item.status === status);
        return items.length > 0 && <fieldset key={status}><legend>{status === 'archived' ? '归档项目' : '在用项目'}</legend>{items.map(item => <label className="project-picker-option" key={item.id}>
          <input type={multiple ? 'checkbox' : 'radio'} name={name} checked={selected.includes(item.id)} onClick={() => { if (!multiple) { close(); trigger.current?.focus(); } }} onChange={() => { pick(multiple ? selected.includes(item.id) ? selected.filter(id => id !== item.id) : [...selected, item.id] : [item.id]); if (!multiple) { close(); trigger.current?.focus(); } }} />
          <span>{projectLabel(item)}</span>
        </label>)}</fieldset>;
      })}{!matches.length && <p className="project-picker-empty" role="status">{projects.length ? '没有匹配的项目' : '暂无可选项目'}</p>}</div>
    </div>
  </div>;
}

export function reportMonth() {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' }).formatToParts(new Date());
  const year = Number(parts.find(part => part.type === 'year')?.value); const month = Number(parts.find(part => part.type === 'month')?.value);
  return new Date(Date.UTC(year, month - 2, 1)).toISOString().slice(0, 7);
}

export function LedgerExport({ kind, owner, projects, project, unavailable, run, message, valid, signal, paused }: {
  kind: 'ledger' | 'debt'; owner: string; projects: Project[]; project: number; unavailable: string;
  run: (action: () => Promise<void>, projects: number[]) => Promise<string | null>;
  message: (text: string) => void; valid: () => boolean; signal: AbortSignal | undefined; paused: boolean;
}) {
  const [open, setOpen] = useState(false); const [ids, setIds] = useState<number[] | null>(null);
  const [confirm, setConfirm] = useState(false); const [keyword, setKeyword] = useState('');
  const [feedback, setFeedback] = useState(''); const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null); const trigger = useRef<HTMLButtonElement>(null);
  const [preferenceError, setPreferenceError] = useState('');
  const preferenceKey = `mtrl:export-projects:v1:${encodeURIComponent(owner)}:${kind}`;
  const title = kind === 'ledger' ? '逐月台账导出' : '总欠款汇总导出';
  const selected = (ids ?? (project ? [project] : [])).filter(id => projects.some(item => item.id === id));
  const chosen = selected.flatMap(id => { const item = projects.find(item => item.id === id); return item ? [item] : []; });
  const month = reportMonth();
  const scopeError = chosen.length !== selected.length ? '项目范围已变化，请重新选择。' : chosen.some(item => !item.warehouse_name?.trim()) ? '所选项目尚未建仓，请调整范围。' : '';
  const reason = unavailable || scopeError;
  useEffect(() => { if (open && !paused) { if (!dialog.current?.open) dialog.current?.showModal(); } else dialog.current?.close(); }, [open,paused]);
  const close = () => { dialog.current?.close(); setOpen(false); if (!paused && valid()) requestAnimationFrame(() => trigger.current?.focus()); };
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
      const value: unknown = saved === null ? (project ? [project] : []) : JSON.parse(saved);
      if (!Array.isArray(value) || !value.every(id => Number.isSafeInteger(id) && id > 0)) throw new Error('Invalid export preference');
      choose([...new Set<number>(value)].filter(id => projects.some(item => item.id === id)));
    } catch { setIds([]); setPreferenceError('本机记忆未能读取，请重新选择；本次仍可导出。'); }
  }
  const move = (index: number, offset: number) => {
    const next = [...selected]; [next[index], next[index + offset]] = [next[index + offset]!, next[index]!]; choose(next);
  };
  async function save() {
    if (reason || busy || !chosen.length) return;
    setBusy(true); setFeedback('');
    const snapshot = [...chosen];
    try {
      const failure = await run(async () => {
        const params = new URLSearchParams({ projects: snapshot.map(item => item.warehouse_name!).join(',') });
        if (kind === 'ledger') params.set('ym', month);
        const result = await requestFile(`/api/m05/${kind === 'ledger' ? 'ledger' : 'debt'}/export?${params}`, signal);
        if (!valid() || signal?.aborted) return;
        const url = URL.createObjectURL(result.blob); const link = document.createElement('a'); link.href = url; link.download = result.filename; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000); close(); message(kind === 'ledger' ? '台账已导出。' : '总欠款已导出。');
      }, snapshot.map(item => item.id));
      if (valid() && failure) setFeedback(failure);
    } finally { setBusy(false); }
  }
  return <>
    <button ref={trigger} className="ledger-export-toggle" aria-haspopup="dialog" aria-disabled={Boolean(unavailable)} title={unavailable || title} onClick={() => {
      if (unavailable) return;
      restore();
      setFeedback(''); setConfirm(false); setOpen(true);
    }}>{title}…</button>
    {open && createPortal(<dialog ref={dialog} className="ledger-export-dialog" aria-labelledby={`${kind}-export-title`} {...closing.dialogProps}><DialogContents title={title} titleId={`${kind}-export-title`} closing={closing}>
      <p>{kind === 'ledger' ? `报告月 ${month} · 每项目3表 · 多项目ZIP` : '实时汇总 · 一项目一行 · 无欠款数据的项目不出行'}</p>
      <p className="muted">项目与顺序自动记在本机，关闭不撤销选择；清除浏览器数据或换设备需重选。</p>
      {preferenceError && <p className="notice" role="alert">{preferenceError}</p>}
      {!confirm ? <>
        <div className="export-selection-tools"><label><span>搜索项目</span><input type="search" value={keyword} onChange={event => setKeyword(event.target.value)} /></label><button onClick={() => choose(projects.map(item => item.id))}>全选</button><button onClick={() => choose([])}>清空</button></div>
        <div className="export-projects" role="group" aria-label="导出项目候选">{projects.filter(item => `${item.disp}${item.name_full}${item.warehouse_name ?? ''}`.includes(keyword.trim())).map(item => <button key={item.id} aria-pressed={selected.includes(item.id)} onClick={() => { setFeedback(''); choose(selected.includes(item.id) ? selected.filter(id => id !== item.id) : [...selected, item.id]); }}>
          {selected.includes(item.id) ? '☑' : '☐'} {projectLabel(item)}{item.status === 'archived' ? '（归档）' : ''}
        </button>)}</div>
        <p>已选 {chosen.length} 个项目</p>
      </> : <>
        <p>{kind === 'ledger' ? chosen.length === 1 ? '将生成1个工作簿。' : `选了${chosen.length}个项目，将生成一个zip。` : `已选 ${chosen.length} 个项目，按以下顺序导出。`}</p>
        <div className="export-table"><BoundedTable columns={[{ min: 4, max: 6 },{ min: 10, max: 28, flex: 1 },{ min: 10, max: 14 }]}><thead><tr><th>顺序</th><th><button disabled={busy} onClick={() => choose([...chosen].sort((a, b) => projectLabel(a).localeCompare(projectLabel(b), 'zh')).map(item => item.id))}>项目排序</button></th><th>调整顺序</th></tr></thead><tbody>{chosen.map((item, index) => <tr key={item.id}><td>{index + 1}</td><td>{projectLabel(item)}</td><td><button aria-label={`上移${projectLabel(item)}`} disabled={busy || index === 0} onClick={() => move(index, -1)}>上移</button> <button aria-label={`下移${projectLabel(item)}`} disabled={busy || index === chosen.length - 1} onClick={() => move(index, 1)}>下移</button></td></tr>)}</tbody></BoundedTable></div>
      </>}
      {(reason || feedback) && <p className="notice" role="alert">{reason || feedback}</p>}
      {busy && <p role="status">正在生成文件…</p>}
      <div className="dialog-actions"><button disabled={busy} onClick={closing.requestClose}>关闭</button>{confirm ? <><button disabled={busy} onClick={() => { setFeedback(''); setConfirm(false); }}>返回选择</button><button className="primary" disabled={Boolean(reason) || busy || !chosen.length} onClick={() => void save()}>保存到本地</button></> : <button className="primary" disabled={Boolean(reason) || !chosen.length} onClick={() => { setFeedback(''); setConfirm(true); }}>确认清单</button>}</div>
    </DialogContents></dialog>, document.body)}
  </>;
}
