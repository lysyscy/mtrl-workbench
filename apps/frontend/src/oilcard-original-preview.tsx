import Button from 'antd/es/button';
import Select from 'antd/es/select';
import { useEffect, useRef, useState } from 'react';
import type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { BusinessModal } from './business-modal';
import { DialogContents, useDialogClose } from './dialog-close';
import type { OilInvoice } from './oilcard-invoice-api';

function PreviewPage({ document, pageNumber }: { document: PDFDocumentProxy; pageNumber: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [ready, setReady] = useState(false), [failed, setFailed] = useState(false);
  useEffect(() => {
    const surface = canvas.current;
    if (!surface) return;
    let disposed = false, render: RenderTask | undefined;
    const observer = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return;
      observer.disconnect();
      void document.getPage(pageNumber).then(page => {
        if (disposed) return;
        const paper = page.getViewport({ scale: 1 });
        const viewport = page.getViewport({ scale: 1680 / Math.max(paper.width, paper.height) });
        surface.width = Math.ceil(viewport.width);
        surface.height = Math.ceil(viewport.height);
        render = page.render({ canvas: surface, viewport });
        return render.promise.then(() => { if (!disposed) setReady(true); });
      }).catch(() => { if (!disposed) setFailed(true); });
    }, { rootMargin: '240px' });
    observer.observe(surface);
    return () => { disposed = true; observer.disconnect(); render?.cancel(); };
  }, [document, pageNumber]);
  return <figure className="oilcard-preview-page">
    {document.numPages > 1 && <figcaption>第 {pageNumber} 页</figcaption>}
    {failed && <p role="alert">这一页暂时无法显示。</p>}
    <canvas ref={canvas} role="img" aria-label={`发票原件第 ${pageNumber} 页`} data-ready={ready} hidden={failed} />
  </figure>;
}

export function OilOriginalPreview({ invoice, originalId, onOriginalChange, close, save, saving }: {
  invoice: OilInvoice; originalId: number; onOriginalChange: (id: number) => void;
  close: () => void; save: () => void; saving: boolean;
}) {
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [failed, setFailed] = useState(false), [zoom, setZoom] = useState(false);
  const closing = useDialogClose({ busy: false, dirty: false, close });
  useEffect(() => {
    let disposed = false, loading: PDFDocumentLoadingTask | undefined;
    void import('pdfjs-dist').then(pdf => {
      if (disposed) return;
      pdf.GlobalWorkerOptions.workerSrc = workerUrl;
      loading = pdf.getDocument({ url: '/api/m13/invoices/originals/' + originalId, enableXfa: false });
      return loading.promise.then(result => { if (!disposed) setDocument(result); });
    }).catch(() => { if (!disposed) setFailed(true); });
    return () => { disposed = true; void loading?.destroy().catch(() => {}); };
  }, [originalId]);
  return <BusinessModal open className="oilcard-original-preview" titleId="oilcard-original-preview" requestClose={closing.requestClose}>
    <DialogContents title="发票原件预览" titleId="oilcard-original-preview" closing={closing}>
      <div className="oilcard-preview-toolbar">
        <span>{invoice.invoice_no || '票号待核'}</span>
        {invoice.originals.length > 1 && <Select aria-label="选择发票原件" value={originalId} onChange={onOriginalChange}
          options={invoice.originals.map((file, index) => ({ value: file.id, label: index === 0 ? '主原件' : `原件 ${index + 1}${file.outcome === 'conflict' ? '（待核）' : ''}` }))} />}
        <Button disabled={!document} aria-pressed={zoom} onClick={() => setZoom(value => !value)}>{zoom ? '适合窗口' : '放大'}</Button>
        <Button loading={saving} onClick={save}>保存原件</Button>
      </div>
      <div className="oilcard-preview-stage" tabIndex={0} role="region" aria-label="原件逐页预览" data-zoom={zoom}>
        {failed ? <p className="notice" role="alert">原件暂时无法预览，可保存后查看。</p> :
          document ? Array.from({ length: document.numPages }, (_, index) =>
            <PreviewPage key={index} document={document} pageNumber={index + 1} />) : <p role="status">正在读取原件…</p>}
      </div>
    </DialogContents>
  </BusinessModal>;
}
