import { ApiError, record, requestJson } from './api';
import { body, cents } from './notices-api';

export const categories = ['主辅材','工具','劳保','周转材料','临时设施'];
export const mechLabels = ['租分公司设备','内租设备','外租零租含税','外租包月含税','外租零租不含税','外租包月不含税'];
export const mechKeys = mechLabels.map((_, i) => `mech_${i}`);
export const materialKeys = ['in','out'].flatMap(direction => categories.map(name => `${direction}_${name}`));
export const dataKeys = [...materialKeys,...mechKeys];
export const tabLabels = ['表① 原始表','表② 调整后表','差异表'];
export type Amounts = Record<string,string|null>;
export type ProcessRow = Amounts & { ym:string };
export interface Difference { id:number; doc_no:string; seq:string; material:string; warehouse:string; before:string|null; after:string|null; delta:string|null; remark:string; operator:string; at:string }
export interface Matrix { raw:ProcessRow[]; adjusted:ProcessRow[]; totals:{raw:Amounts;adjusted:Amounts}; segments:{raw:{name:string;total:string|null}[];adjusted:{name:string;total:string|null}[]}; diffs:Difference[]; diff_totals:Amounts }
export interface ProcessData { projects:string[]; matrices:Record<string,Matrix>; sources:Record<string,Record<string,Record<string,{mode:string}>>>; signatures:Record<string,Record<string,string>> }
const invalid = () => new ApiError('过程资料读取不完整，请重读。');
function amount(value:unknown):string|null {
  if (value === null) return null;
  if (typeof value !== 'string' && typeof value !== 'number') throw invalid();
  const text=String(value); cents(text); return text;
}
function amounts(value:unknown,keys=dataKeys):Amounts {
  if(!record(value)) throw invalid();
  return Object.fromEntries(keys.map(key => [key,amount(value[key])]));
}
function rows(value:unknown):ProcessRow[] {
  if(!Array.isArray(value)) throw invalid();
  const result=value.map(row => {
    if(!record(row) || typeof row.ym !== 'string' || !/^\d{4}-(0[1-9]|1[0-2])$/.test(row.ym)) throw invalid();
    return {...amounts(row),ym:row.ym};
  });
  if(new Set(result.map(r=>r.ym)).size!==result.length) throw invalid();
  return result;
}
export function readProcess(value:unknown,mechanical:unknown):ProcessData {
  if(!record(value) || value.ok!==true || !Array.isArray(value.projects) || !value.projects.every(p=>typeof p==='string') || !record(value.matrices) || !record(mechanical) || !record(mechanical.sources) || !record(mechanical.effective_signatures)) throw invalid();
  const matrices:Record<string,Matrix>={};
  for(const warehouse of value.projects as string[]) {
    const m=value.matrices[warehouse];
    if(!record(m) || !record(m.totals) || !record(m.segments) || !Array.isArray(m.diffs)) throw invalid();
    const raw=rows(m.raw),adjusted=rows(m.adjusted);
    if(raw.length!==adjusted.length || raw.some((r,i)=>r.ym!==adjusted[i]?.ym)) throw invalid();
    function segments(value:unknown) {
      if(!Array.isArray(value) || value.length!==4) throw invalid();
      return value.map(s=>{if(!record(s) || typeof s.name!=='string') throw invalid();return {name:s.name,total:amount(s.total)};});
    }
    const diffs=m.diffs.map((d:unknown):Difference=>{
      if(!record(d) || typeof d.id!=='number' || !Number.isSafeInteger(d.id) || !['doc_no','material','warehouse','remark','operator','at'].every(k=>typeof d[k]==='string') || !['string','number'].includes(typeof d.seq)) throw invalid();
      return {...d,seq:String(d.seq),...amounts(d,['before','after','delta'])} as unknown as Difference;
    });
    matrices[warehouse]={raw,adjusted,totals:{raw:amounts(m.totals.raw),adjusted:amounts(m.totals.adjusted)},segments:{raw:segments(m.segments.raw),adjusted:segments(m.segments.adjusted)},diffs,diff_totals:amounts(m.diff_totals,['before','after','delta'])};
  }
  // Sources and signatures belong to the existing mechanical effective-value contract.
  for(const [warehouse,months] of Object.entries(mechanical.sources)) {
    if(!record(months)) throw invalid();
    for(const [ym,columns] of Object.entries(months)) {
      if(!record(columns)) throw invalid();
      for(const key of mechKeys) if(!record(columns[key]) || typeof columns[key].mode!=='string') throw invalid();
      const signatures=mechanical.effective_signatures[warehouse];
      if(!record(signatures) || typeof signatures[ym]!=='string') throw invalid();
    }
  }
  return {projects:value.projects as string[],matrices,sources:mechanical.sources as ProcessData['sources'],signatures:mechanical.effective_signatures as ProcessData['signatures']};
}
export async function getProcess(signal?:AbortSignal) {
  const init=signal ? {signal} : {};
  const [matrix,mechanical]=await Promise.all([requestJson('/api/m06/matrix',init),requestJson('/api/m06/mech',init)]);
  return readProcess(matrix,mechanical);
}
export async function saveProcess(warehouse:string,ym:string,column:string,value:string,signal:AbortSignal) {
  const result=await requestJson('/api/m06/mech',{method:'POST',signal,...body({warehouse,ym,values:{[column]:value}})});
  if(!record(result) || result.ok!==true || result.warehouse!==warehouse || result.ym!==ym) throw new ApiError('保存回执未确认，请重读核对，勿重复提交。',0,'invalid_response');
}
export async function manualProcess(warehouse:string,ym:string,column:string,signature:string,signal:AbortSignal) {
  const result=await requestJson('/api/m06/workbench/source-manual',{method:'POST',signal,...body({warehouse,ym,columns:[column],effective_signature:signature,confirmed:true})});
  if(!record(result) || result.ok!==true || result.warehouse!==warehouse || result.ym!==ym) throw new ApiError('切换回执未确认，请重读核对，勿重复提交。',0,'invalid_response');
}
