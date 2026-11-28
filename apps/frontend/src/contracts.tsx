import { useAmountComparator } from './use-amount-comparator';
import { DialogPresence } from './workspace-motion';
import { searchWithinRows, useGridSearch } from './grid-search';
import { AnimatePresence } from 'motion/react';
import Button from 'antd/es/button';
import App from 'antd/es/app';
import Checkbox from 'antd/es/checkbox';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import { readProjects, requestJson } from './api';
import type { Identity } from './api';
import { ProjectPicker } from './ledger-controls';
import { pageGridGeometry, fixedWidth, gridTheme } from './grid';
import { contentColumn } from './grid-content-widths';
import { EllipsisText, TextPreview } from './grid-text';
import { GridWidthContext, useGridWidthColumns, useGridWidths } from './grid-widths';
import { useRetainedGridColumns } from './grid-layout';
import { EnumTag } from './enum-tag';
import { useHistoryGuard } from './history';
import { contractApprovalStatuses, contractMoneyKeys, nextArchiveNumbers, contractWrite, readContracts, contractHistoryDate, contractRemarkText, historyContractRemark } from './contracts-api';
import { contractColumnWidth, contractTotalSamples, isContractAmount } from './contract-column-widths';
import type { ContractRow } from './contracts-api';
import { cents, decimal, money, receipt, searchKey } from './notices-api';
import { ContractEditor, archiveNoHint } from './contract-dialog';
import { createInlineFieldQueue } from './inline-field-queue';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { ContractFetch, ContractSettings } from './contract-tools';
import { ContractExports } from './contract-export';
import { ContractSubtableDialog } from './contract-subtables';
import { useContractSubtables } from './use-contract-subtables';
import { ReadFailure, ReadPlaceholder, ReadStatusLane, readPhase } from './read-region';

const defaultColumn: ColDef<ContractRow> = {sortable:true,resizable:true,suppressMovable:true,suppressAutoSize:true,wrapText:false,autoHeight:false,wrapHeaderText:false,autoHeaderHeight:false};
const contractRowId = (row: ContractRow) => row.id;

type ContractSelection={visibleCount:number;selectedVisible:number;pending:boolean;chooseAll:(checked:boolean)=>void};
const ContractSelectionContext=createContext<ContractSelection>(null!);
function ContractSelectionHeader(){
  const {visibleCount, selectedVisible, pending, chooseAll} = useContext(ContractSelectionContext);
  return <Checkbox aria-label="选择当前合同" disabled={pending}
    checked={visibleCount > 0 && selectedVisible === visibleCount}
    indeterminate={selectedVisible > 0 && selectedVisible < visibleCount}
    onChange={event => chooseAll(event.target.checked)} />;
}
const amountSubtables = new Map<string, { kind: 'supplier' | 'trade' | 'payment'; label: string }>([
  ['inv_sum', {kind: 'supplier', label: '供应商发票'}],
  ['trade_inv_sum', {kind: 'trade', label: '贸易公司发票'}],
  ['pay_sum', {kind: 'payment', label: '付款'}],
]);
const approvalOptions = ['', ...contractApprovalStatuses, '无状态'].map(value => ({ value, label: value || '全部' }));
const initialFilters=()=>({projects:[] as number[],tag:'纳入台账',arch:'',approval:''});
const inlineKeys = ['remark','arch_no','ret_date','payment_term','payment_method'] as const;
type InlineKey = typeof inlineKeys[number];
type InlineControl={disabled:boolean;methods:string[];drafts:Record<string,string>;change:(id:number,key:InlineKey,value:string)=>void;save:(row:ContractRow,key:InlineKey|'arch',value:string)=>Promise<boolean>;remark:(row:ContractRow,value:string)=>void;next:(row:ContractRow)=>string;advance:(row:ContractRow)=>Promise<void>};
const VALID_DATE=/^\d{4}-\d{2}-\d{2}$/;
function ContractInlineCell(p:ICellRendererParams<ContractRow>&{editKey:InlineKey;control:()=>InlineControl;scrolling?:boolean}){
  const row=p.data!,key=p.editKey,name=`${row.id}:${key}`,control=p.control();
  const value=control.drafts[name]??(key==='remark'?contractRemarkText(row.remark??''):row[key]);
  const [text,setText]=useState(value), [methodIntent,setMethodIntent]=useState<'focus'|'open'|null>(null);
  useEffect(()=>setText(value),[value]);
  if(p.node.rowPinned)return null;
  if (key === 'payment_method' && p.scrolling && !methodIntent) {
    return <button className="contract-scroll-method" type="button" role="combobox" aria-expanded={false} aria-haspopup="listbox"
      aria-label={`${row.contract_no||row.material} 合同付款方式`} disabled={control.disabled}
      onFocus={event => { if (event.currentTarget.matches(':focus-visible')) setMethodIntent('focus'); }}
      onPointerDown={event => { if (event.pointerType === 'mouse' && event.button === 0) { event.preventDefault(); setMethodIntent('open'); } }}
      onClick={() => setMethodIntent('open')}>
      {text?<EnumTag kind="payMethod" value={text}/>:'未约定'}</button>;
  }
  if(key==='payment_method')return <Select autoFocus={methodIntent !== null} defaultOpen={methodIntent === 'open'} className="contract-inline-select" aria-label={`${row.contract_no||row.material} 合同付款方式`} value={text} disabled={control.disabled} options={['',...control.methods].map(value=>({value,label:value?<EnumTag kind="payMethod" value={value}/>: '未约定'}))} onChange={value=>{setText(value);p.control().change(row.id,key,value);void p.control().save(row,key,value);}}/>;
  return <TextPreview text={text}><Input className={key==='arch_no'?'record-value record-hint':'record-value'} onDoubleClick={key==='remark'?()=>p.control().remark(row,text):undefined} aria-label={`${row.contract_no||row.material} ${key==='remark'?'备注':key==='arch_no'?'存档号':key==='payment_term'?'账期':'寄回日期'}`} type={key==='ret_date'?'date':'text'} value={text} maxLength={key==='remark'?255-(contractHistoryDate(row.remark)?historyContractRemark(contractHistoryDate(row.remark),'').length:0):key==='arch_no'||key==='payment_term'?32:undefined} disabled={control.disabled} placeholder={key==='arch_no'?archiveNoHint(control.next(row)):'可填'} onChange={e=>{const next=e.target.value;setText(next);p.control().change(row.id,key,next);if(key==='ret_date'&&VALID_DATE.test(next))void p.control().save(row,key,next);}} onBlur={()=>void p.control().save(row,key,text)} onKeyDown={e=>{if(e.key!=='Enter'||e.nativeEvent.isComposing)return;e.preventDefault();if(key==='arch_no'&&!text.trim()){const next=p.control().next(row);setText(next);p.control().change(row.id,key,next);return;}void p.control().save(row,key,text);}}/></TextPreview>;
}
function ContractRemarkEditor({ row, initial, busy, disabled, paused, error, save, close }: { row:ContractRow;initial:string;busy:boolean;disabled:boolean;paused:boolean;error:string;save:(value:string)=>Promise<boolean>;close:()=>void }) {
  const [text,setText]=useState(initial);
  const closing=useDialogClose({busy,dirty:text!==initial,close,active:!paused});
  const date=contractHistoryDate(row.remark),maxLength=255-(date?historyContractRemark(date,'').length:0);
  return <BusinessModal open={!paused} className="contract-work-dialog contract-remark-editor" titleId="contract-remark-title" requestClose={closing.requestClose}><DialogContents title="编辑合同备注" titleId="contract-remark-title" closing={closing}>
    <p className="muted">{row.contract_no||row.material}{date?`，历史核对截至 ${date}`:''}</p>
    <Input.TextArea autoFocus aria-label="合同备注全文" value={text} maxLength={maxLength} showCount disabled={busy||disabled} onChange={event=>setText(event.target.value)}/>
    {error&&<p className="notice" role="alert">{error}</p>}
    <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button className="primary" disabled={busy||disabled} onClick={()=>void save(text).then(ok=>{if(ok)close();})}>{busy?'正在保存…':'保存'}</Button></div>
  </DialogContents></BusinessModal>;
}
export function ContractsPage({ me,blocked,active }: { me:Identity|null;blocked:boolean;active:boolean }) {
  const { message }=App.useApp();
  const announce=(text:string)=>{void message.success({key:'contract-success',content:text,duration:3});};
  const client=useQueryClient(),grid=useRef<GridApi<ContractRow>|null>(null),root=useRef<HTMLDivElement>(null),lock=useRef(false),pendingFocus=useRef(0);
  const { applied: search, pending: searchBusy, input: searchInput, reset: setSearch } = useGridSearch(active && !blocked);
  const [filters,setFilters]=useState(initialFilters),[picked,setPicked]=useState<Set<number>>(()=>new Set()),[trade,setTrade]=useState(false);
  const editorSequence=useRef(0);
  const [editors,setEditors]=useState<Record<string,{row:ContractRow|null;materialOnly:boolean;presenceId:number}>>({}),[editorId,setEditorId]=useState<string|null>(null),[tool,setTool]=useState<'fetch'|'party'|null>(null);
  function openEditor(row:ContractRow|null,materialOnly=Boolean(row)){const key=row?`${row.id}:${materialOnly?'material':'full'}`:'new',presenceId=++editorSequence.current;setEditors(old=>old[key]?old:{...old,[key]:{row,materialOnly,presenceId}});setEditorId(key);}
  function closeEditor(key:string){setEditors(old=>{const next={...old};delete next[key];return next;});setEditorId(current=>current===key?null:current);}
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[uncertain,setUncertain]=useState(false);
  const [params]=useSearchParams();
  const [inlineDrafts,setInlineDrafts]=useState<Record<string,string>>({}),[subtable,setSubtable]=useState<{row:ContractRow;kind:'supplier'|'trade'|'payment'}|null>(null);
  const [remarkEditor,setRemarkEditor]=useState<{row:ContractRow;initial:string}|null>(null);
  function openRemark(row:ContractRow,value:string){setRemarkEditor({row,initial:value});}
  const inlineDraftRef=useRef(inlineDrafts);inlineDraftRef.current=inlineDrafts;
  const subtables=useContractSubtables(me?.id,!blocked&&active&&Boolean(me)),[sort,setSort]=useState('');
  const query=useQuery({queryKey:['contracts'],enabled:!blocked&&active,refetchOnMount:'always',queryFn:async({signal})=>readContracts(await requestJson('/api/m11/list',{signal}))});
  const projects=useQuery({queryKey:['projects','all'],enabled:!blocked&&active,queryFn:async({signal})=>readProjects(await requestJson('/api/m01/projects?status=all&keyword=',{signal}))});
  const rows=useMemo(()=>query.data?.rows??[],[query.data?.rows]);
  const compareAmounts = useAmountComparator(rows);
  const archiveNumbers=useMemo(()=>nextArchiveNumbers(rows),[rows]);
  const nextArchiveNo=(row:ContractRow)=>archiveNumbers.get(row.project_key)??'1';
  const projectRows=useMemo(()=>projects.data??[],[projects.data]);
  const projectNames = useMemo(() => {
    const names = new Map<string | null, string>();
    for (const project of projectRows) {
      if (!names.has(project.warehouse_name)) names.set(project.warehouse_name, project.disp);
    }
    return names;
  }, [projectRows]);
  const scope = useMemo(() => {
    const warehouses = new Set(projectRows.filter(project => filters.projects.includes(project.id)).map(project => project.warehouse_name));
    return rows.filter(row =>
      (!filters.tag || row.tag === filters.tag) &&
      (!filters.arch || (row.arch || '未存档') === filters.arch) &&
      (!filters.approval || (row.approve_status ?? '无状态') === filters.approval) &&
      (!filters.projects.length || warehouses.has(row.project_key)));
  }, [rows, projectRows, filters]);
  const searchable = useMemo(() => (query.data?.columns ?? []).filter(column => column.key !== 'ops'), [query.data?.columns]);
  const needle = searchKey(search);
  const find = useMemo(() => searchWithinRows(scope, (row, needle) =>
    searchKey(projectNames.get(row.project_key) ?? '').includes(needle) ||
      searchable.some(column => {
        const value = row[column.key as keyof ContractRow];
        const text = value === null && (contractMoneyKeys as readonly string[]).includes(column.key) ? '未确定' : String(value ?? '');
        const normalized = searchKey(text);
        return normalized.includes(needle) || (column.type === 'date' && normalized.replaceAll('-', '/').includes(needle));
      })), [scope, projectNames, searchable]);
  const shown = useMemo(() => find(needle), [find, needle]);
  const totalRow=useMemo(()=>shown.length?[{id:-1,material:'合计',...Object.fromEntries(contractMoneyKeys.map(key=>[key,decimal(shown.reduce((sum,row)=>sum+cents(row[key]??'0'),0n))]))} as ContractRow]:[],[shown]);
  const selected = useMemo(() => rows.filter(row => picked.has(row.id)), [rows, picked]);
  const hidden = useMemo(() => {
    if (!selected.length) return 0;
    const visible = new Set(shown.map(row => row.id));
    return selected.filter(row => !visible.has(row.id)).length;
  }, [selected, shown]);
  const unavailable=blocked||!active||!me||busy||uncertain||query.isPending||query.isError||query.isFetching||!projects.data||projects.isError;
  useHistoryGuard('contracts',()=>busy||lock.current||subtables.summary.busy?'集采合同正在处理，请稍候。':uncertain||subtables.summary.uncertain?'合同操作结果待核实，请先重读。':subtables.summary.dirty?'合同子表有未保存输入，请先处理。':Object.keys(inlineDraftRef.current).length?'合同收发登记有未保存输入，请先处理。':'');
  useEffect(()=>{const valid=new Set(rows.map(row=>row.id));setPicked(old=>{const next=new Set([...old].filter(id=>valid.has(id)));return next.size===old.size?old:next;});},[rows]);
  useEffect(()=>{if(!active)return;const id=Number(params.get('contract'));if(id>0&&query.data){const row=query.data.rows.find(row=>row.id===id);pendingFocus.current=id;if(row){setEditorId(null);setFilters({...initialFilters(),tag:''});setSearch('');grid.current?.ensureNodeVisible(node=>node.data?.id===id,'middle');}else {setEditorId(null);setError('合同已不在列表中，请重读核对。');}}},[params.get('contract'),active,Boolean(query.data)]);
  useEffect(()=>{if(active&&grid.current)grid.current.refreshCells({force:true});},[uncertain]);
  async function refresh(){
    await client.invalidateQueries({refetchType:'none'});
    if(me)void client.invalidateQueries({queryKey:['history',`${me.id}:${me.account}`],exact:true});
    await client.cancelQueries({queryKey:['contracts'],exact:true});
    await client.fetchQuery({queryKey:['contracts'],staleTime:0,queryFn:async({signal})=>readContracts(await requestJson('/api/m11/list',{signal}))});
  }
  async function reread(){try{await refresh();setUncertain(false);setError('');announce('已重读合同。');}catch(failure){setError(failure instanceof Error?failure.message:'重读失败，请重试。');}}
  async function tag(ids:number[],value:string){
    if(unavailable||lock.current||!ids.length)return;
    lock.current=true;setBusy(true);setError('');let written=false;
    try{const result=await contractWrite('/api/m11/tag',{ids,tag:value});written=true;setPicked(old=>new Set([...old].filter(id=>!ids.includes(id))));await refresh();announce(receipt(result));}
    catch(failure){setUncertain(true);setError(`${written?'标记已保存，列表重读失败。':'标记结果待核实。'}${failure instanceof Error?failure.message:'请重读核对。'}勿重复操作。`);}
    finally{lock.current=false;setBusy(false);}
  }
  function changeInline(id:number,key:InlineKey,value:string){const next={...inlineDraftRef.current,[`${id}:${key}`]:value};inlineDraftRef.current=next;setInlineDrafts(next);}
  const fieldQueue=useRef(createInlineFieldQueue());
  const fieldScope=useRef({blocked,active,owner:me?`${me.id}:${me.account}`:'',uncertain});fieldScope.current={blocked,active,owner:me?`${me.id}:${me.account}`:'',uncertain};
  useEffect(()=>{fieldScope.current.blocked=blocked;return()=>{fieldScope.current.blocked=true;fieldQueue.current.reject();};},[]);
  function saveField(row:ContractRow,key:InlineKey|'arch',value:string,notify=key==='arch'):Promise<boolean> {
    if(blocked||!active||!me||uncertain||query.isError||!query.data)return Promise.resolve(false);
    const name=`${row.id}:${key}`,owner=fieldScope.current.owner;
    return fieldQueue.current.push(name,async()=>{
      const scope=fieldScope.current;if(scope.blocked||!scope.active||scope.uncertain||scope.owner!==owner)return false;
      const latest=client.getQueryData<{rows:ContractRow[]}>(['contracts'])?.rows.find(r=>r.id===row.id)??row;
      const history=key==='remark'?contractHistoryDate(latest.remark):'',next=history?historyContractRemark(history,value):value.trim();
      let written=false;
      try{
        if(next!==latest[key]){
          const result=await contractWrite('/api/m11/fields',{id:latest.id,fields:{[key]:next}});
          written=true;await refresh();
          if(notify)announce(key==='arch'?`存档状态已更新为「${next}」。`:receipt(result));
        }
        if(inlineDraftRef.current[name]===value){
          const copy={...inlineDraftRef.current};delete copy[name];inlineDraftRef.current=copy;inlineControl.current.drafts=copy;setInlineDrafts(copy);
          const node=grid.current?.getRowNode(String(latest.id));
          if(node)grid.current?.refreshCells({force:true,rowNodes:[node],columns:[key]});
        }
        return true;
      }catch(failure){
        setUncertain(true);
        setError(`${written?'登记已保存，列表重读失败。':'登记结果待核实。'}${failure instanceof Error?failure.message:'请重读核对。'}勿重复操作。`);
        return false;
      }
    },()=>{void drainFieldQueue();});
  }
  async function drainFieldQueue() {
    setBusy(true);lock.current=true;setError('');
    try{
      while(true){
        const task=fieldQueue.current.take();
        if(!task)break;
        const scope=fieldScope.current;
        if(scope.blocked||!scope.active||scope.uncertain){fieldQueue.current.reject();task.settle(false);break;}
        let ok=false;
        try{ok=await task.run();}catch{ok=false;}
        task.settle(ok);
        if(!ok){fieldQueue.current.reject();break;}
      }
    }finally{fieldQueue.current.release();lock.current=false;setBusy(false);}
  }
  const actionDisabled=(active&&blocked)||!me||uncertain||query.isPending||query.isError||!projects.data||projects.isError;
  const inlineDisabled=actionDisabled||busy&&!fieldQueue.current.running;
  const paymentMethodsKey=JSON.stringify(query.data?.payment_methods??[]);
  const nextArch=(arch:string)=>!arch||arch==='未存档'?'资产处':arch==='资产处'?'已存档':'未存档';
  const advancing=useRef(false);
  async function advance(row:ContractRow) {
    if(blocked||!active||actionDisabled||advancing.current)return;
    advancing.current=true;
    try{
      const draft=inlineDraftRef.current[`${row.id}:arch_no`];
      if(draft!==undefined&&!await saveField(row,'arch_no',draft,false))return;
      const latest=client.getQueryData<{rows:ContractRow[]}>(['contracts'])?.rows.find(r=>r.id===row.id)??row;
      await saveField(latest,'arch',nextArch(latest.arch));
    }finally{advancing.current=false;}
  }
  const inlineControl=useRef<InlineControl>({disabled:inlineDisabled,methods:query.data?.payment_methods??[],drafts:inlineDrafts,change:changeInline,save:saveField,remark:openRemark,next:nextArchiveNo,advance});
  inlineControl.current={disabled:inlineDisabled,methods:query.data?.payment_methods??[],drafts:inlineDrafts,change:changeInline,save:saveField,remark:openRemark,next:nextArchiveNo,advance};
  const painted = useRef({inlineDisabled, actionDisabled, paymentMethodsKey, rows, picked, shown});
  useEffect(() => {
    const api = grid.current;
    if (!active || !api || api.isDestroyed()) return;
    const before = painted.current;
    painted.current = {inlineDisabled, actionDisabled, paymentMethodsKey, rows, picked, shown};
    const columns = new Set<string>();
    if (inlineDisabled !== before.inlineDisabled) for (const key of inlineKeys) columns.add(key);
    if (paymentMethodsKey !== before.paymentMethodsKey) columns.add('payment_method');
    if (rows !== before.rows) columns.add('arch_no');
    if (actionDisabled !== before.actionDisabled) columns.add('actions');
    if (picked !== before.picked || shown !== before.shown) columns.add('select');
    if (columns.size) api.refreshCells({force:true, columns:[...columns]});
  }, [active, inlineDisabled, actionDisabled, paymentMethodsKey, rows, picked, shown]);
  const state=useRef({unavailable,actionDisabled,picked,shown,tag,advance});state.current={unavailable,actionDisabled,picked,shown,tag,advance};
  const visibleCount = shown.length;
  const selectedVisible = selected.length - hidden;
  const selection=useMemo<ContractSelection>(()=>({visibleCount,selectedVisible,pending:searchBusy,chooseAll:checked=>setPicked(old=>{const next=new Set(old);for(const row of state.current.shown){if(checked)next.add(row.id);else next.delete(row.id);}return next;})}),[visibleCount,selectedVisible,searchBusy]);
  const scale=Number(me?.ui_scale_css??1);
  const widthTotals = useMemo(() => contractTotalSamples(rows), [rows]);
  const widths = useGridWidths('contracts', root, scale, active && !blocked,
    { content: { rows, totals: widthTotals, readableTextWidth: 205, retainBy: contractRowId } });
  const selectionColumn=useMemo<ColDef<ContractRow>>(()=>({colId:'select',headerName:'选择',...fixedWidth(28,scale),sortable:false,pinned:'left',headerComponent:ContractSelectionHeader,cellRenderer:(p:ICellRendererParams<ContractRow>)=>p.node.rowPinned?'':<Checkbox aria-label={`选择合同${p.data!.contract_no||p.data!.material}`} checked={state.current.picked.has(p.data!.id)} onChange={e=>setPicked(old=>{const next=new Set(old);if(e.target.checked)next.add(p.data!.id);else next.delete(p.data!.id);return next;})}/>}),[scale]);
  const contractColumns=useMemo<ColDef<ContractRow>[]>(()=>[
    selectionColumn,
    ...(query.data?.columns??[]).filter(c=>c.key!=='ops').map(c=>{
      const numeric=isContractAmount(c.key);
      const subtable = amountSubtables.get(c.key);
      const editKey = inlineKeys.find(key => key === c.key);
      const editorParams = {editKey, control: () => inlineControl.current};
      const header=c.key==='tag'?'纳入状态':c.label.replace('（自动）','');
      const projectName = (row: ContractRow) => projectNames.get(row.project_key) || (projects.isPending ? '项目读取中…' : '项目未匹配');
      const sizing = contractColumnWidth(c.key, { subtable: Boolean(subtable), projectName,
        archiveHint: row => archiveNoHint(inlineControl.current.next(row)), methods: query.data?.payment_methods ?? [] });
      return {field:c.key as keyof ContractRow,hide:!trade&&['trade_co','trade_contract_amt','trade_inv_sum'].includes(c.key),headerName:header,...sizing,wrapHeaderText:false,autoHeaderHeight:false,wrapText:false,autoHeight:false,cellClass:numeric?'money':sizing.context.columnContent.kind==='bounded'?'contract-identifier':'',...(['project_seq','date','material'].includes(c.key)?{pinned:'left' as const}:{}),...(editKey ? {cellRendererParams: {...editorParams, deferRender: editKey === 'payment_method'}} : {}),
        ...(editKey === 'payment_method' ? {loadingCellRenderer: ContractInlineCell, loadingCellRendererParams: {...editorParams, scrolling:true}} : {}),
        comparator:numeric?(a:string|null,b:string|null)=>compareAmounts(a??'0',b??'0'):undefined,
        cellRenderer:editKey ? ContractInlineCell : (p:ICellRendererParams<ContractRow>)=>{
          if(p.node.rowPinned && !subtable)return c.key==='material'?'合计':numeric?money(p.value??'0'):'';
          const row=p.data!;
          if (subtable) return <div className="contract-amount-action">
            <span>{money(String(p.value ?? '0'))}</span>
            {!p.node.rowPinned && (subtable.kind !== 'trade' || row.trade_co) && <Button size="small"
              aria-label={`${row.contract_no || row.material} ${subtable.label}子表`}
              onClick={() => setSubtable({row, kind: subtable.kind})}>子表</Button>}
          </div>;
          if(c.key==='material')return <div className="contract-object"><Button size="small" aria-label={`编辑材料名：${row.material||'材料名未填'}`} onClick={()=>{openEditor(row,true);}}><EllipsisText text={row.material||'材料名未填'}/></Button><small><EllipsisText text={projectName(row)}/></small></div>;
          if(c.key==='tag'||c.key==='arch')return <Tag className={`status-tag ${c.key==='tag'?(row.tag==='纳入台账'?'status-positive':'status-neutral'):(row.arch==='已存档'?'status-positive':row.arch==='资产处'?'status-pending':'status-neutral')}`}>{String(p.value||'未存档')}</Tag>;
          if(c.key==='approve_status'){
            if(row.approve_status===null)return <span className="muted">—</span>;
            return <Tag className={`status-tag ${row.approve_status==='已审批'?'status-positive':'status-pending'}`}>{row.approve_status}</Tag>;
          }
          return numeric?(p.value===null?'未确定':money(String(p.value))):['supplier','trade_co'].includes(c.key)?<EllipsisText text={String(p.value??'')}/>:String(p.value??'');
        }} as ColDef<ContractRow>;
    }),
    {colId:'actions',headerName:'操作',...contentColumn('bounded', undefined, measure => measure.buttons(['不纳入','推进存档'], { gap: 0 }) + 4),sortable:false,cellRenderer:(p:ICellRendererParams<ContractRow>)=>p.node.rowPinned?'':<div className="contract-row-actions"><Button size="small" disabled={state.current.actionDisabled} onClick={()=>void state.current.tag([p.data!.id],p.data!.tag==='纳入台账'?'不纳入':'纳入台账')}>{p.data!.tag==='纳入台账'?'不纳入':'纳入'}</Button><Button size="small" title={`存档状态将更新为「${nextArch(p.data!.arch)}」`} disabled={state.current.actionDisabled} onClick={()=>void state.current.advance(p.data!)}>推进存档</Button></div>}
  ],[query.data?.columns,query.data?.payment_methods,trade,projectNames,projects.isPending,selectionColumn,compareAmounts]);
  const retainedColumns=useRetainedGridColumns(contractColumns,root,widths.layoutKey);
  const activeWidths=useMemo(()=>widths.columns(retainedColumns),[retainedColumns,widths.columns]);
  const widthColumns=useGridWidthColumns(activeWidths,widths.savedWidths,'material');
  const {busy:subBusy,uncertain:subUncertain,dirty:subDirty}=subtables.summary;
  const exportUnavailable=blocked||!active?'当前页面暂不可操作。':!me?'请先登录。':busy||subBusy?'合同正在保存，请稍候。':uncertain||subUncertain?'合同操作结果待核实，请先重读。':subDirty?'合同子表有未保存输入，请先处理。':query.isPending||query.isFetching||projects.isPending||projects.isFetching?'正在读取合同及项目，请稍候。':query.isError||projects.isError?'合同或项目读取失败，请先重读。':Object.keys(inlineDrafts).length?'请先保存收发登记输入。':Object.keys(editors).length||tool||subtable||remarkEditor?'请先处理并关闭合同窗口。':'';
  function exportIds(){if(!grid.current)throw new Error('合同列表尚未准备好，请稍候。');const ids:number[]=[];grid.current.forEachNodeAfterFilterAndSort(node=>{if(node.data&&!node.rowPinned)ids.push(node.data.id);});return ids;}
  const readState=readPhase(query);
  const placeheld=readState==='idle'||readState==='reading'||readState==='error';
  const pageState=useRef({blocked,active,editorId});pageState.current={blocked,active,editorId};
  function created(id:number){if(pageState.current.blocked||!pageState.current.active||pageState.current.editorId!=='new')return;setFilters({...initialFilters(),tag:''});setSearch('');pendingFocus.current=id;const row=client.getQueryData<{rows:ContractRow[]}>(['contracts'])?.rows.find(r=>r.id===id);closeEditor('new');if(row){grid.current?.ensureNodeVisible(node=>node.data?.id===id,'middle');if(contractHistoryDate(row.remark))setSubtable({row,kind:'supplier'});}}
  return <section className="wb-surface contracts-page page-shell page-shell--fill" data-page-layout="fill" aria-labelledby="page-title" data-page-chrome>
    <div className="contract-toolbar">
      <h2>集采台账，合同主表</h2>
      <div className="contract-chrome-actions">
        <Button disabled={unavailable} onClick={()=>setTool('fetch')}>抓取采购合同信息</Button>
        <Button onClick={()=>{if(trade)grid.current?.applyColumnState({state:['trade_co','trade_contract_amt','trade_inv_sum'].map(colId=>({colId,sort:null}))});setTrade(old=>!old);}}>{trade?'隐藏':'显示'}贸易公司列</Button>
        <Button disabled={unavailable} onClick={()=>openEditor(null)}>+ 手工新增合同</Button>
        <ContractExports owner={me?`${me.id}:${me.account}`:'anonymous'} projects={projectRows} project={filters.projects.length===1?filters.projects[0]!:0} getIds={exportIds} scope={JSON.stringify([filters,searchInput.value,sort,query.dataUpdatedAt,projects.dataUpdatedAt])} searchBusy={searchBusy} unavailable={exportUnavailable} paused={blocked||!active}/>
      </div>
    </div>
    <div className="jc-bulk-selection"><span className="contract-selection-count">已勾选 {selected.length} 行{hidden>0?`（列表外 ${hidden} 行）`:''}</span>{picked.size>0&&<Button size="small" onClick={()=>setPicked(new Set())}>清空勾选</Button>}<div>{(query.data?.tags??[]).map(value=><Button key={value} disabled={unavailable||searchBusy||!picked.size||hidden>0} title={hidden?'请先清空搜索或调整筛选核对勾选范围':''} onClick={()=>void tag([...picked],value)}>批量{value}</Button>)}</div></div>
    <div className="wb-toolbar contract-filters">
      <label className="contract-project-field">项目<ProjectPicker projects={projectRows} selected={filters.projects} multiple label="合同筛选项目" emptyLabel="全部项目" disabled={blocked||projects.isPending} pick={ids=>setFilters(old=>({...old,projects:ids}))}/></label>
      <label>纳入状态<Select aria-label="纳入状态" value={filters.tag} options={['',...(query.data?.tags??[])].map(value=>({value,label:value||'全部'}))} onChange={tag=>setFilters(old=>({...old,tag}))}/></label>
      <label>审批状态<Select aria-label="审批状态" value={filters.approval} options={approvalOptions} onChange={approval=>setFilters(old=>({...old,approval}))}/></label>
      <label>存档情况<Select aria-label="合同存档筛选" value={filters.arch} options={['','未存档','资产处','已存档'].map(value=>({value,label:value||'全部'}))} onChange={arch=>setFilters(old=>({...old,arch}))}/></label>
      <label className="contract-search-field">搜索<Input aria-label="搜索" placeholder="搜索各列内容" allowClear {...searchInput}/></label>
      <Button disabled={blocked||!active} onClick={()=>setTool('party')}>甲方单位分类</Button>
      <Button onClick={()=>{setFilters(initialFilters());setSearch('');}}>重置</Button>
      <span className="contract-filter-count">已勾选 <b>{selected.length}</b> 行 · {placeheld ? (readState==='reading'?'正在读取…':'尚未读取') : searchBusy ? '正在筛选…' : <>显示 <b>{shown.length}</b> 条</>}</span>
    </div>
    {error&&<p className="notice" role="alert">{error}<Button onClick={()=>void reread()}>重读核对</Button></p>}
    <ReadStatusLane phase={readState} announce="正在读取集采合同…" className="contract-read-status">
      {(readState==='error'||readState==='stale')&&<ReadFailure read={query} retained="合同更新失败，保留上次结果。"/>}
      {projects.isError&&<ReadFailure read={projects} label="项目清单"/>}
    </ReadStatusLane>
    {editors.new&&<ContractEditor key="new" inline subtables={subtables} contracts={rows} created={created} row={null} me={me} projects={projectRows} methods={query.data?.payment_methods??[]} blocked={blocked||!active||editorId!=='new'} close={()=>closeEditor('new')} refresh={refresh} announce={announce}/>}
    {placeheld?<div className="contracts-grid page-fill-stage contract-read-reserve read-reserve" aria-hidden="true"><ReadPlaceholder rows={8} quiet={readState==='error'}/></div>:<ContractSelectionContext.Provider value={selection}><GridWidthContext.Provider value={widths}><div className="contracts-grid page-fill-stage grid-single-line" aria-busy={searchBusy} ref={root}><AgGridReact<ContractRow> theme={gridTheme} rowBuffer={2} rowData={shown} columnDefs={widthColumns} defaultColDef={defaultColumn} autoSizeStrategy={widths.strategy} getRowId={p=>String(p.data.id)} pinnedBottomRowData={totalRow} rowHeight={pageGridGeometry(scale).rowHeight} headerHeight={pageGridGeometry(scale).headerHeight} suppressCellFocus={false} suppressScrollOnNewData suppressColumnVirtualisation onSortChanged={e=>setSort(JSON.stringify(e.api.getColumnState().filter(c=>c.sort).map(c=>[c.colId,c.sort,c.sortIndex])))} onGridReady={e=>{grid.current=e.api;widths.attach(e.api);}} onRowDataUpdated={e=>{if(pendingFocus.current){const id=pendingFocus.current;pendingFocus.current=0;e.api.ensureNodeVisible(node=>node.data?.id===id,'middle');const target=e.api.getRowNode(String(id));if(target?.rowIndex!=null)e.api.setFocusedCell(target.rowIndex,'material');}}} overlayNoRowsTemplate="没有符合条件的合同，可调整筛选。"/></div></GridWidthContext.Provider></ContractSelectionContext.Provider>}
    <AnimatePresence initial={false}>{Object.entries(editors).filter(([key])=>key!=='new').map(([key,editor])=><ContractEditor key={`${key}:${editor.presenceId}`} materialOnly={editor.materialOnly} nextArchiveNo={editor.row ? nextArchiveNo(editor.row) : '1'} subtables={subtables} contracts={rows} created={created} row={editor.row} me={me} projects={projectRows} methods={query.data?.payment_methods??[]} blocked={blocked||!active||editorId!==key} close={()=>closeEditor(key)} refresh={refresh} announce={announce}/>)}</AnimatePresence>
    <DialogPresence>{subtable&&<ContractSubtableDialog row={subtable.row} kind={subtable.kind} contracts={rows} workspace={subtables} paused={blocked||!active} writable={!unavailable} close={()=>setSubtable(null)}/>}</DialogPresence>
    <DialogPresence>{remarkEditor&&<ContractRemarkEditor key={remarkEditor.row.id} row={remarkEditor.row} initial={remarkEditor.initial} busy={busy} disabled={blocked||!me||uncertain||query.isPending||query.isError} paused={blocked||!active} error={error} save={async value=>{changeInline(remarkEditor.row.id,'remark',value);return saveField(remarkEditor.row,'remark',value,true);}} close={()=>setRemarkEditor(null)}/>}</DialogPresence>
    <DialogPresence>{tool==='fetch'&&<ContractFetch initialSince={query.data?.fetch_default_since ?? ''} me={me} blocked={blocked||!active} close={()=>setTool(null)} refresh={refresh}/>}</DialogPresence>
    <DialogPresence>{tool==='party'&&<ContractSettings me={me} blocked={blocked||!active} close={()=>setTool(null)} refresh={refresh}/>}</DialogPresence>
  </section>;
}
