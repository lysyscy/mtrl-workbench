import Button from 'antd/es/button';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { requestFile } from './api';
import { BusinessModal } from './business-modal';
import { useHistoryGuard } from './history';
import { DialogContents, useDialogClose } from './dialog-close';

export function SettlementExport({ url, scope, disabled, paused, children, method = 'GET', onSettled }: { url: string; scope: string; disabled: boolean; paused: boolean; children: ReactNode; method?: 'GET' | 'POST'; onSettled?: () => Promise<boolean> }) {
  const [open, setOpen] = useState(false), [busy,setBusy] = useState(false), [error,setError] = useState('');
  const trigger = useRef<HTMLButtonElement>(null), request = useRef<AbortController | null>(null), lock = useRef(false);
  const state = useRef({ url, paused, disabled }); state.current = { url, paused, disabled };
  const close = () => { setOpen(false); requestAnimationFrame(() => trigger.current?.focus()); };
  const closing = useDialogClose({ busy, dirty: false, close, active: !paused });
  // Keep waiting for a POST that may still be generating and fixing its month.
  useEffect(() => { if (method === 'GET') request.current?.abort(); setOpen(false); setError(''); }, [url, paused, method]);
  useHistoryGuard(`export:${url}`, () => method === 'POST' && lock.current ? '大表文件正在导出，请稍候。' : '');
  useEffect(() => () => request.current?.abort(), []);
  async function download() {
    if (lock.current || disabled || paused) return;
    lock.current = true; setBusy(true); setError('');
    const controller = new AbortController(); request.current = controller;
    try {
      const file = await requestFile(url, controller.signal, method);
      if (controller.signal.aborted || state.current.url !== url || state.current.paused || state.current.disabled) return;
      const object = URL.createObjectURL(file.blob), link = document.createElement('a');
      link.href = object; link.download = file.filename; link.click(); setTimeout(() => URL.revokeObjectURL(object), 1000); close();
    } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : '导出失败，请重试。'); }
    finally {
      // A POST may have fixed the month even when its download response was lost.
      if (method === 'POST' && onSettled && !await onSettled()) close();
      lock.current = false; setBusy(false);
    }
  }
  return <><Button ref={trigger} type="primary" disabled={disabled || paused} onClick={() => { setError(''); setOpen(true); }}>导出文件…</Button>
    {open && <BusinessModal open={!paused} requestClose={closing.requestClose} titleId="settlement-export-title" className="settlement-export-dialog"><DialogContents title={`导出 · ${scope}`} titleId="settlement-export-title" closing={closing}>
      {children}{error && <p className="notice" role="alert">{error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button><Button type="primary" disabled={disabled || paused} loading={busy} onClick={() => void download()}>保存到本地</Button></div>
    </DialogContents></BusinessModal>}
  </>;
}