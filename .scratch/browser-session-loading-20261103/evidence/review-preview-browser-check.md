# 定向复核：`--browser-notice-check` 受限开发入口

只读复核，未启动服务/未连数据库/未触浏览器与真实 i8，未运行任何测试，未改任何文件（本文件除外）。范围：`tools/dev/frontend_preview_browser_check.py`、`frontend_preview_copy.py::restrict_copy_preview`、`frontend_preview_server.py` 新参数与装配、`backend/tests/test_frontend_preview_browser_check.py`、`docs/guides/frontend-preview.md` 新节（:21-29）。**本回执不代表已获真实启用批准。**

## 结论：none（六点全部通过）

1. **默认阻断保真**。无 scope 时 `allows()` 不被调用，`external` 九条与 `/api/m02/*` 全量 403（`frontend_preview_copy.py:154-185`）；唯一新增放行 `GET /api/m02/browser/state`（`mod02_i8/router.py:208`）只读 broker，不发 i8。
2. **无法绕 scope 做别的外部动作或登录**。`enforce_browser_transport()`（`browser_check.py:120-138`）把 `I8Client._ensure_session`/`_login` 换成抛 `MustReportError`，`http_login` 唯一调用点即 `I8Client._login`（`login.py:82`）；严格客户端仅当 `browser_transport_allowed()` 且 transport 为 `BrowserRelayTransport` 才放行。其余 httpx 直呼只有 `print/ipp.py:85`，入口 `/api/m03/batch` 在 external 内。
3. **body/ContextVar/线程传递成立**。中间件读 body 后由 `_CachedRequest` 回放（`starlette/middleware/base.py:61-67`）；`approved_notice_context()` 只在 `scoped_notice` 时开启（`frontend_preview_copy.py:181-185`），anyio 起同步线程前 `copy_context()`（`_asyncio.py:2698`）。
4. **不碰来源配置/已有副本**。`load_check` 要求 `--copy-source --disposable` 且非 `--existing`（`browser_check.py:92-102`）；`i8_base_url` 只在进程内 `model_copy`（`frontend_preview_server.py:157-165`）；`bind_preview_account` 只改本副本 `preview_account` 行并核 `current_schema()`（:105-117）。
5. **清理与归属沿既有链**。`owned_work` 限定 scope 在登记 run 的 `work` 内；退出由 `isolated_database` finally 核 schema 属主后 `DROP SCHEMA ... CASCADE`（`frontend_preview.py:137-143`）。
6. **证据表述与实现一致**：`:27` 放行面、`:29` 测试覆盖与"仍须当次明确批准"均成立。

范围外观察（既有行为，非本差异）：`POST /api/m13/invoice-batches/.../run` → `delivery.download_pdf`（`https://invoice.sinopec.com`）不在 external 名单，本任务未改。
