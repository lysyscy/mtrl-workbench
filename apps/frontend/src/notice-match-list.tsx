import Button from 'antd/es/button';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Virtuoso } from 'react-virtuoso';
import { money } from './api';
import type { MatchCandidate, ReadyMatch, ReviewMatch } from './notice-link-matches';

export function MatchItems<T>({ items, itemKey, render }: {
  items: readonly T[]; itemKey: (item: T) => string | number; render: (item: T) => ReactNode;
}) {
  if (items.length > 12) {
    return <Virtuoso className="notice-match-list notice-match-list--scroll" data={items}
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

function contractText(candidate: MatchCandidate) {
  return [candidate.contract_no || '无合同编号', candidate.supplier_name, candidate.material].filter(Boolean).join('　');
}

export function ReadyMatchItem({ row }: { row: ReadyMatch }) {
  return <div className="notice-match-item">
    <strong>{row.code}</strong> <span>{money(row.expected_amount)} 元</span>
    <p>{contractText(row.target)}</p>
    <p>{row.reason}{row.payable_codes.length > 0 && `，采购应付单号 ${row.payable_codes.join('、')}`}</p>
  </div>;
}

export function ReviewMatchItem({ row, selected, choose, disabled = false }: {
  row: ReviewMatch; selected?: number | undefined; choose?: (choice: number) => void; disabled?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const picked = row.candidates.find(c => c.contract_id === selected);
  return <details className="notice-match-item" onToggle={event => setExpanded(event.currentTarget.open)}>
    <summary><strong>{row.code}</strong> <span>{money(row.expected_amount)} 元</span>{' '}
      <span>{picked ? `已选 ${picked.contract_no || picked.supplier_name}` : row.reason}</span>
    </summary>
    {expanded && <>
      <p>{[row.project_name, row.title].filter(Boolean).join('　')}</p>
      {!row.candidates.length ? <p>暂无合同候选</p> :
        <MatchItems items={row.candidates} itemKey={candidate => candidate.contract_id} render={candidate =>
          <div className="notice-match-candidate">
            <strong>{contractText(candidate)}</strong>
            <CandidateEvidence candidate={candidate} />
            {choose && candidate.selectable && <Button
              disabled={disabled} aria-pressed={selected === candidate.contract_id}
              onClick={() => choose(candidate.contract_id)}>
              {selected === candidate.contract_id ? '取消选择' : '选择合同'}
            </Button>}
          </div>
        } />}
    </>}
  </details>;
}
