"""出 PDF：HTML → PDF 字节（Playwright 无头 Chromium）。

⚠️ **本模块只做"HTML → PDF"这一件事**，不再掺任何版式逻辑：
- 版式取回 → `print/design.py`；
- 模板驱动渲染（字段注入 · 零值金额留空 · 签名绑定）→ `print/template.py` ＋ `print/fields.py` ＋ `print/signatures.py`；
- 本模块**不碰版式、不注入字段**。
  ℹ️ 历史上这里做过"在 i8 返回的 HTML 上替换 `{{占位符}}`"—— 该假设**已被真机证伪**
  （i8 返回的是版式模板 JSON、里面没有 HTML），相关代码已于 2026-09-15 移除。

依据：**M0-0B 渲染实测** —— 冷启动 ~7.5s / 热启动 ~0.15s ⇒ **批量必须复用同一实例**；
     ⚠️ 服务 / SYSTEM 身份下必须显式设 `PLAYWRIGHT_BROWSERS_PATH`（否则找不到浏览器）。
"""

from __future__ import annotations

import os

from app.core.errors import ExternalServiceError


class PdfRenderer:
    """Playwright 无头渲染（复用同一浏览器实例，避免每单起一次）。"""

    def __init__(self, browsers_path: str | None = None) -> None:
        self._browsers_path = browsers_path or os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        self._browser = None
        self._playwright = None

    def _ensure_browser(self):
        if self._browser is not None:
            return self._browser
        # 延迟 import：测试环境可不装 Playwright / 不启浏览器
        from playwright.sync_api import sync_playwright  # type: ignore

        if self._browsers_path:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = self._browsers_path
        pw = sync_playwright().start()
        self._playwright = pw
        self._browser = pw.chromium.launch(headless=True)
        return self._browser

    def render_html_to_pdf(self, html: str) -> bytes:
        """把 HTML 渲染成 PDF 字节。失败显式报错（不得静默）。"""
        try:
            browser = self._ensure_browser()
            page = browser.new_page()
            try:
                page.set_content(html, wait_until="networkidle")
                pdf = page.pdf(print_background=True, format="A4")
            finally:
                page.close()
        except Exception as exc:  # noqa: BLE001
            raise ExternalServiceError(f"PDF 渲染失败：{type(exc).__name__}: {exc}")
        return pdf

    def close(self) -> None:
        # ⚠️ 不调用 browser.close()（M0-0B：进程收尾会挂死）；直接快退由宿主负责
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:  # noqa: BLE001
            pass
        self._browser = None
        self._playwright = None


__all__ = ["PdfRenderer"]
