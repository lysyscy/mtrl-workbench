import { ApiError } from './api';
import type { CellSaveQueue } from './cell-save';
import { matchesManualOilInvoice, saveManualOilInvoice } from './oilcard-invoice-api';
import type { OilInvoice, OilInvoices, OilManualInvoiceFields, OilManualInvoiceIdentity } from './oilcard-invoice-api';
import { randomUUID } from './random-id';

type Run = CellSaveQueue<{ error: string }, OilInvoices>['run'];
type Submission = { identity: OilManualInvoiceIdentity; fields: OilManualInvoiceFields };
type Readback = { status: 'matched' | 'changed'; id: number; message: string } | { status: 'missing'; message: string };
type Recovery = { submission: Submission; phase: 'checking'; canRetry: boolean; readback?: Readback } | { submission: Submission; phase: 'retry' };

export interface OilManualRegistrationForm {
  key: string;
  row: OilInvoice | undefined;
  submit: (fields: OilManualInvoiceFields, run: Run) => Promise<boolean>;
  dismiss: () => void;
}

export class OilManualRegistration {
  private form: OilManualRegistrationForm | null = null;
  private writing: Submission | null = null;
  private recovery: Recovery | null = null;
  private listeners = new Set<() => void>();

  getPhase = () => this.recovery?.phase ?? 'idle';
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  open(row?: OilInvoice): OilManualRegistrationForm | undefined {
    if (this.writing || this.recovery) return;
    let identity: OilManualInvoiceIdentity;
    if (row) {
      if (!row.manual_request_id || row.invoice_no || row.status !== 'registered') return;
      identity = { id: row.id, version: row.version, request_id: row.manual_request_id };
    } else {
      identity = { request_id: randomUUID() };
    }
    const form: OilManualRegistrationForm = {
      key: identity.request_id, row,
      submit: async (fields, run) => {
        if (this.form !== form || this.writing || this.recovery) return false;
        const snapshot = { ...fields, allocations: fields.allocations.map(part => ({ ...part })) };
        const outcome = await this.submit({ identity, fields: snapshot }, run);
        const close = outcome === 'saved' || outcome === 'uncertain';
        if (close) form.dismiss();
        return close;
      },
      dismiss: () => { if (this.form === form) this.form = null; },
    };
    this.form = form;
    return form;
  }

  readBack(invoices: OilInvoice[]): Readback | undefined {
    const recovery = this.recovery?.phase === 'checking' ? this.recovery : null;
    const submission = this.writing ?? recovery?.submission;
    if (!submission) return;

    const { identity, fields } = submission;
    const editing = 'id' in identity;
    const row = invoices.find(row => editing ? row.id === identity.id : row.manual_request_id === identity.request_id);
    let readback: Readback;
    if (!row) {
      let message = '';
      if (editing) message = '台账中未读到这条手工登记，请核对当前台账。';
      else if (recovery?.canRetry === false) message = '原登记重试发生冲突，当前台账未找到此行。请先核对操作历史，避免重复登记。';
      readback = { status: 'missing', message };
    } else if (matchesManualOilInvoice(row, identity, fields)) {
      readback = { status: 'matched', id: row.id, message: editing ? '已在发票台账读到本次修改。' : '已在发票台账读到本次手工登记。' };
    } else {
      readback = { status: 'changed', id: row.id, message: editing ? '已读到原手工登记，当前内容与本次修改不同。' : '已读到本次手工登记，当前内容与本次输入不同。' };
    }
    if (this.writing && readback.status !== 'matched') throw new ApiError('台账尚未读到与本次输入一致的手工登记。');
    if (recovery && !this.writing) recovery.readback = readback;
    return readback;
  }

  confirmRead() {
    const recovery = this.recovery;
    if (recovery?.phase !== 'checking' || !recovery.readback) return;
    this.setRecovery(recovery.canRetry && recovery.readback.status === 'missing'
      ? { phase: 'retry', submission: recovery.submission } : null);
  }

  async retry(run: Run) {
    if (this.recovery?.phase !== 'retry' || this.writing) return;
    await this.submit(this.recovery.submission, run);
  }

  private async submit(submission: Submission, run: Run) {
    const retrying = this.recovery?.phase === 'retry';
    let canRetry = !('id' in submission.identity);
    this.writing = submission;
    try {
      const outcome = await run(async signal => {
        try {
          await saveManualOilInvoice(submission.fields, submission.identity, signal);
        } catch (failure) {
          if (!(retrying && failure instanceof ApiError && failure.status === 409)) throw failure;
          // The first POST may have committed after the read and then been changed or deleted.
          canRetry = false;
          throw new ApiError(failure.message, failure.status, 'invalid_response');
        }
      }, () => '', '手工登记：');
      if (outcome === 'uncertain') this.setRecovery({ phase: 'checking', submission, canRetry });
      else if (outcome !== 'blocked') this.setRecovery(null);
      return outcome;
    } finally {
      this.writing = null;
    }
  }

  private setRecovery(recovery: Recovery | null) {
    const previous = this.getPhase();
    this.recovery = recovery;
    if (previous !== this.getPhase()) for (const listener of this.listeners) listener();
  }
}
