import Button from 'antd/es/button';
import { useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { readI8KickConfirmation, revokeI8KickToken } from './i8-api';

interface Confirmation {
  scope: object;
  token: string;
  message: string;
  retry: () => Promise<void>;
}

export function useI8KickConfirmation(scopeKey: string) {
  const scope = useMemo(() => ({scopeKey}), [scopeKey]);
  const active = useRef<object | null>(null);
  const pending = useRef<Confirmation | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [revocationNotice, setRevocationNotice] = useState('');
  function takePending() {
    const next = pending.current;
    pending.current = null;
    return next?.token ?? '';
  }

  useLayoutEffect(() => {
    active.current = scope;
    setRevocationNotice('');
    return () => { active.current = null; void revokeI8KickToken(takePending()); };
  }, [scope]);

  function offer(failure: unknown, retry: (token: string) => Promise<void>): boolean {
    const conflict = readI8KickConfirmation(failure);
    if (!conflict) return false;
    if (active.current === scope) {
      void revokeI8KickToken(takePending());
      setRevocationNotice('');
      const next = {scope, ...conflict, retry: () => retry(conflict.token)};
      pending.current = next;
      setConfirmation(next);
    } else void revokeI8KickToken(conflict.token);
    return true;
  }

  async function cancel() {
    const token = takePending();
    setConfirmation(null);
    const notice = await revokeI8KickToken(token);
    if (notice && active.current === scope) setRevocationNotice(notice);
  }

  function dismiss() {
    active.current = null;
    setConfirmation(null);
    void revokeI8KickToken(takePending());
  }

  function confirm() {
    const next = pending.current;
    if (!next || next.scope !== active.current) return;
    pending.current = null;
    setConfirmation(null);
    void next.retry();
  }

  return {message: confirmation?.scope === scope ? confirmation.message : '', revocationNotice, offer, confirm, cancel, dismiss};
}

export function I8KickConfirmationActions({message, confirm, cancel, disabled}: {
  message: string; confirm: () => void; cancel: () => Promise<void>; disabled: boolean;
}) {
  const messageId = useId();
  return <>
    <p id={messageId} className="notice" role="status">{message}</p>
    <div className="dialog-actions">
      <Button htmlType="button" aria-describedby={messageId} autoFocus onClick={() => void cancel()}>取消下线确认</Button>
      <Button htmlType="button" type="primary" danger disabled={disabled} onClick={confirm}>让现有会话下线并继续</Button>
    </div>
  </>;
}
