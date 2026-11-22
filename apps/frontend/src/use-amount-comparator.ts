import { useCallback, useMemo, useRef } from 'react';
import { cents } from './api';

/** Keep the grid comparator stable while limiting its exact cent keys to the current rows. */
export function useAmountComparator(rows: readonly unknown[]) {
  const values = useMemo(() => new Map<string, bigint>(), [rows]);
  const current = useRef(values);
  current.current = values;
  return useCallback((a: string, b: string) => {
    if (a === b) return 0;
    if (!a || !b) return a ? 1 : b ? -1 : 0;
    const left = sortValue(current.current, a), right = sortValue(current.current, b);
    return left < right ? -1 : left > right ? 1 : 0;
  }, []);
}

function sortValue(values: Map<string, bigint>, text: string) {
  let value = values.get(text);
  if (value === undefined) {
    value = cents(text);
    values.set(text, value);
  }
  return value;
}
