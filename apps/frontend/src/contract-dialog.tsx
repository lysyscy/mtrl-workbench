import { BusinessDate } from './time-picker';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Checkbox from 'antd/es/checkbox';
import { useEffect, useId, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, uncertainWrite, requestJson } from './api';
import type { Identity, Project } from './api';
import { ProjectPicker } from './ledger-controls';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { contractHistoryDate, contractRemarkText, historyContractRemark, contractFields, contractWrite, editableContractKeys, readContractDetail } from './contracts-api';
import type { ContractFields, ContractRow } from './contracts-api';
import { money } from './notices-api';
import { todayBeijing } from './contract-subtables-api';

import { ContractSubtables, hasSubtableDrafts, newSubtableState } from './contract-subtables';
import type { SubtableWorkspace, ChangeSubtables } from './contract-subtables';

export function nextContractArchiveNo(contracts:ContractRow[],row:ContractRow):string {
  let max=0n;
  for(const contract of contracts){const no=contract.arch_no.trim();if(contract.project_key===row.project_key&&/^\d+$/.test(no)&&BigInt(no)>max)max=BigInt(no);}
  return String(max+1n);
}

const emptyFields = (): ContractFields => ({ material_name:'',payment_term:'',payment_method:'',remark:'',arch:'未存档',arch_no:'',ret_date:'' });
interface Props { inline?:boolean;materialOnly?:boolean;subtables:SubtableWorkspace; changeSubtables:ChangeSubtables; contracts:ContractRow[]; created:(id:number)=>void; row: ContractRow | null; projects: Project[]; methods: string[]; me: Identity | null; blocked: boolean; close: () => void; refresh: () => Promise<void>; announce: (text: string) => void }
export function ContractEditor({ inline=false, materialOnly=false, subtables, changeSubtables, contracts, created, row, projects, methods, me, blocked, close, refresh, announce }: Props) {
  const [fields,setFields] = useState(emptyFields), [baseline,setBaseline] = useState<ContractFields|null>(null);
  const initialDate=useRef(todayBeijing());
  const [project,setProject] = useState<number[]>([]), [date,setDate] = useState(initialDate.current), [supplier,setSupplier] = useState('');
  const [history,setHistory]=useState(false),[cutoff,setCutoff]=useState('');
  const [amount,setAmount] = useState('0.00'), [trade,setTrade] = useState(''), [tradeAmount,setTradeAmount] = useState('');
  const [busy,setBusy] = useState(false), [saved,setSaved] = useState(false), [uncertain,setUncertain] = useState(false), [error,setError] = useState('');
  const titleId=useId();
  const lock = useRef(false), live = useRef({blocked,me}); live.current = {blocked,me};
  const detail = useQuery({ queryKey:['contract-detail',row?.id], enabled: Boolean(row) && !blocked, staleTime:0, refetchOnMount:'always', queryFn: async ({signal}) => readContractDetail(await requestJson(`/api/m11/detail?id=${row!.id}`,{signal})) });
  useEffect(() => { if (detail.data && !detail.isFetching && baseline === null) { const next=contractFields(detail.data);setFields(next);setBaseline(next); } }, [detail.data,detail.isFetching,baseline]);
  const source = detail.data ?? row, historyDate=contractHistoryDate((detail.data??row)?.remark??'');
  const keys=materialOnly?(['material_name'] as const):editableContractKeys;
  const dirty = !saved && (row ? baseline !== null && keys.some(k => fields[k] !== baseline[k]) : Boolean(history || cutoff || project.length || date!==initialDate.current || supplier || amount!=='0.00' || trade || tradeAmount || keys.some(k=>fields[k]!==emptyFields()[k])));
  const substate=row&&!materialOnly?subtables[row.id]:undefined, subdirty=hasSubtableDrafts(substate), subBusy=Boolean(substate?.busy);
  const closing = useDialogClose({ busy:busy||subBusy,dirty:dirty||subdirty,close:()=>{if(row&&!materialOnly)changeSubtables(old=>old[row.id]?{...old,[row.id]:{...old[row.id]!,drafts:newSubtableState(historyDate).drafts,deleting:null,focus:null}}:old);close();},active:!blocked });
  const unavailable = blocked || !me || subBusy || Boolean(substate?.uncertain) || busy || saved || uncertain || Boolean(row && (!baseline || detail.isPending || detail.isError));
  function change(key: keyof ContractFields,value:string) { setFields(old=>({...old,[key]:value})); }
  async function save() {
    if (unavailable || lock.current || row && !dirty || !row && !project.length) return;
    lock.current=true;setBusy(true);setError('');let written=false;
    const snapshot={...fields};
    try {
      const chosen=projects.find(p=>p.id===project[0]);
      if(!row&&history){
        if(!/^\d{4}-\d{2}-\d{2}$/.test(cutoff)||Number.isNaN(Date.parse(`${cutoff}T00:00:00Z`))||new Date(`${cutoff}T00:00:00Z`).toISOString().slice(0,10)!==cutoff)throw new ApiError('请填写有效核对截至日。',400);
        if(contracts.some(c=>c.project_key===chosen?.warehouse_name&&contractHistoryDate(c.remark)))throw new ApiError('本项目已有历史汇总，请修改原行的子表。',400);
      }
      const changes=Object.fromEntries(keys.filter(k=>snapshot[k]!==baseline?.[k]).map(k=>[k,snapshot[k]]));
      const result=await contractWrite(row?'/api/m11/fields':'/api/m11/add',row?{id:row.id,fields:changes}:{project_key:chosen?.warehouse_name,contract_date:date,supplier,contract_amt:amount||'0',trade_co:trade||null,trade_contract_amt:tradeAmount||null,...snapshot,...(history?{contract_date:'',material_name:chosen?.name_full, supplier:'',contract_amt:'0',trade_co:null,trade_contract_amt:null,remark:historyContractRemark(cutoff,snapshot.remark)}:{})});
      if(!row&&!(typeof result.id==='number'&&Number.isSafeInteger(result.id)&&result.id>0))throw new ApiError('新增回执未确认合同，请重读核对，勿重复提交。',0,'invalid_response');
      written=true;setSaved(true);
      await refresh();
      if (row) await detail.refetch({throwOnError:true});
      announce(row?'合同已保存。':'合同已新增。');if(!subdirty)close();if(!row&&typeof result.id==='number')created(result.id);
    } catch (failure) {
      const known=!uncertainWrite(failure);
      const unknown=!written && !known;
      setUncertain(unknown);
      setError(`${written?'合同已保存，重读失败；勿重复保存。':unknown?'保存结果待核实，请重读列表和详情核对，勿重复提交。':''}${failure instanceof Error?failure.message:'保存未完成，请重试。'}`);
    } finally { lock.current=false;setBusy(false); }
  }
  async function reread() {
    if (busy || live.current.blocked) return;
    setBusy(true);
    try { await refresh();if(row) await detail.refetch({throwOnError:true});setError(saved?'已重新读取，请核对合同。':uncertain?'已重新读取，请对照合同与本次输入；确认结果后关闭窗口。':'已重读最新合同，本次输入保留。'); }
    catch(failure) {setError(failure instanceof Error?failure.message:'重读失败，请重试。');}
    finally {setBusy(false);}
  }
  if (blocked) return null;
  const contents=<DialogContents title={materialOnly?'材料名':row?'合同详情与维护':'手工新增合同'} titleId={titleId} closing={closing}><form onSubmit={e=>{e.preventDefault();void save();}}><div className="contract-editor-body">
    {row&&materialOnly&&<p>{row.contract_no||'手工合同'}</p>}
    {row && !materialOnly && <div className="contract-source"><strong>{source?.contract_no||'手工合同'}</strong><span>{projects.find(p=>p.warehouse_name===row.project_key)?.disp||'项目未匹配'}，{source?.date||'合同日期未填'}</span><span>供应商：{source?.supplier||'未填'}，合同金额：{money(source!.contract_amt)} 元</span>{source?.trade_co && <span>贸易公司：{source?.trade_co}，合同金额：{source?.trade_contract_amt===null?'未确定':`${money(source!.trade_contract_amt!)} 元`}</span>}</div>}
    {row && detail.isPending ? <p role="status">正在读取合同详情…</p> : row && detail.isError ? <p className="notice" role="alert">{detail.error.message}<Button onClick={()=>void reread()}>重读详情</Button></p> : <>
      {!row&&<><Checkbox checked={history} disabled={unavailable} onChange={e=>setHistory(e.target.checked)}>历史汇总</Checkbox>{history&&<><p>每项目一行。历史未结金额在供应商子表录入；已扣除截至日以前的付款，请勿重复录入。</p><label className="contract-field">核对截至日<BusinessDate label="核对截至日" value={cutoff} disabled={unavailable} onChange={setCutoff}/></label></>}</>}
      {!row && <div className="contract-form-grid"><label>项目<ProjectPicker projects={projects.filter(p=>Boolean(p.warehouse_name))} selected={project} pick={setProject} label="合同项目" disabled={unavailable} /></label><label>合同日期<BusinessDate label="合同日期" value={history?'':date} disabled={unavailable||history} onChange={setDate} /></label><label>供应商<Input value={history?'':supplier} maxLength={128} disabled={unavailable||history} onChange={e=>setSupplier(e.target.value)} /></label><label>合同金额（元）<Input value={history?'':amount} inputMode="decimal" pattern="[0-9]+([.][0-9]{1,2})?" disabled={unavailable||history} onChange={e=>setAmount(e.target.value)} /></label><label>贸易公司<Input value={history?'':trade} disabled={unavailable||history} onChange={e=>setTrade(e.target.value)} /></label><label>贸易公司合同金额（元）<Input value={history?'':tradeAmount} inputMode="decimal" pattern="[0-9]+([.][0-9]{1,2})?" disabled={unavailable||history} onChange={e=>setTradeAmount(e.target.value)} /></label></div>}
      <div className="contract-form-grid"><label>材料名<Input autoFocus={materialOnly} value={!row&&history?projects.find(p=>p.id===project[0])?.name_full??'':fields.material_name} maxLength={128} disabled={unavailable||!row&&history} onChange={e=>change('material_name',e.target.value)} /></label>{!materialOnly&&<><label>账期<Input value={fields.payment_term} maxLength={32} disabled={unavailable} onChange={e=>change('payment_term',e.target.value)} /></label><label>合同付款方式<Select aria-label="合同付款方式" value={fields.payment_method} disabled={unavailable} options={['',...methods].map(value=>({value,label:value||'未约定'}))} onChange={value=>change('payment_method',value)} /></label>{row && <><label>存档情况<Select aria-label="存档情况" value={fields.arch} disabled={unavailable} options={['未存档','资产处','已存档'].map(value=>({value,label:value}))} onChange={value=>change('arch',value)} /></label><label>存档号<Input value={fields.arch_no} maxLength={32} placeholder={row?nextContractArchiveNo(contracts,row):'1'} title="本项目下一个存档号；空框按两次回车填入并保存" disabled={unavailable} onChange={e=>change('arch_no',e.target.value)} onKeyDown={e=>{if(e.key!=='Enter'||e.nativeEvent.isComposing)return;e.preventDefault();if(!fields.arch_no.trim())change('arch_no',nextContractArchiveNo(contracts,row!));else void save();}} /></label><label>寄回日期<BusinessDate label="寄回日期" value={fields.ret_date} disabled={unavailable} onChange={value=>change('ret_date',value)} /></label></>}</>}</div>
      {!materialOnly&&<label className="contract-remark">备注<Input.TextArea value={historyDate?contractRemarkText(fields.remark):fields.remark} maxLength={255-(!row&&history||historyDate?historyContractRemark(historyDate||cutoff,'').length:0)} autoSize={{minRows:2,maxRows:5}} disabled={unavailable} onChange={e=>change('remark',historyDate?historyContractRemark(historyDate,e.target.value):e.target.value)} /></label>}
      {row&&!materialOnly&&<ContractSubtables key={row.id} contracts={contracts} contractId={row.id} historyDate={historyDate} workspace={subtables} change={changeSubtables} writable={Boolean(me)&&!busy&&!uncertain} paused={blocked}/>}
    </>}
    {error && <p className="notice" role="alert">{error}</p>}

    </div><div className="dialog-actions"><Button disabled={busy||subBusy} onClick={closing.requestClose}>{saved||uncertain?'关闭':'取消'}</Button>{(error||saved||uncertain)&&<Button disabled={busy||blocked} onClick={()=>void reread()}>重读核对</Button>}{!saved&&!uncertain&&<Button htmlType="submit" className="primary" disabled={unavailable||Boolean(row&&!dirty)||!row&&!project.length}>{busy?'正在保存…':materialOnly?'保存材料名':'保存合同'}</Button>}</div>
  </form></DialogContents>;
  return inline&&!row?<div className={`contract-editor contract-inline-editor${closing.confirming?' contract-editor-discard':''}`}>{contents}</div>:<BusinessModal open className={`project-dialog contract-editor${materialOnly?' contract-material-editor':''}${closing.confirming?' contract-editor-discard':''}`} titleId={titleId} requestClose={closing.requestClose}>{contents}</BusinessModal>;
}
