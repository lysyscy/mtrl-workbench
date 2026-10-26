import { useEffect, useRef, useState } from 'react';
import { currentMonth } from './business-time';
import DatePicker from 'antd/es/date-picker';
import Select from 'antd/es/select';
import Button from 'antd/es/button';
import Popover from 'antd/es/popover';
import Calendar from 'antd/es/calendar';
import Segmented from 'antd/es/segmented';
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
  singleEntry?: boolean;
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

export function TimePicker(props: TimePickerProps) {
  return props.singleEntry ? <SingleEntryPeriod {...props} /> : <StandardTimePicker {...props} />;
}

function StandardTimePicker({ value, onChange, modes, disabled = false, label = '时间' }: TimePickerProps) {
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

/** One popover owns mode and period selection; Calendar supplies the month grid. */
function SingleEntryPeriod({ value, onChange, modes, disabled = false, label = '时间' }: TimePickerProps) {
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null), trigger = useRef<HTMLButtonElement>(null);
  const initial = modeOf(value);
  const [mode, setMode] = useState<TimeMode>(initial === '全部' ? '月' : initial);
  const [year, setYear] = useState(() => /^\d{4}/.test(value) ? Number(value.slice(0, 4)) : Number(currentMonth().slice(0, 4)));
  const [start, setStart] = useState<number | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const available = modes.includes(mode) ? mode : modes.find(item => item !== '全部') ?? '月';
  function commit(next: string) { onChange(next); setOpen(false); setStart(null); setHover(null); trigger.current?.focus(); }
  function changeOpen(next: boolean) {
    if (disabled) return;
    setOpen(next); setStart(null); setHover(null);
    if (next) { setMode(initial === '全部' ? modes.find(item => item !== '全部') ?? '月' : initial); setYear(/^\d{4}/.test(value) ? Number(value.slice(0, 4)) : Number(currentMonth().slice(0, 4))); requestAnimationFrame(() => panel.current?.querySelector<HTMLElement>('.ant-segmented input:checked,button[aria-pressed="true"],button')?.focus()); }
  }
  function chooseMonth(month: number) {
    if (available === '跨月') {
      if (start === null) { setStart(month); setHover(month); }
      else commit(`${year}-${pad(Math.min(start, month) + 1)}~${year}-${pad(Math.max(start, month) + 1)}`);
    } else commit(`${year}-${pad(month + 1)}`);
  }
  const selectedRange = modeOf(value) === '跨月' && Number(value.slice(0, 4)) === year ? [Number(value.slice(5, 7)) - 1, Number(value.slice(13, 15)) - 1] : null;
  const endpoint = hover ?? start;
  const yearsStart = Math.floor(year / 10) * 10 - 1;
  const popup = <div ref={panel} role="dialog" aria-label={`${label}选择`} className="business-period-panel" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); setOpen(false); trigger.current?.focus(); } }}>
    {modes.length > 1 && <Segmented aria-label={`${label}模式`} value={available} options={[...modes]} block onChange={next => { setStart(null); setHover(null); if (next === '全部') commit('全部'); else setMode(next as TimeMode); }} />}
    <div className="business-period-year"><Button aria-label={available === '年' ? '前十年' : '上一年'} type="text" disabled={start !== null} onClick={() => setYear(year - (available === '年' ? 10 : 1))}>‹</Button><strong aria-live="polite">{available === '年' ? `${yearsStart + 1} — ${yearsStart + 10}` : `${year} 年`}</strong><Button aria-label={available === '年' ? '后十年' : '下一年'} type="text" disabled={start !== null} onClick={() => setYear(year + (available === '年' ? 10 : 1))}>›</Button></div>
    {available === '年' ? <div className="business-period-years">{Array.from({ length: 12 }, (_, index) => yearsStart + index).map(item => <Button key={item} type={value === String(item) ? 'primary' : 'text'} onClick={() => commit(String(item))}>{item}</Button>)}</div> : <Calendar mode="year" fullscreen={false} value={dayjs(`${year}-01-01`)} headerRender={() => null}
      onSelect={(date, info) => { if (info.source === 'month') chooseMonth(date.month()); }}
      fullCellRender={(date, info) => {
        if (info.type !== 'month') return info.originNode;
        const month = date.month();
        const range = start === null ? selectedRange : [Math.min(start, endpoint!), Math.max(start, endpoint!)];
        const selected = range ? month === range[0] || month === range[1] : modeOf(value) === '月' && value === `${year}-${pad(month + 1)}`;
        return <Button type="text" aria-label={`${year}年${month + 1}月`} aria-pressed={selected} className={`business-period-month${selected ? ' is-selected' : ''}${range && month >= range[0]! && month <= range[1]! ? ' in-range' : ''}`} onMouseEnter={() => { if (start !== null) setHover(month); }} onFocus={() => { if (start !== null) setHover(month); }} onClick={event => { event.stopPropagation(); chooseMonth(month); }}>{month + 1}月</Button>;
      }} />}
    <div className="business-period-footer"><span aria-live="polite">{available === '跨月' ? start === null ? '选择起月，再选择止月' : `已选 ${start + 1} 月，请选止月` : '选择即生效'}</span><Button type="link" onClick={() => commit(currentMonth())}>本月</Button></div>
  </div>;
  return <Popover trigger="click" open={open && !disabled} onOpenChange={changeOpen} content={popup} placement="bottomLeft" classNames={{ root: 'business-period-popover ag-custom-component-popup' }} getPopupContainer={trigger => trigger.closest<HTMLElement>('.ant-modal-container') ?? document.body}>
    <Button ref={trigger} className="business-period-trigger" disabled={disabled} aria-label={label} aria-haspopup="dialog" aria-expanded={open}>{timeLabel(value)}<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg></Button>
  </Popover>;
}
