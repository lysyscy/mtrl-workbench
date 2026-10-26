import Modal from 'antd/es/modal';
import type { ReactNode } from 'react';
import { useEffect, useRef } from 'react';

// Only the close protocol belongs here; drafts and request state stay with the caller.
export function BusinessModal({ open, requestClose, className, titleId, children }: {
  open: boolean; requestClose: () => unknown; className: string; titleId: string; children: ReactNode;
}) {
  const previous = useRef<HTMLElement | null>(null), wasOpen = useRef(false), mounted = useRef(false);
  const currentOpen = useRef(open), body = useRef<HTMLDivElement>(null); currentOpen.current = open;
  if (open && !wasOpen.current) previous.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  wasOpen.current = open;
  function restore() {
    requestAnimationFrame(() => {
      if (mounted.current && currentOpen.current) return;
      const target = previous.current;
      if (target?.isConnected && !target.closest('[hidden],[inert]') && (document.activeElement === document.body || body.current?.contains(document.activeElement))) target.focus({ preventScroll: true });
    });
  }
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; restore(); }; }, []);
  useEffect(() => { if (!open) restore(); }, [open]);
  // rc-dialog labels only its own header; our heading lives in the body.
  return <Modal open={open} onCancel={requestClose} footer={null} closable={false} keyboard centered
    mask={{ closable: true }} width="max-content" focusable={{ focusTriggerAfterClose: false }}
    panelRef={panel => { panel?.setAttribute('aria-labelledby', titleId); }} className="business-modal" destroyOnHidden={false}>
    <div ref={body} className={className}>{children}</div>
  </Modal>;
}
