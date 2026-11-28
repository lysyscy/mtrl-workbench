import Modal from 'antd/es/modal';
import type { ReactNode } from 'react';
import { createContext, useContext, useEffect, useId, useRef } from 'react';
import { usePresence } from 'motion/react';
import { MotionAccess, useWorkspaceReducedMotion } from './workspace-motion';

export const BusinessModalTitle = createContext<string | null>(null);

export type BusinessModalLayout = 'compact' | 'scroll-body' | 'pane';

export function BusinessModal({ open, requestClose, className, titleId, children, centered = true, layout = 'compact', zIndex }: {
  open: boolean; requestClose: () => unknown; className: string; titleId: string; children: ReactNode; centered?: boolean; layout?: BusinessModalLayout; zIndex?: number;
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
  // constraint: rc-dialog only labels its own header. The visible heading is in the body.
  if (!present && (reduced || !allowed)) return null;
  return <Modal open={visible} afterClose={() => { if (!present) safeToRemove?.(); }} onCancel={() => { if (visible) requestClose(); }} footer={null} closable={false} keyboard={visible} centered={centered}
    mask={{ closable: true }} width="max-content" {...(zIndex === undefined ? {} : { zIndex })} focusable={{ focusTriggerAfterClose: false }}
    rootClassName={visible ? 'business-modal-root' : 'business-modal-root business-modal-leaving'} transitionName="business-dialog-motion"
    rootStyle={{ opacity: allowed ? undefined : 0, pointerEvents: allowed ? undefined : 'none' }}
    panelRef={panel => { if (panel) { panel.setAttribute('aria-labelledby', accessibleTitleId); panel.inert = !visible; panel.setAttribute('aria-hidden', String(!visible)); } }} className={`business-modal business-modal--${layout}`} destroyOnHidden={false}>
    <BusinessModalTitle.Provider value={accessibleTitleId}><div ref={body} inert={!visible} className={className} data-modal-layout={layout}>{children}</div></BusinessModalTitle.Provider>
  </Modal>;
}
