import App from 'antd/es/app';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Tag from 'antd/es/tag';
import { createContext, useContext, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ColGroupDef, ICellRendererParams } from 'ag-grid-community';
import { readProjects, requestJson } from './api';
import type { Identity, Project } from './api';
import { pageGridGeometry, contentWidth, fixedWidth, gridTheme } from './grid';
import { ProjectSelectionOrder, reportMonth } from './ledger-controls';
import { TimePicker } from './time-picker';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { useCellSaveQueue } from './use-cell-save';
import { money } from './notices-api';
import { SettlementExport } from './settlement-export';
import { getBig, saveBigCell, saveBigSelection } from './big-api';
import type { AutoKey, BigData, BigRow, DerivedKey, ManualKey, TotalKey } from './big-api';
import { PreparedGrid, useGridPresentation } from './grid-presentation';
const bigRowId = (row: BigRow) => row.warehouse;
const emptyBig: BigRow[] = [];

type Props = { me: Identity | null; blocked: boolean; active: boolean };
const labels: Record<ManualKey,string> = {open_ym:'开工时间',mech_est:'机械费测算',contract:'合同（预估）价',output_cum:'产值累计（含税）',oil:'工程用油',note:'备注'};
interface Draft { warehouse: string; display: string; key: ManualKey; value: string; original: string; error: string; revision: number }
const keyOf = (warehouse: string,key: ManualKey) => JSON.stringify([warehouse,key]);
interface Cells {
  drafts: Record<string,Draft>; disabled: boolean;
  change: (row: BigRow,key: ManualKey,value: string) => void;
  save: (key: string,retry?: boolean) => void; cancel: (key: string) => void;
}
const BigCells = createContext<Cells | null>(null);
function ManualInput({data,node,colDef}: ICellRendererParams<BigRow>) {
  const cells = useContext(BigCells)!;
  if (!data || node.rowPinned) return null;
  const field = colDef!.colId as ManualKey, key = keyOf(data.warehouse,field), draft = cells.drafts[key], cell = data.manual[field];
  return <div className={`big-manual${draft?.error ? ' has-error' : ''}`}>
    <Input aria-label={`${data.display}，${labels[field]}`} value={draft?.value ?? cell.value ?? ''} disabled={cells.disabled}
      placeholder="待填" status={draft?.error ? 'error' : ''} title={draft?.error || (cell.from ? `带入自 ${cell.from}；修改保存为本月值，清空恢复带入` : cell.value === null ? '尚未录入' : '本月录入；清空恢复带入')}
      className={`record-value${field === 'note' || field === 'open_ym' ? '' : ' big-money-input'}`}
      onChange={e => cells.change(data,field,e.target.value)} onBlur={() => cells.save(key)} onKeyDown={e => {
        e.stopPropagation(); if(e.nativeEvent.isComposing) return;
        if(e.key === 'Enter') {e.preventDefault();cells.save(key,true);}
        if(e.key === 'Escape') cells.cancel(key);

      }} />
    {draft?.error ? <Tag className="big-origin-tag">保存失败</Tag> : cell.from ? <Tag className="big-carry-tag" title={`带入自 ${cell.from}`}>{cell.from} 带入</Tag> : cell.value !== null ? <span className="big-origin">本月</span> : null}
  </div>;
}

export function BigPage(props: Props) {
  const [ym,setYm] = useState(reportMonth), [visited,setVisited] = useState(() => [ym]);
  const projects = useQuery({queryKey:['projects','all'],enabled:props.active && !props.blocked,queryFn:async({signal}) => readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  function choose(value: string) {setYm(value);setVisited(old => old.includes(value) ? old : [...old,value]);}
  return <section className="big-page" aria-label="月度会大表">
    <div data-page-chrome className="big-period"><label>核算月<TimePicker label="大表核算月" value={ym} onChange={choose} modes={['月']} disabled={props.blocked} /></label></div>
    {visited.map(month => <div className="big-month" key={month} hidden={month !== ym} inert={month !== ym}><BigMonth {...props} ym={month} active={props.active && month === ym} projects={projects.data ?? []} projectsError={projects.error?.message ?? ''} retryProjects={() => void projects.refetch()} /></div>)}
  </section>;
}

function BigMonth({ym,me,blocked,active,projects,projectsError,retryProjects}: Props & {ym:string;projects:Project[];projectsError:string;retryProjects:()=>void}) {
  const root = useRef<HTMLDivElement>(null), client = useQueryClient();
  const {message}=App.useApp();
  const queryKey = ['big',ym];
  const query = useQuery({queryKey,enabled:active && !blocked,queryFn:({signal}) => getBig(ym,signal)});
  const [picking,setPicking]=useState(false),revision=useRef(0);
  const saves=useCellSaveQueue<Draft,BigData>({
    enabled:active&&!blocked&&Boolean(me),canWrite:!query.isPending&&!query.isError,stopOnRejection:true,
    read:reload,
    write:(draft,signal)=>saveBigCell(ym,draft.warehouse,draft.key,draft.value,signal),
    validate:draft=>query.data?.rows.some(row=>row.warehouse===draft.warehouse)?'':'项目已不在大表中，请取消此项或重新选题。',
    acknowledge:(current,submitted)=>current.revision===submitted.revision?undefined:{...current,original:submitted.value},
    saved:()=>'',
  },{key:`big:${ym}`,label:'大表',pending:picking});
  const {drafts,busy,uncertain,verified,error}=saves;
  const dirty = Object.keys(drafts).length > 0;
  const disabled = blocked || !active || !me || uncertain || query.isPending || query.isError;
  const controlsDisabled = disabled || busy || dirty || query.isFetching;
  async function reload() {
    await client.invalidateQueries({refetchType:'none'});
    await client.cancelQueries({queryKey,exact:true});
    if(me)void client.invalidateQueries({queryKey:['history',`${me.id}:${me.account}`],exact:true});
    return client.fetchQuery({queryKey,staleTime:0,queryFn:({signal}) => getBig(ym,signal)});
  }
  const save=saves.save;
  async function selection(selected: string[]) {
    if(controlsDisabled)return false;
    const saved=await saves.run(signal=>saveBigSelection(ym,selected,signal),()=>'')==='saved';
    if(saved)void message.success('项目与顺序已保存。');
    return saved;
  }
  const reconcileExport=()=>saves.reconcile('导出结果待核实，请重读核对本月名单。');
  const scale=Number(me?.ui_scale_css ?? 1);
  const columns=useMemo<(ColDef<BigRow>|ColGroupDef<BigRow>)[]>(() => {
    function value(key: AutoKey|DerivedKey|ManualKey,p: {data:BigRow|undefined;node?:{rowPinned?:string|null|undefined}|null}) {
      if(p.node?.rowPinned) return (p.data as unknown as {totals:BigData['totals']})?.totals[key as TotalKey] ?? null;
      if(!p.data) return null;
      return key in p.data.auto ? p.data.auto[key as AutoKey] : key in p.data.derived ? p.data.derived[key as DerivedKey] : p.data.manual[key as ManualKey].value;
    }
    const context = document.createElement('canvas').getContext('2d');
    const font = getComputedStyle(document.documentElement);
    if (context) context.font = `600 ${Number(font.getPropertyValue('--font-ui-size')) || 13.5}px ${font.getPropertyValue('--fs')}`;
    const digitWidth=Math.max(...[...'0123456789'].map(char=>context?.measureText(char).width ?? 8.2));
    const textWidth=(text:string)=>[...text].reduce((width,char)=>width+(/\d/.test(char)?digitWidth:context?.measureText(char).width ?? 8.2),0);
    if(context) context.font=`400 ${Number(font.getPropertyValue('--font-ui-size')) || 13.5}px ${font.getPropertyValue('--fs')}`;
    const dateWidth=Math.ceil((context?.measureText('8888-88').width ?? 58) + 10);
    if(context) context.font=`600 ${Number(font.getPropertyValue('--font-ui-size')) || 13.5}px ${font.getPropertyValue('--fs')}`;
    const amountWidth = (key: AutoKey|DerivedKey|ManualKey, editable = false) => {
      const values = (query.data?.rows ?? []).map(row => value(key,{data:row}));
      values.push(query.data?.totals[key as TotalKey] ?? null);
      const texts = values.map(amount => amount == null ? '—' : key.endsWith('rate') ? `${(Number(amount)*100).toFixed(1)}%` : money(String(amount)));
      // The shared density uses 4px on each side, plus the cell borders.
      const edge=['hw_cum','rent_cum','mat_cum','oil','output_rate'].includes(key)?11:10;
      const width = Math.ceil(Math.max(key.endsWith('rate') ? 20 : editable ? 80 : 0, ...texts.map(text => textWidth(text) + (editable ? 14 : edge))));
      return contentWidth(width,Math.max(width + 48,editable ? 160 : 0),scale,1);
    };
    const number=(key:AutoKey|DerivedKey,label:string,tip?:string):ColDef<BigRow> => ({colId:key,headerName:label,headerTooltip:tip ?? label,headerClass:key.endsWith('rate')?'big-rate-header':'',cellClass:'big-money',wrapText:true,autoHeight:true,valueGetter:p=>value(key,p),valueFormatter:p=>p.value==null?(p.node?.rowPinned?'':'—'):key.endsWith('rate') ? `${(Number(p.value)*100).toFixed(1)}%` : money(String(p.value)),...amountWidth(key)});
    const manual=(key:ManualKey):ColDef<BigRow> => ({colId:key,headerName:labels[key],headerTooltip:key==='open_ym'?'开工时间，YYYY-MM':labels[key],cellClass:key==='note'?'big-manual-cell':'big-manual-cell big-money',wrapText:true,autoHeight:true,valueGetter:p=>value(key,p),cellRendererSelector:p=>p.node.rowPinned?undefined:{component:ManualInput},valueFormatter:p=>p.value==null?'':key==='open_ym'||key==='note'?String(p.value):money(String(p.value)),...(key==='note' ? contentWidth(40,240,scale,1) : key==='open_ym' ? contentWidth(dateWidth,112,scale) : amountWidth(key,true))});
    const boundary = (column: ColDef<BigRow>): ColDef<BigRow> => ({...column,headerClass:`${column.headerClass ?? ''} big-group-start`,cellClass:`${column.cellClass ?? ''} big-group-start`});
    return [
      {headerName:'项目',marryChildren:true,children:[
        {field:'seq',headerName:'序号',pinned:'left',valueGetter:p=>p.node?.rowPinned?'':p.data?.seq,...fixedWidth(Math.max(40,Math.ceil(textWidth(String(query.data?.rows.length ?? 0)) + 12)),scale)},
        {field:'display',headerName:'项目名称',pinned:'left',wrapText:true,autoHeight:true,...contentWidth(46,180,scale,1)},
        {...manual('open_ym'),pinned:'left'},
      ]},
      {headerName:'辅材使用（不含税）',headerClass:'big-group-start',marryChildren:true,children:[boundary(number('hw_cum','焊材累计','提取合计：历史值＋所选年12个月，原单入库金额')),number('hw_mon','焊材当月'),number('qt_cum','三气累计','气体提取合计：历史值＋所选年12个月，原单入库金额'),number('qt_mon','三气当月')]},
      {headerName:'机械使用与测算',headerClass:'big-group-start',marryChildren:true,children:[boundary(number('rent_cum','外租机械开工累计','有效零租含税＋包月含税，开工累计')),number('rent_mon','外租机械当月'),number('lease_cum','设备租赁开工累计','有效内租设备，开工累计'),number('lease_mon','设备租赁当月'),number('total_cum','合计','外租机械开工累计＋设备租赁开工累计'),manual('mech_est'),number('use_rate','使用率','合计÷机械费测算；零分母留空')]},
      {headerName:'产值',headerClass:'big-group-start',marryChildren:true,children:[boundary(number('output_rate','产值完成率','产值累计÷合同（预估）价；零分母留空')),manual('contract'),manual('output_cum')]},
      boundary(number('mat_cum','主材累计（含税）','本项目纳入集采台账的合同结算合计')),boundary(manual('oil')),boundary(manual('note')),
    ];
  },[scale,query.data]);
  const total=useMemo(() => query.data?.rows.length ? [{warehouse:'__total',display:'合计',totals:query.data.totals} as unknown as BigRow] : [],[query.data]);
  const presentation = useGridPresentation({table: 'monthly-big', root, active, rows: query.data?.rows ?? emptyBig, totals: total, columns, rowId: bigRowId, scale, scope: ym, identity: ym});
  return <>
    <div data-page-chrome className="big-toolbar"><div className="big-project-state"><span className="big-count">{query.data ? `${query.data.rows.length} 个项目` : ''}</span>{query.data && <span className="big-selection-source">{query.data.selection.fixed ? `${ym} 名单已固定` : query.data.selection.source === 'legacy' ? '沿用原项目名单，待固定' : query.data.selection.source === 'default' ? '默认项目名单，待固定' : `名单沿用 ${query.data.selection.source}，待固定`}</span>}</div><div className="big-export-actions">
      <Button disabled={blocked||busy||!dirty} onMouseDown={e=>e.preventDefault()} onClick={()=>saves.update(()=>({}))}>取消未保存修改</Button>
      <Button disabled={controlsDisabled || !!projectsError || !query.data} onClick={()=>setPicking(true)}>选择项目与排序…</Button>
      <SettlementExport method="POST" onSettled={reconcileExport} scope={`${ym} 月度会大表`} url={`/api/m07/big/export?${new URLSearchParams({period:ym})}`} paused={!active || blocked} disabled={controlsDisabled || !query.data?.rows.length}>
        <p>{ym}，{query.data?.rows.length} 个项目，原模板 Excel</p><ol className="big-export-list">{query.data?.rows.map(r=><li key={r.warehouse}>{r.display}</li>)}</ol>
      </SettlementExport>
    </div></div>
    {(error || query.isError || projectsError) && <p className="notice" role="alert">{error || query.error?.message || projectsError}<Button disabled={busy || blocked} onClick={()=>{
      retryProjects();void saves.reread();
    }}>重读核对</Button></p>}
    {uncertain && <p className="notice" role="alert">核对刚才的保存结果后再继续。<Button disabled={!verified || busy || query.isFetching || query.isError} onClick={()=>{saves.confirm();}}>已核对，继续</Button></p>}
    {Object.entries(drafts).filter(([,d])=>d.error).map(([id,d])=><div className="big-draft" key={id}><span>{d.display}，{labels[d.key]}：{d.value || '清空，恢复带入'}<span role="alert">，{d.error}</span></span>
      <Button size="small" disabled={disabled || busy} onMouseDown={e=>e.preventDefault()} onClick={()=>save(id,true)}>保存这项</Button>
      <Button size="small" disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>{saves.update(drafts=>{const next={...drafts};delete next[id];return next;});}}>取消修改</Button></div>)}
    {query.isPending ? <p role="status">正在读取月度会大表…</p> : query.data && <BigCells.Provider value={{drafts,disabled,save,
      change:(row,key,value)=>{const id=keyOf(row.warehouse,key);saves.update((drafts,writing)=>{const old=drafts[id],next={...drafts,[id]:{warehouse:row.warehouse,display:row.display,key,value,original:old?.original??row.manual[key].value??'',error:'',revision:++revision.current}};if(!writing&&value===next[id]!.original)delete next[id];return next;});},
      cancel:id=>saves.update((drafts,writing)=>{if(writing)return drafts;const next={...drafts};delete next[id];return next;})}}>
      {!query.data.mat_available && <p className="notice">主材累计暂不可得，请先核对集采取数。</p>}
      <PreparedGrid presentation={presentation} className={`big-grid${query.data.rows.length ? '' : ' is-empty'}`} grid={{theme:gridTheme,domLayout:'autoHeight',
        getRowId:p=>p.data.warehouse,defaultColDef:{resizable: true,sortable:false,suppressMovable:true,wrapHeaderText:true,suppressKeyboardEvent:e=>e.event.target instanceof HTMLInputElement},
        groupHeaderHeight:pageGridGeometry(scale).groupHeaderHeight,suppressScrollOnNewData:true,suppressColumnVirtualisation:true,
        overlayNoRowsTemplate:`<span>${query.data.candidates.length ? '未选择项目，请使用“选择项目与排序”。' : '当前没有在建非壳项目，请核对项目档案。'}</span>`,
}} />
    </BigCells.Provider>}
    {picking && query.data && <ProjectOrder data={query.data} projects={projects} busy={busy} disabled={controlsDisabled} paused={!active || blocked} save={selection} close={()=>setPicking(false)} />}
  </>;
}

function ProjectOrder({data,projects,busy,disabled,paused,save,close}:{data:BigData;projects:Project[];busy:boolean;disabled:boolean;paused:boolean;save:(selected:string[])=>Promise<boolean>;close:()=>void}) {
  const available=projects.filter(p=>data.candidates.some(c=>c.warehouse===p.warehouse_name));
  const [selected,setSelected]=useState(()=>[...data.selected]);
  const [order,setOrder]=useState(()=>[...data.selected,...data.candidates.map(c=>c.warehouse).filter(wh=>!data.selected.includes(wh))]);
  const ordered=order.flatMap(wh=>available.filter(p=>p.warehouse_name===wh));
  const dirty=selected.join('\0')!==data.selected.join('\0');
  const closing=useDialogClose({busy,dirty,close,active:!paused});
  function move(index:number,offset:number) {const next=[...order];[next[index],next[index+offset]]=[next[index+offset]!,next[index]!];setOrder(next);setSelected(next.filter(wh=>selected.includes(wh)));}
  const missing=data.candidates.some(c=>!available.some(p=>p.warehouse_name===c.warehouse));
  return <BusinessModal open={!paused} requestClose={closing.requestClose} titleId="big-order-title" className="big-order-dialog"><DialogContents title={`${data.month}，选择项目与排序`} titleId="big-order-title" closing={closing}>
    <ProjectSelectionOrder projects={ordered} selected={selected.flatMap(wh=>available.filter(p=>p.warehouse_name===wh).map(p=>p.id))} choose={ids=>setSelected(ids.flatMap(id=>{const p=available.find(p=>p.id===id);return p?.warehouse_name?[p.warehouse_name]:[];}))} move={move} disabled={busy || disabled || missing} label="大表项目选择与顺序" />
    <p className="big-order-summary">{selected.length} 个项目，页面与导出同序</p>
    {missing && <p className="notice" role="alert">项目档案已变化，请关闭后重读再选。</p>}
    {!selected.length && <p>保存后大表为空；以后可重新选择项目。</p>}
    <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" loading={busy} disabled={disabled || missing || (!dirty && data.selection.fixed)} onClick={()=>void save([...selected]).then(ok=>{if(ok)close();})}>保存项目与顺序</Button></div>
  </DialogContents></BusinessModal>;
}
