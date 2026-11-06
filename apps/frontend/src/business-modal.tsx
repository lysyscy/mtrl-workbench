import Modal from 'antd/es/modal';
import type { ReactNode } from 'react';
import { createContext, useContext, useEffect, useId, useRef } from 'react';
import { usePresence } from 'motion/react';
import { MotionAccess, useWorkspaceReducedMotion } from './workspace-motion';

export const BusinessModalTitle = createContext<string | null>(null);

// Only the close protocol belongs here; drafts and request state stay with the caller.
export function BusinessModal({ open, requestClose, className, titleId, children, centered = true }: {
  open: boolean; requestClose: () => unknown; className: string; titleId: string; children: ReactNode; centered?: boolean;
}) {
  const [present, safeToRemove] = usePresence();
  const allowed = useContext(MotionAccess), reduced = useWorkspaceReducedMotion();
  const accessibleTitleId = `${titleId}-${useId()}`;
  const visible = open && present && allowed;
  const previous = useRef<HTMLElement | null>(null), wasOpen = useRef(false), mounted = useRef(false);
  const currentOpen = useRef(visible), body = useRef<HTMLDivElement>(null); currentOpen.current = visible;
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
  useEffect(() => { if (!visible) restore(); }, [visible]);
  useEffect(() => { if (!present && (!open || reduced || !allowed)) safeToRemove?.(); }, [present, open, reduced, allowed, safeToRemove]);
  // rc-dialog labels only its own header; our heading lives in the body.
  if (!present && (reduced || !allowed)) return null;
  return <Modal open={visible} afterClose={() => { if (!present) safeToRemove?.(); }} onCancel={() => { if (visible) requestClose(); }} footer={null} closable={false} keyboard={visible} centered={centered}
    mask={{ closable: true }} width="max-content" focusable={{ focusTriggerAfterClose: false }}
    rootClassName={visible ? 'business-modal-root' : 'business-modal-root business-modal-leaving'} transitionName="business-dialog-motion"
    rootStyle={{ opacity: allowed ? undefined : 0, pointerEvents: allowed ? undefined : 'none' }}
    panelRef={panel => { if (panel) { panel.setAttribute('aria-labelledby', accessibleTitleId); panel.inert = !visible; panel.setAttribute('aria-hidden', String(!visible)); } }} className="business-modal" destroyOnHidden={false}>
    <BusinessModalTitle.Provider value={accessibleTitleId}><div ref={body} inert={!visible} className={className}>{children}</div></BusinessModalTitle.Provider>
  </Modal>;
}
