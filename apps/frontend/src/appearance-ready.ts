import type { Identity } from './api';

let applied: string | undefined;

export async function loadTextFonts(text: string, weights: readonly number[] = [400, 500, 600]) {
  const chars = [...new Set(text)].join('');
  if (!chars) return;
  try {
    await Promise.all(weights.map(weight => document.fonts.load(`${weight} 14px MiSans`, chars)));
  } catch {
    throw new Error('字体加载失败，请重试。');
  }
}

export async function prepareAppearance(me: Identity | null, signal: AbortSignal) {
  const key = `${me?.account ?? ''}:${me?.theme ?? ''}`;
  const current = document.querySelector<HTMLLinkElement>('#user-theme');
  // The server already renders this account's theme on direct entry. Reload only after a preference/account change.
  if (!current?.sheet || (applied !== undefined && applied !== key)) {
    const replacement = document.createElement('link');
    replacement.rel = 'stylesheet'; replacement.media = 'not all';
    replacement.href = `/static/theme.css?surface=react&identity=${encodeURIComponent(me?.account ?? '')}&theme=${encodeURIComponent(me?.theme ?? '')}`;
    await new Promise<void>((resolve, reject) => {
      const clean = () => { signal.removeEventListener('abort', abort); replacement.onload = null; replacement.onerror = null; };
      const abort = () => { clean(); replacement.remove(); reject(new DOMException('Aborted', 'AbortError')); };
      replacement.onload = () => { clean(); resolve(); };
      replacement.onerror = () => { clean(); replacement.remove(); reject(new Error('主题加载失败，请重试。')); };
      signal.addEventListener('abort', abort, { once: true });
      document.head.append(replacement);
    });
    if (signal.aborted) { replacement.remove(); return; }
    current?.remove(); replacement.id = 'user-theme'; replacement.media = 'all';
  }
  if (signal.aborted) return;
  document.documentElement.style.setProperty('--fscale', me?.ui_scale_css ?? '1');
  applied = key;
}

// Use the weights actually present in the mounted view, rather than fetching every shard in all weights.
export async function loadElementFonts(root: HTMLElement) {
  const groups = new Map<number, string>();
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode, parent = node.parentElement;
    if (!parent || !node.textContent?.trim() || parent.closest('style,script,[hidden]')) continue;
    const weight = Number(getComputedStyle(parent).fontWeight) || 400;
    groups.set(weight, (groups.get(weight) ?? '') + node.textContent);
  }
  for (const input of root.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input,textarea')) {
    const weight = Number(getComputedStyle(input).fontWeight) || 400;
    groups.set(weight, (groups.get(weight) ?? '') + input.value + input.placeholder);
  }
  await Promise.all([...groups].map(([weight, text]) => loadTextFonts(text, [weight])));
}
