import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { ReadGrid } from './business-grid';
import { useRef, useState } from 'react';
import { ApiError, record, requestJson } from './api';
import { body, money } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';
import { SESSION_MODE_BROWSER, sessionPayload } from './i8-browser-relay';
import { useI8Session } from './i8-session';
interface AutoRow { notice_id:number; code:string; contract_id:number|null; contract_no?:string; amount?:string; payable_codes?:string[]; reason:string }
function readRows(value:unknown):AutoRow[] {
  if(!record(value)||!Array.isArray(value.rows)||!value.rows.every(r=>record(r)&&Number.isSafeInteger(r.notice_id)&&typeof r.code==='string'&&typeof r.reason==='string'&&(r.contract_id===null||Number.isSafeInteger(r.contract_id)&&typeof r.contract_no==='string'&&typeof r.amount==='string'&&Array.isArray(r.payable_codes)&&r.payable_codes.every(c=>typeof c==='string'))))throw new ApiError('关联回执不完整，请重新读取核对。');
  return value.rows as AutoRow[];
}
export function AutoLinkDialog({ids,blocked,close,refresh,announce}:{ids:number[];blocked:boolean;close:()=>void;refresh:()=>Promise<void>;announce:(message:string,needsAttention?:boolean)=>void}) {
  const lock=useRef(false);
  // 取数方式来自账号工作区的统一选择（「i8 接入」页）。
  const session=useI8Session();
  const browserBlocked=session.mode===SESSION_MODE_BROWSER&&!session.connected;
  const [rows,setRows]=useState<AutoRow[]|null>(null),[busy,setBusy]=useState(false),[done,setDone]=useState(false),[error,setError]=useState('');
  const closing = useDialogClose({ busy, dirty: false, close });
  const ready=rows?.filter(r=>r.contract_id!==null).length??0;
  async function run(confirm:boolean){
    if(blocked||busy||done||lock.current||browserBlocked||confirm&&!ready)return;
    lock.current=true;setBusy(true);setError('');let saved=false;
    try{
      const selections=(rows??[]).filter(r=>r.contract_id!==null).map(({notice_id,contract_id,amount,payable_codes})=>({notice_id,contract_id,amount,payable_codes}));
      // 会话来源字段统一由 `sessionPayload` 生成：`browser` 连接不在就当场失败（不退回登录），
      // `http` 保留原来的强踢授权（读取合同应付确实可能顶号，保持既有行为）。
      const mode=sessionPayload(session,{allow_kick:true});
      const result=await requestJson(confirm?'/api/m11/auto-link':'/api/m11/auto-link-preview',{method:'POST',...body({notice_ids:ids,...mode,...(confirm?{selections}:{})})});
      saved=confirm;if(confirm)setDone(true);
      const results=readRows(result);setRows(results);
      if(confirm){if(!record(result)||!Number.isSafeInteger(result.linked))throw new ApiError('关联数量读取不完整，请重读列表核对。');const remaining=ids.length-results.filter(row=>row.contract_id!==null).length;await refresh();announce(`已关联 ${result.linked} 条${remaining?`；${remaining} 条未关联，请核对结果。`:''}`,remaining>0);}
    }catch(failure){setError(`${saved?'操作已完成，读取尚待核对，勿重复确认。':''}${failure instanceof Error?failure.message:'操作失败，请重试。'}`);}
    finally{setBusy(false);lock.current=false;}
  }
  return <BusinessModal open={!blocked} className="project-dialog notice-dialog notice-contract-dialog notice-result-dialog" titleId="auto-link-title" requestClose={closing.requestClose}><DialogContents title="一键关联集采合同" titleId="auto-link-title" closing={closing}><p>读取采购合同应付；只补当前列表中未关联的通知书，已有合同保持。{session.mode===SESSION_MODE_BROWSER?'本次读取由你浏览器里已登录的 i8 标签发出：不登录、不顶号；连接失效时会明确停止。':'读取可能重新登录 i8，并使该账号其他会话下线。'}</p>{rows&&<><p>可关联 {ready} 条，其余保留人工处理。</p><ReadGrid manualWidths table="notice-auto-link" className="notice-result-grid" label="关联预览与结果" domLayout="autoHeight" rows={rows} rowId={row=>String(row.notice_id)} columns={[
      {field:'code',headerName:'通知书'},
      {colId:'result',headerName:'合同／处理结果',cellRenderer:({data:r}:{data:AutoRow})=><>{r.contract_no||r.reason}{r.amount&&<div>{money(r.amount)} 元</div>}{r.contract_no&&<p>{r.reason}</p>}</>},
      {colId:'basis',headerName:'采购应付依据',valueGetter:p=>p.data?.payable_codes?.join('、')??''},
    ]}/></>}{error&&<p className="notice" role="alert">{error}</p>}{busy&&<p role="status">正在核对…</p>}<div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>{done?'关闭':'取消'}</Button>{!done&&<Button htmlType="submit" className="primary" disabled={blocked||busy||browserBlocked||!ids.length||rows!==null&&!ready} onClick={()=>void run(rows!==null)}>{rows===null?'确认读取并预览':`关联这 ${ready} 条`}</Button>}</div></DialogContents></BusinessModal>;
}
