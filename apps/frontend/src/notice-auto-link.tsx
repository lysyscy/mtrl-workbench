import Button from 'antd/es/button';
import { BusinessModal } from './business-modal';
import { BoundedTable } from './bounded-table';
import { useRef, useState } from 'react';
import { ApiError, record, requestJson } from './api';
import { body, money } from './notices-api';
import { DialogContents, useDialogClose } from './dialog-close';
interface AutoRow { notice_id:number; code:string; contract_id:number|null; contract_no?:string; amount?:string; payable_codes?:string[]; reason:string }
function readRows(value:unknown):AutoRow[] {
  if(!record(value)||!Array.isArray(value.rows)||!value.rows.every(r=>record(r)&&Number.isSafeInteger(r.notice_id)&&typeof r.code==='string'&&typeof r.reason==='string'&&(r.contract_id===null||Number.isSafeInteger(r.contract_id)&&typeof r.contract_no==='string'&&typeof r.amount==='string'&&Array.isArray(r.payable_codes)&&r.payable_codes.every(c=>typeof c==='string'))))throw new ApiError('关联回执不完整，请重新读取核对。');
  return value.rows as AutoRow[];
}
export function AutoLinkDialog({ids,blocked,close,refresh,announce}:{ids:number[];blocked:boolean;close:()=>void;refresh:()=>Promise<void>;announce:(message:string)=>void}) {
  const lock=useRef(false);
  const [rows,setRows]=useState<AutoRow[]|null>(null),[busy,setBusy]=useState(false),[done,setDone]=useState(false),[error,setError]=useState('');
  const closing = useDialogClose({ busy, dirty: false, close });
  const ready=rows?.filter(r=>r.contract_id!==null).length??0;
  async function run(confirm:boolean){
    if(blocked||busy||done||lock.current||confirm&&!ready)return;
    lock.current=true;setBusy(true);setError('');let saved=false;
    try{
      const selections=(rows??[]).filter(r=>r.contract_id!==null).map(({notice_id,contract_id,amount,payable_codes})=>({notice_id,contract_id,amount,payable_codes}));
      const result=await requestJson(confirm?'/api/m11/auto-link':'/api/m11/auto-link-preview',{method:'POST',...body({notice_ids:ids,...(confirm?{selections}:{})})});
      saved=confirm;if(confirm)setDone(true);
      setRows(readRows(result));
      if(confirm){if(!record(result)||!Number.isSafeInteger(result.linked))throw new ApiError('关联数量读取不完整，请重读列表核对。');announce(`已关联 ${result.linked} 条；未关联的请人工核对。`);await refresh();}
    }catch(failure){setError(`${saved?'操作已完成，读取尚待核对，勿重复确认。':''}${failure instanceof Error?failure.message:'操作失败，请重试。'}`);}
    finally{setBusy(false);lock.current=false;}
  }
  return <BusinessModal open={!blocked} className="project-dialog notice-dialog notice-contract-dialog" titleId="auto-link-title" requestClose={closing.requestClose}><DialogContents title="一键关联集采合同" titleId="auto-link-title" closing={closing}><p>读取采购合同应付；只补当前列表中未关联的通知书，已有合同保持。将登录 i8，在线冲突停止。</p>{rows&&<><p>可关联 {ready} 条，其余保留人工处理。</p><div className="table-scroll"><BoundedTable columns={[{ min: 12, max: 16 },{ min: 12, max: 32, flex: 1 },{ min: 10, max: 28, flex: 1 }]}><thead><tr><th>通知书</th><th>合同／处理结果</th><th>采购应付依据</th></tr></thead><tbody>{rows.map(r=><tr key={r.notice_id}><td>{r.code}</td><td>{r.contract_no||r.reason}{r.amount&&<div>{money(r.amount)} 元</div>}{r.contract_no&&<p>{r.reason}</p>}</td><td>{r.payable_codes?.join('、')}</td></tr>)}</tbody></BoundedTable></div></>}{error&&<p className="notice" role="alert">{error}</p>}{busy&&<p role="status">正在核对…</p>}<div className="dialog-actions"><Button htmlType="submit" disabled={busy} onClick={closing.requestClose}>{done?'关闭':'取消'}</Button>{!done&&<Button htmlType="submit" className="primary" disabled={blocked||busy||!ids.length||rows!==null&&!ready} onClick={()=>void run(rows!==null)}>{rows===null?'确认读取并预览':`关联这 ${ready} 条`}</Button>}</div></DialogContents></BusinessModal>;
}
