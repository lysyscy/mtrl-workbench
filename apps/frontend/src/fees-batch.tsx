import { uncertainWrite } from './api';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import { useEffect, useRef, useState } from 'react';
import type { Identity } from './api';
import { BusinessModal } from './business-modal';
import { BoundedTable } from './bounded-table';
import { DialogContents, useDialogClose } from './dialog-close';
import { TimePicker } from './time-picker';
import { addMonth, feeWrite } from './fees-api';
import type { FeeRow } from './fees-api';

export function FeeBatch({ me, ym, project, display, rows, paused, close, saved }: {
  me: Identity | null; ym: string; project: string; display: string; rows: FeeRow[]; paused: boolean; close: () => void; saved: () => Promise<unknown>;
}) {
  const [sourceRows] = useState(rows);
  const [names] = useState(() => [...new Set(rows.map(row => row.item.trim()))]);
  const [start, setStart] = useState(() => addMonth(ym,-2)), [count, setCount] = useState(3);
  const [values, setValues] = useState<Record<string,string>>(() => Object.fromEntries(names.map(name => [`${name}:2`,rows.find(row => row.item.trim() === name)!.amount])));
  const initial = useRef(JSON.stringify([start,count,values]));
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [uncertain, setUncertain] = useState(false), [verified, setVerified] = useState(false), [written, setWritten] = useState(false);
  const writeAbort = useRef(new AbortController());
  useEffect(() => { writeAbort.current = new AbortController(); return () => writeAbort.current.abort(); }, []);
  const lock = useRef(false), current = useRef({ paused, me }); current.current = { paused, me };
  const months = Array.from({ length: count }, (_,i) => addMonth(start,i));
  const closing = useDialogClose({ busy: busy || uncertain && !verified, dirty: !written && initial.current !== JSON.stringify([start,count,values]), close, active: !paused });
  async function save() {
    if (lock.current || current.current.paused || !current.current.me || uncertain || written) return;
    lock.current = true; setBusy(true); setError(''); let success = false;
    try {
      await feeWrite('batch', { project, items: names,
        months: months.map((month,i) => ({ ym: month, values: Object.fromEntries(names.map(name => [name,values[`${name}:${i}`] ?? ''])) })) }, writeAbort.current.signal);
      if (writeAbort.current.signal.aborted) return;
      success = true; setWritten(true); await saved(); close();
    } catch (failure) {
      if (writeAbort.current.signal.aborted) return;
      setUncertain(success || uncertainWrite(failure)); setVerified(false);
      setError(`${success ? '已保存，重读失败。' : ''}${failure instanceof Error ? failure.message : '操作失败。'}${success || uncertainWrite(failure) ? '请先核对，勿重复提交。' : ''}`);
    } finally { lock.current = false; setBusy(false); }
  }
  async function reread() {
    if (lock.current || paused) return; lock.current = true; setBusy(true);
    try { await saved(); setVerified(true); setError('已重新读取费用，请核对本次录入的各月份；确认未写入才可再次保存。'); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '重读失败。'); }
    finally { lock.current = false; setBusy(false); }
  }
  return <BusinessModal open={!paused} requestClose={closing.requestClose} className="fee-batch-dialog" titleId="fee-batch-title"><DialogContents title="特殊费用 · 按月批量录入" titleId="fee-batch-title" closing={closing}>
    <p>{display}</p><div className="fee-batch-toolbar"><label>首个核算月<TimePicker label="批量首个核算月" modes={['月']} value={start} onChange={setStart} disabled={busy || uncertain || written} /></label>
      <Button disabled={busy || uncertain || written} onClick={() => setCount(n => n+1)}>增加下一月</Button>
      <Button disabled={busy || uncertain || written || count <= 1} onClick={() => { if (names.some(name => values[`${name}:${count-1}`]?.trim())) { setError('最后一个月仍有输入，请先清空后移除。'); return; } setCount(n => n-1); }}>移除最后一月</Button></div>
    <p className="muted">空格不写；非法金额整批不写；同月同名更新最早一条。</p>
    <div className="fee-batch-table"><BoundedTable columns={[{ min: 14, max: 30, flex: 1 }, ...months.map(() => ({ min: 12, max: 18, flex: 1 }))]}><thead><tr><th>数据项</th>{months.map(month => <th key={month}>{month}</th>)}</tr></thead><tbody>
      {names.map(name => <tr key={name}><th>{name || '未命名'}</th>{months.map((month,i) => <td key={i}><Input aria-label={`${month}${name || '未命名'}金额`} value={values[`${name}:${i}`] ?? ''} disabled={busy || uncertain || written} className="fee-money-input" placeholder="不写"
        onChange={event => setValues(old => ({ ...old,[`${name}:${i}`]:event.target.value }))} /></td>)}</tr>)}
    </tbody></BoundedTable></div>
    {sourceRows.length !== names.length && <p className="notice">同名项合为一行；批量保存更新每月最早一条同名项。</p>}
    {error && <p className="notice" role="alert">{error}</p>}{busy && <p role="status">正在处理…</p>}
    {uncertain && <div className="fee-batch-toolbar"><Button disabled={busy} onClick={() => void reread()}>重读核对</Button>{verified && !written && <Button onClick={() => { setUncertain(false); setError('请核对保留输入后再保存。'); }}>已确认未写入，继续编辑</Button>}{verified && <Button onClick={close}>已核对，关闭</Button>}</div>}
    <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button className="primary" disabled={busy || uncertain || written || !me} onClick={() => void save()}>保存</Button></div>
  </DialogContents></BusinessModal>;
}
