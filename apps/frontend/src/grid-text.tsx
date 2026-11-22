import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import Tooltip from 'antd/es/tooltip';
import { fullTextWidth } from './grid';

// Measure on demand, rather than observing every text/input in a virtual grid.
function clipped(root: HTMLElement | null) {
  if (!root) return false;
  const input = root.querySelector<HTMLInputElement | HTMLTextAreaElement>('input,textarea');
  if (input) {
    const css = getComputedStyle(input), context = document.createElement('canvas').getContext('2d')!;
    context.font = css.font;
    const available = input.clientWidth - (parseFloat(css.paddingLeft) || 0) - (parseFloat(css.paddingRight) || 0);
    return context.measureText(input.value).width > available + 1;
  }
  const text = root.querySelector<HTMLElement>('.grid-ellipsis') ?? root;
  return text.scrollWidth > text.clientWidth + 1;
}

export function TextPreview({text, children}: {text: string; children: ReactNode}) {
  const root = useRef<HTMLSpanElement>(null), timer = useRef(0), tooltipId = useId();
  const [preview, setPreview] = useState<'unused' | 'open' | 'closed'>('unused');
  useEffect(() => () => window.clearTimeout(timer.current), []);
  function enter() {
    window.clearTimeout(timer.current);
    if (preview === 'open' || !text) return;
    timer.current = window.setTimeout(() => {
      if (clipped(root.current)) setPreview('open');
    }, 300);
  }
  function leave() {
    window.clearTimeout(timer.current);
    if (preview === 'open') timer.current = window.setTimeout(() => setPreview('closed'), 150);
  }
  // The editor stays mounted. A cell pays for its popup and positioning only
  // when the user actually hovers clipped text.
  return <span ref={root} className="grid-text-preview" onMouseEnter={enter} onMouseLeave={leave}
    aria-describedby={preview === 'open' ? tooltipId : undefined}>
    {children}
    {preview !== 'unused' && <Tooltip id={tooltipId} title={<span className="grid-full-text" onMouseDown={event => event.stopPropagation()}
      onClick={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()}>{text}</span>}
      open={preview === 'open' && Boolean(text)} trigger={[]} onOpenChange={next => { if (!next) setPreview('closed'); }} destroyOnHidden
      styles={{root: {maxWidth: 'min(40rem, calc(100vw - 24px))', pointerEvents: 'auto'}, container: {maxHeight: 'min(32rem, calc(100dvh - 32px))', overflowY: 'auto'}}}>
      <span className="grid-text-anchor" aria-hidden="true" />
    </Tooltip>}
  </span>;
}

export function EllipsisText({text, fullText = text}: {text: string; fullText?: string}) {
  return <TextPreview text={fullText}><span className="grid-ellipsis">{text}</span></TextPreview>;
}

// Strict fields include the full result and header/sort affordance in their floor.
// Flexible text columns use explicit bounds instead; this helper never gives them flex.
export function completeColumnWidth(values: readonly unknown[], header: string, scale: number, extra = 0) {
  const minWidth = Math.ceil(Math.max(fullTextWidth(values.map(value => String(value ?? '')), scale).minWidth + extra * scale,
    fullTextWidth([header], scale).minWidth + 20 * scale));
  return {initialWidth: minWidth, minWidth, suppressAutoSize: true};
}
