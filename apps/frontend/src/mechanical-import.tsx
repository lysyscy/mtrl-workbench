import { useEffect, useRef, useState } from 'react';
import { ApiError, record, requestJson } from './api';
import { body } from './notices-api';
import { detailNet, detailProblems, detailSum, mechanicalMoney as money } from './mechanical-api';
import type { Category, DetailRow, Effective } from './mechanical-api';
import { fields, MechanicalDialog } from './mechanical-details';

interface Batch { key: string; warehouse: string; ym: string; category: Category; incoming: DetailRow[]; rows: DetailRow[]; source: unknown; effective: Effective; conflicts: { id: string; row_id: string; field: string; current: unknown; incoming: unknown }[] }
interface Preview { preview_id: string; batches: Batch[] }
interface Receipt { warehouse: string; ym: string; category: Category; revision: number }
function readPreview(value: unknown): Preview {
  if (!record(value) || typeof value.preview_id !== 'string' || !Array.isArray(value.batches) || !value.batches.length || value.batches.some((b: unknown) => !record(b) || typeof b.key !== 'string' || typeof b.warehouse !== 'string' || typeof b.ym !== 'string' || !['zero','monthly'].includes(String(b.category)) || !Array.isArray(b.incoming) || !Array.isArray(b.rows) || !Array.isArray(b.conflicts) || !record(b.effective) || !record(b.effective.values))) throw new ApiError('录入预览不完整，请重新预览。');
  return value as unknown as Preview;
}
function sourceText(value: unknown): string {
  if (value == null || value === '') return '—';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}
function sourceLocation(value: unknown): string {
  if (!record(value)) return sourceText(value);
  return [value.sheet,value.row!=null?'第'+sourceText(value.row)+'行':null,value.cell].filter(Boolean).join(' · ') || sourceText(value.file) || '已附来源';
}
function conflictText(value: unknown, category: Category, wholeRow: boolean): string {
  if (value == null) return wholeRow ? '移除该行' : '空白';
  if (record(value) && wholeRow) {
    const aliases: Record<string,string> = {use:'usage',vendor:'lessor',memo:'note'};
    return fields[category].flatMap(([field,label])=>{
      const item=value[field]??value[aliases[field]??''];
      return item==null||item===''?[]:[label+'：'+sourceText(item)];
    }).join('；');
  }
  return sourceText(value);
}
export function MechanicalImport({ writable, keywords, label, close, refresh, busyChanged, draftConflict, view }: {
  writable: boolean; keywords: string[]; label: (warehouse: string) => string; close: () => void; refresh: () => Promise<boolean>; busyChanged: (busy: boolean) => void; draftConflict: (batches: Batch[]) => boolean; view: (batch: Receipt) => void;
}) {
  const [file,setFile] = useState<File | null>(null), [preview,setPreview] = useState<Preview | null>(null);
  const [resolutions,setResolutions] = useState<Record<string,string>>({}), [receipt,setReceipt] = useState<Receipt[] | null>(null);
  const [busy,setBusy] = useState(false), [message,setMessage] = useState('');
  const lock = useRef(false), alive = useRef(true);
  useEffect(()=>{alive.current=true;return ()=>{alive.current=false;};},[]);
  async function run(action: () => Promise<void>) {
    if (lock.current || !writable) return;
    lock.current=true;setBusy(true);busyChanged(true);setMessage('');
    try { await action(); } catch(error) { if(alive.current)setMessage(error instanceof Error ? error.message : '录入未完成，请核对后重试。'); }
    finally { lock.current=false;busyChanged(false);if(alive.current)setBusy(false); }
  }
  async function load() {
    if (!file) throw new ApiError('请选择Agent整理的录入文件。');
    if (file.size>25*1024*1024) throw new ApiError('文件超过25MB，请按月份拆分。');
    let data: unknown;
    try { data=JSON.parse(await file.text()); } catch { throw new ApiError('文件内容无法识别，请核对录入文件。'); }
    if (record(data) && data.detail_import) data=data.detail_import;
    if (!record(data) || !Array.isArray(data.batches) || !data.batches.length) throw new ApiError('请选择零租／包月明细录入文件。');
    const result=readPreview(await requestJson('/api/m06/workbench/import-preview',{method:'POST',...body({...data,request_id:crypto.randomUUID()})}));
    if(alive.current){setPreview(result);setResolutions({});}
  }
  const conflicts=preview?.batches.flatMap(batch=>batch.conflicts.map(conflict=>({batch,conflict,key:batch.key+'|'+conflict.id})))??[];
  const missing=conflicts.some(item=>!resolutions[item.key]);
  const unsaved=Boolean(preview&&draftConflict(preview.batches));
  async function confirm() {
    if (!preview || missing || unsaved) return;
    const result=await requestJson('/api/m06/workbench/import-confirm',{method:'POST',...body({preview_id:preview.preview_id,resolutions,confirm_amounts:false})});
    if (!record(result) || result.ok!==true || !Array.isArray(result.batches) || result.batches.length!==preview.batches.length || result.batches.some((b: unknown)=>!record(b)||typeof b.warehouse!=='string'||typeof b.ym!=='string'||!['zero','monthly'].includes(String(b.category))||!Number.isSafeInteger(b.revision))) throw new ApiError('写入回执不完整，请重新读取并核对明细。');
    if(alive.current)setReceipt(result.batches as Receipt[]);
    const read=await refresh();
    if(alive.current)setMessage(read?'明细已写入，有效月值仍待单独确认。':'明细已写入，重新读取失败；关闭后请重新读取。');
  }
  return <MechanicalDialog title={receipt?'原报明细录入回执':preview?'确认录入明细':'录入原报明细'} close={close} busy={busy}>
    {!preview&&!receipt&&<label>Agent整理的录入文件<input type="file" accept=".json,application/json" disabled={busy} onChange={event=>{setFile(event.target.files?.[0]??null);setMessage('');}} /></label>}
    {preview&&!receipt&&<>
      <p>确认只保存明细；有效月值在明细页另行确认。金额单位：元。</p>
      <div className="mechanical-import-table"><table><thead><tr><th>项目／月份</th><th>类别</th><th>原报行数</th><th>有效含税 → 原报建议</th><th>有效净额 → 原报建议</th><th>来源</th></tr></thead><tbody>{preview.batches.map(batch=>{
        const gross=detailSum(batch.incoming.map(row=>row.amount)),net=detailSum(batch.incoming.map(detailNet));
        const oldGross=batch.effective.values[batch.category==='zero'?'mech_2':'mech_3'],oldNet=batch.effective.values[batch.category==='zero'?'mech_4':'mech_5'];
        const source=record(batch.source)?batch.source.file:batch.source;
        const reduction=(old:unknown,next:string|null)=>old!=null&&next!=null&&Number(next)<Number(old)?' · 减少，请核实':'';
        return <tr key={batch.key}><th>{label(batch.warehouse)}／{batch.ym}</th><td>{batch.category==='zero'?'零租':'包月'}</td><td>{batch.incoming.length}</td><td className="money">{money(oldGross)} → {money(gross)}{reduction(oldGross,gross)}</td><td className="money">{money(oldNet)} → {money(net)}{reduction(oldNet,net)}{batch.incoming.some(row=>detailNet(row)===null)?' · 部分净额待核':''}</td><td>{sourceText(source)}</td></tr>;
      })}</tbody></table></div>
      {preview.batches.map(batch=><details key={batch.key}><summary>{label(batch.warehouse)}／{batch.ym}／{batch.category==='zero'?'零租':'包月'} · 查看原报明细与来源</summary><p className="mechanical-import-source">{record(batch.source)?<>{sourceText(batch.source.file)} · {sourceLocation(batch.source)}{batch.source.sha256!=null&&<><br />原文件指纹：{sourceText(batch.source.sha256)}</>}</>:sourceText(batch.source)}</p><div className="mechanical-import-table"><table><thead><tr><th>设备／规格</th><th>出租单位</th><th>车牌</th><th>日期／期间</th><th>含税</th><th>票种／税率</th><th>不含税</th><th>来源</th><th>待补</th></tr></thead><tbody>{batch.incoming.map(row=><tr key={row.id}><td>{sourceText(row.device)} {String(row.spec??'')}</td><td>{String(row.vendor??row.lessor??'')}</td><td>{String(row.plate||'待补')}</td><td>{String(row.date??'')}</td><td className="money">{money(row.amount)}</td><td>{String(row.tax||'待核')}</td><td className="money">{money(detailNet(row))}</td><td>{sourceLocation(row.source)}</td><td>{detailProblems(row,batch.category,batch.ym,keywords).join('、')||'—'}</td></tr>)}</tbody></table></div></details>)}
      {conflicts.length>0&&<><h3>逐项确认修订冲突</h3><div className="mechanical-import-table"><table><thead><tr><th>位置</th><th>系统当前值</th><th>原报新值</th><th>采用</th></tr></thead><tbody>{conflicts.map(({batch,conflict,key})=>{
        const field=conflict.field==='__row__'?'整行／拆合行':fields[batch.category].find(([field])=>field===({usage:'use',lessor:'vendor',note:'memo'} as Record<string,string>)[conflict.field]||field===conflict.field)?.[1]??({original:'原报含税',sourceNet:'原报不含税',originalTax:'原报票种／税率',source:'来源'} as Record<string,string>)[conflict.field]??'明细字段';
        const row=batch.incoming.find(row=>row.id===conflict.row_id)??batch.rows.find(row=>row.id===conflict.row_id);
        return <tr key={key}><th>{label(batch.warehouse)}／{batch.ym}／{String(row?.device??'明细')}／{field}</th><td>{conflictText(conflict.current,batch.category,conflict.field==='__row__')}</td><td>{conflictText(conflict.incoming,batch.category,conflict.field==='__row__')}</td><td><select aria-label={`采用${label(batch.warehouse)}${field}`} value={resolutions[key]??''} disabled={busy} onChange={event=>setResolutions(previous=>({...previous,[key]:event.target.value}))}><option value="">请选择</option><option value="current">保留系统值</option><option value="incoming">采用原报值</option></select></td></tr>;
      })}</tbody></table></div></>}
      {unsaved&&<p role="alert">本次项目／月份有未保存明细，请关闭后先保存或撤销修改，再重新预览。</p>}
    </>}
    {receipt&&<ul>{receipt.map(batch=><li key={batch.warehouse+batch.ym+batch.category}>{label(batch.warehouse)}／{batch.ym}／{batch.category==='zero'?'零租':'包月'} · 已保存 <button disabled={busy||!writable} onClick={()=>view(batch)}>查看明细</button></li>)}</ul>}
    {message&&<p role="status">{message}</p>}
    <footer><button disabled={busy} onClick={close}>{receipt?'关闭':'取消'}</button>{!receipt&&(preview?<><button disabled={busy||!writable} onClick={()=>{setPreview(null);setResolutions({});setMessage('');}}>重新选择文件</button><button disabled={busy||!writable||missing||unsaved} title={missing?'请逐项选择修订冲突':''} onClick={()=>void run(confirm)}>{busy?'正在写入…':'确认写入明细'}</button></>:<button disabled={busy||!writable} onClick={()=>void run(load)}>{busy?'正在预览…':'查看录入预览'}</button>)}</footer>
  </MechanicalDialog>;
}
