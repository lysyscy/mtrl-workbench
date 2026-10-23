import { useEffect, useId, useMemo, useRef } from 'react';
import { DialogContents, useDialogClose } from './dialog-close';
import { BusinessModal } from './business-modal';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, GridApi } from 'ag-grid-community';
import { gridTheme } from './grid';
import { mechanicalMoney as money, detailNet, detailProblems, detailSum, editDetailRow } from './mechanical-api';
import type { Category, Detail, DetailRow, Effective } from './mechanical-api';
import './mechanical.css';

export interface Draft { warehouse: string; ym: string; category: Category; revision: number; rows: DetailRow[]; version: number }
export const detailKey = (warehouse: string, ym: string, category: Category) => JSON.stringify([warehouse,ym,category]);
export const fields: Record<Category, [string,string][]> = {
  zero: [['device','设备名称'],['spec','规格型号'],['unit','单位'],['qty','数量'],['rate','零租单价'],['amount','合价（元）'],['tax','票种／税率'],['net','不含税价'],['date','租赁日期／期间'],['use','用途'],['team','使用班组'],['reviewer','审核人'],['vendor','出租单位'],['plate','车牌号'],['memo','备注']],
  monthly: [['device','设备名称'],['spec','规格型号'],['unit','单位'],['plan','计划月数'],['used','已包月数'],['rate','包月单价'],['amount','合价（元）'],['net','不含税价'],['date','入场日期'],['vendor','出租单位'],['reviewer','审核人'],['tax','票种／税率'],['oil','含油说明'],['plate','车牌号'],['memo','原备注']],
};
const aliases: Record<string,string> = { use:'usage', vendor:'lessor', memo:'note' };
export function Details({ name, saved, effective, draft, category, ym, keywords, problemsOnly, writable, change, register }: {
  name: string; saved: Detail | undefined; effective: Effective | undefined; draft: Draft | undefined; category: Category; ym: string; warehouse: string; keywords: string[]; problemsOnly: boolean; writable: boolean;
  change: (rows: DetailRow[]) => void; register: (api: GridApi<DetailRow> | null) => void;
}) {
  const rows = draft?.rows ?? saved?.rows ?? [];
  const current = useRef({ rows, change, writable, keywords }); current.current = { rows, change, writable, keywords };
  const api = useRef<GridApi<DetailRow> | null>(null);
  const visible = useMemo(() => problemsOnly ? rows.filter(row => detailProblems(row,category,ym,keywords).length) : rows, [rows,category,ym,keywords,problemsOnly]);
  const gross = draft ? detailSum(rows.map(row => row.amount)) : saved?.totals.gross;
  const net = draft ? detailSum(rows.map(detailNet)) : saved?.totals.net;
  const columns = category === 'zero' ? ['mech_2','mech_4'] : ['mech_3','mech_5'];
  const scale = Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')) || 1;
  const columnDefs = useMemo<ColDef<DetailRow>[]>(() => [
    { colId:'seq',headerName:'序号',pinned:'left',width:56*scale,valueGetter:p => p.data ? current.current.rows.findIndex(row => row.id === p.data!.id)+1 : '' },
    ...fields[category].map(([field,label]): ColDef<DetailRow> => ({
      colId:field,field,headerName:label,pinned:field === 'device' ? 'left' : null,width:(field === 'device' || field === 'memo' || field === 'date' ? 165 : field === 'vendor' ? 180 : 112)*scale,
      editable:field !== 'net' ? () => current.current.writable : false,
      valueGetter:p => p.data ? field === 'net' ? detailNet(p.data) : p.data[field] ?? p.data[aliases[field] ?? ''] ?? '' : '',
      valueFormatter:p => field === 'net' ? money(p.value as string | null) : String(p.value ?? ''),
      cellClass:['amount','rate','net','qty','plan','used'].includes(field) ? 'money' : '',
      cellEditorParams:{maxLength:4000},
      cellClassRules:{ 'mechanical-missing':p => Boolean(p.data && detailProblems(p.data,category,ym,current.current.keywords).includes(field === 'device' ? '设备名称' : field === 'amount' ? '合价' : field === 'tax' ? '票种／税率' : field === 'plate' ? '车牌' : '')) },
    })),
    { colId:'problems',headerName:'待补',width:180*scale,valueGetter:p => p.data ? detailProblems(p.data,category,ym,current.current.keywords).join('、') : '' },
    { colId:'actions',headerName:'操作',width:75*scale,cellRenderer:(p: { data?: DetailRow }) => p.data && current.current.writable ? <button className="mechanical-link danger" onClick={() => current.current.change(current.current.rows.filter(row => row.id !== p.data!.id))}>移除</button> : null },
  ], [category,ym,scale]);
  useEffect(() => { api.current?.refreshCells({force:true}); }, [writable,keywords]);
  return <section className="mechanical-detail-group" aria-label={`${name}${category === 'zero' ? '零租' : '包月'}明细`}>
    <div className="mechanical-detail-head"><h2>{name}</h2><span>{rows.length} 条 · {draft ? '待保存（草稿参考）' : '已保存明细'}</span><button disabled={!writable} onClick={() => { const row = {id:crypto.randomUUID(),device:'',amount:'',tax:''};change([...rows,row]);requestAnimationFrame(() => {const grid=api.current;const node=grid?.getRowNode(row.id);if(node?.rowIndex != null){grid?.ensureIndexVisible(node.rowIndex);grid?.startEditingCell({rowIndex:node.rowIndex,colKey:'device'});}}); }}>增行</button></div>
    <div className="mechanical-detail-totals"><span>明细含税 <strong>{money(gross)}</strong> · 不含税 <strong>{money(net)}</strong>{rows.some(row=>detailNet(row)===null)?`（${rows.filter(row=>detailNet(row)===null).length}条待补）`:''}</span><span>有效月值：含税 {money(effective?.values[columns[0]!])} · 不含税 {money(effective?.values[columns[1]!])}</span></div>
    <div className="mechanical-detail-grid" onInputCapture={event=>{const input=event.target;if(!(input instanceof HTMLInputElement)||!current.current.writable)return;const id=input.closest('[row-id]')?.getAttribute('row-id'),field=input.closest('[col-id]')?.getAttribute('col-id');if(!id||!field||field==='net')return;current.current.change(current.current.rows.map(row=>row.id===id?editDetailRow(row,field,input.value,category):row));}} style={{height:Math.min(420,80+Math.max(rows.length,2)*34)*scale}}>
      <AgGridReact<DetailRow> theme={gridTheme} rowData={visible} columnDefs={columnDefs} getRowId={p => p.data.id} readOnlyEdit singleClickEdit stopEditingWhenCellsLoseFocus suppressScrollOnNewData animateRows={false}
        rowHeight={34*scale} headerHeight={42*scale} defaultColDef={{sortable:false,resizable:true,suppressMovable:true,wrapHeaderText:true,autoHeaderHeight:true}}
        overlayNoRowsTemplate={problemsOnly ? '此项目没有待补字段。' : '尚无明细；可增行，有效月值保留。'}
        onGridReady={event => {api.current=event.api;register(event.api);}} onGridPreDestroyed={() => register(null)}
        onCellEditRequest={event => {const field=event.colDef.field;if(!field || !event.data || !current.current.writable)return;current.current.change(current.current.rows.map(row => row.id === event.data!.id ? editDetailRow(row,field,String(event.newValue ?? ''),category) : row));}} />
    </div>
  </section>;
}

export function MechanicalDialog({ title, close, busy, dirty = false, paused = false, children }: { title: string; close: () => void; busy: boolean; dirty?: boolean; paused?: boolean; children: React.ReactNode | ((requestClose: () => boolean) => React.ReactNode) }) {
  const titleId = useId();
  const closing = useDialogClose({ busy, dirty, close, active: !paused });
  return <BusinessModal open={!paused} requestClose={closing.requestClose} className="mechanical-dialog" titleId={titleId}><DialogContents title={title} titleId={titleId} closing={closing}>{typeof children === 'function' ? children(closing.requestClose) : children}</DialogContents></BusinessModal>;
}
