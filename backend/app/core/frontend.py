"""Opt-in static preview; the existing /app and API routes keep their owners."""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles


def install_preview(app: FastAPI, directory: str, static_file) -> None:
    if not directory:
        return
    root = Path(directory).resolve(strict=True)
    if not (root / 'index.html').is_file() or not (root / 'assets').is_dir():
        raise RuntimeError('前端预览需要完整生产构建，请先执行 pnpm build')
    app.mount('/preview/assets', StaticFiles(directory=root / 'assets'), name='frontend-preview-assets')

    @app.get('/preview', include_in_schema=False)
    @app.get('/preview/{path:path}', include_in_schema=False)
    def frontend_preview(request: Request, path: str = ''):
        # Missing versioned assets must be 404, never the SPA document.
        if path.startswith('assets/') or Path(path).suffix:
            raise HTTPException(status_code=404)
        return static_file(request, root / 'index.html', 'text/html')
