"""`MOD-04` 的 **JSON API**（前端壳 · `TAIL-35`）—— **手动行 ＋ 导入**。

⚠️ **为什么单独一件**：`router.py` 已顶到 **>600 行**（`doc_audit` 的 `T5` 是**禁合入硬线**）
   ⇒ 把 JSON 端点与页面（PRG）端点分家。
⚠️ 本层**不写任何判定**：一律复用既有出口 ——
   `plan_manual.manual_row_payload`（手动行校验 · 与 PRG 端点**同一份**）·
   `importer.parse_workbook` / `attach_projects` / `repo.merge_month`（导入 · §9.5 幂等）。
⚠️ 会话走 `session_scope()`（**与 `router.get_db` 等价**，但它经 `Depends` 暴露 ⇒ 自检可注入桩）。
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod04_plan import repository as repo
from app.mod04_plan.importer import attach_projects, parse_workbook
from app.mod04_plan.plan_manual import assert_manual_editable, manual_row_payload
from app.mod04_plan.project_views import project_briefs, project_label

router = APIRouter(tags=["mod04"])


class PlanRowRequest(BaseModel):
    """手动**新增 / 编辑**一行付款计划（§4.3.3.1）—— 字段名与 `manual_row_payload` 对齐。"""

    row_id: str = ""
    row_ym: str = ""
    project_id: str = ""
    doc_no: str = ""
    flow_amount: str = ""
    planned_amount: str = ""
    pay_date: str = ""
    pay_method: str = ""
    remark: str = ""


@router.post("/api/m04/plans")
def api_plan_row_save(req: PlanRowRequest) -> dict:
    """⭐ **`TAIL-35`：手动行 新增 / 编辑**（§4.3.3.1）—— 校验**唯一出口 = `plan_manual.manual_row_payload`**。

    ⭐ 与 PRG 端点（`POST /m04/row/save`）**同一份判定**：⛔ 不在本层另写一套（`D18`：判定一律后端）。
    ⚠️ 校验不过 **抛 `MustReportError`** ⇒ 400 ＋ 原样原因；壳侧据「§4.3.3.1 校验失败 = **保留已填内容**」
       把原因显示出来、**不清空草稿**。
    ⚠️ 手动行落库后**与导入行同住一表、走同一条审查链路**（§4.3.4）；导入**不触碰**它（§9.5）。
    """
    payload = manual_row_payload(
        year_month=req.row_ym, project_id=req.project_id, doc_no=req.doc_no,
        flow_amount=req.flow_amount, planned_amount=req.planned_amount,
        pay_date=req.pay_date, pay_method=req.pay_method, remark=req.remark,
    )
    values = dict(payload.values)
    with session_scope() as session:
        if values.get("project_id") is not None:
            values["project_input"] = project_label(session, values["project_id"])

        if str(req.row_id or "").strip().isdigit():
            row = repo.get_row(session, int(req.row_id))
            if row is None:
                raise MustReportError(f"要保存的计划行 {req.row_id} 不存在")
            assert_manual_editable(row)                  # 只有手动行可编辑（§4.3.3.1）
            touched = repo.update_manual_row(session, row, values)
            msg = f"已保存手动行 {row.id}（改动 {len(touched)} 个字段：{'、'.join(touched) or '无'}）"
        else:
            row = repo.create_manual_row(session, values)
            msg = f"已新增 1 行手动付款计划（行号 {row.id}）"
        row_id = row.id
    return {"ok": True, "row_id": row_id, "message": msg + "；" + "；".join(payload.notes)}


@router.post("/api/m04/import")
async def api_plan_import(year_month: str = Form(""), file: UploadFile = File(...)) -> dict:
    """⭐ **`TAIL-35`：导入付款计划 Excel**（§4.3.3）—— 按所选月份「**清该月自动行 → 重写该批**」（§9.5 幂等）。

    ⭐ 与 PRG 端点**同一实现链**（`parse_workbook` → `attach_projects` → `repo.merge_month`）。
    ⚠️ **手动行不被触碰**（§9.5）；⛔ **不做判重拦截** —— 同月同单据号两行是 §4.3.4 的「重复上报」，导入照收、审查暴露。
    ⚠️ 上传形态 = **multipart/form-data**（⛔ 不是 JSON）⇒ 壳侧必须用 `FormData`。
    ⚠️ 原型 `V.m04` 的导入是**一步式**（弹窗选月 → 选文件 → 导入）—— **没有「预览」这一步**，
       所以这里也**不发明**预览（§15 `TAIL-35` 原先写的「三步」是推测，已按原型订正）。
    """
    try:
        data = await file.read()
        with session_scope() as session:
            parsed = parse_workbook(data)
            rows = attach_projects(parsed.rows, project_briefs(session))
            result = repo.merge_month(session, year_month=year_month, rows=rows)
    except MustReportError:
        raise                                            # 口径性报错（年月不合法 / 表头认不出）原样透出
    except Exception as exc:                             # noqa: BLE001
        raise MustReportError(f"解析失败：{type(exc).__name__}: {exc}") from exc

    msg = (
        f"已导入 {len(rows)} 行到 {year_month}：新建 {result['created']} · 复用更新 {result['updated']}"
        f" · 删除该月残影 {result['deleted']}"
        f"（可手改列一律保留；该月手动行 {result['manual_kept']} 行未被触碰）"
    )
    if parsed.alerts:
        msg += "；提示：" + "；".join(parsed.alerts[:3])
    return {"ok": True, "rows": len(rows), "stats": result, "year_month": year_month,
            "alerts": list(parsed.alerts or []), "message": msg}


__all__ = ["router"]
