import test from 'node:test';
import assert from 'node:assert/strict';
import { CellSaveQueue } from '../../src/cell-save.ts';
import { ApiError } from '../../src/api.ts';

test('cell_save_snapshots_and_unknown_result_lock', async () => {
  const deferred = () => { let resolve, reject; const promise = new Promise((yes,no) => {resolve=yes;reject=no}); return {promise,resolve,reject}; };
  const untilIdle = queue => new Promise(resolve => {
    if (!queue.getSnapshot().busy) return resolve();
    const release = queue.subscribe(() => {if (!queue.getSnapshot().busy) {release();resolve()}});
  });
  const draft = (value,revision) => ({value,revision,error:''});
  const options = {
    enabled:true, write:async()=>{}, read:async()=>({}),
    acknowledge:(current,sent)=>current.revision === sent.revision ? undefined : {...current,original:sent.value},
    saved:()=> '已保存', describe:sent=>'范围 '+sent.value+'：', stopOnRejection:true,
  };
  const queue = new CellSaveQueue(() => options);
  const write = deferred(); const submitted=[];
  options.write = async value => {submitted.push(value);await write.promise};
  queue.update(() => ({a:draft('1.25',1)})); queue.save('a');
  queue.update(current => ({...current,a:draft('2.50',2)}));
  write.resolve(); await untilIdle(queue);
  assert.equal(submitted.length,1);
  assert.equal(queue.getSnapshot().drafts.a.value,'2.50');
  assert.equal(queue.getSnapshot().drafts.a.original,'1.25');

  // Keep the acknowledged value visible while the server readback is still pending.
  const pendingRead = deferred();
  options.write = async () => {}; options.read = () => pendingRead.promise;
  queue.save('a'); await Promise.resolve();
  assert.equal(queue.getSnapshot().drafts.a?.value,'2.50','Do not flash the old cached value before readback');
  pendingRead.resolve({}); await untilIdle(queue);
  assert.equal(queue.getSnapshot().drafts.a,undefined);
  options.read = async () => ({});
  queue.update(() => ({a:draft('2.50',2)}));

  // A clear rejection retains the draft and does not silently retry it.
  options.write = async () => {throw new ApiError('明确拒绝',400)};
  queue.save('a'); await untilIdle(queue);
  assert.equal(queue.getSnapshot().uncertain,false);
  assert.equal(queue.getSnapshot().drafts.a.value,'2.50');
  assert.equal(queue.getSnapshot().drafts.a.error,'明确拒绝');

  // A committed write followed by a failed read is not a failed write.
  const read = deferred(); let writes=0;
  options.write = async () => {writes++}; options.read = () => read.promise;
  queue.save('a',true);
  await Promise.resolve();
  queue.update(current => ({...current,a:draft('3.75',3)}));
  read.reject(new Error('读回失败')); await untilIdle(queue);
  assert.equal(writes,1); assert.equal(queue.getSnapshot().uncertain,true);
  assert.match(queue.getSnapshot().error,/^范围 2\.50：/,'Failure feedback identifies the submitted snapshot, not the newer draft');
  assert.equal(queue.getSnapshot().drafts.a.value,'3.75');
  queue.save('a',true); assert.equal(writes,1);
  queue.update(() => ({})); queue.confirm();
  assert.equal(queue.getSnapshot().uncertain,true,'Discard cannot release an unknown result');
  options.read = async () => {throw new Error('仍不可读')};
  assert.equal(await queue.reread(),false); queue.confirm();
  assert.equal(queue.getSnapshot().uncertain,true);
  options.read = async () => ({});
  assert.equal(await queue.reread(),true);
  assert.equal(queue.getSnapshot().uncertain,true,'Readback still requires the existing human acknowledgement');
  queue.confirm(); assert.equal(queue.getSnapshot().uncertain,false); assert.equal(writes,1);

  // A known successful write stays visible on a failed read, then retires after explicit reconciliation.
  options.write = async () => {}; options.read = async () => {throw new Error('读回失败')};
  queue.update(() => ({c:draft('4.00',4)})); queue.save('c'); await untilIdle(queue);
  assert.equal(queue.getSnapshot().drafts.c.value,'4.00');
  options.read = async () => ({}); await queue.reread(); queue.confirm();
  assert.equal(queue.getSnapshot().drafts.c,undefined);

  // A lost write response must retain its submitted draft, not acknowledge it.
  options.write = async () => {writes++;throw new Error('连接中断')};
  queue.update(() => ({b:draft('5.00',4)})); queue.save('b'); await untilIdle(queue);
  assert.equal(queue.getSnapshot().uncertain,true);
  assert.equal(queue.getSnapshot().drafts.b.value,'5.00');
  queue.save('b',true); assert.equal(writes,2);
  queue.dispose();
  console.log('Submission snapshots, rejection, committed/read-failed and lost-reply protection passed');
});
