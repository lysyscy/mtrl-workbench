"""Conservative text extraction for the observed Sinopec electronic invoice.

PDF has no semantic layer. Accept only matching plain/layout labelled facts,
with subtotal arithmetic and a complete card number in the remarks. Image-only,
ambiguous and unfamiliar layouts remain evidence for manual confirmation.
"""
from datetime import date
from hashlib import sha256
from io import BytesIO
import re

from pypdf import PdfReader

from app.core.errors import MustReportError
from app.core.money import sum_money, to_money

MAX_PDF_BYTES = 20 * 1024 * 1024


def _only(values):
    unique = set(values)
    return next(iter(unique)) if len(unique) == 1 else None


def _facts(text):
    compact = re.sub(r'[ \t\r\u3000]', '', text).replace('￥', '¥')
    number = _only(re.findall(r'发票号码[:：]\s*(\d{20}|\d{8})(?!\d)', compact))
    dates = []
    for y, m, d in re.findall(r'开票日期[:：]\s*(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?', compact):
        try:
            dates.append(date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            dates.append(None)
    invoice_date = _only(dates)
    amount = _only(re.findall(r'[（(]小写[）)]\s*¥(-?\d+(?:,\d{3})*\.\d{2})(?!\d)', compact))
    amount = str(to_money(amount.replace(',', ''))) if amount else None
    totals = re.findall(r'(?<!税)合计\s*¥(-?\d+(?:,\d{3})*\.\d{2})\s*¥(-?\d+(?:,\d{3})*\.\d{2})', compact)
    arithmetic = bool(amount and totals and all(sum_money(to_money(x.replace(',', '')) for x in pair) == to_money(amount) for pair in totals))
    # Labels can be split vertically. Remarks start after the amount section;
    # bank-account lines are never treated as a card, regardless of their length.
    tail = compact.split('小写', 1)[-1]
    tail = re.split(r'备\s*注', tail, maxsplit=1)[-1]
    tail = re.split(r'开票人[:：]', tail, maxsplit=1)[0]
    labelled = re.findall(r'(?:加油卡号|油卡卡号|油卡号|卡号)[:：]\s*(\d{19}|\d{16})(?!\d)', tail)
    # Observed electronic Sinopec invoices put a standalone 1000… card in
    # remarks, with separate labelled bank accounts. Do not take the last number.
    standalone = re.findall(r'(?m)^\s*(1000\d{15})\s*$', tail)
    card_no = _only(labelled + standalone)
    known = all(label in compact for label in ('电子发票', '成品油', '中国石化', '价税合计'))
    return {'invoice_no': number, 'invoice_date': invoice_date, 'amount': amount,
            'card_no': card_no, 'reliable': bool(known and arithmetic and number and invoice_date and amount and card_no and to_money(amount) > 0)}


def recognize_pdf(content):
    """No database/network work here; keep expensive parsing out of write transactions."""
    if not content.startswith(b'%PDF-') or not content or len(content) > MAX_PDF_BYTES:
        raise MustReportError('请选择不超过20 MiB的PDF原件。')
    empty = dict(invoice_no=None, invoice_date=None, amount=None, card_no=None, reliable=False, text_sha256=None)
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted or len(reader.pages) != 1:
            return {**empty, 'reason': '加密或多页PDF，请查看原件后补正票面信息。'}
        page = reader.pages[0]
        stream = page.get_contents()
        if stream is not None and len(stream.get_data()) > 8 * 1024 * 1024:
            return {**empty, 'reason': 'PDF内容过大，已保留原件，请人工核对。'}
        plain_text = page.extract_text() or ''
        plain = _facts(plain_text)
        layout = _facts(page.extract_text(extraction_mode='layout') or '')
        agrees = plain == layout
        # Compare all extracted visible text, not just the four accounting facts.
        # Ignore whitespace and PDF metadata; changes elsewhere on the invoice
        # (buyer, seller, taxes, item details) must remain conflict evidence.
        text_sha = sha256(re.sub(r'\s+', '', plain_text).encode('utf-8')).hexdigest() if plain_text.strip() else None
        if plain['reliable'] and agrees:
            return {**plain, 'text_sha256': text_sha, 'reason': ''}
        # Preserve only facts on which both representations agree.
        fields = {key: plain[key] if plain[key] == layout[key] else None for key in ('invoice_no', 'invoice_date', 'amount', 'card_no')}
        return {**fields, 'text_sha256': text_sha, 'reliable': False, 'reason': '票面识别或完整卡号不可靠，请查看原件后补正。'}
    except Exception:
        # Original remains recoverable even for malformed PDFs; never infer facts.
        return {**empty, 'reason': 'PDF未能可靠识别，已保留原件，请人工核对。'}
