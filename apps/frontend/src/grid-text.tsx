import { useRef, useState } from 'react';
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
  const root = useRef<HTMLSpanElement>(null), [open, setOpen] = useState(false);
  return <Tooltip title={<span className="grid-full-text">{text}</span>} open={open}
    onOpenChange={next => setOpen(next && Boolean(text) && clipped(root.current))}
    mouseEnterDelay={0.3} mouseLeaveDelay={0.15} destroyOnHidden
    styles={{root: {maxWidth: 'min(40rem, calc(100vw - 24px))', pointerEvents: 'auto'}, container: {maxHeight: 'min(32rem, calc(100dvh - 32px))', overflowY: 'auto'}}}>
    <span ref={root} className="grid-text-preview">{children}</span>
  </Tooltip>;
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
