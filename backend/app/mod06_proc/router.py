"""`MOD-06` 路由：过程资料页（`/m06`）＋ **机械手录**（`/m06/mech`）＋ **历史导入三步**（`/m06/import*`）。

⚠️ 只读页面：**材料列没有写路径**（§5.2.3 单向流）—— 要改材料数据回 `/m08` 打调整单。
⚠️ 本模块**只有两条写路径**：① **机械手录**（`/m06/mech` → 旁路表，两段都可录，§5.2.5 ③）
   ② **历史导入**（`/m06/import/*` → 只写历史段快照，§5.2.5 ①②）。
⚠️ 写操作一律 **PRG**（POST → 303 → GET）或就地回显；校验失败**一个字都不写库**。
⚠️ 查询参数的解析出口与 `MOD-08` 共用（`query_params`），不各写一份。
"""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core import preview_store
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod06_proc import domain as D
from app.mod06_proc import importer, mech_ui, repository as repo
from app.mod06_proc.import_view import render_import_page
from app.mod06_proc.service import build_import_data, build_page_data, parse_state
from app.mod06_proc.view import render_export_preview, render_proc_page
from app.mod08_inv.router import query_params

router = APIRouter(tags=["mod06"])

MESSAGE_KINDS = ("ok", "wn", "err")


def _one(params: dict, name: str, default: str = "") -> str:
    value = params.get(name, default)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


# ---------------------------------------------------------------- 过程资料页


@router.get("/m06", response_class=HTMLResponse)
def proc_page(request: Request):
    params = query_params(request)
    with session_scope() as s:
        data = build_page_data(s, parse_state(params))
    kind = _one(params, "msgkind") or "ok"
    return HTMLResponse(render_proc_page(
        data,
        message=_one(params, "msg"),
        kind=kind if kind in MESSAGE_KINDS else "ok",
        mech_ym=D.normalize_ym(_one(params, "mech_ym")),
    ))


@router.get("/m06/export", response_class=HTMLResponse)
def proc_export(request: Request):
    """导出清单预览（§7.1 · 001-01）。

    ⚠️ 本端点**只出清单**（与原型一致）；**真实文件写出**归切片 6 的 `ACC-X-EXP-001`。
    """
    with session_scope() as s:
        return HTMLResponse(render_export_preview(build_page_data(s, parse_state(query_params(request)))))


# ---------------------------------------------------------------- ① 机械手录（§5.2.5 ③）


@router.post("/m06/mech")
async def mech_save(request: Request):
    """保存某「核算月 × 项目」的**机械 6 列手录值**（两段都可录；**负数拒绝且不写库**）。

    ⚠️ 手录值落**旁路载体** ⇒ 重抓 i8 / 重导历史**都不覆盖它**（§5.2.5 ③）。
    """
    form = await request.form()
    warehouse = str(form.get("pj") or "").strip()
    tab = str(form.get("tab") or "").strip()
    ym = D.normalize_ym(form.get("ym"))
    back = "/m06?" + urlencode({"pj": warehouse, "tab": tab})

    def _fail(message: str) -> RedirectResponse:
        return RedirectResponse(back + "&" + urlencode({"msg": message, "msgkind": "err"}),
                                status_code=303)

    if not warehouse:
        return _fail("没有选中项目 —— 先在页面上选一个项目再手录（项目键 = 仓库名）。")
    if not ym:
        return _fail(f"核算月认不出：{form.get('ym') or '（空）'} —— 请写 2026-08 这种形态。")
    try:
        values = mech_ui.parse_mech_values({f"mech_{i}": form.get(f"mech_{i}")
                                            for i in range(len(D.MECH_COLUMNS))})
    except ValueError as exc:
        return _fail(f"未保存：{exc}")

    with session_scope() as s:
        repo.save_mech(s, ym=ym, warehouse=warehouse,
                       values={k: Decimal(v) for k, v in values.items()},
                       project_id=None)
    return RedirectResponse(
        back + "&" + urlencode({"msg": f"已保存 {ym} 的机械 {len(D.MECH_COLUMNS)} 列手录值"
                                       f"（旁路载体，重抓 / 重导都不会覆盖它）",
                                "msgkind": "ok", "mech_ym": ym}),
        status_code=303)


# ---------------------------------------------------------------- ② 历史导入（§5.2.5 ①②）


def _payload(plan: importer.ImportPlan, *, warehouse: str) -> dict:
    """预览结果 → 可暂存的纯数据（**不含密钥**；`batch` 在预览这一刻定死）。"""
    return {
        "warehouse": warehouse,
        "batch": importer.next_batch(),
        "rows": [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in row.items()}
                 for row in plan.rows],
        "anomalies": plan.anomalies,
        "ignored_mech": plan.ignored_mech,
        "unknown_headers": plan.unknown_headers,
        "default_cutoff": plan.default_cutoff,
    }


def _plan_of(payload: dict) -> importer.ImportPlan:
    """暂存结果 → `ImportPlan`（确认时重建；**不重新解析文件**）。"""
    plan = importer.ImportPlan(
        anomalies=list(payload.get("anomalies") or []),
        ignored_mech=list(payload.get("ignored_mech") or []),
        unknown_headers=list(payload.get("unknown_headers") or []),
    )
    for row in payload.get("rows") or []:
        plan.rows.append({k: (Decimal(str(v)) if k != "ym" else str(v)) for k, v in row.items()})
    return plan


@router.get("/m06/import", response_class=HTMLResponse)
def import_page(request: Request):
    """历史导入页（三步走 ＋ 列说明 ＋ 批次清单）。"""
    pj = _one(query_params(request), "pj")
    with session_scope() as s:
        data = build_import_data(s, warehouse=pj)
    return HTMLResponse(render_import_page(data))


@router.post("/m06/import/preview", response_class=HTMLResponse)
async def import_preview(file: UploadFile = File(...), pj: str = Form("")):
    """解析上传的 `.xlsx` → **预览**（⚠️ **一个字节都不写库**）。"""
    try:
        content = await file.read()
        plan = importer.parse_sheet(content)
        with session_scope() as s:
            data = build_import_data(s, warehouse=str(pj or ""))
        if not data["warehouse"]:
            raise MustReportError("还没有可导入的项目 —— 先在「库存单据」页抓一次库存单据明细。")
        token = preview_store.save(_payload(plan, warehouse=data["warehouse"]))
        preview = {
            "writable": plan.writable, "months": plan.months,
            "anomalies": plan.anomalies, "ignored_mech": plan.ignored_mech,
            "unknown_headers": plan.unknown_headers, "default_cutoff": plan.default_cutoff,
            "rows": [{k: (f"{v:.2f}" if isinstance(v, Decimal) else v) for k, v in row.items()}
                     for row in plan.rows],
        }
        return HTMLResponse(render_import_page(data, preview=preview, token=token))
    except MustReportError as exc:
        with session_scope() as s:
            data = build_import_data(s, warehouse=str(pj or ""))
        return HTMLResponse(render_import_page(data, message=exc.message, kind="err"))
    except Exception as exc:                                    # noqa: BLE001
        with session_scope() as s:
            data = build_import_data(s, warehouse=str(pj or ""))
        return HTMLResponse(render_import_page(
            data, message=f"解析失败：{type(exc).__name__}: {exc}", kind="err"))


@router.post("/m06/import/confirm", response_class=HTMLResponse)
def import_confirm(token: str = Form(...), pj: str = Form(""), cutoff_ym: str = Form("")):
    """凭 token 取回解析结果 → **写历史段 ＋ 记批次** → 给**核对报告**。"""
    try:
        payload = preview_store.load(token)
        plan = _plan_of(payload)
        warehouse = str(pj or payload.get("warehouse") or "")
        batch = str(payload.get("batch") or importer.next_batch())
        with session_scope() as s:
            out = importer.commit(s, plan, warehouse=warehouse, batch=batch,
                                  operator=current_operator(), cutoff_ym=cutoff_ym)
            report = importer.check_report(s, warehouse=warehouse, batch_no=out["batch"],
                                           cutoff_ym=out["cutoff_ym"])
            data = build_import_data(s, warehouse=warehouse)
        return HTMLResponse(render_import_page(
            data, report=report,
            message=f"已导入 {out['rows']} 个月（批次 {out['batch']}）· 截止核算月 "
                    f"{out['cutoff_ym'] or '（空）'} —— 历史段材料列改用本批快照；正式段未受影响",
            kind="ok"))
    except MustReportError as exc:
        with session_scope() as s:
            data = build_import_data(s, warehouse=str(pj or ""))
        return HTMLResponse(render_import_page(data, message=exc.message, kind="err"))
    except Exception as exc:                                    # noqa: BLE001
        with session_scope() as s:
            data = build_import_data(s, warehouse=str(pj or ""))
        return HTMLResponse(render_import_page(
            data, message=f"导入失败：{type(exc).__name__}: {exc}", kind="err"))


@router.post("/m06/import/rollback", response_class=HTMLResponse)
def import_rollback(batch: str = Form(...), pj: str = Form("")):
    """**整批回滚**（置 `rolled_back` ＋ 留痕，**不物理删**）→ 再给核对报告。"""
    try:
        with session_scope() as s:
            count = importer.rollback(s, batch_no=batch)
            data = build_import_data(s, warehouse=str(pj or ""))
            cutoff = data["cutoff_ym"]
            report = importer.check_report(s, warehouse=data["warehouse"], batch_no=batch,
                                           cutoff_ym=cutoff)
        return HTMLResponse(render_import_page(
            data, report=report,
            message=f"批次 {batch} 已整批回滚：{count} 行不再计入历史段（留痕、未物理删）"
                    f"—— 可以重新上传修正后的文件",
            kind="wn"))
    except MustReportError as exc:
        with session_scope() as s:
            data = build_import_data(s, warehouse=str(pj or ""))
        return HTMLResponse(render_import_page(data, message=exc.message, kind="err"))
    except Exception as exc:                                    # noqa: BLE001
        with session_scope() as s:
            data = build_import_data(s, warehouse=str(pj or ""))
        return HTMLResponse(render_import_page(
            data, message=f"回滚失败：{type(exc).__name__}: {exc}", kind="err"))


# ============================================================ JSON API（前端壳：原型直接接数据）


@router.get("/api/m06/mech")
def api_mech() -> dict:
    """机械 6 列手录值（**全量**）→ 按「仓库名 → 核算月 → [6 列]」聚合。

    ⭐ **出参形状刻意与原型 `MACH6` 一致** ⇒ 壳里那十几处引用（过程资料 17 列的机械 6 列 /
    活动大表 / 机械结算 / 台账项目候选）**一行不用改**，只换数据来源。

    ⚠️ 机械费是**旁路载体**（`proc_mech_manual`）：重抓 i8 / 重导历史**都不覆盖它**（§5.2.5 ③）。
    ⭐ 本表是 **`m05` 机械欠款的结算源** —— 接上它，`m05` 的「机械欠款」才会从 0 变成真数。
    """
    with session_scope() as s:
        rows = repo.load_mech(s)

    out: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        wh = str(r.get("warehouse") or "").strip()
        ym = str(r.get("ym") or "").strip()
        if not wh or not ym:
            continue                      # 键不全的行落不到任何项目/月份上（真库里不会有）
        vals = []
        for i in range(len(D.MECH_COLUMNS)):
            try:
                vals.append(round(float(r.get(f"mech_{i}") or 0), 2))
            except (TypeError, ValueError):
                vals.append(0.0)
        out.setdefault(wh, {})[ym] = vals
    return {"mech": out, "count": len(rows), "columns": list(D.MECH_COLUMNS)}


__all__ = ["router"]
