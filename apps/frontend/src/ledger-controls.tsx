import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { Project } from './api';
import { requestFile } from './api';

export function ProjectPicker({ projects, selected, pick, multiple = false, label, disabled = false, initiallyOpen = false }: {
  projects: Project[]; selected: number[]; pick: (ids: number[]) => void; multiple?: boolean; label: string; disabled?: boolean; initiallyOpen?: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen); const [keyword, setKeyword] = useState('');
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener('pointerdown', close); return () => document.removeEventListener('pointerdown', close);
  }, []);
  return <div className="ledger-project" ref={root} onKeyDown={event => { if (event.key === 'Escape') setOpen(false); }}>
    <button className={open ? 'on' : ''} aria-label={label} aria-expanded={open} disabled={disabled} onClick={() => setOpen(value => !value)}>{multiple ? `已选 ${selected.length} 个项目` : (() => { const item = projects.find(item => selected.includes(item.id)); return item ? `${item.disp || item.name_full}${item.status === 'archived' ? '（归档）' : ''}` : '请选择项目'; })()} ▾</button>
    {open && <div className="ledger-project-menu" role="group" aria-label={multiple ? '导出项目候选' : '查看项目候选'}>
      <label><span>搜索项目</span><input type="search" value={keyword} onChange={event => setKeyword(event.target.value)} /></label>
      {multiple && <div className="picker-actions"><button onClick={() => pick(projects.map(item => item.id))}>全选</button><button onClick={() => pick([])}>清空</button></div>}
      <div className="picker-options">{projects.filter(item => `${item.disp}${item.name_full}${item.warehouse_name ?? ''}`.includes(keyword.trim())).map(item => <button key={item.id} aria-pressed={selected.includes(item.id)} onClick={() => { pick(multiple ? selected.includes(item.id) ? selected.filter(id => id !== item.id) : [...selected, item.id] : [item.id]); if (!multiple) setOpen(false); }}>
        <span>{multiple ? `${selected.includes(item.id) ? '☑' : '☐'} ` : ''}{item.disp || item.name_full}{item.status === 'archived' && <span className="archived">（归档）</span>}</span><small>{item.warehouse_name || '未建仓'} · {item.name_full}</small>
      </button>)}</div>
    </div>}
  </div>;
}

export function reportMonth() {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' }).formatToParts(new Date());
  const year = Number(parts.find(part => part.type === 'year')?.value); const month = Number(parts.find(part => part.type === 'month')?.value);
  return new Date(Date.UTC(year, month - 2, 1)).toISOString().slice(0, 7);
}

export function LedgerExport({ kind, projects, project, unavailable, run, message, valid, signal, paused }: {
  kind: 'ledger' | 'debt'; projects: Project[]; project: number; unavailable: string;
  run: (action: () => Promise<void>, projects: number[]) => Promise<string | null>;
  message: (text: string) => void; valid: () => boolean; signal: AbortSignal | undefined; paused: boolean;
}) {
  const [open, setOpen] = useState(false); const [ids, setIds] = useState<number[] | null>(null);
  const [confirm, setConfirm] = useState(false); const [keyword, setKeyword] = useState('');
  const [feedback, setFeedback] = useState(''); const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null); const trigger = useRef<HTMLButtonElement>(null);
  const title = kind === 'ledger' ? '逐月台账导出' : '总欠款汇总导出';
  const selected = ids ?? (project ? [project] : []);
  const chosen = selected.flatMap(id => { const item = projects.find(item => item.id === id); return item ? [item] : []; });
  const month = reportMonth();
  const scopeError = chosen.length !== selected.length ? '项目范围已变化，请重新选择。' : chosen.some(item => !item.warehouse_name?.trim()) ? '所选项目尚未建仓，请调整范围。' : '';
  const reason = unavailable || scopeError;
  useEffect(() => { if (open) dialog.current?.showModal(); }, [open]);
  useEffect(() => { if (paused) { dialog.current?.close(); setOpen(false); } }, [paused]);
  const close = () => { dialog.current?.close(); setOpen(false); if (!paused && valid()) requestAnimationFrame(() => trigger.current?.focus()); };
  const move = (index: number, offset: number) => {
    const next = [...selected]; [next[index], next[index + offset]] = [next[index + offset]!, next[index]!]; setIds(next);
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
      if (ids === null) setIds(project ? [project] : []);
      setFeedback(''); setConfirm(false); setOpen(true);
    }}>{title}…</button>
    {open && createPortal(<dialog ref={dialog} className="ledger-export-dialog" aria-labelledby={`${kind}-export-title`} onCancel={event => { if (busy) event.preventDefault(); else close(); }} onClose={close}>
      <h2 id={`${kind}-export-title`}>{title}</h2>
      <p>{kind === 'ledger' ? `报告月 ${month} · 每项目3表 · 多项目ZIP` : '实时汇总 · 一项目一行 · 无欠款数据的项目不出行'}</p>
      {!confirm ? <>
        <div className="export-selection-tools"><label><span>搜索项目</span><input type="search" value={keyword} onChange={event => setKeyword(event.target.value)} /></label><button onClick={() => setIds(projects.map(item => item.id))}>全选</button><button onClick={() => setIds([])}>清空</button></div>
        <div className="export-projects" role="group" aria-label="导出项目候选">{projects.filter(item => `${item.disp}${item.name_full}${item.warehouse_name ?? ''}`.includes(keyword.trim())).map(item => <button key={item.id} aria-pressed={selected.includes(item.id)} onClick={() => { setFeedback(''); setIds(selected.includes(item.id) ? selected.filter(id => id !== item.id) : [...selected, item.id]); }}>
          {selected.includes(item.id) ? '☑' : '☐'} {item.disp || item.name_full}{item.status === 'archived' ? '（归档）' : ''}
        </button>)}</div>
        <p>已选 {chosen.length} 个项目</p>
      </> : <>
        <p>{kind === 'ledger' ? chosen.length === 1 ? '将生成1个工作簿。' : `选了${chosen.length}个项目，将生成一个zip。` : `已选 ${chosen.length} 个项目，按以下顺序导出。`}</p>
        <div className="export-table"><table><thead><tr><th>顺序</th><th><button disabled={busy} onClick={() => setIds([...chosen].sort((a, b) => (a.disp || a.name_full).localeCompare(b.disp || b.name_full, 'zh')).map(item => item.id))}>项目排序</button></th><th>调整顺序</th></tr></thead><tbody>{chosen.map((item, index) => <tr key={item.id}><td>{index + 1}</td><td>{item.disp || item.name_full}</td><td><button aria-label={`上移${item.disp || item.name_full}`} disabled={busy || index === 0} onClick={() => move(index, -1)}>上移</button> <button aria-label={`下移${item.disp || item.name_full}`} disabled={busy || index === chosen.length - 1} onClick={() => move(index, 1)}>下移</button></td></tr>)}</tbody></table></div>
      </>}
      {(reason || feedback) && <p className="notice" role="alert">{reason || feedback}</p>}
      {busy && <p role="status">正在生成文件…</p>}
      <div className="dialog-actions"><button disabled={busy} onClick={close}>取消</button>{confirm ? <><button disabled={busy} onClick={() => { setFeedback(''); setConfirm(false); }}>返回选择</button><button className="primary" disabled={Boolean(reason) || busy || !chosen.length} onClick={() => void save()}>保存到本地</button></> : <button className="primary" disabled={Boolean(reason) || !chosen.length} onClick={() => { setFeedback(''); setConfirm(true); }}>确认清单</button>}</div>
    </dialog>, document.body)}
  </>;
}
