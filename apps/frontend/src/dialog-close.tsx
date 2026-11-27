import Button from 'antd/es/button';
import { useContext, useId, useRef, useState } from 'react';
import { BusinessModalTitle } from './business-modal';
import { useHistoryGuard } from './history';
import type { ComponentProps, MouseEvent, ReactNode, SyntheticEvent } from 'react';

export function useDialogClose({ busy, dirty, close, beforeRequestClose, active = true, open = true }: {
  busy: boolean; dirty: boolean; close: () => void; beforeRequestClose?: () => void; active?: boolean; open?: boolean;
}) {
  const id = useId();
  // Most editors mount when opened. A retained open editor still owns its draft
  // after the user changes pages. Only a document reload would discard it.
  useHistoryGuard(id, action => {
    if (!open || (action === 'history' && !active)) return '';
    return busy ? '正在处理操作，请稍候。' : dirty ? '有未保存输入，请先处理。' : '';
  });
  const [confirming, setConfirming] = useState(false);
  const previousFocus = useRef<HTMLElement | null>(null);
  function requestClose() {
    if (busy) return false;
    beforeRequestClose?.();
    if (dirty) {
      if (!confirming) {
        const focused = globalThis.document?.activeElement;
        previousFocus.current = focused && focused instanceof HTMLElement ? focused : null;
      }
      setConfirming(true);
      return false;
    }
    close(); return true;
  }
  return {
    busy, confirming, requestClose,
    resume: () => {
      setConfirming(false);
      const target = previousFocus.current;
      previousFocus.current = null;
      if (target) requestAnimationFrame(() => {
        if (target.isConnected && !target.closest('[hidden],[inert]')) target.focus({ preventScroll: true });
      });
    },
    discard: () => { if (!busy) { setConfirming(false); close(); } },
    dialogProps: {
      onCancel: (event: SyntheticEvent<HTMLDialogElement>) => { event.preventDefault(); requestClose(); },
      onClick: (event: MouseEvent<HTMLDialogElement>) => {
        if (event.target !== event.currentTarget) return;
        const box = event.currentTarget.getBoundingClientRect();
        if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) requestClose();
      },
    },
  };
}

export type DialogCloseState = ReturnType<typeof useDialogClose>;
export function DialogHeading({ id, ...props }: ComponentProps<'h2'>) {
  const titleId = useContext(BusinessModalTitle) ?? id;
  return <h2 {...props} id={titleId} />;
}
export function DiscardConfirmation({ titleId, closing }: { titleId: string; closing: Pick<DialogCloseState,'busy'|'resume'|'discard'> }) {
  return <div className="dialog-discard">
    <DialogHeading id={titleId}>放弃未保存的修改？</DialogHeading>
    <p>本次输入和选择尚未保存。</p>
    <div className="dialog-actions">
      <Button htmlType="button" type="primary" autoFocus disabled={closing.busy} onClick={closing.resume}>继续编辑</Button>
      <Button htmlType="button" danger disabled={closing.busy} onClick={closing.discard}>放弃并关闭</Button>
    </div>
  </div>;
}

export function DialogContents({ title, titleId: requestedTitleId, closing, footer, children }: { title: ReactNode; titleId: string; closing: DialogCloseState; footer?: ReactNode; children: ReactNode }) {
  const titleId = useContext(BusinessModalTitle) ?? requestedTitleId;
  return <>
    {closing.confirming && <DiscardConfirmation titleId={titleId} closing={closing} />}
    <div className="dialog-frame" hidden={closing.confirming}>
      <div className="dialog-close-heading"><h2 id={closing.confirming ? undefined : titleId}>{title}</h2><Button htmlType="button" className="dialog-close-button" aria-label="关闭弹窗" disabled={closing.busy} onClick={closing.requestClose}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></Button></div>
      {footer !== undefined ? <><div className="dialog-body">{children}</div><div className="dialog-footer">{footer}</div></> : children}
    </div>
  </>;
}
