import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { BoundedGrid } from './bounded-grid';
import { useRef, useState } from 'react';
import { ApiError, record, requestJson, uncertainWrite } from './api';
import { body, money } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';
import { SESSION_MODE_BROWSER, sessionPayload } from './i8-browser-relay';
import type { SessionChoice } from './i8-browser-relay';
import { I8ConnectionWaitStatus, useI8ActionWait, useI8Session } from './i8-session';
import { I8KickConfirmationActions, useI8KickConfirmation } from './i8-kick-confirmation';
interface AutoRow { notice_id:number; code:string; contract_id:number|null; contract_no?:string; amount?:string; payable_codes?:string[]; reason:string }
function readRows(value:unknown, expectedIds:number[]):AutoRow[] {
  if(!record(value)||!Array.isArray(value.rows)||!value.rows.every(r=>record(r)&&Number.isSafeInteger(r.notice_id)&&typeof r.code==='string'&&typeof r.reason==='string'&&(r.contract_id===null||Number.isSafeInteger(r.contract_id)&&typeof r.contract_no==='string'&&typeof r.amount==='string'&&Array.isArray(r.payable_codes)&&r.payable_codes.every(c=>typeof c==='string'))))throw new ApiError('关联回执不完整，请重新读取核对。');
  const pending = new Set(expectedIds);
  if (!value.rows.every(row => pending.delete(row.notice_id)) || pending.size) {
    throw new ApiError('关联回执与本次通知书不一致。');
  }
  return value.rows as AutoRow[];
}
export function AutoLinkDialog({ids,blocked,close,refresh,announce}:{ids:number[];blocked:boolean;close:()=>void;refresh:()=>Promise<void>;announce:(message:string,needsAttention?:boolean)=>void}) {
  const lock=useRef(false);
  // 取数方式来自账号工作区的统一选择（「i8 接入」页）。
  const session=useI8Session();
  const [rows,setRows]=useState<AutoRow[]|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [completion, setCompletion] = useState<{summary: string} | 'unknown' | null>(null);
  const scopeKey = JSON.stringify([ids, rows !== null, session.mode, blocked]);
  const {waiting, cancelWaiting, runWhenReady} = useI8ActionWait(scopeKey);
  const kick = useI8KickConfirmation(scopeKey);
  const closing = useDialogClose({ busy, dirty: false, close: () => { cancelWaiting(); kick.dismiss(); close(); } });
  const ready=rows?.filter(r=>r.contract_id!==null).length??0;
  async function run(choice: SessionChoice, kickToken?:string){
    const confirm = rows !== null;
    if(blocked||busy||completion||lock.current||confirm&&!ready||!kickToken&&kick.message)return;
    lock.current=true;setBusy(true);setError('');
    let verifiedSummary = '';
    try{
      const selections=(rows??[]).filter(r=>r.contract_id!==null).map(({notice_id,contract_id,amount,payable_codes})=>({notice_id,contract_id,amount,payable_codes}));
      const mode=sessionPayload(choice,kickToken?{kick_token:kickToken}:{});
      const result=await requestJson(confirm?'/api/m11/auto-link':'/api/m11/auto-link-preview',{method:'POST',...body({notice_ids:ids,...mode,...(confirm?{selections}:{})})});
      if (!confirm) {
        setRows(readRows(result, ids));
        return;
      }
      const results = readRows(result, selections.map(row => row.notice_id));
      if (!record(result) || typeof result.linked !== 'number' || !Number.isSafeInteger(result.linked)
        || result.linked < 0 || result.linked > results.filter(row => row.contract_id !== null).length) {
        throw new ApiError('关联数量读取不完整。');
      }
      const byId = new Map(results.map(row => [row.notice_id, row]));
      setRows(rows.map(row => byId.get(row.notice_id) ?? row));
      verifiedSummary = `本次已关联 ${result.linked} 条，跳过 ${rows.length - result.linked} 条。`;
      setCompletion({summary: verifiedSummary});
      await refresh();
      announce(verifiedSummary);
    }catch(failure){
      if(!kickToken&&!verifiedSummary&&kick.offer(failure,token=>run(choice,token)))return;
      const detail = failure instanceof Error ? failure.message : '操作失败，请重试。';
      if (confirm && (verifiedSummary || uncertainWrite(failure))) {
        if (!verifiedSummary) setCompletion('unknown');
        const warning = `${verifiedSummary || '关联结果待核对。'}请重读列表核对，勿重复确认。${detail}`;
        setError(warning);
        announce(warning, true);
      } else {
        setError(detail);
      }
    }
    finally{setBusy(false);lock.current=false;}
  }
  const summary = completion === 'unknown' ? '以下为确认前的预览。'
    : completion?.summary ?? `可关联 ${ready} 条，其余保留人工处理。`;
  return <BusinessModal open={!blocked} layout="pane" className="project-dialog notice-dialog notice-contract-dialog notice-result-dialog" titleId="auto-link-title" requestClose={closing.requestClose}><DialogContents title="一键关联集采合同" titleId="auto-link-title" closing={closing}><p>读取采购合同应付；只补当前列表中未关联的通知书，已有合同保持。{session.mode===SESSION_MODE_BROWSER?'本次读取由你浏览器里已登录的 i8 标签发出：不登录、不顶号；连接失效时会明确停止。':'工作台直连遇到在线冲突时，需要另行确认是否让现有会话下线。'}</p>{waiting && <I8ConnectionWaitStatus />}{rows&&<><p>{summary}</p><BoundedGrid fill minRows={4} table="notice-auto-link" className="notice-result-grid" label="关联预览与结果" rows={rows} rowId={row=>String(row.notice_id)} columns={[
      {field:'code',headerName:'通知书'},
      {colId:'result',headerName:'合同／处理结果',cellRenderer:({data:r}:{data:AutoRow})=><>{r.contract_no||r.reason}{r.amount&&<div>{money(r.amount)} 元</div>}{r.contract_no&&<p>{r.reason}</p>}</>},
      {colId:'basis',headerName:'采购应付／关联依据',valueGetter:p=>p.data?.payable_codes?.join('、')??''},
    ]}/></>}{error&&<p className="notice" role="alert">{error}</p>}{busy&&<p role="status">正在核对…</p>}
    <div role="status" className={kick.revocationNotice ? 'notice' : undefined}>{kick.revocationNotice}</div>
    {kick.message?<I8KickConfirmationActions {...kick} disabled={blocked||busy||waiting}/>:<div className="dialog-actions"><Button htmlType="button" disabled={busy} onClick={closing.requestClose}>{completion?'关闭':'取消'}</Button>{waiting && <Button htmlType="button" onClick={cancelWaiting}>取消等待</Button>}{!completion&&<Button htmlType="submit" className="primary" disabled={blocked||busy||waiting||!ids.length||rows!==null&&!ready} onClick={() => void runWhenReady(run)}>{rows===null?'确认读取并预览':`关联这 ${ready} 条`}</Button>}</div>}</DialogContents></BusinessModal>;
}
