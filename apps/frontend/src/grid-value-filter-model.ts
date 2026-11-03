import Decimal from 'decimal.js';

export type ValueFilterKind = 'text' | 'date' | 'number';
export type FilterValue = string | number | null | undefined;
export interface ValueFilterModel { values: string[] }
export interface ValueCandidate { key: string; label: string; count: number }
export interface ValueFilterNode { key: string; label: string; count: number; values: string[]; search: string; children?: ValueFilterNode[] }

export function valueFilterKey(value: FilterValue, kind: ValueFilterKind): string {
  if (value === null || value === undefined || value === '') return 'blank:';
  const text = String(value);
  if (kind === 'number') {
    try { const number = new Decimal(text); if (number.isFinite()) return `n:${number.toFixed()}`; } catch { /* Preserve unexpected source text rather than making it zero. */ }
  }
  if (kind === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(text)) {
    const parsed = new Date(`${text}T00:00:00Z`);
    if (!Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === text) return `d:${text}`;
  }
  return `t:${text}`;
}
export function valueFilterPasses(model: ValueFilterModel | null | undefined, value: FilterValue, kind: ValueFilterKind): boolean {
  return !model?.values.length || model.values.includes(valueFilterKey(value, kind));
}
export function toggleValueFilter(model: ValueFilterModel | null, values: readonly string[], checked: boolean): ValueFilterModel | null {
  const selected = new Set(model?.values ?? []);
  for (const value of values) { if (checked) selected.add(value); else selected.delete(value); }
  return selected.size ? { values: [...selected] } : null;
}
export function compareFilterValues(a: FilterValue, b: FilterValue, kind: ValueFilterKind): number {
  const left = valueFilterKey(a, kind), right = valueFilterKey(b, kind);
  if (kind === 'number' && left.startsWith('n:') && right.startsWith('n:')) return new Decimal(left.slice(2)).comparedTo(right.slice(2));
  if (left === 'blank:' || right === 'blank:') return Number(left === 'blank:') - Number(right === 'blank:');
  return String(a ?? '').localeCompare(String(b ?? ''), 'zh', { numeric: true });
}
export function valueFilterCandidates(values: readonly FilterValue[], kind: ValueFilterKind, format?: (value: FilterValue) => string): ValueCandidate[] {
  const candidates = new Map<string, ValueCandidate>();
  for (const value of values) {
    const key = valueFilterKey(value, kind), existing = candidates.get(key);
    if (existing) existing.count++;
    else candidates.set(key, { key, count: 1, label: key === 'blank:' ? '（空白）' : format ? format(value) : key.startsWith('n:') ? key.slice(2) : String(value) });
  }
  return [...candidates.values()].sort((a, b) => compareFilterValues(a.key.slice(a.key.indexOf(':') + 1), b.key.slice(b.key.indexOf(':') + 1), kind));
}
export function valueFilterTree(candidates: readonly ValueCandidate[], kind: ValueFilterKind): ValueFilterNode[] {
  const roots: ValueFilterNode[] = [], years = new Map<string, ValueFilterNode>(), months = new Map<string, ValueFilterNode>();
  for (const item of candidates) {
    const date = kind === 'date' && item.key.startsWith('d:') ? item.key.slice(2) : null;
    const leaf: ValueFilterNode = { ...item, values: [item.key], search: item.label.toLocaleLowerCase() };
    if (!date) { roots.push(leaf); continue; }
    const year = date.slice(0, 4), month = date.slice(0, 7);
    if (!years.has(year)) { const node = { key: `year:${year}`, label: `${year}年`, count: 0, values: [], search: year, children: [] }; years.set(year, node); roots.push(node); }
    if (!months.has(month)) { const node = { key: `month:${month}`, label: `${Number(date.slice(5, 7))}月`, count: 0, values: [], search: month, children: [] }; months.set(month, node); years.get(year)!.children!.push(node); }
    const yearNode = years.get(year)!, monthNode = months.get(month)!;
    for (const node of [yearNode, monthNode]) { node.values.push(item.key); node.count += item.count; }
    monthNode.children!.push({ ...leaf, label: `${Number(date.slice(8))}日`, search: `${date} ${item.label}`.toLocaleLowerCase() });
  }
  return roots;
}
export function searchValueFilterTree(nodes: readonly ValueFilterNode[], search: string): ValueFilterNode[] {
  const term = search.trim().toLocaleLowerCase();
  if (!term) return [...nodes];
  return nodes.flatMap(node => {
    if (node.search.includes(term) || node.label.toLocaleLowerCase().includes(term)) return [node];
    const children = node.children ? searchValueFilterTree(node.children, term) : [];
    return children.length ? [{ ...node, children }] : [];
  });
}
export function checkedValueFilterNodes(nodes: readonly ValueFilterNode[], model: ValueFilterModel | null) {
  const selected = new Set(model?.values ?? []), checked: string[] = [], halfChecked: string[] = [];
  const visit = (node: ValueFilterNode) => {
    const count = node.values.filter(key => selected.has(key)).length;
    if (count === node.values.length && count > 0) checked.push(node.key);
    else if (count > 0) halfChecked.push(node.key);
    node.children?.forEach(visit);
  };
  nodes.forEach(visit);
  return { checked, halfChecked };
}
