import test from 'node:test';
import assert from 'node:assert/strict';
import { createInlineFieldQueue } from '../../src/inline-field-queue.ts';

// 这一层守的是"一次点击推进存档"的真实缺陷：旧的 saveField 在保存进行中直接返回
// false，第二次点击拿不到完成信号。队列必须排队，并各自结算。

const flush = () => new Promise(resolve => setTimeout(resolve, 0));

function consumer(queue) {
  const drain = async () => {
    while (true) {
      const task = queue.take();
      if (!task) break;
      const ok = await task.run();
      task.settle(ok);
      if (!ok) break;
    }
    queue.release();
  };
  return () => { void drain(); };
}

test('saving a value then clicking advance queues instead of dropping the click', async () => {
  const queue = createInlineFieldQueue();
  const writes = [];
  let releaseFirst;
  const start = consumer(queue);
  const first = queue.push('1:arch_no', async () => {
    writes.push('arch_no');
    await new Promise(resolve => { releaseFirst = resolve; });
    return true;
  }, start);
  await flush();
  assert.equal(queue.size, 0, '第一笔已被取走执行');
  assert.equal(queue.running, true);

  // 保存仍在进行中点"推进存档"：必须排队并最终拿到 true，而不是立刻 false。
  const second = queue.push('1:arch', async () => { writes.push('arch'); return true; }, start);
  await flush();
  assert.deepEqual(writes, ['arch_no'], '串行：第二笔等第一笔结束');

  releaseFirst();
  assert.equal(await first, true);
  assert.equal(await second, true);
  assert.deepEqual(writes, ['arch_no', 'arch'], '两笔都真正写入，顺序稳定');
  assert.equal(queue.running, false);
});

test('a superseded value in the same cell settles false so it is never reported saved', async () => {
  const queue = createInlineFieldQueue();
  const seen = [];
  // 消费方尚未启动：两笔都还排在队列里，后到的值应当顶掉前一笔。
  const stale = queue.push('2:remark', async () => { seen.push('old'); return true; }, () => {});
  const latest = queue.push('2:remark', async () => { seen.push('new'); return true; }, () => {});
  assert.equal(queue.size, 1);
  assert.equal(await stale, false, '被顶掉的那笔按未写入结算');
  const task = queue.take();
  assert.equal(await task.run(), true);
  task.settle(true);
  assert.equal(await latest, true);
  assert.deepEqual(seen, ['new']);
});

test('reject settles every queued entry as not written', async () => {
  const queue = createInlineFieldQueue();
  const entries = [queue.push('3:arch_no', async () => true, () => {}), queue.push('3:ret_date', async () => true, () => {})];
  queue.reject();
  assert.deepEqual(await Promise.all(entries), [false, false]);
  assert.equal(queue.size, 0);
});

test('release allows the next push to start a fresh drain', async () => {
  const queue = createInlineFieldQueue();
  let starts = 0;
  const start = consumer(queue);
  const staged = () => { starts += 1; start(); };
  assert.equal(await queue.push('4:arch', async () => true, staged), true);
  assert.equal(await queue.push('4:arch_no', async () => true, staged), true);
  assert.equal(starts, 2);
});
