import Button from 'antd/es/button';
import { useId, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, body, requestJson, uncertainWrite } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { sessionPayload } from './i8-browser-relay';
import type { SessionChoice } from './i8-browser-relay';
import { I8ConnectionWaitStatus, useI8ActionWait, useI8Session } from './i8-session';
import { I8KickConfirmationActions, useI8KickConfirmation } from './i8-kick-confirmation';
import { readLinkConfirmation, readMatchPreview, readyLinkSelections, reviewLinkSelections } from './notice-link-matches';
import type { LinkConfirmationRow } from './notice-link-matches';
import { MatchItems, ReadyMatchItem, ReviewMatchItem } from './notice-match-list';

type MatchGroups = Extract<ReturnType<typeof readMatchPreview>, { kind: 'preview' }>['groups'];

export function AutoLinkDialog({ ids, blocked, close, refresh, announce, openManualLink }: {
  ids: number[]; blocked: boolean; close: () => void; refresh: () => Promise<void>;
  announce: (message: string, needsAttention?: boolean) => void;
  openManualLink: (noticeId: number) => boolean;
}) {
  const lock = useRef(false);
  const manualNotice = useRef<number | null>(null);
  const [groups, setGroups] = useState<MatchGroups>();
  const [choices, setChoices] = useState(new Map<number, number>());
  const [results, setResults] = useState(new Map<number, LinkConfirmationRow>());
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState('');
  const session = useI8Session();
  const scopeKey = JSON.stringify([ids, blocked, session.actionKey]);
  const currentScope = useRef<string | null>(null);
  useLayoutEffect(() => {
    currentScope.current = scopeKey;
    return () => { currentScope.current = null; };
  }, [scopeKey]);
  const { waiting, cancelWaiting, runWhenReady } = useI8ActionWait(scopeKey);
  const kick = useI8KickConfirmation(scopeKey);
  const kickMessageId = useId();
  const closing = useDialogClose({
    busy, dirty: choices.size > 0, active: !blocked,
    close: () => {
      const noticeId = manualNotice.current;
      manualNotice.current = null;
      if (noticeId !== null && !openManualLink(noticeId)) {
        setError('这条通知书已无法手动关联，请重读列表核对。');
        return;
      }
      cancelWaiting(); kick.dismiss(); close();
    },
  });
  const closeState = { ...closing, resume: () => { manualNotice.current = null; closing.resume(); } };

  const ready = groups?.auto_ready.filter(row => !results.has(row.notice_id)) ?? [];
  const review = groups?.needs_review.filter(row => !results.has(row.notice_id)) ?? [];
  const canSelectReview = review.some(row => row.candidates.some(candidate => candidate.selectable));
  const selected = reviewLinkSelections(review, choices);
  const linked = [...results.values()].filter(row => row.contract_id !== null);
  const skipped = [...(groups?.skipped ?? []), ...[...results.values()].filter(row => row.contract_id === null)];

  async function preview(choice?: SessionChoice, kickToken?: string) {
    if (currentScope.current !== scopeKey || blocked || lock.current || groups || !ids.length || !kickToken && kick.message) return;
    lock.current = true;
    setBusy(true);
    setError('');
    let readPayables = false;
    try {
      const sessionFields = choice ? sessionPayload(choice, kickToken ? { kick_token: kickToken } : {}) : {};
      const value = await requestJson('/api/m11/auto-link-preview', { method: 'POST', ...body({ notice_ids: ids, ...sessionFields }) });
      const result = readMatchPreview(value, ids);
      if (currentScope.current !== scopeKey) return;
      if (result.kind === 'preview') setGroups(result.groups);
      else if (!choice) readPayables = true;
      else throw new ApiError('采购应付还未读到，请重新预览。');
    } catch (failure) {
      if (!choice || kickToken || !kick.offer(failure, token => preview(choice, token))) {
        setError(failure instanceof Error ? failure.message : '关联预览失败，请重试。');
      }
    } finally {
      lock.current = false;
      setBusy(false);
    }
    if (readPayables && currentScope.current === scopeKey) void runWhenReady(next => preview(next));
  }

  async function confirm(selections: ReturnType<typeof readyLinkSelections>) {
    if (blocked || lock.current || uncertain || !selections.length) return;
    lock.current = true;
    setBusy(true);
    setError('');
    let verified = '';
    try {
      const value = await requestJson('/api/m11/auto-link', { method: 'POST', ...body({ selections }) });
      const result = readLinkConfirmation(value, selections);
      setResults(previous => new Map([...previous, ...result.rows.map(row => [row.notice_id, row] as const)]));
      setChoices(previous => {
        const next = new Map(previous);
        for (const row of result.rows) next.delete(row.notice_id);
        return next;
      });
      verified = `已关联 ${result.linked} 条，跳过 ${selections.length - result.linked} 条。`;
      await refresh();
      announce(verified);
    } catch (failure) {
      const detail = failure instanceof Error ? failure.message : '操作失败，请重试。';
      if (verified || uncertainWrite(failure)) {
        setUncertain(true);
        const warning = `${verified || '关联结果待核对。'}请重读列表核对。 ${detail}`;
        setError(warning);
        announce(warning, true);
      } else setError(detail);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  function choose(noticeId: number, contractId: number) {
    setChoices(previous => {
      const next = new Map(previous);
      if (next.get(noticeId) === contractId) next.delete(noticeId);
      else next.set(noticeId, contractId);
      return next;
    });
  }

  const confirmDisabled = blocked || busy || uncertain;
  return <BusinessModal open={!blocked} layout={groups ? 'scroll-body' : 'compact'}
    className={groups ? 'project-dialog notice-contract-dialog' : 'project-dialog'}
    titleId="auto-link-title" requestClose={closing.requestClose}>
    <DialogContents title="批量关联集采合同" titleId="auto-link-title" closing={closeState}>
      <div className="dialog-body">
        {!groups && <p>预览 {ids.length} 条通知书。需要核对金额时会读取 i8 采购应付。</p>}
        {waiting && <I8ConnectionWaitStatus />}
        {busy && <p role="status">{groups ? '正在保存关联…' : '正在生成预览…'}</p>}
        {groups && <>
          {ready.length ? <section className="notice-match-section">
            <div className="notice-match-heading"><h3>可直接关联 {ready.length} 条</h3>
              <Button type="primary" disabled={confirmDisabled}
                onClick={() => void confirm(readyLinkSelections(ready))}>关联这 {ready.length} 条</Button>
            </div>
            <MatchItems items={ready} itemKey={row => row.notice_id} render={row => <ReadyMatchItem row={row} />} />
          </section> : <p className="notice-match-summary muted">可直接关联 0 条</p>}
          <section className="notice-match-section">
            <div className="notice-match-heading"><h3>需核对 {review.length} 条</h3>
              {canSelectReview && <Button disabled={confirmDisabled || !selected.length}
                onClick={() => void confirm(selected)}>确认已选 {selected.length} 条</Button>}
            </div>
            <MatchItems items={review} itemKey={row => row.notice_id} render={row =>
              <ReviewMatchItem row={row} selected={choices.get(row.notice_id)} disabled={confirmDisabled}
                choose={contractId => choose(row.notice_id, contractId)}
                openManualLink={() => {
                  manualNotice.current = row.notice_id;
                  closing.requestClose();
                }} />} />
          </section>
          {linked.length > 0 && <details className="notice-match-section">
            <summary>已关联 {linked.length} 条</summary>
            <MatchItems items={linked} itemKey={row => row.notice_id} render={row =>
              <div className="notice-match-item notice-match-facts"><strong>{row.code}</strong><span>{row.contract_no}</span></div>} />
          </details>}
          <details className="notice-match-section">
            <summary>已跳过 {skipped.length} 条</summary>
            <MatchItems items={skipped} itemKey={row => row.notice_id} render={row =>
              <div className="notice-match-item notice-match-facts"><strong>{row.code}</strong><span>{row.reason}</span></div>} />
          </details>
        </>}
        {error && <p className="notice" role="alert">{error}</p>}
        {kick.message && <p className="notice" role="status" id={kickMessageId}>{kick.message}</p>}
        {kick.revocationNotice && <p className="notice" role="status">{kick.revocationNotice}</p>}
      </div>
      {kick.message ? <I8KickConfirmationActions {...kick} descriptionId={kickMessageId} disabled={blocked || busy || waiting} /> :
        <div className="dialog-actions">
          <Button htmlType="button" disabled={busy} onClick={closing.requestClose}>{groups ? '关闭' : '取消'}</Button>
          {waiting && <Button htmlType="button" onClick={cancelWaiting}>取消等待</Button>}
          {!groups && <Button htmlType="button" type="primary" disabled={blocked || busy || waiting || !ids.length}
            onClick={() => void preview()}>确认读取并预览</Button>}
        </div>}
    </DialogContents>
  </BusinessModal>;
}
