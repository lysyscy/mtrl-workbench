"""Expire newly deleted ordinary invoices after their undo record is pruned."""
from datetime import datetime
import json

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.db import session_scope
from app.core.history import OperationHistory
from .models import (OilContinuationSource, OilDeliveryBatch, OilDeliveryItem, OilDeliveryLink,
                     OilInvoice, OilInvoiceAllocation, OilInvoiceNumber, OilInvoiceOriginal, OilInvoiceRetirement)
from .service import _lock


def protected_invoice(session, invoice_id):
    if session.scalar(select(OilInvoice.id).where(OilInvoice.related_invoice_id == invoice_id).limit(1)):
        return True
    originals = set(session.scalars(select(OilInvoiceOriginal.id).where(OilInvoiceOriginal.invoice_id == invoice_id)))
    return any(
        (target['kind'] == 'invoice' and target['id'] == invoice_id)
        or (target['kind'] == 'pdf' and target['id'] in originals)
        for raw in session.scalars(select(OilContinuationSource.confirmations_json))
        for receipt in json.loads(raw).values()
        for target in receipt['targets']
    )


def record_deletion(session, operation):
    if operation.label != '删除油卡本地发票登记':
        return
    for change in operation.changes:
        before, after = change['before'], change['after']
        if (change['table'] == OilInvoice.__tablename__ and before and after and not before['deleted']
                and after['deleted'] and after['kind'] == 'normal' and after['status'] != 'voided'
                and not protected_invoice(session, change['id'])):
            record = insert(OilInvoiceRetirement).values(invoice_id=change['id'], operation_id=operation.id)
            session.execute(record.on_conflict_do_update(
                index_elements=[OilInvoiceRetirement.invoice_id], set_={'operation_id': operation.id},
            ))


def purge_expired():
    with session_scope() as session:
        session.connection().exec_driver_sql("SET LOCAL statement_timeout = '10s'")
        ready = select(OilInvoiceRetirement).where(~select(OperationHistory.id).where(
            OperationHistory.id == OilInvoiceRetirement.operation_id,
        ).exists()).order_by(OilInvoiceRetirement.invoice_id).limit(100)
        if not session.scalar(select(ready.exists())):
            return
        _lock(session)
        for retirement in session.scalars(ready):
            invoice = session.get(OilInvoice, retirement.invoice_id, with_for_update=True)
            if invoice and invoice.deleted and _link_in_progress(session, invoice.id):
                continue
            session.delete(retirement)
            if invoice and invoice.deleted and not protected_invoice(session, invoice.id):
                _purge(session, invoice.id)
                session.delete(invoice)


def _link_in_progress(session, invoice_id):
    from .invoice_batches import LEASE
    return session.scalar(select(OilDeliveryLink.id).join(
        OilInvoiceOriginal, OilInvoiceOriginal.id == OilDeliveryLink.original_id,
    ).where(OilInvoiceOriginal.invoice_id == invoice_id, OilDeliveryLink.state == 'running',
            OilDeliveryLink.claimed_at >= datetime.now() - LEASE).limit(1)) is not None


def _purge(session, invoice_id):
    originals = select(OilInvoiceOriginal.id).where(OilInvoiceOriginal.invoice_id == invoice_id)
    links = select(OilDeliveryLink.id).where(OilDeliveryLink.original_id.in_(originals))
    removed = set(session.scalars(delete(OilDeliveryItem).where(
        OilDeliveryItem.link_id.in_(links),
    ).returning(OilDeliveryItem.batch_id)))
    if removed:
        for batch_id in removed:
            remaining = list(session.scalars(select(OilDeliveryItem).where(
                OilDeliveryItem.batch_id == batch_id,
            ).order_by(OilDeliveryItem.position)))
            if not remaining:
                session.execute(delete(OilDeliveryBatch).where(OilDeliveryBatch.id == batch_id))
            for position, item in enumerate(remaining, 1):
                if item.position != position:
                    session.execute(update(OilDeliveryItem).where(OilDeliveryItem.id == item.id).values(position=position))
    session.execute(delete(OilDeliveryLink).where(OilDeliveryLink.original_id.in_(originals)))
    for model in (OilInvoiceOriginal, OilInvoiceNumber, OilInvoiceAllocation):
        session.execute(delete(model).where(model.invoice_id == invoice_id))
