import { uncertainWrite } from './api';

type Drafts<D> = Record<string, D>;
export type SaveOutcome = 'saved' | 'rejected' | 'uncertain' | 'blocked';
export interface CellSaveOptions<D, R> {
  enabled: boolean;
  canWrite?: boolean;
  read: () => Promise<R>;
  write: (draft: D, signal: AbortSignal) => Promise<void>;
  acknowledge: (current: D, submitted: D) => D | undefined;
  saved: (submitted: D, result: R) => string;
  describe?: (submitted: D) => string;
  validate?: (draft: D) => string;
  stopOnRejection?: boolean;
}
interface Snapshot<D> {
  drafts: Drafts<D>; busy: boolean; uncertain: boolean; verified: boolean; error: string; feedback: string;
}

// Callers own draft identity and reliable domain reads. This module owns the
// ordering: snapshot -> acknowledged write -> retain newer draft -> readback.
// An unknown write stops the queue; dropping a draft never releases that lock.
export class CellSaveQueue<D extends { error: string }, R> {
  private snapshot: Snapshot<D> = { drafts: {}, busy: false, uncertain: false, verified: false, error: '', feedback: '' };
  private listeners = new Set<() => void>();
  private queue: string[] = [];
  private alive = true;
  private request = new AbortController();
  private generation = 0;
  constructor(private options: () => CellSaveOptions<D, R>) {}
  getSnapshot = () => this.snapshot;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private publish(patch: Partial<Snapshot<D>>) {
    if (!this.alive) return;
    this.snapshot = { ...this.snapshot, ...patch };
    for (const listener of this.listeners) listener();
  }
  mount = () => { this.alive = true; if (this.request.signal.aborted) this.request = new AbortController(); };
  dispose = () => { this.alive = false; this.queue = []; this.request.abort(); };
  pause = () => { this.queue = []; };
  update = (change: (drafts: Drafts<D>, writing: boolean) => Drafts<D>) => { this.publish({ drafts: change(this.snapshot.drafts, this.snapshot.busy) }); };
  clearFeedback = () => { this.publish({ error: '', feedback: '' }); };
  private allowed() { return this.alive && this.options().enabled && this.options().canWrite !== false && !this.snapshot.uncertain; }
  save = (key: string, retry = false) => {
    const draft = this.snapshot.drafts[key];
    if (!draft || !this.allowed() || draft.error && !retry) return;
    if (retry && draft.error) this.update(current => ({ ...current, [key]: { ...current[key]!, error: '' } }));
    if (!this.queue.includes(key)) this.queue.push(key);
    void this.drain();
  };
  private async drain() {
    if (this.snapshot.busy || !this.allowed()) return;
    const key = this.queue.shift(); if (!key) return;
    const submitted = this.snapshot.drafts[key];
    if (!submitted || submitted.error) { void this.drain(); return; }
    const adapter = this.options(), invalid = adapter.validate?.(submitted);
    if (invalid) {
      this.update(current => ({ ...current, [key]: { ...current[key]!, error: invalid } }));
      this.publish({ error: invalid });
      if (adapter.stopOnRejection) this.pause(); else void this.drain();
      return;
    }
    const outcome = await this.perform(
      signal => adapter.write(submitted, signal),
      result => this.options().saved(submitted, result),
      () => this.update(current => {
        const next = { ...current }, present = next[key];
        if (present) { const retained = adapter.acknowledge(present, submitted); if (retained) next[key] = retained; else delete next[key]; }
        return next;
      }),
      message => this.update(current => current[key] ? { ...current, [key]: { ...current[key]!, error: message } } : current),
      adapter.describe?.(submitted) ?? '',
    );
    if (outcome === 'rejected' && adapter.stopOnRejection) this.pause();
    void this.drain();
  }
  // Non-cell actions on the same page share the write lock and readback rules.
  // Result classification lets a domain modal keep a rejected choice, but close
  // an acknowledged or unknown action without inviting duplicate submission.
  run = async (write: (signal: AbortSignal) => Promise<void>, saved: (result: R) => string, description = ''): Promise<SaveOutcome> => {
    const outcome = await this.perform(write, saved, undefined, undefined, description); void this.drain(); return outcome;
  };
  private async perform(write: (signal: AbortSignal) => Promise<void>, saved: (result: R) => string,
    acknowledge?: () => void, rejected?: (message: string) => void, description = ''): Promise<SaveOutcome> {
    if (this.snapshot.busy || !this.allowed()) return 'blocked';
    const adapter = this.options();
    this.generation++; this.publish({ busy: true, verified: false, error: '', feedback: '' });
    let written = false;
    try {
      await write(this.request.signal); written = true;
      if (!this.alive) return 'blocked';
      acknowledge?.();
      const result = await adapter.read();
      if (!this.alive) return 'blocked';
      this.publish({ feedback: saved(result) });
      return 'saved';
    } catch (failure) {
      if (!this.alive) return 'blocked';
      const message = failure instanceof Error ? failure.message : '保存失败，请重试。';
      if (written || uncertainWrite(failure)) {
        this.pause();
        this.publish({ uncertain: true, verified: false, error: `${description}${written ? '已保存，重读失败。' : '保存结果待核实。'}${message}请重读核对，勿重复提交。` });
        return 'uncertain';
      }
      rejected?.(message); this.publish({ error: message });
      return 'rejected';
    } finally { this.publish({ busy: false }); }
  }
  reread = async (feedback = '已重读，未保存输入仍保留。') => {
    if (!this.alive || this.snapshot.busy || !this.options().enabled) return false;
    const generation = this.generation;
    try {
      await this.options().read();
      if (!this.alive || generation !== this.generation) return false;
      this.publish({ verified: true, error: '', feedback }); return true;
    } catch (failure) {
      if (generation === this.generation) this.publish({ verified: false, error: failure instanceof Error ? failure.message : '重读失败。' });
      return false;
    }
  };
  confirm = (feedback = '已确认，请核对保留输入后再保存。') => {
    if (this.snapshot.busy || !this.snapshot.verified || !this.options().enabled) return;
    this.publish({ uncertain: false, verified: false, error: '', feedback });
  };
  // An external POST (file generation) may have written even after a lost reply.
  reconcile = async (failurePrefix: string) => {
    const generation = ++this.generation;
    try { await this.options().read(); return this.alive && generation === this.generation; }
    catch (failure) {
      if (generation === this.generation) { this.pause(); this.publish({ uncertain: true, verified: false, error: failurePrefix + (failure instanceof Error ? failure.message : '') }); }
      return false;
    }
  };
}

