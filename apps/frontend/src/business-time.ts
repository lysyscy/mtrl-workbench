/** Calendar periods follow the workbench's Beijing time convention. */
export function currentMonth(date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' }).formatToParts(date);
  return `${parts.find(part => part.type === 'year')!.value}-${parts.find(part => part.type === 'month')!.value}`;
}

export interface TimeRange { dateFrom: string; dateTo: string }
const pad = (n: number) => String(n).padStart(2, '0');
const dateText = (date: Date) => `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
const monthEnd = (month: string) => dateText(new Date(Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5)), 0)));
/** Closed document/payment date interval. A week is stored as its Monday. */
export function timeRange(value: string): TimeRange {
  if (!value || value === '全部') return { dateFrom: '', dateTo: '' };
  if (/^\d{4}-(0[1-9]|1[0-2])$/.test(value)) return { dateFrom: `${value}-01`, dateTo: monthEnd(value) };
  if (/^\d{4}$/.test(value)) return { dateFrom: `${value}-01-01`, dateTo: `${value}-12-31` };
  const range = /^(\d{4})-(0[1-9]|1[0-2])~\1-(0[1-9]|1[0-2])$/.exec(value);
  if (range && range[2]! <= range[3]!) return { dateFrom: `${value.slice(0, 7)}-01`, dateTo: monthEnd(value.slice(8)) };
  const quarter = /^(\d{4})Q([1-4])$/.exec(value);
  if (quarter) return { dateFrom: `${quarter[1]}-${pad(Number(quarter[2]) * 3 - 2)}-01`, dateTo: monthEnd(`${quarter[1]}-${pad(Number(quarter[2]) * 3)}`) };
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const date = new Date(`${value}T00:00:00Z`);
    if (!Number.isNaN(date.getTime()) && dateText(date) === value && date.getUTCDay() === 1) {
      date.setUTCDate(date.getUTCDate() + 6);
      return { dateFrom: value, dateTo: dateText(date) };
    }
  }
  throw new RangeError('时间范围无效');
}
export function timeMatches(value: string, date: string) {
  const { dateFrom, dateTo } = timeRange(value);
  return !dateFrom || (date.slice(0, 10) >= dateFrom && date.slice(0, 10) <= dateTo);
}
