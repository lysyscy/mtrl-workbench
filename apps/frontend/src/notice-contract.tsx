import { Link } from 'react-router';
import { useHistoryGuard } from './history';
import Button from 'antd/es/button';
import Radio from 'antd/es/radio';
import { Virtuoso } from 'react-virtuoso';
import { BusinessModal } from './business-modal';
import { DiscardConfirmation } from './dialog-close';
import { ReadGrid } from './business-grid';
import { contentWidth, numberColumnWidth } from './grid';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson, uncertainWrite } from './api';
import { body, cents, money, receipt, readNotices } from './notices-api';
import type { NoticeRow } from './notices-api';
import { SupplierStep } from './notice-supplier-step';

interface Invoice { id: number; kind: string; date: string; amount: string }
interface Reason { kind: string; text: string; amounts?: string[]; prior_amount?: string; invoice_total?: string; notice_codes?: string[] }
export interface Candidate {
  id: number; contract_no: string; date: string; supplier: string; material: string;
  contract_amt: string; trade_co: string | null; trade_contract_amt: string | null;
  inv_sum: string; trade_inv_sum: string; pay_sum: string; debt: string;
  supplier_uninvoiced: string; trade_uninvoiced: string | null; invoices: Invoice[];
  recommendation: { reasons: Reason[]; invoice_side: string; combination_limited: boolean };
}
interface Candidates { current_contract_id: number | null; notice_amount: string; supplier: string; read_only: boolean; rows: Candidate[] }
interface Props { row: NoticeRow; blocked: boolean; close: () => void; refresh: () => Promise<void>; announce: (message: string) => void }
const contractName = (candidate: Candidate) => candidate.material.trim() || '材料名称未填';
const hasTradeSide = (candidate: Candidate) => Boolean(candidate.trade_co || candidate.invoices.some(invoice => invoice.kind === 'trade'));
function InvoiceSide({ candidate, kind }: { candidate: Candidate; kind: 'supplier' | 'trade' }) {
  const invoices = candidate.invoices.filter(invoice => invoice.kind === kind);
  const trade = kind === 'trade', name = trade ? '贸易公司' : '供应商';
  const scale=Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))||1;
  const uninvoiced = trade ? candidate.trade_uninvoiced : candidate.supplier_uninvoiced;
  return <div className="contract-invoice-side">
    {hasTradeSide(candidate) && <p className="contract-trade-name">{name}，{trade ? candidate.trade_co || '名称未填' : candidate.supplier}</p>}
    <div className="contract-amounts"><div><span>{name}合同金额</span><strong>{trade && candidate.trade_contract_amt === null ? '未确定' : `${money(trade ? candidate.trade_contract_amt! : candidate.contract_amt)} 元`}</strong></div><div><span>{name}发票总金额</span><strong>{money(trade ? candidate.trade_inv_sum : candidate.inv_sum)} 元</strong></div></div>
    <p className="contract-uninvoiced">{uninvoiced === null ? '未开票金额未确定' : <>{cents(uninvoiced) < 0n ? '超开票' : '未开票'} {money(uninvoiced.replace(/^-/,''))} 元</>}</p>
    <ReadGrid manualWidths table="notice-candidate-invoices" className="contract-invoices" label={`${contractName(candidate)}${name}发票明细`} domLayout="autoHeight" rows={invoices} rowId={invoice=>String(invoice.id)} grid={{overlayNoRowsTemplate:'未录入发票'}} columns={[
      {field:'date',headerName:`${name}发票日期`,...contentWidth(110,180,scale),valueFormatter:p=>p.value||'日期未填'},
      {field:'amount',headerName:'金额（元）',...numberColumnWidth(invoices.map(invoice=>money(invoice.amount)),scale,false,1),cellClass:'money',valueFormatter:p=>money(p.value)},
    ]} />
  </div>;
}
function Recommendation({ candidate, amount }: { candidate: Candidate; amount: string }) {
  const { reasons, combination_limited } = candidate.recommendation;
  return <div className="contract-reasons">{reasons.map((reason,index) => <div key={index}><span>{reason.text}</span>{reason.kind === 'invoice' && reason.amounts && <strong>{reason.amounts.map(money).join(' + ')} = {money(amount)} 元</strong>}{reason.kind === 'combined_notices' && reason.prior_amount && reason.invoice_total && <><strong>{money(reason.prior_amount)} + {money(amount)} = {money(reason.invoice_total)} 元</strong><small>{reason.notice_codes?.join('、')}</small></>}</div>)}{combination_limited && <small>超过12笔，仅比较单笔和全部发票合计。</small>}</div>;
}
export function ContractDialog({ row, blocked, close, refresh, announce }: Props) {
  const lock = useRef(false), decisionTitle = useRef<HTMLHeadingElement>(null), closeButton = useRef<HTMLButtonElement>(null);
  const [selected,setSelected] = useState<number | null>(null), [decision,setDecision] = useState<'none'|'discard'|'unlink'>('none');
  const [step,setStep] = useState(row.has_link ? 2 : 1), [supplier,setSupplier] = useState(row.jc_supplier);
  const initialSupplier = useRef(row.jc_supplier), supplierBaseline = useRef(row.jc_supplier), supplierEdited = useRef(false), stepHeading = useRef<HTMLHeadingElement>(null);
  const [busy,setBusy] = useState(false), [saved,setSaved] = useState(false), [error,setError] = useState('');
  const query = useQuery({ queryKey: ['notice-maintenance','link',row.notice_id,row.bill_no,'all-suppliers'], enabled: !blocked, staleTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: false, retry: false, queryFn: async ({signal}) => {
    const value = await requestJson(`/api/m11/link-recommendations?notice_id=${row.notice_id}&supplier=`,{signal});
    if (!record(value) || !Array.isArray(value.rows) || !value.rows.every(candidate => record(candidate) && typeof candidate.material === 'string' && Array.isArray(candidate.invoices) && record(candidate.recommendation)) || typeof value.notice_amount !== 'string') throw new ApiError('合同候选读取不完整，请重读。');
    return value as unknown as Candidates;
  } });
  const matches = useQuery({ queryKey: ['notice-maintenance','sup-match',row.notice_id,row.bill_no], enabled: !blocked && !row.is_revoked && !row.is_excluded && row.category === 'jc', refetchOnWindowFocus: false, retry: false, queryFn: async ({signal}) => {
    const value = await requestJson('/api/m03/actions/sup-match',{method:'POST',signal,...body({notice_id:row.notice_id})});
    if (!record(value) || !Array.isArray(value.pool) || !value.pool.every(x => typeof x === 'string') || !Array.isArray(value.cands) || !value.cands.every(x => typeof x === 'string') || typeof value.level_name !== 'string') throw new ApiError('供应商候选读取不完整，请重读。');
    return value as {pool:string[];cands:string[];level:number;level_name:string};
  } });
  const data = query.data, current = data?.rows.find(candidate => candidate.id === data.current_contract_id), chosen = data?.rows.find(candidate => candidate.id === selected);
  const readOnly = row.is_revoked || row.is_excluded || row.category !== 'jc' || Boolean(data?.read_only);
  const rows = data?.rows.filter(candidate => candidate.id === data.current_contract_id || !supplier.trim() || candidate.supplier === supplier.trim()) ?? [];
  const dirty = !saved && (supplier.trim() !== supplierBaseline.current || selected !== null && selected !== data?.current_contract_id);
  useEffect(() => {
    if (!supplierEdited.current && !initialSupplier.current && matches.data?.cands.length === 1) {
      supplierBaseline.current=matches.data.cands[0]!;setSupplier(supplierBaseline.current);
    }
  }, [matches.data]);
  function chooseSupplier(value: string) {
    supplierEdited.current = true;setSupplier(value);
    if (chosen && chosen.supplier !== value.trim()) setSelected(null);
  }
  function goStep(value: number) { setStep(value); }
  useHistoryGuard('contract', () => saved ? '关联结果待核实，请先重读核对。' : busy || lock.current ? '合同关联正在保存，请稍候。' : dirty ? '供应商与合同关联有未保存选择，请先处理。' : '');
  const modifying = Boolean(data?.current_contract_id), unavailable = blocked || busy || saved || query.isFetching || !data;
  useEffect(() => { if (decision !== 'none') decisionTitle.current?.focus(); else stepHeading.current?.focus(); }, [decision,step]);
  function requestClose() { if (busy || saved) return; if (dirty) setDecision('discard'); else close(); }
  async function save(action: 'link'|'unlink'|'supplier' = 'link') {
    if (unavailable || lock.current || action !== 'unlink' && readOnly || action === 'supplier' && modifying || action === 'link' && (!chosen || chosen.id === current?.id || !rows.some(c => c.id === chosen.id))) return;
    lock.current=true;setBusy(true);setError('');let written=false;
    try {
      const result = await requestJson(action === 'supplier' ? '/api/m03/actions/jc-supplier' : action === 'unlink' ? '/api/m11/unlink' : '/api/m11/link',{method:'POST',...body({notice_id:row.notice_id,...(action === 'supplier' ? {supplier:supplier.trim()} : action === 'link' ? {contract_id:chosen!.id} : {})})});
      written=true;setSaved(true);announce(receipt(result));await refresh();close();
    } catch (failure) {
      setDecision('none');
      const unknown=uncertainWrite(failure);
      if(unknown)setSaved(true);
      setError(`${written ? '关联已保存，列表尚待重读核对，勿重复保存。' : unknown ? '关联结果待核实，请重读核对，勿重复保存。' : ''}${failure instanceof Error ? failure.message : '关联未保存，请重试。'}`);
    }
    finally { lock.current=false;setBusy(false); }
  }
  async function readBack() {
    if (busy || lock.current) return;
    lock.current=true;setBusy(true);
    try {
      await refresh();
      const latest=readNotices(await requestJson('/api/m03/notice-list?period='));
      const actual=latest.find(item => item.notice_id === row.notice_id && item.bill_no === row.bill_no);
      if (!actual) throw new Error('未读到本条通知书，请继续核对。');
      announce(`已重读核对：${actual.has_link ? '已关联合同' : '未关联合同'}，${actual.jc_supplier || '供应商未录入'}`);
      close();
    } catch (failure) { setError(`结果仍待核实，请重读核对。${failure instanceof Error ? failure.message : ''}`); }
    finally {lock.current=false;setBusy(false);}
  }
  return <BusinessModal open={!blocked} className="project-dialog contract-dialog notice-association-dialog" titleId="contract-dialog-title" requestClose={requestClose}>    {decision === 'discard' ? <DiscardConfirmation titleId="contract-dialog-title" headingRef={decisionTitle} closing={{busy,resume:() => setDecision('none'),discard:close}} /> : decision === 'unlink' ? <div className="contract-decision"><h2 ref={decisionTitle} tabIndex={-1} id="contract-dialog-title">解除当前合同关联？</h2><p>{current ? contractName(current) : '当前合同'}</p><div className="dialog-actions"><Button htmlType="button" disabled={busy} onClick={() => setDecision('none')}>返回</Button><Button htmlType="button" className="danger" disabled={busy} onClick={() => void save('unlink')}>确认解除</Button></div></div> : <>
      <div className="contract-fixed-header"><div className="contract-dialog-heading"><h2 id="contract-dialog-title">供应商与合同关联</h2><Button htmlType="submit" ref={closeButton} className="contract-close" aria-label="关闭合同关联" disabled={busy || saved} onClick={requestClose}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></Button></div>
      <nav className="association-steps" aria-label="关联步骤"><span aria-current={step === 1 ? 'step' : undefined}>1，确认供应商</span><span aria-current={step === 2 ? 'step' : undefined}>2，选择合同</span><small>确认前不会改变现有关联</small></nav>
      {step === 2 && <div className="contract-notice"><div><strong>{row.bill_name || row.bill_no}</strong><span>{row.project_display}，{row.bill_no}，{data?.supplier || row.jc_supplier || '供应商未录入'}</span></div><div className="contract-notice-amount"><span>通知书审批金额</span><strong>{money(data?.notice_amount ?? row.amount_approved)}<small> 元</small></strong></div></div>}
      </div>
      <h3 className="association-step-heading" ref={stepHeading} tabIndex={-1}>{step === 1 ? '确认供应商' : '选择合同'}</h3>
      {readOnly && <p className="notice">本条仅可查看、解除现有关联。供应商由当前合同确定。</p>}
      {step === 1 ? <SupplierStep row={row} supplier={supplier} choose={chooseSupplier} matches={matches.data} loading={matches.isLoading} error={matches.isError ? matches.error.message : ''} retry={() => void matches.refetch()} contracts={rows.filter(c => c.supplier === supplier.trim() || !supplier.trim())} contractLoading={query.isFetching} contractError={query.isError ? query.error.message : ''} retryContracts={() => void query.refetch()} current={current} disabled={unavailable || readOnly} /> : <>
      {query.isPending ? <p role="status" className="contract-loading">正在读取合同与发票…</p> : query.isError ? <p role="alert" className="notice">{query.error.message}<Button htmlType="submit" onClick={() => void query.refetch()}>重读候选</Button></p> : data && <>
        {modifying && <div className="contract-current"><span className="contract-state">当前关联</span><strong>{current ? contractName(current) : '当前合同不在候选中'}</strong><span>{current?.contract_no}</span><Link to={`/contracts?contract=${data.current_contract_id}`}>查看合同详情</Link></div>}
        {rows.filter(candidate => candidate.recommendation.reasons.some(reason => reason.kind === 'invoice')).length > 1 && <p className="contract-candidate-note">多份合同的发票金额均可对应，请核对材料和合同号。</p>}
        {rows.length === 0 ? <p className="contract-empty">本项目、供应商下没有可选合同，请核对项目归属和供应商。</p> : <Virtuoso className="contract-candidates" role="radiogroup" aria-label={modifying ? '选择拟换合同' : '选择关联合同'} data={rows} computeItemKey={(_index,candidate)=>candidate.id} itemContent={(_index,candidate) => {
          const isCurrent = candidate.id === data.current_contract_id, isSelected = selected === candidate.id, recommended = candidate.recommendation.reasons.length > 0;
          return <div className="contract-candidate-item"><article className={`contract-candidate${isSelected ? ' is-selected' : ''}`} key={candidate.id}>
            <div className="contract-candidate-heading"><label className="contract-choice"><Radio name="contract-choice" aria-label={`选择${contractName(candidate)}，${candidate.contract_no}`} checked={isSelected} disabled={unavailable || readOnly} onChange={() => setSelected(candidate.id)} /><span><strong>{contractName(candidate)}</strong><small>{candidate.supplier}，{candidate.date || '合同日期未填'}，{candidate.contract_no || '合同号未填'}</small></span></label><div className="contract-states">{isCurrent && <span className="contract-state">当前关联</span>}{recommended && <span className="contract-state recommended">推荐</span>}{isSelected && <span className="contract-state selected">{modifying && !isCurrent ? '拟换合同' : '已选择'}</span>}</div></div>
            <div className={`contract-invoice-grid${hasTradeSide(candidate) ? ' has-trade' : ''}`}><InvoiceSide candidate={candidate} kind="supplier" />{hasTradeSide(candidate) && <InvoiceSide candidate={candidate} kind="trade" />}</div>
            <Recommendation candidate={candidate} amount={data.notice_amount} />
          </article></div>;
        }}/>}
      </>}
      {chosen && <div className="contract-selection" role="status"><div><span>{modifying ? chosen.id === current?.id ? '保持当前关联' : '拟换合同' : '已选合同'}</span><strong>{contractName(chosen)}</strong></div><div><span>关联前欠款</span><b>{money(chosen.debt)} 元</b></div><div><span>本条统计付款</span><b>{money(row.stat_paid)} 元</b></div><p className="contract-match">{cents(chosen.debt) === cents(row.stat_paid) ? '金额一致' : '金额不一致，仍可关联'}</p></div>}
      </>}
      {error && <p className="notice" role="alert">{error}{saved && <Button disabled={busy} onClick={() => void readBack()}>重读核对</Button>}</p>}
      <div className="contract-footer"><div>{modifying && <Button htmlType="submit" className="danger" disabled={unavailable} onClick={() => setDecision('unlink')}>解除当前关联</Button>}</div><div className="dialog-actions">{step === 2 && <Button disabled={busy || saved} onClick={() => goStep(1)}>上一步</Button>}<Button htmlType="button" disabled={busy || saved} onClick={requestClose}>{saved ? '请先重读核对' : '取消'}</Button>{step === 1 ? <>{!modifying && <Button disabled={unavailable || readOnly || supplier.trim() === initialSupplier.current} onClick={() => void save('supplier')}>记住供应商，稍后关联</Button>}<Button type="primary" disabled={unavailable} onClick={() => goStep(2)}>下一步：选择合同</Button></> : !readOnly && <Button htmlType="button" type="primary" disabled={unavailable || !chosen || chosen.id === current?.id} onClick={() => void save()}>{busy ? '正在保存…' : modifying ? '确认修改关联' : '确认关联'}</Button>}</div></div>
    </>}
  </BusinessModal>;
}
