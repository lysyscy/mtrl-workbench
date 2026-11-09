import Button from 'antd/es/button';
import type { ReactNode } from 'react';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';

export function OilDeleteDialog({ title, children, busy, disabled, error, close, submit }: {
  title: string; children: ReactNode; busy: boolean; disabled: boolean; error: string;
  close: () => void; submit: () => void;
}) {
  const closing = useDialogClose({ busy, dirty: false, close });
  const titleId = 'oilcard-delete-title';
  return <BusinessModal open className="oilcard-delete-dialog" titleId={titleId} requestClose={closing.requestClose}>
    <DialogContents title={title} titleId={titleId} closing={closing}>
      {children}
      {error && <p role="alert" className="notice">{error}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={closing.requestClose}>取消</Button>
        <Button type="primary" danger disabled={busy || disabled} onClick={submit}>确认删除</Button></div>
    </DialogContents>
  </BusinessModal>;
}
