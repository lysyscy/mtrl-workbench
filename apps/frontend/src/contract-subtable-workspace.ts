import { ApiError } from './api';
import { draftProblem, emptySubtableDraft } from './contract-subtables-api';
import type { SubtableDraft, SubtableKind } from './contract-subtables-api';
import { clearSubtableSnapshot, newSubtableRequestId, readSubtableSnapshot, snapshotIsEmpty, subtableStorageAvailable, writeSubtableSnapshot } from './contract-subtable-recovery';
import type { SubtableOperation, SubtableSnapshot } from './contract-subtable-recovery';

const kinds: readonly SubtableKind[] = ['supplier', 'trade', 'payment'];
export const subtableDraftDirty = (draft: SubtableDraft) => draft.amount !== '' || draft.date !== draft.initialDate;
const messageOf = (failure: unknown) => failure instanceof Error ? failure.message : '请联系维护人员。';
const rejected = (failure: unknown) => failure instanceof ApiError && failure.code !== 'invalid_response'
  && (failure.status === 200 || failure.status >= 400 && failure.status < 500);
type Unresolved = 'checking' | 'unknown' | 'not_found';
type Deletion = { kind: SubtableKind; id: number; date: string; amount: string };
type Focus = { kind: SubtableKind; id: number };
export interface SubtableView {
  drafts: Readonly<Record<SubtableKind, Readonly<SubtableDraft>>>;
  busy: boolean; uncertain: boolean; dirty: boolean; error: string; feedback: string; storageWarning: string;
  deleting: Deletion | null; focus: Focus | null; retry: readonly SubtableKind[];
}
interface Entry {
  historyDate: string; drafts: Record<SubtableKind, SubtableDraft>;
  pending: Partial<Record<SubtableKind, SubtableOperation>>;
  unresolved: Partial<Record<SubtableKind, Unresolved>>;
  recoveryErrors: Partial<Record<SubtableKind, string>>;
  busy: boolean; referenceUnknown: boolean; restored: boolean;
  referenceError: string;
  error: string; feedback: string; storageWarning: string;
  deleting: Deletion | null; focus: Focus | null;
}
interface Options {
  allowed: () => boolean;
  write: (contractId: number, operation: SubtableOperation) => Promise<number | null>;
  lookup: (requestId: string) => Promise<{ status: 'not_found' } | { status: 'completed'; result: Record<string, unknown> }>;
  refresh: (contractId: number) => Promise<void>;
  reference: (contractId: number, noticeId: number) => Promise<void>;
  announce: (message: string) => void;
}
function emptyDraft(kind: SubtableKind, historyDate: string) {
  const draft = emptySubtableDraft();
  return kind === 'supplier' && historyDate ? { ...draft, date: historyDate, initialDate: historyDate } : draft;
}
const labels = (entry: Entry, kind: SubtableKind) => kind === 'payment' ? '手工付款' : kind === 'trade' ? '贸易公司发票' : entry.historyDate ? '历史未结金额' : '供应商发票';

/** Account-owned submission identity. Views never write pending operations or order recovery effects. */
export class ContractSubtableWorkspace {
  private entries = new Map<number, Entry>();
  private snapshot: Readonly<Record<number, SubtableView>> = {};
  private listeners = new Set<() => void>();
  private activations = new Map<number, Promise<void>>();
  private alive = true;
  private epoch = 0;
  constructor(private accountId: number | undefined, private options: Options) {}
  getSnapshot = () => this.snapshot;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  mount = () => { this.alive = true; };
  dispose = () => { this.alive = false; this.epoch++; this.activations.clear(); };
  view = (id: number) => this.snapshot[id];
  get summary() {
    const rows = Object.values(this.snapshot);
    return { busy: rows.some(row => row.busy), uncertain: rows.some(row => row.uncertain), dirty: rows.some(row => row.dirty) };
  }
  private entry(id: number, historyDate: string) {
    let entry = this.entries.get(id);
    if (!entry) {
      entry = { historyDate, drafts: { supplier: emptyDraft('supplier', historyDate), trade: emptyDraft('trade', historyDate), payment: emptyDraft('payment', historyDate) },
        pending: {}, unresolved: {}, recoveryErrors: {}, busy: false, referenceUnknown: false, referenceError: '', restored: false, error: '', feedback: '', storageWarning: '', deleting: null, focus: null };
      this.entries.set(id, entry);
    }
    entry.historyDate = historyDate;
    return entry;
  }
  private uncertain(entry: Entry) { return entry.referenceUnknown || Object.values(entry.unresolved).some(value => value !== 'not_found'); }
  private persist(id: number, entry: Entry) {
    if (!entry.restored || !this.accountId) return;
    const drafts: SubtableSnapshot['drafts'] = {};
    for (const kind of kinds) if (subtableDraftDirty(entry.drafts[kind])) drafts[kind] = entry.drafts[kind];
    const snapshot: SubtableSnapshot = { version: 1, accountId: this.accountId, contractId: id, operations: { ...entry.pending }, drafts };
    if (snapshotIsEmpty(snapshot)) clearSubtableSnapshot(this.accountId, id);
    else if (!writeSubtableSnapshot(snapshot)) entry.storageWarning = '本次保护有限：浏览器未能暂存子表输入，刷新页面可能丢失。';
  }
  private publish(id: number, entry: Entry) {
    if (!this.alive) return;
    this.persist(id, entry);
    this.snapshot = { ...this.snapshot, [id]: { drafts: { ...entry.drafts }, busy: entry.busy,
      uncertain: this.uncertain(entry), dirty: kinds.some(kind => subtableDraftDirty(entry.drafts[kind])),
      error: [...new Set([entry.referenceError, ...Object.values(entry.recoveryErrors), entry.error].filter(Boolean))].join(' '),
      feedback: Object.values(entry.unresolved).includes('checking') ? '正在核对提交的保存结果…' : this.uncertain(entry) ? '' : entry.feedback,
      storageWarning: entry.storageWarning, deleting: entry.deleting, focus: entry.focus,
      retry: kinds.filter(kind => entry.unresolved[kind] === 'not_found') } };
    for (const listener of this.listeners) listener();
  }
  private valid(epoch: number) { return this.alive && epoch === this.epoch; }
  activate = (id: number, historyDate: string): Promise<void> => {
    if (!this.alive || !this.accountId || !this.options.allowed()) return Promise.resolve();
    const running = this.activations.get(id); if (running) return running;
    const entry = this.entry(id, historyDate), epoch = this.epoch;
    if (entry.busy) return Promise.resolve();
    if (!entry.restored) {
      if (!subtableStorageAvailable()) entry.storageWarning = '本次保护有限：浏览器禁止本地暂存，刷新页面会丢失未保存的输入。';
      const snapshot = readSubtableSnapshot(this.accountId, id);
      for (const kind of kinds) {
        const draft = snapshot?.drafts[kind];
        if (draft && !subtableDraftDirty(entry.drafts[kind])) entry.drafts[kind] = draft;
        const operation = snapshot?.operations[kind];
        if (operation) entry.pending[kind] = operation;
      }
      entry.restored = true;
    }
    const pending = kinds.flatMap(kind => entry.pending[kind] ? [entry.pending[kind]!] : []);
    for (const operation of pending) entry.unresolved[operation.kind] = 'checking';
    if (pending.length) entry.feedback = '正在核对上次提交的保存结果…';
    this.publish(id, entry);
    const run = Promise.resolve().then(async () => {
      for (const operation of pending) { if (!this.valid(epoch)) return; await this.confirm(id, entry, operation, epoch); }
    }).finally(() => { if (this.activations.get(id) === run) this.activations.delete(id); });
    this.activations.set(id, run);
    return run;
  };
  edit = (id: number, kind: SubtableKind, key: 'date' | 'amount', value: string) => {
    const entry = this.entries.get(id);
    if (!entry || entry.busy || this.uncertain(entry) || !this.options.allowed()) return;
    entry.drafts[kind] = { ...entry.drafts[kind], [key]: value }; this.publish(id, entry);
  };
  discard = (id: number, kind?: SubtableKind) => {
    const entry = this.entries.get(id); if (!entry || entry.busy) return;
    for (const key of kind ? [kind] : kinds) entry.drafts[key] = emptyDraft(key, entry.historyDate);
    if (!kind || entry.deleting?.kind === kind) entry.deleting = null;
    if (!kind) entry.focus = null;
    // Persist before the view unmounts. Pending identities deliberately survive.
    this.publish(id, entry);
  };
  selectDeletion = (id: number, target: Deletion | null) => {
    const entry = this.entries.get(id);
    if (!entry || entry.busy || this.uncertain(entry) || !this.options.allowed()) return;
    entry.deleting = target; this.publish(id, entry);
  };
  private acknowledge(entry: Entry, operation: SubtableOperation, focus: number | null) {
    delete entry.pending[operation.kind]; delete entry.unresolved[operation.kind];
    delete entry.recoveryErrors[operation.kind];
    const draft = entry.drafts[operation.kind];
    if (operation.action === 'add' && draft.date.trim() === operation.date && draft.amount.trim() === operation.amount)
      entry.drafts[operation.kind] = emptyDraft(operation.kind, entry.historyDate);
    if (focus !== null) entry.focus = { kind: operation.kind, id: focus };
    entry.error = ''; entry.feedback = '';
  }
  private async confirm(id: number, entry: Entry, operation: SubtableOperation, epoch: number) {
    const current = () => this.valid(epoch) && entry.pending[operation.kind]?.requestId === operation.requestId;
    try {
      const lookup = await this.options.lookup(operation.requestId);
      if (!current()) return;
      if (lookup.status === 'completed') {
        const focus = lookup.result.id;
        this.acknowledge(entry, operation, typeof focus === 'number' && Number.isSafeInteger(focus) && focus > 0 ? focus : null);
        this.publish(id, entry);
        try { await this.options.refresh(id); }
        catch { if (this.valid(epoch)) { entry.error = `${labels(entry, operation.kind)}已保存，明细重读失败，可刷新页面查看。`; this.publish(id, entry); } }
        if (this.valid(epoch)) this.options.announce(operation.action === 'del' ? '已删除。' : `${labels(entry, operation.kind)}已保存。`);
      } else {
        delete entry.recoveryErrors[operation.kind];
        entry.unresolved[operation.kind] = 'not_found'; entry.error = '';
        entry.feedback = `暂未查到上次${labels(entry, operation.kind)}操作的保存结果，可重试上次操作；将沿用原提交，不会重复记账。`;
        this.publish(id, entry);
      }
    } catch (failure) {
      if (!current()) return;
      entry.unresolved[operation.kind] = 'unknown';
      entry.recoveryErrors[operation.kind] = `未能确认本次${labels(entry, operation.kind)}是否已保存：${messageOf(failure)}请刷新页面后重试核对；同一次提交不会重复记账。`;
      this.publish(id, entry);
    }
  }
  submit = async (id: number, kind: SubtableKind, deleting = false) => {
    const entry = this.entries.get(id);
    if (!this.alive || !entry?.restored || entry.busy || this.uncertain(entry) || !this.options.allowed()) return;
    const previous = entry.pending[kind], retry = previous && entry.unresolved[kind] === 'not_found' ? previous : undefined;
    if (!retry && deleting && entry.deleting?.kind !== kind) return;
    const draft = entry.drafts[kind], problem = retry || deleting ? '' : draftProblem(draft);
    if (problem) { entry.error = `${labels(entry, kind)}：${problem}`; this.publish(id, entry); return; }
    const operation: SubtableOperation = retry ?? { requestId: newSubtableRequestId(), kind, action: deleting ? 'del' : 'add',
      date: deleting ? '' : draft.date.trim(), amount: deleting ? '' : draft.amount.trim(), rowId: deleting ? entry.deleting!.id : null, at: Date.now() };
    const epoch = this.epoch;
    entry.busy = true; entry.error = ''; entry.feedback = ''; entry.pending[kind] = operation; entry.unresolved[kind] = 'checking';
    this.publish(id, entry); // Synchronous persistence always precedes the POST.
    try {
      const focus = await this.options.write(id, operation);
      if (!this.valid(epoch)) return;
      entry.deleting = null; entry.focus = null; this.acknowledge(entry, operation, focus); this.publish(id, entry);
      try {
        await this.options.refresh(id);
        if (this.valid(epoch)) this.options.announce(operation.action === 'del' ? '已删除。' : `${labels(entry, kind)}已新增。`);
      } catch (failure) { if (this.valid(epoch)) { entry.error = `已保存，明细重读失败，可刷新页面查看。${messageOf(failure)}`; this.publish(id, entry); } }
    } catch (failure) {
      if (!this.valid(epoch)) return;
      if (rejected(failure)) {
        delete entry.pending[kind]; delete entry.unresolved[kind]; delete entry.recoveryErrors[kind]; entry.error = `未保存。${messageOf(failure)}`; this.publish(id, entry);
      } else {
        entry.feedback = `未取得${labels(entry, kind)}保存确认，正在核对本次结果…`; this.publish(id, entry);
        await this.confirm(id, entry, operation, epoch);
      }
    } finally { if (this.valid(epoch)) { entry.busy = false; this.publish(id, entry); } }
  };
  reference = async (id: number, noticeId: number): Promise<'saved' | 'written' | 'unknown' | 'rejected' | 'blocked'> => {
    const entry = this.entries.get(id);
    if (!this.alive || !entry || entry.busy || this.uncertain(entry) || !this.options.allowed()) return 'blocked';
    const epoch = this.epoch;
    entry.busy = true; entry.error = ''; entry.feedback = ''; this.publish(id, entry);
    let written = false;
    try {
      await this.options.reference(id, noticeId); written = true;
      if (!this.valid(epoch)) return 'blocked';
      await this.options.refresh(id);
      if (!this.valid(epoch)) return 'blocked';
      this.options.announce('已引用付款记录。'); return 'saved';
    } catch (failure) {
      if (!this.valid(epoch)) return 'blocked';
      const known = rejected(failure); entry.referenceUnknown = !written && !known;
      entry.error = `${written ? '已关联，明细重读失败，请刷新页面核对，勿重复引用。' : known ? '未关联。' : '关联结果待确认，请刷新页面核对，勿重复引用。'}${messageOf(failure)}`;
      entry.referenceError = entry.referenceUnknown ? entry.error : '';
      return written ? 'written' : known ? 'rejected' : 'unknown';
    } finally { if (this.valid(epoch)) { entry.busy = false; this.publish(id, entry); } }
  };
}
