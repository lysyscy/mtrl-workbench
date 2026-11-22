import { useEffect, useState } from 'react';
import type { ChangeEvent, CompositionEvent } from 'react';

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
