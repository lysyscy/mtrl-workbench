import Button from 'antd/es/button';
import Select from 'antd/es/select';
import { useEffect, useState } from 'react';
import { record, requestJson } from './api';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';

interface Preferences { theme: string; themes: string[]; ui_scale: string; scales: { key: string; label: string }[] }
function readPreferences(data: unknown): Preferences {
  if (!record(data) || typeof data.theme !== 'string' || !Array.isArray(data.themes) || !data.themes.every(x => typeof x === 'string') || typeof data.ui_scale !== 'string' || !Array.isArray(data.scales) || !data.scales.every(x => record(x) && typeof x.key === 'string' && typeof x.label === 'string')) throw new Error('外观选项读取不完整，请重试。');
  return data as unknown as Preferences;
}

export function AppearancePreferences({ close, saved }: { close: () => void; saved: () => Promise<void> }) {
  const [options, setOptions] = useState<Preferences | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const closing = useDialogClose({ dirty: false, busy, close });
  useEffect(() => {
    const controller = new AbortController();
    void requestJson('/api/m15/theme', { signal: controller.signal }).then(data => setOptions(readPreferences(data))).catch(failure => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : '外观读取失败，请重新打开。'); });
    return () => controller.abort();
  }, []);
  async function change(field: 'theme' | 'ui_scale', value: string) {
    if (busy || !options) return;
    setBusy(true); setError('');
    try {
      await requestJson(field === 'theme' ? '/api/m15/theme' : '/api/m15/ui-scale', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ [field]: value }) });
      setOptions({ ...options, [field]: value });
      await saved();
    } catch (failure) { setError(failure instanceof Error ? failure.message : '外观保存失败，请重试。'); }
    finally { setBusy(false); }
  }
  return <BusinessModal open className="project-dialog appearance-dialog" titleId="appearance-title" requestClose={closing.requestClose}><DialogContents title="外观与字号" titleId="appearance-title" closing={closing}>
    {options ? <div className="appearance-fields"><label>配色主题<Select aria-label="配色主题" value={options.theme} disabled={busy} options={options.themes.map(value => ({ value, label: value }))} onChange={value => void change('theme', value)} /></label><label>界面字号<Select aria-label="界面字号" value={options.ui_scale} disabled={busy} options={options.scales.map(option => ({ value: option.key, label: option.label }))} onChange={value => void change('ui_scale', value)} /></label><p>选择后立即保存，仅影响当前账号。</p></div> : !error && <p role="status">正在读取外观选项…</p>}
    {error && <p className="notice" role="alert">{error}</p>}{busy && <p role="status">正在保存…</p>}
    <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>关闭</Button></div>
  </DialogContents></BusinessModal>;
}
