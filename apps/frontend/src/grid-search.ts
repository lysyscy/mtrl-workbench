import { useEffect, useState } from 'react';
import type { ChangeEvent, CompositionEvent } from 'react';

// The page owns the immutable business scope and the strings it makes searchable.
// A longer normalized substring can only remove matches from the previous result.
export function searchWithinRows<T>(scope: T[], matches: (row: T, needle: string) => boolean) {
  let previous = '';
  let result = scope;
  return (needle: string) => {
    if (needle === previous) return result;
    const candidates = needle.includes(previous) ? result : scope;
    const next = needle ? candidates.filter(row => matches(row, needle)) : scope;
    previous = needle;
    result = next.length === candidates.length ? candidates : next;
    return result;
  };
}

// Keep local typing responsive while publishing one settled result to the grid.
export function useGridSearch(active: boolean) {
  const [text, setText] = useState('');
  const [applied, setApplied] = useState('');
  const [composing, setComposing] = useState(false);
  const pending = text !== applied;
  useEffect(() => {
    if (!active || composing || !pending) return;
    const timer = window.setTimeout(() => setApplied(text), 100);
    return () => window.clearTimeout(timer);
  }, [active, composing, pending, text]);

  function reset(value: string) {
    setText(value);
    setApplied(value);
  }
  const input = {
    value: text,
    onChange: (event: ChangeEvent<HTMLInputElement>) => setText(event.target.value),
    onCompositionStart: () => setComposing(true),
    onCompositionEnd: (event: CompositionEvent<HTMLInputElement>) => {
      setComposing(false);
      setText(event.currentTarget.value);
    },
  };
  return { applied, pending, input, reset };
}
