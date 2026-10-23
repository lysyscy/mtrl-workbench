import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Tag from 'antd/es/tag';
import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, record, requestJson } from './api';
import type { Identity } from './api';
import { BusinessModal } from './business-modal';
import { BoundedTable } from './bounded-table';
import { DialogContents, useDialogClose } from './dialog-close';
import { contractWrite } from './contracts-api';
import { receipt } from './notices-api';

interface ToolProps { me:Identity|null;blocked:boolean;close:()=>void;refresh:()=>Promise<void> }
export function ContractFetch({me,blocked,close,refresh}:ToolProps) {
  const [since,setSince]=useState(''),[all,setAll]=useState(false),[busy,setBusy]=useState(false),[done,setDone]=useState(false),[result,setResult]=useState(''),[error,setError]=useState('');
  const [summary,setSummary]=useState<{label:string;count:number}[]>([]),[details,setDetails]=useState<{name:string;count:number}[]>([]);
  const lock=useRef(false),closing=useDialogClose({busy,dirty:!done&&Boolean(since||all),close,active:!blocked});
  const config=useQuery({queryKey:['contract-fetch-config'],enabled:!blocked,staleTime:0,refetchOnMount:'always',queryFn:async({signal})=>{
    const value=await requestJson('/api/m02/config',{signal});
    if(!record(value)||typeof value.ready!=='boolean'||typeof value.account!=='string'||typeof value.i8_user!=='string'||typeof value.message!=='string')throw new ApiError('i8绑定读取不完整，请重读。');
    return {ready:value.ready,account:value.account,i8_user:value.i8_user,message:value.message};
  }});
  async function run(){
    if(blocked||!me||busy||done||lock.current||!config.data?.ready||config.data.account!==me.account)return;
    lock.current=true;setBusy(true);setDone(true);setError('');
    try{
      const value=await contractWrite('/api/m11/fetch',{confirm:true,...(all?{since:''}:since?{since}:{})});
      if(!record(value)||value.ok!==true||typeof value.message!=='string'||!['fetched','matched','unmatched','ignored','material_blank'].every(k=>typeof value[k]==='number')||!Array.isArray(value.unmatched_projects)||!value.unmatched_projects.every(x=>record(x)&&typeof x.name==='string'&&typeof x.count==='number'))throw new ApiError('抓取回执不完整，请到执行记录核对，勿重复抓取。');
      setResult(value.message);setSummary([['抓取',value.fetched],['已匹配',value.matched],['未写入',value.unmatched],['忽略',value.ignored],['材料名未补齐',value.material_blank]].map(([label,count])=>({label:String(label),count:Number(count)})));setDetails(value.unmatched_projects as {name:string;count:number}[]);
    }catch(failure){setError(`抓取结果请在执行记录核对，勿重复抓取。${failure instanceof Error?failure.message:''}`);}
    finally{try{await refresh();}catch{setError(old=>`${old} 列表或执行记录更新失败，请关闭后重读核对。`);}lock.current=false;setBusy(false);}
  }
  return <BusinessModal open={!blocked} className={`project-dialog contract-fetch${closing.confirming?' contract-tool-discard':''}`} titleId="contract-fetch-title" requestClose={closing.requestClose}><DialogContents title="抓取采购合同" titleId="contract-fetch-title" closing={closing}>
    {config.isPending?<p role="status">正在核对 i8 绑定…</p>:config.isError?<p className="notice" role="alert">{config.error.message}<Button onClick={()=>void config.refetch()}>重读绑定</Button></p>:<p>当前账号：{me?.name||me?.account} · i8：{config.data.i8_user||'未绑定'}</p>}
    {!done&&<><label className="contract-field">抓取范围<Select aria-label="合同抓取范围" value={all?'all':'incremental'} disabled={busy} options={[{value:'incremental',label:'增量 / 指定起点'},{value:'all',label:'全部合同'}]} onChange={value=>setAll(value==='all')}/></label>{!all&&<label className="contract-field">合同日期起点（留空按现有合同增量）<Input type="date" value={since} onChange={e=>setSince(e.target.value)}/></label>}<p>抓取会退出此 i8 账号的其他在线会话。保留人工标记、材料名、账期、付款方式和备注；未完成归属的合同不写入。</p></>}
    {config.data&&(!config.data.ready||config.data.account!==me?.account)&&<p role="alert">{config.data.message||'账号已变化，请关闭后重新打开。'}</p>}
    {result&&<p role="status">{result}</p>}{summary.length>0&&<div className="contract-fetch-summary">{summary.map(x=><span key={x.label}>{x.label} {x.count} 条</span>)}</div>}{details.length>0&&<div className="contract-unmatched"><h3>未写入项目</h3><ul>{details.map((x,i)=><li key={i}>{x.name} · {x.count} 条</li>)}</ul></div>}
    {error&&<p className="notice" role="alert">{error}</p>}{busy&&<p role="status">正在抓取，请稍候…</p>}<div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>{done?'关闭':'取消'}</Button>{!done&&<Button className="primary" disabled={busy||blocked||!me||config.isFetching||!config.data?.ready||config.data.account!==me.account} onClick={()=>void run()}>确认抓取</Button>}</div>
  </DialogContents></BusinessModal>;
}
interface Party {name:string;kind:string;kind_name:string;count:number}
interface Ignored {id:number;name_full:string;reason:string;operator:string;active:boolean}
interface Settings {parties:Party[];ignored:Ignored[];kinds:string[];names:Record<string,string>}
export function ContractSettings({kind,me,blocked,close,refresh}:ToolProps&{kind:'party'|'ignore'}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[feedback,setFeedback]=useState(''),[unknown,setUnknown]=useState(false),[name,setName]=useState(''),[reason,setReason]=useState('');
  const [drafts,setDrafts]=useState<Record<string,string>>({});
  const lock=useRef(false),closing=useDialogClose({busy,dirty:Boolean(name||reason||Object.keys(drafts).length),close,active:!blocked});
  const query=useQuery({queryKey:['contract-settings',kind],enabled:!blocked,staleTime:0,refetchOnMount:'always',queryFn:async({signal}):Promise<Settings>=>{
    const value=await requestJson(kind==='party'?'/api/m11/party-kinds':'/api/m14/jc-ignore',{signal});
    if(!record(value)||!Array.isArray(value.items))throw new ApiError('清单读取不完整，请重读。');
    if(kind==='party'){
      if(!value.items.every(x=>record(x)&&typeof x.name==='string'&&typeof x.kind==='string'&&typeof x.kind_name==='string'&&typeof x.count==='number')||!Array.isArray(value.kinds)||!value.kinds.every(x=>typeof x==='string')||!record(value.kind_names)||!Object.values(value.kind_names).every(x=>typeof x==='string'))throw new ApiError('甲方分类读取不完整，请重读。');
      return {parties:value.items as Party[],ignored:[],kinds:value.kinds as string[],names:value.kind_names as Record<string,string>};
    }
    if(!value.items.every(x=>record(x)&&Number.isSafeInteger(x.id)&&typeof x.name_full==='string'&&typeof x.reason==='string'&&typeof x.operator==='string'&&typeof x.active==='boolean'))throw new ApiError('忽略名单读取不完整，请重读。');
    return {parties:[],ignored:value.items as Ignored[],kinds:[],names:{}};
  }});
  async function write(path:string,payload:unknown,method='POST',accepted?:()=>void){
    if(busy||blocked||!me||unknown||lock.current)return;
    lock.current=true;setBusy(true);setError('');setFeedback('');let written=false;
    try{const result=await contractWrite(path,payload,method);written=true;accepted?.();setFeedback(receipt(result));await query.refetch({throwOnError:true});await refresh();}
    catch(failure){setUnknown(true);setError(`${written?'已保存，重读失败。':'结果待核实。'}${failure instanceof Error?failure.message:''}请重读核对，勿重复操作。`);}
    finally{lock.current=false;setBusy(false);}
  }
  async function reread(){if(busy||blocked)return;setBusy(true);try{await query.refetch({throwOnError:true});await refresh();setUnknown(false);setError('');setFeedback('已重读，请核对清单。');}catch(failure){setError(failure instanceof Error?failure.message:'重读失败。');}finally{setBusy(false);}}
  const unavailable=busy||blocked||!me||unknown||query.isPending||query.isError;
  return <BusinessModal open={!blocked} className={`project-dialog contract-settings${closing.confirming?' contract-tool-discard':''}`} titleId="contract-settings-title" requestClose={closing.requestClose}><DialogContents title={kind==='party'?'甲方单位分类':'集采项目忽略名单'} titleId="contract-settings-title" closing={closing}>
    <p>{kind==='party'?'分类决定下次抓取时合同金额的落列；修改分类不重算已有合同。':'仅影响以后抓取。停用后项目可再次抓取，已保存的合同不删除。'}</p>
    {query.isPending?<p role="status">正在读取清单…</p>:query.isError?<p className="notice" role="alert">{query.error.message}</p>:query.data&&<div className="contract-settings-table"><BoundedTable columns={kind==='party'?[{min:14,max:34,flex:1},{min:6,max:8},{min:10,max:16},{min:5,max:7}]:[{min:14,max:32,flex:1},{min:12,max:28,flex:1},{min:7,max:10},{min:7,max:10}]}><thead><tr>{(kind==='party'?['甲方单位','合同数','分类','操作']:['项目全称','原因','状态','操作']).map(label=><th key={label}>{label}</th>)}</tr></thead><tbody>{kind==='party'?query.data.parties.map(item=><tr key={item.name}><td>{item.name}</td><td>{item.count}</td><td><Select aria-label={`${item.name}分类`} value={drafts[item.name]??item.kind} disabled={unavailable} options={query.data!.kinds.map(value=>({value,label:query.data!.names[value]||value}))} onChange={value=>setDrafts(old=>{const next={...old};if(value===item.kind)delete next[item.name];else next[item.name]=value;return next;})}/></td><td><Button size="small" disabled={unavailable||!drafts[item.name]} onClick={()=>void write('/api/m11/party-kind',{name:item.name,kind:drafts[item.name]},'POST',()=>setDrafts(old=>{const next={...old};delete next[item.name];return next;}))}>保存</Button></td></tr>):query.data.ignored.map(item=><tr key={item.id}><td>{item.name_full}</td><td>{item.reason||'—'}</td><td><Tag className={`enum-tag ${item.active?'status-pending':'status-neutral'}`}>{item.active?'正在忽略':'已停用'}</Tag></td><td><Button size="small" disabled={unavailable} onClick={()=>void write(`/api/m14/jc-ignore/${item.id}`,{active:!item.active},'PUT')}>{item.active?'停用忽略':'恢复忽略'}</Button></td></tr>)}</tbody></BoundedTable>{(kind==='party'?!query.data.parties.length:!query.data.ignored.length)&&<p className="state">清单为空</p>}</div>}
    {kind==='ignore'&&<form className="contract-ignore-add" onSubmit={e=>{e.preventDefault();if(name.trim())void write('/api/m14/jc-ignore',{name_full:name,reason},'POST',()=>{setName('');setReason('');});}}><label>项目全称<Input value={name} disabled={unavailable} onChange={e=>setName(e.target.value)}/></label><label>忽略原因<Input value={reason} disabled={unavailable} onChange={e=>setReason(e.target.value)}/></label><Button htmlType="submit" disabled={unavailable||!name.trim()}>加入名单</Button></form>}
    {feedback&&<p role="status">{feedback}</p>}{error&&<p className="notice" role="alert">{error}</p>}<div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button disabled={busy||blocked} onClick={()=>void reread()}>重读清单</Button></div>
  </DialogContents></BusinessModal>;
}
