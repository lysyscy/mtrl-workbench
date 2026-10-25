import { useEffect, useRef, useState } from 'react';
import type { CSSProperties, KeyboardEvent } from 'react';
import Button from 'antd/es/button';
import { record, requestJson } from './api';
import { useDialogClose } from './dialog-close';
import './appearance-preferences.css';

type Palette = { name: string; label: string; description: string; scene: string; vars: Record<string, string> };
type Scale = { key: string; label: string; css: string };
interface Preferences { theme: string; themes: string[]; palette: Palette[]; ui_scale: string; scales: Scale[] }
const previewRoles = ['--bg', '--sf', '--sf2', '--bd', '--bd2', '--tx', '--tx2', '--pri', '--sel', '--sb', '--sb-tx', '--sb-on'];
function validPalette(item: unknown): item is Palette {
  if (!record(item)) return false;
  const vars = item.vars;
  return ['name', 'label', 'description', 'scene'].every(key => typeof item[key] === 'string') && record(vars) && Object.values(vars).every(value => typeof value === 'string') && previewRoles.every(key => typeof vars[key] === 'string' && vars[key]);
}
function readPreferences(data: unknown): Preferences {
  if (!record(data) || typeof data.theme !== 'string' || !Array.isArray(data.themes) || !data.themes.every(x => typeof x === 'string') || !Array.isArray(data.palette) || !data.palette.every(validPalette) || typeof data.ui_scale !== 'string' || !Array.isArray(data.scales) || !data.scales.every(x => record(x) && typeof x.key === 'string' && typeof x.label === 'string' && typeof x.css === 'string' && /^1(?:\.\d+)?$/.test(x.css))) throw new Error('外观选项读取不完整，请重试。');
  const result = data as unknown as Preferences;
  if (!result.palette.length || result.palette.length !== result.themes.length || !result.themes.every((name, i) => result.palette[i]?.name === name) || !result.themes.includes(result.theme) || !result.scales.some(item => item.key === result.ui_scale)) throw new Error('外观选项读取不完整，请重试。');
  return result;
}
async function loadPreferences(signal: AbortSignal) {
  return readPreferences(await requestJson('/api/m15/theme?surface=react', { signal }));
}
function Check() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg>;
}
function ThemePreview({ palette }: { palette: Palette }) {
  return <span className="appearance-mini" style={palette.vars as CSSProperties} aria-hidden="true"><span className="appearance-mini-nav"><i /><i /><i className="is-active" /><i /></span><span className="appearance-mini-body"><span className="appearance-mini-head"><i /><b /></span><span className="appearance-mini-sheet"><span className="appearance-mini-th" /><span className="appearance-mini-row"><i /><b>12,345.67</b></span><span className="appearance-mini-row is-selected"><i /><b>8,560.00</b></span><span className="appearance-mini-row"><i /><b>780.00</b></span></span></span></span>;
}

export function AppearancePreferences({ close, saved, compact }: { close: () => void; saved: () => Promise<void>; compact: boolean }) {
  const [options, setOptions] = useState<Preferences | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [needsReadback, setNeedsReadback] = useState(false);
  const inFlight = useRef(false), life = useRef<AbortController | null>(null);
  const panel = useRef<HTMLElement>(null), closeButton = useRef<HTMLButtonElement>(null);
  const closing = useDialogClose({ dirty: false, busy: Boolean(busy), close });
  useEffect(() => {
    const controller = new AbortController(); life.current = controller;
    const trigger = document.querySelector<HTMLButtonElement>('.account-pill');
    closeButton.current?.focus();
    void loadPreferences(controller.signal).then(next => { if (!controller.signal.aborted) setOptions(next); }).catch(failure => {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : '外观读取失败，请重试。');
    });
    return () => { controller.abort(); requestAnimationFrame(() => { if (trigger?.isConnected) trigger.focus(); }); };
  }, []);
  useEffect(() => {
    if (compact && !panel.current?.contains(document.activeElement)) closeButton.current?.focus();
  }, [compact]);
  async function reload() {
    const controller = life.current;
    if (!controller || inFlight.current) return;
    inFlight.current = true; setBusy('正在重新读取…'); setError('');
    try {
      const next = await loadPreferences(controller.signal);
      if (controller.signal.aborted) return;
      setOptions(next); await saved();
      if (!controller.signal.aborted) { setNeedsReadback(false); setFeedback('已重新读取当前账号设置。'); }
    } catch (failure) {
      if (!controller.signal.aborted) { setError(failure instanceof Error ? failure.message : '外观读取失败，请重试。'); setNeedsReadback(true); }
    } finally { inFlight.current = false; if (!controller.signal.aborted) setBusy(''); }
  }
  async function change(field: 'theme' | 'ui_scale', value: string, label: string) {
    const controller = life.current;
    if (!controller || controller.signal.aborted || inFlight.current || needsReadback || !options || options[field] === value) return;
    inFlight.current = true; setBusy(`正在保存「${label}」…`); setError(''); setFeedback('');
    let confirmed = false;
    try {
      const response = await requestJson(field === 'theme' ? '/api/m15/theme' : '/api/m15/ui-scale', { method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ [field]: value }) });
      if (!record(response) || response.ok !== true) throw new Error('保存回执不完整。');
      confirmed = true;
      const next = await loadPreferences(controller.signal);
      if (controller.signal.aborted) return;
      if (next[field] !== value) throw new Error('当前设置已变化，请重新读取后核对。');
      setOptions(next); await saved();
      if (!controller.signal.aborted) setFeedback(`已保存「${label}」，仅影响当前账号。`);
    } catch (failure) {
      if (!controller.signal.aborted) {
        setNeedsReadback(true);
        setError(`${confirmed ? '已收到保存成功回执，但重读未完成' : '保存结果未确认'}；请重新读取后再选择。${failure instanceof Error ? failure.message : ''}`);
      }
    } finally { inFlight.current = false; if (!controller.signal.aborted) setBusy(''); }
  }
  function groupKeys(event: KeyboardEvent<HTMLDivElement>, field: 'theme' | 'ui_scale') {
    if (!options || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    if (inFlight.current || needsReadback) return;
    const entries = field === 'theme' ? options.palette.map(item => ({ value: item.name, label: item.label })) : options.scales.map(item => ({ value: item.key, label: item.label }));
    const current = entries.findIndex(item => item.value === options[field]);
    const index = event.key === 'Home' ? 0 : event.key === 'End' ? entries.length - 1 : (current + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1) + entries.length) % entries.length;
    const next = entries[index];
    if (!next) return;
    event.currentTarget.querySelectorAll<HTMLButtonElement>('[role=radio]')[index]?.focus();
    void change(field, next.value, next.label);
  }
  function panelKeys(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closing.requestClose(); }
    if (event.key !== 'Tab' || !compact) return;
    const elements = [...(panel.current?.querySelectorAll<HTMLElement>('button,a[href],[tabindex]') ?? [])].filter(el => el.tabIndex >= 0 && !el.hasAttribute('disabled'));
    const first = elements[0], last = elements.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }
  const unavailable = Boolean(busy) || needsReadback;
  return <aside ref={panel} className="appearance-dialog appearance-panel" role="dialog" aria-modal={compact} aria-labelledby="appearance-title" aria-busy={Boolean(busy)} onKeyDown={panelKeys}>
    <div className="appearance-heading"><div><h2 id="appearance-title">外观与字号</h2><p>点击即保存，仅影响当前账号</p></div><button type="button" ref={closeButton} className="appearance-close" aria-label="收起外观面板" disabled={Boolean(busy)} onClick={closing.requestClose}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button></div>
    <div className="appearance-body">
      {options ? <><div className="appearance-section-title"><h3>配色主题</h3><span>{options.themes.length} 套完整界面</span></div><div className="appearance-theme-choices" role="radiogroup" aria-label="配色主题" onKeyDown={event => groupKeys(event, 'theme')}>
        {options.palette.map(item => <button type="button" role="radio" aria-label={`${item.label}主题`} aria-checked={options.theme === item.name} aria-disabled={unavailable} tabIndex={options.theme === item.name ? 0 : -1} key={item.name} className={`appearance-choice ${options.theme === item.name ? 'is-selected' : ''}`} onClick={() => void change('theme', item.name, item.label)}><ThemePreview palette={item} /><span className="appearance-choice-title">{item.label}<span className="appearance-check">{options.theme === item.name && <Check />}</span></span><span className="appearance-description">{item.description}</span></button>)}
      </div><div className="appearance-section-title appearance-size-heading"><h3>界面大小</h3><span>文字、控件和行高一起变化</span></div><div className="appearance-scale-choices" role="radiogroup" aria-label="界面字号" onKeyDown={event => groupKeys(event, 'ui_scale')}>
        {options.scales.map(item => <button type="button" role="radio" aria-label={`${item.label}字号`} aria-checked={options.ui_scale === item.key} aria-disabled={unavailable} tabIndex={options.ui_scale === item.key ? 0 : -1} key={item.key} style={{ '--sample-scale': item.css } as CSSProperties} className={`appearance-choice appearance-scale-choice ${options.ui_scale === item.key ? 'is-selected' : ''}`} onClick={() => void change('ui_scale', item.key, item.label)}><span className="appearance-choice-title">{item.label}<small>{Number(item.css)}×</small><span className="appearance-check">{options.ui_scale === item.key && <Check />}</span></span><span className="appearance-size-sample"><span>台账</span><span>1,234.56</span></span><span className="appearance-control-sample">查看明细</span></button>)}
      </div></> : !error && <p role="status">正在读取外观选项…</p>}
    </div>
    <div className="appearance-feedback">{busy ? <p role="status">{busy}</p> : error ? <p role="alert">{error}</p> : <p role="status">{feedback || '选择后立即应用，收起面板可查看完整页面。'}</p>}{!busy && (error || needsReadback) && <Button onClick={() => void reload()}>重新读取</Button>}</div>
  </aside>;
}
