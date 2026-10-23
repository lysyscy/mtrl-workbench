import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import { useEffect, useRef, useState } from 'react';
import type { Project } from './api';
import { requestFile } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { tabLabels } from './process-api';

export function ProcessExport({projects,current,tab,paused,reason}:{projects:Project[];current:string;tab:number;paused:boolean;reason:string}) {
  const [open,setOpen]=useState(false),[selected,setSelected]=useState<string[]|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const trigger=useRef<HTMLButtonElement>(null),request=useRef<AbortController|null>(null),lock=useRef(false);
  const chosen=(selected??[current]).filter(key=>projects.some(p=>p.warehouse_name===key));
  const state=useRef({paused,reason,tab});state.current={paused,reason,tab};
  const close=()=>{setOpen(false);requestAnimationFrame(()=>trigger.current?.focus());};
  const closing=useDialogClose({busy,dirty:false,close,active:open&&!paused});
  useEffect(()=>{if(paused){request.current?.abort();setOpen(false);}},[paused]);
  useEffect(()=>()=>request.current?.abort(),[]);
  async function download() {
    if(lock.current || paused || reason || !chosen.length) return;
    lock.current=true;setBusy(true);setError('');const controller=new AbortController();request.current=controller;
    try {
      const file=await requestFile(`/api/m06/export?${new URLSearchParams({projects:chosen.join(','),tab:String(tab)})}`,controller.signal);
      if(controller.signal.aborted || state.current.paused || state.current.reason || state.current.tab!==tab) return;
      const url=URL.createObjectURL(file.blob),link=document.createElement('a');link.href=url;link.download=file.filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);close();
    }catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'导出失败，请重试。');}
    finally{lock.current=false;setBusy(false);}
  }
  return <><Button ref={trigger} type="primary" disabled={paused||Boolean(reason)||!projects.length} title={reason} onClick={()=>{setOpen(true);setError('');}}>导出文件…</Button>
    {open&&<BusinessModal open={!paused} titleId="process-export-title" requestClose={closing.requestClose} className="process-export-dialog"><DialogContents title={`导出 · ${tabLabels[tab]}`} titleId="process-export-title" closing={closing}>
      <p>每项目一本工作簿，多个项目打包为 ZIP。{tab===2?'差异导出按月逐列列示调整后与原始的差额。':''}</p>
      <div className="process-export-tools"><Button disabled={busy} onClick={()=>setSelected(projects.map(p=>p.warehouse_name!))}>全选</Button><Button disabled={busy} onClick={()=>setSelected([])}>清空</Button><span>已选 {chosen.length} 个项目</span></div>
      <div className="process-export-projects">{projects.map(p=><Checkbox key={p.id} disabled={busy} checked={chosen.includes(p.warehouse_name!)} onChange={e=>setSelected(e.target.checked?[...chosen,p.warehouse_name!]:chosen.filter(k=>k!==p.warehouse_name))}>{p.disp}</Checkbox>)}</div>
      {(reason||error)&&<p role="alert" className="notice">{reason||error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" loading={busy} disabled={paused||Boolean(reason)||!chosen.length} onClick={()=>void download()}>保存到本地</Button></div>
    </DialogContents></BusinessModal>}
  </>;
}
