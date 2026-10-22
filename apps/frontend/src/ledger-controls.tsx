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
      <label>搜索项目<input type="search" value={keyword} onChange={event => setKeyword(event.target.value)} /></label>
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

export function LedgerExport({ projects, project, disabled, run, message, valid, signal, paused }: {
  projects: Project[]; project: number; disabled: boolean; run: (action: () => Promise<void>) => Promise<void>; message: (text: string) => void; valid: () => boolean; signal: AbortSignal | undefined; paused: boolean;
}) {
  const [open, setOpen] = useState(false); const [ids, setIds] = useState<number[]>([]);
  const [preview, setPreview] = useState<Project[] | null>(null); const [sort, setSort] = useState({ column: 'seq', descending: false });
  const dialog = useRef<HTMLDialogElement>(null); const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (preview) dialog.current?.showModal(); else { dialog.current?.close(); trigger.current?.focus(); } }, [preview]);
  useEffect(() => { if (paused) { dialog.current?.close(); setPreview(null); } }, [paused]);
  const chosen = projects.filter(item => ids.includes(item.id));
  const shown = preview ? [...preview].sort((a, b) => (sort.column === 'name' ? (a.disp || a.name_full).localeCompare(b.disp || b.name_full, 'zh') : preview.indexOf(a) - preview.indexOf(b)) * (sort.descending ? -1 : 1)) : [];
  const month = reportMonth();
  return <>
    <button className={`ledger-export-toggle primary${open ? ' on' : ''}`} aria-expanded={open} disabled={disabled} onClick={() => { if (!open && !ids.length) setIds(project ? [project] : []); setOpen(value => !value); }}>批量导出（先选项目）…</button>
    {open && createPortal(<div className="ledger-export-strip">
      <div className="export-line"><b>① 逐月台账</b><span>项目（可多选）</span><ProjectPicker key="export" projects={projects} selected={ids} pick={setIds} multiple label="导出项目（可多选）" disabled={disabled} initiallyOpen />
        <button ref={trigger} className="primary" disabled={disabled || !chosen.length} onClick={() => { setSort({ column: 'seq', descending: false }); setPreview(chosen); }}>导出台账</button><button onClick={() => { setOpen(false); setIds([]); }}>取消</button></div>
      <p>{chosen.length}个项目 · 每项目3表 · 报告月{month} · 多项目ZIP</p>
      <div className="export-line export-debt"><b>② 总欠款汇总</b><span>本次预览尚未接入</span><a href="/app">打开旧版预览</a></div>
    </div>, document.getElementById('ledger-export-slot')!)}
    {preview && <dialog ref={dialog} className="ledger-export-dialog" onCancel={() => setPreview(null)} onClose={() => setPreview(null)}>
      <h2>导出 · 逐月欠款台账（每项目一个工作簿）</h2><p>{preview.length === 1 ? '将生成1个工作簿' : `选了${preview.length}个项目，将生成一个zip，内含${preview.length}个工作簿`}；每本3个工作表。</p>
      <table><thead><tr>{[['seq', '#'], ['name', '工作簿（每项目一个）'], ['sheets', '工作表']].map(([key, label]) => <th key={key}><button onClick={() => setSort(value => ({ column: key!, descending: value.column === key ? !value.descending : false }))}>{label} ↕</button></th>)}</tr></thead><tbody>{shown.map(item => <tr key={item.id}><td>{preview.indexOf(item) + 1}</td><td>{item.disp || item.name_full}_欠款台账_{month}.xlsx</td><td>辅材欠款 / 机械欠款 / 特殊费用月报表</td></tr>)}</tbody></table>
      <div className="dialog-actions"><button onClick={() => setPreview(null)}>关闭</button><button className="primary" disabled={disabled} onClick={() => { const snapshot = preview; void run(async () => {
        const result = await requestFile(`/api/m05/ledger/export?${new URLSearchParams({ projects: snapshot.map(item => item.warehouse_name || item.name_full).join(','), ym: month })}`, signal);
        if (!valid() || signal?.aborted) return;
        const url = URL.createObjectURL(result.blob); const link = document.createElement('a'); link.href = url; link.download = result.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setPreview(null); message('台账已导出。');
      }); }}>保存到本地</button></div>
    </dialog>}
  </>;
}
