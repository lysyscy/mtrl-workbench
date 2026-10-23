import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ApiError, requestJson } from './api';
import type { Identity, Project } from './api';
import { ProjectPicker } from './ledger-controls';
import { BusinessModal } from './business-modal';
import { BoundedTable } from './bounded-table';
import { DialogContents, useDialogClose } from './dialog-close';
import { contractFields, contractWrite, editableContractKeys, readContractDetail } from './contracts-api';
import type { ContractFields, ContractRow } from './contracts-api';
import { money } from './notices-api';

const emptyFields = (): ContractFields => ({ material_name:'',payment_term:'',payment_method:'',remark:'',arch:'未存档',arch_no:'',ret_date:'' });
interface Props { row: ContractRow | null; projects: Project[]; methods: string[]; me: Identity | null; blocked: boolean; close: () => void; refresh: () => Promise<void>; announce: (text: string) => void }
export function ContractEditor({ row, projects, methods, me, blocked, close, refresh, announce }: Props) {
  const [fields,setFields] = useState(emptyFields), [baseline,setBaseline] = useState<ContractFields|null>(null);
  const [project,setProject] = useState<number[]>([]), [date,setDate] = useState(''), [supplier,setSupplier] = useState('');
  const [amount,setAmount] = useState(''), [trade,setTrade] = useState(''), [tradeAmount,setTradeAmount] = useState('');
  const [busy,setBusy] = useState(false), [saved,setSaved] = useState(false), [uncertain,setUncertain] = useState(false), [error,setError] = useState('');
  const lock = useRef(false), live = useRef({blocked,me}); live.current = {blocked,me};
  const detail = useQuery({ queryKey:['contract-detail',row?.id], enabled: Boolean(row) && !blocked, staleTime:0, refetchOnMount:'always', queryFn: async ({signal}) => readContractDetail(await requestJson(`/api/m11/detail?id=${row!.id}`,{signal})) });
  useEffect(() => { if (detail.data && !detail.isFetching && baseline === null) { const next=contractFields(detail.data);setFields(next);setBaseline(next); } }, [detail.data,detail.isFetching,baseline]);
  const source = detail.data ?? row;
  const dirty = !saved && (row ? baseline !== null && editableContractKeys.some(k => fields[k] !== baseline[k]) : Boolean(project.length || date || supplier || amount || trade || tradeAmount || editableContractKeys.some(k=>fields[k]!==emptyFields()[k])));
  const closing = useDialogClose({ busy,dirty,close,active:!blocked });
  const unavailable = blocked || !me || busy || saved || uncertain || Boolean(row && (!baseline || detail.isPending || detail.isError));
  function change(key: keyof ContractFields,value:string) { setFields(old=>({...old,[key]:value})); }
  async function save() {
    if (unavailable || lock.current || row && !dirty || !row && !project.length) return;
    lock.current=true;setBusy(true);setError('');let written=false;
    const snapshot={...fields};
    try {
      const chosen=projects.find(p=>p.id===project[0]);
      const changes=Object.fromEntries(editableContractKeys.filter(k=>snapshot[k]!==baseline?.[k]).map(k=>[k,snapshot[k]]));
      await contractWrite(row?'/api/m11/fields':'/api/m11/add',row?{id:row.id,fields:changes}:{project_key:chosen?.warehouse_name,contract_date:date,supplier,contract_amt:amount||'0',trade_co:trade||null,trade_contract_amt:tradeAmount||null,...snapshot});
      written=true;setSaved(true);
      await refresh();
      if (row) await detail.refetch({throwOnError:true});
      announce(row?'合同已保存。':'合同已新增。');close();
    } catch (failure) {
      const known=failure instanceof ApiError && failure.status>0 && failure.code!=='invalid_response';
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
  return <BusinessModal open className={`project-dialog contract-editor${closing.confirming?' contract-editor-discard':''}`} titleId="contract-editor-title" requestClose={closing.requestClose}><DialogContents title={row?'合同详情与维护':'新增集采合同'} titleId="contract-editor-title" closing={closing}><form onSubmit={e=>{e.preventDefault();void save();}}><div className="contract-editor-body">
    {row && <div className="contract-source"><strong>{source?.contract_no||'手工合同'}</strong><span>{projects.find(p=>p.warehouse_name===row.project_key)?.disp||'项目未匹配'} · {source?.date||'合同日期未填'}</span><span>供应商：{source?.supplier||'未填'} · 合同金额：{money(source!.contract_amt)} 元</span>{source?.trade_co && <span>贸易公司：{source?.trade_co} · 合同金额：{source?.trade_contract_amt===null?'未确定':`${money(source!.trade_contract_amt!)} 元`}</span>}</div>}
    {row && detail.isPending ? <p role="status">正在读取合同详情…</p> : row && detail.isError ? <p className="notice" role="alert">{detail.error.message}<Button onClick={()=>void reread()}>重读详情</Button></p> : <>
      {!row && <div className="contract-form-grid"><label>项目<ProjectPicker projects={projects.filter(p=>Boolean(p.warehouse_name))} selected={project} pick={setProject} label="合同项目" disabled={unavailable} /></label><label>合同日期<Input type="date" value={date} disabled={unavailable} onChange={e=>setDate(e.target.value)} /></label><label>供应商<Input value={supplier} maxLength={128} disabled={unavailable} onChange={e=>setSupplier(e.target.value)} /></label><label>合同金额（元）<Input value={amount} inputMode="decimal" pattern="[0-9]+([.][0-9]{1,2})?" disabled={unavailable} onChange={e=>setAmount(e.target.value)} /></label><label>贸易公司<Input value={trade} disabled={unavailable} onChange={e=>setTrade(e.target.value)} /></label><label>贸易公司合同金额（元）<Input value={tradeAmount} inputMode="decimal" pattern="[0-9]+([.][0-9]{1,2})?" disabled={unavailable} onChange={e=>setTradeAmount(e.target.value)} /></label></div>}
      <div className="contract-form-grid"><label>材料名<Input value={fields.material_name} maxLength={128} disabled={unavailable} onChange={e=>change('material_name',e.target.value)} /></label><label>账期<Input value={fields.payment_term} maxLength={32} disabled={unavailable} onChange={e=>change('payment_term',e.target.value)} /></label><label>合同付款方式<Select aria-label="合同付款方式" value={fields.payment_method} disabled={unavailable} options={['',...methods].map(value=>({value,label:value||'未约定'}))} onChange={value=>change('payment_method',value)} /></label>{row && <><label>存档情况<Select aria-label="存档情况" value={fields.arch} disabled={unavailable} options={['未存档','资产处','已存档'].map(value=>({value,label:value}))} onChange={value=>change('arch',value)} /></label><label>存档号<Input value={fields.arch_no} maxLength={32} disabled={unavailable} onChange={e=>change('arch_no',e.target.value)} /></label><label>寄回日期<Input type="date" value={fields.ret_date} disabled={unavailable} onChange={e=>change('ret_date',e.target.value)} /></label></>}</div>
      <label className="contract-remark">备注<Input.TextArea value={fields.remark} maxLength={255} autoSize={{minRows:2,maxRows:5}} disabled={unavailable} onChange={e=>change('remark',e.target.value)} /></label>
      {row && detail.data && <><div className="contract-detail-totals">{[['结算金额',detail.data.settle],['付款金额',detail.data.pay_sum],['欠款金额',detail.data.debt]].map(([label,value])=><span key={label}>{label}<strong>{money(value!)} 元</strong></span>)}</div><div className="contract-evidence">{(['supplier','trade'] as const).filter(kind=>kind==='supplier'||row.trade_co||detail.data!.trade_invoices.length).map(kind=><section key={kind}><h3>{kind==='supplier'?'供应商':'贸易公司'}发票依据</h3><div className="table-scroll"><BoundedTable columns={[{min:10,max:16,flex:1},{min:10,max:18,flex:1}]}><thead><tr><th>发票日期</th><th>金额（元）</th></tr></thead><tbody>{detail.data![kind==='supplier'?'supplier_invoices':'trade_invoices'].map(invoice=><tr key={invoice.id}><td>{invoice.date||'未填'}</td><td className="money">{money(invoice.amount)}</td></tr>)}</tbody></BoundedTable>{!detail.data![kind==='supplier'?'supplier_invoices':'trade_invoices'].length&&<p className="state">暂无发票</p>}</div></section>)}</div>{row.notice_ids.length>0&&<section className="contract-linked"><h3>已关联通知书</h3><div>{row.notice_ids.map(id=><Link key={id} to={`/notices?notice=${id}`}>查看通知书 · 供应商与关联维护</Link>)}</div></section>}</>}
    </>}
    {error && <p className="notice" role="alert">{error}</p>}

    </div><div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>{saved||uncertain?'关闭':'取消'}</Button>{(error||saved||uncertain)&&<Button disabled={busy||blocked} onClick={()=>void reread()}>重读核对</Button>}{!saved&&!uncertain&&<Button htmlType="submit" className="primary" disabled={unavailable||Boolean(row&&!dirty)||!row&&!project.length}>{busy?'正在保存…':'保存合同'}</Button>}</div>
  </form></DialogContents></BusinessModal>;
}
