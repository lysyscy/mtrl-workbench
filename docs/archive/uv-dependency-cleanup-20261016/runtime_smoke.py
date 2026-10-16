"""Offline runtime checks: synthetic upload, HTTP parser selection, PDF render."""
import importlib.metadata as metadata
import faulthandler
from io import BytesIO
from pathlib import Path
faulthandler.dump_traceback_later(20)
print('Loading runtime libraries', flush=True)

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.testclient import TestClient
from gmssl import sm2
from Cryptodome.Cipher import AES
import alembic
import psycopg
import pydantic_settings
import sqlalchemy
import win32api
import win32print
import xlrd
import xlsxwriter
from loguru import logger
from openpyxl import Workbook, load_workbook
from pandas import DataFrame
from playwright.sync_api import sync_playwright
from uvicorn import Config

installed = {d.metadata['Name'].lower().replace('_', '-') for d in metadata.distributions()}
assert not installed.intersection({'pytest', 'pip-audit', 'requests', 'websockets', 'watchfiles', 'pyyaml'})
app = FastAPI()

@app.post('/upload')
async def upload(file: UploadFile = File(...), note: str = Form(...)):
    return {'content': (await file.read()).decode(), 'note': note}

with TestClient(app) as client:
    print('Checking multipart upload', flush=True)
    response = client.post('/upload', files={'file': ('sample.txt', b'offline')}, data={'note': 'ok'})
    assert response.status_code == 200 and response.json() == {'content': 'offline', 'note': 'ok'}
config = Config(app, log_config=None, lifespan='off')
config.load()
print('HTTP configuration passed', flush=True)
assert config.http_protocol_class.__module__ == 'uvicorn.protocols.http.httptools_impl'
assert config.ws_protocol_class is None
book = Workbook()
book.active['A1'] = 'synthetic'
buffer = BytesIO()
book.save(buffer)
buffer.seek(0)
assert load_workbook(buffer).active['A1'].value == 'synthetic'
assert DataFrame({'value': [2, 3]})['value'].sum() == 5
with sync_playwright() as p:
    print('Rendering synthetic PDF', flush=True)
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content('<html><body>Offline PDF smoke</body></html>')
    pdf = page.pdf()
    assert pdf.startswith(b'%PDF-') and len(pdf) > 1000
    browser.close()
faulthandler.cancel_dump_traceback_later()
print(f'PASS: {len(installed)} runtime packages; multipart upload, httptools, Excel/pandas, PDF, driver and crypto imports')
