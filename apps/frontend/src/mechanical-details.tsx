import Button from 'antd/es/button';
import Input from 'antd/es/input';
import { Fragment } from 'react';
import { useId } from 'react';
import { DialogContents, useDialogClose } from './dialog-close';
import { BusinessModal } from './business-modal';
import { numberColumnWidth } from './grid';
import { mechanicalMoney as money, detailNet, detailProblems, detailSum, editDetailRow } from './mechanical-api';
import type { Category, Detail, DetailRow } from './mechanical-api';
import './mechanical.css';

export function mechanicalNumberWidth(values: readonly unknown[], scale: number, control = false) {
  return numberColumnWidth(values, scale, control);
}
const numericFields = ['amount','rate','net','qty','plan','used'];

export interface Draft { warehouse: string; ym: string; category: Category; revision: number; rows: DetailRow[]; version: number }
export const detailKey = (warehouse: string, ym: string, category: Category) => JSON.stringify([warehouse,ym,category]);
export const fields: Record<Category, [string,string][]> = {
  zero: [['device','设备名称'],['spec','规格型号'],['unit','单位'],['qty','数量'],['rate','零租单价'],['amount','合价（元）'],['tax','票种／税率'],['net','不含税价'],['date','租赁日期／期间'],['use','用途'],['team','使用班组'],['reviewer','审核人'],['vendor','出租单位'],['plate','车牌号'],['memo','备注']],
  monthly: [['device','设备名称'],['spec','规格型号'],['unit','单位'],['plan','计划月数'],['used','已包月数'],['rate','包月单价'],['amount','合价（元）'],['net','不含税价'],['date','入场日期'],['vendor','出租单位'],['reviewer','审核人'],['tax','票种／税率'],['oil','含油说明'],['plate','车牌号'],['memo','原备注']],
};
const aliases: Record<string,string> = { use:'usage', vendor:'lessor', memo:'note' };
interface DetailGroup { warehouse:string; name:string; saved:Detail|undefined; draft:Draft|undefined }
export function DetailsTable({ scale,groups,category,ym,keywords,problemsOnly,writable,change }: {
  scale:number;groups:DetailGroup[];category:Category;ym:string;keywords:string[];problemsOnly:boolean;writable:boolean;change:(warehouse:string,rows:DetailRow[])=>void;
}) {
  const labels=fields[category],grossIndex=labels.findIndex(([field])=>field==='amount');
  const widths=labels.map(([field])=>numericFields.includes(field)?numberColumnWidth(groups.flatMap(group=>{const rows=group.draft?.rows??group.saved?.rows??[];return [...rows.map(row=>field==='net'?money(detailNet(row)):row[field]??''),field==='amount'?money(detailSum(rows.map(row=>row.amount))):field==='net'?money(detailSum(rows.map(detailNet))):''];}),scale,true).minWidth/scale:['unit','tax'].includes(field)?64:field==='memo'?160:120);
  let count=0;
  return <><div className="mechanical-detail-table" role="region" aria-label={category==='zero'?'零租明细':'包月明细'}><table><colgroup><col style={{width:48*scale}}/>{labels.map(([field],index)=><col key={field} style={{width:widths[index]!*scale}}/>) }<col style={{width:80*scale}}/></colgroup>
    <thead><tr><th>序号</th>{labels.map(([field,label])=><th key={field}>{label}</th>)}<th className="mechanical-detail-actions">操作</th></tr></thead><tbody>{groups.map(group=>{
      const rows=group.draft?.rows??group.saved?.rows??[],shown=rows.map((row,index)=>({row,index})).filter(({row})=>!problemsOnly||detailProblems(row,category,ym,keywords).length);
      const gross=group.draft?detailSum(rows.map(row=>row.amount)):group.saved?.totals.gross,net=group.draft?detailSum(rows.map(detailNet)):group.saved?.totals.net,missing=rows.filter(row=>detailNet(row)===null).length;count+=shown.length;
      return <Fragment key={group.warehouse}><tr className="mechanical-detail-group-row"><th colSpan={grossIndex+1}><strong>{group.name}</strong><span>，{shown.length}条{group.draft?'，待保存（草稿参考）':''}</span></th>{labels.slice(grossIndex).map(([field])=><td key={field} className={field==='amount'||field==='net'?'money':''}>{field==='amount'?money(gross):field==='net'?<>{money(net)}{missing>0&&<small>（{missing}条待补）</small>}</>:null}</td>)}<td className="mechanical-detail-actions"><Button size="small" disabled={!writable} onClick={()=>{const row={id:crypto.randomUUID(),device:'',unit:'台班',amount:'',tax:''};change(group.warehouse,[...rows,row]);requestAnimationFrame(()=>document.getElementById('mechanical-device-'+row.id)?.focus());}}>增行</Button></td></tr>
        {shown.map(({row,index})=><tr key={row.id}><td>{index+1}</td>{labels.map(([field,label])=>{
          const exempt=field==='plate'&&((category==='monthly'&&ym<'2026-06')||keywords.some(word=>String(row.device??'').includes(word)))&&!row.plate;
          return <td key={field} className={field==='net'?'money':''}>{field==='net'?(detailNet(row)===null?'待补税率':money(detailNet(row))):exempt?<span className="muted">无需车牌</span>:<Input id={field==='device'?'mechanical-device-'+row.id:undefined} aria-label={`${group.name} 第${index+1}行 ${label}`} inputMode={numericFields.includes(field)?'decimal':'text'} className={numericFields.includes(field)?'money':''} value={String(row[field]??row[aliases[field]??'']??'')} disabled={!writable} maxLength={4000} onChange={e=>change(group.warehouse,rows.map(item=>item.id===row.id?editDetailRow(item,field,e.target.value,category):item))}/>}</td>;
        })}<td className="mechanical-detail-actions"><Button danger size="small" disabled={!writable} onClick={()=>change(group.warehouse,rows.filter(item=>item.id!==row.id))}>移除</Button></td></tr>)}
        {!shown.length&&<tr><td className="state" colSpan={labels.length+2}>{problemsOnly?'此项目没有待补字段。':'尚无明细；在项目右侧“增行”录入。有效月值保留。'}</td></tr>}
      </Fragment>;
    })}{!groups.length&&<tr><td className="state" colSpan={labels.length+2}>尚未选择显示项目。用“显示项目”选入已有项目后增行。</td></tr>}</tbody></table></div><p className="mechanical-feedback">当前显示 {count} 条，项目合计见合价、不含税价列</p></>;
}

export function MechanicalDialog({ title, close, busy, dirty = false, paused = false, className = '', children }: { className?: string; title: string; close: () => void; busy: boolean; dirty?: boolean; paused?: boolean; children: React.ReactNode | ((requestClose: () => boolean) => React.ReactNode) }) {
  const titleId = useId();
  const closing = useDialogClose({ busy, dirty, close, active: !paused });
  return <BusinessModal open={!paused} requestClose={closing.requestClose} className={`mechanical-dialog ${className}`} titleId={titleId}><DialogContents title={title} titleId={titleId} closing={closing}><div className="mechanical-dialog-body">{typeof children === 'function' ? children(closing.requestClose) : children}</div></DialogContents></BusinessModal>;
}
