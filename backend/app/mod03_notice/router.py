"""MOD-03 路由 —— **批量打印 / 仅导出 PDF / 打印机设置 / 抓取**（API）。

⚠️ 薄层：真实依赖（i8 / Playwright / 打印机 / DB）在此组装；
   编排逻辑全在 `service.run_batch`（纯函数，可离线单测）。
⚠️ 依赖一律经 `Depends` 暴露 —— 测试用 `app.dependency_overrides` 注入桩，
   使「系统内勾选 → 单选/多选端到端」（001-09）可在不连库、不启浏览器下断言。

⚠️ 本文件只服务「勾选 → 输出」这条链路与设置入口；**列表查询与行级动作在 `notice_api_router.py`**。
   ⚠️ 2026-09-19（`§19` 批 4）：MOD-03 的**服务端渲染页已全部删除** ⇒ **别把页面再写回来**
   （新页面一律进新壳 `app/web/index.html`）。

⚠️ 2026-09-19 **拆件**（`doc_audit` 的 `T5`：本件曾 **647 行 > 600 = 禁合入**）：
   把「**可注入执行器 ＋ 单行落库**」（`get_batch_executor` / `apply_fetched_row` /
   `get_fetch_executor` / `get_notice_lister` / `_persist_run`）搬到 `notice_executors.py`；
   ⛔ **路由一条都没搬** —— `tools/chain_expected.txt` 的落点钉的就是本文件的 `::名字`。
   ⛔ 那四个名字在本文件**再导出**（落点表与测试都从这里取），别删。
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.logging import get_logger
from app.mod01_projects import repository as proj_repo
from app.mod01_projects.domain import (
    append_keyword_dedup,
    candidates_of,
    i8_warehouse_lookup,
    validate_keyword_in_doc,
)
from app.mod01_projects.models import TYPE_SMALL
from app.mod01_projects.repository import all_projects
from app.mod02_i8 import wh_cache
from app.mod03_notice import pdf_cache
from app.mod03_notice.domain import still_unsettled
from app.mod03_notice.print.dispatch import list_printers
from app.mod03_notice.repository import latest_unresolved
from app.mod03_notice.schemas import (
    AssignRequest,
    AssignResponse,
    BatchRequest,
    BatchResponse,
    FetchRequest,
    FetchResponse,
    ItemOutcomeOut,
    PrinterSettingRequest,
    PrinterSettingResponse,
    UnresolvedResponse,
    WarehouseCheckOut,
    WarehouseCheckRequest,
)
from app.mod03_notice.service import BatchResult
from app.mod03_notice.settings_store import apply_printer_setting

# ⚠️ **兼容再导出**（2026-09-19 拆件）：四个名字的**实体在 `notice_executors.py`**，
#    但落点表（`tools/chain_expected.txt`）与测试都从**本模块**取
#    （`test_acc_pay_print.py` / `test_acc_pay_pdf.py` / `test_unresolved_freshness.py`）
#    ⇒ ⛔ **别删这几行**。（`inspect.getsource()` 取的是函数**自己的源文件** ⇒ 再导出不影响那条断言。）
from app.mod03_notice.notice_executors import (  # noqa: F401
    apply_fetched_row,
    get_batch_executor,
    get_fetch_executor,
    get_notice_lister,
)

logger = get_logger()

router = APIRouter(prefix="/api/m03", tags=["mod03"])


# --------------------------------------------------------------- 路由


@router.post("/notices/fetch", response_model=FetchResponse)
def fetch_notices(
    req: FetchRequest,
    executor: Callable[[str, bool], tuple[int, int]] = Depends(get_fetch_executor),
) -> FetchResponse:
    """按核算年月抓取（D4 最小取数）。

    ⚠️ 登录含强踢（KillOnlineUser）：`allow_kick=False` 时若检测到在线冲突 ⇒ 直接失败、不踢人。
    ⚠️ 抓取失败**不自动重试登录**（D9）。
    """
    fetched, upserted = executor(req.year_month, req.allow_kick)
    return FetchResponse(year_month=req.year_month, fetched=fetched, upserted=upserted)


@router.get("/notices/unresolved", response_model=UnresolvedResponse)
def unresolved_notices() -> UnresolvedResponse:
    """**最近一次付款通知书抓取**的未命中清单 ＋ 该壳下的候选小微（`TAIL-29`-② 弹窗的数据源）。

    ⭐ **弹窗的唯一数据源** —— ⛔ 不暂存整批抓取数据（用户 2026-09-18 裁定 `B`：
       补完关键词**再抓一次**，那时 `resolve_ownership` 会自动命中并落库，库里不留半成品）。
    ⚠️⚠️ **两层"新鲜度"**（`TAIL-41` 修复，2026-09-18）：
       ① **只认最近一次抓取**（`repository.latest_unresolved`）：抓取**成功之后**就不该再有清单；
       ② 清单里每一条还要**按当前档案现算**（`domain.still_unsettled`）—— 用户可能**刚补过词 /
          刚建过小微**，那些行**已经能归属了** ⇒ **当场不再出现**（否则对着已解决的清单白干）。
    """
    with session_scope() as session:
        projects = all_projects(session)
        items = still_unsettled(latest_unresolved(session), projects)
        out = [
            {
                **it,
                "candidates": (
                    candidates_of(int(it["shell_id"]), projects) if it.get("shell_id") else []
                ),
            }
            for it in items
        ]
    return UnresolvedResponse(items=out)


@router.post("/notices/ownership-assign", response_model=AssignResponse)
def assign_ownership(req: AssignRequest) -> AssignResponse:
    """把「关键词」补到某个具体小微名下（**去重追加**）⇒ 用户**再抓一次**即自动命中（链路 C）。

    口径（§2.5.1 链路 C · 原型 `ownOk` 三态）：
    - ⛔ 关键词**必须出现在单据名里**（`validate_keyword_in_doc`）—— **填不出说明不是它**（不猜）
    - **选已有小微** ⇒ `append_keyword_dedup` 追加（**只动 `match_keywords`**，别的字段一律不碰）
    - **属于新小微** ⇒ 壳 ＋ 仓库名 ＋ 关键词；⚠️ **已归档的壳下不许新建**
      （新小微必然「在建」⇒ 会当场破坏「壳归档 ⇔ 小微全归档」；该判定由 `create_project` 内部出口负责，此处只把它翻译成中文回执）
    - ⛔ 本端点**不写任何通知书数据** —— 本批已被拒、库里没有它的行（§2.7.4）

    ⚠️ 本动作**只补档案**，补完必须**再抓一次**（回执里讲清这一点，别让用户以为已经落库）。
    """
    try:
        keyword = validate_keyword_in_doc(req.keyword, req.doc_name)
    except MustReportError as exc:
        return AssignResponse(ok=False, message=str(exc))

    with session_scope() as session:
        projects = all_projects(session)

        if req.small_id:
            small = next((p for p in projects if p.id == req.small_id), None)
            if small is None:
                return AssignResponse(ok=False, message=f"具体小微 {req.small_id} 不存在")
            proj_repo.set_keywords(
                session, small, append_keyword_dedup(small.match_keywords, keyword)
            )
            label = small.disp or small.warehouse_name or small.name_full
            return AssignResponse(
                ok=True,
                message=(
                    f"关键词「{keyword}」已去重追加到 <b>{label}</b>。"
                    "请**再抓一次** —— 这次会自动命中并写入。"
                ),
            )

        name = (req.new_small_name or "").strip()
        if not name:
            return AssignResponse(ok=False, message="新建小微需要填「仓库名」")
        shell = next((p for p in projects if p.id == req.shell_id), None)
        if shell is None:
            return AssignResponse(ok=False, message="壳未建档 ⇒ 必须先有壳后有微（链路 A）")
        try:
            proj_repo.create_project(
                session,
                project_type=TYPE_SMALL,
                name_full=shell.name_full,
                warehouse_name=name,
                parent_shell_id=shell.id,
                match_keywords=[keyword],
            )
        except MustReportError as exc:      # 已归档的壳下不许新建 —— 原样把原因给用户
            return AssignResponse(ok=False, message=str(exc))
        return AssignResponse(
            ok=True,
            message=(
                f"已建档并归集：<b>{name}</b>（关键词「{keyword}」）。"
                "请**再抓一次** —— 这次会自动命中并写入。"
            ),
        )


def _wh_loader_dep() -> Callable[..., list[dict]]:
    """仓库名单取数（`API-05`）—— ⚠️ **局部导入** `mod02_i8.router`（与 `get_fetch_executor` 同款，
    避开模块级循环依赖）；测试用 `app.dependency_overrides[_wh_loader_dep]` 注入桩（**不连 i8**）。"""
    from app.mod02_i8.router import get_warehouse_rows  # noqa: PLC0415

    return get_warehouse_rows()


@router.post("/notices/warehouse-check", response_model=WarehouseCheckOut)
def warehouse_check(
    req: WarehouseCheckRequest,
    wh_loader: Callable[..., list[dict]] = Depends(_wh_loader_dep),
) -> WarehouseCheckOut:
    """**兜底前先跑一次 i8 仓库名单**（`TAIL-39` · 用户 2026-09-18 口述裁定）。

    原话：「**在兜底前，系统的设计里应该有去仓库跑了一环这个逻辑，而且如果跑完没结果要在界面上提醒用户**」。
    为什么要这一环：链路 C 的兜底 = **手填仓库名**新建具体小微 ⇒ 用户若**凭猜**填，就留下一条与 i8 不符的
    **假档案行**；日后 i8 真建了仓库 ⇒ 系统**再建一行**（重复）。

    ⚠️ **只读**：不落库、不建档（名单本身也不留档 —— 与 `POST /api/m02/sync/warehouses` 同一口径）；
       判定走 `mod01_projects.domain.i8_warehouse_lookup`（**唯一出口**），本层只组装回执。
    ⚠️ 取名单**要登录 i8**、可能**强踢**在线用户 ⇒ `allow_kick` 默认 `False`，壳侧必须**二次确认之后**才传 `True`（`D9`）。
    ⚠️ **禁静默**：取不到 ⇒ `degraded=True` ＋ 中文说明，⛔ **不许把"没取到"说成"名单里没有"**（那是两回事）。
    """
    name = str(req.warehouse_name or "").strip()
    if not name:
        return WarehouseCheckOut(warehouse_name="", degraded=True, message="请先填「仓库名」再查")

    cached_at = ""
    head = ""
    try:
        rows = wh_loader(req.allow_kick)
    except Exception as exc:                              # noqa: BLE001
        # ⭐ `TAIL-39`：抓不到 ⇒ **回退到上一次的名单**接着判（缓存是优化、不是功能），
        #    但**必须说清"这是几点抓的"** —— ⛔ 不许把旧名单说成刚抓的（`wh_cache` 纪律 2）。
        rows, cached_at = wh_cache.load()
        if not rows:
            return WarehouseCheckOut(
                warehouse_name=name,
                degraded=True,
                message=(
                    f"没取到 i8 仓库名单：{type(exc).__name__}: {exc}"
                    "（⚠️ 这只是**没查到**，**不等于名单里没有**；也没有可用的上次名单 —— 可稍后重试）"
                ),
            )
        head = (f"⚠️ 这次**没取到**名单（{type(exc).__name__}）⇒ 下面用的是 "
                f"**{cached_at or '未知时间'}** 那份缓存（{len(rows)} 条）：<br>")

    info = i8_warehouse_lookup(name, rows)
    total = int(info["total"])
    if info["found"]:
        owners = info["owners"]
        more = "（⚠️ 同名挂多条全名 ⇒ 要人来定，系统不替选）" if len(owners) > 1 else ""
        return WarehouseCheckOut(
            warehouse_name=name,
            found=True,
            owners=owners,
            total=total,
            from_cache=bool(cached_at),
            cached_at=cached_at,
            message=head + (
                f"i8 名单里**有**「{name}」，挂在 "
                + ("、".join(f"「{o}」" for o in owners) if owners else "（名单里这行没写所属项目）")
                + f" 下{more}（名单共 {total} 条）"
            ),
        )
    return WarehouseCheckOut(
        warehouse_name=name,
        found=False,
        total=total,
        from_cache=bool(cached_at),
        cached_at=cached_at,
        message=head + (
            f"⚠️ i8 名单里**没有**「{name}」（名单共 {total} 条）—— 若现在按这个名字建具体小微，"
            "日后 i8 真建了这个仓库，系统会**再建一行**（重复）。**要建请显式确认**。"
        ),
    )


@router.post("/batch", response_model=None)
def batch(
    req: BatchRequest,
    executor: Callable[[list[int], str], BatchResult] = Depends(get_batch_executor),
):  # type: ignore[no-untyped-def]
    """批量打印 / 仅导出 PDF（共用同一次勾选，由 `mode` 分流）。

    ⚠️⚠️ **2026-09-20 加异常兜底**（用户实测踩到）：原先这里是
    `result = executor(...)` **裸调、不兜异常** ⇒ 链路里**任何一步抛**（i8 登录 / `PdfRenderer`
    起浏览器 / 取数 / 渲染 / 投递）都会变成 **HTTP 500** ⇒ 界面上只显示"500"，
    **真因只在服务端 stderr 里**（用户点「只导出 PDF」看到的就是这个，只能来问我"是不是登录的问题"）。
    ⇒ 现在把**可预期的**失败（`MustReportError`）与**未预期的**异常**都兜住**，
      按本项目一贯口径回「**200 ＋ `ok:false` ＋ 一句中文**」，并把**类型名**一并带出
      —— ⛔ 界面上**不许只显示一个状态码**：那样用户既报不准、我也查不动。

    ⚠️ 为什么 `response_model` 从 `BatchResponse` 改成 `None`：兜底分支要回 `JSONResponse`，
       而 `response_model` 会**按模型校验并改写**返回体 ⇒ 失败分支会被它改成 500。
       （成功分支**仍然回 `BatchResponse`**，形状一字未变 ⇒ 前端不受影响。）
    """
    from fastapi.responses import JSONResponse

    try:
        result = executor(req.ids, req.mode)
    except MustReportError as exc:
        return JSONResponse(status_code=200, content={"ok": False, "message": exc.message})
    except Exception as exc:                      # noqa: BLE001 —— 见 docstring：一律兜住、带回真因
        logger.exception("批量%s 失败（未预期异常）", req.mode)
        return JSONResponse(status_code=200, content={
            "ok": False,
            "message": f"批量执行失败：{type(exc).__name__}: {exc}",
        })
    # ⭐⭐ **导出不再落盘**（用户 2026-09-20：「导出换成浏览器下载」）⇒ 把这一批的字节交给
    #    `pdf_cache` 拿一个 token；前端凭下面这个 `download_url` 取一次
    #    （单张 = PDF / 多张 = 打包 zip），**取完就在浏览器里，本机不留文件**。
    token = pdf_cache.put(result.files) if result.files else ""
    batch_name = Path(result.batch_dir).name if result.batch_dir else ""
    items = [
        ItemOutcomeOut(
            notice_id=o.notice_id,
            bill_no=o.bill_no,
            ok=o.ok,
            reason=o.reason,
            pdf_path=o.pdf_path,
            download_url=(
                f"/api/m03/pdf/{token}" if token
                # ⚠️ 兜底：**显式给了目录**（工具 / 自检）那种走旧路径 —— 生产路径已不落盘
                else (f"/api/m03/pdf/{batch_name}/{Path(o.pdf_path).name}"
                      if o.pdf_path and batch_name else "")
            ),
        )
        for o in result.outcomes
    ]
    resp = BatchResponse(
        mode=result.mode,
        total=result.total,
        success=len(result.success),
        failed=len(result.failed),
        unprinted_bill_nos=result.unprinted_bill_nos,
        batch_dir=result.batch_dir,
        items=items,
    )
    # 001-08 / 001-03 / PDF-001-05：批内存在未产出 ⇒ 随响应显式带出（前端必须展示，不得静默）
    if resp.failed:
        logger.warning("批量{} 未产出 {} 张：{}", result.mode, resp.failed, resp.unprinted_bill_nos)
    return resp


@router.get("/pdf/{batch}/{name}")
def download_pdf(batch: str, name: str) -> FileResponse:
    """产物取用入口（PDF-001-04）—— 仅允许取 `artifacts/pdf/` 下的文件（防目录穿越）。"""
    root = get_settings().pdf_export_path.resolve()
    target = (root / batch / name).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="产物不存在")
    return FileResponse(target, media_type="application/pdf", filename=name)


@router.get("/pdf/{token}")
def download_batch(token: str) -> Response:
    """把**这一批**导出产物交给浏览器（`PDF-001-04` 的新形态 · 2026-09-20）。

    - **单张** ⇒ 直接回那个 PDF；**多张** ⇒ **打包成一个 zip** 一次下载
      （⚠️ 浏览器不允许一次响应触发 N 个下载 ⇒ 多张只能打包，这是唯一的办法）。
    - ⭐ 字节来自 `pdf_cache`（**不落盘**）—— 渲染出来就趁热交给浏览器，
      **本机不留文件**（用户 2026-09-20 口径）。
    - ⚠️ 取不到（过期 / 服务重启过 / token 是伪造的）⇒ **404 ＋ 中文**，
      ⛔ **绝不静默回一个空文件/空 zip** —— 那会让人以为"导出成功但里面没东西"，是最难查的一类。
    - ⚠️ 文件名**由后端带出**（`X-Export-Filename`，UTF-8 percent-encoded）——
      ⛔ 不让壳自己拼：命名规则一旦两处各写一份，改一处就会静默走形（同 `m06`/`m07`/`m08` 的口径）。
    """
    files = pdf_cache.get(token)
    if not files:
        raise HTTPException(
            status_code=404,
            detail="导出产物已过期（或服务重启过）—— 请重新点一次「只导出 PDF」",
        )
    if len(files) == 1:
        name, blob = next(iter(files.items()))
        return Response(content=blob, media_type="application/pdf", headers=_download_headers(name))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, blob in files.items():
            zf.writestr(name, blob)
    zip_name = f"付款通知书_{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers=_download_headers(zip_name))


def _download_headers(name: str) -> dict[str, str]:
    """浏览器下载头。⚠️ 中文名走 **RFC 5987**（`filename*=UTF-8''…`）—— 裸 `filename=` 遇中文会乱码。"""
    return {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}",
        "X-Export-Filename": quote(name),
    }


@router.get("/settings/printers", response_model=list[str])
def list_local_printers() -> list[str]:
    """本机装了驱动的打印机名（给设置弹窗选 —— 选「系统驱动」通道时**名字要一字不差**）。

    ⚠️ 拿不到就回**空表**（没装 `pywin32` / 不是 Windows）：说明"给不了提示"，⛔ 不是错误、⛔ 不猜名字。
    """
    return list_printers()


@router.get("/settings/printer", response_model=PrinterSettingResponse)
def get_printer_setting() -> PrinterSettingResponse:
    """打印机设置当前值（设置弹窗回填用）—— **地址 ＋ 出纸通道 ＋ 打印机名**（`TAIL-46`-③）。"""
    s = get_settings()
    return PrinterSettingResponse(
        printer_ipp_url=s.printer_ipp_url,
        print_mode=s.print_mode or "auto",
        printer_name=s.printer_name or "",
    )


@router.put("/settings/printer", response_model=PrinterSettingResponse)
def set_printer_setting(req: PrinterSettingRequest) -> PrinterSettingResponse:
    """修改打印机设置（SETUP-001）：写 `.env` + `cache_clear()` ⇒ **即时生效、无需重启**。

    ⚠️ 三项**一起写**；任一项非法 ⇒ **一个字都不写**（先校验后落盘 —— 不许出现"地址改了、通道没改"的半套）。
    """
    out = apply_printer_setting(
        req.printer_ipp_url, mode=req.print_mode, printer_name=req.printer_name
    )
    return PrinterSettingResponse(**out)


# ⚠️ 2026-09-19（`§19` 批 4 · **S4⑤**）：本文件原先还在底部**兼容再导出**一个页面 router
#    （`page_router`，实体在 `notice_router.py`）—— 页面已全部删除（授权 `D18`），该再导出随之删掉。
#    MOD-03 对外的可调用面 = 本 router（`/api/m03/*` 抓取 / 打印 / PDF / 设置）
#    ＋ `notice_api_router`（`/api/m03/*` 列表与行级动作）。⛔ 别再往这里挂页面。

__all__ = ["router", "apply_fetched_row"]
