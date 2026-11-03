import type { SubtableDraft, SubtableKind } from './contract-subtables-api';
import { randomUUID } from './random-id';

/**
 * 合同子表（供应商发票 / 贸易发票 / 付款）的本地恢复数据。
 *
 * 这里只保存「一次真实写操作的稳定 ID」和「未保存草稿」：
 * - requestId 在写入前生成，网络未知重试与 F5 恢复都复用它，绝不新 ID 重投；
 * - 快照只用于还原界面与确认，模块自身不发请求、不重放。
 *
 * 存储按「账号 + 合同」隔离，换号不会读到别人的记录。
 */

/** 一次真实子表写操作的进行中记录。只用于"确认是否已完成"，永不用于自动重投。 */
export interface SubtableOperation {
  /** 稳定 UUID：网络未知重试 / F5 恢复都复用同一个 */
  requestId: string;
  kind: SubtableKind;
  action: 'add' | 'del';
  /** 新增时的日期，删除时为空串 */
  date: string;
  /** 新增时的金额，删除时为空串 */
  amount: string;
  /** 删除时的行 id，新增时为 null */
  rowId: number | null;
  /** 记入时间戳 ms，仅用于展示/清理 */
  at: number;
}

/** 只读快照：恢复时用于还原界面，绝不自动重放 */
export interface SubtableSnapshot {
  version: 1;
  accountId: number;
  contractId: number;
  /** 每侧最多一条进行中操作 */
  operations: Partial<Record<SubtableKind, SubtableOperation>>;
  /** 未保存草稿 */
  drafts: Partial<Record<SubtableKind, SubtableDraft>>;
}

const KINDS: readonly SubtableKind[] = ['supplier', 'trade', 'payment'];
const PROBE_KEY = 'm11-subtable:probe';

function snapshotKey(accountId: number, contractId: number): string {
  return `m11-subtable:${accountId}:${contractId}`;
}

// sessionStorage 在调用时读取：不缓存引用，也不在模块顶层探测（导入即副作用）。
function storage(): Storage | null {
  try {
    const value = globalThis.sessionStorage;
    if (!value || typeof value.getItem !== 'function' || typeof value.setItem !== 'function' || typeof value.removeItem !== 'function') return null;
    return value;
  } catch {
    return null;
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

const isId = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;

function readOperation(kind: SubtableKind, value: unknown): SubtableOperation | null {
  if (!isObject(value)) return null;
  const { requestId, action, date, amount, rowId, at } = value;
  if (typeof requestId !== 'string' || requestId === '') return null;
  if (value.kind !== kind) return null;
  if (action !== 'add' && action !== 'del') return null;
  if (typeof date !== 'string' || typeof amount !== 'string') return null;
  if (!(rowId === null || isId(rowId))) return null;
  if (typeof at !== 'number' || !Number.isFinite(at)) return null;
  return { requestId, kind, action, date, amount, rowId, at };
}

function readDraft(value: unknown): SubtableDraft | null {
  if (!isObject(value)) return null;
  const { date, amount, initialDate } = value;
  if (typeof date !== 'string' || typeof amount !== 'string' || typeof initialDate !== 'string') return null;
  return { date, amount, initialDate };
}

function readOperations(value: unknown): Partial<Record<SubtableKind, SubtableOperation>> {
  const operations: Partial<Record<SubtableKind, SubtableOperation>> = {};
  if (!isObject(value)) return operations;
  for (const kind of KINDS) {
    const operation = readOperation(kind, value[kind]);
    if (operation) operations[kind] = operation;
  }
  return operations;
}

function readDrafts(value: unknown): Partial<Record<SubtableKind, SubtableDraft>> {
  const drafts: Partial<Record<SubtableKind, SubtableDraft>> = {};
  if (!isObject(value)) return drafts;
  for (const kind of KINDS) {
    const draft = readDraft(value[kind]);
    if (draft) drafts[kind] = draft;
  }
  return drafts;
}

/** sessionStorage 是否可用（探测写读删一次，异常一律 false，不抛） */
export function subtableStorageAvailable(): boolean {
  const store = storage();
  if (!store) return false;
  try {
    store.setItem(PROBE_KEY, '1');
    const readBack = store.getItem(PROBE_KEY);
    store.removeItem(PROBE_KEY);
    return readBack === '1';
  } catch {
    return false;
  }
}

/** 读快照；不可用/无记录/版本不符/账号或合同不符 → null。绝不返回别的账号的数据。 */
export function readSubtableSnapshot(accountId: number, contractId: number): SubtableSnapshot | null {
  if (!isId(accountId) || !isId(contractId)) return null;
  const store = storage();
  if (!store) return null;
  let text: string | null;
  try {
    text = store.getItem(snapshotKey(accountId, contractId));
  } catch {
    return null;
  }
  if (!text) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    return null;
  }
  // 未识别的内容一律不采用，但也不删除：写入方可能属于更新的版本。
  if (!isObject(parsed)) return null;
  if (parsed.version !== 1) return null;
  if (parsed.accountId !== accountId || parsed.contractId !== contractId) return null;
  if (parsed.operations !== undefined && !isObject(parsed.operations)) return null;
  if (parsed.drafts !== undefined && !isObject(parsed.drafts)) return null;
  return {
    version: 1,
    accountId,
    contractId,
    operations: readOperations(parsed.operations),
    drafts: readDrafts(parsed.drafts),
  };
}

/** 写快照；成功 true，storage 不可用或写失败 false（调用方据此提示"本次保护有限"）。不抛。 */
export function writeSubtableSnapshot(snapshot: SubtableSnapshot): boolean {
  if (!isId(snapshot.accountId) || !isId(snapshot.contractId)) return false;
  const store = storage();
  if (!store) return false;
  // 只落已知字段，避免把调用方意外挂上的内容写进 storage。
  const operations: Record<string, SubtableOperation> = {};
  for (const kind of KINDS) {
    const operation = readOperation(kind, snapshot.operations[kind]);
    if (operation) operations[kind] = operation;
  }
  const drafts: Record<string, SubtableDraft> = {};
  for (const kind of KINDS) {
    const draft = readDraft(snapshot.drafts[kind]);
    if (draft) drafts[kind] = draft;
  }
  try {
    store.setItem(snapshotKey(snapshot.accountId, snapshot.contractId), JSON.stringify({
      version: 1,
      accountId: snapshot.accountId,
      contractId: snapshot.contractId,
      operations,
      drafts,
    }));
    return true;
  } catch {
    return false;
  }
}

/** 清除该账号+合同的快照（合同关闭、无草稿无进行中操作时调用） */
export function clearSubtableSnapshot(accountId: number, contractId: number): void {
  if (!isId(accountId) || !isId(contractId)) return;
  const store = storage();
  if (!store) return;
  try {
    store.removeItem(snapshotKey(accountId, contractId));
  } catch {
    // 清除失败不影响调用方：快照下次写入会被覆盖。
  }
}

/** 生成新的稳定操作 ID */
export function newSubtableRequestId(): string {
  return randomUUID();
}

export function emptySubtableSnapshot(accountId: number, contractId: number): SubtableSnapshot {
  return { version: 1, accountId, contractId, operations: {}, drafts: {} };
}

const draftDirty = (draft: SubtableDraft) => draft.amount !== '' || draft.date !== draft.initialDate;

/** 判断快照是否为空（无 operations 且无 dirty drafts），空则调用方可以整条清掉 */
export function snapshotIsEmpty(snapshot: SubtableSnapshot): boolean {
  if (KINDS.some(kind => snapshot.operations[kind] !== undefined)) return false;
  return !KINDS.some(kind => {
    const draft = snapshot.drafts[kind];
    return draft !== undefined && draftDirty(draft);
  });
}
