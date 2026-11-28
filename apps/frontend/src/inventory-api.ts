import { ApiError, assertAmountText, body, cents, confirmWrite, decimal, record, requestJson } from './api';
import { timeMatches } from './business-time';

export const fields = [
  ['doc_no','单据编号','text'],['seq','序号','text'],['material','物料','text'],['material_property','物料性质','enum'],
  ['spec','规格','text'],['unit','单位','enum'],['qty','数量','num'],['price_excl','不含税单价','num'],
  ['price_incl','含税单价','num'],['amount','原始金额','num'],['adj_amount','调整后金额','num'],['tax_total','价税合计','num'],
  ['biz_type','业务类型','enum'],['vendor','供应商 / 班组','text'],['doc_date','单据日期','text'],
  ['warehouse','仓库','enum'],['wbs_name','wbs 名称','text'],['cbs_name','cbs 名称','text'],
] as const;
export type Field = typeof fields[number][0];
export const numericFields = ['qty','price_excl','price_incl','amount','tax_total'] as const;
export type NumericField = typeof numericFields[number];
export type InventoryValues = Record<NumericField | 'material_property',string>;
export type CalculationBasis = Record<'amount'|'tax_total','unchanged'|'price'|'amount'>;
export type InventoryRow = Record<Field,string> & { id:number; ym:string; direction:string; project_full_name:string; adjusted:boolean; original_values:InventoryValues; edit_token:string; adjusted_values?:Partial<InventoryValues> };
export interface Adjustment { id:number; row_id:number; before_amount:string; amount:string; remark:string; operator:string; changed_at:string; values:Partial<InventoryValues>; before_values:Partial<InventoryValues>|null }
export interface Inventory { rows:InventoryRow[]; adjustments:Adjustment[]; projects:string[]; materialProperties:string[] }
const invalid = () => new ApiError('库存读取不完整，请重读。');
function numeric(value:unknown):string {
  if (typeof value !== 'number' && typeof value !== 'string') throw invalid();
  const text = String(value); assertAmountText(text); return text;
}
function readValues(value:unknown,partial=false):Partial<InventoryValues> {
  if(!record(value)) throw invalid();
  const result:Partial<InventoryValues>={};
  for(const key of [...numericFields,'material_property'] as const) {
    if(partial && value[key]===undefined) continue;
    if(key==='material_property') {if(typeof value[key]!=='string') throw invalid();result[key]=value[key];}
    else result[key]=numeric(value[key]);
  }
  return result;
}
export function effectiveValues(row:InventoryRow,adjustment?:Adjustment):InventoryValues {return {...row.original_values,...(adjustment?.values ?? row.adjusted_values)};}
export function readInventory(value:unknown):Inventory {
  if (!record(value) || !Array.isArray(value.rows) || !Array.isArray(value.adjustments) || !Array.isArray(value.projects) || !value.projects.every(p => typeof p === 'string') || !Array.isArray(value.material_properties) || !value.material_properties.every(p=>typeof p==='string')) throw invalid();
  const rows = value.rows.map((row:unknown) => {
    if (!record(row) || !Number.isSafeInteger(row.id) || typeof row.ym !== 'string' || typeof row.project_full_name !== 'string' || typeof row.adjusted !== 'boolean') throw invalid();
    if(typeof row.direction!=='string' || typeof row.edit_token!=='string') throw invalid();
    const result = {...row,original_values:readValues(row.original_values),...(row.adjusted_values ? {adjusted_values:readValues(row.adjusted_values,true)} : {})} as InventoryRow;
    for (const [key,,type] of fields) {
      if (key === 'adj_amount' && row[key] == null) result[key] = '';
      else if (type === 'num') result[key] = numeric(row[key]);
      else if (typeof row[key] !== 'string') throw invalid();
    }
    return result;
  });
  const adjustments = value.adjustments.map((a:unknown) => {
    if (!record(a) || typeof a.id !== 'number' || !Number.isSafeInteger(a.id) || typeof a.row_id !== 'number' || !Number.isSafeInteger(a.row_id) ||
      typeof a.remark !== 'string' || typeof a.operator !== 'string' || typeof a.changed_at !== 'string') throw invalid();
    return { ...a, id: a.id, row_id: a.row_id, remark: a.remark, operator: a.operator, changed_at: a.changed_at,
      before_amount: numeric(a.before_amount), amount: numeric(a.amount), values: readValues(a.values, true),
      before_values: a.before_values === null ? null : readValues(a.before_values, true) } satisfies Adjustment;
  });
  const rowIds = new Set(rows.map(r => r.id));
  if (rowIds.size !== rows.length) throw invalid();
  const adjustmentRowIds = new Set(adjustments.map(a => a.row_id));
  if (adjustmentRowIds.size !== adjustments.length || rows.some(r => r.adjusted !== adjustmentRowIds.has(r.id))) throw invalid();
  return {rows,adjustments,projects:value.projects as string[],materialProperties:value.material_properties as string[]};
}
export const getInventory = async (signal?:AbortSignal) => readInventory(await requestJson('/api/m08/inventory',signal ? {signal} : {}));
export function coarseRows(rows:InventoryRow[], period:string, warehouses:string[], direction:string, adjusted:boolean) {
  return rows.filter(r => timeMatches(period,`${r.ym}-01`) && (!warehouses.length || warehouses.includes(r.warehouse)) && (direction === '全部' || direction === r.direction) && (!adjusted || r.adjusted));
}
export function sumRows(rows:InventoryRow[], key:'qty'|'amount'|'adj_amount'|'tax_total') {
  const values = rows.map(r => r[key]).filter(Boolean);
  return values.length ? decimal(values.reduce((sum,value) => sum + cents(value),0n)) : '';
}
export async function adjustInventory(rowId:number, values:InventoryValues, basis:CalculationBasis, remark:string, expected:string, clear:boolean,signal:AbortSignal) {
  const value = await requestJson(`/api/m08/adjust${clear ? '/clear' : ''}`, {method:'POST',signal,...body(clear ? {row_id:rowId,expected} : {row_id:rowId,values,basis,remark,expected})});
  confirmWrite(record(value) && value.ok === true && value.row_id === rowId, '操作回执未确认，请重读核对，勿重复提交。');
}
