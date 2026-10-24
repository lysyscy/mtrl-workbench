import Button from 'antd/es/button';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { Identity } from './api';
import { readProjects, requestJson } from './api';
import { contentWidth, fitGridColumns, gridTheme, pageGridGeometry } from './grid';
import { ProjectPicker, reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { money } from './notices-api';
import { getFeeYear } from './fees-api';
import type { FeeYearData, FeeYearRow } from './fees-api';
import { FeeScope } from './fees-month';
import './fees.css';

export function FeesPage({ me, blocked, active }: { me: Identity | null; blocked: boolean; active: boolean }) {
  const [year, setYear] = useState(() => reportMonth().slice(0,4)), [project, setProject] = useState('');
  const [detail, setDetail] = useState<{year: string; project: string; month: string} | null>(null);
  const projects = useQuery({ queryKey: ['projects','all'], enabled: active && !blocked, queryFn: async ({ signal }) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=', { signal })) });
  const query = useQuery({ queryKey: ['fees-year',year,project], enabled: active && !blocked, queryFn: ({ signal }) => getFeeYear(year,project,signal) });
  useEffect(() => { if (!project && query.data?.project) setProject(query.data.project); }, [project,query.data]);
  const ready = query.data && query.data.year === year && query.data.project === project;
  function open(month?: string) {
    if (ready) setDetail({ year, project, month: month ?? `${year}-${reportMonth().slice(5)}` });
  }
  return <section className="fees-page" aria-label="特殊费用">
    <div className="fee-filters"><label>年份<TimePicker label="费用年份" modes={['年']} value={year} onChange={setYear} disabled={blocked} /></label>
      <label>项目<ProjectPicker projects={(projects.data ?? []).filter(p => p.warehouse_name && p.project_type !== 'shell')} selected={(projects.data ?? []).filter(p => p.warehouse_name === project).map(p => p.id)}
        pick={ids => { const next = projects.data?.find(p => p.id === ids[0])?.warehouse_name; if (next) setProject(next); }} label="费用项目" disabled={blocked || projects.isPending} /></label>
    </div>
    <div className="fee-toolbar"><Button disabled={!ready || !me || blocked || !active || query.isFetching || !query.data?.can_edit} onClick={() => open()}>增加手填项</Button>
      <span className="muted">随逐月欠款台账导出 · 特殊费用月报表</span></div>
    {(projects.isError || query.isError) && <p role="alert" className="notice">{projects.error?.message || query.error?.message}<Button onClick={() => { void projects.refetch(); void query.refetch(); }}>重读</Button></p>}
    {query.isPending ? <p role="status">正在读取费用…</p> : ready && <FeeYearTable data={query.data!} scale={Number(me?.ui_scale_css ?? 1)} open={open} />}
    {detail && <FeeDetails key={`${detail.year}:${detail.project}`} {...detail} me={me} blocked={blocked} active={active} close={() => setDetail(null)} />}
  </section>;
}

function FeeYearTable({ data, scale, open }: { data: FeeYearData; scale: number; open: (month?: string) => void }) {
  const root = useRef<HTMLDivElement>(null);
  const columns = useMemo<ColDef<FeeYearRow>[]>(() => {
    const width = (values: (string | null)[]) => {
      const min = Math.max(56, ...values.map(v => v === null ? 0 : money(v).length * 8.2 + 20));
      return contentWidth(min,min+48,scale,1);
    };
    const amount = (index: number) => (p: ICellRendererParams<FeeYearRow>) => {
      if (!p.data) return null;
      const value = index < 0 ? p.data.prior : index > 11 ? p.data.total : p.data.months[index]!;
      const text = value === null ? '' : money(value);
      if (p.node.rowPinned || !p.data.manual) return text;
      const month = index < 0 ? p.data.periods.find(ym => ym < `${data.year}-01`) : index > 11 ? p.data.periods.find(ym => ym.startsWith(data.year)) : `${data.year}-${String(index+1).padStart(2,'0')}`;
      return <button className="fee-amount-link" aria-label={`${p.data.item || '未命名'} ${index < 0 ? '往年' : index > 11 ? '累计' : `${index+1}月`}明细`} onClick={() => open(month)}>{text || '—'}</button>;
    };
    return [
      { field:'item',headerName:'费用项名称',pinned:'left',wrapText:true,autoHeight:true,...contentWidth(144,260,scale,1),valueFormatter:p => p.value || '未命名',cellRenderer:(p:ICellRendererParams<FeeYearRow>) => p.node.rowPinned || !p.data?.manual ? p.value : <button className="fee-name-link" onClick={() => open(p.data?.periods.find(ym => ym.startsWith(data.year)) ?? p.data?.periods[0])}>{p.value || '未命名'}</button> },
      { field:'prior',headerName:'往年',cellClass:'money',cellRenderer:amount(-1),...width([...data.rows.map(r => r.prior),data.prior]) },
      ...Array.from({length:12},(_,i):ColDef<FeeYearRow> => ({colId:`month-${i+1}`,headerName:`${i+1}月`,cellClass:'money',valueGetter:p => p.data?.months[i],cellRenderer:amount(i),...width([...data.rows.map(r => r.months[i]!),data.months[i]!])})),
      { field:'total',headerName:'累计',headerTooltip:'往年 + 所选年1至12月',cellClass:'money',cellRenderer:amount(12),...width([...data.rows.map(r => r.total),data.total]) },
    ];
  },[data,scale,open]);
  const totals: FeeYearRow[] = [{item:'合计',manual:false,prior:data.prior,months:data.months,total:data.total,periods:[]}];
  return <div ref={root} className="fees-grid fees-annual-grid" aria-label="特殊费用年度表"><AgGridReact<FeeYearRow> theme={gridTheme} domLayout="autoHeight" rowData={data.rows} columnDefs={columns} pinnedBottomRowData={totals}
    getRowId={p => JSON.stringify(p.data.item)} defaultColDef={{resizable:true,sortable:false,suppressMovable:true}} rowHeight={pageGridGeometry(scale).rowHeight} headerHeight={pageGridGeometry(scale).headerHeight}
    suppressScrollOnNewData suppressColumnVirtualisation onGridReady={e => fitGridColumns(e.api,root.current,true)} onFirstDataRendered={e => fitGridColumns(e.api,root.current,true)} onGridSizeChanged={e => fitGridColumns(e.api,root.current)} onRowDataUpdated={e => fitGridColumns(e.api,root.current,true)} /></div>;
}

function FeeDetails({ project, month, me, blocked, active, close }: {year:string;project:string;month:string;me:Identity|null;blocked:boolean;active:boolean;close:()=>void}) {
  const [ym,setYm] = useState(month), [visited,setVisited] = useState([month]);
  const [states,setStates] = useState<Record<string,{busy:boolean;dirty:boolean}>>({});
  const status = useCallback((key:string,busy:boolean,dirty:boolean) => setStates(old => old[key]?.busy === busy && old[key]?.dirty === dirty ? old : {...old,[key]:{busy,dirty}}),[]);
  const busy = Object.values(states).some(s => s.busy), dirty = Object.values(states).some(s => s.dirty);
  const closing = useDialogClose({busy,dirty,close,active:active && !blocked});
  return <BusinessModal open={active && !blocked} requestClose={closing.requestClose} className="fee-details-dialog fees-page" titleId="fee-details-title"><DialogContents title="特殊费用 · 月份明细" titleId="fee-details-title" closing={closing}>
    <div className="fee-filters"><label>核算月<TimePicker label="费用明细核算月" modes={['月']} value={ym} disabled={busy} onChange={next => {setYm(next);setVisited(old => old.includes(next) ? old : [...old,next]);}} /></label><span className="muted">{project}</span></div>
    {visited.map(value => <div key={value} hidden={ym !== value} inert={ym !== value}><FeeScope ym={value} project={project} me={me} blocked={blocked} active={active && ym === value && !closing.confirming} status={status} /></div>)}
    <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>关闭</Button></div>
  </DialogContents></BusinessModal>;
}
