"""FastAPI 应用装配。

⚠️ **中间件顺序**（工程坑 1.5-16）：**IP 白名单在内 · request_id 居中 · CORS 最外**。
Starlette 的中间件是"**后 add 的先执行**"，所以实际 add 顺序必须写成：
`CORS → request_id → IP 白名单`，运行时才得到「白名单最先拦住、CORS 最后套上」。

⚠️ **不引入反向代理**（D1=A）⇒ **一律不信任 `X-Forwarded-For`**，只认 TCP 对端地址，
避免伪造头绕过白名单。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger, setup_logging
from app.home.router import router as home_router
from app.mod01_projects.router import router as mod01_router
from app.mod02_i8.router import router as mod02_router
from app.mod03_notice.page import THEME_CSS
from app.mod03_notice.notice_api_router import api_router as mod03_api_router
from app.mod03_notice.router import page_router as mod03_page_router
from app.mod03_notice.router import router as mod03_router
from app.mod04_plan.router import router as mod04_router
from app.mod05_flow.router import router as mod05_router
from app.mod06_proc.router import router as mod06_router
from app.mod07_setl.router import router as mod07_router
from app.mod08_inv.router import router as mod08_router
from app.mod09_fee.router import router as mod09_router
from app.mod14_config.router import router as mod14_router

# 各模块页面（单文件，托管在本进程；切片 MVP，完整前端在后续阶段）
_APP_DIR = Path(__file__).resolve().parent
# ⚠️ 2026-09-18（`TAIL-27` · `§19` **批 1**）：**m01 / m02 已删** —— 这两页的读全部走
#    `/api/m01/*` · `/api/m02/*`（新壳 `WIRED` 已在用），**无独有能力** ⇒ 旧静态页整体删除
#    （授权 `D18`：工作区删干净、不留档；git 历史保留）。
# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 4**）：**最后一个静态页 `m03.html` 已删**（授权 `D18`）——
#    它的「批量打印 / 只导出 PDF / 打印机设置」前置已于 2026-09-18 补齐（`TAIL-46`：新壳真调
#    `POST /api/m03/batch` 与 `/api/m03/settings/printer`，**不再是模拟 toast**）⇒ 无独有能力。
#    ⇒ 旧静态页托管机制（`_PAGES` ＋ 下面的 `add_api_route` 循环）**整体删除**。
#    全站页面现在只有两条路：**新壳**（`/` ＝ `web/index.html`）与**模块路由的服务端渲染页**。


def _client_ip(request: Request) -> str:
    client = request.client
    return client.host if client else ""


def _install_ip_allowlist(app: FastAPI) -> None:
    """应用层 IP 白名单（D1=A）。

    `ALLOWED_IP_CIDRS` 为空时：dev 放行并记 warning；**prod 直接拒绝启动**（不接受"默认全放"）。
    """
    settings = get_settings()
    raw = (settings.allowed_ip_cidrs or "").strip()
    networks = [ip_network(cidr.strip()) for cidr in raw.split(",") if cidr.strip()]

    if not networks and settings.app_env != "dev":
        raise RuntimeError(
            "ALLOWED_IP_CIDRS 未配置 —— 非 dev 环境拒绝以「默认全放」启动（工程底线·安全）"
        )

    @app.middleware("http")
    async def ip_allowlist(request: Request, call_next):
        if not networks:
            return await call_next(request)
        host = _client_ip(request)
        try:
            addr = ip_address(host)
        except ValueError:
            return JSONResponse({"code": "forbidden", "message": "来源地址非法"}, status_code=403)
        if not any(addr in net for net in networks):
            get_logger().warning("IP 白名单拦截：{} {}", host, request.url.path)
            return JSONResponse(
                {"code": "forbidden", "message": "来源 IP 不在允许范围"},
                status_code=403,
            )
        return await call_next(request)


def _install_request_id(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        with get_logger().contextualize(request_id=rid):
            response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


def _install_cors(app: FastAPI) -> None:
    settings = get_settings()
    origins = [o.strip() for o in (settings.cors_allow_origins or "").split(",") if o.strip()]
    if not origins:
        return  # 同源部署，无需 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        get_logger().warning("业务错误 {}：{}", exc.code, exc.message)
        return JSONResponse(exc.to_payload(), status_code=exc.http_status)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    get_logger().info("应用启动 env={}", get_settings().app_env)
    yield
    get_logger().info("应用停止")


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()

    app = FastAPI(
        title="材料报表自动化工作台",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env == "dev" else None,
        redoc_url=None,
    )

    # ⚠️ add 顺序 = CORS → request_id → 白名单（运行期执行顺序相反，见模块 docstring）
    _install_cors(app)
    _install_request_id(app)
    _install_ip_allowlist(app)
    _install_error_handlers(app)

    # ⭐ 看板 = 默认落地页（**不占模块号** · 原型导读）⇒ 挂在根路径 `/`（`ACC-HOME-TODO-001`）
    app.include_router(home_router)
    app.include_router(mod01_router)
    app.include_router(mod02_router)
    app.include_router(mod03_router)
    # MOD-03 的**列表页**（`/m03/notices`）走服务端渲染（与 MOD-04/05 同款）；
    # ⚠️ 2026-09-19（`§19` 批 4）：静态 `static/m03.html`（打印 / PDF / 设置）**已删**（授权 `D18`）——
    #    前置已补齐（`TAIL-46`：新壳真调 `POST /api/m03/batch` 与 `/api/m03/settings/printer` ✓）。
    #    ⛔ 此前那条「本文件永远保留 / 用户裁定 A」是**张冠李戴**（裁定的对象是**前端形态**：
    #    保留后端托管单页 MVP · 不启用 Vue3 工程 · 后续阶段再评估），2026-09-18 已当场更正 ⇒ 归入删除范围。
    app.include_router(mod03_page_router)
    # ⭐ **JSON 动作 API**（前端壳 `app/web/` 用）：改分类 / 剔除 / 恢复 —— 与表单向共用同一批纯函数
    app.include_router(mod03_api_router)
    # MOD-04 起：页面也由模块路由**服务端渲染**（`/m04` 在本 router 内，不走 _PAGES 静态托管）
    app.include_router(mod04_router)
    # MOD-05 同款：`/m05` · `/m05/debt` · `/m05/ledger` · `/m05/stats` 都在本 router 内
    app.include_router(mod05_router)
    # MOD-08 起：报表域页面同样服务端渲染（`/m06` 过程资料 · `/m07` 收发结存 · `/m08` 库存单据）
    app.include_router(mod06_router)
    app.include_router(mod07_router)
    app.include_router(mod08_router)
    # MOD-09 特殊费用月报表（独立新报表 = 1 自动项 + N 手填项，§5.5 / `DEV-R-04`）
    app.include_router(mod09_router)
    app.include_router(mod14_router)

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    # ★ 主题真源（**唯一入口**）：静态页用 `<link>` 引它、服务端渲染页内联同一常量
    #   ⇒ 换主题只改 `page.THEME_CSS` **一处**；`no-cache` 保证改完即时生效（不必重启/清浏览器缓存）
    @app.get("/static/theme.css", include_in_schema=False)
    def theme_css() -> Response:
        return Response(
            content=THEME_CSS, media_type="text/css", headers={"Cache-Control": "no-cache"}
        )

    # ⭐ **新前端壳**（`app/web/index.html`）—— 走「原型直接接数据」（用户 2026-09-17 裁定）。
    #    ⚠️ 挂在 `/app`（**不抢 `/`**）：打样期间与旧服务端渲染页**并存** ⇒ 逐页切换、随时可停。
    @app.get("/app", include_in_schema=False)
    def web_shell() -> FileResponse:
        return FileResponse(_APP_DIR / "web" / "index.html", media_type="text/html")

    # ⚠️ 2026-09-19（`§19` 批 4）：原先这里按 `_PAGES` 逐个托管**旧静态页**（切片 MVP）——
    #    最后一个（`m03`）已删 ⇒ **整段移除**（连同上面的 `_PAGES` 定义）。
    #    ⛔ 别再注册"按名字托管的静态页"：新页面要么进**新壳**（`web/index.html`），
    #    要么走**模块路由的服务端渲染** —— 两条路都留了断言，加第三种会绕开它们。

    # ⚠️ 根路径 `/` 已由 `home_router`（看板）接管，**别再注册第二个 `/`** ——
    #    FastAPI 按注册顺序匹配（先注册的赢），多注册一个会让人以为是它在生效。

    return app


app = create_app()
