import { uncertainWrite } from './api';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import { useEffect, useRef, useState } from 'react';
import type { Identity } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { cents, decimal, money } from './notices-api';
import { adjustInventory } from './inventory-api';
import type { Adjustment, Inventory, InventoryRow } from './inventory-api';

export function InventoryAdjust({row,adjustment,me,paused,close,reload,unknown,onUnknown,missing}: {
  row:InventoryRow; adjustment:Adjustment|undefined; me:Identity|null; paused:boolean; close:()=>void; reload:()=>Promise<Inventory>;
  unknown:boolean;onUnknown:(value:boolean)=>void;missing:boolean;
}) {
  const [amount,setAmount] = useState(adjustment?.amount ?? row.amount), [remark,setRemark] = useState(adjustment?.remark ?? '');
  const [baseline,setBaseline] = useState({amount:adjustment?.amount ?? row.amount,remark:adjustment?.remark ?? ''});
  const [busy,setBusy] = useState(false), [error,setError] = useState(''), [feedback,setFeedback] = useState('');
  const [verified,setVerified] = useState(false), [confirmClear,setConfirmClear] = useState(false);
  const writeAbort = useRef(new AbortController());
  useEffect(() => { writeAbort.current = new AbortController(); return () => writeAbort.current.abort(); }, []);
  const lock = useRef(false), closing = useDialogClose({busy,dirty:amount !== baseline.amount || remark !== baseline.remark,close,active:!paused});
  let problem = amount.trim() ? '' : '调整后金额必填。', difference = '';
  try {difference = decimal(cents(amount.trim().replace(/[,，]/g,''))-cents(row.amount));}
  catch { /* The existing backend owns parsing and rounding of submitted text. */ }
  if (!remark.trim()) problem ||= '调整备注必填。';
  async function write(clear:boolean) {
    if (lock.current || paused || !me || unknown || (!clear && problem)) return;
    lock.current = true; setBusy(true); setError(''); setFeedback('');onUnknown(true); let written = false;
    try {
      await adjustInventory(row.id,amount,remark,clear,writeAbort.current.signal); written = true;
      if (writeAbort.current.signal.aborted) return;
      setBaseline({amount,remark}); setConfirmClear(false);
      const data = await reload();
      const saved = data.adjustments.find(a => a.row_id === row.id);
      if (!clear && saved) {setAmount(saved.amount);setRemark(saved.remark);setBaseline({amount:saved.amount,remark:saved.remark});}
      onUnknown(false);
      if (clear) close(); else setFeedback('调整单已保存；原始数据未改，相关报表已标记重读。');
    } catch (e) {
      if (writeAbort.current.signal.aborted) return;
      if (written || uncertainWrite(e)) {onUnknown(true);setVerified(false);}
      else onUnknown(false);
      setError(`${written ? '已保存，重读失败。' : uncertainWrite(e) ? '结果待核实，勿重复提交。' : ''}${e instanceof Error ? e.message : '操作失败。'}`);
    } finally {lock.current = false;setBusy(false);}
  }
  async function reread() {
    if (lock.current || paused) return;
    lock.current = true;setBusy(true);
    try {await reload();setVerified(true);setFeedback('已重读，请核对当前调整单；输入仍保留。');}
    catch(e) {setError(e instanceof Error ? e.message : '重读失败。');}
    finally {lock.current = false;setBusy(false);}
  }
  return <BusinessModal open={!paused} requestClose={closing.requestClose} className="inventory-dialog" titleId="inventory-adjust-title"><DialogContents title={`调整单 · ${row.doc_no} #${row.seq}`} titleId="inventory-adjust-title" closing={closing}>
    <dl className="inventory-details"><dt>物料 / 规格</dt><dd>{row.material} / {row.spec || '—'}</dd><dt>核算月 / 仓库</dt><dd>{row.ym} / {row.warehouse}</dd><dt>项目全名</dt><dd>{row.project_full_name || '未记录'}</dd><dt>i8 原始金额</dt><dd>{money(row.amount)}</dd></dl>
    <form onSubmit={e => {e.preventDefault();void write(false);}}>
      {missing && <p className="notice" role="alert">这条原单已不在当前库存，不能继续调整。请关闭后核对原单。</p>}
      <div className="inventory-fields"><label>调整后金额<Input aria-label="调整后金额" value={amount} disabled={busy || unknown || !me} onChange={e => {setAmount(e.target.value);setConfirmClear(false);}} /></label><label>与当前原单差额<output>{difference ? money(difference) : '—'}</output></label></div>
      <label className="inventory-remark">调整备注<Input.TextArea aria-label="调整备注" value={remark} disabled={busy || unknown || !me} onChange={e => {setRemark(e.target.value);setConfirmClear(false);}} autoSize={{minRows:2,maxRows:4}} /></label>
      <p>只调整本条金额，重抓保留调整单。</p>
      {adjustment ? <div className="inventory-trail"><p>留痕：{money(adjustment.before_amount)} → {money(adjustment.amount)}</p><p>{adjustment.operator || '未记录操作人'} · {adjustment.changed_at || '未记录时间'}</p><p>{adjustment.remark}</p></div> : <p>当前没有调整单。</p>}
      {feedback && <p role="status">{feedback}</p>}{error && <p className="notice" role="alert">{error}{!unknown && <Button disabled={busy || paused} onClick={() => void reread()}>重读核对</Button>}</p>}
      {unknown && !busy && <p className="inventory-warning">核对实际结果后再继续。<Button disabled={busy || paused} onClick={() => void reread()}>重读核对</Button><Button disabled={!verified || busy || paused} onClick={() => {onUnknown(false);setError('');setVerified(false);}}>已核对，继续编辑</Button></p>}
      {confirmClear && <div className="inventory-trail" role="alert"><p>撤销本条调整单：{adjustment ? money(adjustment.amount) : '—'} → 原单 {money(row.amount)}。相关统计将重算。</p><Button danger disabled={busy || unknown || paused} onClick={() => void write(true)}>确认撤销调整单</Button><Button disabled={busy} onClick={() => setConfirmClear(false)}>保留调整</Button></div>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button>{adjustment && <Button danger disabled={busy || unknown || !me} onClick={() => setConfirmClear(true)}>撤销调整单…</Button>}<Button type="primary" htmlType="submit" loading={busy} disabled={paused || unknown || !me || Boolean(problem)} title={problem}>保存调整单</Button></div>
      {problem && <p className="muted">{problem}</p>}
    </form>
  </DialogContents></BusinessModal>;
}
