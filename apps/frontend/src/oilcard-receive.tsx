import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { uncertainWrite } from './api';
import { BusinessGrid } from './business-grid';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import { contentWidth } from './grid';
import { randomUUID } from './random-id';
import { createDeliveryBatch, deliveryLabels, findDeliveryBatch, getDeliveryBatch, getDeliveryBatches, runDeliveryItem } from './oilcard-batch-api';
import type { DeliveryBatch, DeliveryItem } from './oilcard-batch-api';

const BatchActions = createContext<{ disabled: boolean; open: (item: DeliveryItem) => void }>({ disabled: true, open: () => {} });
function InvoiceAction({ data }: ICellRendererParams<DeliveryItem>) {
  const state = useContext(BatchActions);
  return data?.invoice_id ? <Button size="small" disabled={state.disabled} onClick={() => state.open(data)}>核对发票</Button> : '';
}
export function OilReceiveDialog({ active, disabled, scale, close, onUpdated, onOpenInvoice, onLock, onUncertain }: {
  active: boolean; disabled: boolean; scale: number; close: () => void; onUpdated: () => Promise<unknown>;
  onOpenInvoice: (item: DeliveryItem) => void; onLock: (value: boolean) => void; onUncertain: (value: boolean) => void;
}) {
  const client = useQueryClient(), [links, setLinks] = useState(''), [selected, setSelected] = useState(0);
  const [busy, setBusy] = useState(false), [unknown, setUnknown] = useState<'create' | 'run' | null>(null), [error, setError] = useState('');
  const requestId = useRef(randomUUID()), request = useRef<AbortController | null>(null), alive = useRef(true), opening = useRef<DeliveryItem | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; request.current?.abort(); onLock(false); onUncertain(false); }; }, [onLock, onUncertain]);
  useEffect(() => { if (!active || disabled) request.current?.abort(); }, [active, disabled]);
  useEffect(() => { onLock(busy || Boolean(unknown)); onUncertain(Boolean(unknown)); }, [busy, unknown, onLock, onUncertain]);
  const recent = useQuery({ queryKey: ['oilcard-delivery-batches'], enabled: active && !disabled, queryFn: ({ signal }) => getDeliveryBatches(signal) });
  useEffect(() => { if (!selected && recent.data?.[0]) setSelected(recent.data[0].id); }, [selected, recent.data]);
  const query = useQuery({ queryKey: ['oilcard-delivery-batch', selected], enabled: active && !disabled && selected > 0, queryFn: ({ signal }) => getDeliveryBatch(selected, signal) });
  const current = useRef(query.data); current.current = query.data;
  const baseClosing = useDialogClose({ busy: busy || Boolean(unknown), dirty: Boolean(links.trim()), close: () => { close(); if (opening.current) onOpenInvoice(opening.current); } });
  const closing = { ...baseClosing, resume: () => { opening.current = null; baseClosing.resume(); } };
  const blocked = disabled || !active || busy || Boolean(unknown);
  function publish(batch: DeliveryBatch) { current.current = batch; setSelected(batch.id); client.setQueryData(['oilcard-delivery-batch', batch.id], batch); }
  async function process(batch: DeliveryBatch, signal: AbortSignal) {
    for (const item of batch.items) {
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
      if (!item.can_run) continue;
      const updated = await runDeliveryItem(batch.id, item.id, signal);
      if (!alive.current || signal.aborted) return;
      publish(updated);
    }
  }
  async function start(create: boolean) {
    if (blocked || create && !links.trim()) return;
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setError(''); let phase: 'create' | 'run' = create ? 'create' : 'run', acknowledged = false;
    try {
      let batch = current.current;
      if (create) { batch = await createDeliveryBatch(requestId.current, links, controller.signal); if (!alive.current) return; publish(batch); setLinks(''); requestId.current = randomUUID(); phase = 'run'; }
      if (!batch) return;
      await process(batch, controller.signal);
      if (!alive.current || controller.signal.aborted) return;
      acknowledged = true;
      await onUpdated(); await recent.refetch();
    } catch (failure) {
      if (!alive.current) return;
      if (uncertainWrite(failure)) setUnknown(phase);
      setError((acknowledged ? '本次条目已取得回执，台账重读失败。' : '') + (failure instanceof Error ? failure.message : '收票未完成，请重新读取核对。'));
    } finally { if (alive.current) setBusy(false); }
  }
  async function reread() {
    if (busy || disabled || !active) return;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError('');
    try {
      if (unknown === 'create') {
        const batch = await findDeliveryBatch(requestId.current, controller.signal);
        if (!alive.current || controller.signal.aborted) return;
        if (batch) { publish(batch); setLinks(''); requestId.current = randomUUID(); }
        else setError('已核对，本次批次尚未建立，可使用保留链接重新建立。');
      } else if (selected) {
        const batch = await getDeliveryBatch(selected, controller.signal);
        if (!alive.current || controller.signal.aborted) return;
        publish(batch);
      }
      await onUpdated(); await recent.refetch();
      if (alive.current && !controller.signal.aborted) setUnknown(null);
    } catch (failure) { if (alive.current) setError(failure instanceof Error ? failure.message : '批次重读失败，请稍后重试。'); }
    finally { if (alive.current) setBusy(false); }
  }
  const columns = useMemo<ColDef<DeliveryItem>[]>(() => [
    { field: 'position', headerName: '序号', ...contentWidth(68, 90, scale) },
    { field: 'status', headerName: '处理结果', ...contentWidth(120, 170, scale), valueFormatter: p => deliveryLabels[p.value as DeliveryItem['status']] },
    { field: 'message', headerName: '核对事项', ...contentWidth(280, 650, scale, 1) },
    { field: 'invoice_id', headerName: '发票', ...contentWidth(120, 170, scale), cellRenderer: InvoiceAction },
  ], [scale]);
  return <BusinessModal open className="oilcard-receive-dialog" titleId="oilcard-receive-title" requestClose={closing.requestClose}><DialogContents title="交付链接收票" titleId="oilcard-receive-title" closing={closing}>
    <label>交付链接<Input.TextArea aria-label="交付链接" value={links} disabled={blocked} onChange={e => setLinks(e.target.value)} autoSize={{ minRows: 3, maxRows: 6 }} placeholder="每行一条中石化交付链接，最多100条" /></label>
    <div className="oilcard-toolbar"><Button type="primary" disabled={blocked || !links.trim()} loading={busy} onClick={() => void start(true)}>下载并入账</Button>
      <label>历史批次<Select aria-label="选择收票批次" disabled={blocked || recent.isPending || recent.isError} value={selected || null} showSearch={{ optionFilterProp: 'label' }} options={(recent.data ?? []).map(b => ({ value: b.id, label: `批次 #${b.id}  ${b.created_at.replace('T', ' ').slice(0, 19)}` }))} onChange={setSelected} /></label></div>
    {(error || recent.isError || query.isError) && <p className="notice" role="alert">{error || recent.error?.message || query.error?.message}</p>}
    {unknown && <p className="notice" role="alert">收票结果待核实，请先重新读取本批结果，再续办未完成项。</p>}
    {recent.isPending || selected > 0 && query.isPending ? <p role="status">正在读取收票批次…</p> : query.data ? <BatchActions.Provider value={{ disabled: blocked, open: item => { opening.current = item; closing.requestClose(); } }}><BusinessGrid table="oilcard-delivery-items" label="逐项收票结果" rows={query.data.items} columns={columns} rowId={i => String(i.id)} scale={scale} domLayout="normal" style={{ height: '36dvh', minHeight: '200px' }} /></BatchActions.Provider> : <p className="state">粘贴交付链接后建立批次，逐项结果会保留，可随时回来核对续办。</p>}
    <div className="dialog-actions"><Button disabled={busy || Boolean(unknown)} onClick={closing.requestClose}>关闭</Button><Button disabled={busy || disabled || !active} onClick={() => void reread()}>重新读取并核对</Button><Button disabled={blocked || !query.data?.items.some(i => i.can_run)} onClick={() => void start(false)}>续办未完成项</Button></div>
  </DialogContents></BusinessModal>;
}
