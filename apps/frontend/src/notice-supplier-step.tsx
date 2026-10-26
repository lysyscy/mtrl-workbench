import Button from 'antd/es/button';
import type { NoticeRow } from './notices-api';
import { money } from './notices-api';
import type { Candidate } from './notice-contract';

interface Props {
  row: NoticeRow; supplier: string; choose: (value: string) => void;
  matches: {pool:string[];cands:string[];level:number;level_name:string} | undefined;
  loading: boolean; error: string; retry: () => void;
  contracts: Candidate[]; contractLoading: boolean; contractError: string; retryContracts: () => void;
  current: Candidate | undefined; disabled: boolean;
}
export function SupplierStep({row,supplier,choose,matches,loading,error,retry,contracts,contractLoading,contractError,retryContracts,current,disabled}: Props) {
  const names = matches?.cands ?? [];
  const pool = matches?.pool.filter(name => !names.includes(name) && name.includes(supplier.trim())) ?? [];
  return <div className="association-supplier-pane">
    <aside className="association-reference" aria-label="当前通知书">
      <h3>当前通知书</h3><strong className="association-reference-name">{row.bill_name || row.bill_no}</strong>
      <dl className="association-reference-facts"><div><dt>付款项目</dt><dd>{row.project_display}</dd></div><div><dt>单据编码</dt><dd>{row.bill_no}</dd></div></dl>
      <dl className="association-reference-amounts"><div><dt>审批金额</dt><dd>{money(row.amount_approved)}<small>元</small></dd></div><div><dt>统计付款金额</dt><dd>{money(row.stat_paid)}<small>元</small></dd></div></dl>
      <div className="association-reference-state"><strong>{current ? '已关联合同' : '尚未关联合同'}</strong><p>{current ? `${current.material}，${current.contract_no}` : '确认合同后，供应商随合同一并确定。'}</p></div>
      <p className="association-reference-foot">供应商用于收窄下一步的合同范围；也可留空查看本项目全部合同。</p>
    </aside>
    <section className="association-supplier-main" aria-label="供应商选择">
      <h3>确认供应商</h3>
      {loading && <p role="status">正在匹配供应商…</p>}
      {error && <p role="alert" className="notice">{error}<Button onClick={retry}>重读供应商</Button></p>}
      {matches && <p>{matches.level_name}，命中 {names.length} 家{names.length > 1 ? '，请选择，不自动取第一家。' : names.length === 1 ? '，请核对后继续。' : '，可手工指定。'}</p>}
      {matches?.level === 4 && <p className="danger">仅2字片段命中，请核对供应商全名。</p>}
      {names.length > 0 && <div className="association-candidate-list" role="radiogroup" aria-label="匹配的供应商">{names.map(name => <label className="notice-choice" key={name}><input type="radio" name="supplier-candidate" checked={supplier === name} disabled={disabled} onChange={() => choose(name)} /><span>{name}</span></label>)}</div>}
      <label className="association-supplier-input">供应商名称<input value={supplier} maxLength={128} disabled={disabled} onChange={e => choose(e.target.value)} /></label>
      {matches && !matches.pool.length && <p>本项目暂无集采合同供应商，可直接录入全名。</p>}
      {pool.length > 0 && (supplier.trim() || names.length === 0) && <div className="association-candidate-list" role="group" aria-label="本项目其他供应商">{pool.map(name => <Button className="notice-pool" key={name} disabled={disabled} onClick={() => choose(name)}>{name}</Button>)}</div>}
      <section className="association-contract-glance" aria-label="下一步合同范围"><div className="association-glance-heading"><h3>{supplier.trim() ? '下一步，该供应商的合同' : '下一步，本项目全部合同'}</h3><span>{contractLoading ? '读取中…' : `${contracts.length} 份`}</span></div>
        {contractError ? <p role="alert">{contractError}<Button onClick={retryContracts}>重读合同</Button></p> : <><ul>{contracts.slice(0,3).map(contract => <li key={contract.id}><div><strong>{contract.material || '材料名称未填'}</strong>{contract.id === current?.id && <span className="association-current-mark">当前关联</span>}<small>{contract.contract_no || '合同号未填'}，{contract.supplier}</small></div><div className="association-glance-amount">{money(contract.contract_amt)} 元</div></li>)}</ul>{!contractLoading && contracts.length === 0 && <p className="association-glance-empty">暂无可选合同，可调整供应商，或先记住供应商稍后关联。</p>}<p className="association-glance-foot">{contracts.length > 3 ? `另有 ${contracts.length-3} 份，` : ''}下一步查看合同、发票和金额，选择后再确认关联。</p></>}
      </section>
    </section>
  </div>;
}
