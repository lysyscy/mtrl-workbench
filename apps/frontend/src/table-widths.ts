export interface TableColumnWidth { min: number; max: number; flex?: number }

export function tableWidths(columns: readonly TableColumnWidth[], measured: number[], available: number, em: number): number[] {
  const min = columns.map(c => c.min * em), max = columns.map(c => c.max * em);
  const sizes = columns.map((_, i) => Math.max(min[i]!, Math.min(max[i]!, measured[i] ?? min[i]!)));
  const total = sizes.reduce((a, b) => a + b, 0), floor = min.reduce((a, b) => a + b, 0);
  if (total > available && total > floor) {
    const keep = Math.max(0, (available - floor) / (total - floor));
    return sizes.map((size, i) => min[i]! + (size - min[i]!) * keep);
  }
  let spare = available - total;
  for (let pass = 0; spare > .001 && pass < columns.length; pass++) {
    const flexible = columns.map((c, i) => c.flex && sizes[i]! < max[i]! ? i : -1).filter(i => i >= 0);
    const weight = flexible.reduce((n, i) => n + columns[i]!.flex!, 0);
    if (!weight) break;
    let used = 0;
    for (const i of flexible) { const add = Math.min(max[i]! - sizes[i]!, spare * columns[i]!.flex! / weight); sizes[i]! += add; used += add; }
    spare -= used;
  }
  return sizes;
}
