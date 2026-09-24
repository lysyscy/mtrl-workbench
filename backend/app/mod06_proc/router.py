"""`MOD-06` 路由：过程资料页（`/m06`）＋ **机械手录**（`/m06/mech`）＋ **历史导入三步**（`/m06/import*`）。

⚠️ 只读页面：**材料列没有写路径**（§5.2.3 单向流）—— 要改材料数据回 `/m08` 打调整单。
⚠️ 本模块**只有两条写路径**：① **机械手录**（`/m06/mech` → 旁路表，两段都可录，§5.2.5 ③）
   ② **历史导入**（`/m06/import/*` → 只写历史段快照，§5.2.5 ①②）。
⚠️ 写操作一律 **PRG**（POST → 303 → GET）或就地回显；校验失败**一个字都不写库**。
⚠️ 查询参数的解析出口与 `MOD-08` 共用（`query_params`），不各写一份。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.import_kit.api import build_router as build_imp_router
from app.mod06_proc import domain as D
from app.mod06_proc import imp_spec
from app.mod06_proc import mech_ui, repository as repo
# ⚠️ 历史导入三步（§5.2.5 ①②）的**沿革**（别再往回搬）：
#    2026-09-21（`§19` 收口）三条 PRG ＋ `import_view.py` ⇒ 搬成 JSON API `import_api.py`；
#    2026-09-22/23（`TAIL-75` `B5c`/`B5c-2`）⇒ 旧页与 `import_api.py`**全部退休**，
#    过程资料的导入**只走通用导入面** `/api/imp/m06_proc/*`（见下面 ② 段）。
from app.mod06_proc.service import build_page_data, parse_state
# ⚠️ 2026-09-18（`§19` 批 2）：`app.mod06_proc.view`（`render_proc_page`/`render_export_preview`）
#    的导入已随"过程资料页半边"删除 —— ⛔ 别再加回来（那两个渲染件已整体删除）。
from app.mod08_inv.router import query_params

router = APIRouter(tags=["mod06"])

MESSAGE_KINDS = ("ok", "wn", "err")


# ⚠️ `MESSAGE_KINDS` 与 `_one` 现在只剩「历史导入」那几个 PRG 在用（过程资料页半边已删）。
def _one(params: dict, name: str, default: str = "") -> str:
    value = params.get(name, default)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


# ⚠️ 2026-09-18（`TAIL-27` · `§19` **批 2**）：**过程资料页半边已删**（授权 `D18`）——
#    `proc_page`（`GET /m06`）与 `proc_export`（`GET /m06/export` 的清单预览页）都已删除；
#    导出**真下载**走 `/api/m06/export`（壳在用 ✓，保留）。
#    ⚠️ **本文件的「历史导入」半边仍在**：`GET /m06/import` ＋ `preview|confirm|rollback` 三个 PRG ——
#       壳里**没有任何 `m06/import` 引用**（实测）⇒ 那是全站**唯一**的导入入口 ⇒ **暂留**（前置未满足：
#       要删得先给壳一个"历史导入"入口）。（同 `m14` 的设置页：能力只在旧页，删了就没了。）


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

    from app.report_export import service as EX

    params = query_params(request)
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


# ⚠️ 2026-09-18（`§19` 批 2）：**PRG 版机械手录已删**（`POST /m06/mech` ＋ `mech_save`）——
#    壳走的是 JSON 版 `POST /api/m06/mech`（与它**同一份判定** `mech_ui.parse_mech_values`
#    ＋ `repo.save_mech` ✓，见本文件下方）。⛔ 别把"机械手录"整条当成没实现。
# ---------------------------------------------------------------- ① 机械手录（§5.2.5 ③）


# ---------------------------------------------------------------- ② 导入（§5.2.5 ①②）＝ **只走通用导入面**
#
# ⚠️ 2026-09-23（`TAIL-75` `B5c-2`）：`/api/m06/import/{data,meta,parse,confirm,rollback}` 五条
#    **已全部退休**（`import_api.py` 连件删除）—— 过程资料的导入**只剩这一条路**：
#      · 解析 / 建议 / 记忆 / 预览 / 暂存 = `import_kit`（通用层）；
#      · 落库 / 回滚 = 域钩子 `imp_spec.commit/rollback`（**原样调 `importer.commit`** →
#        `repository.import_snapshot`，⛔ 不是第二套落库）；
#      · 候选项目 / 截止月 / 批次 = 域钩子 `imp_spec.options` ⇒ `GET /api/imp/m06_proc/options`。
#    ⛔ 别再往本文件加导入路由（`D18` 口径 ＋ "同一件事不留两个入口"）。
router.include_router(build_imp_router(imp_spec.SPEC, imp_spec.HOOKS))


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


class MechSaveRequest(BaseModel):
    """手录机械 6 列（项目键 = 仓库名；`ym` = 核算月；`values` = `{mech_0…mech_5: 原值}`）。"""

    warehouse: str = ""
    ym: str = ""
    values: dict[str, Any] = {}


@router.post("/api/m06/mech")
def api_mech_save(req: MechSaveRequest) -> dict:
    """⭐ **`TAIL-38`：「录机械费」的写入口** —— 壳侧面板（原型 `V.m06` 没画这个入口，§5.2.5 ③）。

    ⚠️ 校验**唯一出口 = `mech_ui.parse_mech_values`**（空 ⇒ 0；非数字 / 负数 ⇒ 拒）——
      与 PRG 端点（`POST /m06/mech`）**同一份判定**，⛔ 不在本层另写一套。

    ⚠️ 手录值落**旁路载体**（`proc_mech_manual`）⇒ 重抓 i8 / 重导历史**都不覆盖它**（§5.2.5 ③）。
    ⚠️ 失败 **抛 `MustReportError`** ⇒ 400 ＋ 原样原因（壳侧把它给用户，不静默）。
    """
    warehouse = str(req.warehouse or "").strip()
    if not warehouse:
        raise MustReportError("没有选中项目 —— 项目键 = 仓库名。")
    ym = D.normalize_ym(req.ym)
    if not ym:
        raise MustReportError(f"核算月认不出：{req.ym or '（空）'} —— 请写 2026-08 这种形态。")
    try:
        values = mech_ui.parse_mech_values(req.values)
    except ValueError as exc:
        raise MustReportError(f"未保存：{exc}") from exc

    with session_scope() as s:
        repo.save_mech(s, ym=ym, warehouse=warehouse,
                       values={k: Decimal(v) for k, v in values.items()},
                       project_id=None)
    return {
        "ok": True, "ym": ym, "warehouse": warehouse,
        "columns": list(D.MECH_COLUMNS),
        "message": f"已保存 {ym} 的机械 {len(D.MECH_COLUMNS)} 列手录值"
                   "（旁路载体，重抓 / 重导都不会覆盖它）",
    }


__all__ = ["router"]
