import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { ReadGrid } from './business-grid';
import { numberColumnWidth, fullTextWidth } from './grid';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { ApiError, record, requestFile, requestJson } from './api';
import { body, money } from './notices-api';
import type { NoticeRow } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';
import { SESSION_MODE_BROWSER, sessionPayload } from './i8-browser-relay';
import { useI8Session } from './i8-session';

type BatchMode = 'pdf' | 'print';
type BatchStage = 'connecting' | 'preparing' | 'dispatching';

interface Outcome {
  notice_id: number;
  bill_no: string;
  ok: boolean;
  unverified: boolean;
  reason: string;
  download_url: string;
}

interface Result { total: number; success: number; failed: number; items: Outcome[] }
interface BatchView {
  batch_id: string;
  mode: BatchMode;
  stage: BatchStage;
  status: 'running' | 'ready' | 'failed' | 'complete';
  total: number;
  prepared_count: number;
  dispatch_processed_count: number;
  dispatched_count: number;
  current_bill_no: string;
  failed_bill_no: string;
  failed_notice_id: number | null;
  reason: string;
  kick_token: string;
  items: { notice_id: number; status: string }[];
  result: Result | null;
}

function readBatch(value: unknown, mode: BatchMode): BatchView {
  if (!record(value) || value.mode !== mode || typeof value.batch_id !== 'string' || !value.batch_id
    || !['connecting', 'preparing', 'dispatching'].includes(String(value.stage))
    || !['running', 'ready', 'failed', 'complete'].includes(String(value.status))
    || ![value.total, value.prepared_count, value.dispatch_processed_count, value.dispatched_count].every(Number.isSafeInteger)
    || ![value.current_bill_no, value.failed_bill_no, value.reason, value.kick_token].every(x => typeof x === 'string')
    || (value.failed_notice_id !== null && !Number.isSafeInteger(value.failed_notice_id))
    || !Array.isArray(value.items) || !value.items.every(x => record(x) && Number.isSafeInteger(x.notice_id) && typeof x.status === 'string')) {
    throw new ApiError('批次状态不完整，请重查批次。');
  }
  const result = value.result;
  if (result !== null && (!record(result) || ![result.total, result.success, result.failed].every(Number.isSafeInteger)
    || !Array.isArray(result.items) || !result.items.every(x => record(x) && Number.isSafeInteger(x.notice_id)
      && typeof x.bill_no === 'string' && typeof x.ok === 'boolean' && typeof x.unverified === 'boolean'
      && typeof x.reason === 'string' && typeof x.download_url === 'string'))) {
    throw new ApiError('执行回执不完整，请重查批次。');
  }
  return value as unknown as BatchView;
}

const stageLabel: Record<BatchStage, string> = {
  connecting: '连接 i8', preparing: '准备 PDF', dispatching: '投递打印机',
};
const batchPath = '/api/m03/print-batches';
const pathOf = (id: string) => batchPath + '/' + encodeURIComponent(id);
const messageOf = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;

export function NoticePrint({ rows, mode, blocked, close }: { rows: NoticeRow[]; mode: BatchMode; blocked: boolean; close: () => void }) {
  const session = useI8Session();
  const lock = useRef(false);
  const [scope, setScope] = useState(() => [...rows]);
  const [waiting, setWaiting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [batch, setBatch] = useState<BatchView | null>(null);
  const [error, setError] = useState('');
  const [readFailed, setReadFailed] = useState(false);
  const [kick, setKick] = useState<{ token: string; message: string } | null>(null);
  const [file, setFile] = useState<{ url: string; filename: string; pdf: boolean } | null>(null);
  const blobUrl = useRef('');
  const alive = useRef(true);
  const blockedRef = useRef(blocked);
  const confirmationGeneration = useRef(0);
  blockedRef.current = blocked;
  const title = mode === 'print' ? '批量打印' : '只导出 PDF';
  const closing = useDialogClose({ busy, dirty: false, close });
  const result = batch?.result;
  const preparationFailed = batch?.status === 'failed' && batch.stage !== 'dispatching';
  const failedIds = new Set(preparationFailed && batch.failed_notice_id !== null
    ? batch.items.filter(item => item.status === 'failed').map(item => item.notice_id) : []);
  const remaining = scope.filter(row => !failedIds.has(row.notice_id));
  const stage = batch?.stage ?? 'connecting';
  const completed = stage === 'dispatching' ? batch?.dispatch_processed_count : batch?.prepared_count;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (blobUrl.current) URL.revokeObjectURL(blobUrl.current);
    };
  }, []);
  useEffect(() => {
    setWaiting(false);
    setKick(null);
    return () => { confirmationGeneration.current += 1; };
  }, [blocked, session.mode]);
  useEffect(() => {
    if (waiting && !blocked && session.mode === SESSION_MODE_BROWSER && session.connected) {
      setWaiting(false);
      void prepare();
    }
  }, [waiting, blocked, session.mode, session.connected]);

  async function loadFile(value: Result) {
    const url = value.items.find(x => x.ok && x.download_url)?.download_url;
    if (!url) throw new ApiError('没有可下载的产物，请核对逐条回执。');
    const item = await requestFile(url);
    if (!alive.current) return;
    clearFile();
    blobUrl.current = URL.createObjectURL(item.blob);
    setFile({ url: blobUrl.current, filename: item.filename, pdf: item.blob.type.includes('application/pdf') });
  }

  function clearFile() {
    if (blobUrl.current) URL.revokeObjectURL(blobUrl.current);
    blobUrl.current = '';
    setFile(null);
  }

  async function follow(handle: BatchView, generation: number, reread = false) {
    const path = pathOf(handle.batch_id);
    try {
      let current = reread ? readBatch(await requestJson(path), mode) : handle;
      while (alive.current) {
        if (current.batch_id !== handle.batch_id) throw new ApiError('批次编号已变化，请重查原批次。');
        setBatch(current);
        if (current.status === 'ready' && mode === 'print') {
          if (blockedRef.current) { setReadFailed(true); return; }
          current = readBatch(await requestJson(path + '/dispatch', { method: 'POST' }), mode);
        } else if (current.status === 'running') {
          await new Promise(resolve => setTimeout(resolve, 500));
          if (!alive.current) return;
          current = readBatch(await requestJson(path), mode);
        } else {
          if (generation === confirmationGeneration.current && session.mode !== SESSION_MODE_BROWSER && current.kick_token) {
            setKick({ token: current.kick_token, message: current.reason });
          }
          if (mode === 'pdf' && current.result?.success) {
            try { await loadFile(current.result); }
            catch (failure) { setError(messageOf(failure, '下载失败，请重试下载。')); }
          }
          return;
        }
      }
    } catch (failure) {
      setReadFailed(true);
      setError(messageOf(failure, '批次状态暂时无法核对，请重查原批次。'));
    }
  }

  async function prepare(token = '') {
    if (blocked || lock.current || !scope.length) return;
    if (session.mode === SESSION_MODE_BROWSER && !session.connected) {
      setBatch(null);
      setError('');
      setWaiting(true);
      if (!session.maintaining) void session.connect();
      return;
    }
    lock.current = true;
    setBusy(true);
    setBatch(null);
    setKick(null);
    setError('');
    setReadFailed(false);
    clearFile();
    const generation = confirmationGeneration.current;
    try {
      const payload = sessionPayload(session, token ? { kick_token: token } : {}, {
        ids: scope.map(row => row.notice_id), mode,
      });
      const initial = readBatch(await requestJson(batchPath + '/prepare', { method: 'POST', ...body(payload) }), mode);
      await follow(initial, generation);
    } catch (failure) {
      if (generation === confirmationGeneration.current && !token
        && session.mode !== SESSION_MODE_BROWSER && failure instanceof ApiError
        && failure.status === 409 && failure.code === 'i8_online_conflict'
        && record(failure.detail) && typeof failure.detail.kick_token === 'string' && failure.detail.kick_token) {
        setKick({ token: failure.detail.kick_token, message: failure.message });
      } else setError(messageOf(failure, '连接 i8 失败，请重试全批。'));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  async function recheck() {
    if (!batch || blocked || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    setReadFailed(false);
    try { await follow(batch, confirmationGeneration.current, true); }
    finally { lock.current = false; setBusy(false); }
  }

  function removeFailed() {
    setScope(remaining);
    setBatch(null);
    setKick(null);
    setError('');
    clearFile();
  }

  async function retryDownload() {
    if (!result || blocked || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try { await loadFile(result); }
    catch (failure) { setError(messageOf(failure, '下载失败，请重试下载。')); }
    finally { lock.current = false; setBusy(false); }
  }

  return <BusinessModal open={!blocked} className="project-dialog notice-print-dialog" titleId="notice-print-title" requestClose={closing.requestClose}>
    <DialogContents title={title} titleId="notice-print-title" closing={closing}>
      <p>本批 {scope.length} 条通知书（含搜索隐藏行）。</p>
      <ReadGrid table="notice-print-list" className="notice-print-list" label="本批通知书" domLayout="autoHeight" rows={scope} rowId={row => String(row.notice_id)} columns={[
        { field: 'bill_no', headerName: '单据编码', ...fullTextWidth(scope.map(row => row.bill_no || '—')), wrapText: false, valueFormatter: p => p.value || '—' },
        { field: 'project_display', headerName: '付款项目' },
        { field: 'amount_approved', headerName: '审批金额（元）', ...numberColumnWidth(scope.map(row => money(row.amount_approved))), cellClass: 'money', valueFormatter: p => money(p.value) },
      ]} />
      {(waiting || busy || batch?.status === 'running') && <div>
        <p>{stageLabel[stage]}{stage !== 'connecting' && <> {completed}/{batch?.total}</>}{batch?.current_bill_no && <> · {batch.current_bill_no}</>}</p>
        {stage !== 'connecting' && <progress aria-label={stageLabel[stage]} max={batch?.total} value={completed} />}
        {waiting && <p role="status">{session.notice || '正在连接工作台与 i8 浏览器会话…'}</p>}
      </div>}
      {preparationFailed && <p className="notice" role="alert">
        {stageLabel[stage]}失败{batch.failed_bill_no && <> · {batch.failed_bill_no}</>}。{batch.reason} 已投递 {batch.dispatched_count} 张。
      </p>}
      {result && (mode === 'pdf' || !preparationFailed) && <section aria-label="执行回执">
        <p role="status">{mode === 'pdf' ? '已生成' : '已投递'} {result.success} / 共 {result.total} 条，未完成 {result.failed} 条。</p>
        <ul>{result.items.map(item => <li key={item.notice_id} className={!item.ok ? 'notice' : ''}>
          {item.bill_no || item.notice_id}：{!item.ok ? '未完成' : item.unverified ? '已投递但未核实，请核对出纸，勿重复打印' : mode === 'pdf' ? '已生成' : '已投递'}
          {item.reason && <>，{item.reason}</>}
        </li>)}</ul>
      </section>}
      {error && <p className="notice" role="alert">{error}</p>}
      {kick && <p className="notice" role="status">{kick.message}</p>}
      {file?.pdf && <><p><a href={file.url} target="_blank" rel="noreferrer">在新窗口预览 PDF</a></p>
        <iframe className="notice-pdf-preview" title="付款通知书 PDF 预览" src={file.url} /></>}
      <div className="dialog-actions">
        <Link to="/i8" onClick={event => { if (busy) event.preventDefault(); else closing.requestClose(); }}>查看运行记录</Link>
        <Button htmlType="button" disabled={busy} onClick={closing.requestClose}>关闭</Button>
        {waiting && <Button htmlType="button" onClick={() => setWaiting(false)}>取消等待</Button>}
        {!busy && !waiting && kick && session.mode !== SESSION_MODE_BROWSER && <>
          <Button htmlType="button" onClick={() => setKick(null)}>取消下线确认</Button>
          <Button htmlType="button" type="primary" disabled={blocked} onClick={() => void prepare(kick.token)}>让现有会话下线并继续</Button>
        </>}
        {!busy && !waiting && !kick && (!batch || preparationFailed) &&
          <Button htmlType="button" type="primary" disabled={blocked} onClick={() => void prepare()}>
            {preparationFailed || error ? '重试全批' : '确认本批'}
          </Button>}
        {preparationFailed && failedIds.size > 0 && remaining.length > 0 &&
          <Button htmlType="button" disabled={busy || blocked} onClick={removeFailed}>移出异常单并重新确认剩余批次</Button>}
        {readFailed && <Button htmlType="button" disabled={busy || blocked} onClick={() => void recheck()}>重查原批次</Button>}
        {file && <Button htmlType="button" type="primary" disabled={busy || blocked} onClick={() => {
          const link = document.createElement('a');
          link.href = file.url;
          link.download = file.filename;
          link.click();
        }}>下载 {file.filename}</Button>}
        {mode === 'pdf' && Boolean(result?.success) && !file &&
          <Button htmlType="button" disabled={busy || blocked} onClick={() => void retryDownload()}>重试下载</Button>}
      </div>
    </DialogContents>
  </BusinessModal>;
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
