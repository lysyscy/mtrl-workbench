import Decimal from 'decimal.js';
import { numericFields } from './inventory-api';
import type { CalculationBasis, InventoryValues, NumericField } from './inventory-api';

export const valueLabels = {qty:'数量',price_excl:'不含税单价',price_incl:'含税单价',amount:'金额',tax_total:'价税合计',material_property:'物料性质'};
const pairs = {amount:'price_excl',tax_total:'price_incl'} as const;
const DecimalMoney = Decimal.clone({precision:40,rounding:Decimal.ROUND_HALF_UP});
function number(text:string,key:NumericField) {
  const clean=text.trim().replace(/[,，]/g,'');
  if(!clean || !/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(clean)) throw new Error(`${valueLabels[key]}请输入有效的非负数。`);
  const n=new DecimalMoney(clean).toDecimalPlaces(2);
  if(n.gte('10000000000000000')) throw new Error(`${valueLabels[key]}超出可保存范围。`);
  return n;
}
export function calculateInventory(values:InventoryValues,basis:CalculationBasis,baseline:InventoryValues):InventoryValues {
  const parsed=Object.fromEntries(numericFields.map(key=>[key,number(values[key],key)])) as Record<NumericField,Decimal>;
  for(const total of ['amount','tax_total'] as const) {
    const price=pairs[total],mode=basis[total];
    if(mode==='unchanged') {
      if(['qty',price,total].some(key=>!parsed[key as NumericField].eq(number(baseline[key as NumericField],key as NumericField)))) throw new Error(`${valueLabels[total]}关联数值已改变，请编辑数量、对应单价或金额重新联算。`);
    } else if(mode==='price') parsed[total]=parsed.qty.mul(parsed[price]).toDecimalPlaces(2);
    else if(parsed.qty.isZero()) {
      if(!parsed[total].isZero()) throw new Error(`数量为 0，无法反算${valueLabels[price]}，请先填写数量。`);
    } else parsed[price]=parsed[total].div(parsed.qty).toDecimalPlaces(2);
  }
  return {...values,...Object.fromEntries(numericFields.map(key=>[key,number(parsed[key].toFixed(2),key).toFixed(2)]))};
}
export function editInventory(values:InventoryValues,basis:CalculationBasis,key:NumericField,text:string,baseline:InventoryValues) {
  const next={...values,[key]:text},mode={...basis};
  if(key==='qty') {mode.amount='price';mode.tax_total='price';}
  else if(key==='price_excl') mode.amount='price';
  else if(key==='price_incl') mode.tax_total='price';
  else mode[key]='amount';
  try {return {values:{...calculateInventory(next,mode,baseline),[key]:text},basis:mode};}
  catch {return {values:next,basis:mode};}
}
