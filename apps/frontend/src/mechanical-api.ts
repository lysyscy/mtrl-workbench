import { ApiError, record } from './api';

export interface Workbench { months: string[]; shown: string[]; warehouses: string[] }
export interface ReportCell { value: string; rowspan: number; colspan: number; column: number }
export interface ReportSheet { name: string; rows: ReportCell[][] }
export interface MechanicalReport { ym: string; sheets: ReportSheet[]; warnings: string[]; snapshot_token: string }
const sheetNames = ['工程公司汇总表', '零租设备月报表', '包月外租设备月报', '年度汇总'];
const invalid = () => new ApiError('机械报表结果不完整，请重新读取；仍失败请联系维护人员。');
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === 'string');
export function readWorkbench(value: unknown): Workbench {
  if (!record(value) || value.ok !== true || !strings(value.months) || value.months.some(month => !/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) || !record(value.settings) || !strings(value.settings.shown_projects) || !Array.isArray(value.projects)) throw invalid();
  const warehouses = value.projects.map((project: unknown) => { if (!record(project) || typeof project.warehouse !== 'string') throw invalid(); return project.warehouse; });
  return { months: value.months, shown: value.settings.shown_projects, warehouses };
}
export function readMechanicalReport(value: unknown, ym: string, warehouses: string[]): MechanicalReport {
  if (!record(value) || value.ok !== true || value.ym !== ym || typeof value.snapshot_token !== 'string' || !/^[a-f0-9]{64}$/.test(value.snapshot_token) || !strings(value.warnings) || !Array.isArray(value.projects) || value.projects.length !== warehouses.length || value.projects.some((project: unknown, index: number) => !record(project) || project.warehouse !== warehouses[index]) || !Array.isArray(value.sheets) || value.sheets.length !== 4) throw invalid();
  const sheets = value.sheets.map((sheet: unknown, index: number): ReportSheet => {
    if (!record(sheet) || typeof sheet.name !== 'string' || sheet.name !== sheetNames[index] || !Array.isArray(sheet.rows)) throw invalid();
    const rows = sheet.rows.map((row: unknown): ReportCell[] => {
      if (!Array.isArray(row)) throw invalid();
      let previous = 0;
      return row.map((cell: unknown) => {
        if (!record(cell) || typeof cell.value !== 'string' || typeof cell.rowspan !== 'number' || !Number.isSafeInteger(cell.rowspan) || cell.rowspan < 1 || typeof cell.colspan !== 'number' || !Number.isSafeInteger(cell.colspan) || cell.colspan < 1 || typeof cell.column !== 'number' || !Number.isSafeInteger(cell.column) || cell.column <= previous) throw invalid();
        previous = cell.column;
        return { value: cell.value, rowspan: cell.rowspan, colspan: cell.colspan, column: cell.column };
      });
    });
    return { name: sheet.name, rows };
  });
  if (sheets[0]!.rows.length !== warehouses.length + 6) throw invalid();
  return { ym, sheets, warnings: value.warnings, snapshot_token: value.snapshot_token };
}
