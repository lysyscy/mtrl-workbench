import Tag from 'antd/es/tag';
const categoryTones: Record<string, string> = { 辅材: 'blue', 机械: 'ochre', 集采: 'purple' };
const methodTones: Record<string, string> = { 现汇: 'cyan', 承兑: 'ochre', 供应链: 'blue', 其他: 'cyan' };

export function EnumTag({ kind, value }: { kind: 'category' | 'payMethod'; value?: string }) {
  const tone = (kind === 'category' ? categoryTones : methodTones)[value ?? ''];
  return <Tag className={`enum-tag${tone ? ` category-${tone}` : ''}`}>{value || '—'}</Tag>;
}
