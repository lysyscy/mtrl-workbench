"""Local font delivery and real Chromium glyph use; no business writes."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.mod03_notice.page import render_theme
from app.mod15_user.page import login_html
from tools.audit.workspace_paths import output


FONTS = Path(__file__).resolve().parents[1] / 'app/web/fonts'


def test_font_assets_and_license_are_public_and_revalidated():
    with TestClient(create_app(), client=('127.0.0.1', 50123)) as client:
        for file in FONTS.iterdir():
            if file.suffix not in {'.woff2', '.pdf', '.txt'}:
                continue
            response = client.get('/static/fonts/' + file.name)
            assert response.status_code == 200
            assert response.content == file.read_bytes()
            if file.suffix == '.woff2':
                assert response.headers['content-type'] == 'font/woff2'
            assert client.get('/static/fonts/' + file.name, headers={
                'If-None-Match': response.headers['etag'],
            }).status_code == 304
        assert client.get('/static/fonts/unknown.woff2').status_code == 404
        assert client.get('/static/fonts/%2e%2e%2fmain.py').status_code == 404










def test_react_subsets_are_local_and_unknown_font_paths_are_rejected():
    import hashlib
    import json
    from app.mod03_notice.theme_react import render_react_theme

    manifest = json.loads((FONTS / 'misans-web/manifest.json').read_text(encoding='utf-8'))
    assert render_react_theme('松绿').startswith("@import url('/static/fonts/misans-web.css');")
    with TestClient(create_app(), client=('127.0.0.1', 50123)) as client:
        css = client.get('/static/fonts/misans-web.css')
        assert css.status_code == 200 and css.content == (FONTS / 'misans-web.css').read_bytes()
        assert 'https://' not in css.text
        assert client.get('/static/fonts/misans-web.css', headers={'If-None-Match': css.headers['etag']}).status_code == 304
        for weight in ['400', '500', '600']:
            files = [f for f in manifest['unmodified_official_subsets'] if f['file'].startswith(weight + '-')]
            for item in [files[0], files[-1]]:
                response = client.get('/static/fonts/misans-web/' + item['file'])
                assert response.status_code == 200
                assert hashlib.sha256(response.content).hexdigest() == item['sha256']
                assert response.headers['content-type'] == 'font/woff2'
        for name in ['misans-web/manifest.json', 'misans-web/missing.woff2', 'misans-web/%2e%2e/main.py']:
            assert client.get('/static/fonts/' + name).status_code == 404
