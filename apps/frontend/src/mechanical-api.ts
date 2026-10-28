import { ApiError, record } from './api';

export type Category = 'zero' | 'monthly';
export interface DetailRow { id: string; [field: string]: unknown }
export interface Detail { warehouse: string; ym: string; category: Category; revision: number; rows: DetailRow[]; totals: { gross: string | null; net: string | null }; issues: { id: string; fields: string[] }[] }
export interface Effective { warehouse: string; ym: string; signature: string; values: Record<string, string | null>; sources: Record<string, { mode: string }> }
export interface SourceRow { id: string; bill?: string; periodName?: string; periodKey?: string; amount?: string | null; approval?: string | null }
export interface Relation { warehouse: string; relation: string; left: string | null; right: string | null; pending: string | null; raw: string | null; ignored: string; revision: number; i8_revision: number; i6: string | null; fetched_at?: string }
export interface BillDifference extends SourceRow { warehouse: string; document_id: string; fact: string; settlement: string; difference: string; ignored: boolean; revision: number }
export interface Discovery { id: string; warehouse: string; kind: string; status: string; revision: number; note?: string; projectName?: string; projectId?: string; totals?: Record<string,string | null>; sources?: Record<string,SourceRow[]> }
export interface Matter { id: string; warehouse: string; text: string; completed: boolean; revision: number; metadata: Record<string,unknown> }
export interface I8Snapshot { warehouse: string; sources: Record<string,SourceRow[]>; totals: Record<string,string | null>; scope?: unknown }
export interface I8Project extends I8Snapshot { before: Partial<I8Snapshot>; complete: boolean; reduction: boolean; changed: boolean; missing: string[] }
export interface I8Preview { preview_id: string; projects: I8Project[]; unmapped_projects: Discovery[]; counts: Record<string,number> }
export interface WorkbenchSummary { warehouse:string; ym:string; cumulative:Record<string,string|null>; note?:string }
export interface Workbench { months: string[]; shown: string[]; warehouses: string[]; details: Detail[]; effective: Effective[]; relations: Relation[]; billDifferences: BillDifference[]; discoveries: Discovery[]; matters: Matter[]; i8: I8Snapshot[]; histories: Record<string,unknown>[]; summary:WorkbenchSummary[]; settings: { revision: number; plate_keywords: string[] } }
export function readDetail(value: unknown): Detail {
  if (!record(value) || typeof value.warehouse !== 'string' || typeof value.ym !== 'string' || !['zero','monthly'].includes(String(value.category)) || !Number.isSafeInteger(value.revision) || !Array.isArray(value.rows) || value.rows.some((r: unknown) => !record(r) || typeof r.id !== 'string') || !record(value.totals) || !Array.isArray(value.issues) || !nullableAmount(value.totals.gross) || !nullableAmount(value.totals.net)) throw invalid();
  return value as unknown as Detail;
}
export interface ReportCell { value: string; rowspan: number; colspan: number; column: number }
export interface ReportSheet { name: string; rows: ReportCell[][]; project_rows: { warehouse: string; row: number }[] }
export interface MechanicalReport { ym: string; sheets: ReportSheet[] }
const sheetNames = ['工程公司汇总表', '零租设备月报表', '包月外租设备月报', '年度汇总'];
const invalid = () => new ApiError('机械报表结果不完整，请重新读取；仍失败请联系维护人员。');
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === 'string');
const revision = (value: unknown) => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
const amount = (value: unknown) => typeof value === 'string' && /^-?\d+(?:\.\d+)?$/.test(value);
const nullableAmount = (value: unknown) => value === null || amount(value);
const sourceKinds = ['usage','project','team'] as const;
function sources(value: unknown): boolean {
  return record(value) && sourceKinds.every(kind => Array.isArray(value[kind]) && value[kind].every((row: unknown) => record(row) && typeof row.id === 'string' && !!row.id && ['bill','periodName','periodKey'].every(key => row[key] == null || typeof row[key] === 'string') && ['amount','approval'].every(key => row[key] === undefined || nullableAmount(row[key]))));
}
const totals = (value: unknown) => record(value) && sourceKinds.every(kind => nullableAmount(value[kind]));
const snapshot = (value: unknown) => record(value) && typeof value.warehouse === 'string' && !!value.warehouse && sources(value.sources) && totals(value.totals);
function discovery(value: unknown, requireRevision = true): boolean {
  return record(value) && typeof value.id === 'string' && !!value.id && typeof value.warehouse === 'string' && ['first','changed','unmapped','missing-project'].includes(String(value.kind)) && ['pending','resolved'].includes(String(value.status)) && (!requireRevision || revision(value.revision)) && ['note','projectName','projectId'].every(key => value[key] == null || typeof value[key] === 'string') && (value.sources === undefined || sources(value.sources)) && (value.totals === undefined || totals(value.totals));
}
const matter = (value: unknown) => record(value) && typeof value.id === 'string' && !!value.id && typeof value.warehouse === 'string' && typeof value.text === 'string' && typeof value.completed === 'boolean' && revision(value.revision) && record(value.metadata);
export function readI8Preview(value: unknown): I8Preview {
  const counts=record(value)?value.counts:undefined;
  if (!record(value) || value.ok !== true || typeof value.preview_id !== 'string' || !value.preview_id || !record(counts) || !sourceKinds.every(kind => revision(counts[kind])) || !Array.isArray(value.projects) || !Array.isArray(value.unmapped_projects) || !value.unmapped_projects.every(item => discovery(item, false))) throw invalid();
  for (const item of value.projects) {
    if (!record(item) || !snapshot(item) || typeof item.complete !== 'boolean' || typeof item.reduction !== 'boolean' || typeof item.changed !== 'boolean' || !strings(item.missing) || !record(item.before) || (Object.keys(item.before).length > 0 && (!snapshot(item.before) || item.before.warehouse !== item.warehouse))) throw invalid();
  }
  if (new Set(value.projects.map(item => item.warehouse)).size !== value.projects.length) throw invalid();
  return value as unknown as I8Preview;
}
export function readWorkResult(value: unknown, action: string, payload: Record<string,unknown>): void {
  if (!record(value) || value.ok !== true) throw receiptInvalid();
  const warehouses=value.warehouses;
  const valid = action === 'i8-confirm' ? strings(warehouses) && strings(payload.warehouses) && payload.warehouses.every(wh => warehouses.includes(wh))
    : action === 'ignore' ? revision(value.revision) && amount(value.amount)
    : action === 'document-ignore' ? revision(value.revision) && value.ignored === !payload.undo
    : action === 'settings' ? revision(value.revision) && strings(value.shown_projects) && strings(value.plate_keywords)
    : action === 'matter-save' ? matter(value) && value.warehouse === payload.warehouse && value.text === String(payload.text).trim() && value.completed === payload.completed && (!payload.id || value.id === payload.id)
    : action === 'discovery-resolve' ? discovery(value) && value.id === payload.id && value.status === 'resolved' && value.note === String(payload.note).trim()
    : false;
  if (!valid) throw receiptInvalid();
}
const receiptInvalid = () => new ApiError('操作回执不完整，请重新读取核对后再办理。', 0, 'invalid_receipt');
export function readWorkbench(value: unknown): Workbench {
  if (!record(value) || value.ok !== true || !strings(value.months) || value.months.some(month => !/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) || !record(value.settings) || !strings(value.settings.shown_projects) || !Array.isArray(value.projects)) throw invalid();
  const warehouses = value.projects.map((project: unknown) => { if (!record(project) || typeof project.warehouse !== 'string') throw invalid(); return project.warehouse; });
  if (!Array.isArray(value.details) || !Array.isArray(value.effective) || !Array.isArray(value.reconciliations) || !Array.isArray(value.billDifferences) || !Array.isArray(value.discoveries) || !Array.isArray(value.matters) || !Array.isArray(value.i8) || !Array.isArray(value.histories) || !Array.isArray(value.summary) || value.summary.some((item:unknown)=>!record(item)||typeof item.warehouse!=='string'||typeof item.ym!=='string'||!record(item.cumulative)||!Object.values(item.cumulative).every(nullableAmount)||(item.note!=null&&typeof item.note!=='string')) || !revision(value.settings.revision) || !strings(value.settings.plate_keywords)) throw invalid();
  const effective = value.effective.map((r: unknown): Effective => {
    if (!record(r) || typeof r.warehouse !== 'string' || typeof r.ym !== 'string' || typeof r.signature !== 'string' || !record(r.values) || !record(r.sources)) throw invalid();
    return r as unknown as Effective;
  });
  if (value.reconciliations.some((r: unknown) => !record(r) || typeof r.warehouse !== 'string' || !['report','internal'].includes(String(r.relation)) || !['left','right','pending','raw','i6'].every(key => nullableAmount(r[key])) || !amount(r.ignored) || !revision(r.revision) || !revision(r.i8_revision) || (r.fetched_at != null && typeof r.fetched_at !== 'string')) || value.billDifferences.some((r: unknown) => !record(r) || typeof r.warehouse !== 'string' || !['id','document_id','fact'].every(key => typeof r[key] === 'string' && !!r[key]) || !['settlement','approval','difference'].every(key => amount(r[key])) || !revision(r.revision) || typeof r.ignored !== 'boolean') || !value.discoveries.every(item => discovery(item)) || !value.matters.every(matter) || !value.i8.every(snapshot) || value.histories.some((item: unknown) => !record(item) || typeof item.warehouse !== 'string')) throw invalid();
  return { months: value.months, shown: value.settings.shown_projects, warehouses, details: value.details.map(readDetail), effective, relations: value.reconciliations as Relation[], billDifferences: value.billDifferences as BillDifference[], discoveries: value.discoveries as Discovery[], matters: value.matters as Matter[], i8: value.i8 as I8Snapshot[], histories: value.histories as Record<string,unknown>[], summary:value.summary as WorkbenchSummary[], settings: { revision: value.settings.revision as number, plate_keywords: value.settings.plate_keywords } };
}
export function readMechanicalReport(value: unknown, ym: string, warehouses: string[]): MechanicalReport {
  if (!record(value) || value.ok !== true || value.ym !== ym || !Array.isArray(value.projects) || value.projects.length !== warehouses.length || value.projects.some((project: unknown, index: number) => !record(project) || project.warehouse !== warehouses[index]) || !Array.isArray(value.sheets) || value.sheets.length !== 4) throw invalid();
  const sheets = value.sheets.map((sheet: unknown, index: number): ReportSheet => {
    if (!record(sheet) || typeof sheet.name !== 'string' || sheet.name !== sheetNames[index] || !Array.isArray(sheet.rows) || !Array.isArray(sheet.project_rows) || sheet.project_rows.length !== warehouses.length) throw invalid();
    const rows = sheet.rows.map((row: unknown): ReportCell[] => {
      if (!Array.isArray(row)) throw invalid();
      let previous = 0;
      return row.map((cell: unknown) => {
        if (!record(cell) || typeof cell.value !== 'string' || typeof cell.rowspan !== 'number' || !Number.isSafeInteger(cell.rowspan) || cell.rowspan < 1 || typeof cell.colspan !== 'number' || !Number.isSafeInteger(cell.colspan) || cell.colspan < 1 || typeof cell.column !== 'number' || !Number.isSafeInteger(cell.column) || cell.column <= previous) throw invalid();
        previous = cell.column;
        return { value: cell.value, rowspan: cell.rowspan, colspan: cell.colspan, column: cell.column };
      });
    });
    const project_rows = sheet.project_rows.map((group: unknown, index: number) => {
      if (!record(group) || typeof group.warehouse !== 'string' || group.warehouse !== warehouses[index] || typeof group.row !== 'number' || !Number.isSafeInteger(group.row) || group.row < 1 || group.row > rows.length) throw invalid();
      return { warehouse: group.warehouse, row: group.row };
    });
    if (new Set(project_rows.map(group => group.row)).size !== project_rows.length) throw invalid();
    return { name: sheet.name, rows, project_rows };
  });
  if (sheets[0]!.rows.length !== warehouses.length + 6) throw invalid();
  return { ym, sheets };
}

// Match the existing detail editor: preserve source precision, round only the total.
function decimal(value: unknown): { value: bigint; places: number } | null {
  const text = String(value ?? '').trim(); if (!/^-?\d+(?:\.\d+)?$/.test(text)) return null;
  const [whole, fraction = ''] = text.replace(/^-/, '').split('.');
  return { value: (text.startsWith('-') ? -1n : 1n) * BigInt(whole + fraction), places: fraction.length };
}
const round = (value: bigint, divisor: bigint) => (value < 0n ? -1n : 1n) * (((value < 0n ? -value : value) * 2n + divisor) / (divisor * 2n));
const textMoney = (cents: bigint) => `${cents < 0n ? '-' : ''}${(cents < 0n ? -cents : cents) / 100n}.${((cents < 0n ? -cents : cents) % 100n).toString().padStart(2,'0')}`;
export function detailSum(values: unknown[]): string | null {
  const numbers = values.map(decimal).filter(n => n !== null); if (!numbers.length) return null;
  const places = Math.max(...numbers.map(n => n.places));
  return textMoney(round(numbers.reduce((sum,n) => sum + n.value * 10n ** BigInt(places - n.places),0n) * 100n,10n ** BigInt(places)));
}
export function detailNet(row: DetailRow): string | null {
  const amount = decimal(row.amount), tax = String(row.tax ?? '').trim(); if (!amount || !tax) return null;
  const ordinary = tax.includes('普票'); const match = tax.match(/^(?:专票\s*)?(\d+(?:\.\d+)?)\s*%(?:\s*专票?)?(?:[，,\s].*)?$/);
  if (!ordinary && (!match || Number(match[1]) > 100)) return null;
  const original = decimal(row.original);
  if (decimal(row.sourceNet) && original && amount.value * 10n ** BigInt(original.places) === original.value * 10n ** BigInt(amount.places) && tax === row.originalTax) return String(row.sourceNet);
  if (ordinary) return String(row.amount);
  const rate = decimal(match![1])!; const base = 100n * 10n ** BigInt(rate.places);
  return textMoney(round(amount.value * 100n * base, (base + rate.value) * 10n ** BigInt(amount.places)));
}
export function detailProblems(row: DetailRow, category: Category, month: string, keywords: string[]): string[] {
  const problems: string[] = [];
  if (!String(row.device ?? '').trim()) problems.push('设备名称');
  if (!decimal(row.amount)) problems.push('合价');
  if (detailNet(row) === null) problems.push('票种／税率');
  if (!(category === 'monthly' && month < '2026-06') && !keywords.some(word => String(row.device ?? '').includes(word)) && (!String(row.plate ?? '').trim() || /^(无|无牌|场内|炮捶|加班.*|有加班)$/.test(String(row.plate).trim()))) problems.push('车牌');
  return problems;
}

export function editDetailRow(row: DetailRow, field: string, value: string, category: Category): DetailRow {
  const next = { ...row, [field]: value };
  const alias = ({ use: 'usage', vendor: 'lessor', memo: 'note' } as Record<string,string>)[field];
  if (alias) delete next[alias];
  const measure = category === 'zero' ? 'qty' : 'used';
  if ((field === 'rate' || field === measure) && /^\d+(?:\.\d{1,3})?$/.test(String(next[measure] ?? ''))) {
    const rate = decimal(next.rate), quantity = decimal(next[measure]);
    if (rate && quantity) next.amount = textMoney(round(rate.value * quantity.value * 100n, 10n ** BigInt(rate.places + quantity.places)));
  }
  if (['amount', 'rate', measure, 'tax'].includes(field)) delete next.net;
  return next;
}

export function mechanicalMoney(value: unknown): string {
  const text=detailSum([value]); return text === null ? '—' : text.replace(/\B(?=(\d{3})+(?!\d))/g,',');
}
