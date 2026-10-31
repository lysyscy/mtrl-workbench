import Input from 'antd/es/input';
import DatePicker from 'antd/es/date-picker';
import dayjs from 'dayjs';

export function OilDateText({ label, value, disabled, change, save }: { label: string; value: string; disabled: boolean; change: (value: string, commit: boolean) => void; save: () => void }) {
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) && dayjs(value).isValid() && dayjs(value).format('YYYY-MM-DD') === value ? dayjs(value) : null;
  return <div className="oilcard-date-text"><Input aria-label={label} value={value} disabled={disabled} placeholder="日期、文字或留空" onChange={e => change(e.target.value, false)} onBlur={save} onKeyDown={e => { if (!e.nativeEvent.isComposing && e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }} />
    <DatePicker aria-label={`选择${label}`} title="选择日期" value={date} inputReadOnly allowClear={false} disabled={disabled} format={() => ''} placeholder="" className="oilcard-calendar" classNames={{ popup: { root: 'ag-custom-component-popup' } }} onChange={next => { if (next) change(next.format('YYYY-MM-DD'), true); }} /></div>;
}
