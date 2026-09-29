"""FastAPI 应用装配。

⚠️ **中间件顺序**（工程坑 1.5-16）：**IP 白名单在内 · request_id 居中 · CORS 最外**。
Starlette 的中间件是"**后 add 的先执行**"，所以实际 add 顺序必须写成：
`CORS → request_id → IP 白名单`，运行时才得到「白名单最先拦住、CORS 最后套上」。

⚠️ **不引入反向代理**（D1=A）⇒ **一律不信任 `X-Forwarded-For`**，只认 TCP 对端地址，
避免伪造头绕过白名单。

⚠️ **压缩（GZip）放最内层**：它只压"真正进到应用"的正常响应 —— 被白名单拦掉的 403 不经它
（本来就不必压，省一层 CPU）。⇒ 见 `create_app` 里的 add 顺序。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger, setup_logging
from app.home.router import router as home_router
from app.mod01_projects.router import router as mod01_router
from app.mod02_i8.router import router as mod02_router
from app.mod03_notice.page import DEFAULT_THEME as _DEFAULT_THEME
from app.mod03_notice.notice_api_router import api_router as mod03_api_router
from app.mod03_notice.router import router as mod03_router
from app.mod04_plan.router import router as mod04_router
from app.mod05_flow.router import router as mod05_router
from app.mod06_proc.router import router as mod06_router
from app.mod07_setl.router import router as mod07_router
from app.mod08_inv.router import router as mod08_router
from app.mod09_fee.router import router as mod09_router
from app.mod11_jc.router import router as mod11_router
# ⛔ `MOD-12` 差异登**已取消（已撤页）**（2026-09-20 用户裁定）—— 曾短暂存在过 `mod12_diff`
#    包与路由，依据是「独立一页」，而《说明书》§5.8.3 明写「**归属「库存单据」（不独立成模块）**」⇒
#    差异的**载体 = 调整单**（`m08`）、**产出 = 差异表**（`m06`，系统按调整单算）⇒ 无独立页。
#    ⭐ 这段注释是**撤项记录**；`doc_audit` 的 `T8` 守卫会在有人试图把它加回来时报红
#      （真源 = `tools/audit_common.py::CANCELLED`）。
#    ⇒ 包与路由都已删除；能力判据改由 `ACC-DIF-REG-001`（4 条）指着 `m08`/`m06` 的真落点。
from app.mod14_config.router import router as mod14_router
# MOD-15：**从第一天起就是 JSON API ＋ 新壳**（⛔ 没有服务端渲染页）—— 同 `mod11` 的做法。
# ⚠️ 本模块还顺手把 `core/identity.py` 的「当前登录用户」对到了**真实账号**
#    （§1.5.1 末行：留痕的改前人 / 录入人「统一取当前登录用户」＝ 账号体系与业务字段的**唯一接点**）。
from app.mod15_user.api import router as mod15_api_router

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


def _install_session(app: FastAPI) -> None:
    """把**会话 cookie** 解成「当前登录用户」，放进 `core/session.py` 的 `ContextVar`。

    ⚠️ 这是**登录态进业务字段的唯一通道**：`core/identity.current_operator()` 读那个
       `ContextVar`（⛔ 业务模块一处都不用改 —— `identity.py` 模块头的承诺）。

    ⚠️⚠️ **每个请求必须先清空再写入**：`ContextVar` 在**线程/任务复用**时会把上一个请求的值
       带过来 ⇒ 一旦某请求没带 cookie（或 cookie 过期），它就会**继承上一个人的名字** ——
       那种错**不报错**、只是留痕里的人名**是别人的**，是全系统最难查的一类。
    """
    from app.core import session as SESS

    @app.middleware("http")
    async def session_loader(request: Request, call_next):
        SESS.set_current_name("")                              # ⚠️ 先清（见上）
        who = SESS.read(request.cookies.get(SESS.COOKIE_NAME))
        if who:
            SESS.set_current_name(who)
        return await call_next(request)


#: 「写动作」的方法集（未登录 ⇒ 一律拒）—— 读方法（GET/HEAD/OPTIONS）**不在**其中（§1.5.1「只能看」）
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: 未登录也能打的**写**端点 —— **只管"登录本身"**（⛔ 往里加业务端点就是开口子）
AUTH_FREE_WRITE_PATHS = frozenset({"/m15/login", "/api/m15/logout"})


def _install_auth_gate(app: FastAPI) -> None:
    """⭐ **未登录 ⇒ 写动作一律拒**（《说明书》§1.5.1 · 2026-09-21 用户裁定「未登录 = 无身份」）。

    ⚠️⚠️ 补它的理由（2026-09-25 用户报障「未登录状态什么都能做」）：原先**没有任何全局鉴权** ——
       会话中间件只把 cookie 解成"当前登录用户"，**不拦任何请求**；唯一会拒的是 `mod15` 自己的写动作
       （且返 200 + `ok:false`）⇒ 其余所有模块（付款 / 集采 / 材料 / 项目…）的写端点**零判定**。
    ⚠️ **读一律放行**（口径原文 =「未登录**只能看**」）：⛔ 不要顺手改成"未登录只渲染登录页" ——
       那会把**不带会话的真机自检 / 探针**全打白屏（`_shell_smoke` 等 20 条），且比 §1.5.1 更严，须单独裁定。
    ⚠️ 判定**只看会话票**（`SESS.read` ⇒ 验签 ＋ 查有效期）：与 `_install_session` **同一个出口**，
       ⛔ 不在这里另查账号表（那就是第二套口径）。
    """
    from app.core import session as SESS

    @app.middleware("http")
    async def auth_gate(request: Request, call_next):
        if request.method not in WRITE_METHODS:
            return await call_next(request)                    # 读：放行（"只能看"）
        if request.url.path in AUTH_FREE_WRITE_PATHS:
            return await call_next(request)                    # 登录 / 登出本身
        if SESS.read(request.cookies.get(SESS.COOKIE_NAME)):
            return await call_next(request)                    # 有有效会话票 ⇒ 正常走
        get_logger().warning("未登录拦截写动作：{} {}", request.method, request.url.path)
        return JSONResponse(
            {"code": "unauthorized", "message": "未登录：本系统未登录只能查看，改数据请先登录"},
            status_code=401,
        )


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

    # ⭐ 压缩（性能 P1 · 2026-09-19）：新壳 `index.html` 未压缩 ≈ 620 KB ⇒ 首屏白等；GZip 后 ≈ 1/5。
    #    ⚠️ 位置：**最早 add ⇒ 最内层**（本文件 docstring 那条顺序规矩）—— 只压"真正进到应用"的
    #    正常响应；被白名单拦掉的 403 不经它（本来就不必压）。⚠️ 它是**纯 ASGI** 中间件，
    #    与外围的 `BaseHTTPMiddleware`（CORS / request_id / 白名单）叠加是安全组合。
    #    `minimum_size` 以下不压：小响应压了反而更大（多一层 gzip 头）。
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # ⚠️ add 顺序 = CORS → request_id → 白名单（运行期执行顺序相反，见模块 docstring）
    _install_cors(app)
    _install_request_id(app)
    _install_session(app)
    _install_auth_gate(app)          # ⭐ §1.5.1「未登录 ⇒ 写动作一律拒」（2026-09-25 用户裁定 A）
    _install_ip_allowlist(app)
    _install_error_handlers(app)

    # ⭐ 看板 = 默认落地页（**不占模块号** · 原型导读）—— ⚠️ 2026-09-21 起**看板在壳里**
    #    （`§19` 批 5 收口：旧服务端渲染页 `home/view.py` 已删）⇒ 本路由现在只剩
    #    `GET /`（**302 → `/app`**，⛔ 不是 301：301 会被浏览器长期缓存）＋ 记账端点 `/api/home/run-counts`。
    app.include_router(home_router)
    app.include_router(mod01_router)
    app.include_router(mod02_router)
    app.include_router(mod03_router)
    # ⭐ **JSON API 汇总**（前端壳 `app/web/` 用）：列表查询 ＋ 改分类 / 剔除 / 恢复 / 统计手改 /
    #    手动行增删 / 批量付款 —— 判定一律共用同一批纯函数出口。
    # ⚠️ 2026-09-19（`§19` 批 4 · **S4⑤**）：MOD-03 的**服务端渲染页已全部删除**（授权 `D18`）——
    #    静态页 `m03.html`（批 4.5）＋ 列表页 `/m03/notices` / 批量付款窗口 `/m03/pay` /
    #    查看关联 `/m03/notices/trace` ＋ 9 条行级 PRG（`notice_actions_router` / `notice_pay_router`）。
    #    ⛔ 此前的「本文件永远保留 / 用户裁定 A」是**张冠李戴**（裁定的对象是**前端形态**：
    #    保留后端托管单页 MVP · 不启用 Vue3 工程），2026-09-18 已当场更正 ⇒ 归入删除范围。
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
    # MOD-11 集采台账（M5 切片 5 · 2026-09-19 开工）：**从第一天起就是 JSON API ＋ 新壳**
    #  ⚠️ 本模块没有服务端渲染页；读 `/api/m11/list` · `/api/m11/detail`（写动作随 M5-4 进）
    app.include_router(mod11_router)
    # ⛔ 原 `mod12_router`（差异登记的 JSON API）已撤 —— 见上方 import 处的说明（2026-09-20 用户裁定）
    app.include_router(mod14_router)
    # MOD-15 用户管理（`MOD-15` · §1.5）：**从第一天起就是 JSON API ＋ 新壳**（⛔ 无服务端渲染页）
    #  ⚠️ 本模块还顺手把 `core/identity.py` 的「当前登录用户」对到了**真实账号**
    #     （§1.5.1 末行：留痕的改前人 / 录入人「统一取当前登录用户」＝ 账号体系与业务字段的唯一接点）
    app.include_router(mod15_api_router)
    # ⭐ 通用导入面（`TAIL-75`）：这里只挂**域清单**那一个端点（`GET /api/imp/domains`）——
    #   ⚠️ 各域自己的 `parse/preview/commit` 端点在**各自模块的 router** 里挂（`import_kit.build_router`
    #   ⇒ `mod06_proc/router.py` 已挂 m06）⇒ 加一个域**不用改本文件**。
    from app.import_kit.api import domains_router as _imp_domains_router   # noqa: PLC0415

    app.include_router(_imp_domains_router())

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    # ★ 主题真源（**唯一入口**）：静态页用 `<link>` 引它、服务端渲染页内联同一常量
    #   ⇒ 换主题只改 `page.THEME_CSS` **一处**；`no-cache` 保证改完即时生效（不必重启/清浏览器缓存）
    #
    # ⭐ 2026-09-20（`ACC-UI-THEME-001/001-06`「主题选择**按用户隔离**」）：
    #   本端点改为**按当前登录用户**出主题 —— 同一个 URL、不同的会话 cookie，
    #   拿到**不同的 CSS** ⇒ 「A 与 B 各自的选择互不影响」就是这一句的直接含义。
    #   ⚠️ **未登录 / 未设置 / 账号已删** 一律回落**默认套**（⛔ 未登录也必须有样式，不能白屏）。
    #   ⚠️ **只有"取哪一套"按用户** —— **主题定义本身**仍然只有一处（`page.THEMES`，
    #      `001-03`「单一真源」钉着它）⇒ 这里⛔ 不会、也不许长出第二份取值。
    @app.get("/static/theme.css", include_in_schema=False)
    def theme_css(request: Request) -> Response:
        from app.core import session as SESS
        from app.core.db import session_scope
        from app.mod03_notice.page import render_theme
        from app.mod15_user import repository as USR

        who = SESS.read(request.cookies.get(SESS.COOKIE_NAME))
        if who:
            with session_scope() as s:
                name = USR.theme_by_account(s, who)
        else:
            name = _DEFAULT_THEME
        return Response(
            content=render_theme(name), media_type="text/css",
            headers={"Cache-Control": "no-cache"},
        )

    # ⭐ **新前端壳**（`app/web/index.html`）—— 走「原型直接接数据」（用户 2026-09-17 裁定）。
    #    ⚠️ 挂在 `/app`（**不抢 `/`**）：打样期间与旧服务端渲染页**并存** ⇒ 逐页切换、随时可停。
    @app.get("/app", include_in_schema=False)
    def web_shell() -> FileResponse:
        return FileResponse(_APP_DIR / "web" / "index.html", media_type="text/html")

    # ⭐ **壳的外链件**（`web/shell/*.js`）—— 壳的**接线层**都在这几件里（`P4`② 2026-09-19 起拆 · `P2-a` 2026-09-28 加件）。
    #    ⚠️ **件清单的唯一出口 = `index.html` 的 `<script src>`**（`tools/audit/shell_source.py` 按它现读）
    #       ⇒ ⛔ 别在此处写死件数或件名（会随拆件涨，写了必漂）。
    #    ⚠️ 路由名与文件名**必须**是 `/static/shell/<name>.js`：`tools/shell_source.py`（读壳的**唯一出口**）
    #       正是按这个形态反查文件的 ⇒ 换目录 / 换形态要**同批**改那里（否则测试读到的 ≠ 浏览器执行的）。
    #    ⚠️ **逐条显式注册**（⛔ 不用通配 `{name}` 参数）：件数很少、零路径穿越风险；加一件要**同时**改这里
    #       与 `index.html` 的 `<script src>`（`syntax_audit` 会逐件 `node --check`，漏一件就红）。
    #        ⭐ 2026-09-21（`§19` 四个暂留件收口）新增第 **4** 件 `legacy.js`。
    def _shell_js(name: str) -> FileResponse:
        return FileResponse(
            _APP_DIR / "web" / "shell" / name,
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/static/shell/actions.js", include_in_schema=False)
    def shell_actions_js() -> FileResponse:
        return _shell_js("actions.js")

    # ⭐ 2026-09-24 加件（`TAIL-48` §八.5 第 1 刀：`API` 切进 `api.js`）。
    #    ⚠️ **拆件要两处登记**：① `index.html` 的 `<script src>`（读壳的唯一出口认这个）
    #    ② **本文件的一条路由**（缺 ⇒ 浏览器 404 ⇒ `ReferenceError` 整支崩）
    #    ⇒ 机器守 = `tests/test_shell_part_routes.py`（⛔ 别只改一处）。

    # ⭐ `P2-a` 拆件（2026-09-28 · `TAIL-164`）：`shell/base.js`。
    #    ⚠️ **两处登记**：本路由 ＋ `index.html` 的 `<script src>`（缺一 ⇒ 浏览器 404 ⇒ 整支壳崩）。
    @app.get("/static/shell/base.js", include_in_schema=False)
    def shell_base_js_js() -> FileResponse:
        return _shell_js("base.js")

    # ⭐ `P2-a` 拆件（2026-09-28 · `TAIL-164`）：`shell/view.js`。
    #    ⚠️ **两处登记**：本路由 ＋ `index.html` 的 `<script src>`（缺一 ⇒ 浏览器 404 ⇒ 整支壳崩）。
    @app.get("/static/shell/view.js", include_in_schema=False)
    def shell_view_js_js() -> FileResponse:
        return _shell_js("view.js")

    # ⭐ `P2-a` 拆件（2026-09-28 · `TAIL-164`）：`shell/ui.js`。
    #    ⚠️ **两处登记**：本路由 ＋ `index.html` 的 `<script src>`（缺一 ⇒ 浏览器 404 ⇒ 整支壳崩）。
    @app.get("/static/shell/ui.js", include_in_schema=False)
    def shell_ui_js_js() -> FileResponse:
        return _shell_js("ui.js")

    # ⭐ `P2-a` 拆件（2026-09-28 · `TAIL-164`）：`shell/proj.js`。
    #    ⚠️ **两处登记**：本路由 ＋ `index.html` 的 `<script src>`（缺一 ⇒ 浏览器 404 ⇒ 整支壳崩）。
    @app.get("/static/shell/proj.js", include_in_schema=False)
    def shell_proj_js_js() -> FileResponse:
        return _shell_js("proj.js")

    # ⭐ `P2-a` 拆件（2026-09-28 · `TAIL-164`）：`shell/pages-a.js`。
    #    ⚠️ **两处登记**：本路由 ＋ `index.html` 的 `<script src>`（缺一 ⇒ 浏览器 404 ⇒ 整支壳崩）。
    @app.get("/static/shell/pages-a.js", include_in_schema=False)
    def shell_pages_a_js_js() -> FileResponse:
        return _shell_js("pages-a.js")

    # ⭐ `P2-a` 拆件（2026-09-28 · `TAIL-164`）：`shell/pages-b.js`。
    #    ⚠️ **两处登记**：本路由 ＋ `index.html` 的 `<script src>`（缺一 ⇒ 浏览器 404 ⇒ 整支壳崩）。
    @app.get("/static/shell/pages-b.js", include_in_schema=False)
    def shell_pages_b_js_js() -> FileResponse:
        return _shell_js("pages-b.js")
    @app.get("/static/shell/api.js", include_in_schema=False)
    def shell_api_js() -> FileResponse:
        return _shell_js("api.js")

    @app.get("/static/shell/core.js", include_in_schema=False)
    def shell_core_js() -> FileResponse:
        return _shell_js("core.js")

    @app.get("/static/shell/print-export.js", include_in_schema=False)
    def shell_print_export_js() -> FileResponse:
        return _shell_js("print-export.js")

    # ⭐ `§19`「四个暂留件收口」（2026-09-21）：设置 ＋ 三个历史导入的**壳内实现**（接线层加件）。
    @app.get("/static/shell/legacy.js", include_in_schema=False)
    def shell_legacy_js() -> FileResponse:
        return _shell_js("legacy.js")

    # ⚠️ 2026-09-19（`§19` 批 4）：原先这里按 `_PAGES` 逐个托管**旧静态页**（切片 MVP）——
    #    最后一个（`m03`）已删 ⇒ **整段移除**（连同上面的 `_PAGES` 定义）。
    #    ⛔ 别再注册"按名字托管的静态页"：新页面要么进**新壳**（`web/index.html`），
    #    要么走**模块路由的服务端渲染** —— 两条路都留了断言，加第三种会绕开它们。

    # ⚠️ 根路径 `/` 已由 `home_router` 接管（**302 → `/app`** —— 看板已进壳），**别再注册第二个 `/`** ——
    #    FastAPI 按注册顺序匹配（先注册的赢），多注册一个会让人以为是它在生效。

    return app


app = create_app()
