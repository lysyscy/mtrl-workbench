/**
 * 台账行内字段的串行写入队列。
 *
 * 修的是这样一个真实缺陷：同一行的"存档号"blur 保存还没落地时用户点"推进存档"，
 * 旧实现在保存进行中直接 return false，把这次点击整条丢掉（既不排队也不重试）。
 * 这里改成排队：每次调用都拿到属于自己那一笔的完成结果；同一格后到的值顶掉尚未开始的
 * 旧值（旧调用按"未写入"结算），因此既不丢点击，也不会把被顶掉的输入当成已保存。
 */
export interface InlineFieldTask {
  key: string;
  run: () => Promise<boolean>;
  settle: (ok: boolean) => void;
}

export interface InlineFieldQueue {
  /** 入队；队列空闲时调用 start 启动消费。返回本笔是否真的写入并已刷新。 */
  push: (key: string, run: () => Promise<boolean>, start: () => void) => Promise<boolean>;
  /** 取出下一笔（消费方负责执行 run 并 settle）；空队列返回 null。 */
  take: () => InlineFieldTask | null;
  /** 队列里是否还有待写条目。 */
  readonly size: number;
  /** 是否有一轮消费正在进行。 */
  readonly running: boolean;
  /** 剩余全部按未写入结算并清空。 */
  reject: () => void;
  /** 一轮消费结束，允许下次 push 重新启动。 */
  release: () => void;
}

export function createInlineFieldQueue(): InlineFieldQueue {
  const pending = new Map<string, InlineFieldTask>();
  let running = false;
  return {
    get size() { return pending.size; },
    get running() { return running; },
    push(key, run, start) {
      return new Promise<boolean>(settle => {
        pending.get(key)?.settle(false);
        pending.set(key, { key, run, settle });
        if (running) return;
        running = true;
        start();
      });
    },
    take() {
      const entry = pending.values().next().value as InlineFieldTask | undefined;
      if (!entry) return null;
      pending.delete(entry.key);
      return entry;
    },
    reject() {
      for (const entry of pending.values()) entry.settle(false);
      pending.clear();
    },
    release() { running = false; },
  };
}
