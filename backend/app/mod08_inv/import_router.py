"""`MOD-08` 库存单据明细 · **手动 Excel 导入**（§3.6 的降级通道）—— 路由（三步）。

⚠️ **与抓取同一条管线**：解析 = `importer.parse_rows`（按表头认列 · 缺关键列即报错）；
   分组 = `fetch_service.group_by_scope`；落库 = `repository.upsert_details`（幂等刷新）。
   ⇒ 本层**不另写判定**，只做「选文件 → 预览 → 确认」的编排。
⚠️ **预览不写库**：解析结果暂存 `core.preview_store`，确认时凭 token 取回（**不重新解析文件**）。
⚠️ **本页不写执行记录**：`RunRecord` 的 `run_type` 只登记 `fetch` / `print` / `export_pdf`；
   手动导入不是抓取 ⇒ 看板的「本月尚未抓取」在手动补数后**仍应提示**（那是事实）。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from app.core import preview_store
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod08_inv import importer
from app.mod08_inv.import_view import render_import_page
from app.mod08_inv.repository import upsert_details

router = APIRouter(tags=["mod08-import"])


def _payload(rows: list[dict]) -> dict:
    """解析结果 → 可暂存的纯数据（金额列转串；**不含文件本体、不含密钥**）。"""
    out: list[dict] = []
    for row in rows:
        out.append({k: (f"{v}" if k in importer.NUMERIC_FIELDS else v) for k, v in row.items()})
    return {"rows": out}


def _rows_of(payload: dict) -> list[dict]:
    """暂存结果 → 规范行（金额列转回 `Decimal`；**不重新解析文件**）。"""
    out: list[dict] = []
    for row in payload.get("rows") or []:
        out.append({k: (Decimal(str(v)) if k in importer.NUMERIC_FIELDS else v)
                    for k, v in row.items()})
    if not out:
        raise MustReportError("预览结果里没有可写入的行 —— 请重新上传文件解析一次。")
    return out


def _groups_of(rows: list[dict]) -> list[dict]:
    """按「核算年月 ＋ 仓库」分组 → 预览用的小表（**与落库范围同一把尺**）。"""
    from app.core.money import sum_money
    from app.mod08_inv.fetch_service import group_by_scope

    out: list[dict] = []
    for (ym, warehouse), group in sorted(group_by_scope(rows).items()):
        out.append({"ym": ym, "warehouse": warehouse, "rows": len(group),
                    "amount": f'{sum_money([r.get("amount") for r in group]):.2f}'})
    return out


def _apply(s, rows: list[dict]) -> dict:
    """分组 ＋ **幂等刷新**落库 → 逐范围统计（与抓取**同一个出口**）。"""
    from app.mod08_inv.fetch_service import group_by_scope

    groups: list[dict] = []
    totals = {"inserted": 0, "updated": 0, "deleted": 0, "kept_with_adjustment": 0}
    for (ym, warehouse), group in sorted(group_by_scope(rows).items()):
        part = upsert_details(s, ym=ym, warehouse=warehouse, rows=group)
        for key in totals:
            totals[key] += part[key]
        groups.append({"ym": ym, "warehouse": warehouse, "rows": len(group), **part})
    return {"groups": groups, "totals": totals}


# ---------------------------------------------------------------- 页面（三步）


@router.get("/m08/import", response_class=HTMLResponse)
def page() -> HTMLResponse:
    """手动导入页（列要求 ＋ 三步走）。"""
    return HTMLResponse(render_import_page())


@router.post("/m08/import/preview", response_class=HTMLResponse)
async def preview(file: UploadFile = File(...)) -> HTMLResponse:
    """解析上传的 `.xlsx` → **预览**（⚠️ **一个字节都不写库**）。"""
    try:
        content = await file.read()
        rows = importer.parse_rows(content)
        token = preview_store.save(_payload(rows))
        return HTMLResponse(render_import_page(
            preview={"rows": len(rows), "groups": _groups_of(rows)}, token=token))
    except MustReportError as exc:
        return HTMLResponse(render_import_page(message=exc.message, kind="err"))
    except Exception as exc:                                # noqa: BLE001
        return HTMLResponse(render_import_page(
            message=f"解析失败：{type(exc).__name__}: {exc}", kind="err"))


@router.post("/m08/import/confirm", response_class=HTMLResponse)
def confirm(token: str = Form(...)) -> HTMLResponse:
    """凭 token 取回解析结果 → **幂等刷新落库** → 给逐范围统计。"""
    try:
        rows = _rows_of(preview_store.load(token))
        with session_scope() as s:
            result = _apply(s, rows)
        t = result["totals"]
        return HTMLResponse(render_import_page(
            result=result,
            message=f"已导入 {len(rows)} 行（{len(result['groups'])} 个「核算年月 ＋ 仓库」范围）："
                    f"新增 {t['inserted']} · 更新 {t['updated']} · 删除 {t['deleted']} · "
                    f"因有调整单而保留 {t['kept_with_adjustment']}",
            kind="ok"))
    except MustReportError as exc:
        return HTMLResponse(render_import_page(message=exc.message, kind="err"))
    except Exception as exc:                                # noqa: BLE001
        return HTMLResponse(render_import_page(
            message=f"导入失败：{type(exc).__name__}: {exc}", kind="err"))


__all__ = ["router"]
