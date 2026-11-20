/** Holds only unissued confirmations. Once issued, the caller owns the request and its result. */
export function createI8ActionGate() {
  let waiting: AbortController | null = null;

  return {
    cancel() {
      const current = waiting;
      waiting = null;
      current?.abort();
    },
    async run<T>(prepare: (signal: AbortSignal) => Promise<boolean>, issue: () => T,
      setWaiting: (waiting: boolean) => void): Promise<T | undefined> {
      if (waiting) return undefined;
      const current = new AbortController();
      waiting = current;
      setWaiting(true);
      let ready = false;
      try {
        ready = await prepare(current.signal);
      } finally {
        if (waiting === current) {
          waiting = null;
          setWaiting(false);
        }
      }
      if (ready && !current.signal.aborted) return issue();
      return undefined;
    },
  };
}
