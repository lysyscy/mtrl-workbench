"""Serve complete React releases without changing the API or database target."""
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles


def install_frontend(app: FastAPI, directory: str, static_file, *, base: str) -> None:
    if not directory:
        return
    root = Path(directory).resolve(strict=True)
    if not (root / 'index.html').is_file() or not (root / 'assets').is_dir():
        raise RuntimeError('前端预览需要完整生产构建，请先执行 pnpm build')
    if base not in {'/app', '/preview'}:
        raise ValueError('Unsupported frontend entry')
    html = (root / 'index.html').read_text(encoding='utf-8')
    assets = re.findall(r'(?:src|href)=[\"\']([^\"\']*/assets/[^\"\']+)[\"\']', html)
    if not assets or any(not asset.startswith(base + '/assets/') for asset in assets):
        raise RuntimeError('前端构建基址与入口不一致')
    for asset in assets:
        path = (root / 'assets' / asset.split('/assets/', 1)[1]).resolve()
        if not path.is_relative_to(root / 'assets') or not path.is_file():
            raise RuntimeError('前端构建资源缺失')
    app.mount(base + '/assets', StaticFiles(directory=root / 'assets'), name='frontend-' + base[1:] + '-assets')

    @app.get(base, include_in_schema=False)
    @app.get(base + '/{path:path}', include_in_schema=False)
    def frontend_preview(request: Request, path: str = ''):
        # Missing versioned assets must be 404, never the SPA document.
        if path.startswith('assets/') or Path(path).suffix:
            raise HTTPException(status_code=404)
        return static_file(request, root / 'index.html', 'text/html')


def install_preview(app: FastAPI, directory: str, static_file) -> None:
    install_frontend(app, directory, static_file, base='/preview')
