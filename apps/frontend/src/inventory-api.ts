import { ApiError, body, cents, confirmWrite, decimal, record, requestJson } from './api';
import { timeMatches } from './time-picker';

export const fields = [
  ['doc_no','单据编号','text'],['seq','序号','text'],['direction','方向','enum'],['material','物料','text'],
  ['spec','规格','text'],['unit','单位','enum'],['qty','数量','num'],['price_excl','不含税单价','num'],
  ['price_incl','含税单价','num'],['amount','金额','num'],['adj_amount','调整后金额','num'],['tax_total','价税合计','num'],
  ['biz_type','业务类型','enum'],['vendor','供应商 / 班组','text'],['doc_date','单据日期','text'],
  ['audit_date','审核日期','text'],['warehouse','仓库','enum'],['wbs_name','wbs 名称','text'],['cbs_name','cbs 名称','text'],
] as const;
export type Field = typeof fields[number][0];
export type InventoryRow = Record<Field,string> & { id:number; ym:string; project_full_name:string; adjusted:boolean };
export interface Adjustment { id:number; row_id:number; before_amount:string; amount:string; remark:string; operator:string; changed_at:string }
export interface Inventory { rows:InventoryRow[]; adjustments:Adjustment[]; projects:string[] }
export interface ColumnFilter { q:string; min:string; max:string; values:string[] }
export type Filters = Partial<Record<Field,ColumnFilter>>;
export const emptyFilter = ():ColumnFilter => ({q:'',min:'',max:'',values:[]});
export const filterOn = (f:ColumnFilter) => Boolean(f.q || f.min || f.max || f.values.length);
const invalid = () => new ApiError('库存读取不完整，请重读。');
function numeric(value:unknown):string {
  if (typeof value !== 'number' && typeof value !== 'string') throw invalid();
  const text = String(value); cents(text); return text;
}
export function readInventory(value:unknown):Inventory {
  if (!record(value) || !Array.isArray(value.rows) || !Array.isArray(value.adjustments) || !Array.isArray(value.projects) || !value.projects.every(p => typeof p === 'string')) throw invalid();
  const rows = value.rows.map((row:unknown) => {
    if (!record(row) || !Number.isSafeInteger(row.id) || typeof row.ym !== 'string' || typeof row.project_full_name !== 'string' || typeof row.adjusted !== 'boolean') throw invalid();
    const result = {...row} as InventoryRow;
    for (const [key,,type] of fields) {
      if (key === 'adj_amount' && row[key] == null && !row.adjusted) result[key] = '';
      else if (type === 'num') result[key] = numeric(row[key]);
      else if (typeof row[key] !== 'string') throw invalid();
    }
    return result;
  });
  const adjustments = value.adjustments.map((a:unknown) => {
    if (!record(a) || !Number.isSafeInteger(a.id) || !Number.isSafeInteger(a.row_id) || !['remark','operator','changed_at'].every(k => typeof a[k] === 'string')) throw invalid();
    return {...a,before_amount:numeric(a.before_amount),amount:numeric(a.amount)} as unknown as Adjustment;
  });
  if (new Set(rows.map(r => r.id)).size !== rows.length || new Set(adjustments.map(a => a.row_id)).size !== adjustments.length || rows.some(r => r.adjusted !== adjustments.some(a => a.row_id === r.id))) throw invalid();
  return {rows,adjustments,projects:value.projects as string[]};
}
export const getInventory = async (signal?:AbortSignal) => readInventory(await requestJson('/api/m08/inventory',signal ? {signal} : {}));
export function coarseRows(rows:InventoryRow[], period:string, warehouses:string[], direction:string, adjusted:boolean) {
  return rows.filter(r => timeMatches(period,`${r.ym}-01`) && (!warehouses.length || warehouses.includes(r.warehouse)) && (direction === '全部' || direction === r.direction) && (!adjusted || r.adjusted));
}
export function filterRows(rows:InventoryRow[], filters:Filters) {
  const active = fields.flatMap(([key,,type]) => {
    const f = filters[key];
    return f && filterOn(f) ? [{key,type,q:f.q.toLocaleLowerCase(),min:f.min,max:f.max,
      lower:Number(f.min.replace(/,/g,'')),upper:Number(f.max.replace(/,/g,'')),values:f.values}] : [];
  });
  if (!active.length) return rows;
  return rows.filter(r => active.every(f => {
    const raw = r[f.key];
    if (f.type === 'num') {
      if (!raw) return false;
      if (f.min && (!Number.isFinite(f.lower) || Number(raw) < f.lower)) return false;
      if (f.max && (!Number.isFinite(f.upper) || Number(raw) > f.upper)) return false;
    } else if (f.q && !raw.toLocaleLowerCase().includes(f.q)) return false;
    return !f.values.length || f.values.includes(raw);
  }));
}

export function sumRows(rows:InventoryRow[], key:'qty'|'amount'|'adj_amount'|'tax_total') {
  const values = rows.map(r => r[key]).filter(Boolean);
  return values.length ? decimal(values.reduce((sum,value) => sum + cents(value),0n)) : '';
}
export async function adjustInventory(rowId:number, amount:string, remark:string, clear:boolean,signal:AbortSignal) {
  const value = await requestJson(`/api/m08/adjust${clear ? '/clear' : ''}`, {method:'POST',signal,...body(clear ? {row_id:rowId} : {row_id:rowId,amount,remark})});
  confirmWrite(record(value) && value.ok === true && value.row_id === rowId, '操作回执未确认，请重读核对，勿重复提交。');
}
