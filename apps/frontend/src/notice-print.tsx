import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { ReadGrid } from './business-grid';
import { numberColumnWidth, fullTextWidth } from './grid';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { ApiError, record, requestFile, requestJson } from './api';
import { body, money } from './notices-api';
import type { NoticeRow } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';
import { SESSION_MODE_BROWSER, sessionPayload } from './i8-browser-relay';
import { readI8KickConfirmation, revokeI8KickToken } from './i8-api';
import type { SessionChoice } from './i8-browser-relay';
import { I8ConnectionWaitStatus, useI8ActionWait, useI8Session } from './i8-session';

type BatchMode = 'pdf' | 'print';
type BatchStage = 'connecting' | 'preparing' | 'dispatching' | 'done';
type ScopeRow = Pick<NoticeRow, 'notice_id' | 'bill_no'> & Partial<Pick<NoticeRow, 'project_display' | 'amount_approved'>>;
interface PrepareScope { ids: number[]; mode: BatchMode; expected_account: string }
interface KickConfirmation { token: string; message: string; retry: () => Promise<void> }

type DeliveryStatus = 'accepted' | 'failed' | 'unknown';
interface Attempt {
  status: DeliveryStatus;
  channel: string;
  job_id: number | null;
  reason: string;
}

interface Delivery {
  delivery_status: DeliveryStatus | 'pending' | 'in_flight';
  channel: string;
  job_id: number | null;
  attempts: Attempt[];
}

interface Outcome {
  notice_id: number;
  bill_no: string;
  ok: boolean;
  unverified: boolean;
  reason: string;
  download_url: string;
}

interface Result { total: number; success: number; failed: number; items: Outcome[] }
interface A4Block {
  code: 'a4_blocked';
  reason: string;
  can_switch_channel: boolean;
  export_action: string;
}

export interface BatchView {
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
  items: (Delivery & { notice_id: number; bill_no: string; status: string; reason: string })[];
  a4_blocked: A4Block | null;
  result: Result | null;
}

const deliveryLabel = {
  pending: '待投递', in_flight: '正在投递', accepted: '打印机已接收', failed: '明确失败', unknown: '结果待核实',
};
const channelLabel: Record<string, string> = {ipp: 'IPP', driver: '系统驱动', raw: 'RAW 9100'};
const nullableInteger = (value: unknown) => value === null || Number.isSafeInteger(value);
const validAttempt = (value: unknown) => record(value) && typeof value.channel === 'string'
  && ['accepted', 'failed', 'unknown'].includes(String(value.status))
  && nullableInteger(value.job_id) && typeof value.reason === 'string';

function readBatch(value: unknown, mode: BatchMode): BatchView {
  if (!record(value) || value.mode !== mode || typeof value.batch_id !== 'string' || !value.batch_id
    || !['connecting', 'preparing', 'dispatching', 'done'].includes(String(value.stage))
    || !['running', 'ready', 'failed', 'complete'].includes(String(value.status))
    || ![value.total, value.prepared_count, value.dispatch_processed_count, value.dispatched_count].every(Number.isSafeInteger)
    || ![value.current_bill_no, value.failed_bill_no, value.reason, value.kick_token].every(x => typeof x === 'string')
    || (value.failed_notice_id !== null && !Number.isSafeInteger(value.failed_notice_id))
    || !Array.isArray(value.items) || !value.items.every(x => record(x) && Number.isSafeInteger(x.notice_id)
      && [x.bill_no, x.status, x.channel, x.reason].every(field => typeof field === 'string')
      && ['pending', 'in_flight', 'accepted', 'failed', 'unknown'].includes(String(x.delivery_status)) && nullableInteger(x.job_id)
      && Array.isArray(x.attempts) && x.attempts.every(validAttempt))) {
    throw new ApiError('批次状态不完整，请重查批次。');
  }
  const block = value.a4_blocked;
  if (block !== null && (!record(block) || block.code !== 'a4_blocked' || typeof block.reason !== 'string'
    || typeof block.can_switch_channel !== 'boolean' || block.export_action !== pathOf(value.batch_id) + '/export-pdf')) {
    throw new ApiError('A4 校验结果不完整，请重查批次。');
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
  connecting: '连接 i8', preparing: '准备 PDF', dispatching: '投递打印机', done: '投递结束',
};
const batchPath = '/api/m03/print-batches';
const pathOf = (id: string) => batchPath + '/' + encodeURIComponent(id);
const messageOf = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;

const batchKey = (owner: string) => 'notice-print-batch:' + owner;

function rememberBatch(owner: string, id: string) {
  try { window.sessionStorage.setItem(batchKey(owner), id); }
  catch { /* The server can still discover the batch if storage is unavailable. */ }
}

export async function recoverNoticePrint(owner: string, signal?: AbortSignal): Promise<BatchView | null> {
  let id: string | null = null;
  try { id = window.sessionStorage.getItem(batchKey(owner)); }
  catch { /* Fall back to the owner-scoped endpoint. */ }
  if (id) {
    try {
      const batch = readBatch(await requestJson(pathOf(id), {signal: signal ?? null}), 'print');
      if (batch.batch_id !== id) throw new ApiError('批次编号已变化，请重查原批次。');
      return batch;
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 404) throw error;
      return null;
    }
  }
  const value = await requestJson(batchPath + '/active', {signal: signal ?? null});
  return value === null ? null : readBatch(value, 'print');
}

export function NoticePrint({rows, mode, owner, resumed, blocked, close}: {
  rows: NoticeRow[]; mode: BatchMode; owner: string; resumed?: BatchView | undefined; blocked: boolean; close: () => void;
}) {
  const session = useI8Session();
  const lock = useRef(false);
  const [scope, setScope] = useState<ScopeRow[]>(() => rows.length || !resumed
    ? [...rows] : resumed.items.map(({notice_id, bill_no}) => ({notice_id, bill_no})));
  const {waiting, cancelWaiting, runWhenReady} = useI8ActionWait(
    JSON.stringify([owner, mode, blocked, scope.map(row => row.notice_id)]),
  );
  const [busy, setBusy] = useState(false);
  const [batch, setBatch] = useState<BatchView | null>(resumed ?? null);
  const [error, setError] = useState('');
  const [readFailed, setReadFailed] = useState(false);
  const [printerUri, setPrinterUri] = useState('');
  const [kick, setKick] = useState<KickConfirmation | null>(null);
  const pendingKick = useRef<KickConfirmation | null>(null);
  const [revocationNotice, setRevocationNotice] = useState('');
  const handledTokens = useRef(new Set<string>());
  const [file, setFile] = useState<{ url: string; filename: string; pdf: boolean } | null>(null);
  const blobUrl = useRef('');
  const alive = useRef(true);
  const blockedRef = useRef(blocked);
  const confirmationGeneration = useRef(0);
  blockedRef.current = blocked;
  const title = mode === 'print' ? '批量打印' : '只导出 PDF';
  const closeLocked = busy && batch?.stage !== 'dispatching';
  const closing = useDialogClose({
    busy: closeLocked, dirty: false, beforeRequestClose: cancelWaiting,
    close: () => { void cancelKick(); close(); },
  });
  const result = batch?.result;
  const deliveryStage = batch?.stage === 'dispatching' || batch?.stage === 'done';
  const preparationFailed = batch?.status === 'failed' && !deliveryStage;
  const recoveredItems = resumed && batch?.batch_id === resumed.batch_id ? batch.items : null;
  const recoveredLabels = new Map(recoveredItems?.map(item => [item.notice_id, item.bill_no]));
  const listedScope = scope.map(row => ({...row, bill_no: recoveredLabels.get(row.notice_id) ?? row.bill_no}));
  const visibleScope = scope.length > 0 && (!recoveredItems || (
    recoveredLabels.size === batch?.total && scope.length === batch.total
    && scope.every(row => recoveredLabels.get(row.notice_id))
  ));
  const failedIds = new Set(preparationFailed && batch.failed_notice_id !== null
    ? batch.items.filter(item => item.status === 'failed').map(item => item.notice_id) : []);
  const remaining = listedScope.filter(row => !failedIds.has(row.notice_id));
  const stage = batch?.stage ?? 'connecting';
  const a4Block = batch?.a4_blocked;
  const completed = deliveryStage ? batch?.dispatch_processed_count : batch?.prepared_count;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (blobUrl.current) URL.revokeObjectURL(blobUrl.current);
    };
  }, []);
  function takeKick() {
    confirmationGeneration.current += 1;
    const pending = pendingKick.current;
    pendingKick.current = null;
    return pending?.token ?? '';
  }

  async function cancelKick() {
    const token = takeKick();
    const generation = confirmationGeneration.current;
    setKick(null);
    const notice = await revokeI8KickToken(token);
    if (notice && alive.current && generation === confirmationGeneration.current) setRevocationNotice(notice);
  }

  function offerKick(token: string, message: string, generation: number, retry: () => Promise<void>) {
    if (!token || handledTokens.current.has(token)) return;
    handledTokens.current.add(token);
    if (!alive.current || blockedRef.current || generation !== confirmationGeneration.current) {
      void revokeI8KickToken(token);
      return;
    }
    const next = {token, message, retry};
    pendingKick.current = next;
    setRevocationNotice('');
    setKick(next);
  }

  function confirmKick() {
    const pending = pendingKick.current;
    if (!pending || lock.current || blockedRef.current) return;
    pendingKick.current = null;
    setKick(null);
    void pending.retry();
  }

  useLayoutEffect(() => {
    setKick(null);
    setRevocationNotice('');
    return () => { void revokeI8KickToken(takeKick()); };
  }, [blocked, session.mode, owner, scope]);

  useEffect(() => {
    if (!resumed) return;
    const recovery = new AbortController();
    void follow(resumed, {signal: recovery.signal});
    return () => recovery.abort();
  }, [resumed, owner]);

  async function loadFile(url?: string) {
    if (!url) throw new ApiError('没有可下载的产物，请核对逐条回执。');
    const item = await requestFile(url);
    if (!alive.current) return null;
    clearFile();
    blobUrl.current = URL.createObjectURL(item.blob);
    const next = {url: blobUrl.current, filename: item.filename, pdf: item.blob.type.includes('application/pdf')};
    setFile(next);
    return next;
  }

  function download(item: {url: string; filename: string}) {
    const link = document.createElement('a');
    link.href = item.url;
    link.download = item.filename;
    link.click();
  }

  function clearFile() {
    if (blobUrl.current) URL.revokeObjectURL(blobUrl.current);
    blobUrl.current = '';
    setFile(null);
  }

  async function follow(handle: BatchView, options: {
    reread?: boolean; dispatchOnReady?: boolean; signal?: AbortSignal;
    onKick?: (token: string, message: string) => void;
  } = {}) {
    const path = pathOf(handle.batch_id);
    try {
      let current = options.reread ? readBatch(await requestJson(path), mode) : handle;
      while (alive.current && !options.signal?.aborted) {
        if (current.batch_id !== handle.batch_id) throw new ApiError('批次编号已变化，请重查原批次。');
        if (mode === 'print') rememberBatch(owner, current.batch_id);
        setBatch(current);
        if (current.status === 'ready') {
          if (!options.dispatchOnReady || blockedRef.current || current.a4_blocked) return;
          current = await requestDispatch(current);
        } else if (current.status === 'running') {
          await new Promise(resolve => setTimeout(resolve, 500));
          if (!alive.current || options.signal?.aborted) return;
          current = readBatch(await requestJson(path, {signal: options.signal ?? null}), mode);
        } else {
          if (current.kick_token) options.onKick?.(current.kick_token, current.reason);
          if (mode === 'pdf' && current.result?.success) {
            try { await loadFile(current.result.items.find(x => x.ok && x.download_url)?.download_url); }
            catch (failure) { setError(messageOf(failure, '下载失败，请重试下载。')); }
          }
          return;
        }
      }
    } catch (failure) {
      if (!alive.current || options.signal?.aborted) return;
      setReadFailed(true);
      setError(messageOf(failure, '批次状态暂时无法核对，请重查原批次。'));
    }
  }

  async function requestDispatch(current: BatchView, choice?: 'ipp') {
    const target = printerUri.trim();
    const override = choice ? {mode: choice, ...(target ? {printer_uri: target} : {})} : null;
    const next = readBatch(await requestJson(pathOf(current.batch_id) + '/dispatch', {
      method: 'POST', ...(override ? body(override) : {}),
    }), 'print');
    if (next.batch_id !== current.batch_id) throw new ApiError('批次编号已变化，请重查原批次。');
    return next;
  }

  async function dispatch(choice?: 'ipp') {
    if (batch?.status !== 'ready' || !visibleScope || blocked || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    setReadFailed(false);
    try { await follow(await requestDispatch(batch, choice)); }
    catch (failure) {
      setReadFailed(true);
      setError(messageOf(failure, '无法核对投递状态，请重查原批次。'));
    } finally { lock.current = false; setBusy(false); }
  }

  async function exportPrepared() {
    if (!a4Block || blocked || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      const result = await requestJson(a4Block.export_action, {method: 'POST'});
      if (!record(result) || typeof result.download_url !== 'string'
        || !/^\/api\/m03\/pdf\/[\w-]+$/.test(result.download_url)) {
        throw new ApiError('下载地址不完整，请重试导出本批 PDF。');
      }
      const exported = await loadFile(result.download_url);
      if (exported) download(exported);
    } catch (failure) {
      setError(messageOf(failure, '下载失败，请重试导出本批 PDF。'));
    } finally { lock.current = false; setBusy(false); }
  }

  async function prepare(choice: SessionChoice, token = '', frozen: PrepareScope = {
    ids: scope.map(row => row.notice_id), mode, expected_account: owner,
  }) {
    if (!alive.current || blockedRef.current || lock.current || !scope.length) return;
    lock.current = true;
    setBusy(true);
    setBatch(null);
    setKick(null);
    setError('');
    setReadFailed(false);
    clearFile();
    const generation = confirmationGeneration.current;
    const onKick = (nextToken: string, message: string) => {
      if (token || choice.mode === SESSION_MODE_BROWSER) {
        revokeI8KickToken(nextToken);
        if (alive.current) setError(message);
      } else offerKick(nextToken, message, generation, () => prepare(choice, nextToken, frozen));
    };
    try {
      const payload = sessionPayload(choice, token ? { kick_token: token } : {}, {...frozen});
      const initial = readBatch(await requestJson(batchPath + '/prepare', { method: 'POST', ...body(payload) }), mode);
      await follow(initial, {dispatchOnReady: true, onKick});
    } catch (failure) {
      const conflict = readI8KickConfirmation(failure);
      if (conflict) onKick(conflict.token, conflict.message);
      else if (alive.current) setError(messageOf(failure, '连接 i8 失败，请重试全批。'));
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
    try { await follow(batch, {reread: true}); }
    finally { lock.current = false; setBusy(false); }
  }

  function removeFailed() {
    void cancelKick();
    setScope(remaining);
    setBatch(null);
    setError('');
    clearFile();
  }

  async function retryDownload() {
    if (!result || blocked || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try { await loadFile(result.items.find(x => x.ok && x.download_url)?.download_url); }
    catch (failure) { setError(messageOf(failure, '下载失败，请重试下载。')); }
    finally { lock.current = false; setBusy(false); }
  }

  return <BusinessModal open={!blocked} className="project-dialog notice-print-dialog" titleId="notice-print-title" requestClose={closing.requestClose}>
    <DialogContents title={title} titleId="notice-print-title" closing={closing}>
      <p>本批 {batch?.total ?? scope.length} 条通知书{rows.length > 0 && '（含搜索隐藏行）'}。</p>
      {scope.length > 0 && <ReadGrid table="notice-print-list" className="notice-print-list" label="本批通知书" domLayout="autoHeight" rows={listedScope} rowId={row => String(row.notice_id)} columns={[
        { field: 'bill_no', headerName: '单据编码', ...fullTextWidth(listedScope.map(row => row.bill_no || '—')), wrapText: false, valueFormatter: p => p.value || '—' },
        { field: 'project_display', headerName: '付款项目' },
        { field: 'amount_approved', headerName: '审批金额（元）', ...numberColumnWidth(scope.map(row => row.amount_approved ? money(row.amount_approved) : '—')), cellClass: 'money', valueFormatter: p => p.value ? money(p.value) : '—' },
      ]} />}
      {(waiting || busy || batch?.status === 'running') && <div>
        <p role="status">{stageLabel[stage]}{stage !== 'connecting' && <> {completed}/{batch?.total}</>}{batch?.current_bill_no && <> · {batch.current_bill_no}</>}</p>
        {stage !== 'connecting' && <progress aria-label={stageLabel[stage]} max={batch?.total} value={completed} />}
        {waiting && <I8ConnectionWaitStatus />}
      </div>}
      {preparationFailed && <p className="notice" role="alert">
        {stageLabel[stage]}失败{batch.failed_bill_no && <> · {batch.failed_bill_no}</>}。{batch.reason} 已投递 {batch.dispatched_count} 张。
      </p>}
      {a4Block && <>
        <p className="notice" role="alert">无法确认本批按 A4 出纸。{a4Block.reason} 已投递 0 张。</p>
        {a4Block.can_switch_channel && <label>本批 IPP 地址（选填）<input
          placeholder="留空则沿用打印机设置" value={printerUri}
          disabled={busy || blocked} onChange={event => setPrinterUri(event.target.value)} /></label>}
      </>}
      {batch && deliveryStage && <section aria-label="逐张投递回执">
        {batch.reason && <p role="status">{batch.reason}</p>}
        {batch.status === 'complete' && <p role="status">
          打印机已接收 {batch.dispatched_count} / 共 {batch.total} 张。
        </p>}
        <ul>{batch.items.map(item => <li key={item.notice_id}>
          {item.bill_no}：{deliveryLabel[item.delivery_status]}
          {item.channel && <> · {channelLabel[item.channel] ?? item.channel}</>}
          {item.job_id !== null && <> · 作业号 {item.job_id}</>}
          {item.delivery_status === 'unknown' && <p>{item.reason || '请先核对打印机作业和出纸情况，勿盲目重打。'}</p>}
          {item.attempts.length > 0 && <ul>{item.attempts.map((attempt, index) => <li key={index}>
            {channelLabel[attempt.channel] ?? attempt.channel} · {deliveryLabel[attempt.status]}
            {attempt.job_id !== null && <> · 作业号 {attempt.job_id}</>} · {attempt.reason}
          </li>)}</ul>}
        </li>)}</ul>
      </section>}
      {result && mode === 'pdf' && <section aria-label="执行回执">
        <p role="status">已生成 {result.success} / 共 {result.total} 条，未完成 {result.failed} 条。</p>
        <ul>{result.items.map(item => <li key={item.notice_id} className={!item.ok ? 'notice' : ''}>
          {item.bill_no || item.notice_id}：{item.ok ? '已生成' : '未完成'}
          {item.reason && <>，{item.reason}</>}
        </li>)}</ul>
      </section>}
      {error && <p className="notice" role="alert">{error}</p>}
      {kick && <p className="notice" role="status">{kick.message}</p>}
      <div role="status" className={revocationNotice ? 'notice' : undefined}>{revocationNotice}</div>
      {file?.pdf && <><p><a href={file.url} target="_blank" rel="noreferrer">在新窗口预览 PDF</a></p>
        <iframe className="notice-pdf-preview" title="付款通知书 PDF 预览" src={file.url} /></>}
      <div className="dialog-actions">
        <Link to="/i8" onClick={event => { if (closeLocked) event.preventDefault(); else closing.requestClose(); }}>查看运行记录</Link>
        <Button htmlType="button" disabled={closeLocked} onClick={closing.requestClose}>关闭</Button>
        {waiting && <Button htmlType="button" onClick={cancelWaiting}>取消等待</Button>}
        {!busy && !waiting && kick && session.mode !== SESSION_MODE_BROWSER && <>
          <Button htmlType="button" onClick={() => void cancelKick()}>取消下线确认</Button>
          <Button htmlType="button" type="primary" disabled={blocked} onClick={confirmKick}>让现有会话下线并继续</Button>
        </>}
        {!busy && !waiting && !kick && scope.length > 0 && (!batch || preparationFailed) &&
          <Button htmlType="button" type="primary" disabled={blocked} onClick={() => void runWhenReady(prepare)}>
            {preparationFailed || error ? '重试全批' : '确认本批'}
          </Button>}
        {preparationFailed && failedIds.size > 0 && remaining.length > 0 &&
          <Button htmlType="button" disabled={busy || blocked} onClick={removeFailed}>移出异常单并重新确认剩余批次</Button>}
        {readFailed && <Button htmlType="button" disabled={busy || blocked} onClick={() => void recheck()}>重查原批次</Button>}
        {batch?.status === 'ready' && visibleScope && !a4Block && !readFailed && !busy &&
          <Button htmlType="button" type="primary" disabled={blocked} onClick={() => void dispatch()}>投递原批</Button>}
        {a4Block && !readFailed && <>
          {a4Block.can_switch_channel && <Button htmlType="button" disabled={busy || blocked || !visibleScope}
            onClick={() => void dispatch('ipp')}>切换支持 A4 的通道（IPP）</Button>}
          <Button htmlType="button" type="primary" disabled={busy || blocked}
            onClick={() => void exportPrepared()}>导出本批 PDF</Button>
        </>}
        {file && <Button htmlType="button" type="primary" disabled={busy || blocked} onClick={() => download(file)}>下载 {file.filename}</Button>}
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
    <p>批量打印会先用 IPP 确认设备接受 A4。系统驱动和 RAW 目前无法为打印作业指定 A4。</p>
    <label>打印机名<input list="notice-printer-names" value={printer.printer_name} onChange={e=>setPrinter({...printer,printer_name:e.target.value})} /></label><datalist id="notice-printer-names">{names.map(n=><option key={n} value={n}/>)}</datalist>{!names.length&&<p>未取到本机打印机名，可手动填写。</p>}
    {layouts.map(item=><div key={item.key}><label>{item.label}<input value={item.stored} placeholder={item.env} onChange={e=>setLayouts(old=>old.map(x=>x.key===item.key?{...x,stored:e.target.value}:x))}/></label><p>{plain(item.hint)}</p><p className="mut">当前生效：{item.effective||'未设置'}，{item.stored?'本处所设；清空并保存后使用默认值':'默认值'}</p></div>)}</>}
    {error&&<p className="notice" role="alert">{error}<Button htmlType="submit" disabled={busy} onClick={()=>void load()}>重读设置</Button></p>}{feedback&&<p role="status">{feedback}</p>}
    <div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>取消</Button><Button htmlType="submit" className="primary" disabled={busy||blocked||!printer} onClick={()=>void save()}>{busy?'正在保存…':'保存'}</Button></div>
  </DialogContents></BusinessModal>;
}
