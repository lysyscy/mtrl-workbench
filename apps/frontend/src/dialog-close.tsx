import Button from 'antd/es/button';
import { useId } from 'react';
import { useHistoryGuard } from './history';
import { useEffect, useRef, useState } from 'react';
import type { MouseEvent, ReactNode, SyntheticEvent } from 'react';

export function useDialogClose({ busy, dirty, close, active = true }: { busy: boolean; dirty: boolean; close: () => void; active?: boolean }) {
  const id = useId();
  useHistoryGuard(id, () => !active ? '' : busy ? '正在处理操作，请稍候。' : dirty ? '有未保存输入，请先处理。' : '');
  const [confirming, setConfirming] = useState(false);
  function requestClose() {
    if (busy) return false;
    if (dirty) { setConfirming(true); return false; }
    close(); return true;
  }
  return {
    busy, confirming, requestClose,
    resume: () => setConfirming(false),
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
export function DialogContents({ title, titleId, closing, children }: { title: ReactNode; titleId: string; closing: DialogCloseState; children: ReactNode }) {
  const decisionTitle = useRef<HTMLHeadingElement>(null), previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (closing.confirming) {
      previousFocus.current = document.activeElement as HTMLElement | null;
      decisionTitle.current?.focus();
    } else if (previousFocus.current?.isConnected) {
      previousFocus.current.focus(); previousFocus.current = null;
    }
  }, [closing.confirming]);
  return <>
    {closing.confirming && <div className="dialog-discard"><h2 ref={decisionTitle} tabIndex={-1} id={titleId}>放弃未保存的修改？</h2><p>本次输入和选择尚未保存。</p><div className="dialog-actions"><Button htmlType="button" disabled={closing.busy} onClick={closing.resume}>继续编辑</Button><Button htmlType="button" className="primary" disabled={closing.busy} onClick={closing.discard}>放弃并关闭</Button></div></div>}
    <div hidden={closing.confirming}>
      <div className="dialog-close-heading"><h2 id={closing.confirming ? undefined : titleId}>{title}</h2><Button htmlType="button" className="dialog-close-button" aria-label="关闭弹窗" disabled={closing.busy} onClick={closing.requestClose}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></Button></div>
      {children}
    </div>
  </>;
}
