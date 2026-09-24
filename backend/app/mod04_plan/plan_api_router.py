"""`MOD-04` 的 **JSON API**（前端壳 · `TAIL-35`）—— 现在只剩**手动行**（导入已收进通用面）。

⚠️ **为什么单独一件**：`router.py` 已顶到 **>600 行**（`doc_audit` 的 `T5` 是**禁合入硬线**）
   ⇒ 把 JSON 端点与页面（PRG）端点分家。
⚠️ 本层**不写任何判定**：一律复用既有出口 ——
   `plan_manual.manual_row_payload`（手动行校验 · 与 PRG 端点**同一份**）。
⚠️ 会话走 `session_scope()`（**与 `router.get_db` 等价**，但它经 `Depends` 暴露 ⇒ 自检可注入桩）。
⛔ 2026-09-23（`TAIL-75` 余项 · 用户裁定）：**付款计划的导入面已连件删除** ⇒ 只留通用面
   （`/api/imp/m04_plan/*`，落库仍走 `repo.merge_month`）。详见本文件下方那段说明。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod04_plan import repository as repo
from app.mod04_plan.plan_manual import assert_manual_editable, manual_row_payload
from app.mod04_plan.project_views import project_label

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


# ⛔ `m04` 付款计划的**页内导入面**已全部**连件删除**（`TAIL-75` 余项 · 2026-09-23 **用户裁定**：
#    「导入基本上只在刚开始用系统时导一次，之后就实时更新了」⇒ **只留通用面**）：
#    · `POST /api/m04/import/parse`（`TAIL-69` 第①步 预览）—— **已删**
#    · `POST /api/m04/import/confirm`（第②步 落库，凭 token）—— **已删**
#    · `POST /api/m04/import`（一步式，2026-09-22 起**已软退役**、路由留着回"请刷新" ⇒ 同批删掉）
#    · 只服务它们的 `TokenRequest`
#    ⭐ 现在付款计划的导入 = 壳「**数据导入**」页选 `付款计划`（`m04_plan` 域 · `/api/imp/m04_plan/*`）；
#    落库口径仍是**既有出口** `repo.merge_month`（§9.5 幂等）—— 域钩子 `imp_spec.commit` 调的就是它。
#    ⚠️ 域内的解析出口（`importer.parse_workbook` / `attach_projects` / `stage_payload` /
#    `restore_rows` / `match_summary`）**保留** —— 与 `m05` 留 `parse_rows`、`m06` 留 `parse_sheet` 同款
#    （域业务不随页面存亡；通用面的域声明也用着前两件）。
#    ⛔ 别再建"第二条付款计划导入路"（`CANCELLED` 有登记，`T8` 会抓）。


__all__ = ["router"]
