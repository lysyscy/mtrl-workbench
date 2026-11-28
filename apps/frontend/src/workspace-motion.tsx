import { createContext, isValidElement, useContext, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import type { ReactNode } from 'react';

export const ReducedMotion = createContext(false);
export const MotionAccess = createContext(true);
export const useWorkspaceReducedMotion = () => useContext(ReducedMotion);
export const workspaceSpring = { type: 'spring', stiffness: 420, damping: 38, mass: 1 } as const;
export function WorkspaceMarker({ className, layoutId }: { className: string; layoutId: string }) {
  const reduced = useWorkspaceReducedMotion();
  return reduced ? <span aria-hidden="true" className={className} />
    : <motion.span aria-hidden="true" className={className} layoutId={layoutId} transition={workspaceSpring} />;
}

export function DialogPresence({ children }: { children: ReactNode }) {
  const shown = isValidElement(children);
  const type = shown ? children.type : null, key = shown ? children.key : null;
  const [instance, setInstance] = useState({ shown, type, key, id: 0 });
  if (shown !== instance.shown || type !== instance.type || key !== instance.key) {
    setInstance({ shown, type, key, id: instance.id + (shown ? 1 : 0) });
  }
  return <AnimatePresence key={instance.id}>{children}</AnimatePresence>;
}

export function WorkspacePanel({ active, id, labelledBy, children }: { active: boolean; id: string; labelledBy: string; children: ReactNode }) {
  const reduced = useWorkspaceReducedMotion();
  return <motion.div role="tabpanel" id={id} aria-labelledby={labelledBy} aria-hidden={!active} inert={!active}
    initial={false} animate={active ? { opacity: 1, x: 0, visibility: 'visible' } : { opacity: 0, x: reduced ? 0 : 18, transitionEnd: { visibility: 'hidden' } }}
    transition={reduced ? { duration: 0 } : { ...workspaceSpring, opacity: { duration: active ? .18 : .1 } }}
    style={active ? { position: 'relative', zIndex: 1 } : { position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 0 }}>{children}</motion.div>;
}
