import Button from 'antd/es/button';
import { useEffect, useRef, useState } from 'react';
import { requestFile } from './api';

export function OilTotalExport({ disabled, active }: { disabled: boolean; active: boolean }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const request = useRef<AbortController | null>(null), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; request.current?.abort(); }; }, []);
  useEffect(() => { if (!active) request.current?.abort(); }, [active]);
  async function download() {
    if (disabled || busy || !active) return;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError('');
    try {
      const file = await requestFile('/api/m13/export', controller.signal);
      if (controller.signal.aborted || !alive.current) return;
      const url = URL.createObjectURL(file.blob), link = document.createElement('a');
      link.href = url; link.download = file.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) { if (!controller.signal.aborted && alive.current) setError(failure instanceof Error ? failure.message : '总台账导出失败，请重试。'); }
    finally { if (alive.current) setBusy(false); }
  }
  return <div className="oilcard-total-export"><Button disabled={disabled || busy || !active} loading={busy} title="导出所有已保存数据，不受页面筛选影响" onClick={() => void download()}>导出总台账</Button>{error && <p role="alert" className="notice">{error}</p>}</div>;
}
