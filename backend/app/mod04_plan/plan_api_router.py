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


class TokenRequest(BaseModel):
    token: str


@router.post("/api/m04/import/parse")
async def api_plan_import_parse(year_month: str = Form(""), file: UploadFile = File(...)) -> dict:
    """⭐ **`TAIL-69` 第 ① 步：解析并预览**（**一个字节都不写库** —— 校验前不碰库）。

    ⭐ 产出 = `token` ＋ 预览（行数 / 项目匹配盘点 / 解析提示）—— 用户在界面上**先看见再确认**；
       项目匹配**在解析时完成**（确认时**不重算** ⇒ 「所见即所落」，⛔ 第二份口径）。
    ⚠️ 与旧一步式端点**同一实现链**（`parse_workbook` → `attach_projects`），只差「写不写库」。
    """
    try:
        data = await file.read()
        with session_scope() as session:
            parsed = parse_workbook(data)
            rows = attach_projects(parsed.rows, project_briefs(session))
    except MustReportError:
        raise                                            # 口径性报错（表头认不出）原样透出
    except Exception as exc:                             # noqa: BLE001
        raise MustReportError(f"解析失败：{type(exc).__name__}: {exc}") from exc
    if not str(year_month or "").strip():
        raise MustReportError("导入前**必须先选「年月」**（本批数据一律归入所选月份，§4.3.3）")
    from app.import_kit import staging                    # noqa: PLC0415
    from app.mod04_plan.importer import match_summary, stage_payload

    token = staging.save_preview(stage_payload(parsed, rows, year_month))
    return {"ok": True, "token": token,
            "preview": {"year_month": year_month, "columns": dict(parsed.columns),
                        "header_row": parsed.header_row, "alerts": list(parsed.alerts or []),
                        "match": match_summary(rows)}}


@router.post("/api/m04/import/confirm")
def api_plan_import_confirm(req: TokenRequest) -> dict:
    """⭐ **`TAIL-69` 第 ② 步：确认落库**（凭 `parse` 给的 token；幂等口径与旧一步式**一字不差**）。

    ⚠️ token 不存在 / 过期 ⇒ `preview_store` **显式报错**（⛔ 不静默当成空导入 —— 空导入会清掉该月）。
    """
    from app.import_kit import staging                    # noqa: PLC0415
    from app.mod04_plan.importer import restore_rows

    payload = staging.load_preview(req.token)
    year_month, rows = restore_rows(payload)
    alerts = list(payload.get("alerts") or [])
    with session_scope() as session:
        result = repo.merge_month(session, year_month=year_month, rows=rows)
    msg = (
        f"已导入 {len(rows)} 行到 {year_month}：新建 {result['created']} · 复用更新 {result['updated']}"
        f" · 删除该月残影 {result['deleted']}"
        f"（可手改列一律保留；该月手动行 {result['manual_kept']} 行未被触碰）"
    )
    if alerts:
        msg += "；提示：" + "；".join(alerts[:3])
    return {"ok": True, "rows": len(rows), "stats": result, "year_month": year_month,
            "alerts": alerts, "message": msg}


@router.post("/api/m04/import")
async def api_plan_import(year_month: str = Form(""), file: UploadFile = File("")) -> dict:
    """⛔ **已退役**（`TAIL-69` · 2026-09-22）：一步式导入升级为 **`parse` → `confirm` 两步**（预览不写库）。

    ⚠️ **路由先留着、实现先撤**：壳早已切到新端点；留路由是为了**缓存的旧页面**打过来时
       收到一句**明白话**（"请刷新"），而不是一个没头没脑的 404。
       ⭐ 判据已全部搬到新出口（`test_plan_import.py` 两步两条，**claim 一字未改**）；
       下一轮清尾巴时连路由一起删（届时只删路由，判据已在新出口）。
    """
    raise MustReportError(
        "这个导入入口已升级为「**解析预览 → 确认落库**」两步（2026-09-22）。"
        "请**刷新页面**后在「付款计划」页重新打开导入弹窗。"
    )


__all__ = ["router"]
