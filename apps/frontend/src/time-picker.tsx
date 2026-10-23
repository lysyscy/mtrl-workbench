import { useEffect, useState } from 'react';
import DatePicker from 'antd/es/date-picker';
import Select from 'antd/es/select';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
dayjs.locale('zh-cn');

export type TimeMode = '月' | '跨月' | '年' | '季度' | '周' | '全部';
export interface TimeRange { dateFrom: string; dateTo: string }
export interface TimePickerProps {
  value: string;
  onChange: (value: string) => void;
  modes: readonly TimeMode[];
  disabled?: boolean;
  label?: string;
}
const pad = (n: number) => String(n).padStart(2, '0');
const dateText = (date: Date) => `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
const monthEnd = (month: string) => dateText(new Date(Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5)), 0)));
function monday(day: string) {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7);
  return dateText(date);
}
function modeOf(value: string): TimeMode {
  if (!value || value === '全部') return '全部';
  if (value.includes('~')) return '跨月';
  if (value.includes('Q')) return '季度';
  if (value.length === 10) return '周';
  return value.length === 4 ? '年' : '月';
}
export function timeLabel(value: string) { return !value || value === '全部' ? '全部时间' : value.replace('~', ' ~ '); }
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

export function BusinessDate({ value, onChange, disabled = false, label }: { value: string; onChange: (value: string) => void; disabled?: boolean; label: string }) {
  return <DatePicker aria-label={label} value={value ? dayjs(value) : null} onChange={date => onChange(date ? date.format('YYYY-MM-DD') : '')}
    disabled={disabled} format="YYYY-MM-DD" classNames={{ popup: { root: 'ag-custom-component-popup' } }}
    getPopupContainer={trigger => trigger.closest<HTMLElement>('.ant-modal-container') ?? document.body} />;
}

export function TimePicker({ value, onChange, modes, disabled = false, label = '时间' }: TimePickerProps) {
  const [mode, setMode] = useState<TimeMode>(() => modes.includes(modeOf(value)) ? modeOf(value) : modes[0] ?? '月');
  useEffect(() => { const next = modeOf(value); if (modes.includes(next)) setMode(next); }, [value, modes.join(',')]);
  const available = modes.includes(mode) ? mode : modes[0] ?? '月';
  const popup = { popup: { root: 'ag-custom-component-popup' } };
  const container = (trigger: HTMLElement) => trigger.closest<HTMLElement>('.ant-modal-container') ?? document.body;
  const current = modeOf(value) === available && value !== '全部' ? dayjs(available === '季度' ? `${value.slice(0,4)}-${pad(Number(value.slice(5))*3-2)}-01` : value.split('~')[0]) : null;
  function choose(date: dayjs.Dayjs | null) {
    if (!date) { if (modes.includes('全部')) onChange('全部'); return; }
    onChange(available === '周' ? monday(date.format('YYYY-MM-DD')) : available === '季度' ? `${date.year()}Q${Math.ceil((date.month()+1)/3)}` : date.format(available === '年' ? 'YYYY' : 'YYYY-MM'));
  }
  return <span className="business-time-picker">
    {modes.length > 1 && <Select aria-label={`${label}模式`} value={available} disabled={disabled} options={modes.map(item => ({ value: item, label: item }))}
      onChange={next => { setMode(next); if (next === '全部') onChange('全部'); }} getPopupContainer={container} />}
    {available === '跨月' ? <DatePicker.RangePicker aria-label={label} picker="month" format="YYYY-MM" disabled={disabled} allowClear={modes.includes('全部')}
      value={modeOf(value) === '跨月' ? [dayjs(value.slice(0,7)), dayjs(value.slice(8))] : null}
      disabledDate={(date, info) => Boolean(info.from && date.year() !== info.from.year())}
      onChange={dates => { if (dates?.[0] && dates[1]) { if (dates[0].year() === dates[1].year()) onChange(`${dates[0].format('YYYY-MM')}~${dates[1].format('YYYY-MM')}`); } else if (modes.includes('全部')) onChange('全部'); }}
      getPopupContainer={container} classNames={popup} /> : available !== '全部' && <DatePicker aria-label={label}
      picker={available === '年' ? 'year' : available === '季度' ? 'quarter' : available === '周' ? 'week' : 'month'}
      format={available === '周' ? date => `${monday(date.format('YYYY-MM-DD'))} 起` : available === '季度' ? 'YYYY[Q]Q' : available === '年' ? 'YYYY' : 'YYYY-MM'}
      value={current} onChange={choose} disabled={disabled} allowClear={modes.includes('全部')} getPopupContainer={container} classNames={popup} />}
  </span>;
}
