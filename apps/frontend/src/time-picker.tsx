import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import './time-picker.css';

export type TimeMode = '月' | '跨月' | '年' | '季度' | '周' | '全部';
export interface TimeRange { dateFrom: string; dateTo: string }
export interface TimePickerProps {
  value: string;
  onChange: (value: string) => void;
  modes: readonly TimeMode[];
  disabled?: boolean;
  label?: string;
}
const allModes: readonly TimeMode[] = ['月', '跨月', '年', '季度', '周', '全部'];
const pad = (n: number) => String(n).padStart(2, '0');
const dateText = (date: Date) => `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
const monthEnd = (month: string) => dateText(new Date(Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5)), 0)));
function today() {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  return `${parts.find(p => p.type === 'year')!.value}-${parts.find(p => p.type === 'month')!.value}-${parts.find(p => p.type === 'day')!.value}`;
}
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
function weeksOfQuarter(year: number, quarter: number) {
  const date = new Date(`${monday(`${year}-${pad(quarter * 3 - 2)}-01`)}T00:00:00Z`);
  const end = new Date(Date.UTC(year, quarter * 3, 0)), weeks: TimeRange[] = [];
  for (; date <= end; date.setUTCDate(date.getUTCDate() + 7)) {
    const start = dateText(date), last = new Date(date);
    last.setUTCDate(last.getUTCDate() + 6);
    weeks.push({ dateFrom: start, dateTo: dateText(last) });
  }
  return weeks;
}

export function TimePicker({ value, onChange, modes, disabled = false, label = '时间' }: TimePickerProps) {
  const id = useId(), trigger = useRef<HTMLButtonElement>(null), panel = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false), [mode, setMode] = useState<TimeMode>('月');
  const [year, setYear] = useState(Number(today().slice(0, 4))), [quarter, setQuarter] = useState(1), [start, setStart] = useState('');
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const available = allModes.filter(item => modes.includes(item));
  function close() { panel.current?.hidePopover(); }
  function choose(next: string) { if (disabled) return; onChange(next); close(); trigger.current?.focus(); }
  function show() {
    if (open) { close(); return; }
    const day = today(), selected = modeOf(value);
    setMode(available.includes(selected) ? selected : available[0] ?? '月');
    setYear(Number(value.slice(0, 4)) || Number(day.slice(0, 4)));
    setQuarter(selected === '季度' ? Number(value.slice(5)) : Math.ceil(Number((selected === '周' || selected === '月' ? value : day).slice(5, 7)) / 3));
    setStart(''); panel.current?.showPopover();
  }
  useEffect(() => { if (disabled) panel.current?.hidePopover(); }, [disabled]);
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const anchor = trigger.current?.getBoundingClientRect(), pop = panel.current?.getBoundingClientRect();
      if (!anchor || !pop) return;
      const gap = 6, viewport = document.documentElement.clientWidth;
      setPosition({ left: Math.max(gap, Math.min(anchor.left, viewport - pop.width - gap)), top: Math.max(gap, Math.min(anchor.bottom + gap, window.innerHeight - pop.height - gap)) });
    };
    place(); window.addEventListener('resize', place); window.addEventListener('scroll', place, true);
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); };
  }, [open, mode, start, quarter, year]);
  const yearHead = <div className="time-picker-year"><button type="button" aria-label="上一年" disabled={year <= 1000} onClick={() => { setYear(year - 1); setStart(''); }}><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m10 3-5 5 5 5" /></svg></button><strong>{year} 年</strong><button type="button" aria-label="下一年" disabled={year >= 9995} onClick={() => { setYear(year + 1); setStart(''); }}><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m6 3 5 5-5 5" /></svg></button></div>;
  function pickMonth(next: string) {
    if (mode !== '跨月') { choose(next); return; }
    if (!start || next < start) { setStart(next); return; }
    choose(`${start}~${next}`);
  }
  const rangeParts = modeOf(value) === '跨月' ? value.split('~') : [];
  return <span className="time-picker"><button ref={trigger} type="button" className="time-picker-trigger" aria-label={`${label}：${timeLabel(value)}`} aria-expanded={open} aria-controls={id} disabled={disabled || !available.length} onClick={show}><span>{timeLabel(value)}</span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg></button>
    <div ref={panel} id={id} popover="auto" role="group" aria-label={`选择${label}`} className="time-picker-panel" style={position} onToggle={event => setOpen(event.newState === 'open')}>
      {available.length > 1 && <div className="time-picker-modes">{available.map(item => <button key={item} type="button" aria-pressed={mode === item} onClick={() => { if (item === '全部') choose('全部'); else { setMode(item); setStart(''); } }}>{item}</button>)}</div>}
      {mode !== '全部' && yearHead}
      {(mode === '月' || mode === '跨月') && <>{mode === '跨月' && <p className="time-picker-hint">先选起月，再选止月（同一年）</p>}<div className="time-picker-grid">{Array.from({ length: 12 }, (_, index) => {
        const month = `${year}-${pad(index + 1)}`, selected = mode === '月' ? value === month : start ? start === month : rangeParts.length === 2 && month >= rangeParts[0]! && month <= rangeParts[1]!;
        return <button key={month} type="button" aria-pressed={selected} onClick={() => pickMonth(month)}>{index + 1}月</button>;
      })}</div>{start && <p className="time-picker-hint" role="status">起月 {start}，请选择止月</p>}</>}
      {mode === '年' && <div className="time-picker-grid time-picker-years">{Array.from({ length: 9 }, (_, index) => year - 4 + index).map(item => <button key={item} type="button" aria-pressed={value === String(item)} onClick={() => choose(String(item))}>{item}</button>)}</div>}
      {mode === '季度' && <div className="time-picker-grid">{[1, 2, 3, 4].map(item => <button key={item} type="button" aria-pressed={value === `${year}Q${item}`} onClick={() => choose(`${year}Q${item}`)}>Q{item}</button>)}</div>}
      {mode === '周' && <><div className="time-picker-grid">{[1, 2, 3, 4].map(item => <button key={item} type="button" aria-pressed={quarter === item} onClick={() => setQuarter(item)}>Q{item}</button>)}</div><div className="time-picker-weeks">{weeksOfQuarter(year, quarter).map(week => <button key={week.dateFrom} type="button" aria-pressed={value === week.dateFrom} onClick={() => choose(week.dateFrom)}>{week.dateFrom} ~ {week.dateTo}</button>)}</div></>}
      {mode === '全部' && <button type="button" onClick={() => choose('全部')}>全部时间</button>}
      <div className="time-picker-quick">{available.includes('月') && <button type="button" onClick={() => choose(today().slice(0, 7))}>本月</button>}{mode === '季度' && <button type="button" onClick={() => { const day = today(); choose(`${day.slice(0, 4)}Q${Math.ceil(Number(day.slice(5, 7)) / 3)}`); }}>本季</button>}{mode === '周' && <button type="button" onClick={() => choose(monday(today()))}>本周</button>}<button type="button" onClick={close}>关闭</button></div>
    </div>
  </span>;
}
