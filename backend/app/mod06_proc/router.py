"""MOD-06 过程资料读取、导出及机械手录；明细 JSON 由 workbench_api 持有。"""

from __future__ import annotations

from decimal import Decimal, DecimalException
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod06_proc import domain as D
from app.mod06_proc import mech_ui, repository as repo
from app.mod06_proc.service import build_page_data, parse_state
# ⚠️ 2026-09-18（`§19` 批 2）：`app.mod06_proc.view`（`render_proc_page`/`render_export_preview`）
#    的导入已随"过程资料页半边"删除 —— ⛔ 别再加回来（那两个渲染件已整体删除）。
from app.core.query import flatten_query

router = APIRouter(tags=["mod06"])

from app.mod06_proc.workbench_api import router as mechanical_router

router.include_router(mechanical_router)

MESSAGE_KINDS = ("ok", "wn", "err")


# 导出入口沿用旧的假值折叠规则；筛选状态的 query_one 保留 0，两者不混用。
def _one(params: dict, name: str, default: str = "") -> str:
    value = params.get(name, default)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


@router.get("/api/m06/export")
def api_proc_export(request: Request):
    """导出**过程资料成品**（`TAIL-04` 路径① 片 4a）—— **每个项目一本工作簿**；
    选 ≥2 个项目 ⇒ 打成一个 zip。

    ⚠️ 失败（**一个项目都没选** · 项目**没有数据** · 项目**不在档案里**（取不到展示名）·
      模板缺失/损坏 · **显示区对账不过**）⇒ **JSON 200 ＋ `ok:false` ＋ 中文原因**，
      壳侧据 `content-type` 分流（同另四条导出）。⛔ 不回 4xx：那样用户只看到 `HTTP 400`。
    ⚠️ 取数**跟随当前所显示的那张表**（`tab`，001-04）—— 壳侧原样带过来，⛔ 不在前端另算：
      表① 原始 / 表② 调整后 / **差异表 = 逐格差额**（用户 2026-09-18 裁：三张**同形态**、只有数据不同）。
    """
    from urllib.parse import quote

    from fastapi.responses import FileResponse, JSONResponse

    from app import export_registry as EXP
    EX = EXP.get("service")

    params = flatten_query(request.query_params)
    keys = [k.strip() for k in str(_one(params, "projects") or "").split(",") if k.strip()]
    try:
        with session_scope() as s:
            path = EX.export_proc(s, keys, D.tab_of(_one(params, "tab")), _one(params, "ym"))
    except MustReportError as exc:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(exc)})
    media = ("application/zip" if path.suffix == ".zip"
             else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return FileResponse(path, media_type=media, filename=path.name,
                        headers={"X-Export-Filename": quote(path.name)})


@router.get("/api/m06/matrix")
def api_proc_matrix():
    """过程资料所有项目、核算月与汇总的唯一读取出口。"""
    from app.mod06_proc.service import build_matrices
    from app.core.errors import human_reason

    try:
        with session_scope() as s:
            return {"ok": True, **build_matrices(s)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": human_reason("读取过程资料失败", exc)}


# ⚠️ 2026-09-18（`§19` 批 2）：**PRG 版机械手录已删**（`POST /m06/mech` ＋ `mech_save`）——
#    壳走的是 JSON 版 `POST /api/m06/mech`（与它**同一份判定** `mech_ui.parse_mech_values`
#    ＋ `repo.save_mech` ✓，见本文件下方）。⛔ 别把"机械手录"整条当成没实现。
# ---------------------------------------------------------------- ① 机械手录（§5.2.5 ③）


# ============================================================ JSON API（前端壳：原型直接接数据）


@router.get("/api/m06/mech")
def api_mech() -> dict:
    """机械 6 列的**有效值**（按分界月切来源）→ 按「仓库名 → 核算月 → [6 列]」聚合。

    ⭐ **出参形状刻意与原型 `MACH6` 一致** ⇒ 壳里那十几处引用（过程资料 17 列的机械 6 列 /
    活动大表 / 机械结算 / 台账项目候选）**一行不用改**，只换数据来源。

    ⭐⭐ 2026-09-26（`TAIL-107` · 用户裁定）：**历史段（≤ 截止核算月）的机械费来自「过程资料导入」
      的定稿快照**，正式段才是手录 ⇒ 本端点按 `domain.column_source` 取数（**同一出口**，
      ⛔ 不在这里另判段）。⚠️ 改前它只回手录值（"全段手录"），而历史段的手录值**页面根本不读**
      ⇒ 那种"录了却不显示"的错配正是本届口径要堵的。
    ⚠️ 机械费是**旁路载体**（正式段 `proc_mech_manual` / 历史段 快照）：重抓 i8 都动不到它（§5.2.5 ③）。
    ⭐ 本表是 **`m05` 机械欠款的结算源** —— 接上它，`m05` 的「机械欠款」才会从 0 变成真数。

    ⚠️ 额外的 `sections`（旧键一个不动，只**多**一个）＝ `{仓库名: {核算月: "history"|"formal"}}`：
       壳侧据此把"历史段不许手录"**在界面上**也说清（守则 §5.5）。
    """
    with session_scope() as s:
        rows = repo.load_mech(s)                      # 手录（正式段）
        snaps = repo.load_history(s)                  # 快照（历史段的材料 ＋ 机械）
        cutoffs = repo.load_cutoffs(s)                # 每个项目的分界月
        from app.mod06_proc import workbench
        details = workbench.detail_signatures(s)
        existing = {(row['warehouse'], row['ym']) for row in rows}
        for wh, months in details.items():
            for ym in months:
                if (wh, ym) not in existing:
                    state = workbench.effective(s, wh, ym)
                    rows.append({'warehouse': wh, 'ym': ym, **state['values'],
                                 'sources': state['sources'], 'effective_signature': state['signature']})

    zeros = [0.0] * len(D.MECH_COLUMNS)

    def _vals(src: dict) -> list[float]:
        """一条源行 → `[6 个金额]`（`MACH6` 的形状：**只能给数**，没有"空态"这一档）。"""
        out: list[float] = []
        for i in range(len(D.MECH_COLUMNS)):
            try:
                out.append(round(float(src.get(f"mech_{i}") or 0), 2))
            except (TypeError, ValueError):
                out.append(0.0)
        return out

    def _key(r: dict) -> tuple[str, str]:
        return str(r.get("warehouse") or "").strip(), str(r.get("ym") or "").strip()

    manual: dict[tuple[str, str], list[float]] = {}
    snap: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        wh, ym = _key(r)
        if wh and ym:
            manual[(wh, ym)] = _vals(r)
    for wh in {str(r.get("warehouse") or "") for r in snaps}:
        for ym, bucket in D.snapshot_by_month(snaps, warehouse=wh).items():
            if wh and ym:
                snap[(wh, ym)] = _vals(bucket)

    # ⭐ 逐月按**分界月**定来源（`column_source` = 唯一出口，⛔ 不在这里另判）：
    #    历史段 ⇒ 快照值；正式段 ⇒ 手录值。两边都取不到 ⇒ 全 0（`MACH6` 只能给数；页面表体的
    #    "空态"那一档由 `domain.build_matrix` 表达，本端点不吃那一套）。
    out: dict[str, dict[str, list[float]]] = {}
    sections: dict[str, dict[str, str]] = {}
    for wh, ym in sorted(set(manual) | set(snap)):
        cut = cutoffs.get(wh) or ""
        section = D.section_of(ym, cut)
        from_snapshot = (D.column_source(D.MECH_KEYS[0], ym=ym, cutoff_ym=cut)
                         == D.SOURCE_SNAPSHOT)
        out.setdefault(wh, {})[ym] = (snap.get((wh, ym), zeros) if from_snapshot
                                      else manual.get((wh, ym), zeros))
        sections.setdefault(wh, {})[ym] = section
    sources, signatures, effective_values = {}, {}, {}
    for row in rows:
        sources.setdefault(row['warehouse'], {})[row['ym']] = row['sources']
        signatures.setdefault(row['warehouse'], {})[row['ym']] = row['effective_signature']
        effective_values.setdefault(row['warehouse'], {})[row['ym']] = {
            column: format(Decimal(str(row[column])), '.2f') if row[column] not in (None, '') else None
            for column in D.MECH_KEYS}
    return {"mech": out, "count": len(rows), "columns": list(D.MECH_COLUMNS),
            "sections": sections, "sources": sources, "effective_signatures": signatures, "detail_signatures": details, "effective_values": effective_values}


class MechSaveRequest(BaseModel):
    """手录机械 6 列（项目键 = 仓库名；`ym` = 核算月；`values` = `{mech_0…mech_5: 原值}`）。"""

    warehouse: str = ""
    ym: str = ""
    values: dict[str, Any] = {}
    confirmed: bool = False
    effective_signature: str = ''
    detail_signature: str = ''


class MaterialSaveRequest(BaseModel):
    warehouse: str
    ym: str
    column: str
    value: Any
    expected: Any


@router.post('/api/m06/material')
def api_material_save(req: MaterialSaveRequest) -> dict:
    from app.core.money import MoneyError, to_money
    warehouse = req.warehouse.strip()
    ym = D.normalize_ym(req.ym)
    if not warehouse or not ym or ym > '2025-11' or req.column not in D.MATERIAL_KEYS:
        raise MustReportError('只能保存 2025-11 及之前的历史材料金额，请核对项目、月份和列。')
    try:
        amount = None if req.value is None or isinstance(req.value, str) and not req.value.strip() else to_money(req.value)
        expected = None if req.expected is None else to_money(req.expected)
        if amount is not None and abs(amount) >= Decimal('10000000000000000'):
            raise MoneyError('金额超出可保存范围')
    except (ValueError, DecimalException) as exc:
        raise MustReportError('金额无效或超出可保存范围，请核对后重试。') from exc
    with session_scope() as s:
        repo.save_material(s, warehouse=warehouse, ym=ym, column=req.column, amount=amount, expected=expected)
    return {'ok': True, 'warehouse': warehouse, 'ym': ym, 'column': req.column}


@router.post("/api/m06/mech")
def api_mech_save(req: MechSaveRequest) -> dict:
    return _save_mech(req, confirm_details=False)


@router.post('/api/m06/mech-cell')
def api_mech_cell_save(req: MechSaveRequest) -> dict:
    return _save_mech(req, confirm_details=True)


def _save_mech(req: MechSaveRequest, *, confirm_details: bool) -> dict:
    """保存实际提交的机械列；任意月份可改，校验失败不写入。"""
    warehouse = str(req.warehouse or "").strip()
    if not warehouse:
        raise MustReportError("没有选中项目 —— 项目键 = 仓库名。")
    ym = D.normalize_ym(req.ym)
    if not ym:
        raise MustReportError(f"核算月认不出：{req.ym or '（空）'} —— 请写 2026-08 这种形态。")
    try:
        values = {k: v for k, v in mech_ui.parse_mech_values(req.values, empty_as_none=confirm_details).items()
                  if k in req.values}
    except ValueError as exc:
        raise MustReportError(f"未保存：{exc}") from exc

    with session_scope() as s:
        parsed = {k: None if v is None else Decimal(v) for k, v in values.items()}
        if confirm_details:
            from app.mod06_proc import workbench
            workbench.save_process_mech(s, ym=ym, warehouse=warehouse, values=parsed,
                confirmed=req.confirmed, effective_signature=req.effective_signature,
                detail_signature=req.detail_signature, operator=current_operator())
        else:
            repo.save_mech(s, ym=ym, warehouse=warehouse, values=parsed, project_id=None)
    return {
        "ok": True, "ym": ym, "warehouse": warehouse,
        "columns": list(D.MECH_COLUMNS),
        "message": f"已保存 {ym} 的机械费",
    }


__all__ = ["router"]
