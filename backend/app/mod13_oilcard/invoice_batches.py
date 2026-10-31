"""Durable item-by-item coordination; external reads never hold a DB transaction."""
from datetime import datetime, timedelta
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import select

from app.core.db import session_scope
from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from . import delivery, invoices
from .invoice_pdf import recognize_pdf
from .models import OilDeliveryBatch, OilDeliveryItem, OilDeliveryLink, OilInvoiceOriginal
from .service import _get, _lock

LEASE = timedelta(minutes=3)


def create(session, request_id, text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or len(lines) > 100:
        raise MustReportError('每批请粘贴1至100条交付链接，每行一条。')
    fingerprint = sha256(json.dumps(lines, ensure_ascii=False).encode('utf-8')).hexdigest()
    _lock(session)
    existing = session.scalar(select(OilDeliveryBatch).where(OilDeliveryBatch.request_id == request_id))
    if existing:
        if existing.fingerprint != fingerprint:
            raise DataConflictError('这次收票批次已建立且链接内容不同，请先核对原批次。')
        return existing
    batch = OilDeliveryBatch(request_id=request_id, fingerprint=fingerprint, created_by=current_operator())
    session.add(batch); session.flush()
    for position, line in enumerate(lines, 1):
        try:
            token = delivery.link_token(line)
        except delivery.DeliveryError as exc:
            session.add(OilDeliveryItem(batch_id=batch.id, position=position, error=str(exc)))
            continue
        key = sha256(token.encode('utf-8')).hexdigest()
        link = session.scalar(select(OilDeliveryLink).where(OilDeliveryLink.link_key == key))
        reused = link is not None
        if link is None:
            link = OilDeliveryLink(link_key=key, token=token)
            session.add(link); session.flush()
        session.add(OilDeliveryItem(batch_id=batch.id, position=position, link_id=link.id, reused=reused))
    session.flush()
    return batch


def _expired(link):
    return link.claimed_at is None or link.claimed_at < datetime.now() - LEASE


def _item_data(session, item):
    base = {'id': item.id, 'position': item.position, 'invoice_id': None, 'original_id': None}
    if item.link_id is None:
        return {**base, 'status': 'failed', 'message': item.error, 'can_run': False}
    link = session.get(OilDeliveryLink, item.link_id)
    if link.state == 'done' and link.original_id is not None:
        source = session.get(OilInvoiceOriginal, link.original_id)
        outcome = invoices.receipt_outcome(session, source, repeated=item.reused or link.duplicate)
        return {**base, 'invoice_id': source.invoice_id, 'original_id': source.id,
            'status': outcome['receipt_status'], 'message': outcome['receipt_message'], 'can_run': False}
    if link.state == 'running':
        expired = _expired(link)
        return {**base, 'status': 'uncertain' if expired else 'working',
            'message': '上次处理未完成，可核对续办。' if expired else '正在下载或核对，请稍候。', 'can_run': expired}
    return {**base, 'status': 'failed' if link.state == 'failed' else 'queued',
        'message': link.message if link.state == 'failed' else '等待下载', 'can_run': True}


def batch_data(session, batch):
    items = list(session.scalars(select(OilDeliveryItem).where(OilDeliveryItem.batch_id == batch.id).order_by(OilDeliveryItem.position)))
    return {'id': batch.id, 'request_id': batch.request_id, 'created_at': batch.created_at.isoformat(),
        'items': [_item_data(session, item) for item in items]}


def read(session, key):
    batch = session.get(OilDeliveryBatch, key)
    if batch is None:
        raise MustReportError('这批收票不存在，请重新读取批次。')
    return batch_data(session, batch)


def by_request(session, request_id):
    batch = session.scalar(select(OilDeliveryBatch).where(OilDeliveryBatch.request_id == request_id))
    return {'found': batch is not None, 'batch': batch_data(session, batch) if batch else None}


def recent(session):
    return {'batches': [{'id': b.id, 'request_id': b.request_id, 'created_at': b.created_at.isoformat()}
        for b in session.scalars(select(OilDeliveryBatch).order_by(OilDeliveryBatch.id.desc()))]}


def _claim(session, batch_id, item_id):
    _lock(session)
    item = _get(session, OilDeliveryItem, item_id)
    if item.batch_id != batch_id:
        raise MustReportError('收票条目与批次不对应，请重读核对。')
    if item.link_id is None:
        return None
    link = _get(session, OilDeliveryLink, item.link_id)
    if link.state == 'done' or link.state == 'running' and not _expired(link):
        return None
    link.state, link.attempt, link.claimed_at = 'running', str(uuid4()), datetime.now()
    link.message = ''; link.attempts += 1
    session.flush()
    return link.id, link.token, link.attempt


def _complete(session, link_id, attempt, content, recognized):
    _lock(session)
    link = _get(session, OilDeliveryLink, link_id)
    if link.state != 'running' or link.attempt != attempt:
        return False
    digest = sha256(content).hexdigest()
    existing = session.scalar(select(OilInvoiceOriginal.id).where(OilInvoiceOriginal.sha256 == digest))
    source = invoices.receive_pdf(session, content, recognized)
    link.original_id, link.state = source.id, 'done'
    link.duplicate = existing is not None or source.outcome == 'duplicate'
    link.message = ''; session.flush()
    return True


def run(batch_id, item_id):
    with session_scope() as session:
        claim = _claim(session, batch_id, item_id)
    if claim is not None:
        link_id, token, attempt = claim
        try:
            content, expected_number = delivery.download_pdf(token)
            recognized = recognize_pdf(content)
            if recognized['invoice_no'] is not None and recognized['invoice_no'] != expected_number:
                raise delivery.DeliveryError('下载PDF票号与交付信息不一致，请手工上传核对。')
        except delivery.DeliveryError as exc:
            with session_scope() as session:
                _lock(session)
                link = _get(session, OilDeliveryLink, link_id)
                if link.state == 'running' and link.attempt == attempt:
                    link.state, link.message = 'failed', str(exc)
        else:
            # Original archive, accounting and continuation receipt commit together.
            # A lost reply is recovered from this link, never by guessing/reposting.
            with session_scope() as session:
                _complete(session, link_id, attempt, content, recognized)
    with session_scope() as session:
        return read(session, batch_id)
