"""Bounded, read-only adapter for the observed Sinopec delivery protocol."""
import re
import time
from urllib.parse import urlsplit

import httpx

from .invoice_pdf import MAX_PDF_BYTES

ORIGIN = 'https://invoice.sinopec.com'
DETAIL_PATH = '/api/invoice-digital-download-cos/delivery/getInvoiceDetail'
PDF_HOSTS = frozenset({'invoice.sinopec.com', 'ymhce-vpc3-xls-bmp-invoice.oss-cn-beijing.aliyuncs.com'})


class DeliveryError(ValueError):
    """Static, human-readable reason only; no signed URLs or tokens in errors."""


def link_token(raw):
    try:
        url = urlsplit(raw.strip())
        if url.scheme not in ('http', 'https') or url.hostname != 'invoice.sinopec.com' or url.port not in (None, 80, 443) or url.username or url.password or url.query or url.fragment:
            raise ValueError()
        token = url.path.strip('/')
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,128}', token) or url.path.count('/') != 1:
            raise ValueError()
        return token
    except ValueError:
        raise DeliveryError('链接格式不支持，请粘贴完整中石化交付链接。') from None


def _pdf_url(raw):
    try:
        url = urlsplit(raw)
        if url.scheme != 'https' or url.hostname not in PDF_HOSTS or url.port not in (None, 443) or url.username or url.password or url.fragment:
            raise ValueError()
        return raw
    except (ValueError, TypeError):
        raise DeliveryError('交付平台返回了未支持的PDF地址，请改为上传原件。') from None


def download_pdf(token, *, transport=None):
    """No database work. No redirects or arbitrary hosts; stream a bounded PDF."""
    started = time.monotonic()
    try:
        with httpx.Client(timeout=httpx.Timeout(25, connect=10), follow_redirects=False,
                headers={'appid': 'invoice', 'Referer': ORIGIN + '/', 'User-Agent': 'Mozilla/5.0'}, transport=transport) as client:
            with client.stream('GET', ORIGIN + DETAIL_PATH, params={'invoiceNo': token}) as response:
                if response.status_code != 200:
                    raise DeliveryError('交付信息获取失败，请稍后重试或上传PDF。')
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 1024 * 1024 or time.monotonic() - started > 90:
                        raise DeliveryError('交付信息过大或读取超时，请稍后重试。')
            import json
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeError):
                raise DeliveryError('交付平台未返回可识别的信息，请稍后重试。') from None
            if not isinstance(payload, dict) or payload.get('code') != '00000000' or not isinstance(payload.get('data'), dict):
                raise DeliveryError('交付链接无效或已失效，请核对链接或上传PDF。')
            detail = payload['data']
            if not isinstance(detail.get('invoiceNo'), str) or not re.fullmatch(r'(?:\d{8}|\d{20})', detail['invoiceNo']) or not isinstance(detail.get('pdfUrl'), str):
                raise DeliveryError('交付信息不完整，请核对链接或上传PDF。')
            target = _pdf_url(detail['pdfUrl'])
            with client.stream('GET', target) as response:
                if response.status_code != 200:
                    raise DeliveryError('PDF下载失败，请稍后重试或手工上传。')
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_PDF_BYTES or time.monotonic() - started > 90:
                        raise DeliveryError('PDF超过20 MiB或读取超时，请手工上传。')
            if not content.startswith(b'%PDF-'):
                raise DeliveryError('取得的文件不是PDF，请核对交付链接。')
            return bytes(content), detail['invoiceNo']
    except httpx.HTTPError:
        raise DeliveryError('网络获取失败，请稍后重试或手工上传PDF。') from None
