import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ColGroupDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { readProjects, requestFile, requestJson } from './api';
import type { Identity } from './api';
import { ProjectPicker } from './ledger-controls';
import { gridTheme } from './grid';
import { readMechanicalReport, readWorkbench } from './mechanical-api';
import type { MechanicalReport, ReportSheet } from './mechanical-api';

interface SummaryRow { id: string; [column: string]: string }
const groupLabels = ['零租', '包月', '合计', '租赁公司内租', '工程公司内租'];
function Summary({ report, projectIds, detail }: { report: MechanicalReport; projectIds: number[]; detail: (sheet: number, name: string) => void }) {
  const api = useRef<GridApi<SummaryRow> | null>(null);
  const [find, setFind] = useState(''); const [feedback, setFeedback] = useState('');
  const scale = Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1;
  const rows = useMemo(() => report.sheets[0]!.rows.slice(5).map((cells, index) => {
    const row: SummaryRow = { id: String(projectIds[index] ?? 'total') };
    for (const cell of cells) row[`c${cell.column - 1}`] = cell.value;
    return row;
  }), [report, projectIds]);
  const columns = useMemo<(ColDef<SummaryRow> | ColGroupDef<SummaryRow>)[]>(() => [
    { field: 'c0', headerName: '序号', pinned: 'left', width: 60 * scale },
    { field: 'c1', headerName: '项目', pinned: 'left', width: 210 * scale, wrapText: true, autoHeight: true },
    { headerName: '开工年月', children: [{ field: 'c2', headerName: '年', width: 75 * scale }, { field: 'c3', headerName: '月', width: 65 * scale, cellClass: 'mechanical-group-end', headerClass: 'mechanical-group-end' }] },
    ...['累计', '当月'].map((name, group) => ({ headerName: name, headerClass: 'mechanical-group-end', children: groupLabels.map((label, index): ColDef<SummaryRow> => ({
      field: `c${4 + group * 5 + index}`, headerName: label, width: (index > 2 ? 140 : 112) * scale, cellClass: index === 4 ? 'money mechanical-group-end' : 'money', headerClass: index === 4 ? 'mechanical-group-end' : '',
      ...(group === 1 && index < 2 ? { cellRenderer: (params: ICellRendererParams<SummaryRow, string>) => params.node.rowPinned || !params.value ? params.value ?? '' : <button className="mechanical-link" aria-label={`${params.data?.c1} ${label}明细`} onClick={() => detail(index + 1, params.data?.c1 ?? '')}>{params.value}</button> } : {}),
    })) })),
    { field: 'c14', headerName: '备注', width: 160 * scale, wrapText: true, autoHeight: true },
  ], [scale, detail]);
  function locate() {
    if (!find.trim()) return;
    const index = rows.slice(0, -1).findIndex(row => row.c1?.includes(find.trim()));
    if (index < 0) { setFeedback('没有匹配项目，请调整名称。'); return; }
    api.current?.ensureIndexVisible(index, 'middle'); api.current?.setFocusedCell(index, 'c1'); setFeedback('');
  }
  return <>
    <form className="mechanical-locate" onSubmit={event => { event.preventDefault(); locate(); }}><label>定位项目<input value={find} onChange={event => setFind(event.target.value)} onKeyDown={event => { if (event.nativeEvent.isComposing && event.key === 'Enter') event.preventDefault(); }} /></label><button type="submit">定位</button>{feedback && <span role="status">{feedback}</span>}</form>
    <div className="mechanical-grid" role="region" aria-label="公司汇总">
      <AgGridReact<SummaryRow> theme={gridTheme} rowData={rows.slice(0, -1)} pinnedBottomRowData={rows.slice(-1)} columnDefs={columns} defaultColDef={{ sortable: false, resizable: true, suppressMovable: true, wrapHeaderText: true, autoHeaderHeight: true }} getRowId={params => params.data.id} rowHeight={34 * scale} headerHeight={34 * scale} groupHeaderHeight={30 * scale} onGridReady={event => { api.current = event.api; }} />
    </div>
  </>;
}
function Sheet({ sheet, index, target }: { sheet: ReportSheet; index: number; target: string }) {
  const root = useRef<HTMLDivElement>(null);
  const headers = index === 0 ? 5 : index === 3 ? 1 : 4;
  useEffect(() => {
    if (!target) return;
    const row = [...(root.current?.querySelectorAll('tbody tr') ?? [])].find(row => [...row.querySelectorAll('td')].some(cell => cell.textContent === target));
    row?.scrollIntoView({ block: 'center' });
  }, [sheet, target]);
  const firstWidth = index === 3 ? 210 : 60;
  const secondWidth = index === 3 ? 120 : 210;
  const columns = Math.max(...sheet.rows.flatMap(row => row.map(cell => cell.column + cell.colspan - 1)));
  function renderRow(cells: ReportSheet['rows'][number], row: number, head: boolean) {
    return <tr key={row}>{cells.map(cell => { const Tag = head ? 'th' : 'td'; return <Tag key={cell.column} className={cell.column + cell.colspan - 1 <= 2 ? 'mechanical-frozen' : ''} style={cell.column + cell.colspan - 1 <= 2 ? { left: cell.column === 1 ? 0 : `calc(${firstWidth}px * var(--fscale))` } : undefined} rowSpan={cell.rowspan} colSpan={cell.colspan}>{cell.value}</Tag>; })}</tr>;
  }
  return <div ref={root} className="mechanical-sheet" tabIndex={0} role="region" aria-label={sheet.name}><table><caption>{sheet.name}</caption><colgroup>{Array.from({ length: columns }, (_, column) => <col key={column} style={{ width: `calc(${column === 0 ? firstWidth : column === 1 ? secondWidth : 120}px * var(--fscale))` }} />)}</colgroup><thead>{sheet.rows.slice(0, headers).map((cells, row) => renderRow(cells, row, true))}</thead><tbody>{sheet.rows.slice(headers).map((cells, row) => renderRow(cells, row, false))}</tbody></table></div>;
}
export function MechanicalPage({ me, blocked, exportGuard }: { me: Identity | null; blocked: boolean; exportGuard: string }) {
  const [month, setMonth] = useState(''); const [ids, setIds] = useState<number[] | null>(null);
  const [sheet, setSheet] = useState<number | null>(null); const [target, setTarget] = useState('');
  const [message, setMessage] = useState(''); const [busy, setBusy] = useState(false);
  const download = useRef<AbortController | null>(null); const previewButton = useRef<HTMLButtonElement>(null);
  const projects = useQuery({ queryKey: ['projects', 'all', ''], enabled: !blocked, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const state = useQuery({ queryKey: ['mechanical-state'], enabled: !blocked, queryFn: async ({ signal }) => readWorkbench(await requestJson('/api/m06/workbench', { signal })) });
  const candidates = useMemo(() => projects.data?.filter(project => state.data?.warehouses.includes(project.warehouse_name ?? '')) ?? [], [projects.data, state.data]);
  const selected = useMemo(() => ids ?? (state.data?.shown.length ? state.data.shown.flatMap(warehouse => candidates.filter(project => project.warehouse_name === warehouse).map(project => project.id)) : candidates.map(project => project.id)), [ids, state.data, candidates]);
  const warehouses = useMemo(() => selected.flatMap(id => candidates.find(project => project.id === id)?.warehouse_name ?? []), [selected, candidates]);
  const ym = month || state.data?.months.at(-1) || '';
  const scopeError = selected.length !== warehouses.length ? '所选项目范围已变化，请重新选择。' : projects.isError || state.isError ? '项目或月份读取失败，请先重新读取。' : '';
  const scope = JSON.stringify([ym, warehouses]);
  const valid = useRef({ scope, blocked, exportGuard, scopeError }); valid.current = { scope, blocked, exportGuard, scopeError };
  const report = useQuery({ queryKey: ['mechanical-report', ym, warehouses], enabled: !blocked && !scopeError && Boolean(ym) && warehouses.length > 0, queryFn: async ({ signal }) => readMechanicalReport(await requestJson(`/api/m06/workbench/preview?${new URLSearchParams({ ym, projects: JSON.stringify(warehouses) })}`, { signal }), ym, warehouses) });
  useEffect(() => { setSheet(null); setTarget(''); setMessage(''); download.current?.abort(); download.current = null; setBusy(false); }, [scope, blocked, exportGuard, scopeError]);
  useEffect(() => () => { download.current?.abort(); }, []);
  const unavailable = !me ? '登录后可下载。' : exportGuard || scopeError || (projects.isFetching || state.isFetching ? '正在核对项目和月份，请稍候。' : blocked ? '账号待核实，请稍候。' : report.isFetching || !report.data || report.isError ? '请先取得完整预览。' : '');
  async function save() {
    if (unavailable || busy || download.current || !report.data) return;
    const controller = new AbortController(); download.current = controller; setBusy(true); setMessage('');
    try {
      const result = await requestFile(`/api/m06/workbench/export?${new URLSearchParams({ ym, projects: JSON.stringify(warehouses), snapshot_token: report.data.snapshot_token })}`, controller.signal);
      if (controller.signal.aborted || valid.current.scope !== scope || valid.current.blocked || valid.current.exportGuard || valid.current.scopeError) return;
      const url = URL.createObjectURL(result.blob); const link = document.createElement('a'); link.href = url; link.download = result.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setMessage('四页文件已导出。');
    } catch (error) { if (!controller.signal.aborted && valid.current.scope === scope) setMessage(error instanceof Error ? error.message : '导出失败，请重新预览后重试。'); }
    finally { if (download.current === controller) { download.current = null; setBusy(false); } }
  }
  function detail(index: number, name: string) { setSheet(index); setTarget(name); }
  const error = projects.error || state.error || report.error;
  return <section className="mechanical-card" aria-labelledby="mechanical-title">
    <div className="card-head"><h1 id="mechanical-title">机械费</h1><button ref={previewButton} disabled={Boolean(scopeError) || !report.data || report.isFetching || report.isError} onClick={() => { setSheet(0); setTarget(''); }}>四页报送预览</button></div>
    <div className="filters"><label htmlFor="mechanical-month">月份</label><select id="mechanical-month" value={ym} disabled={blocked || state.isPending} onChange={event => setMonth(event.target.value)}>{state.data?.months.map(month => <option key={month}>{month}</option>)}</select><ProjectPicker projects={candidates} selected={selected} pick={setIds} multiple label="报表项目" disabled={blocked || projects.isPending || state.isPending} /></div>
    <p className="mechanical-boundary">当前可核对已保存报表。明细编辑、月值确认与取数核对尚未接入。</p>
    {scopeError && !error && <p className="notice" role="alert">{scopeError}</p>}
    {error ? <p className="notice" role="alert">{error.message}<button onClick={() => { void projects.refetch(); void state.refetch(); void report.refetch(); }}>重新读取</button></p> : state.isPending || projects.isPending || report.isFetching ? <p className="state" role="status">正在读取机械报表…</p> : !ym ? <p className="state" role="status">暂无已保存月份，请在现有工作区保存后再查看。</p> : !warehouses.length ? <p className="state" role="status">请选择项目查看报表。</p> : null}
    {report.data && !scopeError && !report.isError && !report.isFetching && warehouses.length > 0 && <>
      {report.data.warnings.length > 0 && <details className="mechanical-warnings"><summary>报表待核对（{report.data.warnings.length}）</summary><ul>{report.data.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
      {sheet === null ? <Summary report={report.data} projectIds={selected} detail={detail} /> : <>
        <div className="mechanical-preview-tools"><button onClick={() => { setSheet(null); setTarget(''); requestAnimationFrame(() => previewButton.current?.focus()); }}>返回公司汇总</button><div role="group" aria-label="四页报表">{report.data.sheets.map((item, index) => <button key={item.name} aria-pressed={sheet === index} onClick={() => { setSheet(index); setTarget(''); }}>{item.name}</button>)}</div><button disabled={Boolean(unavailable) || busy} title={unavailable || '下载当前预览的四页文件'} onClick={() => void save()}>{busy ? '正在生成…' : '下载四页Excel'}</button></div>
        {unavailable && <p className="mechanical-feedback" role="status">{unavailable}</p>}
        <Sheet key={sheet} sheet={report.data.sheets[sheet]!} index={sheet} target={target} />
      </>}
    </>}
    {message && <p className="mechanical-feedback" role="status">{message}{message !== '四页文件已导出。' && <button disabled={busy} onClick={() => void report.refetch()}>重新预览</button>}</p>}
  </section>;
}
