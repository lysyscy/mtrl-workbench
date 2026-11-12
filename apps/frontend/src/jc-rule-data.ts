import { ApiError, record } from './api';

export const jcRuleKinds = {
  project: 'i8 项目全名',
  contract: '合同编号',
  keyword: '项目内单据名关键词',
} as const;
export type JcRuleKind = keyof typeof jcRuleKinds;
export interface JcCondition { kind: JcRuleKind; name_full: string; contract_no: string; bill_name_keyword: string }
export interface JcRule extends JcCondition { id: number; reason: string; operator: string; created_at: string }

export const jcRulesPath = '/api/m14/jc-ignore';

export function jcCondition(rule: JcCondition) {
  if (rule.kind === 'contract') return rule.contract_no;
  if (rule.kind === 'keyword') return `${rule.name_full} · 含「${rule.bill_name_keyword}」`;
  return rule.name_full;
}

export function isJcRule(value: unknown): value is JcRule {
  return record(value) && typeof value.id === 'number' && Number.isSafeInteger(value.id) &&
    typeof value.kind === 'string' && Object.hasOwn(jcRuleKinds, value.kind) &&
    ['name_full', 'contract_no', 'bill_name_keyword', 'reason', 'operator', 'created_at'].every(key => typeof value[key] === 'string');
}

export function readJcRules(value: unknown): JcRule[] {
  if (!record(value) || !Array.isArray(value.items) || !value.items.every(isJcRule)) {
    throw new ApiError('集采剔除规则读取不完整，请重试。');
  }
  return value.items;
}
