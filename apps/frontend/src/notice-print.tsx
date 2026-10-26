import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { BoundedTable } from './bounded-table';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { ApiError, record, requestFile, requestJson } from './api';
import { body, money } from './notices-api';
import type { NoticeRow } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';

interface Outcome { notice_id: number; bill_no: string; ok: boolean; unverified: boolean; reason: string; download_url: string }
interface Result { total: number; success: number; failed: number; items: Outcome[]; unprinted_bill_nos: string[] }
function readResult(value: unknown): Result {
  if (!record(value) || ![value.total,value.success,value.failed].every(Number.isSafeInteger) || !Array.isArray(value.items) || !Array.isArray(value.unprinted_bill_nos) || !value.unprinted_bill_nos.every(x => typeof x === 'string') || !value.items.every(x => record(x) && Number.isSafeInteger(x.notice_id) && typeof x.bill_no === 'string' && typeof x.ok === 'boolean' && typeof x.unverified === 'boolean' && typeof x.reason === 'string' && typeof x.download_url === 'string')) throw new ApiError('执行回执不完整，请先查看运行记录核对，勿重复打印。');
  return value as unknown as Result;
}
function download(url: string, filename: string) { const link=document.createElement('a');link.href=url;link.download=filename;link.click(); }
export function NoticePrint({ rows, mode, blocked, close }: { rows: NoticeRow[]; mode: 'pdf'|'print'; blocked: boolean; close: () => void }) {
  const lock=useRef(false), attempted=useRef(false);
  const [busy,setBusy]=useState(true), [result,setResult]=useState<Result|null>(null), [error,setError]=useState('');
  const [file,setFile]=useState<{url:string;filename:string;pdf:boolean}|null>(null);
  const blobUrl=useRef('');
  const title=mode==='print'?'批量打印':'只导出 PDF';
  const closing = useDialogClose({ busy, dirty: false, close });
  useEffect(() => { if (!blocked) void run(); }, [blocked]);
  useEffect(()=>()=>{ if(blobUrl.current) URL.revokeObjectURL(blobUrl.current); },[]);
  async function loadFile(value: Result) {
    const url=value.items.find(x=>x.ok && x.download_url)?.download_url;
    if(!url) throw new ApiError('没有可下载的产物，请核对逐条回执。');
    const item=await requestFile(url);
    blobUrl.current=URL.createObjectURL(item.blob);
    setFile({url:blobUrl.current,filename:item.filename,pdf:item.blob.type.includes('application/pdf')});
  }
  async function run() {
    if(blocked||lock.current||attempted.current) return;
    lock.current=true;attempted.current=true;setBusy(true);setError('');
    try { const value=readResult(await requestJson('/api/m03/batch',{method:'POST',...body({ids:rows.map(r=>r.notice_id),mode})}));setResult(value);if(mode==='pdf'&&value.success) await loadFile(value); }
    catch(e) { setError((e instanceof Error?e.message:'执行未完成，请核对运行记录。')+(mode==='print'?' 请先核对运行记录及打印机，勿直接重复打印。':'')); }
    finally { lock.current=false;setBusy(false); }
  }
  async function retryDownload() {
    if(!result||busy||blocked) return;setBusy(true);setError('');
    try { await loadFile(result); }catch(e) { setError(e instanceof Error?e.message:'下载失败，请重试下载。'); }finally {setBusy(false);}
  }
  return <BusinessModal open={!blocked} className="project-dialog notice-print-dialog" titleId="notice-print-title" requestClose={closing.requestClose}><DialogContents title={title} titleId="notice-print-title" closing={closing}>
    <p>本批 {rows.length} 条通知书（含搜索隐藏行）。</p>
    <div className="notice-print-list"><BoundedTable columns={[{ min: 12, max: 16 },{ min: 9, max: 28, flex: 1 },{ min: 10, max: 16 }]}><thead><tr><th>单据编码</th><th>付款项目</th><th>审批金额（元）</th></tr></thead><tbody>{rows.map(row=><tr key={row.notice_id}><td>{row.bill_no||'—'}</td><td>{row.project_display}</td><td>{money(row.amount_approved)}</td></tr>)}</tbody></BoundedTable></div>
    {busy&&<p role="status">正在{title}，请勿重复操作…</p>}
    {result&&<section aria-label="执行回执"><p role="status">{mode==='pdf'?'已生成':'已投递'} {result.success} / 共 {result.total} 条，失败 {result.failed} 条。</p>
      {result.unprinted_bill_nos.length>0&&<p className="notice" role="alert">未产出的单号：{result.unprinted_bill_nos.join('、')}</p>}
      <ul>{result.items.map((item,i)=><li key={`${item.notice_id}-${i}`} className={!item.ok?'notice':''}>{item.bill_no||item.notice_id}：{!item.ok?'失败':item.unverified?'已投递但未核实，请核对出纸，勿重复打印':mode==='pdf'?'已生成':'已投递'}{item.reason&&`，${item.reason}`}</li>)}</ul>
    </section>}
    {error&&<p className="notice" role="alert">{error}</p>}
    {file?.pdf&&<><p><a href={file.url} target="_blank" rel="noreferrer">在新窗口预览 PDF</a></p><iframe className="notice-pdf-preview" title="付款通知书 PDF 预览" src={file.url} /></>}
    <div className="dialog-actions"><Link to="/i8" onClick={event=>{if(busy)event.preventDefault();else closing.requestClose();}}>查看运行记录</Link><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>关闭</Button>
      {file&&<Button htmlType="submit" className="primary" disabled={busy||blocked} onClick={()=>download(file.url,file.filename)}>下载 {file.filename}</Button>}
      {result&&mode==='pdf'&&result.success>0&&!file&&<Button htmlType="submit" disabled={busy||blocked} onClick={()=>void retryDownload()}>重试下载</Button>}
    </div>
  </DialogContents></BusinessModal>;
}
interface Printer { printer_ipp_url:string;print_mode:string;printer_name:string }
interface Layout { key:string;label:string;hint:string;stored:string;env:string;effective:string }
const settingsSignature=(printer:Printer|null,layouts:Layout[])=>JSON.stringify([printer,layouts.map(({key,stored})=>[key,stored])]);
const plain=(value:string)=>value.replace(/\*\*/g,'').replace(/（§[^）]*）/g,'');
export function PrinterSettings({ blocked, close }: { blocked:boolean;close:()=>void }) {
  const lock=useRef(false), initial=useRef('');
  const [printer,setPrinter]=useState<Printer|null>(null),[layouts,setLayouts]=useState<Layout[]>([]),[names,setNames]=useState<string[]>([]);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[feedback,setFeedback]=useState('');
  const closing = useDialogClose({ busy, dirty: Boolean(printer) && settingsSignature(printer,layouts) !== initial.current, close });
  async function load(signal?:AbortSignal) {
    setError('');
    try {
      const [p,s]=await Promise.all([requestJson('/api/m03/settings/printer',signal?{signal}:{}),requestJson('/api/m14/settings',signal?{signal}:{})]);
      if(!record(p)||!['printer_ipp_url','print_mode','printer_name'].every(k=>typeof p[k]==='string')||!record(s)||!Array.isArray(s.items))throw new ApiError('打印设置读取不完整，请重读。');
      const items=s.items.filter(x=>record(x)&&['i8_print_id_material','i8_print_id_mechanical'].includes(String(x.key)));
      if(items.length!==2||!items.every(x=>record(x)&&['key','label','hint','stored','env','effective'].every(k=>typeof x[k]==='string')))throw new ApiError('版式设置读取不完整，请重读。');
      if(signal?.aborted)return;initial.current=settingsSignature(p as unknown as Printer,items as Layout[]);setPrinter(p as unknown as Printer);setLayouts(items as Layout[]);
    }catch(e){if(!signal?.aborted)setError(e instanceof Error?e.message:'设置读取失败，请重读。');}
  }
  useEffect(()=>{const c=new AbortController();void load(c.signal);void requestJson('/api/m03/settings/printers',{signal:c.signal}).then(x=>{if(Array.isArray(x)&&x.every(n=>typeof n==='string'))setNames(x);}).catch(()=>{});return()=>c.abort();},[]);
  async function save() {
    if(!printer||blocked||lock.current)return;lock.current=true;setBusy(true);setError('');setFeedback('');let printerSaved=false;
    try { await requestJson('/api/m03/settings/printer',{method:'PUT',...body(printer)});printerSaved=true;await requestJson('/api/m14/settings',{method:'POST',...body(Object.fromEntries(layouts.map(x=>[x.key,x.stored.trim()])))});setFeedback('打印机和版式设置已保存，即时生效。');await load(); }
    catch(e){setError((printerSaved?'打印机设置已保存，版式未保存。':'未保存。')+(e instanceof ApiError && e.status>=500 && !printerSaved?'打印设置保存失败，请联系维护人员核对配置文件的写入权限。':e instanceof Error?e.message:'请核对后重试。'));}
    finally{lock.current=false;setBusy(false);}
  }
  return <BusinessModal open={!blocked} className="project-dialog printer-settings-dialog" titleId="printer-settings-title" requestClose={closing.requestClose}><DialogContents title="打印机设置" titleId="printer-settings-title" closing={closing}>
    {!printer?(!error&&<p role="status">正在读取打印设置…</p>):<><label>打印机 IPP 地址<input value={printer.printer_ipp_url} onChange={e=>setPrinter({...printer,printer_ipp_url:e.target.value})} placeholder="ipp://192.168.5.248" /></label>
    <label>出纸通道<select value={printer.print_mode} onChange={e=>setPrinter({...printer,print_mode:e.target.value})}>{[['auto','自动（推荐）'],['ipp','IPP'],['driver','系统驱动'],['raw','RAW 9100']].map(([v,t])=><option key={v} value={v}>{t}</option>)}</select></label>
    <p>优先选自动；系统驱动需安装驱动并填写打印机名。RAW 不受支持时可能打出乱码。</p>
    <label>打印机名<input list="notice-printer-names" value={printer.printer_name} onChange={e=>setPrinter({...printer,printer_name:e.target.value})} /></label><datalist id="notice-printer-names">{names.map(n=><option key={n} value={n}/>)}</datalist>{!names.length&&<p>未取到本机打印机名，可手动填写。</p>}
    {layouts.map(item=><div key={item.key}><label>{item.label}<input value={item.stored} placeholder={item.env} onChange={e=>setLayouts(old=>old.map(x=>x.key===item.key?{...x,stored:e.target.value}:x))}/></label><p>{plain(item.hint)}</p><p className="mut">当前生效：{item.effective||'未设置'}，{item.stored?'本处所设；清空并保存后使用默认值':'默认值'}</p></div>)}</>}
    {error&&<p className="notice" role="alert">{error}<Button htmlType="submit" disabled={busy} onClick={()=>void load()}>重读设置</Button></p>}{feedback&&<p role="status">{feedback}</p>}
    <div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>取消</Button><Button htmlType="submit" className="primary" disabled={busy||blocked||!printer} onClick={()=>void save()}>{busy?'正在保存…':'保存'}</Button></div>
  </DialogContents></BusinessModal>;
}
