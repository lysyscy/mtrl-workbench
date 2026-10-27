"""`MOD-08` 路由：明细总表页（`/m08`）＋ 调整单（`/m08/adjust/{id}`）＋ 抓取弹窗（`/m08/fetch-dialog`）。

⚠️ 写操作一律 **PRG**（POST → 303 → GET），与全站一致；校验失败**不写库**、原地回显。
⚠️ 调整单的判据走 `domain.adjustment_problem`（唯一出口），路由**不另写判定**。
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.core.money import to_money
from app.mod08_inv import domain as D
from app.mod08_inv.repository import (
    adjustments,
    clear_adjustment,
    load_rows,
    save_adjustment,
    save_linked_adjustment,
)
# ⛔ **「手动 Excel 导入」已整体删除**（用户 2026-09-22 裁定：「库存单据手动导入这个模块给删掉，
#    不要了」—— 降级通道改为：i8 不可用 ⇒ **显式报错待人处理**，⛔ 不做手动兜底入口）。
#    曾经的 `import_router.py` ＋ `import_view.py` ＋ `import_api.py` ＋ `importer.py` ＋ 壳 `V.m08imp`
#    **全部已删**（保留相应端点/注册行为测试）。
# ⚠️ 2026-09-19（`§19` 批 2）：`app.mod08_inv.view`（`render_inv_page`/`fetch_dialog_html`/`render_adjust_page`）
#    已随「明细总表页半边」整体删除（授权 `D18`）—— ⛔ 别再加回来。

router = APIRouter(tags=["mod08"])


# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 2**）：**本模块的「明细总表页」半边已删**（授权 `D18`）——
#    `inv_page`（`GET /m08`）· `inv_fetch`（PRG `POST /m08/fetch`）· `fetch_dialog`（`GET /m08/fetch-dialog`）·
#    `adjust_page` / `adjust_save`（`/m08/adjust/{row_id}`）＋ `_safe_back` ＋ `view.py`（327 行）。
#    ⇒ 壳走的是 **JSON API**（`/api/m08/inventory` · `/api/m08/adjust` · `/api/m08/adjust/clear` ·
#      `/api/m08/fetch` · `/api/m08/inventory/export` —— 五个都在本文件下方 ✓）。
# ⚠️ **「手动 Excel 导入」半边** —— ⛔ **2026-09-22 已整体删除**（用户裁定「不要了」；
#    i8 不可用 ⇒ 显式报错待人处理，不做手动兜底）。服务端渲染页与三条 PRG 更早（`D18`）已删 ✓。


# ============================================================ JSON API（前端壳：原型直接接数据）
# ⚠️ 数据形状一律对齐**原型 `V.m08` 的字段名**（`docNo`/`amt`/`wh`…）由**壳的适配层**转 ——
#    后端这里只出**域内规范名**（`doc_no`/`amount`/`warehouse`…），与页面渲染同源。


class AdjustRequest(BaseModel):
    """打 / 改调整单（`ENT-04`）。`amount` 用 **str**（金额一律字符串进、判据自己解析）。"""

    row_id: int
    amount: str = ""
    remark: str = ""
    values: dict[str, str] | None = None
    basis: dict[str, str] = {}
    expected: str = ""


class ClearAdjustRequest(BaseModel):
    row_id: int
    expected: str | None = None


class FetchRequest(BaseModel):
    """按月抓取（`API-03`）。

    ⚠️ `confirm` = **用户在壳的抓取弹窗里点过「按 X 抓取」**（D9 二次确认）。
    ⛔ 缺它一律拒（400）—— 防止任何"直接打进来"的静默抓取（**会顶号**）。
    """

    month: str = ""
    confirm: bool = False


def _money(x) -> float:
    """金额 → JSON 数字（2 位）。⚠️ 出 **number** 而不是字符串：壳里这些值直接参与求和。"""
    try:
        return round(float(to_money(x)), 2)
    except (TypeError, ValueError):
        return 0.0


@router.get("/api/m08/inventory")
def api_inventory() -> dict:
    """明细行（**全量**，已叠加调整后金额）＋ 调整单清单 —— 供前端壳。

    - ★ **全量**返回、筛选由前端做（与 `/api/m03/notice-list?period=` 同款）：原型的
      筛选 / 排序 / 合计 / 列筛选逻辑**一行不改**（`D18`）。
    - ⛔ 不含「操作」列（按钮 HTML 只在页面上成立 —— 全站同款，见 `PAGE_ONLY_KEYS`）。
    - `c5` = **材料 5 类别**（物料性质归集）—— 唯一出口 = `mod06_proc.domain.to_category`；
      壳里「过程资料」的入库 / 出库 5 列聚合直接吃它（⛔ 不在前端重写归集规则）。
    - `adjusted` = 这一行有没有调整单（壳里判 `adjOf` 用它，也用于「只看被调整行」筛选）。
    """
    from app.mod06_proc.domain import to_category, MATERIAL_PROPERTIES
    from app.mod08_inv.adjustment_values import edit_token, effective_value, original_values, adjustment_values

    with session_scope() as s:
        adjs = adjustments(s)
        rows = load_rows(s, adjs=adjs)                       # 本请求复用调整单映射
        items = [
            {
                **r,
                "c5": to_category(effective_value(r, "material_property")) or "",
                "adjusted": r["id"] in adjs,
                "original_values": original_values(r),
                "edit_token": edit_token(r, adjs.get(r["id"])),
            }
            for r in rows
        ]
        payload = [
            {
                "id": a.id,
                "row_id": a.row_id,
                "before_amount": _money(a.before_amount),
                "amount": _money(a.amount),
                "values": adjustment_values(a),
                "before_values": dict(a.before_values or {}),
                "remark": a.remark or "",
                "operator": a.operator or "",
                "changed_at": a.changed_at.strftime("%Y-%m-%d %H:%M") if a.changed_at else "",
            }
            for a in sorted(adjs.values(), key=lambda x: x.id)
        ]
        projects = sorted({str(r.get("warehouse") or "") for r in rows if r.get("warehouse")})
    return {"rows": items, "adjustments": payload, "count": len(items), "projects": projects, "material_properties": list(MATERIAL_PROPERTIES)}


@router.post("/api/m08/adjust")
def api_adjust(req: AdjustRequest) -> dict:
    """打 / 改调整单 —— **判据唯一出口 = `domain.adjustment_problem`**（金额 ≥ 0 · 备注必填）。

    失败 **抛 `MustReportError`** ⇒ 400 ＋ 原样原因（壳侧把原因给用户，不静默）。
    ⚠️ 原始数据**永不被改**：调整单独立存储（`inv_adjustment`），抓取只刷新 `inv_detail`。
    """
    problem = D.adjustment_problem(req.amount, req.remark) if req.values is None else ""
    if problem:
        raise MustReportError(problem)
    try:
        with session_scope() as s:
            if req.values is None:
                adj = save_adjustment(s, row_id=req.row_id, new_amount=req.amount,
                                      remark=req.remark, operator=current_operator())
            else:
                adj = save_linked_adjustment(s, row_id=req.row_id, values=req.values,
                    basis=req.basis, expected=req.expected, remark=req.remark, operator=current_operator())
            out = {
                "ok": True,
                "row_id": adj.row_id,
                "before_amount": _money(adj.before_amount),
                "amount": _money(adj.amount),
                "remark": adj.remark or "",
                "operator": adj.operator or "",
            }
    except ValueError as exc:                               # 行不存在 / 判据不过
        raise MustReportError(str(exc)) from exc
    return out


@router.post("/api/m08/adjust/clear")
def api_adjust_clear(req: ClearAdjustRequest) -> dict:
    """**撤销调整单** —— 回到 i8 原始金额（原始数据未受影响，两表物理分离）。

    依据：原型 `V.m08` 的调整单弹窗**有「撤销调整单」按钮**（**原型即交互规格**，`D18`）。
    """
    with session_scope() as s:
        clear_adjustment(s, row_id=req.row_id, expected=req.expected)
    return {"ok": True, "row_id": req.row_id}


@router.post("/api/m08/fetch")
def api_fetch(req: FetchRequest) -> dict:
    """**按月抓取**库存单据明细（`API-03`）—— 人工触发。

    ⚠️ **会登录 i8 并强踢在线用户**（D9）：`confirm` 必须为真（= 用户已在壳的弹窗里确认过）。
    ⚠️ 失败**显式报错待人处理**（原因 + 请稍后重试；⛔ 无手动兜底 —— 2026-09-22 用户裁定），**绝不自动重试登录**（D9）。
    """
    from app.mod08_inv import fetch_service as FS

    with session_scope() as s:
        return FS.run_fetch(
            s, year_month=req.month, confirmed=req.confirm, operator=current_operator()
        )


@router.get("/api/m08/inventory/export")
def api_export_inventory(
    request: Request,
):
    """导出库存单据明细表**成品 xlsx**（含「过程资料」「安全文明施工费」两张真透视）—— 浏览器直接下载（`TAIL-04`）。

    口径 = **模板法**：以「用户手作成品 xlsx」为基底做 `zip` 字节替换
    （`docs/reference/template-export.md`）；两张透视与数据缓存**逐项对账**（容差 0.01）。

    - 取数 = **HTTP 现导**（`report_export.export`，`spec_key='inv'`）；期间缺省 = 本页默认月（§9.2）。
    - ⭐ 2026-09-21 用户裁定「抓取导出分开」：src = **最近一次抓取的源文件缓存**（`source_cache`），
      **导出不碰 i8** ⇒ 不再有 `allow_kick`（D9 的二次确认都在「抓取」侧）。缺缓存 ⇒ 中文报「请先抓取」。
    - ⚠️ 三种失败（模板缺失/损坏 · 该月没有明细 · **缓存级对账不过**）⇒ **不产出文件**，
       改成 **JSON 200 ＋ `ok:false` ＋ 中文原因** —— 壳侧据 `content-type` 分流：
       `application/json` ⇒ 弹原因；否则当文件下载。
       （⛔ 不回 4xx：那样用户只看到一句 `HTTP 400`，而"该月没有数据"这种话必须给人看。）
    """
    from fastapi.responses import FileResponse, JSONResponse
    from urllib.parse import quote

    from app import export_registry as EXP
    EX = EXP.get("service")

    period = str(request.query_params.get("period") or "").strip() or D.default_month()
    try:
        with session_scope() as s:
            path = EX.export_inventory(s, period)
    except MustReportError as exc:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(exc)})
    # ⚠️ 文件名**由后端带出**（`X-Export-Filename`，UTF-8 percent-encoded）——
    #    ⛔ 不让壳自己拼：命名规则一旦两处各写一份，改一处就会静默走形。
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
        headers={"X-Export-Filename": quote(path.name)},
    )


__all__ = ["router"]
