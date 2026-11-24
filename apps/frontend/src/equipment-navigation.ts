export type RentalTarget = { equipmentId: number; projectId: number | null; projectName: string };

export const equipmentFlashDuration = 1400;

export function scrollToEquipmentTarget(target: HTMLElement, block: ScrollLogicalPosition = 'start') {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  target.scrollIntoView({ behavior: reducedMotion ? 'instant' : 'smooth', block, inline: 'nearest' });
}

// Grid heights and rows are published asynchronously, including when a tab is opened for the first time.
export function whenEquipmentTargetReady(root: HTMLElement, locate: () => boolean) {
  let frame = 0;
  function schedule() {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      if (locate()) observer.disconnect();
    });
  }
  const observer = new MutationObserver(schedule);
  observer.observe(root, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-layout-state'] });
  schedule();
  return () => {
    observer.disconnect();
    cancelAnimationFrame(frame);
  };
}
