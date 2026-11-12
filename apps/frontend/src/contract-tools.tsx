import { DialogPresence } from './workspace-motion';
import { BusinessDate } from './time-picker';
import Button from 'antd/es/button';
import Select from 'antd/es/select';
import { createContext, useContext, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, confirmWrite, record, requestJson, uncertainWrite } from './api';
import type { Identity } from './api';
import { OwnershipDialog, OwnershipProjectLink, useContractOwnershipPending } from './ownership';
import type { OwnershipDocument } from './ownership';
import { BusinessModal } from './business-modal';
import { ReadGrid } from './business-grid';
import { DialogContents, useDialogClose } from './dialog-close';
import { contractWrite } from './contracts-api';
import { body, receipt } from './notices-api';
import { I8FetchActions, I8FetchRecovery, I8FetchStatus, useI8FetchAction } from './i8-fetch';
import { JcReceiptContents, readReceipt, readReceiptRows } from './jc-fetch-receipt';
import type { ReceiptRow } from './jc-fetch-receipt';
import { jcRulesPath } from './jc-rule-data';
import { ReadFailure } from './read-region';
import { useHistoryGuard } from './history';

interface ToolProps { me:Identity|null;blocked:boolean;close:()=>void;refresh:()=>Promise<void> }

function readContractFetch(value: unknown) {
  const result = readReceipt(value);
  if (!record(value) || value.ok !== true || !result || !result.id) {
    throw new ApiError('采购合同抓取回执不完整。', 0, 'invalid_response');
  }
  return { ...result, id: result.id };
}

export function ContractFetch({ me, blocked, close, refresh }: ToolProps) {
  const client = useQueryClient();
  const [since, setSince] = useState('');
  const [all, setAll] = useState(false);
  const [result, setResult] = useState<ReturnType<typeof readContractFetch>>();
  const [fallbackPending, setFallbackPending] = useState<ReceiptRow[]>([]);
  const [ownership, setOwnership] = useState<OwnershipDocument | null>(null);
  const [rule, setRule] = useState<{ row: ReceiptRow; kind: 'project' | 'contract' } | null>(null);
  const [saving, setSaving] = useState(false);
  const [ruleError, setRuleError] = useState('');
  const [feedback, setFeedback] = useState('');
  const ruleLock = useRef(false);
  const action = useI8FetchAction({ me, paused: blocked, refresh, source: 'contracts' });
  const closing = useDialogClose({ busy: action.busy || action.refreshing || saving, dirty: !action.sent && Boolean(since || all), close, active: !blocked });
  const { read: pendingRead, omit } = useContractOwnershipPending(result?.id ?? 0, !blocked && Boolean(result?.unsettled.length));
  const pending = pendingRead.data ? readReceiptRows(pendingRead.data, false) : fallbackPending;
  useHistoryGuard('jc-fetch-rule', () => ruleLock.current ? '集采剔除规则正在保存，请稍候。' : '');

  async function run() {
    const fetched = await action.run({
      path: '/api/m11/fetch',
      payload: { confirm: true, ...(all ? { since: '' } : since ? { since } : {}) },
      parse: readContractFetch,
    });
    if (fetched) {
      setFallbackPending(fetched.unsettled);
      setResult(fetched);
    }
  }

  function selectRule(row: ReceiptRow, kind: 'project' | 'contract') {
    if (ruleLock.current) return;
    setRuleError('');
    setRule({ row, kind });
  }

  async function saveRule() {
    if (!rule || !result || !me || blocked || ruleLock.current) return;
    const { row, kind } = rule;
    ruleLock.current = true;
    setSaving(true);
    setRuleError('');
    setFeedback('');
    try {
      const response = await requestJson(jcRulesPath, { method: 'POST', ...body(kind === 'project'
        ? { kind, name_full: row.project } : { kind, contract_no: row.contract }) });
      confirmWrite(record(response) && response.ok === true, '规则保存回执不完整。');
      setRule(null);
      setFallbackPending(rows => rows.filter(item => kind === 'project' ? item.project !== row.project : item.contract !== row.contract));
      omit(item => kind === 'project' ? item.project_name === row.project : item.contract_no === row.contract);
      setFeedback(record(response) && response.reused === true ? '已有相同剔除规则' : '已加入剔除规则');
      void client.invalidateQueries({ queryKey: ['rules', 'jc-ignore'], refetchType: 'none' });
      try {
        await pendingRead.refetch({ throwOnError: true });
      } catch {
        setFeedback('剔除规则已保存，其他合同的待指定列表未能刷新。');
      }
    } catch (failure) {
      setRuleError(uncertainWrite(failure) ? '规则保存结果待确认，可以重试本次操作。'
        : failure instanceof Error ? failure.message : '剔除规则保存失败。');
    } finally {
      ruleLock.current = false;
      setSaving(false);
    }
  }

  function pendingActions(row: ReceiptRow) {
    if (!result) return null;
    const document: OwnershipDocument = {
      source: 'contract', runId: result.id, number: row.contract, name: row.document, project: row.project,
    };
    return <div className="jc-receipt-row-actions">
      {row.kind === 'not_archived' ? <OwnershipProjectLink document={document} />
        : <Button size="small" disabled={saving || Boolean(ownership) || blocked || !me} onClick={() => {
          setRule(null);
          setOwnership(document);
        }}>补归属关键词</Button>}
      <Button size="small" disabled={saving || blocked || !me || !row.project.trim()} onClick={() => selectRule(row, 'project')}>剔除这个项目</Button>
      <Button size="small" disabled={saving || blocked || !me || !row.contract.trim()} onClick={() => selectRule(row, 'contract')}>仅剔除这份合同</Button>
      {rule?.row.id === row.id && <div className="jc-receipt-rule-confirm">
        <p>{rule.kind === 'project' ? `下次抓取时，跳过「${row.project}」的所有合同。` : `下次抓取时，跳过合同「${row.contract}」。`}</p>
        {ruleError && <p className="notice" role="alert">{ruleError}</p>}
        <Button size="small" disabled={saving} onClick={() => setRule(null)}>取消剔除</Button>
        <Button size="small" disabled={saving} type="primary" onClick={() => void saveRule()}>{saving ? '正在保存…' : '确认加入剔除规则'}</Button>
      </div>}
    </div>;
  }

  return <><BusinessModal open={!blocked && !ownership} className={`project-dialog contract-fetch${result ? ' jc-receipt-dialog' : ''}${closing.confirming ? ' contract-tool-discard' : ''}`} titleId="contract-fetch-title" requestClose={closing.requestClose}>
    <DialogContents title="抓取采购合同" titleId="contract-fetch-title" closing={closing}>
      <I8FetchStatus action={action} me={me} />
      {!action.sent && <>
        <label className="contract-field">抓取范围
          <Select aria-label="合同抓取范围" value={all ? 'all' : 'incremental'} disabled={action.busy} options={[{ value: 'incremental', label: '增量 / 指定起点' }, { value: 'all', label: '全部合同' }]} onChange={value => setAll(value === 'all')} />
        </label>
        {!all && <label className="contract-field">合同日期起点（留空按现有合同增量）<BusinessDate label="合同日期起点" value={since} disabled={action.busy} onChange={setSince} /></label>}
        <p>已审批和未审批合同均写入台账。命中剔除规则或未完成归属的合同不写入；保留人工标记、材料名、账期、付款方式和备注。</p>
      </>}
      {result && <>
        {feedback && <p role="status">{feedback}</p>}
        {pendingRead.isError && <ReadFailure read={pendingRead} label="归属待办" retained="保留上次读取的归属待办。" />}
        <JcReceiptContents data={result} pending={pending} actions={pendingActions} />
      </>}
      <I8FetchRecovery action={action} source="contracts" />
      <I8FetchActions action={saving ? { ...action, busy: true } : action} close={closing.requestClose} onRun={() => void run()} />
    </DialogContents>
  </BusinessModal><DialogPresence>{ownership && <OwnershipDialog document={ownership}
    blocked={blocked} close={() => setOwnership(null)} refresh={refresh} announce={setFeedback} />}</DialogPresence></>;
}
interface Party {name:string;kind:string;kind_name:string;count:number}
interface Settings {parties:Party[];kinds:string[];names:Record<string,string>}
const PartyEditing=createContext<{drafts:Record<string,string>;disabled:boolean;options:{value:string;label:string}[];change:(party:Party,value:string)=>void;save:(party:Party)=>void}>(null!);
function PartyKindCell({data:party}:{data:Party}) {
  const editing=useContext(PartyEditing);
  return <Select aria-label={party.name+'分类'} value={editing.drafts[party.name]??party.kind} disabled={editing.disabled} options={editing.options} onChange={value=>editing.change(party,value)}/>;
}
function PartySaveCell({data:party}:{data:Party}) {
  const editing=useContext(PartyEditing);
  return <Button size="small" disabled={editing.disabled||!editing.drafts[party.name]} onClick={()=>editing.save(party)}>保存</Button>;
}
export function ContractSettings({me,blocked,close,refresh}:ToolProps) {
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[feedback,setFeedback]=useState(''),[unknown,setUnknown]=useState(false);
  const [drafts,setDrafts]=useState<Record<string,string>>({});
  const lock=useRef(false),closing=useDialogClose({busy,dirty:Boolean(Object.keys(drafts).length),close,active:!blocked});
  const query=useQuery({queryKey:['contract-settings','party'],enabled:!blocked,staleTime:0,refetchOnMount:'always',queryFn:async({signal}):Promise<Settings>=>{
    const value=await requestJson('/api/m11/party-kinds',{signal});
    if(!record(value)||!Array.isArray(value.items))throw new ApiError('清单读取不完整，请重读。');
    if(!value.items.every(x=>record(x)&&typeof x.name==='string'&&typeof x.kind==='string'&&typeof x.kind_name==='string'&&typeof x.count==='number')||!Array.isArray(value.kinds)||!value.kinds.every(x=>typeof x==='string')||!record(value.kind_names)||!Object.values(value.kind_names).every(x=>typeof x==='string'))throw new ApiError('甲方分类读取不完整，请重读。');
    return {parties:value.items as Party[],kinds:value.kinds as string[],names:value.kind_names as Record<string,string>};
  }});
  async function write(path:string,payload:unknown,method='POST',accepted?:()=>void){
    if(busy||blocked||!me||unknown||lock.current)return;
    lock.current=true;setBusy(true);setError('');setFeedback('');let written=false;
    try{const result=await contractWrite(path,payload,method);written=true;accepted?.();setFeedback(receipt(result));await query.refetch({throwOnError:true});await refresh();}
    catch(failure){setUnknown(true);setError(`${written?'已保存，重读失败。':'结果待核实。'}${failure instanceof Error?failure.message:''}请重读核对，勿重复操作。`);}
    finally{lock.current=false;setBusy(false);}
  }
  async function reread(){if(busy||blocked)return;setBusy(true);try{await query.refetch({throwOnError:true});await refresh();setUnknown(false);setError('');setFeedback('已重读，请核对清单。');}catch(failure){setError(failure instanceof Error?failure.message:'重读失败。');}finally{setBusy(false);}}
  const unavailable=busy||blocked||!me||unknown||query.isPending||query.isError;
  return <BusinessModal open={!blocked} className={`project-dialog contract-settings${closing.confirming?' contract-tool-discard':''}`} titleId="contract-settings-title" requestClose={closing.requestClose}><DialogContents title="甲方单位分类" titleId="contract-settings-title" closing={closing}>
    <p>分类决定下次抓取时合同金额的落列；修改分类不重算已有合同。</p>
    {query.isPending?<p role="status">正在读取清单…</p>:query.isError?<p className="notice" role="alert">{query.error.message}</p>:query.data&&<PartyEditing.Provider value={{drafts,disabled:unavailable,options:query.data.kinds.map(value=>({value,label:query.data!.names[value]||value})),change:(party,value)=>setDrafts(old=>{const next={...old};if(value===party.kind)delete next[party.name];else next[party.name]=value;return next;}),save:party=>void write('/api/m11/party-kind',{name:party.name,kind:drafts[party.name]},'POST',()=>setDrafts(old=>{const next={...old};delete next[party.name];return next;}))}}><ReadGrid<Party> manualWidths table="contract-settings-party" className="contract-settings-table" label="甲方单位分类" domLayout="autoHeight" rows={query.data.parties} rowId={row=>row.name} columns={[
      {colId:'name',headerName:'甲方单位',valueGetter:p=>p.data!.name},
      {colId:'count',headerName:'合同数',valueGetter:p=>p.data!.count},
      {colId:'kind',headerName:'分类',cellRenderer:PartyKindCell},
      {colId:'actions',headerName:'操作',cellRenderer:PartySaveCell},
    ]}/></PartyEditing.Provider>}
    {feedback&&<p role="status">{feedback}</p>}{error&&<p className="notice" role="alert">{error}</p>}<div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button disabled={busy||blocked} onClick={()=>void reread()}>重读清单</Button></div>
  </DialogContents></BusinessModal>;
}
