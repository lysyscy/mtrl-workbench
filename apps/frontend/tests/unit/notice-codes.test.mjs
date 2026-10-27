import test from 'node:test';
import assert from 'node:assert/strict';
import { matchNoticeCodes } from '../../src/notices-api.ts';

test('notice_code_exception_algorithm_without_browser', async () => {
  const row=(id,code,extra={})=>({notice_id:id,bill_no:code,is_excluded:false,is_revoked:false,pay_status:'未付清',...extra});
  const rows=[row(1,'FKTZS2026100001'),row(2,'FKTZS2026100002',{pay_status:'已付清'}),row(3,'FKTZS2026100003'),row(8,'FKTZS2026100003'),row(4,'FKTZS2026100004',{is_excluded:true}),row(5,'FKTZS2026100005',{is_revoked:true})];
  const result=matchNoticeCodes('"fktzs2026100002" FKTZS2026100001 FKTZS2026100001,FKTZS2026100003；FKTZS2026100004\tFKTZS2026100005 QTZC2026100001 FKTZS2026130001 FKTZS2026109999 名称FKTZS2026100006',rows);
  assert.deepEqual([...result.ids],[2,1]);
  assert.deepEqual([...result.paid],['FKTZS2026100002']);
  assert.deepEqual([...result.duplicates],['FKTZS2026100001（2次）']);
  assert.deepEqual([...result.ambiguous],['FKTZS2026100003（系统2条）']);
  assert.deepEqual(result.blocked.map(row=>row.notice_id),[4,5]);
  assert.deepEqual([...result.missing],['FKTZS2026109999']);
  assert.deepEqual([...result.invalid],['QTZC2026100001','FKTZS2026130001','名称FKTZS2026100006']);
  console.log('Pure notice-code exception cases passed; no browser or HTTP listener');
});
