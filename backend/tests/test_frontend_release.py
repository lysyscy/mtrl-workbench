"""Public release routing rejects mixed builds and preserves API ownership."""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient
import pytest
from app.core.frontend import install_frontend


def release(tmp_path, base='/app'):
    (tmp_path/'assets').mkdir()
    (tmp_path/'assets/main.js').write_text('release', encoding='utf-8')
    (tmp_path/'index.html').write_text(f'<script src="{base}/assets/main.js"></script>', encoding='utf-8')
    return tmp_path


def test_deep_links_assets_and_api(tmp_path):
    root=release(tmp_path)
    app=FastAPI()
    @app.get('/api/check')
    def check(): return {'ok':True}
    install_frontend(app,str(root),lambda request,path,media:FileResponse(path,media_type=media,headers={'Cache-Control':'no-cache'}),base='/app')
    with TestClient(app) as client:
        for path in ['/app','/app/','/app/contracts']:
            response=client.get(path)
            assert response.status_code==200 and response.headers['cache-control']=='no-cache'
        assert client.get('/app/assets/main.js').text=='release'
        for path in ['/app/assets/missing.js','/app/missing.css']:
            assert client.get(path).status_code==404
        assert client.get('/api/check').json()=={'ok':True}


def test_mixed_or_incomplete_release_fails_before_opening(tmp_path):
    root=release(tmp_path,base='/preview')
    with pytest.raises(RuntimeError,match='基址'):
        install_frontend(FastAPI(),str(root),None,base='/app')
    (root/'index.html').write_text('<script src="/app/assets/missing.js"></script>',encoding='utf-8')
    with pytest.raises(RuntimeError,match='缺失'):
        install_frontend(FastAPI(),str(root),None,base='/app')


def test_legacy_rollback_accepts_react_bookmarks_but_not_missing_assets(monkeypatch):
    from app.core.config import get_settings
    from app.main import create_app
    monkeypatch.setenv('FRONTEND_APP_DIR','')
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response=client.get('/app/fees',follow_redirects=False)
            assert response.status_code==302 and response.headers['location']=='/app'
            assert client.get('/app/fees').status_code==200
            assert client.get('/app/assets/retired.js').status_code==404
    finally:get_settings.cache_clear()
