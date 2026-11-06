type RuleContent = { kind: string; values: string; meaning: string };

function normalizedContent(rule: RuleContent) {
  const values = [...new Set(rule.values.split(/[｜|，,]/).map(value => value.trim()).filter(Boolean))];
  return JSON.stringify([rule.kind.trim(), values, rule.meaning.trim()]);
}

// Match the repository's ordered value normalization. A match only helps the user inspect the list.
export function countNewRuleMatches(draft: RuleContent, beforeIds: ReadonlySet<number>, rows: (RuleContent & { id: number })[]) {
  const expected = normalizedContent(draft);
  return rows.filter(row => !beforeIds.has(row.id) && normalizedContent(row) === expected).length;
}
