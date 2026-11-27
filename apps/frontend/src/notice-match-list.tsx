import Button from 'antd/es/button';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Virtuoso } from 'react-virtuoso';
import { money } from './api';
import type { FinishedNoticeFetchJob } from './notice-fetch-job-data';
import type { MatchCandidate, ReadyMatch, ReviewMatch } from './notice-link-matches';

export function MatchItems<T>({ items, itemKey, render }: {
  items: readonly T[]; itemKey: (item: T) => string | number; render: (item: T) => ReactNode;
}) {
  if (items.length > 12) {
    return <Virtuoso className="notice-match-list notice-match-list--scroll" style={{ height: 'min(280px, 28dvh)' }} data={items}
      computeItemKey={(_, item) => itemKey(item)} itemContent={(_, item) => render(item)} />;
  }
  return <div className="notice-match-list">{items.map(item => <div key={itemKey(item)}>{render(item)}</div>)}</div>;
}

function CandidateEvidence({ candidate }: { candidate: MatchCandidate }) {
  return <>
    {candidate.evidence.length > 0 && <p>{candidate.evidence.join('、')}</p>}
    {candidate.payable_codes.length > 0 && <p>采购应付单号 {candidate.payable_codes.join('、')}</p>}
  </>;
}

function CandidateIdentity({ candidate }: { candidate: MatchCandidate }) {
  return <div className="notice-match-facts">
    <strong>{candidate.contract_no || '无合同编号'}</strong>
    {candidate.supplier_name && <span>{candidate.supplier_name}</span>}
    {candidate.material && <span>{candidate.material}</span>}
  </div>;
}

export function ReadyMatchItem({ row }: { row: ReadyMatch }) {
  return <div className="notice-match-item">
    <div className="notice-match-facts"><strong>{row.code}</strong><span>{money(row.expected_amount)} 元</span></div>
    <CandidateIdentity candidate={row.target} />
    <p>{row.reason}{row.payable_codes.length > 0 && `，采购应付单号 ${row.payable_codes.join('、')}`}</p>
  </div>;
}

export function ReviewMatchItem({ row, selected, choose, openManualLink, disabled = false }: {
  row: ReviewMatch; selected?: number | undefined; choose?: (choice: number) => void;
  openManualLink?: () => void; disabled?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const picked = row.candidates.find(candidate => candidate.selectable && candidate.contract_id === selected);
  const canSelect = row.candidates.some(candidate => candidate.selectable);
  return <div className="notice-match-item">
    <details onToggle={event => setExpanded(event.currentTarget.open)}>
      <summary><span className="notice-match-facts">
        <strong>{row.code}</strong><span>{money(row.expected_amount)} 元</span>
        <span>{picked ? `已选 ${picked.contract_no || picked.supplier_name}` : row.reason}</span>
      </span></summary>
      {expanded && <>
        <p className="notice-match-facts"><span>{row.project_name}</span><span>{row.title}</span></p>
        <MatchItems items={row.candidates} itemKey={candidate => candidate.contract_id} render={candidate => {
          const isSelected = picked?.contract_id === candidate.contract_id;
          return <div className={`notice-match-candidate${isSelected ? ' is-selected' : ''}`}>
            <CandidateIdentity candidate={candidate} />
            <CandidateEvidence candidate={candidate} />
            {choose && candidate.selectable && <Button htmlType="button"
              disabled={disabled} aria-pressed={isSelected}
              onClick={() => choose(candidate.contract_id)}>
              {isSelected ? '取消选择' : '选择合同'}
            </Button>}
          </div>;
        }} />
      </>}
    </details>
    {!canSelect && <div className="notice-match-manual">
      <span className="muted">{row.candidates.length ? '候选合同均不可批量确认。' : '暂无合同候选。'}</span>
      {openManualLink && <Button htmlType="button" disabled={disabled} onClick={openManualLink}>去手动关联</Button>}
    </div>}
  </div>;
}

export function FetchMatchDetails({ result }: { result: FinishedNoticeFetchJob['result'] }) {
  return <>
    <section className="notice-match-section">
      <h3>已自动关联 {result.auto_linked} 条</h3>
      <MatchItems items={result.auto_linked_items} itemKey={row => row.notice_id} render={row => <ReadyMatchItem row={row} />} />
    </section>
    <section className="notice-match-section">
      <h3>待人工核对 {result.manual_review} 条</h3>
      <MatchItems items={result.manual_review_items} itemKey={row => row.notice_id} render={row => <ReviewMatchItem row={row} />} />
    </section>
    {result.ignored.length > 0 && <details className="notice-match-section">
      <summary>待归属明细</summary>
      <MatchItems items={result.ignored} itemKey={row => row.bill_no} render={row =>
        <div className="notice-match-item"><strong>{row.bill_no}</strong><p className="notice-match-facts"><span>{row.project_name}</span><span>{row.doc_name}</span></p><p>{row.reason}</p></div>} />
    </details>}
  </>;
}
